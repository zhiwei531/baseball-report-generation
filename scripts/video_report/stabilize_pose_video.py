import argparse
import csv
import json
import math
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np


ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "input.mp4"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "stable_pose_IMG_7408"

mp_pose = mp.solutions.pose

LANDMARK_NAMES = [landmark.name.lower() for landmark in mp_pose.PoseLandmark]
BODY_JOINTS = [
    mp_pose.PoseLandmark.LEFT_SHOULDER.value,
    mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
    mp_pose.PoseLandmark.LEFT_ELBOW.value,
    mp_pose.PoseLandmark.RIGHT_ELBOW.value,
    mp_pose.PoseLandmark.LEFT_WRIST.value,
    mp_pose.PoseLandmark.RIGHT_WRIST.value,
    mp_pose.PoseLandmark.LEFT_HIP.value,
    mp_pose.PoseLandmark.RIGHT_HIP.value,
    mp_pose.PoseLandmark.LEFT_KNEE.value,
    mp_pose.PoseLandmark.RIGHT_KNEE.value,
    mp_pose.PoseLandmark.LEFT_ANKLE.value,
    mp_pose.PoseLandmark.RIGHT_ANKLE.value,
]
CORE_JOINTS = [
    mp_pose.PoseLandmark.LEFT_SHOULDER.value,
    mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
    mp_pose.PoseLandmark.LEFT_HIP.value,
    mp_pose.PoseLandmark.RIGHT_HIP.value,
]
FAST_LIMB_JOINTS = [
    mp_pose.PoseLandmark.LEFT_WRIST.value,
    mp_pose.PoseLandmark.RIGHT_WRIST.value,
    mp_pose.PoseLandmark.LEFT_ANKLE.value,
    mp_pose.PoseLandmark.RIGHT_ANKLE.value,
]
QUALITY_JOINTS = BODY_JOINTS
QUALITY_CORE_REQUIRED = [
    mp_pose.PoseLandmark.LEFT_SHOULDER.value,
    mp_pose.PoseLandmark.RIGHT_SHOULDER.value,
    mp_pose.PoseLandmark.LEFT_HIP.value,
    mp_pose.PoseLandmark.RIGHT_HIP.value,
    mp_pose.PoseLandmark.LEFT_KNEE.value,
    mp_pose.PoseLandmark.RIGHT_KNEE.value,
]
QUALITY_AUXILIARY_JOINTS = {
    mp_pose.PoseLandmark.LEFT_WRIST.value: [
        mp_pose.PoseLandmark.LEFT_PINKY.value,
        mp_pose.PoseLandmark.LEFT_INDEX.value,
        mp_pose.PoseLandmark.LEFT_THUMB.value,
    ],
    mp_pose.PoseLandmark.RIGHT_WRIST.value: [
        mp_pose.PoseLandmark.RIGHT_PINKY.value,
        mp_pose.PoseLandmark.RIGHT_INDEX.value,
        mp_pose.PoseLandmark.RIGHT_THUMB.value,
    ],
    mp_pose.PoseLandmark.LEFT_ANKLE.value: [
        mp_pose.PoseLandmark.LEFT_HEEL.value,
        mp_pose.PoseLandmark.LEFT_FOOT_INDEX.value,
    ],
    mp_pose.PoseLandmark.RIGHT_ANKLE.value: [
        mp_pose.PoseLandmark.RIGHT_HEEL.value,
        mp_pose.PoseLandmark.RIGHT_FOOT_INDEX.value,
    ],
}
QUALITY_LIMB_SEGMENTS = [
    (mp_pose.PoseLandmark.LEFT_SHOULDER.value, mp_pose.PoseLandmark.LEFT_ELBOW.value, "left_upper_arm"),
    (mp_pose.PoseLandmark.LEFT_ELBOW.value, mp_pose.PoseLandmark.LEFT_WRIST.value, "left_forearm"),
    (mp_pose.PoseLandmark.RIGHT_SHOULDER.value, mp_pose.PoseLandmark.RIGHT_ELBOW.value, "right_upper_arm"),
    (mp_pose.PoseLandmark.RIGHT_ELBOW.value, mp_pose.PoseLandmark.RIGHT_WRIST.value, "right_forearm"),
    (mp_pose.PoseLandmark.LEFT_HIP.value, mp_pose.PoseLandmark.LEFT_KNEE.value, "left_thigh"),
    (mp_pose.PoseLandmark.LEFT_KNEE.value, mp_pose.PoseLandmark.LEFT_ANKLE.value, "left_shin"),
    (mp_pose.PoseLandmark.RIGHT_HIP.value, mp_pose.PoseLandmark.RIGHT_KNEE.value, "right_thigh"),
    (mp_pose.PoseLandmark.RIGHT_KNEE.value, mp_pose.PoseLandmark.RIGHT_ANKLE.value, "right_shin"),
]
BODY_CONNECTIONS = [
    (mp_pose.PoseLandmark.LEFT_SHOULDER.value, mp_pose.PoseLandmark.RIGHT_SHOULDER.value),
    (mp_pose.PoseLandmark.LEFT_HIP.value, mp_pose.PoseLandmark.RIGHT_HIP.value),
    (mp_pose.PoseLandmark.LEFT_SHOULDER.value, mp_pose.PoseLandmark.LEFT_HIP.value),
    (mp_pose.PoseLandmark.RIGHT_SHOULDER.value, mp_pose.PoseLandmark.RIGHT_HIP.value),
    (mp_pose.PoseLandmark.LEFT_SHOULDER.value, mp_pose.PoseLandmark.LEFT_ELBOW.value),
    (mp_pose.PoseLandmark.LEFT_ELBOW.value, mp_pose.PoseLandmark.LEFT_WRIST.value),
    (mp_pose.PoseLandmark.RIGHT_SHOULDER.value, mp_pose.PoseLandmark.RIGHT_ELBOW.value),
    (mp_pose.PoseLandmark.RIGHT_ELBOW.value, mp_pose.PoseLandmark.RIGHT_WRIST.value),
    (mp_pose.PoseLandmark.LEFT_HIP.value, mp_pose.PoseLandmark.LEFT_KNEE.value),
    (mp_pose.PoseLandmark.LEFT_KNEE.value, mp_pose.PoseLandmark.LEFT_ANKLE.value),
    (mp_pose.PoseLandmark.RIGHT_HIP.value, mp_pose.PoseLandmark.RIGHT_KNEE.value),
    (mp_pose.PoseLandmark.RIGHT_KNEE.value, mp_pose.PoseLandmark.RIGHT_ANKLE.value),
]

VISIBILITY_THRESHOLD = 0.18
QUALITY_FAST_LIMB_VISIBILITY = 0.30
QUALITY_CORE_VISIBILITY = 0.46
QUALITY_OTHER_VISIBILITY = 0.40
QUALITY_AUX_VISIBILITY = 0.24
STATIC_FAST_LIMB_VISIBILITY = 0.28
STATIC_OTHER_VISIBILITY = 0.40
FUSION_FAST_LIMB_DISTANCE = 0.075
FUSION_OTHER_DISTANCE = 0.095
FUSION_VISIBILITY_MARGIN = 0.15
PERSON_CENTER_JUMP_ABS = 0.22
PERSON_CENTER_JUMP_SCALE = 0.70
PERSON_SCALE_RATIO_MIN = 0.48
PERSON_SCALE_RATIO_MAX = 1.85
BODY_JUMP_ABS = 0.24
BODY_JUMP_SCALE = 0.58
CORE_SMOOTH_SECONDS = 0.10
LIMB_SMOOTH_SECONDS = 0.065
FAST_LIMB_SMOOTH_SECONDS = 0.035
RAW_COLOR = (0, 160, 255)
STABLE_COLOR = (0, 230, 90)
JOINT_BORDER = (255, 255, 255)
QUALITY_GOOD_COLOR = (45, 220, 80)
QUALITY_WARN_COLOR = (0, 215, 255)
QUALITY_BAD_COLOR = (40, 40, 230)


def parse_args():
    parser = argparse.ArgumentParser(description="Create a temporally stabilized pose overlay video.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-frames", type=int, default=0, help="Optional limit for quick debugging.")
    parser.add_argument("--min-detection-confidence", type=float, default=0.45)
    parser.add_argument("--min-tracking-confidence", type=float, default=0.55)
    parser.add_argument("--model-complexity", type=int, default=2)
    parser.add_argument("--visibility-threshold", type=float, default=VISIBILITY_THRESHOLD)
    parser.add_argument("--quality-fast-limb-visibility", type=float, default=QUALITY_FAST_LIMB_VISIBILITY)
    parser.add_argument("--quality-core-visibility", type=float, default=QUALITY_CORE_VISIBILITY)
    parser.add_argument("--quality-other-visibility", type=float, default=QUALITY_OTHER_VISIBILITY)
    parser.add_argument("--quality-aux-visibility", type=float, default=QUALITY_AUX_VISIBILITY)
    parser.add_argument("--static-fast-limb-visibility", type=float, default=STATIC_FAST_LIMB_VISIBILITY)
    parser.add_argument("--static-other-visibility", type=float, default=STATIC_OTHER_VISIBILITY)
    parser.add_argument("--fusion-fast-limb-distance", type=float, default=FUSION_FAST_LIMB_DISTANCE)
    parser.add_argument("--fusion-other-distance", type=float, default=FUSION_OTHER_DISTANCE)
    parser.add_argument("--fusion-visibility-margin", type=float, default=FUSION_VISIBILITY_MARGIN)
    parser.add_argument("--person-center-jump-abs", type=float, default=PERSON_CENTER_JUMP_ABS)
    parser.add_argument("--person-center-jump-scale", type=float, default=PERSON_CENTER_JUMP_SCALE)
    parser.add_argument("--person-scale-ratio-min", type=float, default=PERSON_SCALE_RATIO_MIN)
    parser.add_argument("--person-scale-ratio-max", type=float, default=PERSON_SCALE_RATIO_MAX)
    parser.add_argument("--body-jump-abs", type=float, default=BODY_JUMP_ABS)
    parser.add_argument("--body-jump-scale", type=float, default=BODY_JUMP_SCALE)
    parser.add_argument("--core-smooth-seconds", type=float, default=CORE_SMOOTH_SECONDS)
    parser.add_argument("--limb-smooth-seconds", type=float, default=LIMB_SMOOTH_SECONDS)
    parser.add_argument("--fast-limb-smooth-seconds", type=float, default=FAST_LIMB_SMOOTH_SECONDS)
    return parser.parse_args()


def apply_runtime_config(args):
    global VISIBILITY_THRESHOLD
    global QUALITY_FAST_LIMB_VISIBILITY, QUALITY_CORE_VISIBILITY, QUALITY_OTHER_VISIBILITY, QUALITY_AUX_VISIBILITY
    global STATIC_FAST_LIMB_VISIBILITY, STATIC_OTHER_VISIBILITY
    global FUSION_FAST_LIMB_DISTANCE, FUSION_OTHER_DISTANCE, FUSION_VISIBILITY_MARGIN
    global PERSON_CENTER_JUMP_ABS, PERSON_CENTER_JUMP_SCALE, PERSON_SCALE_RATIO_MIN, PERSON_SCALE_RATIO_MAX
    global BODY_JUMP_ABS, BODY_JUMP_SCALE
    global CORE_SMOOTH_SECONDS, LIMB_SMOOTH_SECONDS, FAST_LIMB_SMOOTH_SECONDS

    VISIBILITY_THRESHOLD = args.visibility_threshold
    QUALITY_FAST_LIMB_VISIBILITY = args.quality_fast_limb_visibility
    QUALITY_CORE_VISIBILITY = args.quality_core_visibility
    QUALITY_OTHER_VISIBILITY = args.quality_other_visibility
    QUALITY_AUX_VISIBILITY = args.quality_aux_visibility
    STATIC_FAST_LIMB_VISIBILITY = args.static_fast_limb_visibility
    STATIC_OTHER_VISIBILITY = args.static_other_visibility
    FUSION_FAST_LIMB_DISTANCE = args.fusion_fast_limb_distance
    FUSION_OTHER_DISTANCE = args.fusion_other_distance
    FUSION_VISIBILITY_MARGIN = args.fusion_visibility_margin
    PERSON_CENTER_JUMP_ABS = args.person_center_jump_abs
    PERSON_CENTER_JUMP_SCALE = args.person_center_jump_scale
    PERSON_SCALE_RATIO_MIN = args.person_scale_ratio_min
    PERSON_SCALE_RATIO_MAX = args.person_scale_ratio_max
    BODY_JUMP_ABS = args.body_jump_abs
    BODY_JUMP_SCALE = args.body_jump_scale
    CORE_SMOOTH_SECONDS = args.core_smooth_seconds
    LIMB_SMOOTH_SECONDS = args.limb_smooth_seconds
    FAST_LIMB_SMOOTH_SECONDS = args.fast_limb_smooth_seconds


def open_video(path):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    return cap, width, height, fps, frame_count


def detect_video(input_path, args, static_image_mode, smooth_landmarks):
    cap, width, height, fps, frame_count = open_video(input_path)
    frames = []
    raw_xyz = []
    raw_visibility = []
    detected = []

    with mp_pose.Pose(
        static_image_mode=static_image_mode,
        model_complexity=args.model_complexity,
        smooth_landmarks=smooth_landmarks,
        enable_segmentation=False,
        min_detection_confidence=args.min_detection_confidence,
        min_tracking_confidence=args.min_tracking_confidence,
    ) as pose:
        frame_idx = 0
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if args.max_frames and frame_idx >= args.max_frames:
                break

            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            result = pose.process(rgb)
            xyz = np.full((33, 3), np.nan, dtype=np.float32)
            visibility = np.zeros(33, dtype=np.float32)

            if result.pose_landmarks:
                for idx, lm in enumerate(result.pose_landmarks.landmark):
                    xyz[idx] = [lm.x, lm.y, lm.z]
                    visibility[idx] = lm.visibility
                detected.append(True)
            else:
                detected.append(False)

            frames.append(frame)
            raw_xyz.append(xyz)
            raw_visibility.append(visibility)
            frame_idx += 1

    cap.release()

    if not frames:
        raise RuntimeError(f"No frames read from video: {input_path}")

    return {
        "frames": frames,
        "raw_xyz": np.stack(raw_xyz),
        "raw_visibility": np.stack(raw_visibility),
        "detected": np.array(detected, dtype=bool),
        "width": width,
        "height": height,
        "fps": fps,
        "frame_count_meta": frame_count,
    }


def person_center_and_scale(xy, visibility):
    good = [idx for idx in BODY_JOINTS if visibility[idx] >= VISIBILITY_THRESHOLD and np.isfinite(xy[idx]).all()]
    if len(good) < 6:
        return None, None
    points = xy[good]
    center = np.nanmedian(points, axis=0)
    span = np.nanmax(points, axis=0) - np.nanmin(points, axis=0)
    scale = float(np.linalg.norm(span))
    return center, max(scale, 1e-3)


def reject_bad_frames(raw_xyz, raw_visibility, detected):
    accepted = np.zeros(len(detected), dtype=bool)
    reason = ["not_detected"] * len(detected)
    centers = np.full((len(detected), 2), np.nan, dtype=np.float32)
    scales = np.full(len(detected), np.nan, dtype=np.float32)
    previous_center = None
    previous_scale = None
    previous_xy = None

    for frame_idx in range(len(detected)):
        if not detected[frame_idx]:
            continue

        xy = raw_xyz[frame_idx, :, :2]
        visibility = raw_visibility[frame_idx]
        center, scale = person_center_and_scale(xy, visibility)
        if center is None:
            reason[frame_idx] = "too_few_visible_body_joints"
            continue

        centers[frame_idx] = center
        scales[frame_idx] = scale

        if previous_center is not None:
            center_jump = float(np.linalg.norm(center - previous_center))
            scale_ratio = scale / max(previous_scale, 1e-3)
            body_jumps = np.linalg.norm(xy[BODY_JOINTS] - previous_xy[BODY_JOINTS], axis=1)
            median_body_jump = float(np.nanmedian(body_jumps))
            if center_jump > max(PERSON_CENTER_JUMP_ABS, PERSON_CENTER_JUMP_SCALE * previous_scale):
                reason[frame_idx] = "person_center_jump"
                continue
            if scale_ratio < PERSON_SCALE_RATIO_MIN or scale_ratio > PERSON_SCALE_RATIO_MAX:
                reason[frame_idx] = "person_scale_jump"
                continue
            if median_body_jump > max(BODY_JUMP_ABS, BODY_JUMP_SCALE * previous_scale):
                reason[frame_idx] = "body_landmark_jump"
                continue

        accepted[frame_idx] = True
        reason[frame_idx] = "accepted"
        previous_center = center
        previous_scale = scale
        previous_xy = xy.copy()

    return accepted, reason, centers, scales


def fuse_static_and_tracking(static_data, tracking_data):
    fused_xyz = tracking_data["raw_xyz"].copy()
    fused_visibility = tracking_data["raw_visibility"].copy()
    fused_detected = tracking_data["detected"] | static_data["detected"]
    replacements = 0

    for frame_idx in range(len(fused_xyz)):
        for landmark_idx in BODY_JOINTS:
            static_point = static_data["raw_xyz"][frame_idx, landmark_idx]
            tracking_point = tracking_data["raw_xyz"][frame_idx, landmark_idx]
            static_vis = static_data["raw_visibility"][frame_idx, landmark_idx]
            tracking_vis = tracking_data["raw_visibility"][frame_idx, landmark_idx]

            is_fast_limb = landmark_idx in FAST_LIMB_JOINTS
            min_static_visibility = STATIC_FAST_LIMB_VISIBILITY if is_fast_limb else STATIC_OTHER_VISIBILITY
            if static_vis < min_static_visibility or not np.isfinite(static_point[:2]).all():
                continue
            if not np.isfinite(tracking_point[:2]).all() or tracking_vis < VISIBILITY_THRESHOLD:
                fused_xyz[frame_idx, landmark_idx] = static_point
                fused_visibility[frame_idx, landmark_idx] = static_vis
                replacements += 1
                continue

            distance = float(np.linalg.norm(static_point[:2] - tracking_point[:2]))
            threshold = FUSION_FAST_LIMB_DISTANCE if is_fast_limb else FUSION_OTHER_DISTANCE
            if distance > threshold and static_vis >= tracking_vis - FUSION_VISIBILITY_MARGIN:
                fused_xyz[frame_idx, landmark_idx] = static_point
                fused_visibility[frame_idx, landmark_idx] = max(static_vis, tracking_vis)
                replacements += 1

    fused_data = dict(tracking_data)
    fused_data["raw_xyz"] = fused_xyz
    fused_data["raw_visibility"] = fused_visibility
    fused_data["detected"] = fused_detected
    return fused_data, replacements


def interpolate_1d(values, valid):
    x = np.arange(len(values))
    if valid.sum() == 0:
        return np.zeros_like(values, dtype=np.float32)
    if valid.sum() == 1:
        filled = np.full_like(values, values[valid][0], dtype=np.float32)
        return filled
    return np.interp(x, x[valid], values[valid]).astype(np.float32)


def fill_missing_landmarks(raw_xyz, raw_visibility, accepted):
    filled_xyz = np.empty_like(raw_xyz)
    filled_visibility = np.empty_like(raw_visibility)
    for landmark_idx in range(raw_xyz.shape[1]):
        valid = accepted & np.isfinite(raw_xyz[:, landmark_idx, 0])
        for dim in range(3):
            filled_xyz[:, landmark_idx, dim] = interpolate_1d(raw_xyz[:, landmark_idx, dim], valid)
        filled_visibility[:, landmark_idx] = interpolate_1d(raw_visibility[:, landmark_idx], valid)
    return filled_xyz, filled_visibility


def gaussian_kernel(radius, sigma):
    xs = np.arange(-radius, radius + 1, dtype=np.float32)
    kernel = np.exp(-(xs * xs) / (2.0 * sigma * sigma))
    kernel /= kernel.sum()
    return kernel


def smooth_series(values, radius, sigma):
    kernel = gaussian_kernel(radius, sigma)
    padded = np.pad(values, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid").astype(np.float32)


def stabilize_landmarks(raw_xyz, raw_visibility, accepted, fps):
    filled_xyz, filled_visibility = fill_missing_landmarks(raw_xyz, raw_visibility, accepted)
    stable_xyz = np.empty_like(filled_xyz)
    stable_visibility = np.empty_like(filled_visibility)

    core_radius = max(3, int(round(fps * CORE_SMOOTH_SECONDS)))
    limb_radius = max(2, int(round(fps * LIMB_SMOOTH_SECONDS)))
    fast_limb_radius = max(1, int(round(fps * FAST_LIMB_SMOOTH_SECONDS)))
    core_radius = min(core_radius, 6)
    limb_radius = min(limb_radius, 4)
    fast_limb_radius = min(fast_limb_radius, 2)

    for landmark_idx in range(filled_xyz.shape[1]):
        if landmark_idx in CORE_JOINTS:
            radius = core_radius
        elif landmark_idx in FAST_LIMB_JOINTS:
            radius = fast_limb_radius
        else:
            radius = limb_radius
        sigma = max(1.0, radius / 2.0)
        for dim in range(3):
            stable_xyz[:, landmark_idx, dim] = smooth_series(filled_xyz[:, landmark_idx, dim], radius, sigma)
        stable_visibility[:, landmark_idx] = smooth_series(filled_visibility[:, landmark_idx], radius, sigma)

    return stable_xyz, stable_visibility, {
        "core_smoothing_radius_frames": core_radius,
        "limb_smoothing_radius_frames": limb_radius,
        "fast_limb_smoothing_radius_frames": fast_limb_radius,
    }


def to_pixel(point, width, height):
    x = int(np.clip(point[0] * width, 0, width - 1))
    y = int(np.clip(point[1] * height, 0, height - 1))
    return x, y


def draw_pose(frame, xyz, visibility, width, height, color, label):
    overlay = frame.copy()
    for start, end in BODY_CONNECTIONS:
        if visibility[start] < VISIBILITY_THRESHOLD or visibility[end] < VISIBILITY_THRESHOLD:
            continue
        if not np.isfinite(xyz[start, :2]).all() or not np.isfinite(xyz[end, :2]).all():
            continue
        cv2.line(overlay, to_pixel(xyz[start], width, height), to_pixel(xyz[end], width, height), color, 5, cv2.LINE_AA)

    for idx in BODY_JOINTS:
        if visibility[idx] < VISIBILITY_THRESHOLD or not np.isfinite(xyz[idx, :2]).all():
            continue
        point = to_pixel(xyz[idx], width, height)
        cv2.circle(overlay, point, 8, JOINT_BORDER, -1, cv2.LINE_AA)
        cv2.circle(overlay, point, 5, color, -1, cv2.LINE_AA)

    cv2.putText(overlay, label, (18, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2, cv2.LINE_AA)
    return overlay


def person_bbox(xyz, visibility, width, height):
    good_points = []
    for idx in QUALITY_JOINTS:
        if visibility[idx] >= VISIBILITY_THRESHOLD and np.isfinite(xyz[idx, :2]).all():
            good_points.append(xyz[idx, :2])
    if len(good_points) < 4:
        return None

    points = np.array(good_points, dtype=np.float32)
    x1 = float(np.nanmin(points[:, 0]) * width)
    y1 = float(np.nanmin(points[:, 1]) * height)
    x2 = float(np.nanmax(points[:, 0]) * width)
    y2 = float(np.nanmax(points[:, 1]) * height)
    pad_x = max(18.0, (x2 - x1) * 0.18)
    pad_y = max(18.0, (y2 - y1) * 0.16)
    return (
        int(np.clip(x1 - pad_x, 0, width - 1)),
        int(np.clip(y1 - pad_y, 0, height - 1)),
        int(np.clip(x2 + pad_x, 0, width - 1)),
        int(np.clip(y2 + pad_y, 0, height - 1)),
    )


def quality_visibility_threshold(landmark_idx):
    if landmark_idx in FAST_LIMB_JOINTS:
        return QUALITY_FAST_LIMB_VISIBILITY
    if landmark_idx in CORE_JOINTS:
        return QUALITY_CORE_VISIBILITY
    return QUALITY_OTHER_VISIBILITY


def auxiliary_support_for_joint(xyz, visibility, landmark_idx):
    aux_indices = QUALITY_AUXILIARY_JOINTS.get(landmark_idx, [])
    supported = []
    for aux_idx in aux_indices:
        if visibility[aux_idx] >= QUALITY_AUX_VISIBILITY and np.isfinite(xyz[aux_idx, :2]).all():
            supported.append(LANDMARK_NAMES[aux_idx])
    return supported


def classify_frame_quality(xyz, visibility, detected, width, height):
    reasons = []
    warnings = []
    bbox = person_bbox(xyz, visibility, width, height)
    if not detected:
        return {
            "usable": False,
            "fusion_candidate": False,
            "quality_label": "red",
            "quality_score": 0.0,
            "visible_required_joints": 0,
            "assisted_required_joints": 0,
            "min_required_visibility": 0.0,
            "bbox": bbox,
            "reason": "no_pose_detected",
        }
    if bbox is None:
        return {
            "usable": False,
            "fusion_candidate": False,
            "quality_label": "red",
            "quality_score": 0.0,
            "visible_required_joints": 0,
            "assisted_required_joints": 0,
            "min_required_visibility": 0.0,
            "bbox": bbox,
            "reason": "too_few_visible_body_joints",
        }

    visible_count = 0
    assisted_count = 0
    vis_values = []
    for idx in QUALITY_JOINTS:
        name = LANDMARK_NAMES[idx]
        vis = float(visibility[idx])
        vis_values.append(vis)
        if not np.isfinite(xyz[idx, :2]).all():
            reasons.append(f"{name}_missing")
            continue
        if vis < quality_visibility_threshold(idx):
            aux_support = auxiliary_support_for_joint(xyz, visibility, idx)
            if idx in QUALITY_AUXILIARY_JOINTS and aux_support:
                warnings.append(f"{name}_low_visibility_aux_{'+'.join(aux_support)}")
                assisted_count += 1
            else:
                reasons.append(f"{name}_low_visibility")
            continue
        visible_count += 1

    center, scale = person_center_and_scale(xyz[:, :2], visibility)
    if center is None or scale is None:
        reasons.append("body_scale_unreliable")
        scale = 1.0

    for start, end, segment_name in QUALITY_LIMB_SEGMENTS:
        if visibility[start] < quality_visibility_threshold(start) or visibility[end] < quality_visibility_threshold(end):
            continue
        segment_len = float(np.linalg.norm(xyz[start, :2] - xyz[end, :2]))
        if segment_len / max(scale, 1e-3) < 0.09:
            if start in FAST_LIMB_JOINTS or end in FAST_LIMB_JOINTS:
                warnings.append(f"{segment_name}_collapsed")
            else:
                reasons.append(f"{segment_name}_collapsed")

    effective_count = visible_count + assisted_count
    core_ok = all(
        visibility[idx] >= quality_visibility_threshold(idx) and np.isfinite(xyz[idx, :2]).all()
        for idx in QUALITY_CORE_REQUIRED
    )
    usable = visible_count == len(QUALITY_JOINTS) and not reasons and not warnings
    fusion_candidate = usable or (core_ok and effective_count >= 10 and len(reasons) <= 1)
    quality_label = "green" if usable else "yellow" if fusion_candidate else "red"
    quality_score = effective_count / len(QUALITY_JOINTS)
    if quality_label == "green":
        reason = "usable_full_body_2d"
    elif quality_label == "yellow":
        reason = "fusion_candidate_" + (";".join((warnings + reasons)[:8]) or "minor_uncertainty")
    else:
        reason = ";".join(reasons[:8]) or "insufficient_full_body_quality"
    return {
        "usable": usable,
        "fusion_candidate": fusion_candidate,
        "quality_label": quality_label,
        "quality_score": round(float(quality_score), 4),
        "visible_required_joints": int(visible_count),
        "assisted_required_joints": int(assisted_count),
        "min_required_visibility": round(float(min(vis_values) if vis_values else 0.0), 4),
        "bbox": bbox,
        "temporal_status": "single_frame",
        "motion_phase": "unknown",
        "reason": reason,
    }


def classify_all_frames(data):
    quality = []
    for frame_idx in range(len(data["frames"])):
        quality.append(
            classify_frame_quality(
                data["raw_xyz"][frame_idx],
                data["raw_visibility"][frame_idx],
                bool(data["detected"][frame_idx]),
                data["width"],
                data["height"],
            )
        )
    motion_phases = estimate_motion_phases(data)
    apply_temporal_quality_rules(quality, motion_phases)
    return quality


def fill_numeric_series(values):
    values = np.asarray(values, dtype=np.float32)
    valid = np.isfinite(values)
    return interpolate_1d(values, valid)


def estimate_motion_phases(data):
    xyz = data["raw_xyz"]
    visibility = data["raw_visibility"]
    frame_count = len(data["frames"])
    wrist_center = np.full((frame_count, 2), np.nan, dtype=np.float32)
    body_scales = np.full(frame_count, np.nan, dtype=np.float32)
    left_wrist = mp_pose.PoseLandmark.LEFT_WRIST.value
    right_wrist = mp_pose.PoseLandmark.RIGHT_WRIST.value

    for idx in range(frame_count):
        wrist_points = []
        for wrist_idx in (left_wrist, right_wrist):
            if visibility[idx, wrist_idx] >= VISIBILITY_THRESHOLD and np.isfinite(xyz[idx, wrist_idx, :2]).all():
                wrist_points.append(xyz[idx, wrist_idx, :2])
        if wrist_points:
            wrist_center[idx] = np.mean(wrist_points, axis=0)
        _, scale = person_center_and_scale(xyz[idx, :, :2], visibility[idx])
        if scale:
            body_scales[idx] = scale

    wrist_center[:, 0] = fill_numeric_series(wrist_center[:, 0])
    wrist_center[:, 1] = fill_numeric_series(wrist_center[:, 1])
    body_scales = fill_numeric_series(body_scales)
    speeds = np.zeros(frame_count, dtype=np.float32)
    if frame_count > 1:
        speeds[1:] = np.linalg.norm(np.diff(wrist_center, axis=0), axis=1) / np.maximum(body_scales[1:], 1e-3)

    threshold = max(float(np.nanmedian(speeds) + np.nanstd(speeds) * 0.65), float(np.nanpercentile(speeds, 65)))
    active = speeds >= threshold
    if active.any():
        active_indices = np.where(active)[0]
        swing_start = max(0, int(active_indices[0]) - 4)
        swing_end = min(frame_count - 1, int(active_indices[-1]) + 8)
    else:
        swing_start = frame_count // 3
        swing_end = min(frame_count - 1, int(frame_count * 0.8))

    phases = []
    for idx in range(frame_count):
        if idx < swing_start:
            phases.append("pre_swing")
        elif idx <= swing_end:
            phases.append("swing_active")
        else:
            phases.append("followthrough")
    return phases


def append_reason(item, reason):
    if reason not in item["reason"]:
        item["reason"] = f"{reason};{item['reason']}"


def mark_yellow(item, temporal_status, reason):
    item["quality_label"] = "yellow"
    item["fusion_candidate"] = True
    item["temporal_status"] = temporal_status
    append_reason(item, reason)


def red_runs(frame_quality):
    runs = []
    start = None
    for idx, item in enumerate(frame_quality):
        if item["quality_label"] == "red":
            if start is None:
                start = idx
        elif start is not None:
            runs.append((start, idx - 1))
            start = None
    if start is not None:
        runs.append((start, len(frame_quality) - 1))
    return runs


def apply_temporal_quality_rules(frame_quality, motion_phases):
    for idx, item in enumerate(frame_quality):
        item["motion_phase"] = motion_phases[idx]
        if item["quality_label"] == "yellow":
            item["temporal_status"] = "single_frame_fusion_candidate"
        elif item["quality_label"] == "green":
            item["temporal_status"] = "direct_2d"

    # 1) A single questionable frame surrounded by good candidates becomes a temporal bridge.
    for idx, item in enumerate(frame_quality):
        if item["quality_label"] != "red":
            continue
        start = max(0, idx - 2)
        end = min(len(frame_quality), idx + 3)
        neighbor_candidates = sum(1 for j in range(start, end) if j != idx and frame_quality[j]["fusion_candidate"])
        if neighbor_candidates >= 3 and item["quality_score"] >= 0.75 and item["visible_required_joints"] >= 9:
            mark_yellow(item, "temporal_bridge", "fusion_candidate_temporal_bridge")

    # 2) Short red gaps of 1-2 frames between candidate frames are interpolation candidates.
    for start, end in red_runs(frame_quality):
        run_len = end - start + 1
        before_ok = start > 0 and frame_quality[start - 1]["fusion_candidate"]
        after_ok = end + 1 < len(frame_quality) and frame_quality[end + 1]["fusion_candidate"]
        if run_len <= 2 and before_ok and after_ok:
            for idx in range(start, end + 1):
                item = frame_quality[idx]
                if item["quality_score"] >= 0.66 and item["visible_required_joints"] >= 8:
                    mark_yellow(item, "short_gap_interpolated", "fusion_candidate_short_gap_interpolated")

    persistent_indices = set()
    for start, end in red_runs(frame_quality):
        if end - start + 1 >= 6:
            for idx in range(start, end + 1):
                persistent_indices.add(idx)
                frame_quality[idx]["temporal_status"] = "persistent_occlusion"
                append_reason(frame_quality[idx], "persistent_occlusion")

    # 3) During the active swing/followthrough, short arm-only uncertainty is a phase occlusion candidate.
    for idx, item in enumerate(frame_quality):
        if item["quality_label"] != "red":
            continue
        if idx in persistent_indices:
            continue
        arm_issue = any(token in item["reason"] for token in ["wrist", "elbow", "forearm", "upper_arm"])
        lower_body_ok = item["visible_required_joints"] >= 9 and item["quality_score"] >= 0.75
        if motion_phases[idx] in {"swing_active", "followthrough"} and arm_issue and lower_body_ok:
            mark_yellow(item, "swing_phase_occlusion_candidate", "fusion_candidate_swing_phase_occlusion")

    # 4) Remaining long red runs are persistent occlusion, not a one-frame failure.
    for start, end in red_runs(frame_quality):
        run_len = end - start + 1
        status = "persistent_occlusion" if run_len >= 3 else "isolated_unusable"
        for idx in range(start, end + 1):
            frame_quality[idx]["temporal_status"] = status
            append_reason(frame_quality[idx], status)


def draw_quality_box(frame, quality_item):
    overlay = frame.copy()
    bbox = quality_item["bbox"]
    quality_label = quality_item["quality_label"]
    if quality_label == "green":
        color = QUALITY_GOOD_COLOR
        label = "2D analysis OK"
    elif quality_label == "yellow":
        color = QUALITY_WARN_COLOR
        label = "fusion candidate"
    else:
        color = QUALITY_BAD_COLOR
        label = "occluded / incomplete"
    if bbox:
        x1, y1, x2, y2 = bbox
        cv2.rectangle(overlay, (x1, y1), (x2, y2), color, 4, cv2.LINE_AA)
        text_y = max(28, y1 - 10)
    else:
        text_y = 38
    cv2.putText(overlay, label, (18, text_y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)
    cv2.putText(
        overlay,
        f"score {quality_item['quality_score']:.2f}  joints {quality_item['visible_required_joints']}+{quality_item['assisted_required_joints']}/{len(QUALITY_JOINTS)}",
        (18, min(frame.shape[0] - 18, text_y + 30)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        color,
        2,
        cv2.LINE_AA,
    )
    return overlay


def video_writer(path, fps, width, height):
    suffix = path.suffix.lower()
    if suffix == ".webm":
        fourcc = cv2.VideoWriter_fourcc(*"VP80")
    elif suffix == ".avi":
        fourcc = cv2.VideoWriter_fourcc(*"MJPG")
    else:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, fps, (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output video: {path}")
    return writer


def write_videos(data, stable_xyz, stable_visibility, frame_quality, output_dir):
    frames = data["frames"]
    raw_xyz = data["raw_xyz"]
    raw_visibility = data["raw_visibility"]
    detected = data["detected"]
    width = data["width"]
    height = data["height"]
    fps = data["fps"]

    raw_path = output_dir / "IMG_7408_old_static_pose.webm"
    stable_path = output_dir / "IMG_7408_stable_pose.webm"
    quality_path = output_dir / "IMG_7408_stable_pose_quality_boxes.webm"
    compare_path = output_dir / "IMG_7408_raw_vs_stable.webm"
    raw_mp4_path = output_dir / "IMG_7408_old_static_pose.mp4"
    stable_mp4_path = output_dir / "IMG_7408_stable_pose.mp4"
    quality_mp4_path = output_dir / "IMG_7408_stable_pose_quality_boxes.mp4"
    compare_mp4_path = output_dir / "IMG_7408_raw_vs_stable.mp4"

    writers = [
        (
            video_writer(raw_path, fps, width, height),
            video_writer(stable_path, fps, width, height),
            video_writer(quality_path, fps, width, height),
            video_writer(compare_path, fps, width * 2, height),
        ),
        (
            video_writer(raw_mp4_path, fps, width, height),
            video_writer(stable_mp4_path, fps, width, height),
            video_writer(quality_mp4_path, fps, width, height),
            video_writer(compare_mp4_path, fps, width * 2, height),
        ),
    ]

    for frame_idx, frame in enumerate(frames):
        raw_label = "old static pose" if detected[frame_idx] else "old static pose: no detection"
        raw = draw_pose(frame, raw_xyz[frame_idx], raw_visibility[frame_idx], width, height, RAW_COLOR, raw_label)
        stable = draw_pose(frame, stable_xyz[frame_idx], stable_visibility[frame_idx], width, height, STABLE_COLOR, "stabilized pose")
        quality = draw_quality_box(stable, frame_quality[frame_idx])
        compare = np.hstack([raw, stable])
        for raw_writer, stable_writer, quality_writer, compare_writer in writers:
            raw_writer.write(raw)
            stable_writer.write(stable)
            quality_writer.write(quality)
            compare_writer.write(compare)

    for writer_group in writers:
        for writer in writer_group:
            writer.release()
    return raw_path, stable_path, quality_path, compare_path


def normalized_jitter(xyz, visibility, frame_mask, scales):
    values = []
    for frame_idx in range(1, len(xyz)):
        if not frame_mask[frame_idx] or not frame_mask[frame_idx - 1]:
            continue
        scale = scales[frame_idx]
        if not np.isfinite(scale) or scale <= 0:
            continue
        visible = (visibility[frame_idx, BODY_JOINTS] >= VISIBILITY_THRESHOLD) & (
            visibility[frame_idx - 1, BODY_JOINTS] >= VISIBILITY_THRESHOLD
        )
        if visible.sum() < 6:
            continue
        jumps = np.linalg.norm(
            xyz[frame_idx, BODY_JOINTS, :2][visible] - xyz[frame_idx - 1, BODY_JOINTS, :2][visible],
            axis=1,
        )
        values.append(float(np.nanmedian(jumps) / scale))
    if not values:
        return None
    return {
        "median": float(np.median(values)),
        "p90": float(np.percentile(values, 90)),
        "samples": len(values),
    }


def calculate_angle(a, b, c):
    ba = a - b
    bc = c - b
    denom = np.linalg.norm(ba) * np.linalg.norm(bc)
    if denom < 1e-6:
        return math.nan
    cos_angle = float(np.dot(ba, bc) / denom)
    cos_angle = float(np.clip(cos_angle, -1.0, 1.0))
    return math.degrees(math.acos(cos_angle))


def angle_set(xyz, width, height):
    points = xyz[:, :2].copy()
    points[:, 0] *= width
    points[:, 1] *= height
    idx = mp_pose.PoseLandmark
    return {
        "left_elbow_angle": calculate_angle(points[idx.LEFT_SHOULDER.value], points[idx.LEFT_ELBOW.value], points[idx.LEFT_WRIST.value]),
        "right_elbow_angle": calculate_angle(points[idx.RIGHT_SHOULDER.value], points[idx.RIGHT_ELBOW.value], points[idx.RIGHT_WRIST.value]),
        "left_knee_angle": calculate_angle(points[idx.LEFT_HIP.value], points[idx.LEFT_KNEE.value], points[idx.LEFT_ANKLE.value]),
        "right_knee_angle": calculate_angle(points[idx.RIGHT_HIP.value], points[idx.RIGHT_KNEE.value], points[idx.RIGHT_ANKLE.value]),
    }


def write_csv(data, accepted, reason, stable_xyz, stable_visibility, output_dir):
    path = output_dir / "IMG_7408_pose_landmarks_stabilized.csv"
    width = data["width"]
    height = data["height"]
    fps = data["fps"]

    fieldnames = [
        "frame",
        "time_sec",
        "detected",
        "accepted_for_stabilization",
        "frame_status",
        "landmark",
        "raw_x_px",
        "raw_y_px",
        "raw_visibility",
        "stable_x_px",
        "stable_y_px",
        "stable_visibility",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_idx in range(len(data["frames"])):
            for landmark_idx, landmark_name in enumerate(LANDMARK_NAMES):
                raw = data["raw_xyz"][frame_idx, landmark_idx]
                stable = stable_xyz[frame_idx, landmark_idx]
                writer.writerow(
                    {
                        "frame": frame_idx,
                        "time_sec": round(frame_idx / fps, 4),
                        "detected": int(data["detected"][frame_idx]),
                        "accepted_for_stabilization": int(accepted[frame_idx]),
                        "frame_status": reason[frame_idx],
                        "landmark": landmark_name,
                        "raw_x_px": "" if not np.isfinite(raw[0]) else round(float(raw[0] * width), 2),
                        "raw_y_px": "" if not np.isfinite(raw[1]) else round(float(raw[1] * height), 2),
                        "raw_visibility": round(float(data["raw_visibility"][frame_idx, landmark_idx]), 4),
                        "stable_x_px": round(float(stable[0] * width), 2),
                        "stable_y_px": round(float(stable[1] * height), 2),
                        "stable_visibility": round(float(stable_visibility[frame_idx, landmark_idx]), 4),
                    }
                )
    return path


def write_frame_quality_csv(data, frame_quality, output_dir):
    path = output_dir / "IMG_7408_frame_quality.csv"
    fieldnames = [
        "frame",
        "time_sec",
        "quality_label",
        "usable_for_2d_analysis",
        "usable_for_2d_3d_fusion",
        "needs_vicon_completion",
        "temporal_status",
        "motion_phase",
        "quality_score",
        "visible_required_joints",
        "assisted_required_joints",
        "required_joint_count",
        "min_required_visibility",
        "bbox_x1",
        "bbox_y1",
        "bbox_x2",
        "bbox_y2",
        "quality_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_idx, item in enumerate(frame_quality):
            bbox = item["bbox"] or ("", "", "", "")
            writer.writerow(
                {
                    "frame": frame_idx,
                    "time_sec": round(frame_idx / data["fps"], 4),
                    "quality_label": item["quality_label"],
                    "usable_for_2d_analysis": int(item["usable"]),
                    "usable_for_2d_3d_fusion": int(item["fusion_candidate"]),
                    "needs_vicon_completion": int(item["quality_label"] == "yellow"),
                    "temporal_status": item["temporal_status"],
                    "motion_phase": item["motion_phase"],
                    "quality_score": item["quality_score"],
                    "visible_required_joints": item["visible_required_joints"],
                    "assisted_required_joints": item["assisted_required_joints"],
                    "required_joint_count": len(QUALITY_JOINTS),
                    "min_required_visibility": item["min_required_visibility"],
                    "bbox_x1": bbox[0],
                    "bbox_y1": bbox[1],
                    "bbox_x2": bbox[2],
                    "bbox_y2": bbox[3],
                    "quality_reason": item["reason"],
                }
            )
    return path


def write_angle_csv(data, stable_xyz, output_dir):
    path = output_dir / "IMG_7408_stable_angles.csv"
    with path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = ["frame", "time_sec", "left_elbow_angle", "right_elbow_angle", "left_knee_angle", "right_knee_angle"]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_idx in range(len(data["frames"])):
            row = {
                "frame": frame_idx,
                "time_sec": round(frame_idx / data["fps"], 4),
            }
            for key, value in angle_set(stable_xyz[frame_idx], data["width"], data["height"]).items():
                row[key] = "" if not np.isfinite(value) else round(value, 2)
            writer.writerow(row)
    return path


def write_contact_sheet(data, stable_xyz, stable_visibility, output_dir):
    frames = data["frames"]
    width = data["width"]
    height = data["height"]
    sample_count = min(8, len(frames))
    indices = np.linspace(0, len(frames) - 1, sample_count, dtype=int)
    thumbs = []
    for idx in indices:
        raw = draw_pose(frames[idx], data["raw_xyz"][idx], data["raw_visibility"][idx], width, height, RAW_COLOR, "raw")
        stable = draw_pose(frames[idx], stable_xyz[idx], stable_visibility[idx], width, height, STABLE_COLOR, "stable")
        pair = np.hstack([raw, stable])
        thumb_width = 520
        thumb_height = int(pair.shape[0] * (thumb_width / pair.shape[1]))
        thumb = cv2.resize(pair, (thumb_width, thumb_height), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, f"frame {idx}", (12, thumb_height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
        thumbs.append(thumb)

    cols = 2
    rows = int(math.ceil(len(thumbs) / cols))
    pad = 12
    cell_h = max(t.shape[0] for t in thumbs)
    sheet = np.full((rows * cell_h + (rows + 1) * pad, cols * 520 + (cols + 1) * pad, 3), 245, dtype=np.uint8)
    for i, thumb in enumerate(thumbs):
        row = i // cols
        col = i % cols
        y = pad + row * (cell_h + pad)
        x = pad + col * (520 + pad)
        sheet[y : y + thumb.shape[0], x : x + thumb.shape[1]] = thumb
    path = output_dir / "IMG_7408_raw_vs_stable_contact_sheet.jpg"
    ok, encoded = cv2.imencode(".jpg", sheet)
    if not ok:
        raise RuntimeError(f"Cannot encode contact sheet: {path}")
    path.write_bytes(encoded.tobytes())
    return path


def write_quality_contact_sheet(data, stable_xyz, stable_visibility, frame_quality, output_dir):
    frames = data["frames"]
    width = data["width"]
    height = data["height"]
    sample_count = min(10, len(frames))
    green_indices = [idx for idx, item in enumerate(frame_quality) if item["quality_label"] == "green"]
    yellow_indices = [idx for idx, item in enumerate(frame_quality) if item["quality_label"] == "yellow"]
    red_indices = [idx for idx, item in enumerate(frame_quality) if item["quality_label"] == "red"]
    green_sample = list(np.linspace(0, len(green_indices) - 1, min(3, len(green_indices)), dtype=int)) if green_indices else []
    yellow_sample = list(np.linspace(0, len(yellow_indices) - 1, min(4, len(yellow_indices)), dtype=int)) if yellow_indices else []
    red_sample = list(np.linspace(0, len(red_indices) - 1, min(3, len(red_indices)), dtype=int)) if red_indices else []
    selected = [green_indices[i] for i in green_sample] + [yellow_indices[i] for i in yellow_sample] + [red_indices[i] for i in red_sample]
    selected = selected[:sample_count]
    if len(selected) < sample_count:
        selected = list(np.linspace(0, len(frames) - 1, sample_count, dtype=int))

    thumbs = []
    for idx in selected:
        stable = draw_pose(frames[idx], stable_xyz[idx], stable_visibility[idx], width, height, STABLE_COLOR, "stable")
        quality = draw_quality_box(stable, frame_quality[idx])
        thumb_width = 320
        thumb_height = int(quality.shape[0] * (thumb_width / quality.shape[1]))
        thumb = cv2.resize(quality, (thumb_width, thumb_height), interpolation=cv2.INTER_AREA)
        cv2.putText(thumb, f"frame {idx}", (10, thumb_height - 12), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (255, 255, 255), 2, cv2.LINE_AA)
        thumbs.append(thumb)

    cols = 5
    rows = int(math.ceil(len(thumbs) / cols))
    pad = 10
    cell_h = max(t.shape[0] for t in thumbs)
    sheet = np.full((rows * cell_h + (rows + 1) * pad, cols * 320 + (cols + 1) * pad, 3), 245, dtype=np.uint8)
    for i, thumb in enumerate(thumbs):
        row = i // cols
        col = i % cols
        y = pad + row * (cell_h + pad)
        x = pad + col * (320 + pad)
        sheet[y : y + thumb.shape[0], x : x + thumb.shape[1]] = thumb
    path = output_dir / "IMG_7408_quality_boxes_contact_sheet.jpg"
    ok, encoded = cv2.imencode(".jpg", sheet)
    if not ok:
        raise RuntimeError(f"Cannot encode quality contact sheet: {path}")
    path.write_bytes(encoded.tobytes())
    return path


def write_report(input_path, data, accepted, reason, metrics, outputs, output_dir):
    rejected_counts = {}
    for item in reason:
        rejected_counts[item] = rejected_counts.get(item, 0) + 1

    report_path = output_dir / "README_stabilization_notes.md"
    raw_jitter = metrics["raw_jitter"]
    tracking_jitter = metrics["tracking_jitter"]
    stable_jitter = metrics["stable_jitter"]
    reduction = metrics["median_jitter_reduction_percent"]

    text = f"""# IMG_7408 稳定骨架视频说明

## 这次改了什么

1. 旧方法主要适合静态图片：`static_image_mode=True` 会把每一帧当作一张互不相关的照片。这样单帧看可能还行，但视频连起来时，模型每帧都可能重新猜一次身体位置，所以骨架容易跳。这次我专门输出了一个 `old_static_pose` 视频作为旧方法基线。
2. 新方法改成视频追踪：`static_image_mode=False`，并打开 MediaPipe 自带的 `smooth_landmarks=True`。这一步会让模型参考前后帧，而不是每帧从零开始。
3. 新方法提高了门槛：`min_detection_confidence={metrics["min_detection_confidence"]}`，`min_tracking_confidence={metrics["min_tracking_confidence"]}`。意思是模型不够确定时，不急着相信那一帧。
4. 新增异常帧剔除：如果整个人的中心点突然跳太远、人体大小突然变化很大、或身体关键点整体跳动不合理，就不把这一帧作为稳定骨架的依据。
5. 新增追踪/静态融合：追踪结果负责连续性；但如果手腕、脚踝等快速肢体点被 tracker 跟丢，而静态检测置信度高，就用静态检测纠正这一帧，避免“为了稳定而画错”。
6. 新增补洞：某一帧没检测到，或被判为异常帧时，不直接让骨架消失，而是用前后可信帧做线性补点。
7. 新增时间平滑：可信坐标补齐后，再用小窗口高斯平滑。肩膀/髋部这些身体核心点平滑更强，手腕/脚踝平滑稍弱，避免把挥棒、投球这类快速动作抹平。
8. 新增完整时间连续性规则：不再只按单帧判死刑。1-2 帧短缺口会标为 `short_gap_interpolated`，前后帧稳定的单帧问题会标为 `temporal_bridge`，挥棒/随挥阶段的手臂遮挡会标为 `swing_phase_occlusion_candidate`，连续多帧仍不可靠才标为 `persistent_occlusion`。

## 为什么这样会更稳

骨架跳动通常不是因为孩子真的突然移动了很多，而是因为模型在某一帧把关节点猜错了。稳定化做的事情可以理解成：先让模型连续追踪同一个人，再把明显不合理的“突然跳点”去掉，最后用前后帧把动作连起来。

## 本次素材信息

- 输入视频：`{input_path}`
- 分辨率：{data["width"]} x {data["height"]}
- FPS：{data["fps"]:.3f}
- 实际处理帧数：{len(data["frames"])}
- 旧静态方法检测成功帧：{int(data["detected"].sum())}/{len(data["frames"])}
- 新视频追踪方法检测成功帧：{metrics["tracking_detected_frames"]}/{len(data["frames"])}
- 被稳定流程接受的可信帧：{int(accepted.sum())}/{len(data["frames"])}
- 追踪/静态融合修正点数：{metrics["fusion_replacements"]}
- 绿色帧，完整 2D 可直接分析：{metrics["green_2d_direct_frames"]}/{len(data["frames"])}
- 黄色帧，轻微遮挡但可进入 2D+Vicon/3D 融合候选：{metrics["yellow_2d_3d_fusion_candidate_frames"]}/{len(data["frames"])}
- 红色帧，严重遮挡或结构不可靠：{metrics["red_unusable_frames"]}/{len(data["frames"])}
- 绿色+黄色可进入后续分析的候选帧：{metrics["fusion_candidate_frames"]}/{len(data["frames"])}
- 时间桥接帧：{metrics["temporal_bridge_frames"]}
- 短缺口插值候选帧：{metrics["short_gap_interpolated_frames"]}
- 挥棒阶段遮挡候选帧：{metrics["swing_phase_occlusion_candidate_frames"]}
- 持续遮挡红色帧：{metrics["persistent_occlusion_frames"]}

## 三色质量判定

绿色框不是指“检测到了人”，而是指这一帧更适合做完整 2D 动作分析：肩、肘、腕、髋、膝、踝这 12 个分析关键点都要达到可见性门槛，并且上下臂、前臂、大腿、小腿不能明显塌到一起。

黄色框表示这一帧不适合当作纯 2D 真值，但可以保留给后续 2D+Vicon/3D 融合：例如手腕短暂低置信、前臂在 2D 里缩短、或某个远端点需要通过手指/脚跟/脚尖等 33 点辅助证据判断。

红色框表示这一帧虽然可能仍然检测到了人体，但四肢关键点不够完整，常见原因包括手腕被球棒或身体遮挡、侧身导致一侧手臂不可见、脚踝靠近画面边缘、或某段核心肢体长度异常变短。红色帧可以保留做展示，但不建议直接拿去做精细角度分析。

## 稳定性指标

这里的“抖动”是按相邻帧身体关键点移动量估算的，并且除以人体大小，方便不同画面大小比较。数字越小，骨架越稳。

- 旧静态骨架 median jitter：{raw_jitter["median"] if raw_jitter else "N/A"}
- 视频追踪骨架 median jitter：{tracking_jitter["median"] if tracking_jitter else "N/A"}
- 融合后、平滑前 median jitter：{metrics["fused_jitter"]["median"] if metrics["fused_jitter"] else "N/A"}
- 稳定骨架 median jitter：{stable_jitter["median"] if stable_jitter else "N/A"}
- 中位抖动下降：{reduction if reduction is not None else "N/A"}%

## 输出文件

- 旧静态方法骨架视频：`{outputs["raw_video"]}`
- 稳定骨架视频：`{outputs["stable_video"]}`
- 三色质量判断视频：`{outputs["quality_boxes_video"]}`
- 左右对比视频：`{outputs["comparison_video"]}`
- 对比抽帧图：`{outputs["contact_sheet"]}`
- 三色质量抽帧图：`{outputs["quality_contact_sheet"]}`
- 每帧关键点 CSV：`{outputs["landmark_csv"]}`
- 每帧质量 CSV：`{outputs["frame_quality_csv"]}`
- 稳定后角度 CSV：`{outputs["angle_csv"]}`
- 统计 JSON：`{outputs["summary_json"]}`

## 还需要注意

这不是重新训练一个新模型，而是把 Week1 的检测流程改成更适合视频的版本。它更稳定，但会带来一个取舍：如果平滑太强，动作会显得稍微“慢一点”；如果平滑太弱，骨架会更跟手但更容易抖。当前参数偏向儿童单人、全身、大占比画面，是为你这段新素材调的。
"""
    report_path.write_text(text, encoding="utf-8")
    return report_path, rejected_counts


def main():
    args = parse_args()
    apply_runtime_config(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    baseline_data = detect_video(args.input, args, static_image_mode=True, smooth_landmarks=False)
    tracking_data = detect_video(args.input, args, static_image_mode=False, smooth_landmarks=True)
    data, fusion_replacements = fuse_static_and_tracking(baseline_data, tracking_data)
    accepted, reason, centers, scales = reject_bad_frames(data["raw_xyz"], data["raw_visibility"], data["detected"])
    stable_xyz, stable_visibility, smoothing = stabilize_landmarks(data["raw_xyz"], data["raw_visibility"], accepted, data["fps"])
    frame_quality = classify_all_frames(data)

    output_data = dict(data)
    output_data["raw_xyz"] = baseline_data["raw_xyz"]
    output_data["raw_visibility"] = baseline_data["raw_visibility"]
    output_data["detected"] = baseline_data["detected"]

    raw_path, stable_path, quality_path, compare_path = write_videos(output_data, stable_xyz, stable_visibility, frame_quality, args.output_dir)
    landmark_csv = write_csv(output_data, accepted, reason, stable_xyz, stable_visibility, args.output_dir)
    quality_csv = write_frame_quality_csv(data, frame_quality, args.output_dir)
    angle_csv = write_angle_csv(data, stable_xyz, args.output_dir)
    contact_sheet = write_contact_sheet(output_data, stable_xyz, stable_visibility, args.output_dir)
    quality_contact_sheet = write_quality_contact_sheet(output_data, stable_xyz, stable_visibility, frame_quality, args.output_dir)

    accepted_scales = scales.copy()
    if np.isfinite(accepted_scales).sum() == 0:
        accepted_scales[:] = 1.0
    else:
        fill_valid = np.isfinite(accepted_scales)
        accepted_scales = interpolate_1d(accepted_scales, fill_valid)

    raw_jitter = normalized_jitter(baseline_data["raw_xyz"], baseline_data["raw_visibility"], baseline_data["detected"], accepted_scales)
    tracking_jitter = normalized_jitter(tracking_data["raw_xyz"], tracking_data["raw_visibility"], tracking_data["detected"], accepted_scales)
    fused_jitter = normalized_jitter(data["raw_xyz"], data["raw_visibility"], data["detected"], accepted_scales)
    stable_jitter = normalized_jitter(
        stable_xyz,
        stable_visibility,
        np.ones(len(data["frames"]), dtype=bool),
        accepted_scales,
    )
    reduction = None
    if raw_jitter and stable_jitter and raw_jitter["median"] > 0:
        reduction = round((1.0 - stable_jitter["median"] / raw_jitter["median"]) * 100.0, 1)

    summary_json = args.output_dir / "IMG_7408_stabilization_summary.json"
    metrics = {
        "input_video": str(args.input),
        "width": data["width"],
        "height": data["height"],
        "fps": data["fps"],
        "processed_frames": len(data["frames"]),
        "detected_frames": int(baseline_data["detected"].sum()),
        "tracking_detected_frames": int(tracking_data["detected"].sum()),
        "accepted_frames": int(accepted.sum()),
        "green_2d_direct_frames": int(sum(1 for item in frame_quality if item["quality_label"] == "green")),
        "yellow_2d_3d_fusion_candidate_frames": int(sum(1 for item in frame_quality if item["quality_label"] == "yellow")),
        "red_unusable_frames": int(sum(1 for item in frame_quality if item["quality_label"] == "red")),
        "usable_full_body_frames": int(sum(1 for item in frame_quality if item["quality_label"] == "green")),
        "fusion_candidate_frames": int(sum(1 for item in frame_quality if item["fusion_candidate"])),
        "occluded_or_incomplete_frames": int(sum(1 for item in frame_quality if item["quality_label"] == "red")),
        "usable_full_body_rate": round(float(sum(1 for item in frame_quality if item["quality_label"] == "green") / len(frame_quality)), 4),
        "fusion_candidate_rate": round(float(sum(1 for item in frame_quality if item["fusion_candidate"]) / len(frame_quality)), 4),
        "temporal_bridge_frames": int(sum(1 for item in frame_quality if item["temporal_status"] == "temporal_bridge")),
        "short_gap_interpolated_frames": int(sum(1 for item in frame_quality if item["temporal_status"] == "short_gap_interpolated")),
        "swing_phase_occlusion_candidate_frames": int(sum(1 for item in frame_quality if item["temporal_status"] == "swing_phase_occlusion_candidate")),
        "persistent_occlusion_frames": int(sum(1 for item in frame_quality if item["temporal_status"] == "persistent_occlusion")),
        "fusion_replacements": int(fusion_replacements),
        "min_detection_confidence": args.min_detection_confidence,
        "min_tracking_confidence": args.min_tracking_confidence,
        "model_complexity": args.model_complexity,
        "raw_jitter": raw_jitter,
        "tracking_jitter": tracking_jitter,
        "fused_jitter": fused_jitter,
        "stable_jitter": stable_jitter,
        "median_jitter_reduction_percent": reduction,
        **smoothing,
    }
    outputs = {
        "raw_video": str(raw_path),
        "stable_video": str(stable_path),
        "quality_boxes_video": str(quality_path),
        "comparison_video": str(compare_path),
        "landmark_csv": str(landmark_csv),
        "frame_quality_csv": str(quality_csv),
        "angle_csv": str(angle_csv),
        "contact_sheet": str(contact_sheet),
        "quality_contact_sheet": str(quality_contact_sheet),
        "summary_json": str(summary_json),
    }
    report_path, rejected_counts = write_report(args.input, output_data, accepted, reason, metrics, outputs, args.output_dir)
    metrics["frame_status_counts"] = rejected_counts
    metrics["outputs"] = outputs | {"report": str(report_path)}
    summary_json.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(metrics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
