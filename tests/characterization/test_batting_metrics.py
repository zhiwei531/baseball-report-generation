from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from build_batting_dashboard_metrics import (
    choose_batting_side,
    compute_trial_metrics,
    detect_ready_event,
    detect_swing_segment,
    first_valid_event_indices,
    lowest_z_event_indices,
    point,
    write_wide_csv,
)
from tests.fixtures.motion_factory import make_batting_trial

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden" / "synthetic_batting_metrics.json"


class BattingMetricCharacterizationTests(unittest.TestCase):
    def test_swing_ready_contact_and_fallback_rules(self) -> None:
        speed = np.array([0, 0, 0, 10, 20, 30, 20, 10, 0, 0], dtype=float)
        raw, expanded, peak, peak_speed, threshold = detect_swing_segment(
            speed, 10.0, expansion_sec=0.2
        )
        np.testing.assert_array_equal(raw, np.arange(3, 8))
        np.testing.assert_array_equal(expanded, np.arange(1, 10))
        self.assertEqual((peak, peak_speed, threshold), (5, 18.0, 8.0))

        count = 3
        frame_count = 20
        bat1 = np.tile([0.0, 0.0, 100.0], (frame_count, 1))
        bat1[8:11, 2] = 200.0
        bat5 = np.tile([0.0, 0.0, 50.0], (frame_count, 1))
        head = np.tile([0.0, 0.0, 170.0], (frame_count, 1))
        ready = detect_ready_event(
            bat1, bat5, head, np.ones(frame_count), 15, 10.0, count, 30.0, 1.0, None
        )
        np.testing.assert_array_equal(ready, [8, 9, 10])
        np.testing.assert_array_equal(
            lowest_z_event_indices(bat1, 3, np.arange(5, 15)), [5, 6, 7]
        )
        missing = np.full((frame_count, 3), np.nan)
        np.testing.assert_array_equal(
            first_valid_event_indices([missing], 3, frame_count), [0, 1, 2]
        )

    def test_all_17_metric_values_units_events_and_formulas(self) -> None:
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        rows = compute_trial_metrics(make_batting_trial(), 5, 5, 1.0, 0)
        by_id = {str(row["metric_key"]): row for row in rows}
        self.assertEqual(len(rows), 17)
        self.assertEqual(set(by_id), set(golden["metric_values"]))
        for metric_id, expected in golden["metric_values"].items():
            self.assertAlmostEqual(float(by_id[metric_id]["value"]), expected, delta=1e-9)
            self.assertEqual(by_id[metric_id]["unit"], golden["units"][metric_id])
            self.assertTrue(str(by_id[metric_id]["formula"]))
            self.assertIsInstance(json.loads(str(by_id[metric_id]["components_json"])), dict)
        structure = [
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
            for row in rows
        ]
        digest = hashlib.sha256(
            json.dumps(
                structure, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, golden["structure_sha256"])
        for event_name, expected_frames in golden["events"].items():
            event_rows = [row for row in rows if row["event_name"] == event_name]
            self.assertTrue(event_rows, event_name)
            self.assertTrue(all(row["event_frames"] == expected_frames for row in event_rows))
        self.assertEqual(choose_batting_side(), ("R", "L"))
        self.assertIn("right-handed assumption", by_id["ready_rear_hip_flexion_deg"]["notes"])
        self.assertIn("lowest Bat1_Z", by_id["contact_bat_speed_kmh"]["notes"])

    def test_missing_point_and_wide_csv_order(self) -> None:
        trial = make_batting_trial()
        self.assertTrue(np.isnan(point(trial, "UNKNOWN_POINT")).all())
        rows = compute_trial_metrics(trial, 5, 5, 1.0, 0)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "wide.csv"
            write_wide_csv(path, rows)
            with path.open(encoding="utf-8", newline="") as handle:
                header = next(csv.reader(handle))
        self.assertEqual(
            header,
            [
                "trial_id",
                "sample_name",
                "athlete",
                "action_type",
                "source_file",
                *[str(row["metric_key"]) for row in rows],
            ],
        )


if __name__ == "__main__":
    unittest.main()
