from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from point_mappings import POSE_GEOMETRY_CONNECTIONS


ROOT = Path(__file__).resolve().parents[1]
ALIGN_DIR = ROOT / "outputs" / "julian_bat_2d_vicon_alignment"
DEFAULT_SUMMARY = ALIGN_DIR / "alignment_summary.json"
DEFAULT_POSE = ALIGN_DIR / "pose2d_landmarks.csv"
DEFAULT_OVERLAY = ALIGN_DIR / "aligned_2d_skeleton_overlay.mp4"
DEFAULT_METRICS = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics.csv"
DEFAULT_OUT = ALIGN_DIR / "vicon_geometry_metric_annotations"

FONT_CANDIDATES = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]

READY_METRICS = [
    "ready_rear_hip_flexion_deg",
    "ready_rear_knee_flexion_deg",
    "ready_hip_shoulder_separation_deg",
]

CONTACT_METRICS = [
    "contact_torso_rotation_open_deg",
    "contact_pelvis_rotation_open_deg",
    "contact_front_knee_flexion_deg",
]

ANGLE_GEOMETRY = {
    # MediaPipe anatomical left/right is unreliable in this side/back view.
    # These are visual-role anchors: rear/load leg is the screen-left leg in
    # the Ready frame, front/support leg is the screen-left leg in Contact.
    "ready_rear_hip_flexion_deg": ("shoulder_mid", "right_hip", "right_knee"),
    "ready_rear_knee_flexion_deg": ("right_hip", "right_knee", "right_ankle"),
    "contact_front_knee_flexion_deg": ("left_hip", "left_knee", "left_ankle"),
}

ANGLE_VALUE_OFFSETS = {
    "ready_rear_hip_flexion_deg": (-118, -28),
    "ready_rear_knee_flexion_deg": (-106, 22),
    "contact_front_knee_flexion_deg": (96, 34),
}

LINE_GEOMETRY = {
    "ready_hip_shoulder_separation_deg": [("left_shoulder", "right_shoulder"), ("left_hip", "right_hip")],
    "contact_pelvis_rotation_open_deg": [("left_hip", "right_hip")],
    "contact_torso_rotation_open_deg": [("left_shoulder", "right_shoulder")],
}

# RGB colors. Convert through cv_color() before drawing with OpenCV.
COLORS = {
    "blue": (42, 122, 232),
    "purple": (130, 73, 230),
    "orange": (244, 122, 32),
    "green": (28, 170, 88),
    "yellow": (250, 210, 38),
    "white": (255, 255, 255),
    "ink": (16, 24, 40),
    "panel": (14, 22, 36),
}

METRIC_COLORS = {
    "ready_rear_hip_flexion_deg": COLORS["purple"],
    "ready_rear_knee_flexion_deg": COLORS["orange"],
    "ready_hip_shoulder_separation_deg": COLORS["blue"],
    "contact_pelvis_rotation_open_deg": COLORS["green"],
    "contact_torso_rotation_open_deg": COLORS["purple"],
    "contact_front_knee_flexion_deg": COLORS["orange"],
}

METRIC_EN = {
    "ready_rear_hip_flexion_deg": "Vicon 3D value | Rear hip flexion",
    "ready_rear_knee_flexion_deg": "Vicon 3D value | Rear knee flexion",
    "ready_hip_shoulder_separation_deg": "Vicon 3D value | Hip-shoulder separation",
    "contact_pelvis_rotation_open_deg": "Vicon 3D value | Pelvis rotation",
    "contact_torso_rotation_open_deg": "Vicon 3D value | Torso rotation",
    "contact_front_knee_flexion_deg": "Vicon 3D value | Front knee flexion",
}

SKELETON_CONNECTIONS = list(POSE_GEOMETRY_CONNECTIONS)


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def cv_color(color: tuple[int, int, int]) -> tuple[int, int, int]:
    return color[2], color[1], color[0]


def fnum(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def load_pose(path: Path) -> dict[int, dict[str, tuple[float, float, float]]]:
    frames: dict[int, dict[str, tuple[float, float, float]]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            x = fnum(row.get("x_px"))
            y = fnum(row.get("y_px"))
            visibility = fnum(row.get("visibility"))
            if x is None or y is None or visibility is None:
                continue
            frames[int(row["frame_index"])][row["landmark"]] = (x, y, visibility)
    return frames


def load_metrics(path: Path, sample_name: str) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = [row for row in csv.DictReader(f) if row["sample_name"] == sample_name]
    return {row["metric_key"]: row for row in rows}


def midpoint(points: dict[str, tuple[float, float, float]], a: str, b: str) -> tuple[float, float] | None:
    if a not in points or b not in points:
        return None
    return ((points[a][0] + points[b][0]) / 2, (points[a][1] + points[b][1]) / 2)


def xy(points: dict[str, tuple[float, float, float]], name: str) -> tuple[float, float] | None:
    if name == "shoulder_mid":
        return midpoint(points, "left_shoulder", "right_shoulder")
    if name == "hip_mid":
        return midpoint(points, "left_hip", "right_hip")
    if name not in points:
        return None
    return points[name][0], points[name][1]


def as_int(p: tuple[float, float]) -> tuple[int, int]:
    return int(round(p[0])), int(round(p[1]))


def vicon_to_video_frame(vicon_frame: int, summary: dict[str, Any]) -> int:
    fps = float(summary["video_meta"]["fps"])
    alignment = summary["alignment"]
    scale = float(alignment.get("slow_motion_factor", 1.0))
    offset = float(
        alignment.get(
            "time_offset_sec_add_to_scaled_vicon_time",
            alignment.get("time_offset_sec_add_to_vicon_time", 0.0),
        )
    )
    return int(round((vicon_frame / 100.0 * scale + offset) * fps))


def score_frame(points: dict[str, tuple[float, float, float]], required: set[str]) -> float:
    return sum(points.get(name, (0.0, 0.0, 0.0))[2] for name in required) / max(len(required), 1)


def choose_event_frame(
    vicon_frames: list[int],
    summary: dict[str, Any],
    poses: dict[int, dict[str, tuple[float, float, float]]],
    required: set[str],
) -> tuple[int, int, float]:
    best: tuple[float, int, int] | None = None
    for vicon_frame in vicon_frames:
        video_frame = vicon_to_video_frame(vicon_frame, summary)
        if video_frame not in poses:
            continue
        score = score_frame(poses.get(video_frame, {}), required)
        item = (score, vicon_frame, video_frame)
        if best is None or item > best:
            best = item
    if best is None:
        raise RuntimeError("No event frame candidates found")
    return best[1], best[2], best[0]


def choose_latest_visible_event_frame(
    vicon_frames: list[int],
    summary: dict[str, Any],
    poses: dict[int, dict[str, tuple[float, float, float]]],
    required: set[str],
) -> tuple[int, int, float]:
    for vicon_frame in sorted(vicon_frames, reverse=True):
        video_frame = vicon_to_video_frame(vicon_frame, summary)
        if video_frame in poses:
            return vicon_frame, video_frame, score_frame(poses[video_frame], required)
    return choose_event_frame(vicon_frames, summary, poses, required)


def event_is_visible(vicon_frames: list[int], summary: dict[str, Any]) -> bool:
    frame_count = int(summary["video_meta"].get("frames_read") or summary["video_meta"].get("frame_count_meta") or 0)
    mapped = [vicon_to_video_frame(frame, summary) for frame in vicon_frames]
    return any(0 <= frame < frame_count for frame in mapped)


def choose_visual_fallback_frame(
    poses: dict[int, dict[str, tuple[float, float, float]]],
    required: set[str],
    frame_start: int = 0,
    frame_end: int = 60,
) -> tuple[int, float]:
    best: tuple[float, int] | None = None
    for frame_idx in range(frame_start, frame_end + 1):
        if frame_idx not in poses:
            continue
        score = score_frame(poses[frame_idx], required)
        item = (score, frame_idx)
        if best is None or item > best:
            best = item
    if best is None:
        return frame_start, 0.0
    return best[1], best[0]


def get_video_frame(video_path: Path, frame_index: int) -> np.ndarray:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open video: {video_path}")
    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {frame_index} from {video_path}")
    return frame


def draw_line(frame: np.ndarray, p1: tuple[float, float], p2: tuple[float, float], color: tuple[int, int, int], thickness: int = 7) -> None:
    c = cv_color(color)
    cv2.line(frame, as_int(p1), as_int(p2), c, thickness, cv2.LINE_AA)
    cv2.circle(frame, as_int(p1), thickness + 2, cv_color(COLORS["white"]), -1, cv2.LINE_AA)
    cv2.circle(frame, as_int(p1), thickness - 1, c, -1, cv2.LINE_AA)
    cv2.circle(frame, as_int(p2), thickness + 2, cv_color(COLORS["white"]), -1, cv2.LINE_AA)
    cv2.circle(frame, as_int(p2), thickness - 1, c, -1, cv2.LINE_AA)


def draw_dashed_arc(
    frame: np.ndarray,
    center: tuple[float, float],
    start_deg: float,
    end_deg: float,
    radius: int,
    color: tuple[int, int, int],
    thickness: int = 3,
    min_sweep_deg: float = 0.0,
) -> None:
    delta = (end_deg - start_deg + 180) % 360 - 180
    if abs(delta) < 1:
        return
    if abs(delta) < min_sweep_deg:
        delta = math.copysign(min_sweep_deg, delta)
    steps = max(42, int(abs(delta) / 1.8))
    angles = np.linspace(math.radians(start_deg), math.radians(start_deg + delta), steps)
    pts = [
        (
            int(round(center[0] + radius * math.cos(angle))),
            int(round(center[1] + radius * math.sin(angle))),
        )
        for angle in angles
    ]
    for idx in range(len(pts) - 1):
        if idx % 18 < 15:
            cv2.line(frame, pts[idx], pts[idx + 1], cv_color(COLORS["white"]), thickness + 5, cv2.LINE_AA)
            cv2.line(frame, pts[idx], pts[idx + 1], cv_color(color), thickness, cv2.LINE_AA)


def draw_dashed_line(
    frame: np.ndarray,
    p1: tuple[float, float],
    p2: tuple[float, float],
    color: tuple[int, int, int],
    thickness: int = 3,
) -> None:
    start = np.array(p1, dtype=float)
    end = np.array(p2, dtype=float)
    vec = end - start
    length = float(np.linalg.norm(vec))
    if length < 1:
        return
    direction = vec / length
    dash = 12
    gap = 8
    pos = 0.0
    while pos < length:
        seg_start = start + direction * pos
        seg_end = start + direction * min(pos + dash, length)
        cv2.line(frame, as_int(tuple(seg_start)), as_int(tuple(seg_end)), cv_color(COLORS["white"]), thickness + 5, cv2.LINE_AA)
        cv2.line(frame, as_int(tuple(seg_start)), as_int(tuple(seg_end)), cv_color(color), thickness, cv2.LINE_AA)
        pos += dash + gap


def draw_angle(
    frame: np.ndarray,
    a: tuple[float, float],
    b: tuple[float, float],
    c: tuple[float, float],
    color: tuple[int, int, int],
) -> None:
    draw_line(frame, b, a, color, thickness=3)
    draw_line(frame, b, c, color, thickness=3)
    va = np.array([a[0] - b[0], a[1] - b[1]], dtype=float)
    vc = np.array([c[0] - b[0], c[1] - b[1]], dtype=float)
    va_len = float(np.linalg.norm(va))
    vc_len = float(np.linalg.norm(vc))
    if va_len >= 1 and vc_len >= 1:
        guide_len = min(112.0, max(76.0, vc_len * 0.68))
        extension = np.array(b, dtype=float) - va / va_len * guide_len
        distal_guide = np.array(b, dtype=float) + vc / vc_len * guide_len
        draw_dashed_line(frame, b, tuple(extension), color, thickness=2)
        draw_dashed_line(frame, b, tuple(distal_guide), color, thickness=2)
    cv2.circle(frame, as_int(b), 6, cv_color(COLORS["white"]), -1, cv2.LINE_AA)
    cv2.circle(frame, as_int(b), 4, cv_color(color), -1, cv2.LINE_AA)


def draw_angle_value_callout(
    frame: np.ndarray,
    joint: tuple[float, float],
    value: str,
    color: tuple[int, int, int],
    offset: tuple[int, int],
) -> None:
    end = (joint[0] + offset[0], joint[1] + offset[1])
    cv2.line(frame, as_int(joint), as_int(end), cv_color(COLORS["white"]), 5, cv2.LINE_AA)
    cv2.line(frame, as_int(joint), as_int(end), cv_color(color), 2, cv2.LINE_AA)
    cv2.circle(frame, as_int(joint), 5, cv_color(COLORS["white"]), -1, cv2.LINE_AA)
    cv2.circle(frame, as_int(joint), 3, cv_color(color), -1, cv2.LINE_AA)
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image, "RGBA")
    font = load_font(24)
    bbox = draw.textbbox((0, 0), value, font=font)
    pad_x, pad_y = 8, 4
    x = int(round(end[0]))
    y = int(round(end[1]))
    if offset[0] < 0:
        x -= bbox[2] - bbox[0] + pad_x * 2
    y -= (bbox[3] - bbox[1]) // 2 + pad_y
    draw.rounded_rectangle(
        (x, y, x + bbox[2] - bbox[0] + pad_x * 2, y + bbox[3] - bbox[1] + pad_y * 2),
        radius=7,
        fill=(255, 255, 255, 226),
        outline=(*color, 255),
        width=2,
    )
    draw.text((x + pad_x, y + pad_y - 1), value, font=font, fill=(*color, 255))
    frame[:] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def draw_label(
    frame: np.ndarray,
    title: str,
    value: str,
    subtitle: str,
    anchor: tuple[int, int],
    color: tuple[int, int, int],
    align: str = "left",
) -> None:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image, "RGBA")
    value_font = load_font(40)
    sub_font = load_font(22)
    text = f"{title} {value}"
    bbox = draw.textbbox((0, 0), text, font=value_font)
    sb = draw.textbbox((0, 0), subtitle, font=sub_font)
    w = max(bbox[2] - bbox[0], sb[2] - sb[0])
    h = (bbox[3] - bbox[1]) + (sb[3] - sb[1]) + 18
    x, y = anchor
    if align == "right":
        x -= w + 36
    draw.rounded_rectangle((x, y, x + w + 40, y + h + 28), radius=14, fill=(255, 255, 255, 238), outline=(*color, 255), width=5)
    draw.text((x + 20, y + 10), text, font=value_font, fill=(*color, 255))
    draw.text((x + 20, y + 58), subtitle, font=sub_font, fill=(58, 66, 82, 255))
    frame[:] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def draw_header(frame: np.ndarray, title: str, vicon_frame: int, video_frame: int) -> None:
    image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(image, "RGBA")
    title_font = load_font(42)
    sub_font = load_font(24)
    draw.rounded_rectangle((28, 24, 990, 132), radius=18, fill=(14, 22, 36, 214))
    draw.text((54, 44), f"打击：{title} 2D 几何标注", font=title_font, fill=(255, 255, 255, 255))
    draw.text((56, 94), f"Vicon frame {vicon_frame} -> video frame {video_frame}", font=sub_font, fill=(218, 226, 238, 255))
    frame[:] = cv2.cvtColor(np.asarray(image), cv2.COLOR_RGB2BGR)


def draw_skeleton(frame: np.ndarray, points: dict[str, tuple[float, float, float]]) -> None:
    for a, b in SKELETON_CONNECTIONS:
        p1 = xy(points, a)
        p2 = xy(points, b)
        if not p1 or not p2:
            continue
        cv2.line(frame, as_int(p1), as_int(p2), cv_color(COLORS["yellow"]), 3, cv2.LINE_AA)
    for name, (x, y, visibility) in points.items():
        if visibility < 0.2:
            continue
        radius = 5 if name in {"left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "right_knee", "left_ankle", "right_ankle"} else 4
        cv2.circle(frame, (round(x), round(y)), radius + 2, cv_color(COLORS["white"]), -1, cv2.LINE_AA)
        cv2.circle(frame, (round(x), round(y)), radius, cv_color(COLORS["green"]), -1, cv2.LINE_AA)


def draw_arrow(frame: np.ndarray, start: tuple[int, int], end: tuple[float, float], color: tuple[int, int, int]) -> None:
    cv2.arrowedLine(frame, start, as_int(end), cv_color(color), 5, cv2.LINE_AA, tipLength=0.08)


def cubic_bezier(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    steps: int = 64,
) -> list[tuple[int, int]]:
    pts = []
    for t in np.linspace(0.0, 1.0, steps):
        x = (1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0] + 3 * (1 - t) * t**2 * p2[0] + t**3 * p3[0]
        y = (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1] + 3 * (1 - t) * t**2 * p2[1] + t**3 * p3[1]
        pts.append((int(round(x)), int(round(y))))
    return pts


def draw_rotation_arrow(
    frame: np.ndarray,
    center: tuple[float, float],
    radius_x: int,
    radius_y: int,
    start_deg: float,
    end_deg: float,
    color: tuple[int, int, int],
    thickness: int = 6,
) -> None:
    if end_deg < start_deg:
        end_deg += 360.0
    pts = []
    for angle_deg in np.linspace(start_deg, end_deg, 72):
        angle = math.radians(angle_deg)
        pts.append(
            (
                int(round(center[0] + radius_x * math.cos(angle))),
                int(round(center[1] + radius_y * math.sin(angle))),
            )
        )
    pts = pts[int(round(len(pts) * 0.2)) :]
    arr = np.array(pts, dtype=np.int32)
    cv2.polylines(frame, [arr], False, cv_color(COLORS["white"]), thickness + 4, cv2.LINE_AA)
    cv2.polylines(frame, [arr], False, cv_color(color), thickness, cv2.LINE_AA)
    cv2.arrowedLine(frame, pts[-5], pts[-1], cv_color(COLORS["white"]), thickness + 4, cv2.LINE_AA, tipLength=0.65)
    cv2.arrowedLine(frame, pts[-5], pts[-1], cv_color(color), thickness, cv2.LINE_AA, tipLength=0.65)


def fmt_metric(row: dict[str, str]) -> str:
    value = float(row["value"])
    unit = row["unit"]
    if unit == "deg":
        return f"{value:.1f}°"
    if unit == "height_ratio":
        return f"{value:.3f}"
    if unit == "mm":
        return f"{value:.0f} mm"
    return f"{value:.1f} {unit}".strip()


def draw_metric(
    frame: np.ndarray,
    points: dict[str, tuple[float, float, float]],
    key: str,
    row: dict[str, str],
    label_anchor: tuple[int, int],
    arrow_start: tuple[int, int] | None = None,
    label_align: str = "left",
) -> None:
    color = METRIC_COLORS[key]
    target: tuple[float, float] | None = None
    if key in ANGLE_GEOMETRY:
        a_name, b_name, c_name = ANGLE_GEOMETRY[key]
        pts = [xy(points, name) for name in (a_name, b_name, c_name)]
        if all(p is not None for p in pts):
            draw_angle(frame, pts[0], pts[1], pts[2], color)  # type: ignore[arg-type]
            draw_angle_value_callout(frame, pts[1], fmt_metric(row), color, ANGLE_VALUE_OFFSETS.get(key, (86, 26)))  # type: ignore[arg-type]
            target = pts[1]
    if key == "ready_hip_shoulder_separation_deg":
        shoulder_l = xy(points, "left_shoulder")
        shoulder_r = xy(points, "right_shoulder")
        hip_l = xy(points, "left_hip")
        hip_r = xy(points, "right_hip")
        if shoulder_l and shoulder_r and hip_l and hip_r:
            draw_line(frame, shoulder_l, shoulder_r, COLORS["blue"], thickness=7)
            draw_line(frame, hip_l, hip_r, COLORS["purple"], thickness=7)
            sm = midpoint(points, "left_shoulder", "right_shoulder")
            hm = midpoint(points, "left_hip", "right_hip")
            if sm and hm:
                draw_line(frame, sm, hm, color, thickness=5)
                target = ((sm[0] + hm[0]) / 2, (sm[1] + hm[1]) / 2)
    elif key == "contact_pelvis_rotation_open_deg":
        hip_l = xy(points, "left_hip")
        hip_r = xy(points, "right_hip")
        hm = midpoint(points, "left_hip", "right_hip")
        if hip_l and hip_r and hm:
            draw_line(frame, hip_l, hip_r, color, thickness=8)
            draw_rotation_arrow(
                frame,
                (hm[0] + 54, hm[1] + 42),
                42,
                25,
                220,
                500,
                color,
            )
            target = hm
    elif key == "contact_torso_rotation_open_deg":
        shoulder_l = xy(points, "left_shoulder")
        shoulder_r = xy(points, "right_shoulder")
        sm = midpoint(points, "left_shoulder", "right_shoulder")
        if shoulder_l and shoulder_r and sm:
            draw_line(frame, shoulder_l, shoulder_r, color, thickness=8)
            draw_rotation_arrow(
                frame,
                (sm[0] + 50, sm[1] + 48),
                51,
                29,
                220,
                500,
                color,
            )
            target = sm
    draw_label(frame, row["metric_name_zh"], fmt_metric(row), METRIC_EN[key], label_anchor, color, label_align)
    if arrow_start and target:
        draw_arrow(frame, arrow_start, target, color)


def annotate_event(
    *,
    video_path: Path,
    poses: dict[int, dict[str, tuple[float, float, float]]],
    metrics: dict[str, dict[str, str]],
    event_name: str,
    metric_keys: list[str],
    vicon_frame: int,
    video_frame: int,
    out_path: Path,
) -> np.ndarray:
    frame = get_video_frame(video_path, video_frame)
    points = poses[video_frame]
    if event_name == "Ready Position":
        anchors = [(740, 188), (730, 308), (720, 428)]
        arrows = [None, None, None]
    else:
        anchors = [(42, 148), (42, 268), (720, 546)]
        arrows = [None, None, None]
    aligns = ["left", "left", "left"]
    draw_skeleton(frame, points)
    for key, anchor, arrow, align in zip(metric_keys, anchors, arrows, aligns):
        draw_metric(frame, points, key, metrics[key], anchor, arrow, align)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out_path), frame)
    return frame


def write_hold_video(frames: list[np.ndarray], out_path: Path, fps: float) -> None:
    if not frames:
        return
    h, w = frames[0].shape[:2]
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output video: {out_path}")
    for frame in frames:
        for _ in range(int(round(fps * 1.8))):
            writer.write(frame)
    writer.release()


def parse_event_frames(row: dict[str, str]) -> list[int]:
    return [int(x) for x in row["event_frames"].split(";") if x]


def main() -> None:
    parser = argparse.ArgumentParser(description="Annotate Vicon geometry metrics on aligned 2D skeleton frames.")
    parser.add_argument(
        "--alignment-dir",
        type=Path,
        default=None,
        help="Directory containing alignment_summary.json, pose2d_landmarks.csv, and optional aligned_2d_skeleton_overlay.mp4.",
    )
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--pose", type=Path, default=DEFAULT_POSE)
    parser.add_argument("--overlay", type=Path, default=DEFAULT_OVERLAY, help="Fallback base video if the raw video from summary is unavailable.")
    parser.add_argument("--video", type=Path, default=None, help="Override the base video used for annotation backgrounds.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--sample-name", default="julian")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    if args.alignment_dir is not None:
        args.summary = args.alignment_dir / "alignment_summary.json"
        args.pose = args.alignment_dir / "pose2d_landmarks.csv"
        args.overlay = args.alignment_dir / "aligned_2d_skeleton_overlay.mp4"

    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    poses = load_pose(args.pose)
    metrics = load_metrics(args.metrics, args.sample_name)
    base_video = args.video or Path(summary["video"])
    if not base_video.exists():
        base_video = args.overlay

    ready_required = {"left_shoulder", "right_shoulder", "left_hip", "right_hip", "right_knee", "right_ankle"}
    contact_required = {"left_shoulder", "right_shoulder", "left_hip", "right_hip", "left_knee", "left_ankle"}

    ready_frames = parse_event_frames(metrics["ready_rear_hip_flexion_deg"])
    contact_frames = parse_event_frames(metrics["contact_front_knee_flexion_deg"])
    ready_visible = event_is_visible(ready_frames, summary)
    ready_vicon = ready_frames[len(ready_frames) // 2]
    ready_video = vicon_to_video_frame(ready_vicon, summary)
    ready_score = 0.0
    if ready_visible:
        ready_vicon, ready_video, ready_score = choose_event_frame(ready_frames, summary, poses, ready_required)
    else:
        ready_video, ready_score = choose_visual_fallback_frame(poses, ready_required, 0, 60)
    contact_vicon, contact_video, contact_score = choose_latest_visible_event_frame(
        contact_frames, summary, poses, contact_required
    )

    ready_frame = annotate_event(
        video_path=base_video,
        poses=poses,
        metrics=metrics,
        event_name="Ready Position",
        metric_keys=READY_METRICS,
        vicon_frame=ready_vicon,
        video_frame=ready_video,
        out_path=args.out_dir / "ready_position_vicon_geometry_on_2d.png",
    )
    contact_frame = annotate_event(
        video_path=base_video,
        poses=poses,
        metrics=metrics,
        event_name="Contact Position",
        metric_keys=CONTACT_METRICS,
        vicon_frame=contact_vicon,
        video_frame=contact_video,
        out_path=args.out_dir / "contact_position_vicon_geometry_on_2d.png",
    )

    video_out = args.out_dir / "vicon_geometry_metrics_on_2d_events.mp4"
    write_hold_video([ready_frame, contact_frame], video_out, float(summary["video_meta"]["fps"]))

    report = {
        "provenance": {
            "sample_name": args.sample_name,
            "metrics": str(args.metrics.resolve()),
            "video": str(base_video.resolve()),
            "alignment_summary": str(args.summary.resolve()),
            "c3d": str(Path(summary["c3d"]).resolve()),
        },
        "ready": {
            "vicon_frame": ready_vicon,
            "video_frame": ready_video,
            "pose_visibility_score": ready_score,
            "visual_fallback_used": not ready_visible,
            "metrics": READY_METRICS,
        },
        "contact": {"vicon_frame": contact_vicon, "video_frame": contact_video, "pose_visibility_score": contact_score, "metrics": CONTACT_METRICS},
        "outputs": {
            "ready_png": str(args.out_dir / "ready_position_vicon_geometry_on_2d.png"),
            "contact_png": str(args.out_dir / "contact_position_vicon_geometry_on_2d.png"),
            "mp4": str(video_out),
        },
        "note": "Values are read from Vicon batting_dashboard_metrics.csv; 2D skeleton is used only as a visual guide.",
    }
    (args.out_dir / "vicon_geometry_metric_annotations.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
