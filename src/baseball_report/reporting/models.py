from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import re
from typing import Mapping

from baseball_report.comparison.models import ComparisonResult
from baseball_report.core.enums import MotionType, QualityStatus, SubjectRole
from baseball_report.core.errors import ReportSchemaError
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.core.serialization import dumps_deterministic, to_jsonable
from baseball_report.core.validation import frozen_mapping, portable_report_ref, require_text
from baseball_report.events.models import MotionEvent
from baseball_report.metrics.models import MetricResult
from baseball_report.visualization.models import ChartArtifact

CURRENT_REPORT_SCHEMA_VERSION = "1.0.0"
_SUPPORTED_SCHEMA = re.compile(r"^(?:0\.\d+\.\d+|1\.0\.\d+)$")


@dataclass(frozen=True)
class SubjectMetadata:
    subject_id: str
    display_name: str
    role: SubjectRole
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.subject_id, "subject_id")
        require_text(self.display_name, "display_name")
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))


@dataclass(frozen=True)
class MotionMetadata:
    sequence_id: str
    motion_type: MotionType
    source_type: str
    frame_rate_hz: float | None
    frame_count: int | None
    coordinate_system: str
    length_unit: str
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.sequence_id, "sequence_id")
        require_text(self.source_type, "source_type")
        require_text(self.coordinate_system, "coordinate_system")
        require_text(self.length_unit, "length_unit")
        if self.frame_rate_hz is not None and self.frame_rate_hz <= 0:
            raise ValueError("frame_rate_hz must be positive")
        if self.frame_count is not None and self.frame_count <= 0:
            raise ValueError("frame_count must be positive")
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))


@dataclass(frozen=True)
class ReportAsset:
    asset_id: str
    kind: str
    file_ref: str
    mime_type: str | None
    sequence_ids: tuple[str, ...] = ()
    metric_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    quality: QualityStatus = QualityStatus.VALID
    provenance: Provenance | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.asset_id, "asset_id")
        require_text(self.kind, "kind")
        try:
            portable_report_ref(self.file_ref, "file_ref")
        except ValueError as exc:
            raise ReportSchemaError(str(exc)) from exc
        object.__setattr__(self, "sequence_ids", tuple(self.sequence_ids))
        object.__setattr__(self, "metric_ids", tuple(self.metric_ids))
        object.__setattr__(self, "event_ids", tuple(self.event_ids))
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))


@dataclass(frozen=True)
class ReportSection:
    section_id: str
    order: int
    title_zh: str
    title_en: str | None
    status: str
    metric_ids: tuple[str, ...] = ()
    event_ids: tuple[str, ...] = ()
    chart_ids: tuple[str, ...] = ()
    asset_ids: tuple[str, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        require_text(self.section_id, "section_id")
        require_text(self.title_zh, "title_zh")
        require_text(self.status, "status")
        if self.order < 0:
            raise ValueError("order must be non-negative")
        object.__setattr__(self, "metric_ids", tuple(self.metric_ids))
        object.__setattr__(self, "event_ids", tuple(self.event_ids))
        object.__setattr__(self, "chart_ids", tuple(self.chart_ids))
        object.__setattr__(self, "asset_ids", tuple(self.asset_ids))
        object.__setattr__(self, "metadata", frozen_mapping(self.metadata))


@dataclass(frozen=True)
class ReportData:
    schema_version: str
    report_id: str
    created_at: str
    subject: SubjectMetadata
    motions: tuple[MotionMetadata, ...]
    events: tuple[MotionEvent, ...]
    metrics: tuple[MetricResult, ...]
    comparisons: tuple[ComparisonResult, ...]
    charts: tuple[ChartArtifact, ...]
    assets: tuple[ReportAsset, ...]
    sections: tuple[ReportSection, ...]
    warnings: tuple[AnalysisWarning, ...]
    provenance: Provenance

    def __post_init__(self) -> None:
        if not _SUPPORTED_SCHEMA.fullmatch(self.schema_version):
            raise ReportSchemaError("schema_version must be a supported 0.x.y or 1.0.x version")
        require_text(self.report_id, "report_id")
        try:
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ReportSchemaError("created_at must be ISO-8601") from exc
        for field_name in (
            "motions",
            "events",
            "metrics",
            "comparisons",
            "charts",
            "assets",
            "sections",
            "warnings",
        ):
            object.__setattr__(self, field_name, tuple(getattr(self, field_name)))
        self._validate_unique("motion sequence", (item.sequence_id for item in self.motions))
        self._validate_unique("event", ((item.sequence_id, item.event_id) for item in self.events))
        self._validate_unique("metric result", ((item.sequence_id, item.metric_id) for item in self.metrics))
        self._validate_unique(
            "comparison result", ((item.sequence_id, item.metric_id) for item in self.comparisons)
        )
        self._validate_unique("chart", (item.artifact_id for item in self.charts))
        self._validate_unique("asset", (item.asset_id for item in self.assets))
        self._validate_unique("section", (item.section_id for item in self.sections))
        orders = tuple(section.order for section in self.sections)
        if orders != tuple(sorted(orders)):
            raise ReportSchemaError("sections must be ordered by their order field")
        self._validate_unique("section order", orders)
        sequence_ids = {item.sequence_id for item in self.motions}
        for event in self.events:
            if event.sequence_id not in sequence_ids:
                raise ReportSchemaError(
                    f"event {event.event_id!r} references unknown motion {event.sequence_id!r}"
                )
        for metric in self.metrics:
            if metric.sequence_id not in sequence_ids:
                raise ReportSchemaError(
                    f"metric {metric.metric_id!r} references unknown motion {metric.sequence_id!r}"
                )
            if metric.event_id is not None and not any(
                event.sequence_id == metric.sequence_id and event.event_id == metric.event_id
                for event in self.events
            ):
                raise ReportSchemaError(
                    f"metric {metric.metric_id!r} references unknown event {metric.event_id!r} "
                    f"for motion {metric.sequence_id!r}"
                )
        metric_keys = {(item.sequence_id, item.metric_id) for item in self.metrics}
        for comparison in self.comparisons:
            key = (comparison.sequence_id, comparison.metric_id)
            if comparison.sequence_id not in sequence_ids:
                raise ReportSchemaError(
                    f"comparison {comparison.metric_id!r} references unknown motion "
                    f"{comparison.sequence_id!r}"
                )
            if key not in metric_keys:
                raise ReportSchemaError(
                    f"comparison references unknown metric {comparison.metric_id!r} "
                    f"for motion {comparison.sequence_id!r}"
                )
        metric_ids = {item.metric_id for item in self.metrics}
        event_ids = {item.event_id for item in self.events}
        chart_ids = {item.artifact_id for item in self.charts}
        asset_ids = {item.asset_id for item in self.assets}
        for asset in self.assets:
            unknown_sequences = sorted(set(asset.sequence_ids) - sequence_ids)
            if unknown_sequences:
                raise ReportSchemaError(
                    f"asset {asset.asset_id!r} references unknown motions: {', '.join(unknown_sequences)}"
                )
            self._validate_references("metric", asset.metric_ids, metric_ids, asset.asset_id)
            self._validate_references("event", asset.event_ids, event_ids, asset.asset_id)
        for chart in self.charts:
            unknown_sequences = sorted(set(chart.sequence_ids) - sequence_ids)
            if unknown_sequences:
                raise ReportSchemaError(
                    f"chart {chart.artifact_id!r} references unknown motions: {', '.join(unknown_sequences)}"
                )
            self._validate_references("metric", chart.metric_ids, metric_ids, chart.artifact_id)
            self._validate_references("event", chart.event_ids, event_ids, chart.artifact_id)
        for section in self.sections:
            self._validate_references("metric", section.metric_ids, metric_ids, section.section_id)
            self._validate_references("event", section.event_ids, event_ids, section.section_id)
            self._validate_references("chart", section.chart_ids, chart_ids, section.section_id)
            self._validate_references("asset", section.asset_ids, asset_ids, section.section_id)
        to_jsonable(self)

    @staticmethod
    def _validate_unique(label: str, values: object) -> None:
        sequence = tuple(values)
        if len(sequence) != len(set(sequence)):
            raise ReportSchemaError(f"duplicate {label} IDs are not allowed")

    @staticmethod
    def _validate_references(label: str, values: tuple[str, ...], available: set[str], section_id: str) -> None:
        missing = sorted(set(values) - available)
        if missing:
            raise ReportSchemaError(
                f"container {section_id!r} references unknown {label} IDs: {', '.join(missing)}"
            )

    def to_dict(self) -> dict[str, object]:
        return to_jsonable(self)

    def to_json(self, *, indent: int | None = 2) -> str:
        return dumps_deterministic(self, indent=indent)
