from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python import vision


ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = ROOT.parents[0]
DEFAULT_MODEL = PROJECT_ROOT / "models" / "pose_landmarker_heavy.task"
DEFAULT_OUT = PROJECT_ROOT / "outputs" / "aligned_2d_vicon"

SCRIPTS_DIR = PROJECT_ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from build_vicon_2026_metrics import (  # noqa: E402
    all_point_rows,
    clean_label,
    key_action_frame,
    read_c3d,
    reconstruction_point_names,
)


LANDMARK_NAMES = [
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
]


def open_video(path: Path) -> tuple[cv2.VideoCapture, int, int, float, int]:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    return cap, width, height, fps, frames


def detect_2d(video_path: Path, model_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not model_path.exists():
        raise FileNotFoundError(f"MediaPipe task model not found: {model_path}")

    cap, width, height, fps, frame_count = open_video(video_path)
    options = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(model_path), delegate=BaseOptions.Delegate.CPU),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.45,
        min_pose_presence_confidence=0.45,
        min_tracking_confidence=0.55,
        output_segmentation_masks=False,
    )

    rows: list[dict[str, Any]] = []
    with vision.PoseLandmarker.create_from_options(options) as detector:
        frame_index = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            timestamp_ms = int(round(frame_index / fps * 1000.0))
            result = detector.detect_for_video(mp_image, timestamp_ms)
            landmarks = result.pose_landmarks[0] if result.pose_landmarks else None
            for idx, name in enumerate(LANDMARK_NAMES):
                lm = landmarks[idx] if landmarks else None
                rows.append(
                    {
                        "frame_index": frame_index,
                        "timestamp_sec": frame_index / fps,
                        "landmark": name,
                        "x_norm": lm.x if lm else "",
                        "y_norm": lm.y if lm else "",
                        "z_norm": lm.z if lm else "",
                        "x_px": lm.x * width if lm else "",
                        "y_px": lm.y * height if lm else "",
                        "visibility": getattr(lm, "visibility", "") if lm else "",
                        "presence": getattr(lm, "presence", "") if lm else "",
                    }
                )
            frame_index += 1

    cap.release()
    meta = {
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count_meta": frame_count,
        "frames_read": frame_index,
        "duration_sec": frame_index / fps if fps else None,
    }
    return rows, meta


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def landmark_series(rows: list[dict[str, Any]], landmark: str, key: str) -> np.ndarray:
    values = []
    for row in rows:
        if row["landmark"] != landmark:
            continue
        value = row[key]
        values.append(float(value) if value != "" else np.nan)
    return np.array(values, dtype=float)


def speed_px_s(x: np.ndarray, y: np.ndarray, fps: float) -> np.ndarray:
    diff = np.sqrt(np.diff(x) ** 2 + np.diff(y) ** 2) * fps
    return np.concatenate([[np.nan], diff])


def finite_argmax(values: np.ndarray) -> int:
    if not np.isfinite(values).any():
        return len(values) // 2
    return int(np.nanargmax(values))


def infer_video_event(rows: list[dict[str, Any]], fps: float) -> dict[str, Any]:
    left = speed_px_s(
        landmark_series(rows, "left_wrist", "x_px"),
        landmark_series(rows, "left_wrist", "y_px"),
        fps,
    )
    right = speed_px_s(
        landmark_series(rows, "right_wrist", "x_px"),
        landmark_series(rows, "right_wrist", "y_px"),
        fps,
    )
    combined = np.nanmax(np.vstack([left, right]), axis=0)
    frame = finite_argmax(combined)
    return {
        "frame_index": frame,
        "time_sec": frame / fps,
        "rule": "2d_wrist_peak_speed",
        "peak_speed_px_s": float(combined[frame]) if math.isfinite(float(combined[frame])) else None,
    }


def build_aligned_rows(
    *,
    c3d_rows: list[dict[str, Any]],
    vicon_event_frame: int,
    vicon_rate_hz: float,
    video_event_frame: int,
    video_fps: float,
    video_capture_fps: float,
    video_frame_count: int,
) -> list[dict[str, Any]]:
    video_event_time = video_event_frame / video_fps
    vicon_event_time = vicon_event_frame / vicon_rate_hz
    rows = []
    for row in c3d_rows:
        vicon_time = float(row["timestamp_sec"])
        aligned_time = vicon_time - vicon_event_time
        video_frame = int(round(video_event_frame + aligned_time * video_capture_fps))
        video_time = video_frame / video_fps
        out = dict(row)
        out["vicon_time_from_event_sec"] = aligned_time
        out["aligned_video_playback_time_sec"] = video_time
        out["aligned_video_capture_time_sec"] = video_frame / video_capture_fps
        out["aligned_video_frame_index"] = video_frame
        out["aligned_video_in_range"] = int(0 <= video_frame < video_frame_count)
        out["video_event_frame_index"] = video_event_frame
        out["vicon_event_frame_index"] = vicon_event_frame
        rows.append(out)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Align a 2D video pose timeline with Vicon C3D 3D points.")
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--c3d", required=True, type=Path)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    parser.add_argument(
        "--video-capture-fps",
        type=float,
        default=None,
        help="Actual camera capture rate for slow-motion video. Defaults to encoded playback FPS.",
    )
    parser.add_argument(
        "--video-event-frame",
        type=int,
        default=None,
        help="Override the MediaPipe-derived event frame when the encoded slow-motion video needs manual phase alignment.",
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    trial = read_c3d(args.c3d.resolve())
    vicon_event_frame, vicon_event_label, vicon_event_rule = key_action_frame(trial)
    vicon_rows = all_point_rows(trial)

    pose2d_rows, video_meta = detect_2d(args.video.resolve(), args.model.resolve())
    playback_fps = float(video_meta["fps"])
    video_capture_fps = float(args.video_capture_fps or playback_fps)
    if args.video_event_frame is None:
        video_event = infer_video_event(pose2d_rows, playback_fps)
        video_event["source"] = "mediapipe_pose"
    else:
        video_event = {
            "frame_index": int(args.video_event_frame),
            "time_sec": int(args.video_event_frame) / playback_fps,
            "rule": "manual_slow_motion_phase_frame",
            "source": "user_reviewed_video_frame",
        }
    aligned_rows = build_aligned_rows(
        c3d_rows=vicon_rows,
        vicon_event_frame=vicon_event_frame,
        vicon_rate_hz=trial.rate_hz,
        video_event_frame=int(video_event["frame_index"]),
        video_fps=playback_fps,
        video_capture_fps=video_capture_fps,
        video_frame_count=int(video_meta["frames_read"]),
    )

    write_csv(out_dir / "pose2d_landmarks.csv", pose2d_rows)
    write_csv(out_dir / "vicon_points_aligned_to_video.csv", aligned_rows)

    summary = {
        "video": str(args.video.resolve()),
        "c3d": str(args.c3d.resolve()),
        "model": str(args.model.resolve()),
        "video_meta": video_meta,
        "video_event": video_event,
        "vicon_meta": {
            "rate_hz": trial.rate_hz,
            "frames": int(trial.points.shape[0]),
            "duration_sec": trial.points.shape[0] / trial.rate_hz,
            "units": trial.units,
            "point_count": int(trial.points.shape[1]),
            "reconstruction_points": [name for _, _, name in reconstruction_point_names(trial)],
        },
        "vicon_event": {
            "frame_index": vicon_event_frame,
            "time_sec": vicon_event_frame / trial.rate_hz,
            "label": vicon_event_label,
            "rule": vicon_event_rule,
        },
        "alignment": {
            "method": f"event_zero: Vicon {vicon_event_rule} aligned to video {video_event['rule']}",
            "video_playback_fps": playback_fps,
            "video_capture_fps": video_capture_fps,
            "slow_motion_factor": video_capture_fps / playback_fps,
            "time_offset_sec_add_to_scaled_vicon_time": video_event["time_sec"]
            - (vicon_event_frame / trial.rate_hz) * (video_capture_fps / playback_fps),
            "video_frame_for_vicon_frame_0": int(
                round(int(video_event["frame_index"]) - (vicon_event_frame / trial.rate_hz) * video_capture_fps)
            ),
        },
        "outputs": {
            "pose2d_landmarks": str(out_dir / "pose2d_landmarks.csv"),
            "vicon_points_aligned_to_video": str(out_dir / "vicon_points_aligned_to_video.csv"),
            "summary": str(out_dir / "alignment_summary.json"),
        },
    }
    (out_dir / "alignment_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
