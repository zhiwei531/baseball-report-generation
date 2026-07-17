from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2

from point_mappings import POSE_CORE_LANDMARKS, POSE_OVERLAY_CONNECTIONS

CONNECTIONS = list(POSE_OVERLAY_CONNECTIONS)
CORE = set(POSE_CORE_LANDMARKS)


def fnum(value: str) -> float | None:
    if value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_pose(path: Path, min_visibility: float) -> dict[int, dict[str, tuple[int, int, float]]]:
    frames: dict[int, dict[str, tuple[int, int, float]]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            x = fnum(row["x_px"])
            y = fnum(row["y_px"])
            visibility = fnum(row["visibility"])
            if x is None or y is None or visibility is None or visibility < min_visibility:
                continue
            frames[int(row["frame_index"])][row["landmark"]] = (round(x), round(y), visibility)
    return frames


def draw_label(frame: Any, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    x, y = origin
    font = cv2.FONT_HERSHEY_SIMPLEX
    scale = 0.58
    thickness = 2
    (w, h), baseline = cv2.getTextSize(text, font, scale, thickness)
    cv2.rectangle(frame, (x - 8, y - h - baseline - 8), (x + w + 8, y + 8), (18, 24, 32), -1)
    cv2.putText(frame, text, (x, y), font, scale, color, thickness, cv2.LINE_AA)


def render_overlay(
    *,
    video_path: Path,
    pose_path: Path,
    summary_path: Path,
    output_path: Path,
    preview_path: Path | None,
    min_visibility: float,
    show_alignment_metadata: bool,
) -> dict[str, Any]:
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    poses = load_pose(pose_path, min_visibility)

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or summary["video_meta"]["fps"])
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(
        str(output_path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output video: {output_path}")

    event_frame = int(summary["video_event"]["frame_index"])
    vicon_event_frame = int(summary["vicon_event"]["frame_index"])
    vicon_rate_hz = float(summary["vicon_meta"]["rate_hz"])
    alignment = summary["alignment"]
    offset = float(
        alignment.get(
            "time_offset_sec_add_to_scaled_vicon_time",
            alignment.get("time_offset_sec_add_to_vicon_time", 0.0),
        )
    )
    capture_fps = float(alignment.get("video_capture_fps", fps))
    slow_factor = float(alignment.get("slow_motion_factor", capture_fps / fps if fps else 1.0))
    written = 0
    detected_frames = 0
    frame_index = 0
    preview_written = False
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        landmarks = poses.get(frame_index, {})
        if landmarks:
            detected_frames += 1
        for a, b in CONNECTIONS:
            if a in landmarks and b in landmarks:
                color = (60, 225, 255) if a in CORE or b in CORE else (60, 170, 255)
                cv2.line(frame, landmarks[a][:2], landmarks[b][:2], color, 3, cv2.LINE_AA)
        for name, (x, y, visibility) in landmarks.items():
            radius = 5 if name in CORE else 4
            color = (40, 230, 90) if visibility >= 0.75 else (0, 215, 255)
            cv2.circle(frame, (x, y), radius + 2, (255, 255, 255), -1, cv2.LINE_AA)
            cv2.circle(frame, (x, y), radius, color, -1, cv2.LINE_AA)

        if show_alignment_metadata:
            timestamp = frame_index / fps
            vicon_frame = vicon_event_frame + (frame_index - event_frame) * vicon_rate_hz / capture_fps
            vicon_time = vicon_frame / vicon_rate_hz
            draw_label(frame, f"aligned 2D skeleton | frame {frame_index} | {timestamp:.2f}s", (24, 34), (230, 245, 255))
            draw_label(
                frame,
                f"capture fps {capture_fps:.2f} | slow factor {slow_factor:.2f}x | offset {offset:.3f}s",
                (24, 70),
                (180, 220, 255),
            )
            draw_label(frame, f"mapped Vicon frame {vicon_frame:.1f} | {vicon_time:.3f}s", (24, 106), (180, 255, 210))
            if abs(frame_index - event_frame) <= 2:
                cv2.rectangle(frame, (0, 0), (width - 1, height - 1), (0, 170, 255), 8)
                draw_label(
                    frame,
                    f"ALIGN EVENT: 2D wrist peak frame {event_frame} = Vicon bat peak frame {vicon_event_frame}",
                    (24, height - 28),
                    (0, 220, 255),
                )
        if preview_path is not None and not preview_written and frame_index == event_frame:
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(preview_path), frame)
            preview_written = True
        writer.write(frame)
        written += 1
        frame_index += 1

    cap.release()
    writer.release()
    if preview_path is not None and not preview_written:
        cap = cv2.VideoCapture(str(output_path))
        ok, frame = cap.read()
        if ok:
            preview_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(preview_path), frame)
            preview_written = True
        cap.release()
    return {
        "output": str(output_path),
        "preview": str(preview_path) if preview_path is not None else None,
        "frames_written": written,
        "video_frames_meta": frame_count,
        "fps": fps,
        "pose_frames_with_landmarks": detected_frames,
        "event_frame": event_frame,
        "preview_written": preview_written,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Render the aligned MediaPipe 2D skeleton overlay video.")
    parser.add_argument("--summary", required=True, type=Path)
    parser.add_argument("--pose", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--preview", type=Path, default=None)
    parser.add_argument("--min-visibility", type=float, default=0.2)
    parser.add_argument(
        "--show-alignment-metadata",
        action="store_true",
        help="Draw QA-only alignment labels and event border. The default is a clean skeleton-only overlay.",
    )
    args = parser.parse_args()
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    result = render_overlay(
        video_path=Path(summary["video"]),
        pose_path=args.pose,
        summary_path=args.summary,
        output_path=args.out,
        preview_path=args.preview,
        min_visibility=args.min_visibility,
        show_alignment_metadata=args.show_alignment_metadata,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
