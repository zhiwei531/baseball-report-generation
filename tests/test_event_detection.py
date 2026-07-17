from __future__ import annotations

import json
import unittest
from pathlib import Path

import numpy as np

import build_batting_dashboard_metrics as batting
import event_detection as events
import pitching.build_pitch_template_metrics_report as pitching
from tests.fixtures.motion_factory import make_batting_trial, make_pitching_trial


ROOT = Path(__file__).resolve().parents[1]


class EventDetectionTests(unittest.TestCase):
    def test_detected_event_enforces_sorted_window_and_primary_membership(self) -> None:
        with self.assertRaises(ValueError):
            events.DetectedEvent(
                event_id="bad",
                indices=(2, 1),
                primary_index=1,
                detector_id="test",
                rule="test rule",
                source="test",
            )
        with self.assertRaises(ValueError):
            events.DetectedEvent(
                event_id="bad",
                indices=(1, 2),
                primary_index=3,
                detector_id="test",
                rule="test rule",
                source="test",
            )

    def test_batting_typed_detectors_match_legacy_golden_windows(self) -> None:
        golden = json.loads(
            (ROOT / "tests/golden/synthetic_batting_metrics.json").read_text(encoding="utf-8")
        )
        trial = make_batting_trial()
        bat_barrel = batting.mapped_point(trial, "bat_barrel")
        bat_handle = batting.mapped_point(trial, "bat_handle")
        head = batting.mapped_point(trial, "head")
        speed = batting.speed_kmh(bat_barrel, trial.rate_hz)
        swing = events.detect_batting_swing_segment(speed, trial.rate_hz)
        ready = events.detect_batting_ready(
            bat_barrel,
            bat_handle,
            head,
            speed,
            swing.raw_indices[0],
            trial.rate_hz,
            5,
            swing.peak_speed_kmh,
            1.0,
            0,
        )
        contact = events.detect_batting_contact(
            bat_barrel,
            5,
            np.asarray(swing.expanded_indices, dtype=int),
        )
        self.assertEqual(
            ";".join(str(index) for index in ready.indices),
            golden["events"]["Ready Position"],
        )
        self.assertEqual(
            ";".join(str(index) for index in contact.indices),
            golden["events"]["Contact Position"],
        )
        self.assertTrue(contact.metadata["proxy"])
        self.assertEqual(ready.detector_id, "batting.ready.legacy_v1")

    def test_batting_no_finite_speed_fallback_is_preserved(self) -> None:
        result = events.detect_batting_swing_segment(np.full(7, np.nan), 100.0)
        self.assertEqual(result.raw_indices, tuple(range(7)))
        self.assertEqual(result.expanded_indices, tuple(range(7)))
        self.assertEqual(result.peak_index, 3)
        self.assertTrue(np.isnan(result.peak_speed_kmh))

    def test_pitching_typed_detector_matches_legacy_golden_and_order(self) -> None:
        golden = json.loads(
            (ROOT / "tests/golden/synthetic_pitching_metrics.json").read_text(encoding="utf-8")
        )
        trial, labels = make_pitching_trial()
        lead_knee = pitching.marker(trial, labels, "LKNE")
        lead_foot = pitching.safe_nanmean(
            [pitching.marker(trial, labels, "LHEE"), pitching.marker(trial, labels, "LTOE")],
            axis=0,
        )
        hand = pitching.safe_nanmean(
            [
                pitching.marker(trial, labels, "RWRA"),
                pitching.marker(trial, labels, "RWRB"),
                pitching.marker(trial, labels, "RFIN"),
            ],
            axis=0,
        )
        result = events.detect_pitching_events(
            lead_knee=lead_knee,
            lead_foot=lead_foot,
            throwing_hand=hand,
            rate_hz=trial.rate_hz,
            floor_mm=0.0,
        )
        self.assertEqual(result.as_legacy_frames(), golden["events"])
        frames = result.as_legacy_frames()
        self.assertLess(frames["peak_knee"], frames["foot_contact"])
        self.assertLessEqual(frames["foot_contact"], frames["foot_plant"])
        self.assertLess(frames["foot_plant"], frames["release"])
        self.assertEqual(result.events["release"].metadata["selection"], "peak_hand_speed_after_plant")

    def test_generic_vicon_key_action_keeps_peak_priority_and_midpoint_fallback(self) -> None:
        speeds = np.array([np.nan, 2.0, 5.0, 1.0])
        batting_event = events.detect_key_action_event(
            action_type="batting",
            right_hand_speed_kmh=np.zeros(4),
            left_hand_speed_kmh=np.zeros(4),
            bat_speed_kmh=speeds,
            frame_count=4,
        )
        self.assertEqual(
            (batting_event.primary_index, batting_event.rule),
            (2, "bat_speed_peak"),
        )
        fallback = events.detect_key_action_event(
            action_type="pitching",
            right_hand_speed_kmh=np.full(5, np.nan),
            left_hand_speed_kmh=np.full(5, np.nan),
            bat_speed_kmh=np.full(5, np.nan),
            frame_count=5,
        )
        self.assertEqual(
            (fallback.primary_index, fallback.rule),
            (2, "mid_frame_fallback"),
        )

    def test_video_wrist_peak_records_image_coordinate_units_and_fallback(self) -> None:
        detected = events.detect_video_wrist_peak(
            np.array([np.nan, 10.0, 30.0, 20.0]),
            120.0,
        )
        self.assertEqual(detected.primary_index, 2)
        self.assertEqual(detected.metadata["peak_speed_px_s"], 30.0)
        self.assertEqual(detected.source, "pose_image_coordinates")
        fallback = events.detect_video_wrist_peak(np.full(6, np.nan), 30.0)
        self.assertEqual(fallback.primary_index, 3)
        self.assertIsNone(fallback.metadata["peak_speed_px_s"])


if __name__ == "__main__":
    unittest.main()
