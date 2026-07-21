from __future__ import annotations

from dataclasses import dataclass

from baseball_report.core.provenance import Provenance
from baseball_report.core.validation import portable_report_ref, require_text


@dataclass(frozen=True)
class ChartArtifact:
    artifact_id: str
    sequence_ids: tuple[str, ...]
    kind: str
    title_zh: str
    title_en: str | None
    data_ref: str | None
    file_ref: str | None
    mime_type: str | None
    event_ids: tuple[str, ...]
    metric_ids: tuple[str, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        for field_name in ("artifact_id", "kind", "title_zh"):
            require_text(getattr(self, field_name), field_name)
        if self.data_ref is not None:
            portable_report_ref(self.data_ref, "data_ref")
        if self.file_ref is not None:
            portable_report_ref(self.file_ref, "file_ref")
        object.__setattr__(self, "sequence_ids", tuple(self.sequence_ids))
        object.__setattr__(self, "event_ids", tuple(self.event_ids))
        object.__setattr__(self, "metric_ids", tuple(self.metric_ids))
