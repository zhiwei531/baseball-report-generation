from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from baseball_report.core.frames import FrameReference
from baseball_report.core.provenance import AnalysisWarning
from baseball_report.core.validation import frozen_mapping, optional_finite, require_text


@dataclass(frozen=True)
class ComparisonPoint:
    """A report-safe snapshot of one subject's metric used in a comparison."""

    subject_id: str
    sequence_id: str
    display_name: str
    role: str
    value: float | None
    unit: str | None
    event_id: str | None
    event_frame: FrameReference | None
    components: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.subject_id, "subject_id")
        require_text(self.sequence_id, "sequence_id")
        require_text(self.display_name, "display_name")
        require_text(self.role, "role")
        object.__setattr__(self, "value", optional_finite(self.value, "value"))
        object.__setattr__(self, "components", frozen_mapping(self.components))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class ComparisonResult:
    metric_id: str
    sequence_id: str
    subject_value: float | None
    reference_value: float | None
    group_mean: float | None
    group_min: float | None
    group_max: float | None
    difference: float | None
    score: float | None
    status: str
    included_subject_ids: tuple[str, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    reference_result: ComparisonPoint | None = None
    peer_results: tuple[ComparisonPoint, ...] = ()

    def __post_init__(self) -> None:
        require_text(self.metric_id, "metric_id")
        require_text(self.sequence_id, "sequence_id")
        require_text(self.status, "status")
        for field_name in (
            "subject_value",
            "reference_value",
            "group_mean",
            "group_min",
            "group_max",
            "difference",
            "score",
        ):
            object.__setattr__(self, field_name, optional_finite(getattr(self, field_name), field_name))
        object.__setattr__(self, "included_subject_ids", tuple(self.included_subject_ids))
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "peer_results", tuple(self.peer_results))
        if self.reference_result is not None and self.reference_value != self.reference_result.value:
            raise ValueError("reference_value must match reference_result.value")
