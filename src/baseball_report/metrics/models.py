from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from baseball_report.core.enums import CoordinateProfile, MotionType, QualityStatus, Side
from baseball_report.core.frames import FrameReference
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.core.validation import frozen_mapping, optional_finite, require_text


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    version: str
    display_name_zh: str
    display_name_en: str
    motion_type: MotionType
    formula_text: str
    required_points: tuple[str, ...]
    required_event_ids: tuple[str, ...]
    coordinate_system: CoordinateProfile
    unit: str | None
    side_rule: str | None
    missing_data_policy: str
    implementation: str

    def __post_init__(self) -> None:
        for field_name in (
            "metric_id",
            "version",
            "display_name_zh",
            "display_name_en",
            "formula_text",
            "missing_data_policy",
            "implementation",
        ):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "required_points", tuple(self.required_points))
        object.__setattr__(self, "required_event_ids", tuple(self.required_event_ids))


@dataclass(frozen=True)
class MetricResult:
    metric_id: str
    definition_version: str
    sequence_id: str
    motion_type: MotionType
    display_name_zh: str
    display_name_en: str
    value: float | None
    unit: str | None
    event_id: str | None
    event_frame: FrameReference | None
    side: Side | None
    reference_value: float | None
    difference: float | None
    status: str
    quality: QualityStatus
    provenance: Provenance
    warnings: tuple[AnalysisWarning, ...] = ()
    components: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "metric_id",
            "definition_version",
            "sequence_id",
            "display_name_zh",
            "display_name_en",
            "status",
        ):
            require_text(getattr(self, field_name), field_name)
        object.__setattr__(self, "value", optional_finite(self.value, "value"))
        object.__setattr__(self, "reference_value", optional_finite(self.reference_value, "reference_value"))
        object.__setattr__(self, "difference", optional_finite(self.difference, "difference"))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "components", frozen_mapping(self.components))
