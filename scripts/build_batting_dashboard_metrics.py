from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from kinematics import (
    circular_difference_deg,
    finite_mean as _finite_mean,
    finite_scalar as _finite_scalar,
    joint_angle_deg,
    signed_angle_about_axis_deg,
    speed_kmh_from_mm,
    vector_angle_deg as _vector_angle_deg,
    velocity_mm_s as _velocity_mm_s,
    xy_angle_deg as _xy_angle_deg,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTS = ROOT / "reports" / "vicon_2026_julian_coach" / "vicon_2026_points_all.csv"
DEFAULT_OUT = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics.csv"
DEFAULT_WIDE_OUT = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics_wide.csv"


@dataclass
class TrialSeries:
    trial_id: str
    sample_name: str
    athlete: str
    action_type: str
    source_file: str
    frames: np.ndarray
    timestamps: np.ndarray
    points: dict[str, np.ndarray]

    @property
    def rate_hz(self) -> float:
        if len(self.timestamps) < 2:
            return float("nan")
        diffs = np.diff(self.timestamps)
        diffs = diffs[np.isfinite(diffs) & (diffs > 0)]
        if diffs.size == 0:
            return float("nan")
        return float(1.0 / np.median(diffs))


def finite_mean(values: np.ndarray, axis: int = 0) -> np.ndarray:
    return _finite_mean(values, axis=axis)


def finite_scalar(values: np.ndarray, fn: str = "mean") -> float:
    return _finite_scalar(values, fn)


def load_trials(path: Path) -> list[TrialSeries]:
    metadata: dict[str, dict[str, str]] = {}
    frame_times: dict[str, dict[int, float]] = defaultdict(dict)
    raw_points: dict[str, dict[str, dict[int, np.ndarray]]] = defaultdict(lambda: defaultdict(dict))

    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("valid") != "1":
                continue
            trial_id = row["trial_id"]
            metadata.setdefault(
                trial_id,
                {
                    "sample_name": row["sample_name"],
                    "athlete": row["athlete"],
                    "action_type": row["action_type"],
                    "source_file": row["source_file"],
                },
            )
            frame = int(row["frame_index"])
            frame_times[trial_id][frame] = float(row["timestamp_sec"])
            raw_points[trial_id][row["point"]][frame] = np.array(
                [float(row["x_mm"]), float(row["y_mm"]), float(row["z_mm"])],
                dtype=float,
            )

    trials: list[TrialSeries] = []
    for trial_id in sorted(metadata):
        frame_ids = np.array(sorted(frame_times[trial_id]), dtype=int)
        timestamps = np.array([frame_times[trial_id][idx] for idx in frame_ids], dtype=float)
        frame_to_pos = {frame: pos for pos, frame in enumerate(frame_ids)}
        points: dict[str, np.ndarray] = {}
        for point_name, by_frame in raw_points[trial_id].items():
            arr = np.full((len(frame_ids), 3), np.nan, dtype=float)
            for frame, xyz in by_frame.items():
                arr[frame_to_pos[frame]] = xyz
            points[point_name] = arr
        meta = metadata[trial_id]
        trials.append(
            TrialSeries(
                trial_id=trial_id,
                sample_name=meta["sample_name"],
                athlete=meta["athlete"],
                action_type=meta["action_type"],
                source_file=meta["source_file"],
                frames=frame_ids,
                timestamps=timestamps,
                points=points,
            )
        )
    return trials


def point(trial: TrialSeries, *names: str) -> np.ndarray:
    series = [trial.points[name] for name in names if name in trial.points]
    if not series:
        return np.full((len(trial.frames), 3), np.nan, dtype=float)
    return finite_mean(np.stack(series), axis=0)


def speed_kmh(series_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    return speed_kmh_from_mm(series_mm, rate_hz)


def smooth_nan(values: np.ndarray, radius: int = 2) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    for idx in range(len(values)):
        start = max(0, idx - radius)
        end = min(len(values), idx + radius + 1)
        out[idx] = finite_scalar(values[start:end], "mean")
    return out


def velocity_mm_s(series_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    return _velocity_mm_s(series_mm, rate_hz)


def angle_at(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return joint_angle_deg(a, b, c)


def flexion_angle(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    return 180.0 - angle_at(a, b, c)


def xy_angle_deg(vec: np.ndarray) -> np.ndarray:
    return _xy_angle_deg(vec)


def circular_diff_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return circular_difference_deg(a, b)


def vector_angle_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return _vector_angle_deg(a, b)


def signed_angle_about_axis(radial: np.ndarray, axis: np.ndarray, reference: np.ndarray) -> np.ndarray:
    return signed_angle_about_axis_deg(radial, axis, reference)


def curvature_1_per_mm(path: np.ndarray) -> np.ndarray:
    p0 = path[:-2]
    p1 = path[1:-1]
    p2 = path[2:]
    a = np.linalg.norm(p1 - p0, axis=1)
    b = np.linalg.norm(p2 - p1, axis=1)
    c = np.linalg.norm(p2 - p0, axis=1)
    cross = np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    denom = a * b * c
    return np.divide(2.0 * cross, denom, out=np.full_like(denom, np.nan), where=denom > 0)


def infer_height_mm(head: np.ndarray, foot: np.ndarray, event_indices: np.ndarray) -> float:
    head_z = finite_scalar(head[event_indices, 2], "mean")
    foot_z = finite_scalar(foot[event_indices, 2], "mean")
    if math.isfinite(head_z) and math.isfinite(foot_z) and head_z > foot_z:
        return head_z - foot_z
    return float("nan")


def first_valid_event_indices(series: list[np.ndarray], count: int, n: int) -> np.ndarray:
    valid = np.ones(n, dtype=bool)
    for values in series:
        valid &= np.isfinite(values).all(axis=1)
    indices = np.where(valid)[0][:count]
    if indices.size:
        return indices
    return np.arange(min(count, n), dtype=int)


def lowest_z_event_indices(series: np.ndarray, count: int, candidates: np.ndarray | None = None) -> np.ndarray:
    if candidates is None:
        candidates = np.arange(series.shape[0])
    valid = np.array([idx for idx in candidates if np.isfinite(series[idx, 2])], dtype=int)
    if valid.size == 0:
        return np.array([], dtype=int)
    lowest = valid[np.argsort(series[valid, 2])[:count]]
    return np.array(sorted(lowest), dtype=int)


def detect_swing_segment(
    bat_speed_kmh: np.ndarray,
    rate_hz: float,
    *,
    threshold_ratio: float = 0.20,
    min_threshold_kmh: float = 8.0,
    expansion_sec: float = 0.15,
) -> tuple[np.ndarray, np.ndarray, int, float, float]:
    speed_smooth = smooth_nan(bat_speed_kmh, radius=2)
    if not np.isfinite(speed_smooth).any():
        fallback = np.arange(len(bat_speed_kmh), dtype=int)
        return fallback, fallback, len(bat_speed_kmh) // 2, float("nan"), float("nan")
    peak_idx = int(np.nanargmax(speed_smooth))
    peak_speed = float(speed_smooth[peak_idx])
    threshold = max(min_threshold_kmh, peak_speed * threshold_ratio)
    active = np.isfinite(speed_smooth) & (speed_smooth >= threshold)
    start = peak_idx
    while start > 0 and active[start - 1]:
        start -= 1
    end = peak_idx
    while end + 1 < len(active) and active[end + 1]:
        end += 1
    margin = max(1, round(expansion_sec * rate_hz))
    expanded_start = max(0, start - margin)
    expanded_end = min(len(active) - 1, end + margin)
    raw = np.arange(start, end + 1, dtype=int)
    expanded = np.arange(expanded_start, expanded_end + 1, dtype=int)
    return raw, expanded, peak_idx, peak_speed, threshold


def detect_ready_event(
    bat1: np.ndarray,
    bat5: np.ndarray,
    head: np.ndarray,
    bat_speed_kmh: np.ndarray,
    swing_start_idx: int,
    rate_hz: float,
    count: int,
    peak_speed_kmh: float,
    lookback_sec: float,
    valid_start_frame: int | None,
) -> np.ndarray:
    lookback = max(count, round(lookback_sec * rate_hz))
    start = max(0, swing_start_idx - lookback)
    if valid_start_frame is not None:
        start = max(start, valid_start_frame)
    stop = max(start, swing_start_idx)
    candidates = np.arange(start, stop, dtype=int)
    if candidates.size == 0:
        return first_valid_event_indices([bat1, bat5, head], count, len(bat1))

    valid = (
        np.isfinite(bat1[candidates]).all(axis=1)
        & np.isfinite(bat5[candidates]).all(axis=1)
        & np.isfinite(head[candidates]).all(axis=1)
        & np.isfinite(bat_speed_kmh[candidates])
    )
    valid_candidates = candidates[valid]
    if valid_candidates.size == 0:
        return first_valid_event_indices([bat1, bat5, head], count, len(bat1))

    speed_limit = max(6.0, peak_speed_kmh * 0.12) if math.isfinite(peak_speed_kmh) else 6.0
    low_speed = np.zeros(len(bat1), dtype=bool)
    low_speed[valid_candidates] = bat_speed_kmh[valid_candidates] <= speed_limit

    blocks: list[tuple[float, int, np.ndarray]] = []
    for block_start in range(start, max(start, stop - count + 1)):
        idx = np.arange(block_start, block_start + count, dtype=int)
        if idx[-1] >= stop:
            continue
        if not np.all(np.isin(idx, valid_candidates)):
            continue
        if not np.all(low_speed[idx]):
            continue
        bat_height = finite_scalar(bat1[idx, 2], "mean")
        mean_speed = finite_scalar(bat_speed_kmh[idx], "mean")
        if math.isfinite(bat_height):
            # Highest raised-bat block wins; slower blocks win ties.
            blocks.append((bat_height - 0.02 * mean_speed, block_start, idx))
    if blocks:
        return max(blocks, key=lambda item: (item[0], -item[1]))[2]

    low_speed_candidates = valid_candidates[bat_speed_kmh[valid_candidates] <= speed_limit]
    if low_speed_candidates.size >= count:
        return np.array(sorted(low_speed_candidates[:count]), dtype=int)
    return np.array(sorted(valid_candidates[:count]), dtype=int)


def indices_label(indices: np.ndarray) -> str:
    return ";".join(str(int(i)) for i in indices)


def event_frame(indices: np.ndarray) -> int | None:
    if indices.size == 0:
        return None
    return int(round(float(np.median(indices))))


def choose_batting_side() -> tuple[str, str]:
    # Current Vicon batting trials are treated as right-handed swings.
    return "R", "L"


def metric_row(
    trial: TrialSeries,
    module: str,
    name: str,
    key: str,
    value: float,
    unit: str,
    aggregation: str,
    event_name: str,
    event_rule: str,
    event_indices: np.ndarray,
    points_used: list[str],
    formula: str,
    notes: str = "",
    components: dict[str, float | str] | None = None,
) -> dict[str, object]:
    primary_event_frame = event_frame(event_indices)
    return {
        "trial_id": trial.trial_id,
        "sample_name": trial.sample_name,
        "athlete": trial.athlete,
        "action_type": trial.action_type,
        "source_file": trial.source_file,
        "module": module,
        "metric_name_zh": name,
        "metric_key": key,
        "value": value,
        "unit": unit,
        "aggregation": aggregation,
        "event_name": event_name,
        "event_rule": event_rule,
        "event_frame": "" if primary_event_frame is None else primary_event_frame,
        "event_frames": indices_label(event_indices),
        "points_used": ";".join(points_used),
        "formula": formula,
        "components_json": json.dumps(components or {}, ensure_ascii=False, sort_keys=True),
        "notes": notes,
    }


def compute_trial_metrics(
    trial: TrialSeries,
    ready_event_frames: int,
    contact_event_frames: int,
    ready_lookback_sec: float,
    ready_valid_start_frame: int | None,
) -> list[dict[str, object]]:
    rate_hz = trial.rate_hz
    n = len(trial.frames)

    rear, front = choose_batting_side()
    rear_prefix = rear
    front_prefix = front

    lhip = point(trial, "LASI", "LPSI")
    rhip = point(trial, "RASI", "RPSI")
    lsho = point(trial, "LSHO")
    rsho = point(trial, "RSHO")
    lkne = point(trial, "LKNE")
    rkne = point(trial, "RKNE")
    lank = point(trial, "LANK", "LHEE", "LTOE")
    rank = point(trial, "RANK", "RHEE", "RTOE")
    lelb = point(trial, "LELB")
    relb = point(trial, "RELB")
    lwrist = point(trial, "LWRA", "LWRB")
    rwrist = point(trial, "RWRA", "RWRB")
    head = point(trial, "LFHD", "RFHD", "LBHD", "RBHD")
    trunk_mid = point(trial, "C7", "T10", "CLAV", "STRN", "RBAK")
    bat1 = point(trial, "Bat1")
    bat5 = point(trial, "Bat5")
    bat_axis = bat1 - bat5
    bat_speed = speed_kmh(bat1, rate_hz)
    swing_raw, swing_segment, swing_peak_idx, swing_peak_speed, swing_threshold = detect_swing_segment(
        bat_speed, rate_hz
    )
    ready_event = detect_ready_event(
        bat1,
        bat5,
        head,
        bat_speed,
        int(swing_raw[0]) if swing_raw.size else swing_peak_idx,
        rate_hz,
        ready_event_frames,
        swing_peak_speed,
        ready_lookback_sec,
        ready_valid_start_frame,
    )
    contact_event = lowest_z_event_indices(bat1, contact_event_frames, candidates=swing_segment)
    if contact_event.size == 0:
        contact_event = np.array([swing_peak_idx], dtype=int)
    ready_rule = (
        f"{len(ready_event)} continuous low-speed raised-bat frames before detected swing; "
        f"ready search start frame {int(ready_event[0]) if ready_event.size else 'NA'}; "
        f"swing raw frames {int(swing_raw[0])}-{int(swing_raw[-1])}, "
        f"expanded frames {int(swing_segment[0])}-{int(swing_segment[-1])}"
    )
    contact_rule = (
        f"{len(contact_event)} frames with lowest Bat1_Z inside detected swing segment "
        f"{int(swing_segment[0])}-{int(swing_segment[-1])}"
    )

    hip_mid = finite_mean(np.stack([lhip, rhip]), axis=0)
    shoulder_mid = finite_mean(np.stack([lsho, rsho]), axis=0)
    com = point(trial, "CentreOfMass")
    com_fallback = 0.6 * hip_mid + 0.4 * trunk_mid
    com_valid = np.isfinite(com).all(axis=1)
    com = np.where(com_valid[:, None], com, com_fallback)
    feet = finite_mean(np.stack([lank, rank]), axis=0)
    height_mm = infer_height_mm(head, feet, ready_event)

    rear_hip = rhip if rear_prefix == "R" else lhip
    rear_knee = rkne if rear_prefix == "R" else lkne
    rear_ankle = rank if rear_prefix == "R" else lank
    rear_shoulder = rsho if rear_prefix == "R" else lsho
    rear_elbow = relb if rear_prefix == "R" else lelb
    rear_wrist_a = point(trial, "RWRA") if rear_prefix == "R" else point(trial, "LWRA")
    rear_wrist_b = point(trial, "RWRB") if rear_prefix == "R" else point(trial, "LWRB")
    front_hip = lhip if front_prefix == "L" else rhip
    front_knee = lkne if front_prefix == "L" else rkne
    front_ankle = lank if front_prefix == "L" else rank

    pelvis_angle = xy_angle_deg(front_hip - rear_hip)
    torso_angle = xy_angle_deg((lsho if front_prefix == "L" else rsho) - rear_shoulder)
    pelvis_ready = finite_scalar(pelvis_angle[ready_event], "mean")
    torso_ready = finite_scalar(torso_angle[ready_event], "mean")
    pelvis_open_signed = circular_diff_deg(pelvis_angle, pelvis_ready)
    torso_open_signed = circular_diff_deg(torso_angle, torso_ready)
    pelvis_open = np.abs(pelvis_open_signed)
    torso_open = np.abs(torso_open_signed)
    hip_shoulder_sep = np.abs(circular_diff_deg(torso_angle, pelvis_angle))

    rear_hip_flex = 180.0 - angle_at(shoulder_mid, rear_hip, rear_knee)
    rear_knee_flex = flexion_angle(rear_hip, rear_knee, rear_ankle)
    front_knee_flex = flexion_angle(front_hip, front_knee, front_ankle)
    bat_tilt = np.degrees(np.arctan2(np.abs(bat_axis[:, 2]), np.linalg.norm(bat_axis[:, :2], axis=1)))
    hand_center = finite_mean(np.stack([lwrist, rwrist]), axis=0)
    barrel_vel = velocity_mm_s(bat1, rate_hz)
    attack_angle = np.degrees(
        np.arctan2(barrel_vel[:, 2], np.linalg.norm(barrel_vel[:, :2], axis=1))
    )
    head_ready = finite_mean(head[ready_event], axis=0)
    head_contact = finite_mean(head[contact_event], axis=0)
    head_displacement = float(np.linalg.norm(head_contact - head_ready))

    com_height_norm = finite_scalar(com[ready_event, 2], "mean") / height_mm
    rear_hip_ready = finite_scalar(rear_hip_flex[ready_event], "mean")
    rear_knee_ready = finite_scalar(rear_knee_flex[ready_event], "mean")
    high_com_score = 100.0 * float(
        np.nanmean(
            [
                np.clip((com_height_norm - 0.48) / 0.14, 0.0, 1.0),
                np.clip((35.0 - rear_hip_ready) / 35.0, 0.0, 1.0),
                np.clip((35.0 - rear_knee_ready) / 35.0, 0.0, 1.0),
            ]
        )
    )

    rear_elbow_height_diff = finite_scalar((rear_elbow - rear_shoulder)[ready_event, 2], "mean")

    contact_velocity = finite_mean(barrel_vel[contact_event], axis=0)
    forward_xy = contact_velocity.copy()
    forward_xy[2] = 0.0
    catcher_xy = -forward_xy
    if np.linalg.norm(catcher_xy) == 0 or not np.isfinite(catcher_xy).all():
        catcher_xy = np.array([np.nan, np.nan, np.nan])
    barrel_to_knob = bat5 - bat1
    catcher_series = np.tile(catcher_xy, (n, 1))
    bat_loading_angle_series = vector_angle_deg(barrel_to_knob[:, :3] * [1, 1, 0], catcher_series)
    bat_loading_angle = finite_scalar(bat_loading_angle_series[ready_event], "mean")

    forearm_axis = rear_wrist_b - rear_elbow
    wrist_radial = rear_wrist_a - rear_wrist_b
    reference = np.tile(np.array([0.0, 0.0, 1.0]), (n, 1))
    forearm_roll = np.unwrap(np.radians(signed_angle_about_axis(wrist_radial, forearm_axis, reference)))
    forearm_roll_deg = np.degrees(forearm_roll)
    forearm_roll_vel = np.concatenate([[np.nan], np.diff(forearm_roll_deg) * rate_hz])
    rollover_vel_peak = finite_scalar(np.abs(forearm_roll_vel[contact_event]), "max")
    contact_center_idx = int(event_frame(contact_event) or contact_event[len(contact_event) // 2])

    high_speed_mask = np.zeros(n, dtype=bool)
    high_speed_mask[swing_segment] = (
        np.isfinite(bat_speed[swing_segment])
        & (bat_speed[swing_segment] >= finite_scalar(bat_speed[swing_segment], "max") * 0.9)
    )
    high_speed_indices = np.where(high_speed_mask)[0]
    if high_speed_indices.size:
        zone_path = bat1[high_speed_indices]
        zone_steps = np.linalg.norm(np.diff(zone_path, axis=0), axis=1)
        zone_length = finite_scalar(zone_steps, "sum") if zone_steps.size else 0.0
        zone_attack_std = finite_scalar(attack_angle[high_speed_indices], "std")
        zone_curvature = finite_scalar(curvature_1_per_mm(zone_path), "mean") if len(zone_path) >= 3 else float("nan")
    else:
        zone_length = float("nan")
        zone_attack_std = float("nan")
        zone_curvature = float("nan")
    length_score = np.clip(zone_length / 650.0, 0.0, 1.0)
    plane_score = np.clip(1.0 - zone_attack_std / 18.0, 0.0, 1.0)
    curvature_score = np.clip(1.0 - zone_curvature / 0.006, 0.0, 1.0)
    stability_score = 100.0 * float(np.nanmean([length_score, plane_score, curvature_score]))

    rows = [
        metric_row(
            trial,
            "Ready Position",
            "重心高度",
            "ready_com_height_ratio",
            com_height_norm,
            "height_ratio",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            ["CentreOfMass", "LASI", "RASI", "LPSI", "RPSI", "C7", "T10", "CLAV", "STRN", "LFHD", "RFHD", "LBHD", "RBHD", "LANK", "RANK", "LHEE", "RHEE", "LTOE", "RTOE"],
            "mean(COM_Z_ready_event) / height_proxy; COM=CentreOfMass if present else 0.6*hip_mid+0.4*trunk_mid; height_proxy=mean(head_Z_ready_event)-mean(feet_Z_ready_event)",
            "event-based, not fixed time window",
        ),
        metric_row(
            trial,
            "Ready Position",
            "后髋屈曲角",
            "ready_rear_hip_flexion_deg",
            rear_hip_ready,
            "deg",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            [f"{rear} hip", f"{rear} knee", "shoulder_mid"],
            "180 - angle(shoulder_mid, rear_hip, rear_knee)",
            "right-handed assumption: rear side=R, front side=L",
        ),
        metric_row(
            trial,
            "Ready Position",
            "后膝屈曲角",
            "ready_rear_knee_flexion_deg",
            rear_knee_ready,
            "deg",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            [f"{rear} hip", f"{rear} knee", f"{rear} ankle/heel/toe"],
            "180 - angle(rear_hip, rear_knee, rear_ankle)",
            "right-handed assumption: rear side=R, front side=L",
        ),
        metric_row(
            trial,
            "Ready Position",
            "髋肩分离角",
            "ready_hip_shoulder_separation_deg",
            finite_scalar(hip_shoulder_sep[ready_event], "mean"),
            "deg",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            ["LASI", "RASI", "LPSI", "RPSI", "LSHO", "RSHO"],
            "abs(wrap_to_180(torso_rotation_xy - pelvis_rotation_xy))",
            "event-based, not fixed time window",
        ),
        metric_row(
            trial,
            "Ready Position",
            "球棒倾角",
            "ready_bat_tilt_deg",
            finite_scalar(bat_tilt[ready_event], "mean"),
            "deg",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            ["Bat1", "Bat5"],
            "atan2(abs((Bat1-Bat5)_Z), norm((Bat1-Bat5)_XY))",
            "0 deg=parallel to ground, 90 deg=vertical",
        ),
        metric_row(
            trial,
            "Ready Position",
            "握棒手高度",
            "ready_hand_height_ratio",
            finite_scalar(hand_center[ready_event, 2], "mean") / height_mm,
            "height_ratio",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            ["LWRA", "LWRB", "RWRA", "RWRB", "LFHD", "RFHD", "LBHD", "RBHD", "LANK", "RANK", "LHEE", "RHEE", "LTOE", "RTOE"],
            "mean(grip_hand_center_Z_ready) / height_proxy; grip_hand_center=mean(left_wrist_center,right_wrist_center)",
            "event-based, not fixed time window",
        ),
        metric_row(
            trial,
            "Contact Position",
            "球棒速度",
            "contact_bat_speed_kmh",
            finite_scalar(bat_speed[contact_event], "mean"),
            "km/h",
            "event mean over Contact Position frames",
            "Contact Position",
            contact_rule,
            contact_event,
            ["Bat1"],
            "mean(norm(diff(Bat1_xyz)/dt) at Contact Position event frames)*3.6/1000",
            "Contact Position event is lowest Bat1_Z frames, not bat-speed peak",
            {
                "instant_frame": contact_center_idx,
                "instant_value": float(bat_speed[contact_center_idx]),
                "event_fixed_value": finite_scalar(bat_speed[contact_event], "mean"),
            },
        ),
        metric_row(
            trial,
            "Contact Position",
            "挥棒路径角（Attack Angle）",
            "contact_attack_angle_deg",
            finite_scalar(attack_angle[contact_event], "mean"),
            "deg",
            "event mean over Contact Position frames",
            "Contact Position",
            contact_rule,
            contact_event,
            ["Bat1"],
            "atan2(Bat1_velocity_Z, norm(Bat1_velocity_XY))",
            "Contact Position event is lowest Bat1_Z frames",
            {
                "instant_frame": contact_center_idx,
                "instant_value": float(attack_angle[contact_center_idx]),
                "event_fixed_value": finite_scalar(attack_angle[contact_event], "mean"),
            },
        ),
        metric_row(
            trial,
            "Contact Position",
            "骨盆旋转角",
            "contact_pelvis_rotation_open_deg",
            finite_scalar(pelvis_open[contact_event], "mean"),
            "deg",
            "event mean over Contact Position frames",
            "Contact Position",
            contact_rule,
            contact_event,
            ["LASI", "RASI", "LPSI", "RPSI"],
            "abs(wrap_to_180(pelvis_rotation_xy_contact_event - mean(pelvis_rotation_xy_ready_event)))",
            "direction-normalized opening magnitude; signed raw value depends on Vicon XY facing direction",
            {
                "signed_event_value_deg": finite_scalar(pelvis_open_signed[contact_event], "mean"),
            },
        ),
        metric_row(
            trial,
            "Contact Position",
            "躯干旋转角",
            "contact_torso_rotation_open_deg",
            finite_scalar(torso_open[contact_event], "mean"),
            "deg",
            "event mean over Contact Position frames",
            "Contact Position",
            contact_rule,
            contact_event,
            ["LSHO", "RSHO"],
            "abs(wrap_to_180(torso_rotation_xy_contact_event - mean(torso_rotation_xy_ready_event)))",
            "direction-normalized opening magnitude; signed raw value depends on Vicon XY facing direction",
            {
                "signed_event_value_deg": finite_scalar(torso_open_signed[contact_event], "mean"),
            },
        ),
        metric_row(
            trial,
            "Contact Position",
            "前膝屈曲角",
            "contact_front_knee_flexion_deg",
            finite_scalar(front_knee_flex[contact_event], "mean"),
            "deg",
            "event mean over Contact Position frames",
            "Contact Position",
            contact_rule,
            contact_event,
            [f"{front} hip", f"{front} knee", f"{front} ankle/heel/toe"],
            "180 - angle(front_hip, front_knee, front_ankle)",
            "right-handed assumption: rear side=R, front side=L",
        ),
        metric_row(
            trial,
            "Contact Position",
            "头部位移",
            "ready_to_contact_head_displacement_mm",
            head_displacement,
            "mm",
            "distance between Ready Position event head center and Contact Position event head center",
            "Ready to Contact",
            f"Ready: {ready_rule}; Contact: {contact_rule}",
            contact_event,
            ["LFHD", "RFHD", "LBHD", "RBHD"],
            "norm(mean(head_center_contact_event) - mean(head_center_ready_event))",
            "event-to-event displacement",
            {
                "ready_event_frames": indices_label(ready_event),
                "contact_event_frames": indices_label(contact_event),
            },
        ),
        metric_row(
            trial,
            "Coach Flag",
            "重心偏高指数",
            "coach_high_com_risk_index",
            high_com_score,
            "0-100 risk",
            "Ready Position event composite",
            "Ready Position",
            ready_rule,
            ready_event,
            ["CentreOfMass", "rear_hip_flexion", "rear_knee_flexion"],
            "100*mean(clip((COM_height_ratio-0.48)/0.14), clip((35-rear_hip_flexion)/35), clip((35-rear_knee_flexion)/35))",
            "heuristic risk index: higher means taller COM plus straighter rear hip/knee",
            {
                "com_height_ratio": com_height_norm,
                "rear_hip_flexion_deg": rear_hip_ready,
                "rear_knee_flexion_deg": rear_knee_ready,
                "swing_segment_frames": indices_label(swing_segment),
                "swing_peak_frame": int(swing_peak_idx),
                "swing_peak_speed_kmh": swing_peak_speed,
                "swing_speed_threshold_kmh": swing_threshold,
            },
        ),
        metric_row(
            trial,
            "Coach Flag",
            "后肘高度差（掉肘）",
            "coach_rear_elbow_height_diff_mm",
            rear_elbow_height_diff,
            "mm",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            [f"{rear}ELB", f"{rear}SHO"],
            "mean(rear_elbow_Z - rear_shoulder_Z)",
            "negative value means rear elbow is below rear shoulder",
        ),
        metric_row(
            trial,
            "Coach Flag",
            "球棒加载角（引棒不足）",
            "coach_bat_loading_angle_to_catcher_deg",
            bat_loading_angle,
            "deg",
            "event mean over Ready Position frames",
            "Ready Position",
            ready_rule,
            ready_event,
            ["Bat1", "Bat5"],
            "angle(project_xy(Bat5-Bat1) at Ready event, catcher_direction); catcher_direction=-project_xy(mean(Bat1_velocity_contact_event))",
            "0 deg means knob/root direction points toward inferred catcher direction",
        ),
        metric_row(
            trial,
            "Coach Flag",
            "手腕翻转角速度（翻腕）",
            "coach_rollover_forearm_roll_velocity_deg_s",
            rollover_vel_peak,
            "deg/s",
            "peak absolute angular velocity over Contact Position event frames",
            "Contact Position",
            contact_rule,
            contact_event,
            [f"{rear}ELB", f"{rear}WRA", f"{rear}WRB"],
            "max(abs(d/dt signed_angle_about_axis(wrist_marker_axis, elbow_to_wrist_axis, global_Z_reference)))",
            "forearm pronation proxy; sign is not interpreted, magnitude is used",
            {
                "instant_frame": contact_center_idx,
                "instant_value": float(abs(forearm_roll_vel[contact_center_idx])),
                "event_fixed_value": rollover_vel_peak,
            },
        ),
        metric_row(
            trial,
            "Coach Flag",
            "击球区稳定性",
            "coach_hitting_zone_stability_score",
            stability_score,
            "0-100 score",
            "composite over frames where Bat1 speed >= 90% peak",
            "High-Speed Hitting Zone",
            "frames inside detected swing segment where Bat1 speed >= 90% of swing-segment peak speed",
            high_speed_indices,
            ["Bat1"],
            "100*mean(clip(path_length_mm/650), clip(1-attack_angle_std_deg/18), clip(1-mean_curvature_1_per_mm/0.006))",
            "higher is more stable; components are stored in components_json",
            {
                "zone_length_mm": zone_length,
                "attack_angle_std_deg": zone_attack_std,
                "mean_curvature_1_per_mm": zone_curvature,
                "length_score": float(length_score),
                "plane_score": float(plane_score),
                "curvature_score": float(curvature_score),
            },
        ),
    ]
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_wide_csv(path: Path, rows: list[dict[str, object]]) -> None:
    by_trial: dict[str, dict[str, object]] = {}
    order: list[str] = []
    for row in rows:
        trial_id = str(row["trial_id"])
        if trial_id not in by_trial:
            by_trial[trial_id] = {
                "trial_id": trial_id,
                "sample_name": row["sample_name"],
                "athlete": row["athlete"],
                "action_type": row["action_type"],
                "source_file": row["source_file"],
            }
        key = str(row["metric_key"])
        if key not in order:
            order.append(key)
        by_trial[trial_id][key] = row["value"]
    fieldnames = ["trial_id", "sample_name", "athlete", "action_type", "source_file", *order]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for trial_id in sorted(by_trial):
            writer.writerow(by_trial[trial_id])


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build 17 batting dashboard metrics from Vicon C3D all-point CSV output."
    )
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--wide-out", type=Path, default=DEFAULT_WIDE_OUT)
    parser.add_argument("--ready-event-frames", type=int, default=5)
    parser.add_argument("--contact-event-frames", type=int, default=5)
    parser.add_argument("--ready-lookback-sec", type=float, default=0.68)
    parser.add_argument(
        "--ready-valid-start-frame",
        type=int,
        default=None,
        help="Earliest frame allowed for Ready Position detection. Use this to exclude pre-action trial content.",
    )
    args = parser.parse_args()

    trials = [trial for trial in load_trials(args.points) if trial.action_type == "batting"]
    rows: list[dict[str, object]] = []
    for trial in trials:
        rows.extend(
            compute_trial_metrics(
                trial,
                ready_event_frames=args.ready_event_frames,
                contact_event_frames=args.contact_event_frames,
                ready_lookback_sec=args.ready_lookback_sec,
                ready_valid_start_frame=args.ready_valid_start_frame,
            )
        )
    write_csv(args.out, rows)
    write_wide_csv(args.wide_out, rows)
    print(args.out)
    print(args.wide_out)


if __name__ == "__main__":
    main()
