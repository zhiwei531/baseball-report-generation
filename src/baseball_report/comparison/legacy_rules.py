from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

import numpy as np


BAT_SPEED_U8_U10_GOOD_MIN_KMH = 48.0
BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH = 72.0
LOWER_IS_BETTER_KEYS = frozenset(
    {
        "coach_high_com_risk_index",
        "coach_rollover_forearm_roll_velocity_deg_s",
        "ready_to_contact_head_displacement_mm",
    }
)


@dataclass(frozen=True)
class PeerStatistics:
    minimum: float | None
    maximum: float | None
    mean: float | None
    included_subject_ids: tuple[str, ...]


def finite_number(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def summarize_peer_values(values: Iterable[tuple[str, object]]) -> PeerStatistics:
    included: list[tuple[str, float]] = []
    for subject_id, value in values:
        if finite_number(value):
            included.append((str(subject_id), float(value)))
    if not included:
        return PeerStatistics(None, None, None, ())
    numbers = [value for _subject_id, value in included]
    return PeerStatistics(
        minimum=min(numbers),
        maximum=max(numbers),
        mean=float(np.mean(numbers)),
        included_subject_ids=tuple(subject_id for subject_id, _value in included),
    )


def pitching_score(value: float, metric: Mapping[str, object], coach_value: float | None = None) -> float:
    """Preserve the current pitching builder's report score exactly."""

    if not finite_number(value):
        return 45
    ideal = metric.get("ideal")
    lo = metric.get("lo")
    hi = metric.get("hi")
    direction = metric.get("direction", "target")
    if finite_number(ideal):
        spread = float(metric.get("spread", max(abs(float(ideal)) * 0.35, 8)))
        return max(0, min(100, 100 - abs(value - float(ideal)) / spread * 45))
    if finite_number(lo) and finite_number(hi):
        lo_f, hi_f = float(lo), float(hi)
        if lo_f <= value <= hi_f:
            return 88
        distance = min(abs(value - lo_f), abs(value - hi_f))
        return max(35, 88 - distance / max(abs(hi_f - lo_f), 1) * 60)
    if direction == "higher":
        target = float(metric.get("target", coach_value if finite_number(coach_value) else value))
        return max(35, min(100, 60 + value / max(target, 1) * 35))
    if direction == "lower_abs":
        return max(35, min(100, 100 - abs(value) / float(metric.get("spread", 30)) * 60))
    return 72


def status_from_score(score: float) -> tuple[str, str]:
    if score >= 82:
        return "优秀", "good"
    if score >= 66:
        return "良好", "review"
    return "待提高", "risk"


def batting_status(metric_id: str, value: float | None, standard: float | None) -> tuple[str, str]:
    """Preserve the current batting card status thresholds exactly."""

    if value is None or not finite_number(value):
        return "良好", "review"
    if metric_id == "contact_bat_speed_kmh":
        if value >= BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH:
            return "优秀", "good"
        if value >= BAT_SPEED_U8_U10_GOOD_MIN_KMH:
            return "良好", "review"
        return "待提高", "risk"
    if standard is None or not finite_number(standard):
        return "良好", "review"
    if metric_id in LOWER_IS_BETTER_KEYS:
        return ("优秀", "good") if value <= standard else ("待提高", "risk")
    if metric_id == "coach_hitting_zone_stability_score":
        return ("优秀", "good") if value >= standard else ("待提高", "risk")
    ratio = abs(value - standard) / max(abs(standard), 1.0)
    if ratio <= 0.12:
        return "优秀", "good"
    if ratio <= 0.30:
        return "良好", "review"
    return "待提高", "risk"


def batting_component_score(metric_id: str, value: float, standard: float) -> float:
    """Preserve the current batting composite component score exactly."""

    if metric_id == "contact_bat_speed_kmh":
        if value >= BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH:
            return 100.0
        if value >= BAT_SPEED_U8_U10_GOOD_MIN_KMH:
            ratio = (value - BAT_SPEED_U8_U10_GOOD_MIN_KMH) / (
                BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH - BAT_SPEED_U8_U10_GOOD_MIN_KMH
            )
            return 70.0 + ratio * 14.0
        return max(20.0, 70.0 * max(value, 0.0) / BAT_SPEED_U8_U10_GOOD_MIN_KMH)
    scale = max(abs(standard), 1.0)
    if metric_id in LOWER_IS_BETTER_KEYS:
        difference_ratio = max(0.0, (value - standard) / scale)
    else:
        difference_ratio = abs(value - standard) / scale
    if difference_ratio <= 0.12:
        return 100.0 - difference_ratio / 0.12 * 8.0
    if difference_ratio <= 0.30:
        return 92.0 - (difference_ratio - 0.12) / 0.18 * 22.0
    if difference_ratio <= 0.60:
        return 70.0 - (difference_ratio - 0.30) / 0.30 * 30.0
    return max(20.0, 40.0 - (difference_ratio - 0.60) / 0.40 * 20.0)


def weighted_batting_score(
    components: Sequence[tuple[str, float]],
    values: Mapping[str, float | None],
    standards: Mapping[str, float | None],
) -> float | None:
    weighted_total = 0.0
    weight_total = 0.0
    for metric_id, weight in components:
        value = values.get(metric_id)
        standard = standards.get(metric_id)
        if not finite_number(value) or not finite_number(standard):
            continue
        weighted_total += batting_component_score(metric_id, float(value), float(standard)) * weight
        weight_total += weight
    return None if weight_total <= 0 else weighted_total / weight_total
