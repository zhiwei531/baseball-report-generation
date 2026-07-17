from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from baseball_report.core.enums import MotionType, QualityStatus
from baseball_report.core.frames import FrameReference, FrameWindow
from baseball_report.core.provenance import AnalysisWarning
from baseball_report.core.validation import frozen_mapping, optional_finite, require_text


@dataclass(frozen=True)
class MotionEvent:
    event_id: str
    sequence_id: str
    motion_type: MotionType
    display_name_zh: str
    display_name_en: str
    primary_frame: FrameReference
    window: FrameWindow
    detector_id: str
    rule: str
    source: str
    quality: QualityStatus
    confidence: float | None = None
    warnings: tuple[AnalysisWarning, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "event_id",
            "sequence_id",
            "display_name_zh",
            "display_name_en",
            "detector_id",
            "rule",
            "source",
        ):
            require_text(getattr(self, field_name), field_name)
        confidence = optional_finite(self.confidence, "confidence")
        if confidence is not None and not 0 <= confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        object.__setattr__(self, "confidence", confidence)
        if self.primary_frame != self.window.primary:
            raise ValueError("primary_frame must match window.primary")
        object.__setattr__(self, "warnings", tuple(self.warnings))
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))


@dataclass(frozen=True)
class EventCollection:
    events: Mapping[str, MotionEvent]
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        events = dict(self.events)
        for event_id, event in events.items():
            if event_id != event.event_id:
                raise ValueError(f"event mapping key {event_id!r} does not match event_id {event.event_id!r}")
        object.__setattr__(self, "events", frozen_mapping(events))
        object.__setattr__(self, "warnings", tuple(self.warnings))
