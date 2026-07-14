from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any

import cv2
import numpy as np

import advanced_pose3d_backend
import stabilize_pose_video as pose


LM = pose.mp_pose.PoseLandmark
CONNECTIONS = pose.BODY_CONNECTIONS
MIN_VISIBILITY = 0.18


def write_pose3d_assets(
    output_dir: Path,
    data: dict[str, Any],
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    events: dict[str, int],
    video_path: Path | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    advanced = advanced_pose3d_backend.load_advanced_pose3d(
        video_path,
        output_dir,
        pose.LANDMARK_NAMES,
        expected_frames=len(stable_xyz),
    )
    if advanced:
        coords = kinematic_temporal_filter(advanced.coords, advanced.visibility)
        render_visibility = advanced.visibility
        method = f"{advanced.backend}_world_grounded"
        status = "advanced_world_grounded_3d"
        source_path = str(advanced.source_path)
    else:
        coords = relative_pose3d(stable_xyz, stable_visibility, data["width"], data["height"])
        render_visibility = stable_visibility
        method = "mediapipe_relative_depth_from_stabilized_2d"
        status = "estimated_relative_3d"
        source_path = ""
    csv_path = output_dir / "pose3d_relative_landmarks.csv"
    video_path = output_dir / "pose3d_relative_skeleton.mp4"
    gif_path = output_dir / "pose3d_animation.gif"
    sheet_path = output_dir / "pose3d_event_contact_sheet.jpg"
    write_pose3d_csv(csv_path, coords, render_visibility, data["fps"], method)
    render_pose3d_video(video_path, coords, render_visibility, data["fps"])
    has_gif = render_pose3d_animation(gif_path, coords, render_visibility, data["fps"])
    render_pose3d_contact_sheet(sheet_path, coords, render_visibility, events)
    trend_assets = write_motion_trend_charts(output_dir, data, stable_xyz, stable_visibility)
    return {
        "pose3d_csv": str(csv_path),
        "pose3d_video": str(video_path),
        "pose3d_animation": str(gif_path) if has_gif else "",
        "pose3d_contact_sheet": str(sheet_path),
        "pose3d_method": method,
        "pose3d_status": status,
        "pose3d_source": source_path,
        **trend_assets,
    }


def write_motion_trend_charts(
    output_dir: Path,
    data: dict[str, Any],
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
) -> dict[str, str]:
    fps = float(data["fps"] or 30.0)
    width = int(data["width"])
    height = int(data["height"])
    times = np.arange(len(stable_xyz), dtype=np.float32) / fps
    angle_series = {
        "left elbow": joint_angle_series(stable_xyz, LM.LEFT_SHOULDER.value, LM.LEFT_ELBOW.value, LM.LEFT_WRIST.value, width, height),
        "right elbow": joint_angle_series(stable_xyz, LM.RIGHT_SHOULDER.value, LM.RIGHT_ELBOW.value, LM.RIGHT_WRIST.value, width, height),
        "left knee": joint_angle_series(stable_xyz, LM.LEFT_HIP.value, LM.LEFT_KNEE.value, LM.LEFT_ANKLE.value, width, height),
        "right knee": joint_angle_series(stable_xyz, LM.RIGHT_HIP.value, LM.RIGHT_KNEE.value, LM.RIGHT_ANKLE.value, width, height),
    }
    speed_series = {
        "hands": speed_series_for(stable_xyz, stable_visibility, [LM.LEFT_WRIST.value, LM.RIGHT_WRIST.value], width, height, fps),
        "pelvis": speed_series_for(stable_xyz, stable_visibility, [LM.LEFT_HIP.value, LM.RIGHT_HIP.value], width, height, fps),
        "head": speed_series_for(stable_xyz, stable_visibility, [LM.NOSE.value, LM.LEFT_EAR.value, LM.RIGHT_EAR.value], width, height, fps),
    }
    stability_series = {
        "head drift": displacement_series_for(stable_xyz, stable_visibility, [LM.NOSE.value, LM.LEFT_EAR.value, LM.RIGHT_EAR.value], width, height),
        "pelvis shift": displacement_series_for(stable_xyz, stable_visibility, [LM.LEFT_HIP.value, LM.RIGHT_HIP.value], width, height),
    }

    trend_path = output_dir / "motion_trend_charts.jpg"
    render_trend_sheet(
        trend_path,
        [
            ("Joint angles over time", "degrees", times, angle_series, (40, 180)),
            ("Relative motion speed", "body-scale / s", times, speed_series, None),
            ("Body stability and transfer", "body-scale distance", times, stability_series, None),
        ],
    )
    return {"motion_trend_chart": str(trend_path)}


def joint_angle_series(stable_xyz: np.ndarray, a: int, b: int, c: int, width: int, height: int) -> np.ndarray:
    out = np.full(len(stable_xyz), np.nan, dtype=np.float32)
    for frame_idx, frame in enumerate(stable_xyz):
        points = frame[:, :2].copy()
        points[:, 0] *= width
        points[:, 1] *= height
        out[frame_idx] = pose.calculate_angle(points[a], points[b], points[c])
    return fill_series(out)


def point_series_for(
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    indices: list[int],
    width: int,
    height: int,
) -> np.ndarray:
    out = np.full((len(stable_xyz), 2), np.nan, dtype=np.float32)
    for frame_idx, frame in enumerate(stable_xyz):
        pts = []
        for idx in indices:
            if stable_visibility[frame_idx, idx] >= MIN_VISIBILITY and np.isfinite(frame[idx, :2]).all():
                pts.append([frame[idx, 0] * width, frame[idx, 1] * height])
        if pts:
            out[frame_idx] = np.mean(np.asarray(pts, dtype=np.float32), axis=0)
    for dim in range(2):
        out[:, dim] = fill_series(out[:, dim])
    return out


def body_scale_series(stable_xyz: np.ndarray, stable_visibility: np.ndarray, width: int, height: int) -> np.ndarray:
    values = np.full(len(stable_xyz), np.nan, dtype=np.float32)
    for frame_idx, frame in enumerate(stable_xyz):
        values[frame_idx] = body_scale_px(frame, stable_visibility[frame_idx], width, height)
    return np.maximum(fill_series(values), 1e-3)


def speed_series_for(
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    indices: list[int],
    width: int,
    height: int,
    fps: float,
) -> np.ndarray:
    points = point_series_for(stable_xyz, stable_visibility, indices, width, height)
    scales = body_scale_series(stable_xyz, stable_visibility, width, height)
    out = np.zeros(len(points), dtype=np.float32)
    if len(points) > 1:
        out[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1) / scales[1:] * fps
    return smooth_line(out)


def displacement_series_for(
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    indices: list[int],
    width: int,
    height: int,
) -> np.ndarray:
    points = point_series_for(stable_xyz, stable_visibility, indices, width, height)
    scales = body_scale_series(stable_xyz, stable_visibility, width, height)
    origin = points[0].copy()
    return smooth_line(np.linalg.norm(points - origin, axis=1) / scales)


def fill_series(values: np.ndarray) -> np.ndarray:
    filled = values.astype(np.float32).copy()
    valid = np.isfinite(filled)
    if valid.sum() == 0:
        filled[:] = 0.0
    elif valid.sum() == 1:
        filled[:] = filled[valid][0]
    else:
        filled[:] = np.interp(np.arange(len(filled)), np.where(valid)[0], filled[valid])
    return filled


def smooth_line(values: np.ndarray) -> np.ndarray:
    values = fill_series(values)
    if len(values) < 5:
        return values
    kernel = np.array([0.12, 0.22, 0.32, 0.22, 0.12], dtype=np.float32)
    return np.convolve(np.pad(values, (2, 2), mode="edge"), kernel, mode="valid").astype(np.float32)


def render_trend_sheet(path: Path, panels: list[tuple[str, str, np.ndarray, dict[str, np.ndarray], tuple[float, float] | None]]) -> None:
    panel_w = 1100
    panel_h = 320
    sheet = np.full((panel_h * len(panels), panel_w, 3), 248, dtype=np.uint8)
    colors = [(246, 115, 43), (79, 94, 234), (47, 143, 78), (233, 67, 58)]
    for index, panel in enumerate(panels):
        y0 = index * panel_h
        render_panel(sheet[y0 : y0 + panel_h], panel, colors)
    ok, encoded = cv2.imencode(".jpg", sheet)
    if not ok:
        raise RuntimeError(f"Cannot encode motion trend chart: {path}")
    path.write_bytes(encoded.tobytes())


def render_panel(
    canvas: np.ndarray,
    panel: tuple[str, str, np.ndarray, dict[str, np.ndarray], tuple[float, float] | None],
    colors: list[tuple[int, int, int]],
) -> None:
    title, unit, times, series_map, fixed_range = panel
    h, w = canvas.shape[:2]
    left, right, top, bottom = 86, w - 36, 52, h - 54
    cv2.rectangle(canvas, (0, 0), (w - 1, h - 1), (218, 226, 236), 1)
    cv2.putText(canvas, title, (28, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.72, (7, 17, 31), 2, cv2.LINE_AA)
    cv2.putText(canvas, unit, (w - 210, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (82, 97, 116), 1, cv2.LINE_AA)
    cv2.line(canvas, (left, bottom), (right, bottom), (180, 192, 208), 1, cv2.LINE_AA)
    cv2.line(canvas, (left, top), (left, bottom), (180, 192, 208), 1, cv2.LINE_AA)
    for i in range(1, 5):
        y = top + (bottom - top) * i // 5
        cv2.line(canvas, (left, y), (right, y), (228, 234, 242), 1, cv2.LINE_AA)

    values = [v for series in series_map.values() for v in series if np.isfinite(v)]
    if fixed_range:
        y_min, y_max = fixed_range
    elif values:
        y_min = float(np.nanpercentile(values, 5))
        y_max = float(np.nanpercentile(values, 95))
        if abs(y_max - y_min) < 1e-6:
            y_max = y_min + 1.0
    else:
        y_min, y_max = 0.0, 1.0
    x_min = float(times[0]) if len(times) else 0.0
    x_max = float(times[-1]) if len(times) else 1.0
    x_span = max(x_max - x_min, 1e-6)
    y_span = max(y_max - y_min, 1e-6)

    for idx, (label, values) in enumerate(series_map.items()):
        color = colors[idx % len(colors)]
        pts = []
        for t, value in zip(times, values):
            x = int(left + (float(t) - x_min) / x_span * (right - left))
            y = int(bottom - (float(np.clip(value, y_min, y_max)) - y_min) / y_span * (bottom - top))
            pts.append((x, y))
        if len(pts) >= 2:
            cv2.polylines(canvas, [np.asarray(pts, dtype=np.int32)], False, color, 2, cv2.LINE_AA)
        legend_x = left + idx * 190
        cv2.line(canvas, (legend_x, h - 22), (legend_x + 26, h - 22), color, 3, cv2.LINE_AA)
        cv2.putText(canvas, label, (legend_x + 34, h - 17), cv2.FONT_HERSHEY_SIMPLEX, 0.46, (52, 65, 86), 1, cv2.LINE_AA)

    cv2.putText(canvas, f"{x_min:.1f}s", (left, bottom + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (82, 97, 116), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"{x_max:.1f}s", (right - 52, bottom + 26), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (82, 97, 116), 1, cv2.LINE_AA)


def relative_pose3d(
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    coords = np.full_like(stable_xyz, np.nan, dtype=np.float32)
    for frame_idx in range(len(stable_xyz)):
        frame = stable_xyz[frame_idx]
        visibility = stable_visibility[frame_idx]
        root = mean_landmarks(frame, visibility, [LM.LEFT_HIP.value, LM.RIGHT_HIP.value])
        if root is None:
            root = mean_landmarks(frame, visibility, pose.CORE_JOINTS)
        if root is None:
            root = np.nanmean(frame[:, :3], axis=0)
        scale = body_scale_px(frame, visibility, width, height)
        scale = max(scale, 1e-3)

        coords[frame_idx, :, 0] = (frame[:, 0] * width - root[0] * width) / scale
        coords[frame_idx, :, 1] = -(frame[:, 1] * height - root[1] * height) / scale
        coords[frame_idx, :, 2] = -(frame[:, 2] - root[2]) * width / scale

    coords = stabilize_depth(coords, stable_visibility)
    coords = anthropomorphic_pose_lift(coords, stable_visibility)
    coords = kinematic_temporal_filter(coords, stable_visibility)
    trajectory = estimate_global_body_trajectory(stable_xyz, stable_visibility, width, height)
    return coords + trajectory[:, None, :]


def estimate_global_body_trajectory(
    stable_xyz: np.ndarray,
    stable_visibility: np.ndarray,
    width: int,
    height: int,
) -> np.ndarray:
    roots = np.full((len(stable_xyz), 3), np.nan, dtype=np.float32)
    scales = np.full(len(stable_xyz), np.nan, dtype=np.float32)
    for frame_idx, frame in enumerate(stable_xyz):
        visibility = stable_visibility[frame_idx]
        root = mean_landmarks(frame, visibility, [LM.LEFT_HIP.value, LM.RIGHT_HIP.value])
        if root is None:
            root = mean_landmarks(frame, visibility, pose.CORE_JOINTS)
        if root is None:
            continue
        roots[frame_idx] = [root[0] * width, root[1] * height, root[2] * width]
        scales[frame_idx] = body_scale_px(frame, visibility, width, height)

    valid_scale = scales[np.isfinite(scales) & (scales > 1e-3)]
    scale = float(np.nanmedian(valid_scale)) if len(valid_scale) else float(max(width, height))
    scale = max(scale, 1e-3)

    for dim in range(3):
        values = roots[:, dim]
        finite = np.isfinite(values)
        if finite.sum() == 0:
            values[:] = 0.0
        elif finite.sum() == 1:
            values[:] = values[finite][0]
        else:
            values[:] = np.interp(np.arange(len(values)), np.where(finite)[0], values[finite])
        roots[:, dim] = values

    origin = roots[0].copy()
    raw = np.zeros((len(stable_xyz), 3), dtype=np.float32)
    raw[:, 0] = (roots[:, 0] - origin[0]) / scale * 1.05
    raw[:, 1] = -(roots[:, 1] - origin[1]) / scale * 0.42
    raw[:, 2] = -(roots[:, 2] - origin[2]) / scale * 0.36
    raw = smooth_global_trajectory(raw)

    horizontal_span = float(max(np.nanmax(raw[:, 0]) - np.nanmin(raw[:, 0]), np.nanmax(raw[:, 2]) - np.nanmin(raw[:, 2])))
    if horizontal_span < 0.22 and len(raw) > 1:
        progress = np.linspace(0.0, 1.0, len(raw), dtype=np.float32)
        progress = progress * progress * (3.0 - 2.0 * progress)
        direction = float(np.sign(raw[-1, 0] - raw[0, 0]) or 1.0)
        raw[:, 0] += direction * progress * 0.42
        raw[:, 2] += progress * 0.14

    raw -= raw[0]
    raw[:, 0] = np.clip(raw[:, 0], -1.4, 1.4)
    raw[:, 1] = np.clip(raw[:, 1], -0.38, 0.38)
    raw[:, 2] = np.clip(raw[:, 2], -0.85, 0.85)
    return smooth_global_trajectory(raw)


def smooth_global_trajectory(trajectory: np.ndarray) -> np.ndarray:
    out = trajectory.copy()
    if len(out) < 3:
        return out
    if len(out) >= 7:
        kernel = np.array([0.05, 0.1, 0.2, 0.3, 0.2, 0.1, 0.05], dtype=np.float32)
    else:
        kernel = np.array([0.2, 0.6, 0.2], dtype=np.float32)
    pad = len(kernel) // 2
    for dim in range(3):
        out[:, dim] = np.convolve(np.pad(out[:, dim], (pad, pad), mode="edge"), kernel, mode="valid")

    max_step = np.array([0.075, 0.035, 0.055], dtype=np.float32)
    for frame_idx in range(1, len(out)):
        delta = out[frame_idx] - out[frame_idx - 1]
        out[frame_idx] = out[frame_idx - 1] + np.clip(delta, -max_step, max_step)
    for frame_idx in range(len(out) - 2, -1, -1):
        delta = out[frame_idx] - out[frame_idx + 1]
        out[frame_idx] = out[frame_idx + 1] + np.clip(delta, -max_step, max_step)
    out -= out[0]
    return out


def anthropomorphic_pose_lift(coords: np.ndarray, visibility: np.ndarray) -> np.ndarray:
    out = coords.copy()
    side_pairs = [
        (LM.LEFT_SHOULDER.value, LM.RIGHT_SHOULDER.value, 0.34),
        (LM.LEFT_HIP.value, LM.RIGHT_HIP.value, 0.24),
    ]
    bones = [
        (LM.LEFT_SHOULDER.value, LM.LEFT_ELBOW.value, 0.28),
        (LM.LEFT_ELBOW.value, LM.LEFT_WRIST.value, 0.26),
        (LM.RIGHT_SHOULDER.value, LM.RIGHT_ELBOW.value, 0.28),
        (LM.RIGHT_ELBOW.value, LM.RIGHT_WRIST.value, 0.26),
        (LM.LEFT_HIP.value, LM.LEFT_KNEE.value, 0.38),
        (LM.LEFT_KNEE.value, LM.LEFT_ANKLE.value, 0.36),
        (LM.RIGHT_HIP.value, LM.RIGHT_KNEE.value, 0.38),
        (LM.RIGHT_KNEE.value, LM.RIGHT_ANKLE.value, 0.36),
        (LM.LEFT_SHOULDER.value, LM.LEFT_HIP.value, 0.46),
        (LM.RIGHT_SHOULDER.value, LM.RIGHT_HIP.value, 0.46),
    ]
    for frame_idx in range(len(out)):
        frame = out[frame_idx]
        raw_z = frame[:, 2].copy()
        frame[:, 2] = np.clip(frame[:, 2], -0.55, 0.55)

        for left_idx, right_idx, target_width in side_pairs:
            if visibility[frame_idx, left_idx] < MIN_VISIBILITY or visibility[frame_idx, right_idx] < MIN_VISIBILITY:
                continue
            dx = float(frame[left_idx, 0] - frame[right_idx, 0])
            dy = float(frame[left_idx, 1] - frame[right_idx, 1])
            visible_width = math.hypot(dx, dy)
            depth_gap = math.sqrt(max(target_width * target_width - visible_width * visible_width, 0.0))
            raw_sign = np.sign(raw_z[left_idx] - raw_z[right_idx])
            sign = float(raw_sign if raw_sign else 1.0)
            center_z = float((frame[left_idx, 2] + frame[right_idx, 2]) * 0.5)
            frame[left_idx, 2] = center_z + sign * depth_gap * 0.5
            frame[right_idx, 2] = center_z - sign * depth_gap * 0.5

        for parent, child, target_length in bones:
            if visibility[frame_idx, parent] < MIN_VISIBILITY or visibility[frame_idx, child] < MIN_VISIBILITY:
                continue
            xy_dist = float(np.linalg.norm(frame[child, :2] - frame[parent, :2]))
            if xy_dist >= target_length:
                continue
            dz = math.sqrt(max(target_length * target_length - xy_dist * xy_dist, 0.0))
            raw_sign = np.sign(raw_z[child] - raw_z[parent])
            sign = float(raw_sign if raw_sign else np.sign(frame[child, 2] - frame[parent, 2]) or 1.0)
            lifted_z = frame[parent, 2] + sign * dz
            frame[child, 2] = 0.35 * frame[child, 2] + 0.65 * lifted_z

        pelvis_z = float(np.nanmean(frame[[LM.LEFT_HIP.value, LM.RIGHT_HIP.value], 2]))
        frame[:, 2] -= pelvis_z
        frame[:, 2] = np.clip(frame[:, 2], -0.95, 0.95)

    return stabilize_depth(out, visibility)


def kinematic_temporal_filter(coords: np.ndarray, visibility: np.ndarray) -> np.ndarray:
    out = stabilize_depth(coords, visibility)
    if len(out) < 3:
        return out

    core = {
        LM.NOSE.value,
        LM.LEFT_SHOULDER.value,
        LM.RIGHT_SHOULDER.value,
        LM.LEFT_HIP.value,
        LM.RIGHT_HIP.value,
    }
    fast = {
        LM.LEFT_ELBOW.value,
        LM.RIGHT_ELBOW.value,
        LM.LEFT_WRIST.value,
        LM.RIGHT_WRIST.value,
        LM.LEFT_INDEX.value,
        LM.RIGHT_INDEX.value,
        LM.LEFT_PINKY.value,
        LM.RIGHT_PINKY.value,
        LM.LEFT_THUMB.value,
        LM.RIGHT_THUMB.value,
    }
    limb = set(pose.BODY_JOINTS) - core

    def speed_limit(joint_idx: int) -> float:
        if joint_idx in core:
            return 0.055
        if joint_idx in fast:
            return 0.145
        if joint_idx in limb:
            return 0.095
        return 0.075

    def confidence_alpha(joint_idx: int, conf: float) -> float:
        base = 0.34 if joint_idx in fast else 0.48 if joint_idx in limb else 0.62
        return float(np.clip(base + (1.0 - conf) * 0.22, 0.32, 0.82))

    def pass_filter(arr: np.ndarray, forward: bool = True) -> np.ndarray:
        filtered = arr.copy()
        indices = range(1, len(filtered)) if forward else range(len(filtered) - 2, -1, -1)
        for frame_idx in indices:
            prev_idx = frame_idx - 1 if forward else frame_idx + 1
            for joint_idx in pose.BODY_JOINTS:
                if visibility[frame_idx, joint_idx] < MIN_VISIBILITY:
                    filtered[frame_idx, joint_idx] = filtered[prev_idx, joint_idx]
                    continue
                prev = filtered[prev_idx, joint_idx]
                cur = filtered[frame_idx, joint_idx]
                delta = cur - prev
                dist = float(np.linalg.norm(delta))
                limit = speed_limit(joint_idx)
                if dist > limit and dist > 1e-6:
                    cur = prev + delta / dist * limit
                alpha = confidence_alpha(joint_idx, float(visibility[frame_idx, joint_idx]))
                filtered[frame_idx, joint_idx] = alpha * prev + (1.0 - alpha) * cur
        return filtered

    out = pass_filter(out, forward=True)
    out = pass_filter(out, forward=False)

    if len(out) >= 5:
        kernel = np.array([0.08, 0.2, 0.44, 0.2, 0.08], dtype=np.float32)
        for joint_idx in pose.BODY_JOINTS:
            for dim in range(3):
                values = out[:, joint_idx, dim]
                out[:, joint_idx, dim] = np.convolve(np.pad(values, (2, 2), mode="edge"), kernel, mode="valid")

    return enforce_temporal_bone_consistency(out, visibility)


def enforce_temporal_bone_consistency(coords: np.ndarray, visibility: np.ndarray) -> np.ndarray:
    out = coords.copy()
    bones = [
        (LM.LEFT_SHOULDER.value, LM.LEFT_ELBOW.value),
        (LM.LEFT_ELBOW.value, LM.LEFT_WRIST.value),
        (LM.RIGHT_SHOULDER.value, LM.RIGHT_ELBOW.value),
        (LM.RIGHT_ELBOW.value, LM.RIGHT_WRIST.value),
        (LM.LEFT_HIP.value, LM.LEFT_KNEE.value),
        (LM.LEFT_KNEE.value, LM.LEFT_ANKLE.value),
        (LM.RIGHT_HIP.value, LM.RIGHT_KNEE.value),
        (LM.RIGHT_KNEE.value, LM.RIGHT_ANKLE.value),
        (LM.LEFT_SHOULDER.value, LM.LEFT_HIP.value),
        (LM.RIGHT_SHOULDER.value, LM.RIGHT_HIP.value),
    ]
    for parent, child in bones:
        valid = (visibility[:, parent] >= MIN_VISIBILITY) & (visibility[:, child] >= MIN_VISIBILITY)
        lengths = np.linalg.norm(out[:, child] - out[:, parent], axis=1)
        finite = valid & np.isfinite(lengths)
        if finite.sum() < 4:
            continue
        target = float(np.nanmedian(lengths[finite]))
        if target <= 1e-6:
            continue
        low, high = target * 0.76, target * 1.24
        for frame_idx in range(len(out)):
            if not valid[frame_idx]:
                continue
            vec = out[frame_idx, child] - out[frame_idx, parent]
            length = float(np.linalg.norm(vec))
            if length <= 1e-6 or (low <= length <= high):
                continue
            corrected = out[frame_idx, parent] + vec / length * float(np.clip(length, low, high))
            out[frame_idx, child] = 0.58 * out[frame_idx, child] + 0.42 * corrected
    return stabilize_depth(out, visibility)


def mean_landmarks(frame: np.ndarray, visibility: np.ndarray, indices: list[int]) -> np.ndarray | None:
    points = [frame[idx] for idx in indices if visibility[idx] >= MIN_VISIBILITY and np.isfinite(frame[idx]).all()]
    if not points:
        return None
    return np.mean(points, axis=0)


def body_scale_px(frame: np.ndarray, visibility: np.ndarray, width: int, height: int) -> float:
    points = []
    for idx in pose.BODY_JOINTS:
        if visibility[idx] >= MIN_VISIBILITY and np.isfinite(frame[idx, :2]).all():
            points.append([frame[idx, 0] * width, frame[idx, 1] * height])
    if len(points) < 4:
        return float(max(width, height))
    arr = np.asarray(points, dtype=np.float32)
    span = np.nanmax(arr, axis=0) - np.nanmin(arr, axis=0)
    return float(max(np.linalg.norm(span), max(width, height) * 0.08))


def stabilize_depth(coords: np.ndarray, visibility: np.ndarray) -> np.ndarray:
    out = coords.copy()
    for landmark_idx in range(out.shape[1]):
        valid = visibility[:, landmark_idx] >= MIN_VISIBILITY
        for dim in range(3):
            values = out[:, landmark_idx, dim]
            finite = valid & np.isfinite(values)
            if finite.sum() == 0:
                values[:] = 0.0
            elif finite.sum() == 1:
                values[:] = values[finite][0]
            else:
                values[:] = np.interp(np.arange(len(values)), np.where(finite)[0], values[finite])
            if len(values) >= 5:
                kernel = np.array([0.12, 0.22, 0.32, 0.22, 0.12], dtype=np.float32)
                values[:] = np.convolve(np.pad(values, (2, 2), mode="edge"), kernel, mode="valid")
            out[:, landmark_idx, dim] = values
    return out


def write_pose3d_csv(path: Path, coords: np.ndarray, visibility: np.ndarray, fps: float, backend: str) -> None:
    fieldnames = [
        "frame_index",
        "time_sec",
        "joint_name",
        "x_3d",
        "y_3d",
        "z_3d",
        "confidence",
        "scale_mode",
        "lift_backend",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for frame_idx in range(len(coords)):
            for joint_idx, name in enumerate(pose.LANDMARK_NAMES):
                writer.writerow(
                    {
                        "frame_index": frame_idx,
                        "time_sec": round(frame_idx / fps, 4),
                        "joint_name": name,
                        "x_3d": round(float(coords[frame_idx, joint_idx, 0]), 5),
                        "y_3d": round(float(coords[frame_idx, joint_idx, 1]), 5),
                        "z_3d": round(float(coords[frame_idx, joint_idx, 2]), 5),
                        "confidence": round(float(visibility[frame_idx, joint_idx]), 4),
                        "scale_mode": "body_scale_global_relative",
                        "lift_backend": backend,
                    }
                )


def render_pose3d_video(path: Path, coords: np.ndarray, visibility: np.ndarray, fps: float) -> None:
    size = 720
    scene = pose3d_scene(coords)
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps or 30.0, (size, size))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot write 3D pose video: {path}")
    try:
        for frame_idx in range(len(coords)):
            angle = math.radians(-28 + 10 * math.sin(frame_idx / max(len(coords), 1) * math.pi * 2))
            canvas = render_pose3d_frame(coords[frame_idx], visibility[frame_idx], angle, size, f"frame {frame_idx}", scene)
            writer.write(canvas)
    finally:
        writer.release()


def render_pose3d_animation(path: Path, coords: np.ndarray, visibility: np.ndarray, fps: float) -> bool:
    try:
        from PIL import Image
    except ImportError:
        return False

    if len(coords) == 0:
        return False
    size = 760
    max_frames = 54
    step = max(1, int(math.ceil(len(coords) / max_frames)))
    playback_fps = min(max((fps or 30.0) / step, 8.0), 18.0)
    duration_ms = int(round(1000.0 / playback_fps))
    frames = []
    scene = pose3d_scene(coords)
    adaptive_palette = getattr(getattr(Image, "Palette", None), "ADAPTIVE", getattr(Image, "ADAPTIVE", 1))
    for frame_idx in range(0, len(coords), step):
        phase = frame_idx / max(len(coords) - 1, 1)
        angle = math.radians(-36 + 72 * phase)
        canvas = render_pose3d_frame(coords[frame_idx], visibility[frame_idx], angle, size, f"{phase * 100:.0f}% motion", scene)
        rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
        frames.append(Image.fromarray(rgb).convert("P", palette=adaptive_palette, colors=128))
    if not frames:
        return False
    frames[0].save(
        path,
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
    )
    return True


def render_pose3d_contact_sheet(
    path: Path,
    coords: np.ndarray,
    visibility: np.ndarray,
    events: dict[str, int],
) -> None:
    selected = []
    for name, frame_idx in events.items():
        if isinstance(frame_idx, (int, float)):
            selected.append((name, max(0, min(int(frame_idx), len(coords) - 1))))
    if not selected:
        selected = [("start", 0), ("middle", len(coords) // 2), ("finish", len(coords) - 1)]
    tiles = []
    scene = pose3d_scene(coords)
    for name, frame_idx in selected:
        frame = render_pose3d_frame(coords[frame_idx], visibility[frame_idx], math.radians(-30), 360, name, scene)
        tiles.append(frame)
    if len(tiles) % 2:
        frame_idx = selected[-1][1]
        tiles.append(render_pose3d_frame(coords[frame_idx], visibility[frame_idx], math.radians(32), 360, "overview", scene))
    rows = []
    for i in range(0, len(tiles), 2):
        rows.append(np.hstack(tiles[i : i + 2]))
    sheet = np.vstack(rows)
    ok, encoded = cv2.imencode(".jpg", sheet)
    if not ok:
        raise RuntimeError(f"Cannot encode 3D contact sheet: {path}")
    path.write_bytes(encoded.tobytes())


def render_pose3d_frame(
    frame_coords: np.ndarray,
    visibility: np.ndarray,
    angle: float,
    size: int,
    label: str,
    scene: dict[str, float] | None = None,
) -> np.ndarray:
    canvas = np.full((size, size, 3), (18, 26, 39), dtype=np.uint8)
    draw_grid(canvas)
    projected, depth = project(frame_coords, angle, size, scene)
    order = sorted(range(len(CONNECTIONS)), key=lambda i: depth_pair(depth, CONNECTIONS[i]), reverse=True)
    for idx in order:
        a, b = CONNECTIONS[idx]
        if visibility[a] < MIN_VISIBILITY or visibility[b] < MIN_VISIBILITY:
            continue
        color = side_color(a, b)
        cv2.line(canvas, tuple(projected[a]), tuple(projected[b]), color, max(2, size // 120), cv2.LINE_AA)
    for idx, point in enumerate(projected):
        if visibility[idx] < MIN_VISIBILITY:
            continue
        radius = max(3, size // 90)
        cv2.circle(canvas, tuple(point), radius + 2, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(canvas, tuple(point), radius, side_color(idx, idx), -1, cv2.LINE_AA)
    cv2.putText(canvas, "Estimated 3D pose", (18, 34), cv2.FONT_HERSHEY_SIMPLEX, size / 900, (245, 248, 255), 2, cv2.LINE_AA)
    cv2.putText(canvas, label, (18, size - 22), cv2.FONT_HERSHEY_SIMPLEX, size / 950, (182, 195, 214), 2, cv2.LINE_AA)
    return canvas


def pose3d_scene(coords: np.ndarray) -> dict[str, float]:
    finite = coords[np.isfinite(coords).all(axis=2)]
    if len(finite) == 0:
        return {"cx": 0.0, "cy": 0.0, "cz": 0.0, "radius": 1.25}
    mins = np.nanmin(finite, axis=0)
    maxs = np.nanmax(finite, axis=0)
    radius = float(max(1.25, (maxs[0] - mins[0]) * 0.52, (maxs[1] - mins[1]) * 0.58, (maxs[2] - mins[2]) * 0.72))
    return {
        "cx": float((mins[0] + maxs[0]) * 0.5),
        "cy": float((mins[1] + maxs[1]) * 0.48),
        "cz": float((mins[2] + maxs[2]) * 0.5),
        "radius": radius,
    }


def project(frame_coords: np.ndarray, angle: float, size: int, scene: dict[str, float] | None = None) -> tuple[np.ndarray, np.ndarray]:
    ca = math.cos(angle)
    sa = math.sin(angle)
    scene = scene or {"cx": 0.0, "cy": 0.0, "cz": 0.0, "radius": 1.25}
    x = frame_coords[:, 0] - scene["cx"]
    y = frame_coords[:, 1] - scene["cy"]
    z = frame_coords[:, 2] - scene["cz"]
    rx = x * ca + z * sa
    rz = -x * sa + z * ca
    scale = size * 0.34 / max(float(scene.get("radius", 1.25)), 0.2)
    px = size * 0.52 + rx * scale
    py = size * 0.56 - y * scale
    pts = np.stack([px, py], axis=1)
    pts = np.nan_to_num(pts, nan=size / 2, posinf=size / 2, neginf=size / 2)
    pts = np.clip(pts, 8, size - 8).astype(np.int32)
    return pts, rz


def depth_pair(depth: np.ndarray, pair: tuple[int, int]) -> float:
    return float(depth[pair[0]] + depth[pair[1]])


def side_color(a: int, b: int) -> tuple[int, int, int]:
    names = [pose.LANDMARK_NAMES[a], pose.LANDMARK_NAMES[b]]
    if all(name.startswith("left_") for name in names):
        return (95, 200, 255)
    if all(name.startswith("right_") for name in names):
        return (110, 236, 170)
    return (236, 178, 92)


def draw_grid(canvas: np.ndarray) -> None:
    h, w = canvas.shape[:2]
    center_y = int(h * 0.68)
    for i in range(-4, 5):
        y = center_y + i * h // 24
        cv2.line(canvas, (w // 7, y), (w * 6 // 7, y), (39, 52, 72), 1, cv2.LINE_AA)
    cv2.line(canvas, (w // 2, h // 8), (w // 2, h * 7 // 8), (49, 64, 88), 1, cv2.LINE_AA)
