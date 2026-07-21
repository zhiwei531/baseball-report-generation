from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from baseball_report.visualization.batting_series import (
    build_batting_time_series,
    build_kinetic_speed_series,
)
import build_julian_coach_metrics_section as legacy_builder
import run_batting_report_pipeline as batting_pipeline


class BattingVisualizationSeriesTests(unittest.TestCase):
    def test_public_pipeline_passes_report_local_pose3d_to_builder(self) -> None:
        args = SimpleNamespace(
            report_dir=Path("reports/player"),
            peers=Path("reports/player/metrics.csv"),
            pitch_report=Path("reports/pitching/index.html"),
            sample_name="player",
            coach_sample_name="coach",
            player_slug="player",
            player_label="Player",
            skip_final_schema=True,
        )
        commands: list[list[object]] = []
        with patch.object(batting_pipeline, "run", side_effect=lambda command, **_kwargs: commands.append(command)):
            batting_pipeline.html_stage(
                args,
                Path("reports/player/batting_dashboard_metrics.csv"),
                Path("reports/player/analysis_report_data.json"),
            )
        command = commands[0]
        pose_index = command.index("--pose3d")
        self.assertEqual(command[pose_index + 1], Path("reports/player/vicon_2026_pose3d.csv"))

    def test_series_are_extracted_before_drawing_with_legacy_values(self) -> None:
        marker_points = {
            "Bat1": (0.0, 0.0, 1000.0),
            "Bat5": (-100.0, 0.0, 1000.0),
            "RASI": (0.0, 0.0, 1000.0),
            "LASI": (-100.0, 0.0, 1000.0),
            "RSHO": (0.0, 0.0, 1500.0),
            "LSHO": (-100.0, 0.0, 1500.0),
            "RWRA": (100.0, 0.0, 1300.0),
            "RELB": (0.0, 0.0, 1300.0),
            "RKNE": (0.0, 0.0, 500.0),
            "RANK": (100.0, 0.0, 0.0),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pose3d.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=(
                        "clip_id",
                        "frame_index",
                        "timestamp_sec",
                        "joint_name",
                        "x_3d",
                        "y_3d",
                        "z_3d",
                    ),
                )
                writer.writeheader()
                for frame in range(5):
                    for name, point in marker_points.items():
                        x = point[0] + (100.0 * frame if name == "Bat1" else 0.0)
                        writer.writerow(
                            {
                                "clip_id": "trial",
                                "frame_index": frame,
                                "timestamp_sec": frame / 10,
                                "joint_name": name,
                                "x_3d": x,
                                "y_3d": point[1],
                                "z_3d": point[2],
                            }
                        )

            rows = {
                "contact_bat_speed_kmh": {"event_frame": "2"},
                "coach_high_com_risk_index": {
                    "components_json": json.dumps(
                        {"swing_segment_frames": "0;1;2;3;4", "swing_peak_frame": 3}
                    )
                },
            }
            batting = build_batting_time_series(path, rows, "trial")
            kinetic = build_kinetic_speed_series(path, rows, "trial")

            expected_times = [-0.2, -0.1, 0.0, 0.1, 0.2]
            self.assertEqual([point[2] for point in batting["speed"]], list(range(5)))
            self.assertEqual([round(point[0], 12) for point in batting["speed"]], expected_times)
            self.assertEqual([round(point[1], 12) for point in batting["speed"]], [3.6] * 5)
            self.assertEqual([round(point[1], 12) for point in batting["angle"]], [0.0] * 5)
            self.assertEqual(batting["contact_time"], 0.0)
            self.assertAlmostEqual(batting["peak_time"], 0.1)
            self.assertEqual(
                [(curve["label"], curve["axis"]) for curve in kinetic],
                [
                    ("下肢", "angular"),
                    ("髋部", "angular"),
                    ("躯干", "angular"),
                    ("手腕", "angular"),
                    ("球棒", "speed"),
                ],
            )
            self.assertEqual(
                [round(point[1], 12) for point in kinetic[-1]["points"]],
                [3.6] * 5,
            )

            previous_path = legacy_builder.DEFAULT_POSE3D
            try:
                legacy_builder.DEFAULT_POSE3D = path
                self.assertEqual(legacy_builder.batting_time_series(rows, "trial"), batting)
                wrapped_kinetic = legacy_builder.kinetic_speed_series(rows, "trial")
                self.assertEqual(
                    [
                        {key: value for key, value in curve.items() if key != "color"}
                        for curve in wrapped_kinetic
                    ],
                    kinetic,
                )
            finally:
                legacy_builder.DEFAULT_POSE3D = previous_path


if __name__ == "__main__":
    unittest.main()
