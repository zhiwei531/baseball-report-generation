from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Sequence

import numpy as np


EVENT_DETECTOR_VERSION = "legacy_v1"


@dataclass(frozen=True)
class DetectedEvent:
    event_id: str
    indices: tuple[int, ...]
    primary_index: int | None
    detector_id: str
    rule: str
    source: str
    confidence: float | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.event_id or not self.detector_id or not self.rule or not self.source:
            raise ValueError("event_id, detector_id, rule, and source are required")
        indices = tuple(int(index) for index in self.indices)
        if tuple(sorted(set(indices))) != indices:
            raise ValueError("event indices must be unique and sorted")
        if self.primary_index is not None and int(self.primary_index) not in indices:
            raise ValueError("primary_index must be inside indices")
        if self.confidence is not None and not 0 <= float(self.confidence) <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "indices", indices)
        object.__setattr__(self, "primary_index", None if self.primary_index is None else int(self.primary_index))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    def as_legacy_indices(self) -> np.ndarray:
        return np.asarray(self.indices, dtype=int)


@dataclass(frozen=True)
class EventDetectionResult:
    events: Mapping[str, DetectedEvent]
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        events = dict(self.events)
        for event_id, event in events.items():
            if event_id != event.event_id:
                raise ValueError(f"event key {event_id!r} does not match event_id")
        object.__setattr__(self, "events", MappingProxyType(events))
        object.__setattr__(self, "warnings", tuple(self.warnings))

    def as_legacy_frames(self) -> dict[str, int]:
        return {
            event_id: event.primary_index
            for event_id, event in self.events.items()
            if event.primary_index is not None
        }


@dataclass(frozen=True)
class SwingSegmentDetection:
    raw_indices: tuple[int, ...]
    expanded_indices: tuple[int, ...]
    peak_index: int
    peak_speed_kmh: float
    threshold_kmh: float
    detector_id: str = "batting.swing_segment.legacy_v1"

    def as_legacy_tuple(self) -> tuple[np.ndarray, np.ndarray, int, float, float]:
        return (
            np.asarray(self.raw_indices, dtype=int),
            np.asarray(self.expanded_indices, dtype=int),
            self.peak_index,
            self.peak_speed_kmh,
            self.threshold_kmh,
        )


def _finite_scalar(values: np.ndarray, operation: str = "mean") -> float:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return float("nan")
    if operation == "mean":
        return float(np.mean(finite))
    if operation == "max":
        return float(np.max(finite))
    raise ValueError(f"unsupported operation: {operation}")


def _smooth_nan(values: np.ndarray, radius: int = 2) -> np.ndarray:
    out = np.full_like(values, np.nan, dtype=float)
    for index in range(len(values)):
        start = max(0, index - radius)
        end = min(len(values), index + radius + 1)
        out[index] = _finite_scalar(values[start:end])
    return out


def primary_index(indices: Sequence[int]) -> int | None:
    if not indices:
        return None
    return int(round(float(np.median(np.asarray(indices, dtype=int)))))


def first_valid_indices(series: Sequence[np.ndarray], count: int, frame_count: int) -> np.ndarray:
    valid = np.ones(frame_count, dtype=bool)
    for values in series:
        valid &= np.isfinite(values).all(axis=1)
    indices = np.where(valid)[0][:count]
    if indices.size:
        return indices
    return np.arange(min(count, frame_count), dtype=int)


def lowest_z_indices(
    series: np.ndarray,
    count: int,
    candidates: np.ndarray | None = None,
) -> np.ndarray:
    if candidates is None:
        candidates = np.arange(series.shape[0])
    valid = np.array([index for index in candidates if np.isfinite(series[index, 2])], dtype=int)
    if valid.size == 0:
        return np.array([], dtype=int)
    lowest = valid[np.argsort(series[valid, 2])[:count]]
    return np.array(sorted(lowest), dtype=int)


def detect_batting_swing_segment(
    bat_speed_kmh: np.ndarray,
    rate_hz: float,
    *,
    threshold_ratio: float = 0.20,
    min_threshold_kmh: float = 8.0,
    expansion_sec: float = 0.15,
) -> SwingSegmentDetection:
    speed_smooth = _smooth_nan(bat_speed_kmh, radius=2)
    if not np.isfinite(speed_smooth).any():
        fallback = tuple(range(len(bat_speed_kmh)))
        return SwingSegmentDetection(
            raw_indices=fallback,
            expanded_indices=fallback,
            peak_index=len(bat_speed_kmh) // 2,
            peak_speed_kmh=float("nan"),
            threshold_kmh=float("nan"),
        )
    peak_index = int(np.nanargmax(speed_smooth))
    peak_speed = float(speed_smooth[peak_index])
    threshold = max(min_threshold_kmh, peak_speed * threshold_ratio)
    active = np.isfinite(speed_smooth) & (speed_smooth >= threshold)
    start = peak_index
    while start > 0 and active[start - 1]:
        start -= 1
    end = peak_index
    while end + 1 < len(active) and active[end + 1]:
        end += 1
    margin = max(1, round(expansion_sec * rate_hz))
    expanded_start = max(0, start - margin)
    expanded_end = min(len(active) - 1, end + margin)
    return SwingSegmentDetection(
        raw_indices=tuple(range(start, end + 1)),
        expanded_indices=tuple(range(expanded_start, expanded_end + 1)),
        peak_index=peak_index,
        peak_speed_kmh=peak_speed,
        threshold_kmh=threshold,
    )


def detect_batting_ready(
    bat_barrel: np.ndarray,
    bat_handle: np.ndarray,
    head: np.ndarray,
    bat_speed_kmh: np.ndarray,
    swing_start_index: int,
    rate_hz: float,
    count: int,
    peak_speed_kmh: float,
    lookback_sec: float,
    valid_start_frame: int | None,
) -> DetectedEvent:
    lookback = max(count, round(lookback_sec * rate_hz))
    start = max(0, swing_start_index - lookback)
    if valid_start_frame is not None:
        start = max(start, valid_start_frame)
    stop = max(start, swing_start_index)
    candidates = np.arange(start, stop, dtype=int)
    selection = "raised_bat_low_speed_block"
    if candidates.size == 0:
        indices = first_valid_indices([bat_barrel, bat_handle, head], count, len(bat_barrel))
        selection = "first_valid_fallback"
    else:
        valid = (
            np.isfinite(bat_barrel[candidates]).all(axis=1)
            & np.isfinite(bat_handle[candidates]).all(axis=1)
            & np.isfinite(head[candidates]).all(axis=1)
            & np.isfinite(bat_speed_kmh[candidates])
        )
        valid_candidates = candidates[valid]
        if valid_candidates.size == 0:
            indices = first_valid_indices([bat_barrel, bat_handle, head], count, len(bat_barrel))
            selection = "first_valid_fallback"
        else:
            speed_limit = max(6.0, peak_speed_kmh * 0.12) if np.isfinite(peak_speed_kmh) else 6.0
            low_speed = np.zeros(len(bat_barrel), dtype=bool)
            low_speed[valid_candidates] = bat_speed_kmh[valid_candidates] <= speed_limit
            blocks: list[tuple[float, int, np.ndarray]] = []
            for block_start in range(start, max(start, stop - count + 1)):
                block = np.arange(block_start, block_start + count, dtype=int)
                if block[-1] >= stop:
                    continue
                if not np.all(np.isin(block, valid_candidates)) or not np.all(low_speed[block]):
                    continue
                bat_height = _finite_scalar(bat_barrel[block, 2])
                mean_speed = _finite_scalar(bat_speed_kmh[block])
                if np.isfinite(bat_height):
                    blocks.append((bat_height - 0.02 * mean_speed, block_start, block))
            if blocks:
                indices = max(blocks, key=lambda item: (item[0], -item[1]))[2]
            else:
                low_speed_candidates = valid_candidates[bat_speed_kmh[valid_candidates] <= speed_limit]
                if low_speed_candidates.size >= count:
                    indices = np.array(sorted(low_speed_candidates[:count]), dtype=int)
                    selection = "first_low_speed_candidates"
                else:
                    indices = np.array(sorted(valid_candidates[:count]), dtype=int)
                    selection = "first_valid_candidates"
    index_tuple = tuple(int(index) for index in indices)
    return DetectedEvent(
        event_id="ready_position",
        indices=index_tuple,
        primary_index=primary_index(index_tuple),
        detector_id="batting.ready.legacy_v1",
        rule="highest continuous low-speed raised-bat block before the detected swing",
        source="vicon_marker_trajectories",
        metadata={
            "selection": selection,
            "count": count,
            "lookback_sec": lookback_sec,
            "valid_start_frame": valid_start_frame,
        },
    )


def detect_batting_contact(
    bat_barrel: np.ndarray,
    count: int,
    candidates: np.ndarray,
) -> DetectedEvent:
    indices = lowest_z_indices(bat_barrel, count, candidates)
    index_tuple = tuple(int(index) for index in indices)
    return DetectedEvent(
        event_id="contact_position",
        indices=index_tuple,
        primary_index=primary_index(index_tuple),
        detector_id="batting.contact_lowest_barrel_z.legacy_v1",
        rule="lowest Bat1 Z frames inside the detected swing segment",
        source="vicon_marker_trajectories",
        metadata={"proxy": True, "count": count},
    )


def _speed_mps(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    difference = np.diff(points_mm, axis=0) / 1000.0
    speed = np.linalg.norm(difference, axis=1) * rate_hz
    return np.concatenate([[np.nan], speed])


def detect_pitching_events(
    *,
    lead_knee: np.ndarray,
    lead_foot: np.ndarray,
    throwing_hand: np.ndarray,
    rate_hz: float,
    floor_mm: float,
) -> EventDetectionResult:
    lead_knee_z = _smooth_nan(lead_knee[:, 2], 2)
    peak = int(np.nanargmax(lead_knee_z))
    lead_foot_z = _smooth_nan(lead_foot[:, 2], 2)
    foot_speed = _smooth_nan(_speed_mps(lead_foot, rate_hz), 2)
    contact_candidates = np.where(
        (np.arange(len(lead_foot_z)) > peak + 10) & (lead_foot_z <= floor_mm + 70)
    )[0]
    if contact_candidates.size:
        contact = int(contact_candidates[0])
        contact_selection = "first_floor_threshold_crossing"
    else:
        contact = min(len(lead_foot_z) - 1, peak + int(1.0 * rate_hz))
        contact_selection = "peak_plus_one_second_fallback"
    plant = contact
    search_end = min(len(lead_foot_z), contact + int(0.28 * rate_hz))
    stable = np.where(
        (np.arange(len(lead_foot_z)) >= contact)
        & (np.arange(len(lead_foot_z)) < search_end)
        & (foot_speed <= 0.75)
    )[0]
    if stable.size:
        plant = int(stable[min(len(stable) - 1, 3)])
        plant_selection = "fourth_stable_candidate_or_last"
    else:
        plant = min(search_end - 1, contact + int(0.14 * rate_hz))
        plant_selection = "contact_plus_0.14_seconds_fallback"
    hand_speed = _smooth_nan(_speed_mps(throwing_hand, rate_hz), 2)
    release_start = plant
    release_end = min(len(hand_speed), plant + int(0.55 * rate_hz))
    release_window = hand_speed[release_start:release_end]
    if np.isfinite(release_window).any():
        release = release_start + int(np.nanargmax(release_window))
        release_selection = "peak_hand_speed_after_plant"
    else:
        release = min(len(hand_speed) - 1, plant + int(0.2 * rate_hz))
        release_selection = "plant_plus_0.2_seconds_fallback"

    def event(event_id: str, index: int, rule: str, metadata: Mapping[str, object]) -> DetectedEvent:
        return DetectedEvent(
            event_id=event_id,
            indices=(index,),
            primary_index=index,
            detector_id=f"pitching.{event_id}.legacy_v1",
            rule=rule,
            source="vicon_marker_trajectories",
            metadata=metadata,
        )

    return EventDetectionResult(
        events={
            "peak_knee": event(
                "peak_knee",
                peak,
                "maximum smoothed lead-knee Z",
                {"smoothing_radius": 2},
            ),
            "foot_contact": event(
                "foot_contact",
                contact,
                "first post-peak-knee lead-foot frame within floor + 70 mm",
                {"selection": contact_selection, "floor_threshold_mm": 70},
            ),
            "foot_plant": event(
                "foot_plant",
                plant,
                "fourth lead-foot speed <= 0.75 m/s candidate within 0.28 s after contact",
                {"selection": plant_selection, "speed_threshold_mps": 0.75},
            ),
            "release": event(
                "release",
                release,
                "maximum smoothed throwing-hand speed within 0.55 s after foot plant",
                {"selection": release_selection},
            ),
        }
    )


def detect_key_action_event(
    *,
    action_type: str,
    right_hand_speed_kmh: np.ndarray,
    left_hand_speed_kmh: np.ndarray,
    bat_speed_kmh: np.ndarray,
    frame_count: int,
) -> DetectedEvent:
    if action_type == "batting" and np.isfinite(bat_speed_kmh).any():
        index = int(np.nanargmax(bat_speed_kmh))
        event_id = "bat_speed_peak"
        label_zh = "球棒峰值速度"
    else:
        right_max = _finite_scalar(right_hand_speed_kmh, "max") if np.isfinite(right_hand_speed_kmh).any() else float("nan")
        left_max = _finite_scalar(left_hand_speed_kmh, "max") if np.isfinite(left_hand_speed_kmh).any() else float("nan")
        if right_max >= left_max and np.isfinite(right_hand_speed_kmh).any():
            index = int(np.nanargmax(right_hand_speed_kmh))
            event_id = "right_hand_speed_peak"
            label_zh = "右手峰值速度"
        elif np.isfinite(left_hand_speed_kmh).any():
            index = int(np.nanargmax(left_hand_speed_kmh))
            event_id = "left_hand_speed_peak"
            label_zh = "左手峰值速度"
        else:
            index = frame_count // 2
            event_id = "mid_frame_fallback"
            label_zh = "动作中段兜底"
    return DetectedEvent(
        event_id=event_id,
        indices=(index,),
        primary_index=index,
        detector_id="common.key_action.legacy_v1",
        rule=event_id,
        source="vicon_marker_speed",
        metadata={"display_name_zh": label_zh, "action_type": action_type},
    )


def detect_video_wrist_peak(combined_wrist_speed_px_s: np.ndarray, fps: float) -> DetectedEvent:
    if np.isfinite(combined_wrist_speed_px_s).any():
        index = int(np.nanargmax(combined_wrist_speed_px_s))
        peak_speed: float | None = float(combined_wrist_speed_px_s[index])
        selection = "peak_speed"
    else:
        index = len(combined_wrist_speed_px_s) // 2
        peak_speed = None
        selection = "mid_frame_fallback"
    return DetectedEvent(
        event_id="video_wrist_speed_peak",
        indices=(index,),
        primary_index=index,
        detector_id="alignment.video_wrist_peak.legacy_v1",
        rule="2d_wrist_peak_speed",
        source="pose_image_coordinates",
        metadata={
            "fps": fps,
            "peak_speed_px_s": peak_speed,
            "selection": selection,
        },
    )
