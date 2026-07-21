from __future__ import annotations

import json
from collections.abc import Mapping

_UNSET = object()


def _text(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def _frame_index(frame: object) -> str:
    if not isinstance(frame, Mapping):
        return ""
    return _text(frame.get("sequence_index"))


def _legacy_fields(components: object) -> tuple[dict[str, object], dict[str, object]]:
    if not isinstance(components, Mapping):
        return {}, {}
    legacy = components.get("legacy_fields")
    fields = dict(legacy) if isinstance(legacy, Mapping) else {}
    calculation = {str(key): value for key, value in components.items() if key != "legacy_fields"}
    return fields, calculation


def _metric_row(
    metric: Mapping[str, object],
    *,
    sample_name: str,
    athlete: str,
    sequence_id: str,
    value: object = _UNSET,
    unit: object = _UNSET,
    event_id: object = _UNSET,
    event_frame: object = _UNSET,
    components: object = _UNSET,
) -> dict[str, str]:
    metric_components = metric.get("components") if components is _UNSET else components
    legacy, calculation = _legacy_fields(metric_components)
    resolved_event_id = metric.get("event_id") if event_id is _UNSET else event_id
    resolved_event_frame = metric.get("event_frame") if event_frame is _UNSET else event_frame
    resolved_value = metric.get("value") if value is _UNSET else value
    resolved_unit = metric.get("unit") if unit is _UNSET else unit
    return {
        "trial_id": sequence_id,
        "sample_name": sample_name,
        "athlete": athlete,
        "action_type": "batting",
        "source_file": _text(legacy.get("source_file")),
        "module": _text(legacy.get("module")),
        "metric_name_zh": _text(metric.get("display_name_zh") or metric.get("metric_id")),
        "metric_key": _text(metric.get("metric_id")),
        "value": _text(resolved_value),
        "unit": _text(resolved_unit),
        "aggregation": _text(legacy.get("aggregation")),
        "event_name": _text(legacy.get("event_name") or resolved_event_id),
        "event_rule": _text(legacy.get("event_rule")),
        "event_frame": _text(legacy.get("event_frame") or _frame_index(resolved_event_frame)),
        "event_frames": _text(legacy.get("event_frames")),
        "points_used": _text(legacy.get("points_used")),
        "formula": _text(legacy.get("formula")),
        "components_json": json.dumps(calculation, ensure_ascii=False, allow_nan=False),
        "notes": _text(legacy.get("notes")),
    }


def batting_builder_rows_from_payload(
    payload: Mapping[str, object],
    *,
    player_sample_name: str,
    coach_sample_name: str,
) -> tuple[list[dict[str, str]], list[dict[str, object]]]:
    """Rebuild the legacy builder view exclusively from validated ReportData 1.0.1."""

    version = _text(payload.get("schema_version"))
    try:
        patch_version = int(version.rsplit(".", 1)[1])
    except (IndexError, ValueError) as exc:
        raise ValueError("batting builder requires ReportData 1.0.1 or newer") from exc
    if not version.startswith("1.0.") or patch_version < 1:
        raise ValueError("batting builder requires ReportData 1.0.1 or newer")
    metrics = payload.get("metrics")
    comparisons = payload.get("comparisons")
    if not isinstance(metrics, list) or not isinstance(comparisons, list):
        raise ValueError("ReportData must contain metric and comparison arrays")
    comparisons_by_key = {
        (item.get("sequence_id"), item.get("metric_id")): item
        for item in comparisons
        if isinstance(item, Mapping)
    }
    rows: list[dict[str, str]] = []
    peer_records: dict[str, dict[str, object]] = {}
    subject = payload.get("subject")
    subject_display_name = (
        _text(subject.get("display_name"))
        if isinstance(subject, Mapping)
        else player_sample_name
    )
    for metric_value in metrics:
        if not isinstance(metric_value, Mapping) or metric_value.get("motion_type") != "batting":
            continue
        sequence_id = _text(metric_value.get("sequence_id"))
        comparison = comparisons_by_key.get((sequence_id, metric_value.get("metric_id")))
        if not isinstance(comparison, Mapping):
            raise ValueError(f"missing comparison for batting metric {metric_value.get('metric_id')!r}")
        rows.append(
            _metric_row(
                metric_value,
                sample_name=player_sample_name,
                athlete=subject_display_name,
                sequence_id=sequence_id,
            )
        )
        reference = comparison.get("reference_result")
        if isinstance(reference, Mapping):
            rows.append(
                _metric_row(
                    metric_value,
                    sample_name=coach_sample_name,
                    athlete=_text(reference.get("display_name") or coach_sample_name),
                    sequence_id=_text(reference.get("sequence_id")),
                    value=reference.get("value"),
                    unit=reference.get("unit"),
                    event_id=reference.get("event_id"),
                    event_frame=reference.get("event_frame"),
                    components=reference.get("components"),
                )
            )
        peers = comparison.get("peer_results")
        if not isinstance(peers, list):
            continue
        for peer in peers:
            if not isinstance(peer, Mapping) or peer.get("value") is None:
                continue
            subject_id = _text(peer.get("subject_id"))
            display_name = _text(peer.get("display_name") or subject_id)
            record = peer_records.setdefault(
                subject_id,
                {"name": display_name, "rows": {}},
            )
            peer_metric_rows = record["rows"]
            assert isinstance(peer_metric_rows, dict)
            peer_metric_rows[_text(metric_value.get("metric_id"))] = {
                "metric_key": _text(metric_value.get("metric_id")),
                "metric_name_zh": _text(
                    metric_value.get("display_name_zh") or metric_value.get("metric_id")
                ),
                "value": _text(peer.get("value")),
                "unit": _text(peer.get("unit")),
            }
    return rows, list(peer_records.values())
