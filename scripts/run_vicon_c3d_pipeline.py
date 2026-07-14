from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


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
    args = parser.parse_args()

    reports_dir = args.reports_dir
    reconstruction_dir = args.assets_dir / "vicon_reconstruction"
    model_dir = args.assets_dir / "vicon_reconstruction_models"
    metrics = reports_dir / "vicon_2026_metrics.csv"
    key_points = reports_dir / "vicon_2026_point_summary.csv"
    all_points = reports_dir / "vicon_2026_points_all.csv"
    pose3d = reports_dir / "vicon_2026_pose3d.csv"
    model_manifest = reports_dir / "vicon_2026_key_pose_models.csv"

    run_step(
        [
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
    )

    if not args.skip_render:
        env = os.environ.copy()
        env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
        env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")
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
            env=env,
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


if __name__ == "__main__":
    main()
