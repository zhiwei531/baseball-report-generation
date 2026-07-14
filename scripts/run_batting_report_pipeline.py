from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pipeline_config import DEFAULT_CONFIG, load_pipeline_config


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(str(item) for item in cmd))
    subprocess.run([str(item) for item in cmd], cwd=ROOT, check=True, env=env)


def plot_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
    env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")
    return env


def c3d_stage(args: argparse.Namespace) -> None:
    cmd = [
        PYTHON,
        "scripts/run_vicon_c3d_pipeline.py",
        "--input-dir",
        args.c3d_dir,
        "--reports-dir",
        args.report_dir,
        "--assets-dir",
        args.report_dir / "assets",
    ]
    if args.skip_reconstruction:
        cmd.append("--skip-render")
    run(cmd, env=plot_env())


def batting_metrics_stage(args: argparse.Namespace) -> Path:
    metrics = args.report_dir / "batting_dashboard_metrics.csv"
    wide = args.report_dir / "batting_dashboard_metrics_wide.csv"
    run(
        [
            PYTHON,
            "scripts/build_batting_dashboard_metrics.py",
            "--points",
            args.report_dir / "vicon_2026_points_all.csv",
            "--out",
            metrics,
            "--wide-out",
            wide,
            "--ready-valid-start-frame",
            args.ready_valid_start_frame,
        ]
    )
    return metrics


def batting_visual_stage(args: argparse.Namespace, metrics: Path) -> None:
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_event_gifs.py",
            "--metrics",
            metrics,
            "--out-dir",
            args.report_dir / "assets" / "vicon_reconstruction_events",
        ],
        env=plot_env(),
    )
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_annotated_speed_gifs.py",
            "--metrics",
            metrics,
            "--points",
            args.report_dir / "vicon_2026_point_summary.csv",
            "--out-dir",
            args.report_dir / "assets" / "vicon_reconstruction_annotated",
        ],
        env=plot_env(),
    )


def alignment_stage(args: argparse.Namespace) -> Path | None:
    if args.alignment_dir is not None:
        return args.alignment_dir
    if args.video is None:
        return None
    if args.c3d_file is None:
        raise SystemExit("--video requires --c3d-file for automatic 2D/Vicon alignment.")
    if args.mediapipe_model is None:
        raise SystemExit("--video requires --mediapipe-model unless --alignment-dir is provided.")

    out_dir = args.report_dir / "alignment_2d"
    cmd = [
        PYTHON,
        "scripts/align_2d_video_vicon.py",
        "--video",
        args.video,
        "--c3d",
        args.c3d_file,
        "--model",
        args.mediapipe_model,
        "--out-dir",
        out_dir,
    ]
    if args.video_capture_fps is not None:
        cmd.extend(["--video-capture-fps", args.video_capture_fps])
    if args.video_event_frame is not None:
        cmd.extend(["--video-event-frame", args.video_event_frame])
    run(cmd)
    run(
        [
            PYTHON,
            "scripts/render_aligned_2d_overlay.py",
            "--summary",
            out_dir / "alignment_summary.json",
            "--pose",
            out_dir / "pose2d_landmarks.csv",
            "--out",
            out_dir / "aligned_2d_skeleton_overlay.mp4",
        ]
    )
    return out_dir


def geometry_stage(args: argparse.Namespace, metrics: Path, alignment_dir: Path | None) -> None:
    if alignment_dir is None:
        if args.require_2d:
            raise SystemExit("2D geometry annotations require --alignment-dir or --video + --c3d-file + --mediapipe-model.")
        print("Skipping 2D geometry annotations: no alignment input provided.")
        return
    cmd = [
        PYTHON,
        "scripts/render_vicon_geometry_metrics_on_2d.py",
        "--alignment-dir",
        alignment_dir,
        "--metrics",
        metrics,
        "--sample-name",
        args.sample_name,
        "--out-dir",
        args.report_dir / "assets" / "vicon_2d_geometry_annotations",
    ]
    if args.video is not None:
        cmd.extend(["--video", args.video])
    run(cmd, env=plot_env())


def illustration_stage(args: argparse.Namespace, metrics: Path) -> None:
    src = args.report_dir / "assets" / "frontend_metric_illustrations"
    if not src.exists():
        if args.require_static_assets:
            raise SystemExit(f"Missing static illustration source directory: {src}")
        print(f"Skipping metric illustration annotation: missing {src}")
        return
    run(
        [
            PYTHON,
            "scripts/annotate_frontend_metric_illustrations.py",
            "--report-dir",
            args.report_dir,
            "--metrics",
            metrics,
        ]
    )


def html_stage(args: argparse.Namespace, metrics: Path) -> None:
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_metrics_section.py",
            "--metrics",
            metrics,
            "--peers",
            args.peers,
            "--out",
            args.report_dir / "julian_coach_metrics_section.html",
            "--pitch-report",
            args.pitch_report,
        ]
    )
    if not args.skip_final_schema:
        run(
            [
                PYTHON,
                "scripts/apply_batting_coach_values.py",
                "--report-dir",
                args.report_dir,
                "--peers",
                args.peers,
            ]
        )


def xlsx_stage(args: argparse.Namespace, metrics: Path) -> None:
    env = os.environ.copy()
    env["METRICS_PATH"] = str(metrics)
    env["OUT_DIR"] = str(args.xlsx_out_dir)
    if args.sample_name:
        env["SAMPLE_NAME"] = args.sample_name
    if args.trial_id:
        env["TRIAL_ID"] = args.trial_id
    run(["node", "scripts/build_batting_metrics_xlsx.mjs"], env=env)


def apply_config_defaults(args: argparse.Namespace) -> None:
    config = load_pipeline_config(args.config)
    configurable = (
        "c3d_dir",
        "report_dir",
        "pitch_report",
        "peers",
        "alignment_dir",
        "video",
        "c3d_file",
        "mediapipe_model",
        "video_capture_fps",
        "video_event_frame",
        "ready_valid_start_frame",
        "xlsx_out_dir",
        "sample_name",
        "trial_id",
    )
    for name in configurable:
        if getattr(args, name) is None:
            setattr(args, name, getattr(config, name))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the batting report from Vicon C3D plus aligned 2D video inputs."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help="Pipeline config JSON with shared root/path defaults.")
    parser.add_argument("--c3d-dir", type=Path, default=None)
    parser.add_argument("--report-dir", type=Path, default=None)
    parser.add_argument("--pitch-report", type=Path, default=None)
    parser.add_argument("--peers", type=Path, default=None)
    parser.add_argument("--alignment-dir", type=Path, default=None)
    parser.add_argument("--video", type=Path, default=None)
    parser.add_argument("--c3d-file", type=Path, default=None, help="Single batting C3D used for 2D/Vicon alignment.")
    parser.add_argument("--mediapipe-model", type=Path, default=None)
    parser.add_argument("--video-capture-fps", type=float, default=None)
    parser.add_argument("--video-event-frame", type=int, default=None)
    parser.add_argument("--ready-valid-start-frame", type=int, default=None)
    parser.add_argument("--xlsx-out-dir", type=Path, default=None)
    parser.add_argument("--sample-name", default=None)
    parser.add_argument("--trial-id", default=None)

    parser.add_argument("--skip-c3d", action="store_true")
    parser.add_argument("--skip-reconstruction", action="store_true")
    parser.add_argument("--skip-2d", action="store_true")
    parser.add_argument("--skip-illustrations", action="store_true")
    parser.add_argument("--skip-final-schema", action="store_true")
    parser.add_argument("--skip-xlsx", action="store_true")
    parser.add_argument("--require-2d", action="store_true")
    parser.add_argument("--require-static-assets", action="store_true")
    args = parser.parse_args()
    apply_config_defaults(args)

    args.report_dir.mkdir(parents=True, exist_ok=True)
    if not args.skip_c3d:
        c3d_stage(args)
    metrics = batting_metrics_stage(args)
    batting_visual_stage(args, metrics)
    alignment_dir = None if args.skip_2d else alignment_stage(args)
    if not args.skip_2d:
        geometry_stage(args, metrics, alignment_dir)
    if not args.skip_illustrations:
        illustration_stage(args, metrics)
    html_stage(args, metrics)
    if not args.skip_xlsx:
        xlsx_stage(args, metrics)

    print("Batting report pipeline outputs:")
    print(args.report_dir / "julian_coach_metrics_section.html")
    print(metrics)
    print(args.report_dir / "assets")


if __name__ == "__main__":
    main()
