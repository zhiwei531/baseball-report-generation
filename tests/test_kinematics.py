from __future__ import annotations

import unittest
import warnings

import numpy as np

import build_batting_dashboard_metrics as batting
import build_julian_coach_annotated_speed_gifs as annotated
import build_vicon_2026_metrics as vicon
import kinematics


class KinematicsPrimitiveTests(unittest.TestCase):
    def setUp(self) -> None:
        self.points = np.array(
            [
                [0.0, 0.0, 0.0],
                [100.0, 200.0, 300.0],
                [150.0, np.nan, 450.0],
                [300.0, 400.0, 600.0],
            ]
        )

    def test_finite_reductions_preserve_empty_and_supported_statistics(self) -> None:
        values = np.array([[1.0, np.nan, 5.0], [3.0, np.nan, np.nan]])
        np.testing.assert_allclose(
            kinematics.finite_mean(values, axis=0),
            [2.0, np.nan, 5.0],
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        self.assertTrue(np.isnan(kinematics.finite_scalar([np.nan])))
        self.assertEqual(kinematics.finite_scalar(values, "max"), 5.0)
        self.assertEqual(kinematics.finite_scalar(values, "min"), 1.0)
        self.assertEqual(kinematics.finite_scalar(values, "median"), 3.0)
        self.assertEqual(kinematics.finite_scalar(values, "sum"), 9.0)

    def test_speed_and_velocity_keep_legacy_nan_and_units(self) -> None:
        expected_speed = np.array([np.nan, 134.6996659238619, np.nan, np.nan])
        np.testing.assert_allclose(
            kinematics.speed_kmh_from_mm(self.points, 100),
            expected_speed,
            equal_nan=True,
            rtol=1e-15,
        )
        expected_velocity = np.vstack(
            [np.full(3, np.nan), np.diff(self.points, axis=0) * 100]
        )
        np.testing.assert_allclose(
            kinematics.velocity_mm_s(self.points, 100),
            expected_velocity,
            equal_nan=True,
            atol=0,
            rtol=0,
        )

    def test_angle_ranges_and_degenerate_vectors(self) -> None:
        a = np.array([[1.0, 0, 0], [0, 0, 0]])
        b = np.zeros((2, 3))
        c = np.array([[0.0, 1, 0], [0, 0, 0]])
        np.testing.assert_allclose(
            kinematics.joint_angle_deg(a, b, c),
            [90.0, np.nan],
            equal_nan=True,
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            legacy = kinematics.joint_angle_deg_legacy_divide(a, b, c)
        np.testing.assert_allclose(legacy, [90.0, np.nan], equal_nan=True)
        np.testing.assert_allclose(
            kinematics.circular_difference_deg(
                np.array([10.0, 350.0]), np.array([350.0, 10.0])
            ),
            [20.0, -20.0],
        )

    def test_signed_axis_angle_orientation(self) -> None:
        radial = np.array([[0.0, 1.0, 0.0], [0.0, -1.0, 0.0]])
        axis = np.tile([0.0, 0.0, 1.0], (2, 1))
        reference = np.tile([1.0, 0.0, 0.0], (2, 1))
        np.testing.assert_allclose(
            kinematics.signed_angle_about_axis_deg(radial, axis, reference),
            [90.0, -90.0],
        )

    def test_legacy_wrappers_are_elementwise_identical(self) -> None:
        np.testing.assert_allclose(
            batting.speed_kmh(self.points, 100),
            kinematics.speed_kmh_from_mm(self.points, 100),
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        np.testing.assert_allclose(
            annotated.speed_kmh(self.points, 100),
            kinematics.speed_kmh_from_mm(self.points, 100),
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        np.testing.assert_allclose(
            vicon.speed_kmh(self.points, 100),
            kinematics.speed_kmh_from_mm(self.points, 100),
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        values = np.array([[1.0, np.nan], [3.0, 5.0]])
        np.testing.assert_allclose(
            batting.finite_mean(values),
            kinematics.finite_mean(values),
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        np.testing.assert_allclose(
            vicon.safe_nanmean(values),
            kinematics.finite_mean(values),
            equal_nan=True,
            atol=0,
            rtol=0,
        )


if __name__ == "__main__":
    unittest.main()
