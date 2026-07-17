from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from pipeline_config import plot_environment


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT.parent / "vicon_2026"
DEFAULT_REPORTS = ROOT / "reports"
DEFAULT_ASSETS = DEFAULT_REPORTS / "assets"


def run_step(args: list[str], *, env: dict[str, str] | None = None) -> None:
    print(" ".join(args))
    subprocess.run(args, cwd=ROOT, check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the full Vicon C3D pipeline: all-frame CSVs, key-pose summary, "
            "reconstruction images, and key-pose OBJ models."
        )
    )
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS)
    parser.add_argument("--assets-dir", type=Path, default=DEFAULT_ASSETS)
    parser.add_argument("--max-gif-frames", type=int, default=72)
    parser.add_argument("--gif-before-sec", type=float, default=0.6)
    parser.add_argument("--pitch-gif-before-sec", type=float, default=1.4)
    parser.add_argument("--gif-after-sec", type=float, default=0.4)
    parser.add_argument("--skip-render", action="store_true")
    parser.add_argument(
        "--save-motion-manifest",
        action="store_true",
        help="Write additive canonical motion metadata without changing legacy CSV columns.",
    )
    args = parser.parse_args()

    reports_dir = args.reports_dir
    reconstruction_dir = args.assets_dir / "vicon_reconstruction"
    model_dir = args.assets_dir / "vicon_reconstruction_models"
    metrics = reports_dir / "vicon_2026_metrics.csv"
    key_points = reports_dir / "vicon_2026_point_summary.csv"
    all_points = reports_dir / "vicon_2026_points_all.csv"
    pose3d = reports_dir / "vicon_2026_pose3d.csv"
    model_manifest = reports_dir / "vicon_2026_key_pose_models.csv"
    motion_manifest = reports_dir / "vicon_2026_motion_manifest.json"

    metrics_command = [
        sys.executable,
        "scripts/build_vicon_2026_metrics.py",
        "--input-dir",
        str(args.input_dir),
        "--metrics-out",
        str(metrics),
        "--points-out",
        str(key_points),
        "--all-points-out",
        str(all_points),
        "--pose3d-out",
        str(pose3d),
    ]
    if args.save_motion_manifest:
        metrics_command.extend(["--motion-manifest-out", str(motion_manifest)])
    run_step(metrics_command)

    if not args.skip_render:
        run_step(
            [
                sys.executable,
                "scripts/render_vicon_reconstruction_images.py",
                "--points",
                str(key_points),
                "--c3d-dir",
                str(args.input_dir),
                "--out-dir",
                str(reconstruction_dir),
                "--model-dir",
                str(model_dir),
                "--model-manifest",
                str(model_manifest),
                "--max-gif-frames",
                str(args.max_gif_frames),
                "--gif-before-sec",
                str(args.gif_before_sec),
                "--pitch-gif-before-sec",
                str(args.pitch_gif_before_sec),
                "--gif-after-sec",
                str(args.gif_after_sec),
            ],
            env=plot_environment(),
        )

    print("Vicon C3D pipeline outputs:")
    for path in (
        metrics,
        key_points,
        all_points,
        pose3d,
        model_manifest,
        reconstruction_dir,
        model_dir,
    ):
        print(path)
    if args.save_motion_manifest:
        print(motion_manifest)


if __name__ == "__main__":
    main()
