from __future__ import annotations

import csv
import json
import math
import tempfile
import unittest
from dataclasses import FrozenInstanceError
from pathlib import Path

import numpy as np

from baseball_report.core.enums import (
    CoordinateProfile,
    MotionType,
    QualityStatus,
    SourceType,
    SubjectRole,
)
from baseball_report.core.errors import InputDataError, ReportSchemaError
from baseball_report.core.frames import FrameReference, FrameWindow
from baseball_report.core.motion import MotionSequence
from baseball_report.core.provenance import Provenance
from baseball_report.core.serialization import dumps_deterministic
from baseball_report.legacy.batting_csv import REQUIRED_COLUMNS, adapt_batting_metrics_csv
from baseball_report.legacy.pitching_summary import (
    PITCHING_REPORT_METRICS,
    adapt_pitching_summary_json,
)
from baseball_report.reporting.models import ReportAsset, ReportData, SubjectMetadata
from baseball_report.reporting.adapters import build_report_data_from_legacy, write_report_data
from baseball_report.reporting.composition import compose_report_view


class CoreModelTests(unittest.TestCase):
    def test_frame_identity_keeps_sequence_and_source_frames(self) -> None:
        frame = FrameReference(10, 700, 0.1, "vicon")
        window = FrameWindow((9, 10, 11), frame)
        self.assertEqual(frame.sequence_index, 10)
        self.assertEqual(frame.source_frame_number, 700)
        self.assertEqual(window.primary, frame)
        with self.assertRaises(ValueError):
            FrameWindow((9, 11), frame)
        with self.assertRaises(ValueError):
            FrameReference(1.5, None, None, "vicon")  # type: ignore[arg-type]

    def test_motion_sequence_owns_read_only_arrays(self) -> None:
        source = np.arange(9, dtype=float).reshape(3, 3)
        sequence = MotionSequence(
            sequence_id="trial",
            source_type=SourceType.C3D,
            motion_type=MotionType.BATTING,
            frame_rate_hz=100.0,
            frame_count=3,
            first_source_frame=690,
            points={"Bat1": source},
            timestamps_seconds=np.array([0.0, 0.01, 0.02]),
            coordinate_system=CoordinateProfile.LEGACY_VICON_Z_UP_MM,
            length_unit="mm",
            provenance=Provenance("c3d", "trial", "legacy.reader"),
        )
        source[0, 0] = 999
        self.assertEqual(sequence.points["Bat1"][0, 0], 0)
        with self.assertRaises(ValueError):
            sequence.points["Bat1"][0, 0] = 2
        with self.assertRaises(FrozenInstanceError):
            sequence.frame_count = 4  # type: ignore[misc]

    def test_serialization_is_deterministic_and_rejects_non_finite(self) -> None:
        self.assertEqual(dumps_deterministic({"b": 2, "a": 1}, indent=None), '{"a":1,"b":2}')
        with self.assertRaises(ReportSchemaError):
            dumps_deterministic({"value": math.nan})

    def test_report_data_supports_legacy_and_stable_schema_with_portable_assets(self) -> None:
        provenance = Provenance("legacy_json", "sample", "adapter")
        subject = SubjectMetadata("bryan", "Bryan", SubjectRole.STUDENT)
        report = ReportData(
            schema_version="0.1.0",
            report_id="bryan-report",
            created_at="2026-07-17T12:00:00+08:00",
            subject=subject,
            motions=(),
            events=(),
            metrics=(),
            comparisons=(),
            charts=(),
            assets=(),
            sections=(),
            warnings=(),
            provenance=provenance,
        )
        self.assertEqual(report.to_dict()["schema_version"], "0.1.0")
        self.assertEqual(report.to_json(), report.to_json())
        stable = ReportData(
            schema_version="1.0.0",
            report_id="stable",
            created_at="2026-07-17T00:00:00Z",
            subject=subject,
            motions=(),
            events=(),
            metrics=(),
            comparisons=(),
            charts=(),
            assets=(),
            sections=(),
            warnings=(),
            provenance=provenance,
        )
        self.assertEqual(stable.schema_version, "1.0.0")
        with self.assertRaises(ReportSchemaError):
            ReportData(
                schema_version="2.0.0",
                report_id="bad",
                created_at="2026-07-17T00:00:00Z",
                subject=subject,
                motions=(),
                events=(),
                metrics=(),
                comparisons=(),
                charts=(),
                assets=(),
                sections=(),
                warnings=(),
                provenance=provenance,
            )
        with self.assertRaises(ReportSchemaError):
            ReportAsset("bad", "image", "/private/report.png", "image/png")


class LegacyAdapterTests(unittest.TestCase):
    def test_batting_csv_preserves_metric_and_event_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "batting.csv"
            base = {column: "" for column in REQUIRED_COLUMNS}
            rows = [
                {
                    **base,
                    "trial_id": "bryan_bat_01",
                    "sample_name": "bryan",
                    "athlete": "bryan",
                    "action_type": "batting",
                    "source_file": "vicon_2026/bryan/Bat 01.c3d",
                    "module": "Ready Position",
                    "metric_name_zh": "髋肩分离角",
                    "metric_key": "ready_hip_shoulder_separation_deg",
                    "value": "11.25",
                    "unit": "deg",
                    "aggregation": "event mean",
                    "event_name": "Ready Position",
                    "event_rule": "five legacy frames",
                    "event_frame": "12",
                    "event_frames": "10;11;12;13;14",
                    "points_used": "LASI;RASI;LSHO;RSHO",
                    "formula": "legacy formula",
                    "components_json": "{}",
                    "notes": "right-handed assumption",
                },
                {
                    **base,
                    "trial_id": "bryan_bat_01",
                    "sample_name": "bryan",
                    "athlete": "bryan",
                    "action_type": "batting",
                    "source_file": "vicon_2026/bryan/Bat 01.c3d",
                    "module": "Contact Position",
                    "metric_name_zh": "球棒速度",
                    "metric_key": "contact_bat_speed_kmh",
                    "value": "41.5",
                    "unit": "km/h",
                    "aggregation": "event mean",
                    "event_name": "Contact Position",
                    "event_rule": "lowest Bat1_Z",
                    "event_frame": "22",
                    "event_frames": "20;21;22;23;24",
                    "points_used": "Bat1",
                    "formula": "legacy speed formula",
                    "components_json": '{"instant_frame":22}',
                    "notes": "not bat-speed peak",
                },
            ]
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
                writer.writeheader()
                writer.writerows(rows)
            adapted = adapt_batting_metrics_csv(path)

        self.assertEqual(len(adapted.bundles), 1)
        bundle = adapted.bundles[0]
        self.assertEqual(bundle.context.algorithm_profile, "legacy_batting_right_v1")
        self.assertEqual([metric.metric_id for metric in bundle.metrics], [row["metric_key"] for row in rows])
        self.assertEqual([metric.value for metric in bundle.metrics], [11.25, 41.5])
        self.assertEqual([metric.unit for metric in bundle.metrics], ["deg", "km/h"])
        self.assertEqual(bundle.metrics[1].event_id, "Contact Position")
        self.assertEqual(bundle.events.events["Contact Position"].window.indices, (20, 21, 22, 23, 24))
        self.assertEqual(
            bundle.metrics[1].components["legacy_fields"]["event_rule"],
            "lowest Bat1_Z",
        )
        self.assertIn("batting.contact.proxy", [warning.code for warning in bundle.metrics[1].warnings])
        report = build_report_data_from_legacy(
            [adapted],
            report_id="bryan-batting",
            created_at="2026-07-17T12:00:00+08:00",
            subject_id="bryan",
            subject_display_name="Bryan",
        )
        self.assertEqual(report.schema_version, "1.0.0")
        self.assertEqual([motion.sequence_id for motion in report.motions], ["bryan_bat_01"])
        self.assertEqual(report.sections[0].section_id, "batting_analysis")
        with tempfile.TemporaryDirectory() as output_dir:
            output = write_report_data(Path(output_dir) / "analysis_report_data.json", report)
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertNotIn("NaN", json.dumps(payload))

    def test_batting_csv_rejects_missing_contract_columns(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.csv"
            path.write_text("metric_key,value\nx,1\n", encoding="utf-8")
            with self.assertRaises(InputDataError):
                adapt_batting_metrics_csv(path)

    def test_pitching_summary_preserves_all_value_keys_and_report_metadata(self) -> None:
        values = {
            "knee_height_pct": 49.5,
            "hand_speed_kmh": 62.25,
            "release_forward_mm": 123.0,
        }
        payload = {
            "assumptions": {"lead_leg": "L", "drive_leg": "R", "throwing_arm": "R"},
            "athletes": [
                {
                    "key": "bryan",
                    "name": "Bryan",
                    "role": "student",
                    "source_file": "/protected/Bryan.c3d",
                    "frames": 662,
                    "rate_hz": 100.0,
                    "height_estimate_mm": 1271.0,
                    "floor_estimate_mm": 70.0,
                    "events": {"peak_knee": 198, "foot_contact": 359, "foot_plant": 379, "release": 419},
                    "values": values,
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pitch_metrics_summary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            adapted = adapt_pitching_summary_json(path)

        bundle = adapted.bundles[0]
        self.assertEqual({metric.metric_id for metric in bundle.metrics}, set(values))
        by_id = {metric.metric_id: metric for metric in bundle.metrics}
        self.assertEqual(len(PITCHING_REPORT_METRICS), 18)
        self.assertEqual(by_id["knee_height_pct"].unit, "pct")
        self.assertEqual(by_id["knee_height_pct"].components["legacy_event_name"], "准备阶段")
        self.assertEqual(by_id["knee_height_pct"].event_frame.sequence_index, 198)
        self.assertEqual(by_id["release_forward_mm"].unit, "mm")
        self.assertEqual(by_id["release_forward_mm"].components["contract_scope"], "auxiliary")
        self.assertIn("pitching.hand_speed.proxy", [warning.code for warning in by_id["hand_speed_kmh"].warnings])
        self.assertEqual(bundle.context.algorithm_profile, "legacy_pitching_right_v1")
        self.assertEqual(bundle.events.events["release"].primary_frame.timestamp_seconds, 4.19)
        report = build_report_data_from_legacy(
            [adapted],
            report_id="bryan-pitching",
            created_at="2026-07-17T12:00:00+08:00",
            subject_id="bryan",
            subject_display_name="Bryan",
        )
        self.assertEqual(report.sections[0].section_id, "pitching_analysis")
        self.assertEqual(report.sections[0].metric_ids, ("knee_height_pct", "hand_speed_kmh"))
        self.assertEqual(report.motions[0].frame_count, 662)

    def test_report_adapter_filters_legacy_peer_bundles_by_subject(self) -> None:
        payload = {
            "assumptions": {"lead_leg": "L", "drive_leg": "R", "throwing_arm": "R"},
            "athletes": [
                {
                    "key": key,
                    "name": name,
                    "role": role,
                    "source_file": f"{key}.c3d",
                    "frames": 10,
                    "rate_hz": 100.0,
                    "events": {"release": 5},
                    "values": {"hand_speed_kmh": value},
                }
                for key, name, role, value in (
                    ("player", "Player", "student", 50.0),
                    ("coach", "Coach", "coach", 60.0),
                )
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pitch_metrics_summary.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            adapted = adapt_pitching_summary_json(path)
        report = build_report_data_from_legacy(
            [adapted],
            report_id="player-only",
            created_at="2026-07-17T12:00:00+08:00",
            subject_id="player",
            subject_display_name="Player",
            subject_keys=("player",),
        )
        self.assertEqual([motion.sequence_id for motion in report.motions], ["player"])
        self.assertEqual({metric.sequence_id for metric in report.metrics}, {"player"})
        self.assertEqual(len(report.comparisons), 1)
        comparison = report.comparisons[0]
        self.assertEqual(comparison.reference_value, 60.0)
        self.assertEqual(comparison.group_mean, 50.0)
        self.assertEqual(comparison.group_min, 50.0)
        self.assertEqual(comparison.group_max, 50.0)
        self.assertEqual(comparison.difference, -10.0)
        self.assertEqual(comparison.included_subject_ids, ("player",))
        view = compose_report_view(report)
        self.assertEqual(view["schema_version"], "report_view.v1")
        section = view["sections"][0]
        self.assertEqual(section["section_id"], "pitching_analysis")
        self.assertEqual(len(section["metrics"]), 1)
        self.assertEqual(section["metrics"][0]["comparison"]["reference_value"], 60.0)
        with self.assertRaisesRegex(ValueError, "no motion bundle"):
            build_report_data_from_legacy(
                [adapted],
                report_id="missing",
                created_at="2026-07-17T12:00:00+08:00",
                subject_id="missing",
                subject_display_name="Missing",
                subject_keys=("missing",),
            )


if __name__ == "__main__":
    unittest.main()
