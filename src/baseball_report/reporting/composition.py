from __future__ import annotations

from baseball_report.core.serialization import to_jsonable

from .models import ReportData, ReportSection


REPORT_VIEW_SCHEMA_VERSION = "report_view.v1"


def compose_report_view(report: ReportData) -> dict[str, object]:
    """Resolve ReportData references into a renderer-facing, ordered view."""

    metrics = {(item.sequence_id, item.metric_id): item for item in report.metrics}
    events = {(item.sequence_id, item.event_id): item for item in report.events}
    comparisons = {
        (item.sequence_id, item.metric_id): item for item in report.comparisons
    }
    charts = {item.artifact_id: item for item in report.charts}
    assets = {item.asset_id: item for item in report.assets}
    sections = [
        _compose_section(section, metrics, events, comparisons, charts, assets)
        for section in report.sections
    ]
    return to_jsonable(
        {
            "schema_version": REPORT_VIEW_SCHEMA_VERSION,
            "report_schema_version": report.schema_version,
            "report_id": report.report_id,
            "subject": report.subject,
            "sections": sections,
            "warnings": report.warnings,
            "provenance": report.provenance,
        }
    )


def _compose_section(
    section: ReportSection,
    metrics: dict[tuple[str, str], object],
    events: dict[tuple[str, str], object],
    comparisons: dict[tuple[str, str], object],
    charts: dict[str, object],
    assets: dict[str, object],
) -> dict[str, object]:
    sequence_ids = tuple(str(value) for value in section.metadata.get("sequence_ids", ()))
    selected_metrics = []
    for sequence_id in sequence_ids:
        for metric_id in section.metric_ids:
            metric = metrics.get((sequence_id, metric_id))
            if metric is not None:
                selected_metrics.append(
                    {
                        "result": metric,
                        "comparison": comparisons.get((sequence_id, metric_id)),
                    }
                )
    selected_events = [
        events[(sequence_id, event_id)]
        for sequence_id in sequence_ids
        for event_id in section.event_ids
        if (sequence_id, event_id) in events
    ]
    return {
        "section_id": section.section_id,
        "order": section.order,
        "title_zh": section.title_zh,
        "title_en": section.title_en,
        "status": section.status,
        "sequence_ids": list(sequence_ids),
        "metrics": selected_metrics,
        "events": selected_events,
        "charts": [charts[artifact_id] for artifact_id in section.chart_ids],
        "assets": [assets[asset_id] for asset_id in section.asset_ids],
        "metadata": section.metadata,
    }
