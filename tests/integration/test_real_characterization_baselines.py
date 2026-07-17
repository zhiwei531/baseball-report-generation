from __future__ import annotations

import json
import os
import unittest
from pathlib import Path

from tools.capture_characterization_baseline import capture_batting, capture_pitching
from tools.capture_report_artifact_baseline import capture_report_artifacts

ROOT = Path(__file__).resolve().parents[2]


class ProtectedBaselineIntegrationTests(unittest.TestCase):
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
