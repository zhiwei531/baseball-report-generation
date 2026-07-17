from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .enums import CoordinateProfile, Handedness, MotionType, Side, SourceType
from .provenance import AnalysisWarning, Provenance
from .validation import frozen_mapping, require_finite, require_text


def _readonly_arrays(
    values: Mapping[str, NDArray[np.generic]] | None,
    frame_count: int,
    field_name: str,
) -> Mapping[str, NDArray[np.generic]] | None:
    if values is None:
        return None
    copied: dict[str, NDArray[np.generic]] = {}
    for name, value in values.items():
        require_text(name, f"{field_name} key")
        array = np.array(value, copy=True)
        if array.ndim == 0 or array.shape[0] != frame_count:
            raise ValueError(f"{field_name}[{name!r}] must have frame_count as its first dimension")
        array.setflags(write=False)
        copied[name] = array
    return frozen_mapping(copied)


@dataclass(frozen=True)
class MotionSequence:
    sequence_id: str
    source_type: SourceType
    motion_type: MotionType
    frame_rate_hz: float
    frame_count: int
    first_source_frame: int | None
    points: Mapping[str, NDArray[np.generic]]
    timestamps_seconds: NDArray[np.floating]
    coordinate_system: CoordinateProfile
    length_unit: str
    provenance: Provenance
    valid: Mapping[str, NDArray[np.generic]] | None = None
    confidence: Mapping[str, NDArray[np.generic]] | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.sequence_id, "sequence_id")
        rate = require_finite(self.frame_rate_hz, "frame_rate_hz", positive=True)
        if isinstance(self.frame_count, bool) or self.frame_count <= 0:
            raise ValueError("frame_count must be a positive integer")
        if self.first_source_frame is not None and self.first_source_frame < 0:
            raise ValueError("first_source_frame must be non-negative")
        require_text(self.length_unit, "length_unit")
        timestamps = np.array(self.timestamps_seconds, dtype=float, copy=True)
        if timestamps.shape != (self.frame_count,) or not np.isfinite(timestamps).all():
            raise ValueError("timestamps_seconds must be a finite vector with frame_count values")
        timestamps.setflags(write=False)
        object.__setattr__(self, "frame_rate_hz", rate)
        object.__setattr__(self, "timestamps_seconds", timestamps)
        points = _readonly_arrays(self.points, self.frame_count, "points")
        if not points:
            raise ValueError("points must contain at least one named point series")
        object.__setattr__(self, "points", points)
        object.__setattr__(self, "valid", _readonly_arrays(self.valid, self.frame_count, "valid"))
        object.__setattr__(self, "confidence", _readonly_arrays(self.confidence, self.frame_count, "confidence"))
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class AnalysisContext:
    subject_id: str
    motion_type: MotionType
    coordinate_system: CoordinateProfile
    length_unit: str
    algorithm_profile: str
    batting_side: Handedness | None = None
    throwing_arm: Side | None = None
    lead_side: Side | None = None
    trail_side: Side | None = None

    def __post_init__(self) -> None:
        require_text(self.subject_id, "subject_id")
        require_text(self.length_unit, "length_unit")
        require_text(self.algorithm_profile, "algorithm_profile")
        if self.lead_side is not None and self.lead_side == self.trail_side:
            raise ValueError("lead_side and trail_side must differ")
