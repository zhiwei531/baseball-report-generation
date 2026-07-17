from __future__ import annotations

from dataclasses import dataclass

from baseball_report.core.provenance import AnalysisWarning
from baseball_report.core.validation import optional_finite, require_text


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
