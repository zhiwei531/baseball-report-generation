from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import tempfile
from pathlib import Path
from typing import Any

from build_batting_dashboard_metrics import compute_trial_metrics, load_trials
from build_vicon_2026_metrics import all_point_rows, read_c3d, write_csv
from pitching.build_pitch_template_metrics_report import (
    METRICS,
    compute_values,
    detect_events,
    estimate_floor_height,
)
from build_vicon_2026_metrics import clean_label


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _file_identity(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"sha256": _sha256_bytes(data), "size_bytes": len(data)}


def _source_metadata(path: Path, trial: object) -> dict[str, object]:
    header = path.read_bytes()[:512]
    first_frame = struct.unpack_from("<H", header, 6)[0]
    last_frame = struct.unpack_from("<H", header, 8)[0]
    labels = [str(label) for label in trial.labels]
    return {
        "input": _file_identity(path),
        "first_source_frame": first_frame,
        "last_source_frame": last_frame,
        "frame_count": int(trial.points.shape[0]),
        "point_count": int(trial.points.shape[1]),
        "rate_hz": float(trial.rate_hz),
        "unit": str(trial.units),
        "raw_labels_sha256": _canonical_sha256(labels),
    }


def capture_batting(path: Path, *, ready_valid_start_frame: int) -> dict[str, object]:
    trial = read_c3d(path)
    rows = all_point_rows(trial)
    with tempfile.TemporaryDirectory() as temp_dir:
        points_path = Path(temp_dir) / "points.csv"
        write_csv(points_path, rows)
        loaded = [item for item in load_trials(points_path) if item.action_type == "batting"]
    if len(loaded) != 1:
        raise RuntimeError(f"expected one batting trial, got {len(loaded)}")
    metric_rows = compute_trial_metrics(
        loaded[0],
        ready_event_frames=5,
        contact_event_frames=5,
        ready_lookback_sec=0.68,
        ready_valid_start_frame=ready_valid_start_frame,
    )
    values: dict[str, float | None] = {}
    units: dict[str, str] = {}
    events: dict[str, dict[str, object]] = {}
    structure = []
    for row in metric_rows:
        metric_id = str(row["metric_key"])
        raw_value = float(row["value"])
        values[metric_id] = raw_value if math.isfinite(raw_value) else None
        units[metric_id] = str(row["unit"])
        event_name = str(row["event_name"])
        events[event_name] = {
            "primary_index": row["event_frame"],
            "indices": row["event_frames"],
        }
        structure.append(
            {
                key: row[key]
                for key in (
                    "metric_key",
                    "metric_name_zh",
                    "unit",
                    "aggregation",
                    "event_name",
                    "event_rule",
                    "event_frame",
                    "event_frames",
                    "points_used",
                    "formula",
                    "notes",
                )
            }
        )
    return {
        "schema_version": "characterization.v1",
        "case_id": "protected_batting_case_a",
        "motion_type": "batting",
        "source": _source_metadata(path, trial),
        "assumptions": {
            "coordinate_profile": "legacy_vicon_z_up_mm",
            "batting_side": "right",
            "ready_valid_start_frame": ready_valid_start_frame,
        },
        "events": events,
        "metric_count": len(metric_rows),
        "metric_ids": [str(row["metric_key"]) for row in metric_rows],
        "units": units,
        "numeric_payload_sha256": _canonical_sha256(values),
        "structure_sha256": _canonical_sha256(structure),
    }


def capture_pitching(path: Path) -> dict[str, object]:
    trial = read_c3d(path)
    labels = [clean_label(label) for label in trial.labels]
    floor_mm, height_mm = estimate_floor_height(trial, labels)
    events = detect_events(trial, labels, floor_mm)
    values = compute_values(trial, labels, events, floor_mm, height_mm)
    safe_values = {
        key: float(value) if math.isfinite(float(value)) else None
        for key, value in values.items()
    }
    registry = [
        {
            key: metric[key]
            for key in ("key", "event", "section", "name", "en", "unit")
        }
        for metric in METRICS
    ]
    return {
        "schema_version": "characterization.v1",
        "case_id": "protected_pitching_case_a",
        "motion_type": "pitching",
        "source": _source_metadata(path, trial),
        "assumptions": {
            "coordinate_profile": "legacy_vicon_z_up_mm",
            "throwing_arm": "right",
            "lead_leg": "left",
            "drive_leg": "right",
        },
        "events": events,
        "metric_count": len(values),
        "metric_ids": sorted(values),
        "report_metric_count": len(METRICS),
        "numeric_payload_sha256": _canonical_sha256(safe_values),
        "report_registry_sha256": _canonical_sha256(registry),
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture or verify an anonymized C3D characterization baseline."
    )
    parser.add_argument("motion", choices=("batting", "pitching"))
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    parser.add_argument("--ready-valid-start-frame", type=int, default=0)
    args = parser.parse_args()
    if bool(args.output) == bool(args.verify):
        parser.error("choose exactly one of --output or --verify")
    manifest = (
        capture_batting(args.input, ready_valid_start_frame=args.ready_valid_start_frame)
        if args.motion == "batting"
        else capture_pitching(args.input)
    )
    if args.verify:
        expected = _load_json(args.verify)
        if manifest != expected:
            raise SystemExit(
                "characterization baseline mismatch\nexpected="
                + json.dumps(expected, ensure_ascii=False, sort_keys=True, indent=2)
                + "\nactual="
                + json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2)
            )
        print(f"baseline verified: {args.verify}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
