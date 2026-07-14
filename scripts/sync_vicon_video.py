from __future__ import annotations

import argparse
import csv
import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

try:
    import cv2  # type: ignore
except Exception:  # pragma: no cover - optional dependency guard
    cv2 = None

try:
    import numpy as np
except Exception as exc:  # pragma: no cover
    raise RuntimeError("sync_vicon_video.py requires numpy") from exc


@dataclass
class C3DData:
    path: Path
    fps: float
    first_frame: int
    labels: list[str]
    points_mm: np.ndarray  # frames x markers x xyz


@dataclass
class SyncResult:
    action: str
    video_path: str
    c3d_path: str
    video_fps: float | None
    video_frames: int | None
    c3d_fps: float
    c3d_frames: int
    video_anchor_frame: int | None
    video_anchor_time_sec: float | None
    c3d_anchor_index: int
    c3d_anchor_frame: int
    c3d_anchor_time_sec: float
    video_to_c3d_offset_sec: float | None
    confidence: str
    method: str


def u16(buffer: bytes, offset: int) -> int:
    return struct.unpack_from("<H", buffer, offset)[0]


def i16(buffer: bytes, offset: int) -> int:
    return struct.unpack_from("<h", buffer, offset)[0]


def f32(buffer: bytes, offset: int) -> float:
    return struct.unpack_from("<f", buffer, offset)[0]


def clean_label(value: str) -> str:
    return value.strip().replace("\x00", "")


def parse_c3d(path: Path) -> C3DData:
    raw = path.read_bytes()
    if len(raw) < 1024 or raw[1] != 80:
        raise ValueError(f"Not a C3D file or unsupported header: {path}")

    param_block = raw[0]
    point_count = u16(raw, 2)
    first_frame = u16(raw, 6)
    last_frame = u16(raw, 8)
    scale = f32(raw, 12)
    data_block = u16(raw, 16)
    fps_header = f32(raw, 20)
    frame_count = last_frame - first_frame + 1
    if point_count <= 0 or frame_count <= 0:
        raise ValueError(f"C3D has no point frames: {path}")

    labels, point_rate = parse_c3d_parameters(raw, param_block)
    if not labels:
        labels = [f"P{i + 1}" for i in range(point_count)]
    if len(labels) < point_count:
        labels.extend(f"P{i + 1}" for i in range(len(labels), point_count))
    labels = labels[:point_count]

    # Negative scale means floating point data. The Bryan files use float32 mm.
    if scale >= 0:
        raise ValueError("Only floating-point C3D point storage is supported in this sync script")
    start = (data_block - 1) * 512
    values_per_frame = point_count * 4
    needed = frame_count * values_per_frame * 4
    if start + needed > len(raw):
        frame_count = max(0, (len(raw) - start) // (values_per_frame * 4))
    arr = np.frombuffer(raw, dtype="<f4", count=frame_count * values_per_frame, offset=start)
    arr = arr.reshape(frame_count, point_count, 4)
    points = arr[:, :, :3].astype(np.float64)
    residual = arr[:, :, 3]
    points[~np.isfinite(points)] = np.nan
    points[residual < 0, :] = np.nan

    return C3DData(
        path=path,
        fps=float(point_rate or fps_header),
        first_frame=first_frame,
        labels=labels,
        points_mm=points,
    )


def parse_c3d_parameters(raw: bytes, param_block: int) -> tuple[list[str], float | None]:
    p = (param_block - 1) * 512 + 4
    groups: dict[int, str] = {}
    labels: list[str] = []
    point_rate: float | None = None
    for _ in range(10000):
        if p + 4 > len(raw):
            break
        name_len = struct.unpack_from("b", raw, p)[0]
        if name_len == 0:
            break
        group_id = struct.unpack_from("b", raw, p + 1)[0]
        nabs = abs(name_len)
        name = raw[p + 2 : p + 2 + nabs].decode("latin1", "replace").strip()
        next_offset_pos = p + 2 + nabs
        next_offset = i16(raw, next_offset_pos)
        if next_offset <= 0:
            break
        data_offset = next_offset_pos + 2
        end = next_offset_pos + next_offset
        if group_id < 0:
            groups[-group_id] = name
        elif data_offset + 2 <= end:
            group = groups.get(group_id, str(group_id)).upper()
            param = name.upper()
            dtype = struct.unpack_from("b", raw, data_offset)[0]
            dim_count = raw[data_offset + 1]
            dims = list(raw[data_offset + 2 : data_offset + 2 + dim_count])
            value_offset = data_offset + 2 + dim_count
            total = 1
            for d in dims:
                total *= max(1, d)
            byte_count = abs(dtype) * total
            value_raw = raw[value_offset : value_offset + byte_count]
            if group == "POINT" and param == "LABELS" and dtype == -1 and len(dims) >= 2:
                width, count = dims[0], dims[1]
                labels = [clean_label(value_raw[i * width : (i + 1) * width].decode("latin1", "replace")) for i in range(count)]
            elif group == "POINT" and param == "RATE" and dtype == 4 and len(value_raw) >= 4:
                point_rate = struct.unpack_from("<f", value_raw, 0)[0]
        p = end
    return labels, point_rate


def marker_indices(labels: list[str], suffixes: Iterable[str]) -> list[int]:
    suffixes_lower = tuple(s.lower() for s in suffixes)
    hits = []
    for index, label in enumerate(labels):
        lower = label.lower()
        plain = lower.split(":")[-1]
        if lower.endswith(suffixes_lower) or plain.endswith(suffixes_lower):
            hits.append(index)
    return hits


def fill_nan(points: np.ndarray) -> np.ndarray:
    out = np.asarray(points, dtype=np.float64).copy()
    if out.ndim == 1:
        out = out[:, None]
    for dim in range(out.shape[1]):
        series = out[:, dim]
        ok = np.isfinite(series)
        if ok.sum() == 0:
            series[:] = 0.0
        elif ok.sum() == 1:
            series[:] = series[ok][0]
        else:
            series[:] = np.interp(np.arange(len(series)), np.where(ok)[0], series[ok])
    return out


def smooth(values: np.ndarray, kernel_size: int = 9) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    if len(arr) < 5:
        return arr
    kernel_size = min(kernel_size, len(arr) if len(arr) % 2 else len(arr) - 1)
    kernel_size = max(3, kernel_size)
    x = np.linspace(-2.0, 2.0, kernel_size)
    kernel = np.exp(-0.5 * x * x)
    kernel /= kernel.sum()
    pad = kernel_size // 2
    return np.convolve(np.pad(arr, (pad, pad), mode="edge"), kernel, mode="valid")


def speed_kmh(points_mm: np.ndarray, fps: float) -> np.ndarray:
    p = fill_nan(points_mm)
    velocity = np.zeros(len(p), dtype=np.float64)
    if len(p) > 1:
        velocity[1:] = np.linalg.norm(np.diff(p, axis=0), axis=1) / 1000.0 * fps * 3.6
    return smooth(velocity)


def c3d_sync_signal(data: C3DData, action: str) -> tuple[np.ndarray, int, str]:
    if action == "bat":
        candidates = marker_indices(data.labels, ["bat1", "bat2", "bat3", "bat4", "bat5"])
        if not candidates:
            raise ValueError("No bat markers found in C3D")
        speeds = [(idx, speed_kmh(data.points_mm[:, idx, :], data.fps)) for idx in candidates]
        idx, signal = max(speeds, key=lambda item: float(np.nanpercentile(item[1], 98)))
        return normalize_signal(signal), int(np.nanargmax(signal)), f"bat marker speed peak: {data.labels[idx]}"

    if action == "pitch":
        # Prefer right-hand markers, but fall back to the fastest wrist/finger marker.
        candidates = marker_indices(data.labels, ["rfin", "rwra", "rwrb", "relb", "lfin", "lwra", "lwrb"])
        if not candidates:
            raise ValueError("No hand markers found in C3D")
        speeds = [(idx, speed_kmh(data.points_mm[:, idx, :], data.fps)) for idx in candidates]
        idx, signal = max(speeds, key=lambda item: float(np.nanpercentile(item[1], 98)))
        return normalize_signal(signal), int(np.nanargmax(signal)), f"throwing hand speed peak: {data.labels[idx]}"

    raise ValueError(f"Unknown action: {action}")


def normalize_signal(values: np.ndarray) -> np.ndarray:
    arr = np.asarray(values, dtype=np.float64)
    arr = fill_nan(arr).reshape(-1)
    lo, hi = np.percentile(arr, [5, 95]) if len(arr) else (0.0, 1.0)
    span = max(float(hi - lo), 1e-9)
    arr = np.clip((arr - lo) / span, 0.0, 1.0)
    return smooth(arr)


def video_motion_signal(path: Path, sample_width: int = 320) -> tuple[np.ndarray, float, int, dict[str, int | float]]:
    if cv2 is None:
        raise RuntimeError("OpenCV is not available. Install opencv-python to extract the 2D video sync curve.")
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {path}")
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    prev = None
    values: list[float] = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame.shape[1] != sample_width:
            scale = sample_width / float(frame.shape[1])
            frame = cv2.resize(frame, (sample_width, max(1, int(frame.shape[0] * scale))))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)
        if prev is None:
            values.append(0.0)
        else:
            diff = cv2.absdiff(gray, prev)
            # Robust motion energy: focus on top motion pixels so background noise matters less.
            flat = diff.reshape(-1).astype(np.float32)
            cutoff = np.percentile(flat, 85)
            active = flat[flat >= cutoff]
            values.append(float(active.mean() if len(active) else flat.mean()))
        prev = gray
    cap.release()
    signal = normalize_signal(np.asarray(values, dtype=np.float64))
    meta = {"width": width, "height": height, "frames": frame_count or len(values), "fps": fps}
    return signal, fps, len(values), meta


def best_offset_by_correlation(video_signal: np.ndarray, vicon_signal: np.ndarray, video_fps: float, vicon_fps: float) -> tuple[float, float]:
    if len(video_signal) < 3 or len(vicon_signal) < 3:
        return 0.0, 0.0
    target_fps = 100.0
    v_times = np.arange(len(video_signal)) / video_fps
    c_times = np.arange(len(vicon_signal)) / vicon_fps
    end = min(v_times[-1], c_times[-1])
    grid = np.arange(0, end, 1.0 / target_fps)
    if len(grid) < 5:
        return 0.0, 0.0
    v = np.interp(grid, v_times, video_signal)
    c = np.interp(grid, c_times, vicon_signal)
    v = (v - v.mean()) / (v.std() + 1e-9)
    c = (c - c.mean()) / (c.std() + 1e-9)
    corr = np.correlate(c, v, mode="full")
    lag = int(np.argmax(corr) - (len(v) - 1))
    coeff = float(np.max(corr) / max(len(v), 1))
    # Positive offset means add this many seconds to video time to get Vicon time.
    return lag / target_fps, coeff


def sync_one(action: str, video_path: Path, c3d_path: Path, output_dir: Path | None = None) -> SyncResult:
    c3d = parse_c3d(c3d_path)
    vicon_signal, c3d_anchor_index, method = c3d_sync_signal(c3d, action)
    c3d_anchor_time = c3d_anchor_index / c3d.fps
    video_anchor_frame = None
    video_anchor_time = None
    offset = None
    confidence = "c3d_event_only"
    video_fps = None
    video_frames = None
    video_signal = None

    if cv2 is not None and video_path.exists():
        try:
            video_signal, video_fps, video_frames, _meta = video_motion_signal(video_path)
            video_anchor_frame = int(np.nanargmax(video_signal))
            video_anchor_time = video_anchor_frame / video_fps
            peak_offset = c3d_anchor_time - video_anchor_time
            corr_offset, corr_score = best_offset_by_correlation(video_signal, vicon_signal, video_fps, c3d.fps)
            # Peak alignment is the priority for explosive baseball actions; correlation is a sanity check.
            offset = peak_offset
            confidence = "high" if abs(corr_offset - peak_offset) < 0.25 or corr_score > 0.35 else "medium_check_peak_manually"
            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                write_signal_csv(output_dir / f"{action}_sync_signals.csv", video_signal, video_fps, vicon_signal, c3d.fps)
        except Exception as exc:
            confidence = f"c3d_event_only_video_error: {exc}"

    return SyncResult(
        action=action,
        video_path=str(video_path),
        c3d_path=str(c3d_path),
        video_fps=video_fps,
        video_frames=video_frames,
        c3d_fps=c3d.fps,
        c3d_frames=len(c3d.points_mm),
        video_anchor_frame=video_anchor_frame,
        video_anchor_time_sec=video_anchor_time,
        c3d_anchor_index=c3d_anchor_index,
        c3d_anchor_frame=c3d.first_frame + c3d_anchor_index,
        c3d_anchor_time_sec=c3d_anchor_time,
        video_to_c3d_offset_sec=offset,
        confidence=confidence,
        method=method,
    )


def write_signal_csv(path: Path, video_signal: np.ndarray, video_fps: float, vicon_signal: np.ndarray, vicon_fps: float) -> None:
    max_len = max(len(video_signal), len(vicon_signal))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["index", "video_time_sec", "video_motion", "vicon_time_sec", "vicon_motion"])
        for index in range(max_len):
            writer.writerow([
                index,
                index / video_fps if index < len(video_signal) else "",
                float(video_signal[index]) if index < len(video_signal) else "",
                index / vicon_fps if index < len(vicon_signal) else "",
                float(vicon_signal[index]) if index < len(vicon_signal) else "",
            ])


def result_to_dict(result: SyncResult) -> dict[str, object]:
    return {
        "action": result.action,
        "video_path": result.video_path,
        "c3d_path": result.c3d_path,
        "video_fps": result.video_fps,
        "video_frames": result.video_frames,
        "c3d_fps": result.c3d_fps,
        "c3d_frames": result.c3d_frames,
        "video_anchor_frame": result.video_anchor_frame,
        "video_anchor_time_sec": result.video_anchor_time_sec,
        "c3d_anchor_index": result.c3d_anchor_index,
        "c3d_anchor_frame": result.c3d_anchor_frame,
        "c3d_anchor_time_sec": result.c3d_anchor_time_sec,
        "video_to_c3d_offset_sec": result.video_to_c3d_offset_sec,
        "mapping_formula": "vicon_time_sec = video_time_sec + video_to_c3d_offset_sec" if result.video_to_c3d_offset_sec is not None else "video dependency missing; use C3D anchor only",
        "confidence": result.confidence,
        "method": result.method,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize one or more sideline 2D videos to Vicon C3D timing.")
    parser.add_argument(
        "--pair",
        action="append",
        nargs=3,
        required=True,
        metavar=("ACTION", "VIDEO", "C3D"),
        help="Repeatable triplet. ACTION must be 'bat' or 'pitch'.",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/vicon_video_sync"))
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for action, video_text, c3d_text in args.pair:
        if action not in {"bat", "pitch"}:
            parser.error(f"Unknown action '{action}'; expected bat or pitch")
        video_path = Path(video_text).resolve()
        c3d_path = Path(c3d_text).resolve()
        if not video_path.exists():
            parser.error(f"Video not found: {video_path}")
        if not c3d_path.exists():
            parser.error(f"C3D not found: {c3d_path}")
        results.append(sync_one(action, video_path, c3d_path, args.output_dir))
    payload = {
        "algorithm_priority": "C3D master clock + action-specific peak alignment + correlation sanity check",
        "notes": [
            "Batting uses the Vicon bat-marker speed peak as the anchor.",
            "Pitching uses the Vicon throwing-hand speed peak as the anchor.",
            "When OpenCV is available, the video anchor is the peak of sideline motion energy.",
            "The final mapping is vicon_time_sec = video_time_sec + offset_sec.",
        ],
        "results": [result_to_dict(r) for r in results],
    }
    out_json = args.output_dir / "vicon_video_sync.json"
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nWrote {out_json}")


if __name__ == "__main__":
    main()
