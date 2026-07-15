from __future__ import annotations

"""Public report executions: pitching, batting, and their final orchestration."""

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str]) -> None:
    print("+", " ".join(str(part) for part in command))
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, env=env)


def resolve_path(value: str, *, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def required(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required final report config field: {key}")
    return value


@dataclass(frozen=True)
class FinalReportConfig:
    root: Path
    batting_config: Path
    pitching_manifest: Path
    pitching_template_dir: Path
    pitching_out_dir: Path
    pitching_previous_assets: Path | None
    pitching_alignment: dict[str, Any] | None

    @property
    def pitch_html(self) -> Path:
        return self.pitching_out_dir / "index.html"


def load_config(path: Path) -> FinalReportConfig:
    config_path = path.expanduser().resolve()
    data = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Final report config must be a JSON object: {config_path}")
    root = resolve_path(str(data.get("root_dir", ".")), root=ROOT)
    pitching = data.get("pitching")
    if not isinstance(pitching, dict):
        raise ValueError("Missing required final report config object: pitching")
    previous_assets = pitching.get("previous_assets")
    alignment = pitching.get("alignment")
    if alignment is not None and not isinstance(alignment, dict):
        raise ValueError("pitching.alignment must be an object when provided")
    return FinalReportConfig(
        root=root,
        batting_config=resolve_path(required(data, "batting_config"), root=root),
        pitching_manifest=resolve_path(required(pitching, "manifest"), root=root),
        pitching_template_dir=resolve_path(required(pitching, "template_dir"), root=root),
        pitching_out_dir=resolve_path(required(pitching, "out_dir"), root=root),
        pitching_previous_assets=resolve_path(str(previous_assets), root=root) if previous_assets else None,
        pitching_alignment=alignment,
    )


def execution_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
    env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")
    return env


def pitching_player_key(manifest_path: Path) -> str:
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    rows = data.get("athletes") if isinstance(data, dict) else data
    if not isinstance(rows, list):
        raise ValueError(f"Pitching manifest does not contain an athletes list: {manifest_path}")
    for row in rows:
        if not isinstance(row, dict):
            continue
        key = str(row.get("key") or "").strip()
        if row.get("role") == "student" and key and key != "coach":
            return key
    raise ValueError(f"Pitching manifest does not contain a student athlete: {manifest_path}")


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
    alignment_out_dir = resolve_path(required(alignment, "out_dir"), root=config.root)
    command = [
        sys.executable,
        "scripts/pitching/run_vicon_2d_alignment.py",
        "--video", resolve_path(required(alignment, "video"), root=config.root),
        "--c3d", resolve_path(required(alignment, "c3d"), root=config.root),
        "--model", resolve_path(required(alignment, "model"), root=config.root),
        "--out-dir", alignment_out_dir,
        "--player-slug", required(alignment, "player_slug"),
        "--player-label", required(alignment, "player_label"),
        "--video-capture-fps", str(alignment["video_capture_fps"]),
        "--video-event-frame", str(alignment["video_event_frame"]),
    ]
    for key in ("min_visibility", "sample_step", "max_frames"):
        if key in alignment:
            command.extend(["--" + key.replace("_", "-"), str(alignment[key])])
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
        if name in {"pitching", "final"}:
            child.add_argument("--skip-pitching-alignment", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)

    if args.execution == "pitching":
        execute_pitching(config, skip_alignment=args.skip_pitching_alignment)
    elif args.execution == "batting":
        execute_batting(config)
    else:
        execute_pitching(config, skip_alignment=args.skip_pitching_alignment)
        execute_batting(config)


if __name__ == "__main__":
    main()
