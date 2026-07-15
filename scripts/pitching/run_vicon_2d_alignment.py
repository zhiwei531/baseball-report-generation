from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent


def run(command: list[str]) -> None:
    print("RUN", subprocess.list2cmdline(command))
    subprocess.run(command, check=True)


def require_file(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{label} was not generated: {path}")


def clean_standard_outputs(out_dir: Path) -> None:
    for child in ("sync", "alignment", "comparison"):
        target = out_dir / child
        if target.exists():
            # Finder/Spotlight sidecars can disappear between scandir and
            # unlink on macOS. They are generated-output noise, not inputs.
            try:
                shutil.rmtree(target)
            except FileNotFoundError:
                pass
    manifest = out_dir / "pitching_alignment_manifest.json"
    if manifest.exists():
        manifest.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run the standard pitching 2D video / Vicon alignment QA path with reviewed "
            "slow-motion capture FPS and release-frame anchor."
        )
    )
    parser.add_argument("--video", required=True, type=Path, help="Raw sideline pitching video.")
    parser.add_argument("--c3d", required=True, type=Path, help="Matching pitching C3D trial.")
    parser.add_argument("--model", required=True, type=Path, help="MediaPipe Pose Landmarker .task model.")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--player-slug", required=True, help="Lowercase output slug, e.g. bryan.")
    parser.add_argument("--player-label", required=True, help="Display label used in comparison render titles.")
    parser.add_argument(
        "--video-capture-fps",
        type=float,
        required=True,
        help="Reviewed true camera capture FPS when the file is encoded as slow motion.",
    )
    parser.add_argument(
        "--video-event-frame",
        type=int,
        required=True,
        help="Reviewed 2D video release frame. Automatic release detection is not used for report output.",
    )
    parser.add_argument("--min-visibility", type=float, default=0.2)
    parser.add_argument("--sample-step", type=int, default=3, help="Use every Nth source video frame in 2D-vs-3D QA.")
    parser.add_argument("--max-frames", type=int, default=160)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video = args.video.resolve()
    c3d = args.c3d.resolve()
    model = args.model.resolve()
    out_dir = args.out_dir.resolve()
    for label, required in (("video", video), ("c3d", c3d), ("model", model)):
        if not required.exists():
            raise FileNotFoundError(f"{label} not found: {required}")

    sync_script = SCRIPT_DIR / "sync_vicon_video.py"
    align_script = SCRIPTS_DIR / "align_2d_video_vicon.py"
    overlay_script = SCRIPTS_DIR / "render_aligned_2d_overlay.py"
    comparison_script = SCRIPTS_DIR / "render_vicon_3d_2d_alignment_comparison.py"
    for required in (sync_script, align_script, overlay_script, comparison_script):
        if not required.exists():
            raise FileNotFoundError(f"Required companion script is missing: {required}")

    out_dir.mkdir(parents=True, exist_ok=True)
    clean_standard_outputs(out_dir)
    sync_dir = out_dir / "sync"
    alignment_dir = out_dir / "alignment"
    comparison_dir = out_dir / "comparison"
    sync_dir.mkdir(parents=True, exist_ok=True)
    alignment_dir.mkdir(parents=True, exist_ok=True)
    comparison_dir.mkdir(parents=True, exist_ok=True)

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

    run(
        [
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
            "--video-capture-fps",
            str(args.video_capture_fps),
            "--video-event-frame",
            str(args.video_event_frame),
        ]
    )

    overlay = alignment_dir / "aligned_2d_skeleton_overlay.mp4"
    run(
        [
            sys.executable,
            str(overlay_script),
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

    run(
        [
            sys.executable,
            str(comparison_script),
            "--summary",
            str(alignment_dir / "alignment_summary.json"),
            "--out-dir",
            str(comparison_dir),
            "--player-slug",
            args.player_slug,
            "--player-label",
            args.player_label,
            "--sample-step",
            str(args.sample_step),
            "--max-frames",
            str(args.max_frames),
        ]
    )

    comparison_mp4 = comparison_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction.mp4"
    comparison_preview = comparison_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction_preview.jpg"
    required_outputs = {
        "clock_sync": sync_dir / "vicon_video_sync.json",
        "sync_signal": sync_dir / "pitch_sync_signals.csv",
        "alignment_summary": alignment_dir / "alignment_summary.json",
        "pose2d_landmarks": alignment_dir / "pose2d_landmarks.csv",
        "vicon_points_aligned_to_video": alignment_dir / "vicon_points_aligned_to_video.csv",
        "aligned_overlay": overlay,
        "comparison_video": comparison_mp4,
        "comparison_preview": comparison_preview,
    }
    for label, path in required_outputs.items():
        require_file(path, label)

    manifest = {
        "kind": "pitch",
        "player_slug": args.player_slug,
        "player_label": args.player_label,
        "video": str(video),
        "c3d": str(c3d),
        "mediapipe_model": str(model),
        "reviewed_video_capture_fps": args.video_capture_fps,
        "reviewed_video_event_frame": args.video_event_frame,
        "outputs": {label: str(path) for label, path in required_outputs.items()},
        "mapping_note": "C3D is the master clock; release frame and capture FPS must be manually reviewed before report use.",
    }
    manifest_path = out_dir / "pitching_alignment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
