from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np

from build_vicon_2026_metrics import C3DTrial, all_point_rows, clean_label, marker, read_c3d
from pitching.sync_vicon_video import parse_c3d
from tests.fixtures.c3d_factory import make_c3d_bytes


class C3DReaderCharacterizationTests(unittest.TestCase):
    def _write_fixture(self, payload: bytes, directory: str, name: str = "fixture.c3d") -> Path:
        path = Path(directory) / name
        path.write_bytes(payload)
        return path

    def test_float_reader_shape_labels_units_and_invalid_rules(self) -> None:
        points = np.array(
            [
                [[100, 200, 300, 0], [0, 0, 0, 0]],
                [[110, 210, 310, -1], [1, 2, 3, 0]],
            ],
            dtype=float,
        )
        payload = make_c3d_bytes(
            labels=("Subject:Bat1", "LASI"),
            points=points,
            first_frame=42,
            rate_hz=100.0,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_fixture(payload, temp_dir)
            trial = read_c3d(path)
            sync = parse_c3d(path)

        self.assertEqual(trial.labels, ["Subject:Bat1", "LASI"])
        self.assertEqual([clean_label(label) for label in trial.labels], ["Bat1", "LASI"])
        self.assertEqual(trial.units, "mm")
        self.assertEqual(trial.rate_hz, 100.0)
        self.assertEqual(trial.points.shape, (2, 2, 4))
        np.testing.assert_allclose(trial.points[0, 0, :3], [100, 200, 300])
        self.assertTrue(np.isnan(trial.points[0, 1, :3]).all())
        self.assertTrue(np.isnan(trial.points[1, 0, :3]).all())
        np.testing.assert_allclose(trial.points[1, 1, :3], [1, 2, 3])

        self.assertFalse(hasattr(trial, "first_frame"))
        self.assertFalse(hasattr(trial, "analog"))
        self.assertFalse(hasattr(trial, "events"))
        self.assertEqual(sync.first_frame, 42)
        self.assertEqual(sync.fps, 100.0)
        self.assertEqual(sync.labels, ["Subject:Bat1", "LASI"])
        self.assertTrue(np.isfinite(sync.points_mm[0, 1]).all())
        self.assertTrue(np.isnan(sync.points_mm[1, 0]).all())

    def test_positive_scale_reader_and_sync_reader_diverge(self) -> None:
        points = np.array([[[1.5, 2.0, 2.5, 0], [10.0, 20.0, 30.0, 0]]], dtype=float)
        payload = make_c3d_bytes(labels=("P1", "P2"), points=points, scale=0.5)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = self._write_fixture(payload, temp_dir, "integer.c3d")
            trial = read_c3d(path)
            with self.assertRaisesRegex(ValueError, "Only floating-point"):
                parse_c3d(path)
        np.testing.assert_allclose(trial.points[0, :, :3], points[0, :, :3])

    def test_marker_alias_average_and_all_missing_behavior(self) -> None:
        trial = C3DTrial(
            path=Path("synthetic.c3d"),
            labels=["Subject:RWRA", "RWRB"],
            points=np.array(
                [
                    [[1, 2, 3, 0], [3, 4, 5, 0]],
                    [[np.nan, np.nan, np.nan, 0], [4, 6, 8, 0]],
                ],
                dtype=float,
            ),
            rate_hz=100.0,
            units="mm",
        )
        np.testing.assert_allclose(marker(trial, "RWRA", "RWRB"), [[2, 3, 4], [4, 6, 8]])
        self.assertTrue(np.isnan(marker(trial, "NO_SUCH_MARKER")).all())

    def test_all_point_rows_use_loaded_zero_based_index(self) -> None:
        points = np.array([[[10, 20, 30, 0]], [[11, 21, 31, 0]]], dtype=float)
        trial = C3DTrial(Path("synthetic.c3d"), ["Subject:Bat1"], points, 100.0, "mm")
        rows = all_point_rows(trial)
        self.assertEqual([row["frame_index"] for row in rows], [0, 1])
        self.assertEqual([row["timestamp_sec"] for row in rows], [0.0, 0.01])
        self.assertNotIn("source_frame_number", rows[0])


if __name__ == "__main__":
    unittest.main()
