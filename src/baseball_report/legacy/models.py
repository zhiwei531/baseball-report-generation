from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from baseball_report.core.motion import AnalysisContext
from baseball_report.core.provenance import AnalysisWarning
from baseball_report.core.validation import frozen_mapping
from baseball_report.events.models import EventCollection
from baseball_report.metrics.models import MetricResult


@dataclass(frozen=True)
class LegacyAnalysisBundle:
    sequence_id: str
    context: AnalysisContext
    events: EventCollection
    metrics: tuple[MetricResult, ...]
    metadata: Mapping[str, object] = field(default_factory=dict)
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "metrics", tuple(self.metrics))
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))
        object.__setattr__(self, "warnings", tuple(self.warnings))


@dataclass(frozen=True)
class LegacyAdaptedReport:
    source_path: Path
    bundles: tuple[LegacyAnalysisBundle, ...]
    warnings: tuple[AnalysisWarning, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_path", Path(self.source_path))
        object.__setattr__(self, "bundles", tuple(self.bundles))
        object.__setattr__(self, "warnings", tuple(self.warnings))
