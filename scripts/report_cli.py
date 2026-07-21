from __future__ import annotations

"""Public report executions: pitching, batting, and their final orchestration."""

import argparse
import sys
from pathlib import Path

from pipeline_config import (
    FinalReportConfig,
    PreflightResult,
    load_final_report_config,
    load_pitching_manifest,
    plot_environment,
    preflight_final_report,
)
from pipeline_runtime import (
    StageExecutionResult,
    configure_logging,
    run_command_stage,
    write_pipeline_manifest,
)


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_STAGES: list[StageExecutionResult] = []


def run(command: list[str], *, env: dict[str, str]) -> None:
    executable = Path(str(command[1] if len(command) > 1 else command[0])).stem
    PIPELINE_STAGES.append(
        run_command_stage(executable, command, cwd=ROOT, env=env)
    )


def load_config(path: Path) -> FinalReportConfig:
    """Compatibility wrapper for callers of the original Stage 0 loader."""
    return load_final_report_config(path)


def execution_env() -> dict[str, str]:
    """Compatibility name for the shared plotting/cache environment."""
    return plot_environment()


def pitching_player_key(manifest_path: Path) -> str:
    return load_pitching_manifest(manifest_path).player.key


def print_preflight(result: PreflightResult) -> None:
    print(f"Preflight: {result.execution}")
    for label, path in result.resolved_paths:
        print(f"  {label}: {path}")
    for warning in result.warnings:
        print(f"  WARNING: {warning}")
    if result.ok:
        print("  status: ready")


def require_outputs(paths: list[Path], stage: str) -> None:
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise RuntimeError(f"{stage} did not produce required outputs: {', '.join(missing)}")


def execute_pitching(config: FinalReportConfig, *, skip_alignment: bool) -> None:
    env = execution_env()
    player_key = pitching_player_key(config.pitching_manifest)
    command = [
        sys.executable,
        "scripts/pitching/build_pitch_template_metrics_report.py",
        "--manifest", config.pitching_manifest,
        "--template-dir", config.pitching_template_dir,
        "--out-dir", config.pitching_out_dir,
    ]
    if config.pitching_previous_assets is not None:
        command.extend(["--previous-assets", config.pitching_previous_assets])
    run(command, env=env)
    if not config.pitch_html.is_file():
        raise RuntimeError(f"Pitching execution did not produce its required HTML: {config.pitch_html}")

    analyst_dir = config.pitching_out_dir / "assets" / "analyst_charts"
    kinetic_dir = config.pitching_out_dir / "assets" / "kinetic_chain"
    run(
        [
            sys.executable,
            "scripts/pitching/generate_professional_pitch_charts.py",
            "--summary", config.pitching_out_dir / "pitch_metrics_summary.json",
            "--out-dir", analyst_dir,
            "--kinetic-out-dir", kinetic_dir,
            "--athlete-key", player_key,
        ],
        env=env,
    )
    require_outputs(
        [
            analyst_dir / f"{player_key}_pitch_angle_time_curve.png",
            analyst_dir / f"{player_key}_pitch_speed_time_curve.png",
            kinetic_dir / f"{player_key}_kinetic_chain_time_curves.png",
        ],
        "pitching researcher charts",
    )

    alignment = config.pitching_alignment
    if alignment is None or skip_alignment:
        return
    alignment_out_dir = alignment.out_dir
    command = [
        sys.executable,
        "scripts/pitching/run_vicon_2d_alignment.py",
        "--video", alignment.video,
        "--c3d", alignment.c3d,
        "--model", alignment.model,
        "--out-dir", alignment_out_dir,
        "--player-slug", alignment.player_slug,
        "--player-label", alignment.player_label,
        "--video-capture-fps", str(alignment.video_capture_fps),
        "--video-event-frame", str(alignment.video_event_frame),
    ]
    for key in ("min_visibility", "sample_step", "max_frames"):
        value = getattr(alignment, key)
        if value is not None:
            command.extend(["--" + key.replace("_", "-"), str(value)])
    run(command, env=env)
    geometry_dir = config.pitching_out_dir / "assets" / "video_2d_alignment"
    run(
        [
            sys.executable,
            "scripts/pitching/render_pitch_event_overlays.py",
            "--alignment-dir", alignment_out_dir / "alignment",
            "--pitch-summary", config.pitching_out_dir / "pitch_metrics_summary.json",
            "--athlete-key", player_key,
            "--out-dir", geometry_dir,
        ],
        env=env,
    )
    require_outputs(
        [
            geometry_dir / f"{player_key}_pitch_peak_knee_2d_overlay.png",
            geometry_dir / f"{player_key}_pitch_foot_plant_2d_overlay.png",
            geometry_dir / f"{player_key}_pitch_release_2d_overlay.png",
            geometry_dir / "pitch_event_overlay_provenance.json",
        ],
        "pitching event geometry overlays",
    )


def execute_batting(config: FinalReportConfig) -> None:
    if not config.pitch_html.is_file():
        raise RuntimeError(
            f"Batting execution requires the pitching execution output: {config.pitch_html}. "
            "Run `report_cli.py pitching --config ...` first, or use `final`."
        )
    run(
        [
            sys.executable,
            "scripts/run_batting_report_pipeline.py",
            "--config", config.batting_config,
            "--pitch-report", config.pitch_html,
        ],
        env=execution_env(),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Public pitching, batting, and final report executions.")
    sub = parser.add_subparsers(dest="execution", required=True)
    for name, help_text in (
        ("pitching", "Build pitching HTML/assets and optional pitching alignment QA."),
        ("batting", "Build batting and embed the current pitching execution output."),
        ("final", "Run pitching followed by batting for one combined deliverable."),
    ):
        child = sub.add_parser(name, help=help_text)
        child.add_argument("--config", required=True, type=Path, help="Combined final-report JSON config.")
        child.add_argument("--log-level", default="INFO")
        child.add_argument("--run-manifest", type=Path, default=None)
        child.add_argument(
            "--dry-run",
            action="store_true",
            help="Resolve and validate configuration without generating or modifying outputs.",
        )
        if name in {"pitching", "final"}:
            child.add_argument("--skip-pitching-alignment", action="store_true")
    args = parser.parse_args()
    configure_logging(args.log_level)
    PIPELINE_STAGES.clear()
    config = load_config(args.config)
    result = preflight_final_report(
        config,
        execution=args.execution,
        skip_pitching_alignment=getattr(args, "skip_pitching_alignment", False),
    )
    print_preflight(result)
    result.require_valid()
    if args.dry_run:
        return

    if args.execution == "pitching":
        execute_pitching(config, skip_alignment=args.skip_pitching_alignment)
    elif args.execution == "batting":
        execute_batting(config)
    else:
        execute_pitching(config, skip_alignment=args.skip_pitching_alignment)
        execute_batting(config)

    if PIPELINE_STAGES:
        manifest_path = args.run_manifest or config.pitching_out_dir / f"{args.execution}_pipeline_run.json"
        write_pipeline_manifest(
            manifest_path,
            pipeline_name=f"report_{args.execution}",
            stages=PIPELINE_STAGES,
            metadata={
                "config": str(config.config_path),
                "pitching_out_dir": str(config.pitching_out_dir),
            },
        )


if __name__ == "__main__":
    main()
