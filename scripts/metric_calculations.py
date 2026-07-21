from __future__ import annotations

from dataclasses import dataclass

import numpy as np


def height_ratio(height_value_mm: float, subject_height_mm: float) -> float:
    return float(height_value_mm / subject_height_mm)


def point_displacement_mm(start_point_mm: np.ndarray, end_point_mm: np.ndarray) -> float:
    return float(np.linalg.norm(end_point_mm - start_point_mm))


def high_com_risk_index(
    com_height_ratio: float,
    rear_hip_flexion_deg: float,
    rear_knee_flexion_deg: float,
) -> float:
    return 100.0 * float(
        np.nanmean(
            [
                np.clip((com_height_ratio - 0.48) / 0.14, 0.0, 1.0),
                np.clip((35.0 - rear_hip_flexion_deg) / 35.0, 0.0, 1.0),
                np.clip((35.0 - rear_knee_flexion_deg) / 35.0, 0.0, 1.0),
            ]
        )
    )


@dataclass(frozen=True)
class HittingZoneStability:
    score: float
    length_score: float
    plane_score: float
    curvature_score: float


def hitting_zone_stability_score(
    zone_length_mm: float,
    attack_angle_std_deg: float,
    mean_curvature_1_per_mm: float,
) -> HittingZoneStability:
    length_score = np.clip(zone_length_mm / 650.0, 0.0, 1.0)
    plane_score = np.clip(1.0 - attack_angle_std_deg / 18.0, 0.0, 1.0)
    curvature_score = np.clip(1.0 - mean_curvature_1_per_mm / 0.006, 0.0, 1.0)
    score = 100.0 * float(np.nanmean([length_score, plane_score, curvature_score]))
    return HittingZoneStability(
        score=score,
        length_score=float(length_score),
        plane_score=float(plane_score),
        curvature_score=float(curvature_score),
    )


def stride_metrics(stride_vector_mm: np.ndarray, subject_height_mm: float) -> tuple[float, float, float]:
    distance_mm = float(np.linalg.norm(stride_vector_mm[:2]))
    distance_pct = float(distance_mm / subject_height_mm * 100)
    direction_deg = float(np.degrees(np.arctan2(stride_vector_mm[1], stride_vector_mm[0])))
    return distance_pct, distance_mm, direction_deg


def arm_slot_deg(forearm_vector_mm: np.ndarray) -> float:
    horizontal = float(np.linalg.norm(forearm_vector_mm[:2]))
    if not np.isfinite(horizontal):
        return float("nan")
    return float(np.degrees(np.arctan2(forearm_vector_mm[2], horizontal)))
