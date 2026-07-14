from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default_report_pipeline.json"


@dataclass(frozen=True)
class PipelineConfig:
    root_dir: Path
    c3d_dir: Path
    report_dir: Path
    pitch_report: Path
    peers: Path
    alignment_dir: Path | None
    video: Path | None
    c3d_file: Path | None
    mediapipe_model: Path | None
    video_capture_fps: float | None
    video_event_frame: int | None
    ready_valid_start_frame: int
    xlsx_out_dir: Path
    sample_name: str
    trial_id: str


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Pipeline config must be a JSON object: {path}")
    return data


def _resolve_root(value: str | None) -> Path:
    raw = value or "."
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def _resolve_path(value: str | None, root_dir: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(value).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root_dir / path).resolve()


def load_pipeline_config(path: Path | str | None = None) -> PipelineConfig:
    config_path = Path(path).expanduser() if path else DEFAULT_CONFIG
    if not config_path.is_absolute():
        config_path = (REPO_ROOT / config_path).resolve()
    data = _read_json(config_path)

    root_dir = _resolve_root(data.get("root_dir"))
    return PipelineConfig(
        root_dir=root_dir,
        c3d_dir=_required_path(data, "c3d_dir", root_dir),
        report_dir=_required_path(data, "report_dir", root_dir),
        pitch_report=_required_path(data, "pitch_report", root_dir),
        peers=_required_path(data, "peers", root_dir),
        alignment_dir=_resolve_path(data.get("alignment_dir"), root_dir),
        video=_resolve_path(data.get("video"), root_dir),
        c3d_file=_resolve_path(data.get("c3d_file"), root_dir),
        mediapipe_model=_resolve_path(data.get("mediapipe_model"), root_dir),
        video_capture_fps=_optional_float(data.get("video_capture_fps")),
        video_event_frame=_optional_int(data.get("video_event_frame")),
        ready_valid_start_frame=_required_int(data.get("ready_valid_start_frame"), "ready_valid_start_frame"),
        xlsx_out_dir=_required_path(data, "xlsx_out_dir", root_dir),
        sample_name=str(data.get("sample_name") or "sample"),
        trial_id=str(data.get("trial_id") or ""),
    )


def _required_path(data: dict[str, Any], key: str, root_dir: Path) -> Path:
    value = _resolve_path(data.get(key), root_dir)
    if value is None:
        raise ValueError(f"Missing required path in pipeline config: {key}")
    return value


def _required_int(value: Any, key: str) -> int:
    if value is None:
        raise ValueError(f"Missing required integer in pipeline config: {key}")
    return int(value)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)
