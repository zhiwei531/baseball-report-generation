from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping

from baseball_report.core.errors import ReportSchemaError
from baseball_report.core.validation import portable_report_ref


REQUIRED_REPORT_FIELDS = (
    "schema_version",
    "report_id",
    "created_at",
    "subject",
    "motions",
    "events",
    "metrics",
    "comparisons",
    "charts",
    "assets",
    "sections",
    "warnings",
    "provenance",
)


def _reject_non_finite(value: object, path: str = "report") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ReportSchemaError(f"{path} contains NaN or Infinity")
    if isinstance(value, Mapping):
        for key, item in value.items():
            _reject_non_finite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_non_finite(item, f"{path}[{index}]")


def _object_list(payload: Mapping[str, object], field: str) -> list[dict[str, object]]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ReportSchemaError(f"{field} must be an array of objects")
    return value


def _unique(rows: list[dict[str, object]], field: str, label: str) -> set[str]:
    values = [str(row.get(field, "")) for row in rows]
    if any(not value for value in values):
        raise ReportSchemaError(f"{label} requires non-empty {field}")
    if len(values) != len(set(values)):
        raise ReportSchemaError(f"duplicate {label} {field} values are not allowed")
    return set(values)


def validate_report_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ReportSchemaError("report payload must be an object")
    missing = [field for field in REQUIRED_REPORT_FIELDS if field not in payload]
    if missing:
        raise ReportSchemaError("report payload is missing fields: " + ", ".join(missing))
    if not str(payload["schema_version"]).startswith("1.0."):
        raise ReportSchemaError("builder contract requires ReportData 1.0.x")
    if not isinstance(payload["subject"], dict):
        raise ReportSchemaError("subject must be an object")
    subject = payload["subject"]
    for field in ("subject_id", "display_name", "role"):
        if not isinstance(subject.get(field), str) or not subject[field].strip():
            raise ReportSchemaError(f"subject requires non-empty {field}")
    _reject_non_finite(payload)

    motions = _object_list(payload, "motions")
    events = _object_list(payload, "events")
    metrics = _object_list(payload, "metrics")
    charts = _object_list(payload, "charts")
    assets = _object_list(payload, "assets")
    sections = _object_list(payload, "sections")
    comparisons = _object_list(payload, "comparisons")
    _object_list(payload, "warnings")

    sequence_ids = _unique(motions, "sequence_id", "motion")
    event_keys = {(str(row.get("sequence_id", "")), str(row.get("event_id", ""))) for row in events}
    if len(event_keys) != len(events) or any(not all(key) for key in event_keys):
        raise ReportSchemaError("events require unique sequence_id/event_id pairs")
    metric_keys = {(str(row.get("sequence_id", "")), str(row.get("metric_id", ""))) for row in metrics}
    if len(metric_keys) != len(metrics) or any(not all(key) for key in metric_keys):
        raise ReportSchemaError("metrics require unique sequence_id/metric_id pairs")
    for sequence_id, event_id in event_keys:
        if sequence_id not in sequence_ids:
            raise ReportSchemaError(f"event {event_id!r} references unknown motion {sequence_id!r}")
    for metric in metrics:
        sequence_id = str(metric["sequence_id"])
        metric_id = str(metric["metric_id"])
        if sequence_id not in sequence_ids:
            raise ReportSchemaError(f"metric {metric_id!r} references unknown motion {sequence_id!r}")
        event_id = metric.get("event_id")
        if event_id is not None and (sequence_id, str(event_id)) not in event_keys:
            raise ReportSchemaError(f"metric {metric_id!r} references unknown event {event_id!r}")
    comparison_keys = {
        (str(row.get("sequence_id", "")), str(row.get("metric_id", ""))) for row in comparisons
    }
    if len(comparison_keys) != len(comparisons) or any(not all(key) for key in comparison_keys):
        raise ReportSchemaError("comparisons require unique sequence_id/metric_id pairs")
    for sequence_id, metric_id in comparison_keys:
        if sequence_id not in sequence_ids:
            raise ReportSchemaError(
                f"comparison {metric_id!r} references unknown motion {sequence_id!r}"
            )
        if (sequence_id, metric_id) not in metric_keys:
            raise ReportSchemaError(
                f"comparison references unknown metric {metric_id!r} for motion {sequence_id!r}"
            )
    if str(payload["schema_version"]) != "1.0.0":
        for comparison in comparisons:
            _validate_comparison_snapshots(comparison)

    chart_ids = _unique(charts, "artifact_id", "chart")
    asset_ids = _unique(assets, "asset_id", "asset")
    _unique(sections, "section_id", "section")
    metric_ids = {metric_id for _sequence_id, metric_id in metric_keys}
    event_ids = {event_id for _sequence_id, event_id in event_keys}
    for asset in assets:
        try:
            portable_report_ref(str(asset.get("file_ref", "")), "file_ref")
        except ValueError as exc:
            raise ReportSchemaError(str(exc)) from exc
        _validate_artifact_references(asset, "asset", sequence_ids, metric_ids, event_ids)
    for chart in charts:
        for field in ("data_ref", "file_ref"):
            ref = chart.get(field)
            if ref is not None:
                try:
                    portable_report_ref(str(ref), field)
                except ValueError as exc:
                    raise ReportSchemaError(str(exc)) from exc
        _validate_artifact_references(chart, "chart", sequence_ids, metric_ids, event_ids)
    for section in sections:
        for field, available in (
            ("metric_ids", metric_ids),
            ("event_ids", event_ids),
            ("chart_ids", chart_ids),
            ("asset_ids", asset_ids),
        ):
            refs = section.get(field, [])
            if not isinstance(refs, list):
                raise ReportSchemaError(f"section {field} must be an array")
            unknown = sorted(set(str(ref) for ref in refs) - available)
            if unknown:
                raise ReportSchemaError(f"section references unknown {field}: {', '.join(unknown)}")
    orders = [section.get("order") for section in sections]
    if any(not isinstance(order, int) or isinstance(order, bool) or order < 0 for order in orders):
        raise ReportSchemaError("section order must be a non-negative integer")
    if orders != sorted(orders) or len(orders) != len(set(orders)):
        raise ReportSchemaError("section order must be sorted and unique")
    return payload


def _validate_comparison_snapshots(comparison: dict[str, object]) -> None:
    if "reference_result" not in comparison or "peer_results" not in comparison:
        raise ReportSchemaError(
            "ReportData 1.0.1+ comparisons require reference_result and peer_results"
        )
    reference = comparison["reference_result"]
    if reference is not None:
        _validate_comparison_point(reference, "reference_result")
        if comparison.get("reference_value") != reference.get("value"):
            raise ReportSchemaError("reference_value must match reference_result.value")
    peers = comparison["peer_results"]
    if not isinstance(peers, list):
        raise ReportSchemaError("peer_results must be an array")
    for peer in peers:
        _validate_comparison_point(peer, "peer_results")


def _validate_comparison_point(value: object, field: str) -> None:
    if not isinstance(value, dict):
        raise ReportSchemaError(f"{field} entries must be objects")
    for key in ("subject_id", "sequence_id", "display_name", "role"):
        item = value.get(key)
        if not isinstance(item, str) or not item.strip():
            raise ReportSchemaError(f"{field} requires non-empty {key}")
    if not isinstance(value.get("components"), dict):
        raise ReportSchemaError(f"{field} components must be an object")
    if not isinstance(value.get("warnings"), list):
        raise ReportSchemaError(f"{field} warnings must be an array")


def _validate_artifact_references(
    artifact: dict[str, object],
    label: str,
    sequence_ids: set[str],
    metric_ids: set[str],
    event_ids: set[str],
) -> None:
    for field, available in (
        ("sequence_ids", sequence_ids),
        ("metric_ids", metric_ids),
        ("event_ids", event_ids),
    ):
        refs = artifact.get(field, [])
        if not isinstance(refs, list):
            raise ReportSchemaError(f"{label} {field} must be an array")
        unknown = sorted(set(str(ref) for ref in refs) - available)
        if unknown:
            raise ReportSchemaError(f"{label} references unknown {field}: {', '.join(unknown)}")


def load_report_payload(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ReportSchemaError(f"cannot read report payload {path}: {exc}") from exc
    return validate_report_payload(payload)
