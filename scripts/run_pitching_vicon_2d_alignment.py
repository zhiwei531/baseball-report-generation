from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print("RUN", subprocess.list2cmdline(command))
    subprocess.run(command, check=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the pitching 2D-video/Vicon alignment path: action-specific clock sync, "
            "MediaPipe pose extraction, frame mapping, and aligned skeleton rendering."
        )
    )
    parser.add_argument("--video", required=True, type=Path, help="Raw sideline pitching video.")
    parser.add_argument("--c3d", required=True, type=Path, help="Matching pitching C3D trial.")
    parser.add_argument(
        "--model",
        required=True,
        type=Path,
        help="MediaPipe Pose Landmarker .task model, for example pose_landmarker_heavy.task.",
    )
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument(
        "--video-capture-fps",
        type=float,
        default=None,
        help="Actual camera capture FPS when the file is encoded as slow motion.",
    )
    parser.add_argument(
        "--video-event-frame",
        type=int,
        default=None,
        help="Optional manually reviewed pitching release frame override.",
    )
    parser.add_argument("--min-visibility", type=float, default=0.2)
    parser.add_argument("--skip-overlay", action="store_true", help="Skip the aligned skeleton MP4 render.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video = args.video.resolve()
    c3d = args.c3d.resolve()
    model = args.model.resolve()
    out_dir = args.out_dir.resolve()
    for required in (video, c3d, model):
        if not required.exists():
            raise FileNotFoundError(required)

    sync_script = SCRIPT_DIR / "sync_vicon_video.py"
    align_script = SCRIPT_DIR / "align_2d_video_vicon.py"
    render_script = SCRIPT_DIR / "render_aligned_2d_overlay.py"
    metric_reader = SCRIPT_DIR / "build_vicon_2026_metrics.py"
    for required in (sync_script, align_script, render_script, metric_reader):
        if not required.exists():
            raise FileNotFoundError(f"Required companion script is missing: {required}")

    sync_dir = out_dir / "sync"
    alignment_dir = out_dir / "alignment"
    sync_dir.mkdir(parents=True, exist_ok=True)
    alignment_dir.mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            str(sync_script),
            "--pair",
            "pitch",
            str(video),
            str(c3d),
            "--output-dir",
            str(sync_dir),
        ]
    )

    align_command = [
        sys.executable,
        str(align_script),
        "--video",
        str(video),
        "--c3d",
        str(c3d),
        "--model",
        str(model),
        "--out-dir",
        str(alignment_dir),
    ]
    if args.video_capture_fps is not None:
        align_command.extend(["--video-capture-fps", str(args.video_capture_fps)])
    if args.video_event_frame is not None:
        align_command.extend(["--video-event-frame", str(args.video_event_frame)])
    run(align_command)

    overlay = alignment_dir / "aligned_2d_skeleton_overlay.mp4"
    if not args.skip_overlay:
        run(
            [
                sys.executable,
                str(render_script),
                "--summary",
                str(alignment_dir / "alignment_summary.json"),
                "--pose",
                str(alignment_dir / "pose2d_landmarks.csv"),
                "--out",
                str(overlay),
                "--min-visibility",
                str(args.min_visibility),
            ]
        )

    manifest = {
        "kind": "pitch",
        "video": str(video),
        "c3d": str(c3d),
        "mediapipe_model": str(model),
        "clock_sync": str(sync_dir / "vicon_video_sync.json"),
        "alignment_summary": str(alignment_dir / "alignment_summary.json"),
        "pose2d_landmarks": str(alignment_dir / "pose2d_landmarks.csv"),
        "vicon_points_aligned_to_video": str(alignment_dir / "vicon_points_aligned_to_video.csv"),
        "aligned_overlay": None if args.skip_overlay else str(overlay),
        "mapping_note": "C3D is the master clock; verify the release frame manually for publication use.",
    }
    manifest_path = out_dir / "pitching_alignment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
