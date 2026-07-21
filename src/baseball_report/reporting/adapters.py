from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable, Sequence

from baseball_report.core.enums import MotionType, SubjectRole
from baseball_report.core.provenance import AnalysisWarning, Provenance
from baseball_report.comparison.legacy_rules import summarize_peer_values
from baseball_report.comparison.models import ComparisonPoint, ComparisonResult
from baseball_report.legacy.models import LegacyAdaptedReport, LegacyAnalysisBundle

from .models import (
    CURRENT_REPORT_SCHEMA_VERSION,
    MotionMetadata,
    ReportAsset,
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
    assets: Sequence[ReportAsset] = (),
) -> ReportData:
    all_bundles = tuple(bundle for report in adapted_reports for bundle in report.bundles)
    bundles = all_bundles
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
    comparisons = _build_comparisons(bundles, all_bundles)
    bound_assets = _bind_assets(assets, motions, metrics, events)
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
                metric_ids=_unique(
                    metric.metric_id
                    for bundle in selected
                    for metric in bundle.metrics
                    if metric.components.get("contract_scope") != "auxiliary"
                ),
                event_ids=_unique(event.event_id for bundle in selected for event in bundle.events.events.values()),
                asset_ids=tuple(
                    asset.asset_id
                    for asset in bound_assets
                    if set(asset.sequence_ids)
                    & {bundle.sequence_id for bundle in selected}
                ),
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
        comparisons=comparisons,
        charts=(),
        assets=bound_assets,
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


def _bind_assets(
    assets: Sequence[ReportAsset],
    motions: Sequence[MotionMetadata],
    metrics: Sequence[object],
    events: Sequence[object],
) -> tuple[ReportAsset, ...]:
    sequence_ids_by_motion = {
        motion_type: tuple(
            motion.sequence_id for motion in motions if motion.motion_type == motion_type
        )
        for motion_type in MotionType
    }
    metric_by_id = {str(getattr(metric, "metric_id")): metric for metric in metrics}
    available_event_ids = {str(getattr(event, "event_id")) for event in events}
    bound: list[ReportAsset] = []
    for asset in assets:
        scope_value = asset.metadata.get("motion_scope")
        try:
            scope = MotionType(str(scope_value)) if scope_value else None
        except ValueError:
            scope = None
        metric_ids = tuple(metric_id for metric_id in asset.metric_ids if metric_id in metric_by_id)
        event_ids = list(event_id for event_id in asset.event_ids if event_id in available_event_ids)
        for metric_id in metric_ids:
            metric_event = getattr(metric_by_id[metric_id], "event_id", None)
            if metric_event in available_event_ids and metric_event not in event_ids:
                event_ids.append(metric_event)
        sequence_ids = sequence_ids_by_motion.get(scope, ()) if scope is not None else ()
        bound.append(
            replace(
                asset,
                sequence_ids=sequence_ids,
                metric_ids=metric_ids,
                event_ids=tuple(event_ids),
            )
        )
    return tuple(bound)


def _bundle_role(bundle: LegacyAnalysisBundle) -> str:
    role = str(bundle.metadata.get("role") or "").strip().casefold()
    if role:
        return role
    identifiers = {
        bundle.context.subject_id.casefold(),
        str(bundle.metadata.get("sample_name") or "").strip().casefold(),
        str(bundle.metadata.get("athlete") or "").strip().casefold(),
    }
    return "coach" if "coach" in identifiers else "student"


def _metrics_by_id(bundle: LegacyAnalysisBundle) -> dict[str, object]:
    return {metric.metric_id: metric for metric in bundle.metrics}


def _bundle_display_name(bundle: LegacyAnalysisBundle) -> str:
    return str(
        bundle.metadata.get("athlete")
        or bundle.metadata.get("name")
        or bundle.metadata.get("sample_name")
        or bundle.context.subject_id
    )


def _comparison_point(bundle: LegacyAnalysisBundle, metric: object) -> ComparisonPoint:
    return ComparisonPoint(
        subject_id=bundle.context.subject_id,
        sequence_id=bundle.sequence_id,
        display_name=_bundle_display_name(bundle),
        role=_bundle_role(bundle),
        value=getattr(metric, "value", None),
        unit=getattr(metric, "unit", None),
        event_id=getattr(metric, "event_id", None),
        event_frame=getattr(metric, "event_frame", None),
        components=getattr(metric, "components", {}),
        warnings=getattr(metric, "warnings", ()),
    )


def _build_comparisons(
    subject_bundles: Sequence[LegacyAnalysisBundle],
    all_bundles: Sequence[LegacyAnalysisBundle],
) -> tuple[ComparisonResult, ...]:
    results: list[ComparisonResult] = []
    for subject_bundle in subject_bundles:
        related = [
            bundle
            for bundle in all_bundles
            if bundle.context.motion_type == subject_bundle.context.motion_type
        ]
        coaches = [bundle for bundle in related if _bundle_role(bundle) == "coach"]
        students = [bundle for bundle in related if _bundle_role(bundle) == "student"]
        student_metrics = [(bundle, _metrics_by_id(bundle)) for bundle in students]
        coach_bundle = coaches[0] if coaches else None
        coach_metrics = _metrics_by_id(coach_bundle) if coach_bundle is not None else {}
        for metric in subject_bundle.metrics:
            stats = summarize_peer_values(
                (
                    bundle.context.subject_id,
                    by_id[metric.metric_id].value if metric.metric_id in by_id else None,
                )
                for bundle, by_id in student_metrics
            )
            reference_metric = coach_metrics.get(metric.metric_id)
            reference_value = getattr(reference_metric, "value", None)
            reference_result = (
                _comparison_point(coach_bundle, reference_metric)
                if coach_bundle is not None and reference_metric is not None
                else None
            )
            peer_results = tuple(
                _comparison_point(bundle, by_id[metric.metric_id])
                for bundle, by_id in student_metrics
                if metric.metric_id in by_id
            )
            difference = (
                metric.value - reference_value
                if metric.value is not None and reference_value is not None
                else None
            )
            results.append(
                ComparisonResult(
                    metric_id=metric.metric_id,
                    sequence_id=subject_bundle.sequence_id,
                    subject_value=metric.value,
                    reference_value=reference_value,
                    group_mean=stats.mean,
                    group_min=stats.minimum,
                    group_max=stats.maximum,
                    difference=difference,
                    score=None,
                    status=metric.status,
                    included_subject_ids=stats.included_subject_ids,
                    reference_result=reference_result,
                    peer_results=peer_results,
                )
            )
    return tuple(results)


def write_report_data(path: Path, report: ReportData) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(report.to_json(indent=2), encoding="utf-8")
    temporary.replace(output)
    return output
