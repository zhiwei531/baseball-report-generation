from __future__ import annotations

"""Single production entry point for a combined pitching + batting report."""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run(command: list[str], *, env: dict[str, str]) -> None:
    print("+", " ".join(str(part) for part in command))
    subprocess.run([str(part) for part in command], cwd=ROOT, check=True, env=env)


def resolve_path(value: str, *, root: Path) -> Path:
    path = Path(value).expanduser()
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def read_config(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Final report config must be a JSON object: {path}")
    return data


def required(mapping: dict[str, Any], key: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Missing required final report config field: {key}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build one final deliverable: pitching assets first, then the batting report that embeds them."
    )
    parser.add_argument("--config", required=True, type=Path, help="Combined final-report JSON config.")
    parser.add_argument("--skip-pitching", action="store_true", help="Reuse an existing pitching report named by the config.")
    parser.add_argument("--skip-pitching-alignment", action="store_true", help="Skip the optional pitching 2D/Vicon QA stage.")
    parser.add_argument("--skip-batting", action="store_true", help="Build only pitching deliverables for diagnosis.")
    args = parser.parse_args()

    config_path = args.config.expanduser().resolve()
    config = read_config(config_path)
    config_root = resolve_path(str(config.get("root_dir", ".")), root=ROOT)
    batting_config = resolve_path(required(config, "batting_config"), root=config_root)
    pitching = config.get("pitching")
    if not isinstance(pitching, dict):
        raise ValueError("Missing required final report config object: pitching")

    manifest = resolve_path(required(pitching, "manifest"), root=config_root)
    template_dir = resolve_path(required(pitching, "template_dir"), root=config_root)
    out_dir = resolve_path(required(pitching, "out_dir"), root=config_root)
    pitch_html = out_dir / "index.html"
    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
    env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")

    if not args.skip_pitching:
        command = [
            sys.executable,
            "scripts/pitching/build_pitch_template_metrics_report.py",
            "--manifest", manifest,
            "--template-dir", template_dir,
            "--out-dir", out_dir,
        ]
        previous_assets = pitching.get("previous_assets")
        if previous_assets:
            command.extend(["--previous-assets", resolve_path(str(previous_assets), root=config_root)])
        run(command, env=env)
    if not pitch_html.is_file():
        raise RuntimeError(f"Pitching build did not produce its required HTML: {pitch_html}")

    alignment = pitching.get("alignment")
    if alignment is not None and not args.skip_pitching_alignment:
        if not isinstance(alignment, dict):
            raise ValueError("pitching.alignment must be an object when provided")
        command = [
            sys.executable,
            "scripts/pitching/run_vicon_2d_alignment.py",
            "--video", resolve_path(required(alignment, "video"), root=config_root),
            "--c3d", resolve_path(required(alignment, "c3d"), root=config_root),
            "--model", resolve_path(required(alignment, "model"), root=config_root),
            "--out-dir", resolve_path(required(alignment, "out_dir"), root=config_root),
            "--player-slug", required(alignment, "player_slug"),
            "--player-label", required(alignment, "player_label"),
            "--video-capture-fps", str(alignment["video_capture_fps"]),
            "--video-event-frame", str(alignment["video_event_frame"]),
        ]
        for key in ("min_visibility", "sample_step", "max_frames"):
            if key in alignment:
                command.extend(["--" + key.replace("_", "-"), str(alignment[key])])
        run(command, env=env)

    if not args.skip_batting:
        run(
            [
                sys.executable,
                "scripts/run_batting_report_pipeline.py",
                "--config", batting_config,
                "--pitch-report", pitch_html,
            ],
            env=env,
        )


if __name__ == "__main__":
    main()
