from __future__ import annotations

import hashlib
import json
import unittest

import numpy as np

import build_batting_dashboard_metrics as batting
import metric_calculations as calculations
import metric_registry as registry
import pitching.build_pitch_template_metrics_report as pitching
from tests.fixtures.motion_factory import make_batting_trial


class MetricRegistryTests(unittest.TestCase):
    def test_batting_registry_matches_all_report_rows(self) -> None:
        rows = batting.compute_trial_metrics(make_batting_trial(), 5, 5, 1.0, 0)
        self.assertEqual(len(registry.BATTING_METRICS), 17)
        self.assertEqual(
            [row["metric_key"] for row in rows],
            [definition.metric_id for definition in registry.BATTING_METRICS],
        )
        for row in rows:
            definition = registry.BATTING_METRICS_BY_ID[str(row["metric_key"])]
            self.assertEqual(row["metric_name_zh"], definition.display_name_zh)
            self.assertEqual(row["unit"], definition.unit)
            self.assertEqual(row["event_name"], definition.event_id)
            self.assertTrue(definition.formula)
            self.assertTrue(definition.required_points)

    def test_pitching_registry_is_the_exact_builder_contract(self) -> None:
        rows = registry.pitching_metric_dicts()
        self.assertEqual(len(rows), 18)
        self.assertEqual(rows, pitching.METRICS)
        digest = hashlib.sha256(
            json.dumps(
                [
                    {key: metric[key] for key in ("key", "event", "section", "name", "en", "unit")}
                    for metric in rows
                ],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        self.assertEqual(
            digest,
            "ca3713fb5d8b44ce4ae6c37313c0a02d3d9de92311884451578d43f5303ee820",
        )

    def test_registry_mappings_and_options_are_immutable(self) -> None:
        with self.assertRaises(TypeError):
            registry.BATTING_METRICS_BY_ID["new"] = registry.BATTING_METRICS[0]  # type: ignore[index]
        with self.assertRaises(TypeError):
            registry.PITCHING_METRICS[0].report_options["ideal"] = 0  # type: ignore[index]

    def test_pure_composite_and_geometry_calculations_keep_units(self) -> None:
        self.assertEqual(calculations.point_displacement_mm(np.zeros(3), np.array([3.0, 4.0, 0.0])), 5.0)
        self.assertEqual(calculations.height_ratio(850.0, 1700.0), 0.5)
        self.assertAlmostEqual(calculations.high_com_risk_index(0.48, 35.0, 35.0), 0.0)
        stability = calculations.hitting_zone_stability_score(650.0, 0.0, 0.0)
        self.assertEqual(stability.score, 100.0)
        self.assertEqual((stability.length_score, stability.plane_score, stability.curvature_score), (1.0, 1.0, 1.0))
        stride_pct, stride_mm, direction = calculations.stride_metrics(np.array([300.0, 400.0, 0.0]), 1000.0)
        self.assertEqual((stride_pct, stride_mm), (50.0, 500.0))
        self.assertAlmostEqual(direction, 53.13010235415598)
        self.assertEqual(calculations.arm_slot_deg(np.array([3.0, 4.0, 5.0])), 45.0)


if __name__ == "__main__":
    unittest.main()
