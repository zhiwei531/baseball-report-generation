from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO_ROOT / "configs" / "default_report_pipeline.json"
ExecutionName = Literal["pitching", "batting", "final"]
_SLUG = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


class ConfigurationError(ValueError):
    """A report configuration is malformed or unsafe to execute."""


@dataclass(frozen=True)
class PipelineConfig:
    config_path: Path
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
    coach_sample_name: str
    player_slug: str
    player_label: str
    trial_id: str


@dataclass(frozen=True)
class PitchingAlignmentConfig:
    video: Path
    c3d: Path
    model: Path
    out_dir: Path
    player_slug: str
    player_label: str
    video_capture_fps: float
    video_event_frame: int
    min_visibility: float | None = None
    sample_step: int | None = None
    max_frames: int | None = None


@dataclass(frozen=True)
class FinalReportConfig:
    config_path: Path
    root: Path
    batting_config: Path
    pitching_manifest: Path
    pitching_template_dir: Path
    pitching_out_dir: Path
    pitching_previous_assets: Path | None
    pitching_alignment: PitchingAlignmentConfig | None

    @property
    def pitch_html(self) -> Path:
        return self.pitching_out_dir / "index.html"


@dataclass(frozen=True)
class PitchingAthleteConfig:
    key: str
    name: str
    role: str
    c3d: Path


@dataclass(frozen=True)
class PitchingManifestConfig:
    manifest_path: Path
    athletes: tuple[PitchingAthleteConfig, ...]

    @property
    def player(self) -> PitchingAthleteConfig:
        return next(
            athlete
            for athlete in self.athletes
            if athlete.role == "student" and athlete.key != "coach"
        )


@dataclass(frozen=True)
class PreflightResult:
    execution: ExecutionName
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    resolved_paths: tuple[tuple[str, Path], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def require_valid(self) -> None:
        if self.errors:
            details = "\n".join(f"- {message}" for message in self.errors)
            raise ConfigurationError(f"Report configuration preflight failed:\n{details}")


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ConfigurationError(f"{label} not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            f"{label} is not valid JSON at line {exc.lineno}, column {exc.colno}: {path}"
        ) from exc
    if not isinstance(data, dict):
        raise ConfigurationError(f"{label} must be a JSON object: {path}")
    return data


def resolve_config_path(path: Path | str | None, *, default: Path) -> Path:
    candidate = Path(path).expanduser() if path else default
    if candidate.is_absolute():
        return candidate.resolve()
    return (REPO_ROOT / candidate).resolve()


def resolve_root(value: object) -> Path:
    raw = str(value or ".")
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (REPO_ROOT / path).resolve()


def resolve_path(value: object, *, root: Path) -> Path | None:
    if value in (None, ""):
        return None
    path = Path(str(value)).expanduser()
    if path.is_absolute():
        return path.resolve()
    return (root / path).resolve()


def plot_environment(environ: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if environ is None else environ)
    env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
    env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")
    required_paths = (str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"))
    existing = tuple(part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys((*required_paths, *existing)))
    return env


def _required_path(data: dict[str, Any], key: str, root_dir: Path, label: str) -> Path:
    value = resolve_path(data.get(key), root=root_dir)
    if value is None:
        raise ConfigurationError(f"Missing required path in {label}: {key}")
    return value


def _required_text(data: dict[str, Any], key: str, label: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"Missing required text in {label}: {key}")
    return value.strip()


def _required_int(value: Any, key: str, label: str) -> int:
    if value is None or isinstance(value, bool):
        raise ConfigurationError(f"Missing required integer in {label}: {key}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid integer in {label}: {key}={value!r}") from exc


def _optional_int(value: Any, key: str, label: str) -> int | None:
    if value in (None, ""):
        return None
    return _required_int(value, key, label)


def _required_float(value: Any, key: str, label: str) -> float:
    if value is None or isinstance(value, bool):
        raise ConfigurationError(f"Missing required number in {label}: {key}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid number in {label}: {key}={value!r}") from exc
    if not result > 0:
        raise ConfigurationError(f"{label}.{key} must be positive")
    return result


def _optional_float(value: Any, key: str, label: str) -> float | None:
    if value in (None, ""):
        return None
    return _required_float(value, key, label)


def _optional_unit_interval(value: Any, key: str, label: str) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, bool):
        raise ConfigurationError(f"Invalid number in {label}: {key}={value!r}")
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigurationError(f"Invalid number in {label}: {key}={value!r}") from exc
    if not 0 <= result <= 1:
        raise ConfigurationError(f"{label}.{key} must be between 0 and 1")
    return result


def _validate_slug(value: str, key: str, label: str) -> str:
    if not _SLUG.fullmatch(value):
        raise ConfigurationError(
            f"{label}.{key} must contain only letters, digits, underscore, or hyphen"
        )
    return value


def load_pipeline_config(path: Path | str | None = None) -> PipelineConfig:
    config_path = resolve_config_path(path, default=DEFAULT_CONFIG)
    label = "batting pipeline config"
    data = _read_json(config_path, label)
    root_dir = resolve_root(data.get("root_dir"))
    sample_name = str(data.get("sample_name") or "sample").strip()
    coach_sample_name = str(data.get("coach_sample_name") or "coach").strip()
    player_slug = str(data.get("player_slug") or sample_name).strip()
    player_label = str(data.get("player_label") or player_slug.title()).strip()
    if not sample_name or not coach_sample_name or not player_label:
        raise ConfigurationError(f"{label} names must not be empty: {config_path}")
    _validate_slug(player_slug, "player_slug", label)
    video_capture_fps = _optional_float(
        data.get("video_capture_fps"), "video_capture_fps", label
    )
    video_event_frame = _optional_int(
        data.get("video_event_frame"), "video_event_frame", label
    )
    if video_event_frame is not None and video_event_frame < 0:
        raise ConfigurationError(f"{label}.video_event_frame must be non-negative")
    ready_valid_start_frame = _required_int(
        data.get("ready_valid_start_frame"), "ready_valid_start_frame", label
    )
    if ready_valid_start_frame < 0:
        raise ConfigurationError(f"{label}.ready_valid_start_frame must be non-negative")
    return PipelineConfig(
        config_path=config_path,
        root_dir=root_dir,
        c3d_dir=_required_path(data, "c3d_dir", root_dir, label),
        report_dir=_required_path(data, "report_dir", root_dir, label),
        pitch_report=_required_path(data, "pitch_report", root_dir, label),
        peers=_required_path(data, "peers", root_dir, label),
        alignment_dir=resolve_path(data.get("alignment_dir"), root=root_dir),
        video=resolve_path(data.get("video"), root=root_dir),
        c3d_file=resolve_path(data.get("c3d_file"), root=root_dir),
        mediapipe_model=resolve_path(data.get("mediapipe_model"), root=root_dir),
        video_capture_fps=video_capture_fps,
        video_event_frame=video_event_frame,
        ready_valid_start_frame=ready_valid_start_frame,
        xlsx_out_dir=_required_path(data, "xlsx_out_dir", root_dir, label),
        sample_name=sample_name,
        coach_sample_name=coach_sample_name,
        player_slug=player_slug,
        player_label=player_label,
        trial_id=str(data.get("trial_id") or "").strip(),
    )


def _load_alignment(data: dict[str, Any], *, root: Path) -> PitchingAlignmentConfig:
    label = "final report config pitching.alignment"
    player_slug = _required_text(data, "player_slug", label)
    video_event_frame = _required_int(data.get("video_event_frame"), "video_event_frame", label)
    if video_event_frame < 0:
        raise ConfigurationError(f"{label}.video_event_frame must be non-negative")
    sample_step = _optional_int(data.get("sample_step"), "sample_step", label)
    max_frames = _optional_int(data.get("max_frames"), "max_frames", label)
    if sample_step is not None and sample_step <= 0:
        raise ConfigurationError(f"{label}.sample_step must be positive")
    if max_frames is not None and max_frames <= 0:
        raise ConfigurationError(f"{label}.max_frames must be positive")
    return PitchingAlignmentConfig(
        video=_required_path(data, "video", root, label),
        c3d=_required_path(data, "c3d", root, label),
        model=_required_path(data, "model", root, label),
        out_dir=_required_path(data, "out_dir", root, label),
        player_slug=_validate_slug(player_slug, "player_slug", label),
        player_label=_required_text(data, "player_label", label),
        video_capture_fps=_required_float(
            data.get("video_capture_fps"), "video_capture_fps", label
        ),
        video_event_frame=video_event_frame,
        min_visibility=_optional_unit_interval(
            data.get("min_visibility"), "min_visibility", label
        ),
        sample_step=sample_step,
        max_frames=max_frames,
    )


def load_final_report_config(path: Path | str) -> FinalReportConfig:
    config_path = resolve_config_path(path, default=REPO_ROOT / "configs" / "final_report.example.json")
    label = "final report config"
    data = _read_json(config_path, label)
    root = resolve_root(data.get("root_dir"))
    pitching = data.get("pitching")
    if not isinstance(pitching, dict):
        raise ConfigurationError("Missing required final report config object: pitching")
    alignment_data = pitching.get("alignment")
    if alignment_data is not None and not isinstance(alignment_data, dict):
        raise ConfigurationError("final report config pitching.alignment must be an object")
    previous_assets = resolve_path(pitching.get("previous_assets"), root=root)
    return FinalReportConfig(
        config_path=config_path,
        root=root,
        batting_config=_required_path(data, "batting_config", root, label),
        pitching_manifest=_required_path(pitching, "manifest", root, f"{label} pitching"),
        pitching_template_dir=_required_path(
            pitching, "template_dir", root, f"{label} pitching"
        ),
        pitching_out_dir=_required_path(pitching, "out_dir", root, f"{label} pitching"),
        pitching_previous_assets=previous_assets,
        pitching_alignment=(
            _load_alignment(alignment_data, root=root) if alignment_data is not None else None
        ),
    )


def load_pitching_manifest(path: Path | str) -> PitchingManifestConfig:
    manifest_path = Path(path).expanduser().resolve()
    try:
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"pitching manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(
            "pitching manifest is not valid JSON at "
            f"line {exc.lineno}, column {exc.colno}: {manifest_path}"
        ) from exc
    rows = data.get("athletes") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ConfigurationError(
            f"Pitching manifest must contain a non-empty athletes array: {manifest_path}"
        )
    athletes: list[PitchingAthleteConfig] = []
    for index, row in enumerate(rows, start=1):
        label = f"pitching manifest athletes[{index}]"
        if not isinstance(row, dict):
            raise ConfigurationError(f"{label} must be an object")
        key = _validate_slug(_required_text(row, "key", label), "key", label)
        role = _required_text(row, "role", label)
        if role not in {"student", "coach"}:
            raise ConfigurationError(f"{label}.role must be 'student' or 'coach'")
        athletes.append(
            PitchingAthleteConfig(
                key=key,
                name=_required_text(row, "name", label),
                role=role,
                c3d=_required_path(row, "c3d", manifest_path.parent, label),
            )
        )
    keys = [athlete.key for athlete in athletes]
    if len(keys) != len(set(keys)):
        raise ConfigurationError(f"Pitching manifest athlete keys must be unique: {manifest_path}")
    coaches = [athlete for athlete in athletes if athlete.role == "coach"]
    if len(coaches) != 1 or coaches[0].key != "coach":
        raise ConfigurationError(
            "Pitching manifest must contain exactly one role='coach' athlete with key='coach'"
        )
    if not any(athlete.role == "student" and athlete.key != "coach" for athlete in athletes):
        raise ConfigurationError("Pitching manifest must contain at least one student athlete")
    if athletes[0].role != "student" or athletes[0].key == "coach":
        raise ConfigurationError(
            "Pitching manifest must place the report subject student in the first row"
        )
    return PitchingManifestConfig(manifest_path, tuple(athletes))


def _missing_file(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_file():
        errors.append(f"{label} file does not exist: {path}")


def _missing_dir(path: Path, label: str, errors: list[str]) -> None:
    if not path.is_dir():
        errors.append(f"{label} directory does not exist: {path}")


def _check_parent(path: Path, label: str, errors: list[str]) -> None:
    parent = path
    while not parent.exists() and parent != parent.parent:
        parent = parent.parent
    if not parent.is_dir():
        errors.append(f"{label} has no existing parent directory: {path}")
    elif not os.access(parent, os.W_OK):
        errors.append(f"{label} parent is not writable: {parent}")


def preflight_final_report(
    config: FinalReportConfig,
    *,
    execution: ExecutionName,
    skip_pitching_alignment: bool = False,
) -> PreflightResult:
    if execution not in {"pitching", "batting", "final"}:
        raise ConfigurationError(f"Unsupported report execution: {execution}")
    errors: list[str] = []
    warnings: list[str] = []
    resolved: list[tuple[str, Path]] = [
        ("repository_root", REPO_ROOT),
        ("final_config", config.config_path),
        ("batting_config", config.batting_config),
        ("pitching_manifest", config.pitching_manifest),
        ("pitching_template_dir", config.pitching_template_dir),
        ("pitching_out_dir", config.pitching_out_dir),
    ]
    _missing_file(config.batting_config, "batting config", errors)
    _missing_file(config.pitching_manifest, "pitching manifest", errors)
    _missing_file(config.pitching_template_dir / "index.html", "pitching template", errors)
    _check_parent(config.pitching_out_dir, "pitching output", errors)
    if config.pitching_previous_assets is not None:
        errors.append(
            "pitching.previous_assets is deprecated and rejected by the current pitching builder"
        )

    batting: PipelineConfig | None = None
    if config.batting_config.is_file():
        try:
            batting = load_pipeline_config(config.batting_config)
        except ConfigurationError as exc:
            errors.append(str(exc))
    manifest: PitchingManifestConfig | None = None
    if config.pitching_manifest.is_file():
        try:
            manifest = load_pitching_manifest(config.pitching_manifest)
        except ConfigurationError as exc:
            errors.append(str(exc))

    if manifest is not None:
        resolved.extend(
            (f"pitching_c3d.{athlete.key}", athlete.c3d) for athlete in manifest.athletes
        )
        if execution in {"pitching", "final"}:
            for athlete in manifest.athletes:
                _missing_file(athlete.c3d, f"pitching C3D ({athlete.key})", errors)

    if batting is not None:
        resolved.extend(
            (
                ("batting_report_dir", batting.report_dir),
                ("batting_pitch_report", batting.pitch_report),
                ("batting_c3d_dir", batting.c3d_dir),
                ("batting_peers", batting.peers),
                ("batting_xlsx_out_dir", batting.xlsx_out_dir),
            )
        )
        if batting.report_dir == config.pitching_out_dir:
            errors.append("Pitching and combined batting output directories must be distinct")
        if batting.pitch_report != config.pitch_html:
            errors.append(
                "Batting pitch_report must match pitching.out_dir/index.html: "
                f"{batting.pitch_report} != {config.pitch_html}"
            )
        if manifest is not None and batting.player_slug != manifest.player.key:
            errors.append(
                "Batting player_slug must match the first pitching student athlete key: "
                f"{batting.player_slug!r} != {manifest.player.key!r}"
            )
        _check_parent(batting.report_dir, "combined batting output", errors)
        _check_parent(batting.xlsx_out_dir, "batting XLSX output", errors)
        if execution in {"batting", "final"}:
            _missing_dir(batting.c3d_dir, "batting C3D input", errors)
            if not batting.peers.exists():
                warnings.append(
                    "Configured batting peers input does not exist; the current builder will use "
                    f"its report-CSV fallback: {batting.peers}"
                )
            if batting.alignment_dir is not None:
                errors.append(
                    "The public batting pipeline does not accept a prebuilt alignment_dir"
                )
            if batting.video is not None:
                for path, label in (
                    (batting.video, "batting video"),
                    (batting.c3d_file, "batting alignment C3D"),
                    (batting.mediapipe_model, "batting MediaPipe model"),
                ):
                    if path is None:
                        errors.append(f"{label} is required when batting video is configured")
                    else:
                        _missing_file(path, label, errors)
                if batting.video_capture_fps is None or batting.video_event_frame is None:
                    errors.append(
                        "Batting video requires reviewed video_capture_fps and video_event_frame"
                    )
        if execution == "batting":
            _missing_file(config.pitch_html, "current pitching report", errors)

    alignment = config.pitching_alignment
    if alignment is not None:
        resolved.extend(
            (
                ("pitching_alignment_video", alignment.video),
                ("pitching_alignment_c3d", alignment.c3d),
                ("pitching_alignment_model", alignment.model),
                ("pitching_alignment_out_dir", alignment.out_dir),
            )
        )
        if manifest is not None and alignment.player_slug != manifest.player.key:
            errors.append(
                "pitching.alignment.player_slug must match the first student athlete key: "
                f"{alignment.player_slug!r} != {manifest.player.key!r}"
            )
        if manifest is not None and alignment.c3d != manifest.player.c3d:
            errors.append(
                "pitching.alignment.c3d must match the first student athlete C3D: "
                f"{alignment.c3d} != {manifest.player.c3d}"
            )
        if execution in {"pitching", "final"} and not skip_pitching_alignment:
            _missing_file(alignment.video, "pitching alignment video", errors)
            _missing_file(alignment.c3d, "pitching alignment C3D", errors)
            _missing_file(alignment.model, "pitching alignment model", errors)
            _check_parent(alignment.out_dir, "pitching alignment output", errors)
        elif skip_pitching_alignment:
            warnings.append("Configured pitching alignment will be skipped by explicit CLI flag")

    if config.pitching_template_dir == config.pitching_out_dir:
        warnings.append(
            "Pitching template_dir and out_dir are identical; the tracked template is also a generated target"
        )
    if config.pitching_out_dir.exists():
        warnings.append(f"Pitching output already exists and may be regenerated: {config.pitching_out_dir}")
    if batting is not None and batting.report_dir.exists():
        warnings.append(f"Combined report output already exists: {batting.report_dir}")
    return PreflightResult(execution, tuple(errors), tuple(warnings), tuple(resolved))
