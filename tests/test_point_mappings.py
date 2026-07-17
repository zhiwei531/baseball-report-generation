from __future__ import annotations

import hashlib
import json
import unittest

import align_2d_video_vicon as alignment
import point_mappings as mappings
import render_aligned_2d_overlay as overlay
import render_vicon_geometry_metrics_on_2d as geometry
import render_vicon_reconstruction_images as reconstruction


def stable_hash(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class PointMappingTests(unittest.TestCase):
    def test_pose_names_and_rtmpose_mapping_preserve_legacy_contract(self) -> None:
        self.assertEqual(len(mappings.MEDIAPIPE_LANDMARK_NAMES), 33)
        self.assertEqual(mappings.MEDIAPIPE_LANDMARK_NAMES[0], "nose")
        self.assertEqual(mappings.MEDIAPIPE_LANDMARK_NAMES[-1], "right_foot_index")
        self.assertEqual(
            set(mappings.RTMPOSE_COCO17_TO_REPORT),
            set(mappings.MEDIAPIPE_LANDMARK_NAMES),
        )
        self.assertEqual(set(mappings.RTMPOSE_COCO17_TO_REPORT.values()), set(range(17)))
        self.assertEqual(alignment.LANDMARK_NAMES, list(mappings.MEDIAPIPE_LANDMARK_NAMES))
        self.assertEqual(alignment.RTMPOSE_COCO17, mappings.RTMPOSE_COCO17_TO_REPORT)

    def test_render_topologies_remain_explicit_and_distinct(self) -> None:
        self.assertEqual(len(mappings.POSE_OVERLAY_CONNECTIONS), 18)
        self.assertEqual(len(mappings.POSE_GEOMETRY_CONNECTIONS), 16)
        self.assertEqual(
            mappings.POSE_GEOMETRY_CONNECTIONS,
            mappings.POSE_OVERLAY_CONNECTIONS[:-2],
        )
        self.assertEqual(overlay.CONNECTIONS, list(mappings.POSE_OVERLAY_CONNECTIONS))
        self.assertEqual(
            geometry.SKELETON_CONNECTIONS,
            list(mappings.POSE_GEOMETRY_CONNECTIONS),
        )
        self.assertEqual(overlay.CORE, set(mappings.POSE_CORE_LANDMARKS))

    def test_batting_and_pitching_profiles_document_current_right_only_rules(self) -> None:
        self.assertEqual(
            mappings.RIGHT_HANDED_BATTING_PROFILE,
            {
                "batting_side": "right",
                "rear_marker_prefix": "R",
                "front_marker_prefix": "L",
            },
        )
        self.assertEqual(mappings.BATTING_POINT_ALIASES["bat_barrel"], ("Bat1",))
        self.assertEqual(
            mappings.PITCHING_ANGLE_CHANNELS,
            {
                "front_knee": ("LKneeAngles", 0),
                "front_hip": ("LHipAngles", 0),
                "rear_knee": ("RKneeAngles", 0),
                "rear_ankle": ("RAnkleAngles", 0),
                "throwing_elbow": ("RElbowAngles", 0),
                "throwing_shoulder_abduction": ("RShoulderAngles", 1),
                "throwing_shoulder_rotation": ("RShoulderAngles", 2),
                "throwing_wrist": ("RWristAngles", 0),
            },
        )
        self.assertEqual(
            mappings.RIGHT_HANDED_PITCHING_PROFILE,
            {"throwing_arm": "R", "drive_leg": "R", "lead_leg": "L"},
        )

    def test_vicon_render_mapping_hashes_match_pre_refactor_baseline(self) -> None:
        parts = {
            part: sorted(labels)
            for part, labels in reconstruction.RAW_MARKER_PARTS.items()
        }
        self.assertEqual(len(reconstruction.BODY_SEGMENTS), 44)
        self.assertEqual(
            stable_hash(reconstruction.BODY_SEGMENTS),
            "eab8d30a9804e373da8ece0888583bd1b3281e4a9c3bc557a4ce5a9b16d22f9b",
        )
        self.assertEqual(len(reconstruction.model_edges()), 83)
        self.assertEqual(
            stable_hash(reconstruction.model_edges()),
            "126ffe518786ae15322b1b86e900857a4eb8192f97574ede9d26fe76abd59bb0",
        )
        self.assertEqual(len(reconstruction.RAW_MARKERS), 39)
        self.assertEqual(
            stable_hash(sorted(reconstruction.RAW_MARKERS)),
            "e7826c15ed603ef8e3401c1c00895e9e8f706b40c1755b595fe92b61df79639e",
        )
        self.assertEqual(
            stable_hash(parts),
            "4a5f8502512b1f1aef33236b4043dac8f6858c6b2c5812bc406c1a9e8279da82",
        )


if __name__ == "__main__":
    unittest.main()
