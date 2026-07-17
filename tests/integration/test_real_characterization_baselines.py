from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

import numpy as np

from baseball_report.io.c3d import adapt_legacy_c3d
from baseball_report.legacy.batting_csv import adapt_batting_metrics_csv
from baseball_report.legacy.pitching_summary import adapt_pitching_summary_json
from baseball_report.reporting.adapters import build_report_data_from_legacy
from baseball_report.reporting.validation import validate_report_payload
from build_vicon_2026_metrics import read_c3d
from tools.capture_characterization_baseline import capture_batting, capture_pitching
from tools.capture_report_artifact_baseline import capture_report_artifacts

ROOT = Path(__file__).resolve().parents[2]


class ProtectedBaselineIntegrationTests(unittest.TestCase):
    @unittest.skipUnless(
        all(
            os.environ.get(name)
            for name in ("BASEBALL_REPORT_PITCHING_DIR", "BASEBALL_REPORT_COMBINED_DIR")
        ),
        "set protected report directories to run the stable ReportData adapter check",
    )
    def test_legacy_report_artifacts_adapt_to_stable_report_data(self) -> None:
        batting_path = Path(os.environ["BASEBALL_REPORT_COMBINED_DIR"]) / "batting_dashboard_metrics.csv"
        pitching_path = Path(os.environ["BASEBALL_REPORT_PITCHING_DIR"]) / "pitch_metrics_summary.json"
        adapted = (
            adapt_batting_metrics_csv(batting_path),
            adapt_pitching_summary_json(pitching_path),
        )
        report = build_report_data_from_legacy(
            adapted,
            report_id="protected-report-schema-check",
            created_at="2026-07-17T12:00:00+08:00",
            subject_id="protected-subject",
            subject_display_name="Protected Subject",
            subject_keys=("bryan",),
        )
        payload = validate_report_payload(report.to_dict())
        self.assertEqual(payload["schema_version"], "1.0.0")
        self.assertGreater(len(payload["motions"]), 0)
        self.assertGreater(len(payload["metrics"]), 0)
        self.assertEqual(len(payload["comparisons"]), len(payload["metrics"]))
        self.assertEqual([section["order"] for section in payload["sections"]], [0, 1])

    @unittest.skipUnless(
        all(
            os.environ.get(name)
            for name in ("BASEBALL_REPORT_BATTING_C3D", "BASEBALL_REPORT_PITCHING_C3D")
        ),
        "set both protected C3D paths to run canonical motion adapter checks",
    )
    def test_c3d_motion_adapter_fixed_cases(self) -> None:
        cases = (
            ("protected_batting_case_a.json", "BASEBALL_REPORT_BATTING_C3D"),
            ("protected_pitching_case_a.json", "BASEBALL_REPORT_PITCHING_C3D"),
        )
        for golden_name, environment_name in cases:
            with self.subTest(case=golden_name):
                expected = json.loads(
                    (ROOT / "tests" / "golden" / golden_name).read_text(encoding="utf-8")
                )
                trial = read_c3d(Path(os.environ[environment_name]))
                adapted = adapt_legacy_c3d(trial)
                source = expected["source"]
                self.assertEqual(adapted.motion.frame_count, source["frame_count"])
                self.assertEqual(adapted.motion.first_source_frame, source["first_source_frame"])
                self.assertEqual(adapted.motion.last_source_frame, source["last_source_frame"])
                self.assertEqual(len(adapted.motion.points), source["point_count"])
                self.assertEqual(adapted.motion.frame_rate_hz, source["rate_hz"])
                self.assertEqual(adapted.motion.length_unit, source["unit"])
                np.testing.assert_allclose(
                    adapted.legacy_points,
                    trial.points,
                    equal_nan=True,
                    atol=0,
                    rtol=0,
                )

    @unittest.skipUnless(
        os.environ.get("BASEBALL_REPORT_BATTING_C3D"),
        "set BASEBALL_REPORT_BATTING_C3D to run the protected batting baseline",
    )
    def test_batting_fixed_case(self) -> None:
        expected = json.loads(
            (ROOT / "tests" / "golden" / "protected_batting_case_a.json").read_text(
                encoding="utf-8"
            )
        )
        actual = capture_batting(
            Path(os.environ["BASEBALL_REPORT_BATTING_C3D"]),
            ready_valid_start_frame=int(
                os.environ.get("BASEBALL_REPORT_BATTING_READY_START", "770")
            ),
        )
        self.assertEqual(actual, expected)

    @unittest.skipUnless(
        os.environ.get("BASEBALL_REPORT_PITCHING_C3D"),
        "set BASEBALL_REPORT_PITCHING_C3D to run the protected pitching baseline",
    )
    def test_pitching_fixed_case(self) -> None:
        expected = json.loads(
            (ROOT / "tests" / "golden" / "protected_pitching_case_a.json").read_text(
                encoding="utf-8"
            )
        )
        actual = capture_pitching(Path(os.environ["BASEBALL_REPORT_PITCHING_C3D"]))
        self.assertEqual(actual, expected)

    @unittest.skipUnless(
        all(
            os.environ.get(name)
            for name in (
                "BASEBALL_REPORT_PITCHING_DIR",
                "BASEBALL_REPORT_COMBINED_DIR",
                "BASEBALL_REPORT_LOCAL_COMBINED_HTML",
                "BASEBALL_REPORT_LOCAL_XLSX",
            )
        ),
        "set all protected report artifact paths to run the report baseline",
    )
    def test_report_artifact_fixed_case(self) -> None:
        expected = json.loads(
            (ROOT / "tests" / "golden" / "protected_report_case_a.json").read_text(
                encoding="utf-8"
            )
        )
        actual = capture_report_artifacts(
            pitching_dir=Path(os.environ["BASEBALL_REPORT_PITCHING_DIR"]),
            combined_dir=Path(os.environ["BASEBALL_REPORT_COMBINED_DIR"]),
            combined_html=Path(os.environ["BASEBALL_REPORT_LOCAL_COMBINED_HTML"]),
            xlsx=Path(os.environ["BASEBALL_REPORT_LOCAL_XLSX"]),
        )
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
