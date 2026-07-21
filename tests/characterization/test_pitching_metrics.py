from __future__ import annotations

import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pitching.build_pitch_template_metrics_report as pitching
from tests.fixtures.motion_factory import make_pitching_trial

ROOT = Path(__file__).resolve().parents[2]
GOLDEN = ROOT / "tests" / "golden" / "synthetic_pitching_metrics.json"


class PitchingMetricCharacterizationTests(unittest.TestCase):
    def test_events_all_values_and_fixed_angle_channels(self) -> None:
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        trial, labels = make_pitching_trial()
        events = pitching.detect_events(trial, labels, 0.0)
        self.assertEqual(events, golden["events"])
        self.assertLess(events["peak_knee"], events["foot_contact"])
        self.assertLessEqual(events["foot_contact"], events["foot_plant"])
        self.assertLess(events["foot_plant"], events["release"])
        values = pitching.compute_values(trial, labels, events, 0.0, 1700.0)
        self.assertEqual(set(values), set(golden["metric_values"]))
        self.assertEqual(len(values), 41)
        for metric_id, expected in golden["metric_values"].items():
            self.assertAlmostEqual(values[metric_id], expected, delta=1e-9)
        self.assertEqual(values["front_knee_peak_deg"], 32.0)
        self.assertEqual(values["rear_knee_peak_deg"], 52.0)
        self.assertEqual(values["rear_ankle_peak_deg"], 62.0)
        self.assertEqual(values["shoulder_abduction_release_deg"], 186.0)
        self.assertEqual(values["shoulder_rotation_release_deg"], 294.0)
        self.assertEqual(values["elbow_flex_release_deg"], 88.0)
        self.assertEqual(values["wrist_flex_release_deg"], 98.0)

    def test_18_report_metrics_scoring_status_and_peer_membership(self) -> None:
        golden = json.loads(GOLDEN.read_text(encoding="utf-8"))
        self.assertEqual(len(pitching.METRICS), 18)
        self.assertEqual(len({str(metric["key"]) for metric in pitching.METRICS}), 18)
        registry = [
            {
                key: metric[key]
                for key in ("key", "event", "section", "name", "en", "unit")
            }
            for metric in pitching.METRICS
        ]
        digest = hashlib.sha256(
            json.dumps(
                registry, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(digest, golden["report_registry_sha256"])
        metric = next(item for item in pitching.METRICS if item["key"] == "knee_height_pct")
        self.assertAlmostEqual(pitching.score_metric(50.0, metric), 100.0)
        self.assertEqual(pitching.status_from_score(82), ("优秀", "good"))
        self.assertEqual(pitching.status_from_score(66), ("良好", "review"))
        self.assertEqual(pitching.status_from_score(65.99), ("待提高", "risk"))
        bundles = [
            pitching.TrialBundle("subject", "Subject", "student", Path("a"), None, [], {}, {"m": 10.0}, 1, 0),
            pitching.TrialBundle("peer", "Peer", "student", Path("b"), None, [], {}, {"m": 20.0}, 1, 0),
            pitching.TrialBundle("coach", "Coach", "coach", Path("c"), None, [], {}, {"m": 100.0}, 1, 0),
        ]
        self.assertEqual(pitching.group_mean_all(bundles, "m"), 15.0)
        self.assertEqual(pitching.peer_stats(bundles, "m"), {"min": 10.0, "max": 20.0, "mean": 15.0})

    def test_summary_and_metric_csv_shapes_preserve_assumptions(self) -> None:
        trial, labels = make_pitching_trial()
        events = pitching.detect_events(trial, labels, 0.0)
        values = pitching.compute_values(trial, labels, events, 0.0, 1700.0)
        bundle = pitching.TrialBundle(
            "case_a", "Case A", "student", Path("synthetic.c3d"), trial, labels, events, values, 1700, 0
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            with patch.multiple(
                pitching,
                OUT_DIR=out_dir,
                PLAYER_NAME="Case A",
                PLAYER_KEY="case_a",
            ):
                pitching.write_json_summary([bundle])
                pitching.write_metric_csv([bundle])
            summary = json.loads((out_dir / "pitch_metrics_summary.json").read_text(encoding="utf-8"))
            with (out_dir / "pitch_metrics_all_players.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.DictReader(handle))
        self.assertEqual(summary["assumptions"]["lead_leg"], "L")
        self.assertEqual(summary["assumptions"]["drive_leg"], "R")
        self.assertEqual(summary["assumptions"]["throwing_arm"], "R")
        self.assertEqual(summary["athletes"][0]["events"], events)
        self.assertEqual(summary["athletes"][0]["values"], values)
        self.assertEqual(len(rows), 18)
        self.assertEqual(
            list(rows[0]),
            ["athlete", "role", "metric_key", "event", "section", "metric_name", "value", "unit"],
        )


if __name__ == "__main__":
    unittest.main()
