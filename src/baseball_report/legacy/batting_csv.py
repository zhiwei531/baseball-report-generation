from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

from baseball_report.core.enums import (
    CoordinateProfile,
    Handedness,
    MotionType,
    QualityStatus,
    Side,
    WarningSeverity,
)
from baseball_report.core.errors import InputDataError
from baseball_report.core.frames import FrameReference, FrameWindow
from baseball_report.core.motion import AnalysisContext
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.events.models import EventCollection, MotionEvent
from baseball_report.metrics.models import MetricResult

from .models import LegacyAdaptedReport, LegacyAnalysisBundle

REQUIRED_COLUMNS = (
    "trial_id",
    "sample_name",
    "athlete",
    "action_type",
    "source_file",
    "module",
    "metric_name_zh",
    "metric_key",
    "value",
    "unit",
    "aggregation",
    "event_name",
    "event_rule",
    "event_frame",
    "event_frames",
    "points_used",
    "formula",
    "components_json",
    "notes",
)


def _parse_indices(value: str, primary: int | None) -> tuple[int, ...]:
    try:
        indices = tuple(int(part) for part in value.split(";") if part.strip())
    except ValueError as exc:
        raise InputDataError(f"invalid legacy batting event_frames: {value!r}") from exc
    if not indices and primary is not None:
        indices = (primary,)
    return indices


def _parse_primary(value: str) -> int | None:
    if not value.strip():
        return None
    try:
        primary = int(value)
    except ValueError as exc:
        raise InputDataError(f"invalid legacy batting event_frame: {value!r}") from exc
    if primary < 0:
        raise InputDataError("legacy batting event_frame must be non-negative")
    return primary


def _parse_value(value: str, metric_id: str) -> tuple[float | None, tuple[AnalysisWarning, ...]]:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = float("nan")
    if math.isfinite(parsed):
        return parsed, ()
    warning = AnalysisWarning(
        code="legacy.metric.unavailable",
        message=f"Legacy batting metric {metric_id} has no finite value",
        context={"raw_value": value},
    )
    return None, (warning,)


def _parse_components(value: str, metric_id: str) -> dict[str, object]:
    if not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise InputDataError(f"invalid components_json for {metric_id}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise InputDataError(f"components_json for {metric_id} must contain an object")
    return parsed


def adapt_batting_metrics_csv(path: str | Path) -> LegacyAdaptedReport:
    """Read the current long-form batting CSV without changing or rewriting it."""

    source_path = Path(path)
    try:
        with source_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or ())]
            if missing:
                raise InputDataError(f"legacy batting CSV is missing columns: {', '.join(missing)}")
            rows = list(reader)
    except OSError as exc:
        raise InputDataError(f"cannot read legacy batting CSV {source_path}: {exc}") from exc
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row["trial_id"], row["sample_name"], row["athlete"])].append(row)

    bundles: list[LegacyAnalysisBundle] = []
    report_warnings: list[AnalysisWarning] = []
    for (trial_id, sample_name, athlete), trial_rows in grouped.items():
        events: dict[str, MotionEvent] = {}
        metrics: list[MetricResult] = []
        bundle_warnings: list[AnalysisWarning] = []
        for row in trial_rows:
            metric_id = row["metric_key"]
            primary_index = _parse_primary(row["event_frame"])
            indices = _parse_indices(row["event_frames"], primary_index)
            frame_ref = None
            event_id = row["event_name"] or None
            if primary_index is not None:
                frame_ref = FrameReference(
                    sequence_index=primary_index,
                    source_frame_number=None,
                    timestamp_seconds=None,
                    source_clock="vicon_loaded_sequence",
                )
            if event_id and frame_ref is not None and indices:
                if primary_index not in indices:
                    raise InputDataError(
                        f"legacy batting metric {metric_id} primary event frame is outside event_frames"
                    )
                candidate = MotionEvent(
                    event_id=event_id,
                    sequence_id=trial_id,
                    motion_type=MotionType.BATTING,
                    display_name_zh=event_id,
                    display_name_en=event_id,
                    primary_frame=frame_ref,
                    window=FrameWindow(indices=indices, primary=frame_ref),
                    detector_id="legacy.batting_csv.event",
                    rule=row["event_rule"] or "legacy event rule unavailable",
                    source="legacy_batting_csv",
                    quality=QualityStatus.VALID,
                    metadata={"legacy_event_frames": row["event_frames"]},
                )
                existing = events.get(event_id)
                if existing is None:
                    events[event_id] = candidate
                elif existing.window.indices != candidate.window.indices:
                    warning = AnalysisWarning(
                        code="legacy.event.window_conflict",
                        message=f"Legacy event {event_id} has multiple windows in trial {trial_id}",
                        context={"metric_id": metric_id, "event_frames": row["event_frames"]},
                    )
                    bundle_warnings.append(warning)
            value, value_warnings = _parse_value(row["value"], metric_id)
            metric_warnings = list(value_warnings)
            if event_id == "Contact Position":
                metric_warnings.append(
                    AnalysisWarning(
                        code="batting.contact.proxy",
                        message="Contact Position is the legacy lowest-Bat1_Z proxy, not verified bat-ball contact",
                        severity=WarningSeverity.INFO,
                    )
                )
            components = _parse_components(row["components_json"], metric_id)
            components["legacy_fields"] = {
                "module": row["module"],
                "aggregation": row["aggregation"],
                "event_name": row["event_name"],
                "event_rule": row["event_rule"],
                "event_frame": row["event_frame"],
                "event_frames": row["event_frames"],
                "points_used": row["points_used"],
                "formula": row["formula"],
                "notes": row["notes"],
                "source_file": row["source_file"],
            }
            provenance = Provenance(
                source_type="legacy_csv",
                source_id=trial_id,
                algorithm_id="scripts.build_batting_dashboard_metrics",
                details={"source_file": row["source_file"], "adapter_source": source_path.name},
            )
            metrics.append(
                MetricResult(
                    metric_id=metric_id,
                    definition_version="legacy.batting_csv.v1",
                    sequence_id=trial_id,
                    motion_type=MotionType.BATTING,
                    display_name_zh=row["metric_name_zh"],
                    display_name_en=metric_id,
                    value=value,
                    unit=row["unit"] or None,
                    event_id=event_id,
                    event_frame=frame_ref,
                    side=None,
                    reference_value=None,
                    difference=None,
                    status="available" if value is not None else "unavailable",
                    quality=QualityStatus.VALID if value is not None else QualityStatus.UNAVAILABLE,
                    warnings=tuple(metric_warnings),
                    components=components,
                    provenance=provenance,
                )
            )
        context = AnalysisContext(
            subject_id=sample_name,
            motion_type=MotionType.BATTING,
            batting_side=Handedness.RIGHT,
            throwing_arm=None,
            lead_side=Side.LEFT,
            trail_side=Side.RIGHT,
            coordinate_system=CoordinateProfile.LEGACY_VICON_Z_UP_MM,
            length_unit="mm",
            algorithm_profile="legacy_batting_right_v1",
        )
        bundles.append(
            LegacyAnalysisBundle(
                sequence_id=trial_id,
                context=context,
                events=EventCollection(events=events, warnings=tuple(bundle_warnings)),
                metrics=tuple(metrics),
                metadata={
                    "sample_name": sample_name,
                    "athlete": athlete,
                    "source_file": trial_rows[0]["source_file"],
                    "action_type": trial_rows[0]["action_type"],
                },
                warnings=tuple(bundle_warnings),
            )
        )
        report_warnings.extend(bundle_warnings)
    return LegacyAdaptedReport(source_path=source_path, bundles=tuple(bundles), warnings=tuple(report_warnings))
