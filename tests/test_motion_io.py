from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from baseball_report.core.enums import (
    CoordinateProfile,
    MotionType,
    SourceType,
)
from baseball_report.io.c3d import adapt_legacy_c3d, inspect_c3d_header
from baseball_report.io.pose_csv import adapt_pose_rows
from build_vicon_2026_metrics import (
    all_point_rows,
    motion_manifest_entry,
    read_c3d,
    write_motion_manifest,
)
from tests.fixtures.c3d_factory import make_c3d_bytes


class C3DMotionAdapterTests(unittest.TestCase):
    def test_motion_wrapper_preserves_arrays_nan_mask_frames_and_timestamps(self) -> None:
        source = np.array(
            [
                [[100, 200, 300, 0], [0, 0, 0, 0]],
                [[110, 210, 310, -1], [1, 2, 3, 0]],
            ],
            dtype=float,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "subject_bat.c3d"
            path.write_bytes(
                make_c3d_bytes(
                    labels=("Subject:Bat1", "LASI"),
                    points=source,
                    first_frame=42,
                    rate_hz=100,
                )
            )
            trial = read_c3d(path)
            wrapped = adapt_legacy_c3d(trial)

        np.testing.assert_allclose(
            wrapped.legacy_points,
            trial.points,
            equal_nan=True,
            atol=0,
            rtol=0,
        )
        self.assertTrue(
            np.array_equal(np.isnan(wrapped.legacy_points), np.isnan(trial.points))
        )
        np.testing.assert_allclose(
            wrapped.motion.timestamps_seconds,
            [row["timestamp_sec"] for row in all_point_rows(trial)[::2]],
            atol=0,
            rtol=0,
        )
        self.assertEqual(wrapped.header.first_frame, 42)
        self.assertEqual(wrapped.header.last_frame, 43)
        self.assertEqual(wrapped.header.storage_type, "float32")
        self.assertEqual(wrapped.motion.first_source_frame, 42)
        self.assertEqual(wrapped.motion.last_source_frame, 43)
        self.assertEqual(wrapped.motion.frame_reference(0).source_frame_number, 42)
        self.assertEqual(wrapped.motion.frame_reference(1).source_frame_number, 43)
        self.assertEqual(wrapped.motion.coordinate_system, CoordinateProfile.LEGACY_VICON_Z_UP_MM)
        self.assertEqual(wrapped.motion.source_type, SourceType.C3D)
        self.assertEqual(wrapped.motion.motion_type, MotionType.BATTING)
        self.assertEqual(wrapped.point_keys, ("Subject:Bat1", "LASI"))
        self.assertEqual(wrapped.clean_labels, ("Bat1", "LASI"))
        self.assertFalse(wrapped.motion.valid["Subject:Bat1"][1])
        self.assertFalse(wrapped.motion.valid["LASI"][0])
        with self.assertRaises(ValueError):
            wrapped.legacy_points[0, 0, 0] = 0

    def test_positive_scale_header_and_manifest_are_additive(self) -> None:
        points = np.array([[[1.5, 2.0, 2.5, 0]]], dtype=float)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pitch.c3d"
            path.write_bytes(
                make_c3d_bytes(labels=("P1",), points=points, first_frame=690, scale=0.5)
            )
            trial = read_c3d(path)
            header = inspect_c3d_header(path)
            output = Path(temp_dir) / "motion_manifest.json"
            write_motion_manifest(output, [trial])
            payload = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual(header.storage_type, "int16_scaled")
        self.assertEqual(header.scale_factor, 0.5)
        self.assertEqual(trial.first_frame, 690)
        self.assertEqual(motion_manifest_entry(trial)["first_source_frame"], 690)
        entry = payload["sequences"][0]
        self.assertEqual(entry["frame_index_convention"], "zero_based_loaded_array")
        self.assertEqual(entry["source_frame_convention"], "c3d_header_frame_number")
        self.assertEqual(entry["storage_type"], "int16_scaled")
        self.assertEqual(entry["length_unit"], "mm")

    def test_duplicate_raw_labels_receive_stable_internal_keys(self) -> None:
        points = np.array([[[1, 2, 3, 0], [4, 5, 6, 0]]], dtype=float)
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "trial.c3d"
            path.write_bytes(make_c3d_bytes(labels=("P", "P"), points=points))
            wrapped = adapt_legacy_c3d(read_c3d(path))
        self.assertEqual(wrapped.point_keys, ("P", "P#2"))
        np.testing.assert_allclose(wrapped.motion.points["P#2"], [[4, 5, 6]])


def pose_row(
    frame: int,
    timestamp: float,
    landmark: str,
    x: float | str,
    y: float | str,
    z: float | str,
) -> dict[str, object]:
    return {
        "frame_index": frame,
        "timestamp_sec": timestamp,
        "landmark": landmark,
        "x_norm": x,
        "y_norm": y,
        "z_norm": z,
        "visibility": 0.9 if x != "" else "",
    }


class PoseMotionAdapterTests(unittest.TestCase):
    def test_mediapipe_rows_preserve_non_contiguous_source_frames(self) -> None:
        rows = [
            pose_row(frame, frame / 30, landmark, x, y, z)
            for frame, values in (
                (5, ((0.1, 0.2, -0.1), (0.3, 0.4, -0.2))),
                (7, ((0.2, 0.3, -0.1), (0.4, 0.5, -0.2))),
            )
            for landmark, (x, y, z) in zip(("left_wrist", "right_wrist"), values)
        ]
        adapted = adapt_pose_rows(
            rows,
            sequence_id="pose_case",
            motion_type=MotionType.BATTING,
            backend="mediapipe_pose_landmarker",
        )
        self.assertEqual(adapted.source_frame_numbers, (5, 7))
        self.assertEqual(adapted.motion.frame_reference(0).source_frame_number, 5)
        self.assertEqual(adapted.motion.frame_reference(1).source_frame_number, 7)
        self.assertAlmostEqual(adapted.motion.frame_rate_hz, 30)
        self.assertTrue(adapted.supports_depth)
        self.assertEqual(adapted.native_landmark_count, 2)
        self.assertEqual(adapted.motion.source_type, SourceType.MEDIAPIPE)
        self.assertEqual(
            adapted.motion.coordinate_system,
            CoordinateProfile.MEDIAPIPE_IMAGE_NORMALIZED,
        )

    def test_rtmpose_single_frame_requires_rate_and_records_degraded_capability(self) -> None:
        rows = [
            pose_row(10, 1 / 3, "left_wrist", 0.1, 0.2, ""),
            pose_row(10, 1 / 3, "right_wrist", "", "", ""),
        ]
        with self.assertRaisesRegex(ValueError, "frame_rate_hz is required"):
            adapt_pose_rows(
                rows,
                sequence_id="pose_case",
                motion_type=MotionType.PITCHING,
                backend="rtmpose_cpu_fallback",
            )
        adapted = adapt_pose_rows(
            rows,
            sequence_id="pose_case",
            motion_type=MotionType.PITCHING,
            backend="rtmpose_cpu_fallback",
            frame_rate_hz=30,
        )
        self.assertEqual(adapted.motion.source_type, SourceType.RTMPOSE)
        self.assertFalse(adapted.supports_depth)
        self.assertEqual(adapted.native_landmark_count, 17)
        self.assertFalse(adapted.motion.valid["right_wrist"][0])
        self.assertEqual(adapted.motion.warnings[0].code, "pose.rtmpose_transport_mapping")

    def test_pose_frames_require_a_consistent_landmark_set(self) -> None:
        rows = [
            pose_row(0, 0, "left_wrist", 0.1, 0.2, 0),
            pose_row(0, 0, "right_wrist", 0.3, 0.4, 0),
            pose_row(1, 0.1, "left_wrist", 0.2, 0.3, 0),
        ]
        with self.assertRaisesRegex(ValueError, "common landmark set"):
            adapt_pose_rows(
                rows,
                sequence_id="pose_case",
                motion_type=MotionType.BATTING,
                backend="mediapipe_pose_landmarker",
            )


if __name__ == "__main__":
    unittest.main()
