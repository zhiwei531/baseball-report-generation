from __future__ import annotations

from dataclasses import dataclass

from .validation import optional_finite, require_text


@dataclass(frozen=True)
class FrameReference:
    sequence_index: int
    source_frame_number: int | None
    timestamp_seconds: float | None
    source_clock: str

    def __post_init__(self) -> None:
        if not isinstance(self.sequence_index, int) or isinstance(self.sequence_index, bool) or self.sequence_index < 0:
            raise ValueError("sequence_index must be a zero-based non-negative integer")
        if self.source_frame_number is not None and (
            not isinstance(self.source_frame_number, int)
            or isinstance(self.source_frame_number, bool)
            or self.source_frame_number < 0
        ):
            raise ValueError("source_frame_number must be non-negative when present")
        timestamp = optional_finite(self.timestamp_seconds, "timestamp_seconds")
        if timestamp is not None and timestamp < 0:
            raise ValueError("timestamp_seconds must be non-negative")
        require_text(self.source_clock, "source_clock")


@dataclass(frozen=True)
class FrameWindow:
    indices: tuple[int, ...]
    primary: FrameReference

    def __post_init__(self) -> None:
        indices = tuple(self.indices)
        if not indices or any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in indices):
            raise ValueError("indices must contain non-negative frame indices")
        if len(set(indices)) != len(indices):
            raise ValueError("indices must not contain duplicates")
        if self.primary.sequence_index not in indices:
            raise ValueError("primary frame must be included in indices")
        object.__setattr__(self, "indices", indices)
