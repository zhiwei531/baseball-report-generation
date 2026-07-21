from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
import re

from baseball_report.core.enums import MotionType, QualityStatus
from baseball_report.core.provenance import Provenance
from baseball_report.reporting.models import ReportAsset


SUPPORTED_ASSET_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".svg", ".json", ".csv"}
)
IGNORED_NAMES = frozenset({".DS_Store"})

BATTING_ILLUSTRATION_METRICS: dict[str, tuple[str, ...]] = {
    "ready_balance": ("ready_com_height_ratio", "ready_to_contact_head_displacement_mm"),
    "ready_lower_body_load": ("ready_rear_hip_flexion_deg", "ready_rear_knee_flexion_deg"),
    "ready_torso_coil": ("ready_hip_shoulder_separation_deg",),
    "ready_bat_readiness": ("ready_bat_tilt_deg", "ready_hand_height_ratio"),
    "contact_bat_efficiency": ("contact_bat_speed_kmh",),
    "contact_swing_path": ("contact_attack_angle_deg",),
    "contact_lower_body_posture": ("contact_pelvis_rotation_open_deg",),
    "contact_upper_body_posture": ("contact_torso_rotation_open_deg",),
    "contact_front_leg_support": ("contact_front_knee_flexion_deg",),
    "contact_stability": ("ready_to_contact_head_displacement_mm",),
    "issue_high_center_of_mass": ("coach_high_com_risk_index",),
    "issue_dropped_rear_elbow": ("coach_rear_elbow_height_diff_mm",),
    "issue_insufficient_bat_load": ("coach_bat_loading_angle_to_catcher_deg",),
    "issue_early_wrist_roll": ("coach_rollover_forearm_roll_velocity_deg_s",),
}

PITCHING_METRIC_IDS = frozenset(
    {
        "knee_height_pct",
        "front_knee_peak_deg",
        "rear_knee_peak_deg",
        "stride_distance_pct",
        "stride_direction_deg",
        "front_knee_plant_deg",
        "rear_knee_plant_deg",
        "elbow_vs_shoulder_cm",
        "shoulder_abduction_plant_deg",
        "front_knee_release_deg",
        "front_knee_change_plant_to_release_deg",
        "shoulder_abduction_release_deg",
        "elbow_flex_release_deg",
        "arm_slot_deg",
        "release_height_pct",
        "hand_speed_kmh",
        "max_hss_deg",
        "hss_release_amount_deg",
        "rear_knee_drive_extension_deg",
    }
)

PITCHING_FLOW_METRICS = (
    "rear_knee_peak_deg",
    "stride_distance_pct",
    "max_hss_deg",
    "arm_slot_deg",
    "hand_speed_kmh",
)


def discover_report_assets(report_root: Path) -> tuple[ReportAsset, ...]:
    """Inventory existing report artifacts without interpreting their numbers."""

    root = report_root.resolve()
    if not root.is_dir():
        return ()
    assets: list[ReportAsset] = []
    for path in sorted(root.rglob("*")):
        if (
            not path.is_file()
            or path.name in IGNORED_NAMES
            or path.name.startswith("._")
            or any(part.startswith("_tmp_") for part in path.relative_to(root).parts)
        ):
            continue
        if path.suffix.lower() not in SUPPORTED_ASSET_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {"analysis_report_data.json", "analysis_report_view.json"}:
            continue
        mime_type, _encoding = mimetypes.guess_type(path.name)
        kind = _asset_kind(path.suffix.lower())
        motion_type, metric_ids, event_ids = infer_asset_association(relative)
        assets.append(
            ReportAsset(
                asset_id=(
                    "asset."
                    + re.sub(r"[^a-zA-Z0-9_.-]+", "_", relative)
                    + "."
                    + hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
                ),
                kind=kind,
                file_ref=relative,
                mime_type=mime_type,
                metric_ids=metric_ids,
                event_ids=event_ids,
                quality=QualityStatus.VALID,
                provenance=Provenance(
                    source_type="generated_report_artifact",
                    source_id=relative,
                    algorithm_id="baseball_report.visualization.manifest.discovery",
                ),
                metadata={
                    "size_bytes": path.stat().st_size,
                    "suffix": path.suffix.lower(),
                    "motion_scope": motion_type.value if motion_type is not None else None,
                    "association_source": "canonical_filename_v1" if metric_ids or event_ids else None,
                },
            )
        )
    return tuple(assets)


def infer_asset_association(
    relative_ref: str,
) -> tuple[MotionType | None, tuple[str, ...], tuple[str, ...]]:
    """Infer only filename associations established by current report builders."""

    relative = relative_ref.casefold()
    stem = Path(relative_ref).stem.removesuffix("_annotated")
    metrics: tuple[str, ...] = ()
    events: tuple[str, ...] = ()
    motion_type: MotionType | None = None

    if relative.startswith("pitch_assets/") or "frontend_metric_illustrations_pitch" in relative:
        motion_type = MotionType.PITCHING
    elif "_pitch_" in relative or "/pitch_" in relative:
        motion_type = MotionType.PITCHING
    elif "batting_" in relative or stem in BATTING_ILLUSTRATION_METRICS:
        motion_type = MotionType.BATTING
    elif any(token in relative for token in ("alignment_2d/", "vicon_2d_geometry_annotations/")):
        motion_type = MotionType.BATTING

    if stem in BATTING_ILLUSTRATION_METRICS:
        metrics = BATTING_ILLUSTRATION_METRICS[stem]
    elif stem in PITCHING_METRIC_IDS:
        motion_type = MotionType.PITCHING
        metrics = (stem,)
    elif stem == "hand_speed_mps" and motion_type == MotionType.PITCHING:
        metrics = ("hand_speed_kmh",)
    elif "bat1_speed_time_curve" in relative:
        motion_type = MotionType.BATTING
        metrics = ("contact_bat_speed_kmh",)
    elif "bat_axis_angle_time_curve" in relative:
        motion_type = MotionType.BATTING
        metrics = ("contact_attack_angle_deg",)
    elif "batting_kinetic_chain_flow" in relative or "batting_kinetic_speed_time_curve" in relative:
        motion_type = MotionType.BATTING
        metrics = (
            "ready_rear_knee_flexion_deg",
            "ready_hip_shoulder_separation_deg",
            "contact_pelvis_rotation_open_deg",
            "contact_torso_rotation_open_deg",
            "contact_bat_speed_kmh",
        )
    elif "pitch_speed_time_curve" in relative:
        motion_type = MotionType.PITCHING
        metrics = ("hand_speed_kmh",)
    elif "pitch_angle_time_curve" in relative:
        motion_type = MotionType.PITCHING
        metrics = tuple(
            metric_id
            for metric_id in PITCHING_METRIC_IDS
            if metric_id.endswith("_deg")
        )
    elif "pitch_kinetic_chain_flow" in relative or "kinetic_chain_time_curves" in relative:
        motion_type = MotionType.PITCHING
        metrics = PITCHING_FLOW_METRICS

    if re.search(r"(?:^|[/_])ready(?:[._/]|$)", relative):
        motion_type = motion_type or MotionType.BATTING
        events = ("Ready Position",)
    elif re.search(r"(?:^|[/_])contact(?:[._/]|$)", relative):
        motion_type = motion_type or MotionType.BATTING
        events = ("Contact Position",)
    elif "peak_knee" in relative:
        motion_type = MotionType.PITCHING
        events = ("peak_knee",)
    elif "foot_plant" in relative:
        motion_type = MotionType.PITCHING
        events = ("foot_plant",)
    elif re.search(r"(?:^|[/_])release(?:[._/]|$)", relative):
        motion_type = MotionType.PITCHING
        events = ("release",)

    return motion_type, tuple(sorted(metrics)), events


def _asset_kind(suffix: str) -> str:
    if suffix in {".png", ".jpg", ".jpeg", ".svg"}:
        return "image"
    if suffix == ".gif":
        return "animation"
    if suffix == ".mp4":
        return "video"
    return "data"
