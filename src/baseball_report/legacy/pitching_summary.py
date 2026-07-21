from __future__ import annotations

import json
import math
from pathlib import Path

from baseball_report.core.enums import CoordinateProfile, MotionType, QualityStatus, Side, WarningSeverity
from baseball_report.core.errors import InputDataError
from baseball_report.core.frames import FrameReference, FrameWindow
from baseball_report.core.motion import AnalysisContext
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.events.models import EventCollection, MotionEvent
from baseball_report.metrics.models import MetricResult

from .models import LegacyAdaptedReport, LegacyAnalysisBundle
from .json_values import normalize_legacy_json

# Exact report-facing registry metadata copied from the current pitching builder.
PITCHING_REPORT_METRICS: dict[str, tuple[str, str, str, str, str | None]] = {
    "knee_height_pct": ("抬腿高度", "Knee Lift Height", "pct", "准备阶段", "peak_knee"),
    "front_knee_peak_deg": ("前腿收紧", "Lead-Knee Tuck", "deg", "准备阶段", "peak_knee"),
    "rear_knee_peak_deg": ("后腿蓄力", "Rear-Leg Load", "deg", "准备阶段", "peak_knee"),
    "stride_distance_pct": ("跨步距离", "Stride Distance", "pct", "前脚落地", "foot_plant"),
    "stride_direction_deg": ("跨步方向", "Stride Direction", "deg", "前脚落地", "foot_plant"),
    "front_knee_plant_deg": ("前膝屈曲", "Lead-Knee Flexion", "deg", "前脚落地", "foot_plant"),
    "rear_knee_plant_deg": ("后膝屈曲", "Rear-Knee Flexion", "deg", "前脚落地", "foot_plant"),
    "elbow_vs_shoulder_cm": ("投球肘相对肩线", "Throwing-Elbow Height", "cm", "前脚落地", "foot_plant"),
    "shoulder_abduction_plant_deg": ("肩外展", "Shoulder Abduction", "deg", "前脚落地", "foot_plant"),
    "front_knee_release_deg": ("出手前膝角", "Release Lead-Knee Angle", "deg", "出手点", "release"),
    "front_knee_change_plant_to_release_deg": ("落地到出手前膝变化", "Lead-Knee Change: Plant to Release", "deg", "出手点", "release"),
    "shoulder_abduction_release_deg": ("出手肩外展", "Release Shoulder Abduction", "deg", "出手点", "release"),
    "elbow_flex_release_deg": ("出手肘屈曲", "Release Elbow Flexion", "deg", "出手点", "release"),
    "arm_slot_deg": ("出手手臂角度", "Release Arm Angle", "deg", "出手点", "release"),
    "release_height_pct": ("出手高度", "Release Height", "pct", "出手点", "release"),
    "hand_speed_kmh": ("出手手速", "Release Hand Speed", "kmh", "出手点", "release"),
    "max_hss_deg": ("最大髋肩分离", "Maximum Hip-Shoulder Separation", "deg", "专项问题", None),
    "hss_release_amount_deg": ("髋肩分离释放量", "Hip-Shoulder Separation Release", "deg", "专项问题", None),
}

_AUXILIARY_UNITS = {
    "elbow_flex_plant_deg": "deg",
    "foot_contact_time_s": "s",
    "foot_plant_time_s": "s",
    "front_hip_peak_deg": "deg",
    "front_knee_change_contact_to_release_deg": "deg",
    "front_toe_direction_deg": "deg",
    "hss_peak_knee_deg": "deg",
    "hss_plant_deg": "deg",
    "hss_release_deg": "deg",
    "knee_height_mm": "mm",
    "max_hss_time_s": "s",
    "peak_knee_time_s": "s",
    "rear_ankle_peak_deg": "deg",
    "rear_knee_drive_extension_deg": "deg",
    "rear_knee_release_deg": "deg",
    "release_forward_mm": "mm",
    "release_height_mm": "mm",
    "release_lateral_mm": "mm",
    "release_time_s": "s",
    "shoulder_rotation_release_deg": "deg",
    "stride_distance_mm": "mm",
    "wrist_flex_release_deg": "deg",
    "wrist_vs_shoulder_cm": "cm",
}


def _finite_value(raw: object, metric_id: str) -> tuple[float | None, tuple[AnalysisWarning, ...]]:
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = float("nan")
    if math.isfinite(value):
        return value, ()
    return None, (
        AnalysisWarning(
            code="legacy.metric.unavailable",
            message=f"Legacy pitching metric {metric_id} has no finite value",
            context={"raw_value": repr(raw)},
        ),
    )


def adapt_pitching_summary_json(path: str | Path) -> LegacyAdaptedReport:
    """Read current pitch_metrics_summary.json into additive typed results."""

    source_path = Path(path)
    try:
        payload = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputDataError(f"cannot read legacy pitching summary {source_path}: {exc}") from exc
    athletes = payload.get("athletes")
    if not isinstance(athletes, list):
        raise InputDataError("legacy pitching summary must contain an athletes list")

    bundles: list[LegacyAnalysisBundle] = []
    for athlete in athletes:
        if not isinstance(athlete, dict):
            raise InputDataError("legacy pitching athlete rows must be objects")
        sequence_id = str(athlete.get("key", "")).strip()
        if not sequence_id:
            raise InputDataError("legacy pitching athlete key is required")
        rate_hz = float(athlete.get("rate_hz", 0))
        if not math.isfinite(rate_hz) or rate_hz <= 0:
            raise InputDataError(f"invalid rate_hz for pitching athlete {sequence_id}")
        event_values = athlete.get("events", {})
        metric_values = athlete.get("values", {})
        if not isinstance(event_values, dict) or not isinstance(metric_values, dict):
            raise InputDataError(f"events and values must be objects for pitching athlete {sequence_id}")
        events: dict[str, MotionEvent] = {}
        for event_id, raw_frame in event_values.items():
            frame_index = int(raw_frame)
            frame_ref = FrameReference(
                sequence_index=frame_index,
                source_frame_number=None,
                timestamp_seconds=frame_index / rate_hz,
                source_clock="vicon_loaded_sequence",
            )
            events[event_id] = MotionEvent(
                event_id=event_id,
                sequence_id=sequence_id,
                motion_type=MotionType.PITCHING,
                display_name_zh=event_id,
                display_name_en=event_id,
                primary_frame=frame_ref,
                window=FrameWindow(indices=(frame_index,), primary=frame_ref),
                detector_id="legacy.pitching_summary.event",
                rule="preserved from pitch_metrics_summary.json",
                source="legacy_pitching_summary",
                quality=QualityStatus.VALID,
            )
        provenance = Provenance(
            source_type="legacy_json",
            source_id=sequence_id,
            algorithm_id="scripts.pitching.build_pitch_template_metrics_report",
            details={"source_file": athlete.get("source_file"), "adapter_source": source_path.name},
        )
        metrics: list[MetricResult] = []
        for metric_id, raw_value in metric_values.items():
            metadata = PITCHING_REPORT_METRICS.get(metric_id)
            if metadata is None:
                name_zh = metric_id
                name_en = metric_id
                unit = _AUXILIARY_UNITS.get(metric_id)
                legacy_event_name = None
                event_id = None
                contract_scope = "auxiliary"
            else:
                name_zh, name_en, unit, legacy_event_name, event_id = metadata
                contract_scope = "report"
            value, warnings = _finite_value(raw_value, metric_id)
            metric_warnings = list(warnings)
            normalized_raw, non_finite_paths = normalize_legacy_json(
                raw_value, "legacy_raw_value"
            )
            if non_finite_paths:
                metric_warnings.append(
                    AnalysisWarning(
                        code="legacy.metadata.non_finite",
                        message=f"Legacy pitching metric {metric_id} contained a non-finite raw value",
                        context={"replaced_with_null": list(non_finite_paths)},
                    )
                )
            if metric_id == "hand_speed_kmh":
                metric_warnings.append(
                    AnalysisWarning(
                        code="pitching.hand_speed.proxy",
                        message="Pitching hand speed is a hand-marker proxy, not ball speed",
                        severity=WarningSeverity.INFO,
                    )
                )
            event_frame = events[event_id].primary_frame if event_id in events else None
            metrics.append(
                MetricResult(
                    metric_id=metric_id,
                    definition_version="legacy.pitching_summary.v1",
                    sequence_id=sequence_id,
                    motion_type=MotionType.PITCHING,
                    display_name_zh=name_zh,
                    display_name_en=name_en,
                    value=value,
                    unit=unit,
                    event_id=event_id,
                    event_frame=event_frame,
                    side=None,
                    reference_value=None,
                    difference=None,
                    status="available" if value is not None else "unavailable",
                    quality=QualityStatus.VALID if value is not None else QualityStatus.UNAVAILABLE,
                    warnings=tuple(metric_warnings),
                    components={
                        "legacy_event_name": legacy_event_name,
                        "contract_scope": contract_scope,
                        "legacy_raw_value": normalized_raw,
                    },
                    provenance=provenance,
                )
            )
        context = AnalysisContext(
            subject_id=sequence_id,
            motion_type=MotionType.PITCHING,
            batting_side=None,
            throwing_arm=Side.RIGHT,
            lead_side=Side.LEFT,
            trail_side=Side.RIGHT,
            coordinate_system=CoordinateProfile.LEGACY_VICON_Z_UP_MM,
            length_unit="mm",
            algorithm_profile="legacy_pitching_right_v1",
        )
        bundles.append(
            LegacyAnalysisBundle(
                sequence_id=sequence_id,
                context=context,
                events=EventCollection(events=events),
                metrics=tuple(metrics),
                metadata={
                    "name": athlete.get("name"),
                    "role": athlete.get("role"),
                    "source_file": athlete.get("source_file"),
                    "frames": athlete.get("frames"),
                    "rate_hz": rate_hz,
                    "height_estimate_mm": athlete.get("height_estimate_mm"),
                    "floor_estimate_mm": athlete.get("floor_estimate_mm"),
                    "assumptions": payload.get("assumptions", {}),
                },
            )
        )
    return LegacyAdaptedReport(source_path=source_path, bundles=tuple(bundles))
