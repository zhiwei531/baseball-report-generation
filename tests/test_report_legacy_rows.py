from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from baseball_report.legacy.batting_csv import REQUIRED_COLUMNS, adapt_batting_metrics_csv
from baseball_report.reporting.adapters import build_report_data_from_legacy
from baseball_report.reporting.legacy_rows import batting_builder_rows_from_payload


class ReportLegacyRowsTests(unittest.TestCase):
    def test_report_data_reconstructs_player_coach_and_peer_rows(self) -> None:
        base = {column: "" for column in REQUIRED_COLUMNS}
        rows = []
        for sample_name, athlete, trial_id, value, instant_frame in (
            ("bryan", "Bryan", "bryan_bat_01", "41.5", 22),
            ("coach", "Coach", "coach_bat_01", "48.25", 32),
            ("julian", "Julian", "julian_bat_01", "39.75", 42),
        ):
            rows.append(
                {
                    **base,
                    "trial_id": trial_id,
                    "sample_name": sample_name,
                    "athlete": athlete,
                    "action_type": "batting",
                    "source_file": f"vicon_2026/{sample_name}/Bat 01.c3d",
                    "module": "Contact Position",
                    "metric_name_zh": "球棒速度",
                    "metric_key": "contact_bat_speed_kmh",
                    "value": value,
                    "unit": "km/h",
                    "aggregation": "event mean",
                    "event_name": "Contact Position",
                    "event_rule": "lowest Bat1_Z",
                    "event_frame": str(instant_frame),
                    "event_frames": ";".join(str(instant_frame + offset) for offset in range(-2, 3)),
                    "points_used": "Bat1",
                    "formula": "legacy speed formula",
                    "components_json": f'{{"instant_frame":{instant_frame}}}',
                    "notes": "not bat-speed peak",
                }
            )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "batting.csv"
            with path.open("w", encoding="utf-8-sig", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(REQUIRED_COLUMNS))
                writer.writeheader()
                writer.writerows(rows)
            adapted = adapt_batting_metrics_csv(path)

        report = build_report_data_from_legacy(
            [adapted],
            report_id="bryan-report",
            created_at="2026-07-21T12:00:00+08:00",
            subject_id="bryan",
            subject_display_name="Bryan",
            subject_keys=("bryan",),
        )
        comparison = report.comparisons[0]
        self.assertEqual(comparison.reference_result.sequence_id, "coach_bat_01")
        self.assertEqual(comparison.reference_result.event_frame.sequence_index, 32)
        self.assertEqual(
            [(point.subject_id, point.value) for point in comparison.peer_results],
            [("bryan", 41.5), ("julian", 39.75)],
        )

        builder_rows, peer_rows = batting_builder_rows_from_payload(
            report.to_dict(),
            player_sample_name="bryan",
            coach_sample_name="coach",
        )
        by_sample = {row["sample_name"]: row for row in builder_rows}
        self.assertEqual(by_sample["bryan"]["trial_id"], "bryan_bat_01")
        self.assertEqual(by_sample["bryan"]["value"], "41.5")
        self.assertEqual(by_sample["coach"]["trial_id"], "coach_bat_01")
        self.assertEqual(by_sample["coach"]["event_frame"], "32")
        self.assertEqual(by_sample["coach"]["components_json"], '{"instant_frame": 32}')
        self.assertEqual(
            {
                record["name"]: record["rows"]["contact_bat_speed_kmh"]["value"]
                for record in peer_rows
            },
            {"Bryan": "41.5", "Julian": "39.75"},
        )

    def test_report_data_1_0_0_is_rejected_at_builder_adapter_boundary(self) -> None:
        with self.assertRaisesRegex(ValueError, "1.0.1"):
            batting_builder_rows_from_payload(
                {"schema_version": "1.0.0", "metrics": [], "comparisons": []},
                player_sample_name="player",
                coach_sample_name="coach",
            )


if __name__ == "__main__":
    unittest.main()
