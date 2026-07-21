from __future__ import annotations

import math
import os
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest

from baseball_report.comparison.legacy_rules import (
    batting_component_score,
    batting_status,
    pitching_score,
    status_from_score,
    summarize_peer_values,
)
from baseball_report.core.errors import ReportBuildError
from baseball_report.reporting.assets import copy_report_asset_tree
from baseball_report.reporting.template_contract import (
    CANONICAL_TEMPLATE_REPO_PATH,
    CANONICAL_TEMPLATE_SHA256,
    CANONICAL_TEMPLATE_SHAPE,
    template_sha256,
    validate_canonical_template,
)
import build_julian_coach_metrics_section as batting_builder
import pipeline_config
import pitching.build_pitch_template_metrics_report as pitching_builder


ROOT = Path(__file__).resolve().parents[1]


class ComparisonRuleParityTests(unittest.TestCase):
    def test_pitching_scores_statuses_and_peer_statistics_keep_legacy_behavior(self) -> None:
        cases = (
            (math.nan, {}, None),
            (10.0, {"ideal": 12.0, "spread": 8.0}, None),
            (20.0, {"lo": 5.0, "hi": 15.0}, None),
            (20.0, {"direction": "higher", "target": 25.0}, 30.0),
            (-12.0, {"direction": "lower_abs", "spread": 30.0}, None),
            (7.0, {}, None),
        )
        for value, metric, coach in cases:
            with self.subTest(value=value, metric=metric):
                self.assertEqual(
                    pitching_builder.score_metric(value, metric, coach),
                    pitching_score(value, metric, coach),
                )
        for score in (0.0, 65.999, 66.0, 81.999, 82.0, 100.0):
            self.assertEqual(pitching_builder.status_from_score(score), status_from_score(score))

        bundles = [
            SimpleNamespace(key="one", role="student", values={"metric": 2.0}),
            SimpleNamespace(key="two", role="student", values={"metric": 4.0}),
            SimpleNamespace(key="missing", role="student", values={"metric": math.nan}),
            SimpleNamespace(key="coach", role="coach", values={"metric": 100.0}),
        ]
        expected = summarize_peer_values((("one", 2.0), ("two", 4.0), ("missing", math.nan)))
        self.assertEqual(
            pitching_builder.peer_stats(bundles, "metric"),
            {"min": expected.minimum, "max": expected.maximum, "mean": expected.mean},
        )
        self.assertEqual(pitching_builder.group_mean_all(bundles, "metric"), expected.mean)
        self.assertEqual(expected.included_subject_ids, ("one", "two"))

    def test_batting_status_and_component_scores_keep_legacy_behavior(self) -> None:
        cases = (
            ("contact_bat_speed_kmh", 47.9, 60.0),
            ("contact_bat_speed_kmh", 48.0, 60.0),
            ("contact_bat_speed_kmh", 72.0, 60.0),
            ("coach_high_com_risk_index", 20.0, 25.0),
            ("coach_hitting_zone_stability_score", 80.0, 85.0),
            ("ready_bat_tilt_deg", 11.2, 10.0),
            ("ready_bat_tilt_deg", 13.0, 10.0),
            ("ready_bat_tilt_deg", None, 10.0),
        )
        for metric_id, value, standard in cases:
            player = {"value": "" if value is None else str(value)}
            coach = {"value": str(standard)}
            self.assertEqual(
                batting_builder.status_for(metric_id, player, coach),
                batting_status(metric_id, value, standard),
            )
        for metric_id, value, standard in (
            ("contact_bat_speed_kmh", 36.0, 60.0),
            ("contact_bat_speed_kmh", 60.0, 60.0),
            ("ready_to_contact_head_displacement_mm", 120.0, 100.0),
            ("ready_bat_tilt_deg", 13.0, 10.0),
            ("ready_bat_tilt_deg", 20.0, 10.0),
        ):
            self.assertEqual(
                batting_builder.component_score_against_standard(metric_id, value, standard),
                batting_component_score(metric_id, value, standard),
            )


class StaticReportingBoundaryTests(unittest.TestCase):
    def test_missing_optional_pitch_annotation_is_removed_without_reusing_assets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir)
            existing = output / "assets" / "video_2d_alignment" / "existing.png"
            existing.parent.mkdir(parents=True)
            existing.write_bytes(b"png")
            html = (
                '<figure class="section-annotation"><img src="assets/video_2d_alignment/existing.png"></figure>'
                '<figure class="section-annotation"><img src="assets/video_2d_alignment/missing.png"></figure>'
            )
            previous_out = pitching_builder.OUT_DIR
            previous_assets = pitching_builder.ASSET_DIR
            try:
                pitching_builder.OUT_DIR = output
                pitching_builder.ASSET_DIR = output / "assets"
                cleaned = pitching_builder.remove_missing_annotation_figures(html)
            finally:
                pitching_builder.OUT_DIR = previous_out
                pitching_builder.ASSET_DIR = previous_assets
        self.assertIn("existing.png", cleaned)
        self.assertNotIn("missing.png", cleaned)

    def test_bryan_template_tokens_are_not_stale_for_bryan(self) -> None:
        bryan_html = "球员Bryan assets/vicon_reconstruction_events/bryan_player_movement.gif"
        self.assertEqual(pitching_builder.stale_subject_references(bryan_html, "bryan"), [])
        self.assertEqual(
            pitching_builder.stale_subject_references(bryan_html, "another_player"),
            ["bryan_player_movement", "球员Bryan"],
        )
        self.assertEqual(
            pitching_builder.stale_subject_references("球员Julian", "bryan"),
            ["球员Julian"],
        )

    def test_git_tracked_canonical_template_blob_is_frozen(self) -> None:
        html = subprocess.run(
            ["git", "show", f"HEAD:{CANONICAL_TEMPLATE_REPO_PATH}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        self.assertEqual(template_sha256(html), CANONICAL_TEMPLATE_SHA256)
        self.assertEqual(
            validate_canonical_template(html, require_exact_blob=True),
            CANONICAL_TEMPLATE_SHAPE,
        )

    def test_asset_copy_is_scoped_and_rejects_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "pitching" / "assets"
            source.mkdir(parents=True)
            (source / "chart.png").write_bytes(b"chart")
            (source / ".DS_Store").write_bytes(b"sidecar")
            destination = root / "combined" / "pitch_assets"
            self.assertEqual(copy_report_asset_tree(source, destination), destination.resolve())
            self.assertEqual((destination / "chart.png").read_bytes(), b"chart")
            self.assertFalse((destination / ".DS_Store").exists())
            with self.assertRaises(ReportBuildError):
                copy_report_asset_tree(source, source)
            with self.assertRaises(ReportBuildError):
                copy_report_asset_tree(source.parent, source)

    def test_public_pipeline_environment_exposes_package_without_sys_path_mutation(self) -> None:
        env = pipeline_config.plot_environment({"PYTHONPATH": "existing"})
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep)[0], str(ROOT / "src"))


if __name__ == "__main__":
    unittest.main()
