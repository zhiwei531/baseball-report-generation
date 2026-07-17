from __future__ import annotations

from pathlib import Path
from typing import Iterable, Sequence

from baseball_report.core.enums import MotionType, SubjectRole
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.legacy.models import LegacyAdaptedReport, LegacyAnalysisBundle

from .models import (
    CURRENT_REPORT_SCHEMA_VERSION,
    MotionMetadata,
    ReportData,
    ReportSection,
    SubjectMetadata,
)


def _optional_positive_int(value: object) -> int | None:
    if value in (None, ""):
        return None
    parsed = int(value)
    return parsed if parsed > 0 else None


def _optional_positive_float(value: object) -> float | None:
    if value in (None, ""):
        return None
    parsed = float(value)
    return parsed if parsed > 0 else None


def _source_type(source_file: object) -> str:
    suffix = Path(str(source_file or "")).suffix.lower()
    if suffix == ".c3d":
        return "c3d"
    if suffix in {".mp4", ".mov", ".avi"}:
        return "video"
    return "legacy_artifact"


def _motion_metadata(bundle: LegacyAnalysisBundle) -> MotionMetadata:
    source_file = bundle.metadata.get("source_file")
    return MotionMetadata(
        sequence_id=bundle.sequence_id,
        motion_type=bundle.context.motion_type,
        source_type=_source_type(source_file),
        frame_rate_hz=_optional_positive_float(bundle.metadata.get("rate_hz")),
        frame_count=_optional_positive_int(bundle.metadata.get("frames")),
        coordinate_system=bundle.context.coordinate_system.value,
        length_unit=bundle.context.length_unit,
        metadata={
            "source_file": source_file,
            "algorithm_profile": bundle.context.algorithm_profile,
            "legacy_metadata": dict(bundle.metadata),
        },
    )


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def build_report_data_from_legacy(
    adapted_reports: Sequence[LegacyAdaptedReport],
    *,
    report_id: str,
    created_at: str,
    subject_id: str,
    subject_display_name: str,
    subject_role: SubjectRole = SubjectRole.STUDENT,
    subject_keys: Iterable[str] | None = None,
) -> ReportData:
    bundles = tuple(bundle for report in adapted_reports for bundle in report.bundles)
    selected_keys = {str(value).strip().casefold() for value in subject_keys or () if str(value).strip()}
    if selected_keys:
        bundles = tuple(bundle for bundle in bundles if _bundle_matches(bundle, selected_keys))
        if not bundles:
            raise ValueError(
                "legacy reports contain no motion bundle matching subject keys: "
                + ", ".join(sorted(selected_keys))
            )
    motions = tuple(_motion_metadata(bundle) for bundle in bundles)
    events = tuple(event for bundle in bundles for event in bundle.events.events.values())
    metrics = tuple(metric for bundle in bundles for metric in bundle.metrics)
    warnings: list[AnalysisWarning] = []
    for report in adapted_reports:
        warnings.extend(report.warnings)
    for bundle in bundles:
        warnings.extend(bundle.warnings)

    sections: list[ReportSection] = []
    for order, motion_type in enumerate((MotionType.BATTING, MotionType.PITCHING)):
        selected = [bundle for bundle in bundles if bundle.context.motion_type == motion_type]
        if not selected:
            continue
        title_zh = "击球分析" if motion_type == MotionType.BATTING else "投球分析"
        title_en = "Batting Analysis" if motion_type == MotionType.BATTING else "Pitching Analysis"
        sections.append(
            ReportSection(
                section_id=f"{motion_type.value}_analysis",
                order=len(sections),
                title_zh=title_zh,
                title_en=title_en,
                status="available",
                metric_ids=_unique(metric.metric_id for bundle in selected for metric in bundle.metrics),
                event_ids=_unique(event.event_id for bundle in selected for event in bundle.events.events.values()),
                metadata={"sequence_ids": [bundle.sequence_id for bundle in selected]},
            )
        )

    source_paths = [str(report.source_path) for report in adapted_reports]
    return ReportData(
        schema_version=CURRENT_REPORT_SCHEMA_VERSION,
        report_id=report_id,
        created_at=created_at,
        subject=SubjectMetadata(subject_id, subject_display_name, subject_role),
        motions=motions,
        events=events,
        metrics=metrics,
        comparisons=(),
        charts=(),
        assets=(),
        sections=tuple(sections),
        warnings=tuple(warnings),
        provenance=Provenance(
            source_type="legacy_adapters",
            source_id=report_id,
            algorithm_id="baseball_report.reporting.adapters.v1",
            details={"source_paths": source_paths},
        ),
    )


def _bundle_matches(bundle: LegacyAnalysisBundle, selected_keys: set[str]) -> bool:
    candidates = {
        bundle.sequence_id,
        bundle.context.subject_id,
        str(bundle.metadata.get("sample_name") or ""),
        str(bundle.metadata.get("athlete") or ""),
        str(bundle.metadata.get("name") or ""),
    }
    return any(candidate.strip().casefold() in selected_keys for candidate in candidates if candidate.strip())


def write_report_data(path: Path, report: ReportData) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(report.to_json(indent=2), encoding="utf-8")
    temporary.replace(output)
    return output
