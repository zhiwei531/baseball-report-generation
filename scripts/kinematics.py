from __future__ import annotations

import numpy as np


def finite_mean(values: np.ndarray, axis: int = 0) -> np.ndarray:
    """Mean over finite values, preserving NaN where the selected axis is empty."""
    array = np.asarray(values, dtype=float)
    valid = np.isfinite(array)
    counts = valid.sum(axis=axis)
    total = np.nansum(array, axis=axis)
    return np.divide(
        total,
        counts,
        out=np.full_like(total, np.nan, dtype=float),
        where=counts > 0,
    )


def finite_scalar(values: np.ndarray, statistic: str = "mean") -> float:
    """Legacy finite-only scalar reductions used by batting calculations."""
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return float("nan")
    if statistic == "max":
        return float(np.nanmax(finite))
    if statistic == "min":
        return float(np.nanmin(finite))
    if statistic == "median":
        return float(np.nanmedian(finite))
    if statistic == "std":
        return float(np.nanstd(finite))
    if statistic == "sum":
        return float(np.nansum(finite))
    if statistic == "p05":
        return float(np.nanpercentile(finite, 5))
    if statistic == "p95":
        return float(np.nanpercentile(finite, 95))
    return float(np.nanmean(finite))


def speed_kmh_from_mm(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    """Legacy first-difference speed: millimetres at Hz to kilometres/hour."""
    diff_m = np.diff(points_mm, axis=0) / 1000.0
    speed = np.linalg.norm(diff_m, axis=1) * rate_hz * 3.6
    return np.concatenate([[np.nan], speed])


def velocity_mm_s(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    """Legacy first-difference XYZ velocity in millimetres/second."""
    return np.vstack([np.full(3, np.nan), np.diff(points_mm, axis=0) * rate_hz])


def joint_angle_deg(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> np.ndarray:
    """Unsigned 0–180 degree angle ABC, returning NaN for zero-length vectors."""
    ba = a - b
    bc = c - b
    denominator = np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1)
    dot = np.einsum("ij,ij->i", ba, bc)
    cosine = np.divide(
        dot,
        denominator,
        out=np.full_like(dot, np.nan),
        where=denominator > 0,
    )
    result = np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))
    result[~np.isfinite(result)] = np.nan
    return result


def joint_angle_deg_legacy_divide(
    a: np.ndarray,
    b: np.ndarray,
    c: np.ndarray,
) -> np.ndarray:
    """Original generic C3D angle variant; direct division is kept intentionally."""
    ba = a - b
    bc = c - b
    denominator = np.linalg.norm(ba, axis=1) * np.linalg.norm(bc, axis=1)
    dot = np.einsum("ij,ij->i", ba, bc)
    cosine = np.clip(dot / denominator, -1.0, 1.0)
    result = np.degrees(np.arccos(cosine))
    result[~np.isfinite(result)] = np.nan
    return result


def xy_angle_deg(vectors: np.ndarray) -> np.ndarray:
    """Global XY atan2 angle in degrees."""
    return np.degrees(np.arctan2(vectors[:, 1], vectors[:, 0]))


def circular_difference_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Signed wrapped angular difference in [-180, 180)."""
    return (a - b + 180.0) % 360.0 - 180.0


def vector_angle_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Unsigned 0–180 degree angle between paired vectors."""
    dot = np.einsum("ij,ij->i", a, b)
    denominator = np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1)
    cosine = np.divide(
        dot,
        denominator,
        out=np.full_like(dot, np.nan),
        where=denominator > 0,
    )
    return np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))


def signed_angle_about_axis_deg(
    radial: np.ndarray,
    axis: np.ndarray,
    reference: np.ndarray,
) -> np.ndarray:
    """Signed projected radial/reference angle about a paired 3D axis."""
    axis_norm = np.linalg.norm(axis, axis=1, keepdims=True)
    axis_unit = np.divide(
        axis,
        axis_norm,
        out=np.full_like(axis, np.nan),
        where=axis_norm > 0,
    )
    ref_proj = reference - axis_unit * np.einsum("ij,ij->i", reference, axis_unit)[:, None]
    radial_proj = radial - axis_unit * np.einsum("ij,ij->i", radial, axis_unit)[:, None]
    ref_norm = np.linalg.norm(ref_proj, axis=1, keepdims=True)
    radial_norm = np.linalg.norm(radial_proj, axis=1, keepdims=True)
    ref_unit = np.divide(
        ref_proj,
        ref_norm,
        out=np.full_like(ref_proj, np.nan),
        where=ref_norm > 0,
    )
    radial_unit = np.divide(
        radial_proj,
        radial_norm,
        out=np.full_like(radial_proj, np.nan),
        where=radial_norm > 0,
    )
    sine = np.einsum("ij,ij->i", np.cross(ref_unit, radial_unit), axis_unit)
    cosine = np.einsum("ij,ij->i", ref_unit, radial_unit)
    return np.degrees(np.arctan2(sine, cosine))
