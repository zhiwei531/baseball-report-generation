from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from .provenance import AnalysisWarning
from .validation import frozen_mapping, require_finite, require_text


@dataclass(frozen=True)
class StageResult:
    stage_name: str
    success: bool
    input_summary: Mapping[str, object] = field(default_factory=dict)
    output_summary: Mapping[str, object] = field(default_factory=dict)
    artifacts: tuple[Path, ...] = ()
    warnings: tuple[AnalysisWarning, ...] = ()
    duration_seconds: float = 0.0

    def __post_init__(self) -> None:
        require_text(self.stage_name, "stage_name")
        duration = require_finite(self.duration_seconds, "duration_seconds")
        if duration < 0:
            raise ValueError("duration_seconds must be non-negative")
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(self, "input_summary", frozen_mapping(self.input_summary))
        object.__setattr__(self, "output_summary", frozen_mapping(self.output_summary))
        object.__setattr__(self, "artifacts", tuple(Path(path) for path in self.artifacts))
        object.__setattr__(self, "warnings", tuple(self.warnings))
