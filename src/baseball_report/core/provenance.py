from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .enums import WarningSeverity
from .validation import frozen_mapping, require_text


@dataclass(frozen=True)
class AnalysisWarning:
    code: str
    message: str
    severity: WarningSeverity = WarningSeverity.WARNING
    context: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.code, "code")
        require_text(self.message, "message")
        object.__setattr__(self, "context", frozen_mapping(self.context))


@dataclass(frozen=True)
class Provenance:
    source_type: str
    source_id: str
    algorithm_id: str
    algorithm_version: str = "legacy_v1"
    details: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.source_type, "source_type")
        require_text(self.source_id, "source_id")
        require_text(self.algorithm_id, "algorithm_id")
        require_text(self.algorithm_version, "algorithm_version")
        object.__setattr__(self, "details", frozen_mapping(self.details))
