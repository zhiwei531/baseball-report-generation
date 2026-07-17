from __future__ import annotations

import argparse
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

import align_2d_video_vicon as alignment


class _FakeCapture:
    def __init__(self, frames: list[np.ndarray]) -> None:
        self.frames = list(frames)
        self.released = False

    def read(self) -> tuple[bool, np.ndarray | None]:
        if not self.frames:
            return False, None
        return True, self.frames.pop(0)

    def release(self) -> None:
        self.released = True


class _FakeDetector:
    def __init__(self, result: object) -> None:
        self.result = result

    def __enter__(self) -> "_FakeDetector":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def detect_for_video(self, _image: object, _timestamp_ms: int) -> object:
        return self.result


class _FakeBaseOptions:
    class Delegate:
        CPU = "cpu"

    def __init__(self, **_kwargs: object) -> None:
        pass


class PoseAlignmentCharacterizationTests(unittest.TestCase):
    def test_mediapipe_path_emits_33_rows_and_missing_values(self) -> None:
        self.assertEqual(len(alignment.LANDMARK_NAMES), 33)
        frame = np.zeros((10, 20, 3), dtype=np.uint8)
        cap = _FakeCapture([frame])
        result = SimpleNamespace(pose_landmarks=[])
        with tempfile.TemporaryDirectory() as temp_dir:
            model = Path(temp_dir) / "pose.task"
            model.write_bytes(b"fixture")
            with (
                patch.object(alignment, "open_video", return_value=(cap, 20, 10, 25.0, 1)),
                patch.object(alignment, "BaseOptions", _FakeBaseOptions),
                patch.object(alignment.vision, "PoseLandmarkerOptions", return_value=object()),
                patch.object(
                    alignment.vision.PoseLandmarker,
                    "create_from_options",
                    return_value=_FakeDetector(result),
                ),
                patch.object(alignment.cv2, "cvtColor", return_value=frame),
                patch.object(alignment.mp, "Image", return_value=object()),
            ):
                rows, meta = alignment.detect_2d(Path("video.mp4"), model)
        self.assertEqual(len(rows), 33)
        self.assertEqual({row["frame_index"] for row in rows}, {0})
        self.assertEqual([row["landmark"] for row in rows], alignment.LANDMARK_NAMES)
        self.assertTrue(all(row["x_norm"] == "" and row["z_norm"] == "" for row in rows))
        self.assertEqual(meta["frames_read"], 1)
        self.assertTrue(cap.released)

    def test_rtmpose_fallback_duplicates_transport_points_and_keeps_z_blank(self) -> None:
        class FakeRTMPose:
            def __init__(self, *_args: object, **_kwargs: object) -> None:
                pass

            def __call__(self, _frame: np.ndarray, **_kwargs: object) -> tuple[np.ndarray, np.ndarray]:
                points = np.arange(34, dtype=float).reshape(1, 17, 2)
                scores = np.linspace(0.5, 1.0, 17).reshape(1, 17)
                return points, scores

        fake_module = types.ModuleType("rtmlib")
        fake_module.RTMPose = FakeRTMPose  # type: ignore[attr-defined]
        cap = _FakeCapture([np.zeros((20, 10, 3), dtype=np.uint8)])
        with (
            patch.dict(sys.modules, {"rtmlib": fake_module}),
            patch.object(alignment, "open_video", return_value=(cap, 10, 20, 25.0, 1)),
        ):
            rows, meta = alignment.detect_2d_rtmpose(Path("video.mp4"))
        self.assertEqual(len(rows), 33)
        by_name = {row["landmark"]: row for row in rows}
        self.assertEqual(by_name["left_wrist"]["x_px"], by_name["left_pinky"]["x_px"])
        self.assertEqual(by_name["left_ankle"]["x_px"], by_name["left_heel"]["x_px"])
        self.assertTrue(all(row["z_norm"] == "" for row in rows))
        self.assertEqual(meta["pose_backend"], "rtmpose_cpu_fallback")

    def test_alignment_uses_capture_fps_but_playback_fps_for_display_time(self) -> None:
        rows = [{"frame_index": index, "timestamp_sec": index / 100.0} for index in range(5)]
        aligned = alignment.build_aligned_rows(
            c3d_rows=rows,
            vicon_event_frame=2,
            vicon_rate_hz=100.0,
            video_event_frame=30,
            video_fps=29.97,
            video_capture_fps=30.0,
            video_frame_count=100,
        )
        self.assertEqual([row["aligned_video_frame_index"] for row in aligned], [29, 30, 30, 30, 31])
        self.assertAlmostEqual(aligned[0]["aligned_video_playback_time_sec"], 29 / 29.97)
        self.assertAlmostEqual(aligned[0]["aligned_video_capture_time_sec"], 29 / 30.0)
        self.assertEqual(aligned[2]["vicon_time_from_event_sec"], 0.0)

    def test_subset_inference_returns_subset_position_not_source_frame(self) -> None:
        rows = []
        for source_frame, left_x in ((10, 0.0), (20, 10.0), (30, 30.0)):
            rows.extend(
                [
                    {
                        "frame_index": source_frame,
                        "landmark": "left_wrist",
                        "x_px": left_x,
                        "y_px": 0.0,
                    },
                    {
                        "frame_index": source_frame,
                        "landmark": "right_wrist",
                        "x_px": 0.0,
                        "y_px": 0.0,
                    },
                ]
            )
        with self.assertWarnsRegex(RuntimeWarning, "All-NaN slice"):
            event = alignment.infer_video_event(rows, 10.0)
        self.assertEqual(event["frame_index"], 2)
        self.assertNotEqual(event["frame_index"], 30)

    def test_reviewed_video_frame_bypasses_automatic_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            out_dir = Path(temp_dir)
            args = argparse.Namespace(
                video=Path("video.mp4"),
                c3d=Path("trial.c3d"),
                out_dir=out_dir,
                model=Path("pose.task"),
                video_capture_fps=100.0,
                video_event_frame=7,
                frame_indices=None,
            )
            trial = SimpleNamespace(
                rate_hz=100.0,
                points=np.zeros((10, 1, 4)),
                units="mm",
            )
            with (
                patch.object(alignment.argparse.ArgumentParser, "parse_args", return_value=args),
                patch.object(alignment, "read_c3d", return_value=trial),
                patch.object(alignment, "key_action_frame", return_value=(2, "event", "rule")),
                patch.object(alignment, "all_point_rows", return_value=[{"timestamp_sec": 0.02}]),
                patch.object(
                    alignment,
                    "detect_2d",
                    return_value=([], {"fps": 25.0, "frames_read": 20}),
                ),
                patch.object(alignment, "infer_video_event", side_effect=AssertionError("must not infer")),
                patch.object(alignment, "build_aligned_rows", return_value=[]),
                patch.object(alignment, "reconstruction_point_names", return_value=[]),
                patch("builtins.print"),
            ):
                alignment.main()
            summary = json.loads((out_dir / "alignment_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["video_event"]["frame_index"], 7)
        self.assertEqual(summary["video_event"]["source"], "user_reviewed_video_frame")
        self.assertEqual(summary["alignment"]["video_capture_fps"], 100.0)


if __name__ == "__main__":
    unittest.main()
