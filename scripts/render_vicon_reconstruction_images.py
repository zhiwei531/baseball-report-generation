from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image

from build_vicon_2026_metrics import C3DTrial, clean_label, infer_action, is_reconstruction_point, read_c3d, trial_id


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTS = ROOT / "reports" / "vicon_2026_point_summary.csv"
DEFAULT_OUT_DIR = ROOT / "reports" / "assets" / "vicon_reconstruction"
DEFAULT_MODEL_DIR = ROOT / "reports" / "assets" / "vicon_reconstruction_models"
DEFAULT_MODEL_MANIFEST = ROOT / "reports" / "vicon_2026_key_pose_models.csv"
DEFAULT_C3D_DIR = ROOT.parent / "vicon_2026"
RENDER_FIGSIZE = (8.0, 5.2)
RENDER_DPI = 180
DEFAULT_GIF_BEFORE_SEC = 0.6
DEFAULT_PITCH_GIF_BEFORE_SEC = 1.4
DEFAULT_GIF_AFTER_SEC = 0.4

PART_COLORS = {
    "头颈": "#d71920",
    "躯干": "#d71920",
    "左臂": "#d71920",
    "右臂": "#d71920",
    "骨盆": "#d71920",
    "左腿": "#d71920",
    "右腿": "#d71920",
    "质心点": "#0b7285",
    "球棒": "#138a13",
}
BODY_MARKER_COLOR = "#003cff"
BODY_LINE_COLOR = "#d71920"
TRAJECTORY_COLOR = "#666666"
BODY_SURFACE_ALPHA = 0.035
LABEL_COLOR = "#1f2937"
BAT_LABEL_COLOR = "#0f6b0f"
BODY_SEGMENTS = [
    ("C7", "T10", "躯干"),
    ("C7", "CLAV", "躯干"),
    ("CLAV", "STRN", "躯干"),
    ("STRN", "T10", "躯干"),
    ("T10", "RBAK", "躯干"),
    ("LSHO", "RSHO", "躯干"),
    ("LSHO", "C7", "躯干"),
    ("RSHO", "C7", "躯干"),
    ("LASI", "RASI", "骨盆"),
    ("LASI", "LPSI", "骨盆"),
    ("RASI", "RPSI", "骨盆"),
    ("LPSI", "RPSI", "骨盆"),
    ("LSHO", "LUPA", "左臂"),
    ("LUPA", "LELB", "左臂"),
    ("LELB", "LFRM", "左臂"),
    ("LFRM", "LWRA", "左臂"),
    ("LFRM", "LWRB", "左臂"),
    ("LWRA", "LWRB", "左臂"),
    ("LELB", "LWRB", "左臂"),
    ("LWRA", "LFIN", "左臂"),
    ("LWRB", "LFIN", "左臂"),
    ("RSHO", "RUPA", "右臂"),
    ("RUPA", "RELB", "右臂"),
    ("RELB", "RFRM", "右臂"),
    ("RFRM", "RWRA", "右臂"),
    ("RFRM", "RWRB", "右臂"),
    ("RWRA", "RWRB", "右臂"),
    ("RELB", "RWRB", "右臂"),
    ("RWRA", "RFIN", "右臂"),
    ("RWRB", "RFIN", "右臂"),
    ("LASI", "LTHI", "左腿"),
    ("LTHI", "LKNE", "左腿"),
    ("LKNE", "LTIB", "左腿"),
    ("LTIB", "LANK", "左腿"),
    ("LANK", "LHEE", "左腿"),
    ("LANK", "LTOE", "左腿"),
    ("LHEE", "LTOE", "左腿"),
    ("RASI", "RTHI", "右腿"),
    ("RTHI", "RKNE", "右腿"),
    ("RKNE", "RTIB", "右腿"),
    ("RTIB", "RANK", "右腿"),
    ("RANK", "RHEE", "右腿"),
    ("RANK", "RTOE", "右腿"),
    ("RHEE", "RTOE", "右腿"),
]
BAT_MARKERS = ["Bat1", "Bat2", "Bat3", "Bat4", "Bat5"]
LABEL_POINTS: list[str] = []
FOOT_MARKERS = {"LANK", "LHEE", "LTOE", "RANK", "RHEE", "RTOE"}
RAW_MARKERS = {
    "LFHD", "RFHD", "LBHD", "RBHD", "C7", "T10", "CLAV", "STRN", "RBAK",
    "LSHO", "LUPA", "LELB", "LFRM", "LWRA", "LWRB", "LFIN",
    "RSHO", "RUPA", "RELB", "RFRM", "RWRA", "RWRB", "RFIN",
    "LASI", "RASI", "LPSI", "RPSI", "LTHI", "LKNE", "LTIB", "LANK", "LHEE", "LTOE",
    "RTHI", "RKNE", "RTIB", "RANK", "RHEE", "RTOE",
}
RAW_MARKER_PARTS = {
    "头颈": {"LFHD", "RFHD", "LBHD", "RBHD"},
    "躯干": {"C7", "T10", "CLAV", "STRN", "RBAK"},
    "左臂": {"LSHO", "LUPA", "LELB", "LFRM", "LWRA", "LWRB", "LFIN"},
    "右臂": {"RSHO", "RUPA", "RELB", "RFRM", "RWRA", "RWRB", "RFIN"},
    "骨盆": {"LASI", "RASI", "LPSI", "RPSI"},
    "左腿": {"LTHI", "LKNE", "LTIB", "LANK", "LHEE", "LTOE"},
    "右腿": {"RTHI", "RKNE", "RTIB", "RANK", "RHEE", "RTOE"},
}
ZH_FONT_PATHS = [
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
]


def zh_font() -> FontProperties | None:
    for path in ZH_FONT_PATHS:
        if path.exists():
            return FontProperties(fname=str(path))
    return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def require_cv2() -> Any:
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError("MP4 export requires opencv-python / cv2.") from exc
    return cv2


def output_path_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def num(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        x = float(value)
    except ValueError:
        return None
    return x if math.isfinite(x) else None


def points_for_trial(rows: list[dict[str, str]]) -> dict[str, tuple[float, float, float]]:
    points = {}
    for row in rows:
        x = num(row.get("key_x_mm"))
        y = num(row.get("key_y_mm"))
        z = num(row.get("key_z_mm"))
        if x is None or y is None or z is None:
            continue
        points[row["point"]] = (x, y, z)
    return points


AxisLimits = tuple[tuple[float, float], tuple[float, float], tuple[float, float]]


def axis_limits_from_coords(coords: np.ndarray, margin: float = 1.55) -> AxisLimits:
    mins = coords.min(axis=0)
    maxs = coords.max(axis=0)
    center = (mins + maxs) / 2
    spans = np.maximum(maxs - mins, np.array([500.0, 500.0, 900.0]))
    xy_span = max(float(spans[0]), float(spans[1]), 800.0)
    x_radius = xy_span * 0.5 * margin
    y_radius = xy_span * 0.5 * (margin * 1.35)
    z_radius = max(float(spans[2]) * 0.5 * (margin * 1.05), 650.0)
    z_center = max(float(center[2]), z_radius - 120.0)
    return (
        (float(center[0] - x_radius), float(center[0] + x_radius)),
        (float(center[1] - y_radius), float(center[1] + y_radius)),
        (float(z_center - z_radius), float(z_center + z_radius)),
    )


def set_equal_axes(ax, points: dict[str, tuple[float, float, float]], limits: AxisLimits | None = None) -> None:
    if limits is None:
        coords = np.array(list(points.values()), dtype=float)
        limits = axis_limits_from_coords(coords)
    (xlim, ylim, zlim) = limits
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_zlim(*zlim)


def recenter_display_limits(
    limits: AxisLimits | None,
    points: dict[str, tuple[float, float, float]],
) -> AxisLimits | None:
    if limits is None or not points:
        return limits
    coords = np.array(list(points.values()), dtype=float)
    coords = coords[np.isfinite(coords).all(axis=1)]
    if coords.size == 0:
        return limits
    xlim, ylim, zlim = limits
    current_y_radius = (ylim[1] - ylim[0]) / 2
    marker_y_min = float(coords[:, 1].min())
    marker_y_max = float(coords[:, 1].max())
    marker_center = (marker_y_min + marker_y_max) / 2
    marker_radius = max((marker_y_max - marker_y_min) / 2 * 1.65, 520.0)
    y_radius = max(current_y_radius, marker_radius)
    foot_coords = np.array([points[name] for name in FOOT_MARKERS if name in points], dtype=float)
    foot_coords = foot_coords[np.isfinite(foot_coords).all(axis=1)] if foot_coords.size else foot_coords
    y_center = float((foot_coords[:, 1].min() + foot_coords[:, 1].max()) / 2) if foot_coords.size else marker_center
    return (xlim, (y_center - y_radius, y_center + y_radius), zlim)


def is_render_point(name: str) -> bool:
    return name in RAW_MARKERS or name == "CentreOfMass" or name.startswith("Bat")


def trial_axis_limits(trial: C3DTrial, frame_indices: np.ndarray | None = None) -> AxisLimits:
    clean = [clean_label(label) for label in trial.labels]
    keep = [idx for idx, name in enumerate(clean) if is_reconstruction_point(name) and is_render_point(name)]
    if frame_indices is None:
        points = trial.points[:, keep, :3]
    else:
        points = trial.points[frame_indices, :, :][:, keep, :3]
    coords = points.reshape(-1, 3)
    coords = coords[np.isfinite(coords).all(axis=1)]
    if coords.size == 0:
        return ((-500.0, 500.0), (-500.0, 500.0), (-100.0, 1200.0))
    # Percentile bounds avoid one bad marker forcing the athlete to become tiny.
    lo = np.nanpercentile(coords, 1, axis=0)
    hi = np.nanpercentile(coords, 99, axis=0)
    return axis_limits_from_coords(np.vstack([lo, hi]), margin=1.35)


def draw_segment(ax, points: dict[str, tuple[float, float, float]], a: str, b: str, color: str, width: float) -> None:
    if a not in points or b not in points:
        return
    pa = points[a]
    pb = points[b]
    ax.plot([pa[0], pb[0]], [pa[1], pb[1]], [pa[2], pb[2]], color=color, linewidth=width, solid_capstyle="round")


def draw_closed_shape(
    ax,
    points: dict[str, tuple[float, float, float]],
    faces: list[list[str]],
    edges: list[tuple[str, str]],
    color: str,
    width: float,
    alpha: float,
) -> None:
    polygons = []
    for face in faces:
        if all(name in points for name in face):
            polygons.append([points[name] for name in face])
    if polygons:
        collection = Poly3DCollection(
            polygons,
            facecolors=color,
            edgecolors=color,
            linewidths=width * 0.75,
            alpha=alpha,
        )
        ax.add_collection3d(collection)
    for a, b in edges:
        draw_segment(ax, points, a, b, color, width)


def complete_edges(names: list[str]) -> list[tuple[str, str]]:
    return [(a, b) for i, a in enumerate(names) for b in names[i + 1:]]


def model_edges() -> list[tuple[str, str]]:
    edges = [(a, b) for a, b, _part in BODY_SEGMENTS]
    edges.extend(
        [
            ("LFHD", "RFHD"),
            ("RFHD", "RBHD"),
            ("RBHD", "LBHD"),
            ("LBHD", "LFHD"),
            ("LFHD", "RBHD"),
            ("RFHD", "LBHD"),
            ("LFHD", "C7"),
            ("RFHD", "C7"),
            ("LBHD", "C7"),
            ("RBHD", "C7"),
        ]
    )
    edges.extend(complete_edges(["C7", "CLAV", "STRN", "T10", "RBAK"]))
    edges.extend(complete_edges(["LASI", "RASI", "LPSI", "RPSI"]))
    edges.extend(complete_edges(["LSHO", "LUPA", "LELB"]))
    edges.extend(complete_edges(["LELB", "LFRM", "LWRA", "LWRB"]))
    edges.extend(complete_edges(["LWRA", "LWRB", "LFIN"]))
    edges.extend(complete_edges(["RSHO", "RUPA", "RELB"]))
    edges.extend(complete_edges(["RELB", "RFRM", "RWRA", "RWRB"]))
    edges.extend(complete_edges(["RWRA", "RWRB", "RFIN"]))
    edges.extend(complete_edges(["LASI", "LPSI", "LTHI", "LKNE"]))
    edges.extend(complete_edges(["LKNE", "LTIB", "LANK"]))
    edges.extend(complete_edges(["RASI", "RPSI", "RTHI", "RKNE"]))
    edges.extend(complete_edges(["RKNE", "RTIB", "RANK"]))
    edges.extend([("LANK", "LHEE"), ("LHEE", "LTOE"), ("LTOE", "LANK")])
    edges.extend([("RANK", "RHEE"), ("RHEE", "RTOE"), ("RTOE", "RANK")])
    edges.extend(complete_edges(BAT_MARKERS))
    deduped: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for a, b in edges:
        key = tuple(sorted((a, b)))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((a, b))
    return deduped


def draw_head_shape(ax, points: dict[str, tuple[float, float, float]]) -> None:
    draw_closed_shape(
        ax,
        points,
        faces=[["LFHD", "RFHD", "RBHD"], ["LFHD", "RBHD", "LBHD"]],
        edges=[
            ("LFHD", "RFHD"),
            ("RFHD", "RBHD"),
            ("RBHD", "LBHD"),
            ("LBHD", "LFHD"),
            ("LFHD", "RBHD"),
            ("RFHD", "LBHD"),
            ("LFHD", "C7"),
            ("RFHD", "C7"),
            ("LBHD", "C7"),
            ("RBHD", "C7"),
        ],
        color=BODY_LINE_COLOR,
        width=0.9,
        alpha=BODY_SURFACE_ALPHA,
    )


def draw_middle_body_shapes(ax, points: dict[str, tuple[float, float, float]]) -> None:
    draw_closed_shape(
        ax,
        points,
        faces=[
            ["C7", "CLAV", "STRN"],
            ["C7", "STRN", "T10"],
            ["C7", "T10", "RBAK"],
            ["T10", "STRN", "RBAK"],
        ],
        edges=complete_edges(["C7", "CLAV", "STRN", "T10", "RBAK"]),
        color=BODY_LINE_COLOR,
        width=0.9,
        alpha=BODY_SURFACE_ALPHA,
    )
    draw_closed_shape(
        ax,
        points,
        faces=[["LASI", "RASI", "RPSI"], ["LASI", "RPSI", "LPSI"]],
        edges=complete_edges(["LASI", "RASI", "LPSI", "RPSI"]),
        color=BODY_LINE_COLOR,
        width=0.9,
        alpha=BODY_SURFACE_ALPHA,
    )


def draw_limb_shapes(ax, points: dict[str, tuple[float, float, float]]) -> None:
    limb_specs = [
        {
            "names": ["LSHO", "LUPA", "LELB"],
            "faces": [["LSHO", "LUPA", "LELB"]],
            "part": "左臂",
        },
        {
            "names": ["LELB", "LFRM", "LWRA", "LWRB"],
            "faces": [
                ["LELB", "LFRM", "LWRA"],
                ["LELB", "LFRM", "LWRB"],
                ["LELB", "LWRA", "LWRB"],
            ],
            "part": "左臂",
        },
        {
            "names": ["LWRA", "LWRB", "LFIN"],
            "faces": [["LWRA", "LWRB", "LFIN"]],
            "part": "左臂",
        },
        {
            "names": ["RSHO", "RUPA", "RELB"],
            "faces": [["RSHO", "RUPA", "RELB"]],
            "part": "右臂",
        },
        {
            "names": ["RELB", "RFRM", "RWRA", "RWRB"],
            "faces": [
                ["RELB", "RFRM", "RWRA"],
                ["RELB", "RFRM", "RWRB"],
                ["RELB", "RWRA", "RWRB"],
            ],
            "part": "右臂",
        },
        {
            "names": ["RWRA", "RWRB", "RFIN"],
            "faces": [["RWRA", "RWRB", "RFIN"]],
            "part": "右臂",
        },
        {
            "names": ["LASI", "LPSI", "LTHI", "LKNE"],
            "faces": [
                ["LASI", "LPSI", "LTHI"],
                ["LASI", "LTHI", "LKNE"],
                ["LPSI", "LTHI", "LKNE"],
            ],
            "part": "左腿",
        },
        {
            "names": ["LKNE", "LTIB", "LANK"],
            "faces": [["LKNE", "LTIB", "LANK"]],
            "part": "左腿",
        },
        {
            "names": ["RASI", "RPSI", "RTHI", "RKNE"],
            "faces": [
                ["RASI", "RPSI", "RTHI"],
                ["RASI", "RTHI", "RKNE"],
                ["RPSI", "RTHI", "RKNE"],
            ],
            "part": "右腿",
        },
        {
            "names": ["RKNE", "RTIB", "RANK"],
            "faces": [["RKNE", "RTIB", "RANK"]],
            "part": "右腿",
        },
    ]
    for spec in limb_specs:
        available = [name for name in spec["names"] if name in points]
        if len(available) < 3:
            continue
        draw_closed_shape(
            ax,
            points,
            faces=spec["faces"],
            edges=complete_edges(available),
            color=BODY_LINE_COLOR,
            width=0.75,
            alpha=BODY_SURFACE_ALPHA,
        )


def draw_foot_shapes(ax, points: dict[str, tuple[float, float, float]]) -> None:
    draw_closed_shape(
        ax,
        points,
        faces=[["LANK", "LHEE", "LTOE"]],
        edges=[("LANK", "LHEE"), ("LHEE", "LTOE"), ("LTOE", "LANK")],
        color=BODY_LINE_COLOR,
        width=0.9,
        alpha=BODY_SURFACE_ALPHA,
    )
    draw_closed_shape(
        ax,
        points,
        faces=[["RANK", "RHEE", "RTOE"]],
        edges=[("RANK", "RHEE"), ("RHEE", "RTOE"), ("RTOE", "RANK")],
        color=BODY_LINE_COLOR,
        width=0.9,
        alpha=BODY_SURFACE_ALPHA,
    )


def draw_bat_rigid_body(ax, points: dict[str, tuple[float, float, float]]) -> None:
    ordered = [name for name in BAT_MARKERS if name in points]
    if len(ordered) < 2:
        return
    for a, b in complete_edges(ordered):
        draw_bat_outline_segment(ax, points, a, b)
    for a, b in zip(ordered, ordered[1:]):
        draw_segment(ax, points, a, b, PART_COLORS["球棒"], 1.35)


def draw_bat_outline_segment(
    ax,
    points: dict[str, tuple[float, float, float]],
    a: str,
    b: str,
) -> None:
    pa = points[a]
    pb = points[b]
    ax.plot(
        [pa[0], pb[0]],
        [pa[1], pb[1]],
        [pa[2], pb[2]],
        color=PART_COLORS["球棒"],
        linewidth=0.65,
        alpha=0.34,
        solid_capstyle="round",
    )


def marker_part(name: str) -> str:
    for part, labels in RAW_MARKER_PARTS.items():
        if name in labels:
            return part
    return "躯干"


def scatter_points(ax, points: dict[str, tuple[float, float, float]], label: str, color: str, size: float, alpha: float = 1.0) -> None:
    if not points:
        return
    coords = np.array(list(points.values()), dtype=float)
    ax.scatter(coords[:, 0], coords[:, 1], coords[:, 2], s=size, c=color, alpha=alpha, depthshade=False, label=label)


def style_reference_axes(ax) -> None:
    ax.set_facecolor("#ffffff")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((1.0, 1.0, 1.0, 1.0))
        axis.pane.set_edgecolor((0.82, 0.84, 0.87, 1.0))
        axis._axinfo["grid"]["color"] = (0.78, 0.80, 0.82, 1.0)
        axis._axinfo["grid"]["linewidth"] = 0.65
        axis._axinfo["axisline"]["color"] = (0.20, 0.22, 0.24, 1.0)
    ax.grid(True)


def draw_bat1_trajectory(ax, trajectory: list[tuple[float, float, float]]) -> None:
    if len(trajectory) < 2:
        return
    coords = np.array(trajectory, dtype=float)
    ax.plot(
        coords[:, 0],
        coords[:, 1],
        coords[:, 2],
        color=TRAJECTORY_COLOR,
        linewidth=0.85,
        linestyle=(0, (3, 4)),
        alpha=0.78,
        label="棒头轨迹",
    )
    ax.scatter(
        [coords[-1, 0]],
        [coords[-1, 1]],
        [coords[-1, 2]],
        s=16,
        c=TRAJECTORY_COLOR,
        marker="x",
        depthshade=False,
    )


def fixed_legend(
    ax,
    font: FontProperties | None,
    include_bat: bool,
    include_bat1_trajectory: bool = False,
    bbox_to_anchor: tuple[float, float] = (0.98, 0.98),
) -> None:
    handles = []
    if include_bat:
        handles.append(
            Line2D([0], [0], color=PART_COLORS["球棒"], linewidth=1.4, label="球棒")
        )
    if include_bat1_trajectory:
        handles.append(
            Line2D(
                [0],
                [0],
                color=TRAJECTORY_COLOR,
                linewidth=0.85,
                linestyle=(0, (3, 4)),
                label="棒头轨迹",
            )
        )
    if not handles:
        return
    legend = ax.legend(
        handles=handles,
        loc="upper right",
        bbox_to_anchor=bbox_to_anchor,
        frameon=True,
        fontsize=7.0,
        borderpad=0.35,
        labelspacing=0.3,
        handlelength=1.6,
        handletextpad=0.5,
    )
    if font is not None:
        for text in legend.get_texts():
            text.set_fontproperties(font)


def split_points(points: dict[str, tuple[float, float, float]]) -> tuple[
    dict[str, tuple[float, float, float]],
    dict[str, tuple[float, float, float]],
    dict[str, tuple[float, float, float]],
    dict[str, tuple[float, float, float]],
]:
    body_points = {k: v for k, v in points.items() if not k.startswith("Bat")}
    raw_points = {k: v for k, v in body_points.items() if k in RAW_MARKERS}
    model_points: dict[str, tuple[float, float, float]] = {}
    com_points = {k: v for k, v in body_points.items() if k == "CentreOfMass"}
    bat_points = {k: v for k, v in points.items() if k.startswith("Bat")}
    return raw_points, model_points, com_points, bat_points


def draw_reconstruction(
    ax,
    points: dict[str, tuple[float, float, float]],
    font: FontProperties | None,
    title: str,
    frame_label: str | None = None,
    show_labels: bool = True,
    axis_limits: AxisLimits | None = None,
    fixed_layout_legend: bool = False,
    bat1_trajectory: list[tuple[float, float, float]] | None = None,
    recenter_limits: bool = True,
) -> None:
    raw_points, model_points, com_points, bat_points = split_points(points)
    visible_points = {**raw_points, **com_points, **bat_points}
    trajectory = bat1_trajectory or []

    style_reference_axes(ax)
    ax.view_init(elev=17, azim=-66)
    for a, b, _part in BODY_SEGMENTS:
        draw_segment(ax, points, a, b, BODY_LINE_COLOR, 1.05)
    draw_head_shape(ax, points)
    draw_middle_body_shapes(ax, points)
    draw_limb_shapes(ax, points)
    draw_foot_shapes(ax, points)
    draw_bat_rigid_body(ax, points)

    for part in ("头颈", "躯干", "骨盆", "左臂", "右臂", "左腿", "右腿"):
        part_points = {name: value for name, value in raw_points.items() if marker_part(name) == part}
        scatter_points(ax, part_points, part, BODY_MARKER_COLOR, 8)
    scatter_points(ax, com_points, "质心点", BODY_MARKER_COLOR, 14)
    scatter_points(ax, bat_points, "球棒点", PART_COLORS["球棒"], 8)
    draw_bat1_trajectory(ax, trajectory)

    if show_labels:
        for name in LABEL_POINTS:
            if name not in visible_points:
                continue
            x, y, z = visible_points[name]
            color = BAT_LABEL_COLOR if name.startswith("Bat") else LABEL_COLOR
            ax.text(x, y, z, name, fontsize=4.5, color=color)

    display_points = dict(visible_points)
    display_points.update({f"Bat1Trajectory{i}": xyz for i, xyz in enumerate(trajectory)})
    display_limits = recenter_display_limits(axis_limits, display_points) if recenter_limits else axis_limits
    set_equal_axes(ax, visible_points, limits=display_limits)
    ax.set_xlabel("X (mm)", labelpad=8, fontsize=9, fontproperties=font)
    ax.set_ylabel("Y (mm)", labelpad=8, fontsize=9, fontproperties=font)
    ax.set_zlabel("Z (mm)", labelpad=8, fontsize=9, fontproperties=font)
    ax.tick_params(axis="both", labelsize=7, pad=1)
    ax.grid(True)
    if frame_label:
        if fixed_layout_legend:
            ax.text2D(
                0.04,
                0.93,
                frame_label,
                transform=ax.transAxes,
                fontsize=8,
                color="#344054",
                fontproperties=font,
                bbox={"facecolor": "#ffffff", "edgecolor": "#d0d5dd", "alpha": 0.86, "pad": 2.4},
            )
        else:
            ax.text2D(0.67, 0.92, frame_label, transform=ax.transAxes, fontsize=9, color="#344054", fontproperties=font)
    fixed_legend(
        ax,
        font,
        include_bat=bool(bat_points),
        include_bat1_trajectory=len(trajectory) >= 2,
        bbox_to_anchor=(0.98, 0.88) if fixed_layout_legend else (0.98, 0.98),
    )
    ax.set_title(title, fontsize=10, color="#101828", fontproperties=font)
    ax.set_box_aspect((1, 1, 1))


def render_trial(rows: list[dict[str, str]], out_dir: Path) -> Path | None:
    if not rows:
        return None
    first = rows[0]
    trial_id = first["trial_id"]
    sample = first.get("athlete", "")
    action = first.get("action_type", "")
    event = first.get("key_event", "关键动作")
    frame = first.get("key_frame_index", "")
    time_sec = num(first.get("key_time_sec"))
    points = points_for_trial(rows)
    if not points:
        return None

    fig = plt.figure(figsize=RENDER_FIGSIZE, dpi=RENDER_DPI)
    ax = fig.add_subplot(111, projection="3d")
    font = zh_font()
    fig.patch.set_facecolor("#ffffff")

    action_text = "投球" if action == "pitching" else "打击"
    time_text = f"{time_sec:.2f}秒" if time_sec is not None else "暂无时间"
    draw_reconstruction(
        ax,
        points,
        font,
        f"{sample} / {action_text} / {event} / 第{frame}帧 / {time_text}",
        show_labels=True,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{trial_id}.png"
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


def bat1_trajectory_points(
    trial: C3DTrial,
    frame_indices: np.ndarray,
    smooth_radius: int = 0,
    max_points: int = 24,
) -> list[tuple[float, float, float]]:
    if infer_action(trial.path) != "batting":
        return []
    clean = [clean_label(label) for label in trial.labels]
    if "Bat1" not in clean:
        return []
    idx = clean.index("Bat1")
    trajectory: list[tuple[float, float, float]] = []
    if len(frame_indices) > max_points:
        frame_indices = np.linspace(int(frame_indices[0]), int(frame_indices[-1]), max_points, dtype=int)
    for frame_idx in frame_indices:
        frame_int = int(frame_idx)
        if smooth_radius:
            start = max(0, frame_int - smooth_radius)
            end = min(trial.points.shape[0], frame_int + smooth_radius + 1)
            window = trial.points[start:end, idx, :3]
            valid = np.isfinite(window).all(axis=1)
            if not valid.any():
                continue
            xyz = np.nanmedian(window[valid], axis=0)
        else:
            xyz = trial.points[frame_int, idx, :3]
        if np.isfinite(xyz).all():
            trajectory.append((float(xyz[0]), float(xyz[1]), float(xyz[2])))
    return trajectory


def bat1_tail_frame_indices(
    trial: C3DTrial,
    end_frame: int,
    tail_sec: float = 0.28,
) -> np.ndarray:
    tail = max(2, int(round(tail_sec * trial.rate_hz)))
    start = max(0, end_frame - tail)
    return np.arange(start, end_frame + 1, dtype=int)


def render_trial_from_c3d(
    trial: C3DTrial,
    rows: list[dict[str, str]],
    out_dir: Path,
    before_sec: float = DEFAULT_GIF_BEFORE_SEC,
    after_sec: float = DEFAULT_GIF_AFTER_SEC,
    pitch_before_sec: float = DEFAULT_PITCH_GIF_BEFORE_SEC,
    smooth_radius: int = 2,
) -> Path | None:
    if not rows:
        return render_trial(rows, out_dir)
    first = rows[0]
    frame_count = trial.points.shape[0]
    key_idx, event = key_frame_from_rows(rows, frame_count)
    before_sec = action_before_seconds(trial, before_sec, pitch_before_sec)
    before = max(1, int(round(before_sec * trial.rate_hz)))
    after = max(1, int(round(after_sec * trial.rate_hz)))
    start = max(0, key_idx - before)
    end = min(frame_count - 1, key_idx + after)
    axis_indices = np.arange(start, end + 1, dtype=int)
    trajectory_indices = bat1_tail_frame_indices(trial, key_idx)
    points = points_for_trial(rows)
    if not points:
        return None

    fig = plt.figure(figsize=RENDER_FIGSIZE, dpi=RENDER_DPI)
    ax = fig.add_subplot(111, projection="3d")
    font = zh_font()
    fig.patch.set_facecolor("#ffffff")

    sample = first.get("athlete", "")
    action = first.get("action_type", "")
    action_text = "投球" if action == "pitching" else "打击"
    time_sec = num(first.get("key_time_sec"))
    time_text = f"{time_sec:.2f}秒" if time_sec is not None else "暂无时间"
    trajectory = bat1_trajectory_points(trial, trajectory_indices, smooth_radius=smooth_radius)
    draw_reconstruction(
        ax,
        points,
        font,
        f"{sample} / {action_text} / {event} / 第{key_idx}帧 / {time_text}",
        show_labels=True,
        axis_limits=trial_axis_limits(trial, frame_indices=axis_indices),
        bat1_trajectory=trajectory,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{first['trial_id']}.png"
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(out_path, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    return out_path


def export_key_pose_obj(rows: list[dict[str, str]], model_dir: Path) -> Path | None:
    if not rows:
        return None
    first = rows[0]
    points = points_for_trial(rows)
    points = {name: xyz for name, xyz in points.items() if is_render_point(name)}
    if not points:
        return None
    trial_key = first["trial_id"]
    model_dir.mkdir(parents=True, exist_ok=True)
    out_path = model_dir / f"{trial_key}_key_pose.obj"
    ordered_names = sorted(points)
    vertex_index = {name: idx + 1 for idx, name in enumerate(ordered_names)}
    lines = [
        f"# trial_id: {trial_key}",
        f"# sample_name: {first.get('sample_name', first.get('athlete', ''))}",
        f"# action_type: {first.get('action_type', '')}",
        f"# key_event: {first.get('key_event', '')}",
        f"# key_frame_index: {first.get('key_frame_index', '')}",
        f"# key_time_sec: {first.get('key_time_sec', '')}",
        "# units: millimeters",
        "o key_pose_reconstruction",
    ]
    for name in ordered_names:
        x, y, z = points[name]
        lines.append(f"v {x:.6f} {y:.6f} {z:.6f} # {name}")
    for a, b in model_edges():
        if a in vertex_index and b in vertex_index:
            lines.append(f"l {vertex_index[a]} {vertex_index[b]}")
    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out_path


def trial_frame_points(trial: C3DTrial, frame_idx: int, smooth_radius: int = 0) -> dict[str, tuple[float, float, float]]:
    clean = [clean_label(label) for label in trial.labels]
    points = {}
    start = max(0, frame_idx - smooth_radius)
    end = min(trial.points.shape[0], frame_idx + smooth_radius + 1)
    for idx, name in enumerate(clean):
        if not is_reconstruction_point(name):
            continue
        if not is_render_point(name):
            continue
        if smooth_radius:
            window = trial.points[start:end, idx, :3]
            valid = np.isfinite(window).all(axis=1)
            if not valid.any():
                continue
            xyz = np.nanmedian(window[valid], axis=0)
        else:
            xyz = trial.points[frame_idx, idx, :3]
        if np.isfinite(xyz).all():
            points[name] = (float(xyz[0]), float(xyz[1]), float(xyz[2]))
    return points


def key_frame_from_rows(rows: list[dict[str, str]], frame_count: int) -> tuple[int, str]:
    if not rows:
        return frame_count // 2, "关键动作"
    first = rows[0]
    key_frame = num(first.get("key_frame_index"))
    if key_frame is None:
        return frame_count // 2, first.get("key_event", "关键动作")
    idx = min(max(int(round(key_frame)), 0), frame_count - 1)
    return idx, first.get("key_event", "关键动作")


def action_before_seconds(trial: C3DTrial, before_sec: float, pitch_before_sec: float) -> float:
    if infer_action(trial.path) == "pitching":
        return max(before_sec, pitch_before_sec)
    return before_sec


def key_action_frame_indices(
    trial: C3DTrial,
    rows: list[dict[str, str]],
    before_sec: float,
    after_sec: float,
    max_frames: int,
    pitch_before_sec: float = DEFAULT_PITCH_GIF_BEFORE_SEC,
) -> tuple[np.ndarray, str]:
    frame_count = trial.points.shape[0]
    key_idx, event = key_frame_from_rows(rows, frame_count)
    before_sec = action_before_seconds(trial, before_sec, pitch_before_sec)
    before = max(1, int(round(before_sec * trial.rate_hz)))
    after = max(1, int(round(after_sec * trial.rate_hz)))
    start = max(0, key_idx - before)
    end = min(frame_count - 1, key_idx + after)
    if end <= start:
        start = max(0, key_idx - 1)
        end = min(frame_count - 1, key_idx + 1)
    count = min(max_frames, end - start + 1)
    return np.linspace(start, end, count, dtype=int), event


def render_trial_gif(
    trial: C3DTrial,
    rows: list[dict[str, str]],
    out_dir: Path,
    max_frames: int = 72,
    frame_duration_ms: int = 85,
    smooth_radius: int = 2,
    before_sec: float = DEFAULT_GIF_BEFORE_SEC,
    after_sec: float = DEFAULT_GIF_AFTER_SEC,
    pitch_before_sec: float = DEFAULT_PITCH_GIF_BEFORE_SEC,
) -> list[Path]:
    frame_count = trial.points.shape[0]
    if frame_count == 0:
        return []
    frame_indices, event = key_action_frame_indices(
        trial,
        rows,
        before_sec,
        after_sec,
        max_frames,
        pitch_before_sec=pitch_before_sec,
    )
    frames: list[Image.Image] = []
    video_frames: list[np.ndarray] = []
    font = zh_font()
    sample = trial.path.parent.name
    action = infer_action(trial.path)
    action_text = "投球" if action == "pitching" else "打击"
    title = f"{sample} / {action_text} / C3D骨架动图"
    limits = trial_axis_limits(trial, frame_indices=frame_indices)
    key_idx, _key_event = key_frame_from_rows(rows, frame_count)
    key_points = points_for_trial(rows) if rows else trial_frame_points(trial, key_idx, smooth_radius=smooth_radius)
    key_trajectory = bat1_trajectory_points(
        trial,
        bat1_tail_frame_indices(trial, key_idx),
        smooth_radius=smooth_radius,
    )
    key_display_points = dict(key_points)
    key_display_points.update({f"Bat1Trajectory{i}": xyz for i, xyz in enumerate(key_trajectory)})
    animation_limits = recenter_display_limits(limits, key_display_points)
    fig = plt.figure(figsize=RENDER_FIGSIZE, dpi=RENDER_DPI)
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_subplot(111, projection="3d")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
    for frame_idx in frame_indices:
        ax.clear()
        points = trial_frame_points(trial, int(frame_idx), smooth_radius=smooth_radius)
        if not points:
            continue
        bat1_trajectory = bat1_trajectory_points(
            trial,
            bat1_tail_frame_indices(trial, int(frame_idx)),
            smooth_radius=smooth_radius,
        )
        draw_reconstruction(
            ax,
            points,
            font,
            title,
            frame_label=f"{event}窗口 / 第{int(frame_idx)}帧 / {frame_idx / trial.rate_hz:.2f}秒",
            show_labels=False,
            axis_limits=animation_limits,
            fixed_layout_legend=True,
            bat1_trajectory=bat1_trajectory,
            recenter_limits=False,
        )
        fig.canvas.draw()
        width, height = fig.canvas.get_width_height()
        frame = Image.frombytes("RGBA", (width, height), fig.canvas.buffer_rgba())
        video_frames.append(np.array(frame.convert("RGB")))
        frames.append(frame.convert("P", palette=Image.Palette.ADAPTIVE))
    plt.close(fig)

    if not frames:
        return []
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    gif_path = out_dir / f"{trial_id(trial.path)}.gif"
    frames[0].save(
        gif_path,
        save_all=True,
        append_images=frames[1:],
        duration=frame_duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )
    outputs.append(gif_path)

    mp4_path = out_dir / f"{trial_id(trial.path)}.mp4"
    write_mp4(mp4_path, video_frames, fps=max(1.0, 1000.0 / frame_duration_ms))
    outputs.append(mp4_path)

    avi_path = out_dir / f"{trial_id(trial.path)}.avi"
    write_avi_mjpg(avi_path, video_frames, fps=max(1.0, 1000.0 / frame_duration_ms))
    outputs.append(avi_path)
    return outputs


def write_mp4(path: Path, frames: list[np.ndarray], fps: float) -> None:
    if not frames:
        return
    cv2 = require_cv2()
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open MP4 writer: {path}")
    try:
        for frame in frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()


def write_avi_mjpg(path: Path, frames: list[np.ndarray], fps: float) -> None:
    if not frames:
        return
    cv2 = require_cv2()
    path.parent.mkdir(parents=True, exist_ok=True)
    height, width = frames[0].shape[:2]
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"MJPG"),
        fps,
        (width, height),
    )
    if not writer.isOpened():
        raise RuntimeError(f"Could not open AVI writer: {path}")
    try:
        for frame in frames:
            writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
    finally:
        writer.release()


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Vicon C3D key-action reconstruction PNGs.")
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS)
    parser.add_argument("--c3d-dir", type=Path, default=DEFAULT_C3D_DIR)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--model-dir", type=Path, default=DEFAULT_MODEL_DIR)
    parser.add_argument("--model-manifest", type=Path, default=DEFAULT_MODEL_MANIFEST)
    parser.add_argument("--max-gif-frames", type=int, default=72)
    parser.add_argument("--gif-before-sec", type=float, default=DEFAULT_GIF_BEFORE_SEC)
    parser.add_argument("--pitch-gif-before-sec", type=float, default=DEFAULT_PITCH_GIF_BEFORE_SEC)
    parser.add_argument("--gif-after-sec", type=float, default=DEFAULT_GIF_AFTER_SEC)
    args = parser.parse_args()

    by_trial: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(args.points):
        by_trial[row["trial_id"]].append(row)

    outputs = []
    model_rows = []
    for trial_key in sorted(by_trial):
        rows = by_trial[trial_key]
        png_out = render_trial(rows, args.out_dir)
        obj_out = export_key_pose_obj(rows, args.model_dir)
        if png_out is not None:
            outputs.append(png_out)
        if obj_out is not None:
            outputs.append(obj_out)
            first = rows[0]
            model_rows.append(
                {
                    "trial_id": trial_key,
                    "sample_name": first.get("sample_name", first.get("athlete", "")),
                    "athlete": first.get("athlete", first.get("sample_name", "")),
                    "action_type": first.get("action_type", ""),
                    "key_event": first.get("key_event", ""),
                    "key_rule": first.get("key_rule", ""),
                    "key_frame_index": first.get("key_frame_index", ""),
                    "key_time_sec": first.get("key_time_sec", ""),
                    "model_path": output_path_label(obj_out),
                    "point_count": len(points_for_trial(rows)),
                }
            )

    for path in sorted(args.c3d_dir.glob("*/*.c3d")):
        if path.name.startswith("._"):
            continue
        trial = read_c3d(path)
        png_out = render_trial_from_c3d(
            trial,
            by_trial.get(trial_id(path), []),
            args.out_dir,
            before_sec=args.gif_before_sec,
            after_sec=args.gif_after_sec,
            pitch_before_sec=args.pitch_gif_before_sec,
        )
        if png_out is not None:
            outputs.append(png_out)
        animation_outputs = render_trial_gif(
            trial,
            by_trial.get(trial_id(path), []),
            args.out_dir,
            max_frames=args.max_gif_frames,
            before_sec=args.gif_before_sec,
            after_sec=args.gif_after_sec,
            pitch_before_sec=args.pitch_gif_before_sec,
        )
        outputs.extend(animation_outputs)

    if model_rows:
        args.model_manifest.parent.mkdir(parents=True, exist_ok=True)
        with args.model_manifest.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(model_rows[0].keys()))
            writer.writeheader()
            writer.writerows(model_rows)
        outputs.append(args.model_manifest)

    for path in outputs:
        print(path)


if __name__ == "__main__":
    main()
