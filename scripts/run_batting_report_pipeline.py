from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

from pipeline_config import DEFAULT_CONFIG, load_pipeline_config, plot_environment
from pipeline_runtime import (
    StageExecutionResult,
    configure_logging,
    run_command_stage,
    write_pipeline_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
BUNDLED_BATTING_ILLUSTRATIONS = ROOT / "assets" / "batting" / "frontend_metric_illustrations"
PIPELINE_STAGES: list[StageExecutionResult] = []


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    executable = Path(str(cmd[1] if len(cmd) > 1 else cmd[0])).stem
    PIPELINE_STAGES.append(
        run_command_stage(executable, cmd, cwd=ROOT, env=env)
    )


def require_paths(paths: list[Path], stage: str) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"{stage} did not produce required outputs: {', '.join(missing)}")


def clean_2d_outputs(report_dir: Path) -> None:
    """Prevent an unsuccessful rebuild from silently retaining old 2D assets."""
    for path in (
        report_dir / "alignment_2d",
        report_dir / "assets" / "vicon_2d_geometry_annotations",
        report_dir / "assets" / "vicon_2d_vicon_3d_comparison",
    ):
        if path.exists():
            # Finder/Spotlight sidecar files can disappear between scandir and
            # unlink on macOS.  They are not report inputs, so a vanished file
            # must not abort a clean rebuild of the generated 2D assets.
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                pass


def validate_alignment_summary(alignment_dir: Path, args: argparse.Namespace) -> None:
    summary_path = alignment_dir / "alignment_summary.json"
    require_paths([summary_path, alignment_dir / "pose2d_landmarks.csv"], "2D alignment")
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    if args.video is not None and Path(summary["video"]).resolve() != args.video.resolve():
        raise RuntimeError("Alignment summary video does not match the configured video.")
    if args.c3d_file is not None and Path(summary["c3d"]).resolve() != args.c3d_file.resolve():
        raise RuntimeError("Alignment summary C3D does not match the configured C3D.")


def plot_env() -> dict[str, str]:
    """Compatibility name for the shared plotting/cache environment."""
    return plot_environment()


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
            "--samples",
            args.sample_name,
            args.coach_sample_name,
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
            "--samples",
            args.sample_name,
            args.coach_sample_name,
        ],
        env=plot_env(),
    )


def alignment_stage(args: argparse.Namespace) -> Path | None:
    if args.alignment_dir is not None:
        raise SystemExit(
            "The standard report entry does not accept a prebuilt alignment directory. "
            "Run the reviewed raw-video alignment stages from this config instead."
        )
    if args.video is None:
        return None
    if args.c3d_file is None:
        raise SystemExit("--video requires --c3d-file for automatic 2D/Vicon alignment.")
    if args.mediapipe_model is None:
        raise SystemExit("--video requires --mediapipe-model unless --alignment-dir is provided.")
    if args.video_capture_fps is None or args.video_event_frame is None:
        raise SystemExit(
            "The standard 2D pipeline requires reviewed --video-capture-fps and --video-event-frame; "
            "automatic event inference is not an accepted report build path."
        )

    out_dir = args.report_dir / "alignment_2d"
    clean_2d_outputs(args.report_dir)
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
    cmd.extend(["--video-capture-fps", args.video_capture_fps])
    cmd.extend(["--video-event-frame", args.video_event_frame])
    run(cmd)
    validate_alignment_summary(out_dir, args)
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
            "--preview",
            out_dir / "aligned_2d_overlay_preview.jpg",
        ]
    )
    require_paths(
        [
            out_dir / "aligned_2d_skeleton_overlay.mp4",
            out_dir / "aligned_2d_overlay_preview.jpg",
        ],
        "aligned 2D overlay",
    )
    comparison_dir = args.report_dir / "assets" / "vicon_2d_vicon_3d_comparison"
    run(
        [
            PYTHON,
            "scripts/render_vicon_3d_2d_alignment_comparison.py",
            "--summary",
            out_dir / "alignment_summary.json",
            "--out-dir",
            comparison_dir,
            "--player-slug",
            args.player_slug,
            "--player-label",
            args.player_label,
        ],
        env=plot_env(),
    )
    require_paths(
        [
            comparison_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction.mp4",
            comparison_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction_preview.jpg",
        ],
        "2D-vs-Vicon-3D comparison",
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
    annotation_report = args.report_dir / "assets" / "vicon_2d_geometry_annotations" / "vicon_geometry_metric_annotations.json"
    require_paths(
        [
            annotation_report,
            args.report_dir / "assets" / "vicon_2d_geometry_annotations" / "ready_position_vicon_geometry_on_2d.png",
            args.report_dir / "assets" / "vicon_2d_geometry_annotations" / "contact_position_vicon_geometry_on_2d.png",
        ],
        "Vicon geometry annotations",
    )
    report = json.loads(annotation_report.read_text(encoding="utf-8"))
    provenance = report.get("provenance", {})
    if provenance.get("sample_name") != args.sample_name:
        raise RuntimeError("2D geometry annotation sample does not match the configured player.")


def illustration_stage(args: argparse.Namespace, metrics: Path) -> None:
    src = args.report_dir / "assets" / "frontend_metric_illustrations"
    if not BUNDLED_BATTING_ILLUSTRATIONS.exists():
        raise SystemExit(f"Bundled batting illustration source directory is missing: {BUNDLED_BATTING_ILLUSTRATIONS}")
    src.mkdir(parents=True, exist_ok=True)
    copied = 0
    for bundled in BUNDLED_BATTING_ILLUSTRATIONS.glob("*.png"):
        target = src / bundled.name
        if not target.exists():
            shutil.copy2(bundled, target)
            copied += 1
    if copied:
        print(f"Copied bundled batting action illustrations to {src}")
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
    out_html = args.report_dir / f"{args.player_slug}_coach_metrics_section.html"
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_metrics_section.py",
            "--metrics",
            metrics,
            "--peers",
            args.peers,
            "--out",
            out_html,
            "--pitch-report",
            args.pitch_report,
            "--player-sample-name",
            args.sample_name,
            "--coach-sample-name",
            args.coach_sample_name,
            "--player-slug",
            args.player_slug,
            "--player-label",
            args.player_label,
        ]
    )
    if not args.skip_final_schema:
        run(
            [
                PYTHON,
                "scripts/apply_batting_coach_values.py",
                "--report-dir",
                args.report_dir,
                "--html",
                out_html,
                "--player-sample-name",
                args.sample_name,
                "--coach-sample-name",
                args.coach_sample_name,
                "--player-slug",
                args.player_slug,
                "--player-label",
                args.player_label,
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


def report_data_stage(args: argparse.Namespace, metrics: Path) -> Path:
    output = args.report_dir / "analysis_report_data.json"
    pitch_summary = args.pitch_report.parent / "pitch_metrics_summary.json"
    env = os.environ.copy()
    source_root = str(ROOT / "src")
    current_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        source_root if not current_pythonpath else os.pathsep.join((source_root, current_pythonpath))
    )
    command = [
        PYTHON,
        "-m",
        "baseball_report.reporting.build_legacy",
        "--batting",
        metrics,
        "--output",
        output,
        "--report-id",
        f"{args.player_slug}-combined-report",
        "--subject-id",
        args.player_slug,
        "--subject-label",
        args.player_label,
        "--subject-key",
        args.sample_name,
        "--subject-key",
        args.player_slug,
    ]
    if pitch_summary.is_file():
        command.extend(["--pitching", pitch_summary])
    run(command, env=env)
    require_paths([output], "ReportData serialization")
    return output


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
        "coach_sample_name",
        "player_slug",
        "player_label",
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
    parser.add_argument("--coach-sample-name", default=None)
    parser.add_argument("--player-slug", default=None)
    parser.add_argument("--player-label", default=None)
    parser.add_argument("--trial-id", default=None)

    parser.add_argument("--skip-c3d", action="store_true")
    parser.add_argument("--skip-reconstruction", action="store_true")
    parser.add_argument("--skip-2d", action="store_true")
    parser.add_argument("--skip-illustrations", action="store_true")
    parser.add_argument("--skip-final-schema", action="store_true")
    parser.add_argument("--skip-xlsx", action="store_true")
    parser.add_argument("--require-2d", action="store_true")
    parser.add_argument("--require-static-assets", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    parser.add_argument("--run-manifest", type=Path, default=None)
    args = parser.parse_args()
    configure_logging(args.log_level)
    PIPELINE_STAGES.clear()
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
    report_data = report_data_stage(args, metrics)

    manifest_path = args.run_manifest or args.report_dir / "batting_pipeline_run.json"
    write_pipeline_manifest(
        manifest_path,
        pipeline_name="batting_report",
        stages=PIPELINE_STAGES,
        metadata={
            "player_slug": args.player_slug,
            "sample_name": args.sample_name,
            "report_dir": str(args.report_dir.resolve()),
        },
    )

    print("Batting report pipeline outputs:")
    print(args.report_dir / f"{args.player_slug}_coach_metrics_section.html")
    print(metrics)
    print(report_data)
    print(args.report_dir / "assets")


if __name__ == "__main__":
    main()
