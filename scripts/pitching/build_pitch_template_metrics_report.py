from __future__ import annotations

import argparse
import csv
import html
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.font_manager import FontProperties
from matplotlib.lines import Line2D
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
TEMPLATE_DIR: Path | None = None
PREV_PITCH_ASSETS: Path | None = None
OUT_DIR = ROOT / "reports" / "pitching"
ASSET_DIR = OUT_DIR / "assets"

C3D_FILES: list[tuple[str, str, str, Path]] = []

from build_vicon_2026_metrics import clean_label, read_c3d, safe_nanmean  # noqa: E402
import render_vicon_reconstruction_images as recon  # noqa: E402


BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#f97316"
RED = "#ef4444"
PURPLE = "#7c3aed"
INK = "#101828"
MID = "#667085"


def zh_font_prop() -> FontProperties | None:
    for path in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return FontProperties(fname=str(path))
    return None


def pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    for path in (
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc") if bold else Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if bold else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


recon.zh_font = zh_font_prop


@dataclass
class TrialBundle:
    key: str
    name: str
    role: str
    path: Path
    trial: object
    clean_labels: list[str]
    events: dict[str, int]
    values: dict[str, float]
    height_mm: float
    floor_mm: float


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def finite(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value))


def metric_point(trial, clean_labels: list[str], name: str) -> np.ndarray:
    if name not in clean_labels:
        return np.full((trial.points.shape[0], 3), np.nan)
    return trial.points[:, clean_labels.index(name), :3].astype(float)


def marker(trial, clean_labels: list[str], *names: str) -> np.ndarray:
    series = [metric_point(trial, clean_labels, name) for name in names if name in clean_labels]
    if not series:
        return np.full((trial.points.shape[0], 3), np.nan)
    return safe_nanmean(series, axis=0)


def channel(trial, clean_labels: list[str], name: str, axis: int) -> np.ndarray:
    return metric_point(trial, clean_labels, name)[:, axis]


def speed_mps(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    diff = np.diff(points_mm, axis=0) / 1000.0
    out = np.linalg.norm(diff, axis=1) * rate_hz
    return np.concatenate([[np.nan], out])


def smooth(values: np.ndarray, radius: int = 2) -> np.ndarray:
    arr = values.astype(float).copy()
    if radius <= 0:
        return arr
    out = np.full_like(arr, np.nan)
    for i in range(len(arr)):
        lo = max(0, i - radius)
        hi = min(len(arr), i + radius + 1)
        if np.isfinite(arr[lo:hi]).any():
            out[i] = np.nanmean(arr[lo:hi])
    return out


def plane_angle(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    vec = a - b
    out = np.degrees(np.arctan2(vec[:, 1], vec[:, 0]))
    out[~np.isfinite(out)] = np.nan
    return out


def circular_abs_diff(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.abs((a - b + 180) % 360 - 180)


def frame_value(values: np.ndarray, frame: int, radius: int = 6) -> float:
    if frame < 0 or frame >= len(values):
        return float("nan")
    value = values[frame]
    if math.isfinite(float(value)):
        return float(value)
    for offset in range(1, radius + 1):
        for idx in (frame - offset, frame + offset):
            if 0 <= idx < len(values) and math.isfinite(float(values[idx])):
                return float(values[idx])
    return float("nan")


def estimate_floor_height(trial, clean_labels: list[str]) -> tuple[float, float]:
    foot = safe_nanmean([marker(trial, clean_labels, n) for n in ("LHEE", "LTOE", "RHEE", "RTOE", "LANK", "RANK")], axis=0)
    floor = float(np.nanpercentile(foot[:, 2], 1) - 30.0)
    head = safe_nanmean([marker(trial, clean_labels, n) for n in ("LFHD", "RFHD", "LBHD", "RBHD")], axis=0)
    height = float(np.nanmedian(head[:, 2]) - floor)
    return floor, height


def detect_events(trial, clean_labels: list[str], floor_mm: float) -> dict[str, int]:
    lkne_z = smooth(marker(trial, clean_labels, "LKNE")[:, 2], 2)
    peak = int(np.nanargmax(lkne_z))
    lfoot = safe_nanmean([marker(trial, clean_labels, "LHEE"), marker(trial, clean_labels, "LTOE")], axis=0)
    lfoot_z = smooth(lfoot[:, 2], 2)
    foot_speed = smooth(speed_mps(lfoot, trial.rate_hz), 2)
    contact_candidates = np.where((np.arange(len(lfoot_z)) > peak + 10) & (lfoot_z <= floor_mm + 70))[0]
    contact = int(contact_candidates[0]) if contact_candidates.size else min(len(lfoot_z) - 1, peak + int(1.0 * trial.rate_hz))
    plant = contact
    search_end = min(len(lfoot_z), contact + int(0.28 * trial.rate_hz))
    stable = np.where((np.arange(len(lfoot_z)) >= contact) & (np.arange(len(lfoot_z)) < search_end) & (foot_speed <= 0.75))[0]
    if stable.size:
        plant = int(stable[min(len(stable) - 1, 3)])
    else:
        plant = min(search_end - 1, contact + int(0.14 * trial.rate_hz))
    hand = safe_nanmean([marker(trial, clean_labels, "RWRA"), marker(trial, clean_labels, "RWRB"), marker(trial, clean_labels, "RFIN")], axis=0)
    hand_speed = smooth(speed_mps(hand, trial.rate_hz), 2)
    rel_start = plant
    rel_end = min(len(hand_speed), plant + int(0.55 * trial.rate_hz))
    window = hand_speed[rel_start:rel_end]
    release = rel_start + int(np.nanargmax(window)) if np.isfinite(window).any() else min(len(hand_speed) - 1, plant + int(0.2 * trial.rate_hz))
    return {"peak_knee": peak, "foot_contact": contact, "foot_plant": plant, "release": release}


def compute_values(trial, clean_labels: list[str], events: dict[str, int], floor_mm: float, height_mm: float) -> dict[str, float]:
    pk = events["peak_knee"]
    fc = events["foot_contact"]
    fp = events["foot_plant"]
    rel = events["release"]

    lhip, rhip = marker(trial, clean_labels, "LASI", "LPSI"), marker(trial, clean_labels, "RASI", "RPSI")
    lsho, rsho = marker(trial, clean_labels, "LSHO"), marker(trial, clean_labels, "RSHO")
    hss = circular_abs_diff(plane_angle(rsho, lsho), plane_angle(rhip, lhip))
    lkne = marker(trial, clean_labels, "LKNE")
    lhee, ltoe = marker(trial, clean_labels, "LHEE"), marker(trial, clean_labels, "LTOE")
    rhee, rtoe = marker(trial, clean_labels, "RHEE"), marker(trial, clean_labels, "RTOE")
    relb, rsho_m = marker(trial, clean_labels, "RELB"), marker(trial, clean_labels, "RSHO")
    rwrist = marker(trial, clean_labels, "RWRA", "RWRB")
    rfin = marker(trial, clean_labels, "RFIN")
    hand = safe_nanmean([rwrist, rfin], axis=0)
    hand_speed = smooth(speed_mps(hand, trial.rate_hz), 2)
    rear_foot_pk = safe_nanmean([rhee[pk], rtoe[pk]], axis=0)
    stride_vec = lhee[fp] - rear_foot_pk
    toe_vec = ltoe[fp] - lhee[fp]
    forearm = rwrist[rel] - relb[rel]
    forearm_horizontal = float(np.linalg.norm(forearm[:2]))
    arm_slot = float(np.degrees(np.arctan2(forearm[2], forearm_horizontal))) if math.isfinite(forearm_horizontal) else float("nan")
    hss_window = hss[pk : rel + 1] if rel > pk else hss
    hss_max = float(np.nanmax(hss_window)) if np.isfinite(hss_window).any() else float("nan")
    hss_max_idx = pk + int(np.nanargmax(hss_window)) if np.isfinite(hss_window).any() and rel > pk else int(np.nanargmax(hss))
    hss_rel = frame_value(hss, rel)
    return {
        "knee_height_pct": (frame_value(lkne[:, 2], pk) - floor_mm) / height_mm * 100,
        "knee_height_mm": frame_value(lkne[:, 2], pk) - floor_mm,
        "front_knee_peak_deg": frame_value(channel(trial, clean_labels, "LKneeAngles", 0), pk),
        "front_hip_peak_deg": frame_value(channel(trial, clean_labels, "LHipAngles", 0), pk),
        "rear_knee_peak_deg": frame_value(channel(trial, clean_labels, "RKneeAngles", 0), pk),
        "rear_ankle_peak_deg": frame_value(channel(trial, clean_labels, "RAnkleAngles", 0), pk),
        "hss_peak_knee_deg": frame_value(hss, pk),
        "stride_distance_pct": float(np.linalg.norm(stride_vec[:2]) / height_mm * 100),
        "stride_distance_mm": float(np.linalg.norm(stride_vec[:2])),
        "stride_direction_deg": float(np.degrees(np.arctan2(stride_vec[1], stride_vec[0]))),
        "front_toe_direction_deg": float(np.degrees(np.arctan2(toe_vec[1], toe_vec[0]))),
        "front_knee_plant_deg": frame_value(channel(trial, clean_labels, "LKneeAngles", 0), fp),
        "rear_knee_plant_deg": frame_value(channel(trial, clean_labels, "RKneeAngles", 0), fp),
        "elbow_vs_shoulder_cm": float((relb[fp, 2] - rsho_m[fp, 2]) / 10.0),
        "wrist_vs_shoulder_cm": float((rwrist[fp, 2] - rsho_m[fp, 2]) / 10.0),
        "elbow_flex_plant_deg": frame_value(channel(trial, clean_labels, "RElbowAngles", 0), fp),
        "shoulder_abduction_plant_deg": frame_value(channel(trial, clean_labels, "RShoulderAngles", 1), fp),
        "hss_plant_deg": frame_value(hss, fp),
        "front_knee_release_deg": frame_value(channel(trial, clean_labels, "LKneeAngles", 0), rel),
        "front_knee_change_plant_to_release_deg": frame_value(channel(trial, clean_labels, "LKneeAngles", 0), rel) - frame_value(channel(trial, clean_labels, "LKneeAngles", 0), fp),
        "front_knee_change_contact_to_release_deg": frame_value(channel(trial, clean_labels, "LKneeAngles", 0), rel) - frame_value(channel(trial, clean_labels, "LKneeAngles", 0), fc),
        "rear_knee_release_deg": frame_value(channel(trial, clean_labels, "RKneeAngles", 0), rel),
        "shoulder_abduction_release_deg": frame_value(channel(trial, clean_labels, "RShoulderAngles", 1), rel),
        "shoulder_rotation_release_deg": frame_value(channel(trial, clean_labels, "RShoulderAngles", 2), rel),
        "elbow_flex_release_deg": frame_value(channel(trial, clean_labels, "RElbowAngles", 0), rel),
        "wrist_flex_release_deg": frame_value(channel(trial, clean_labels, "RWristAngles", 0), rel),
        "arm_slot_deg": arm_slot,
        "release_height_pct": float((rfin[rel, 2] - floor_mm) / height_mm * 100),
        "release_height_mm": float(rfin[rel, 2] - floor_mm),
        "release_lateral_mm": float(rfin[rel, 1]),
        "release_forward_mm": float(rfin[rel, 0]),
        "hss_release_deg": hss_rel,
        "hand_speed_mps": frame_value(hand_speed, rel),
        "max_hss_deg": hss_max,
        "max_hss_time_s": hss_max_idx / trial.rate_hz,
        "hss_release_amount_deg": hss_max - hss_rel,
        "peak_knee_time_s": pk / trial.rate_hz,
        "foot_contact_time_s": fc / trial.rate_hz,
        "foot_plant_time_s": fp / trial.rate_hz,
        "release_time_s": rel / trial.rate_hz,
    }


def load_trial_bundle(key: str, name: str, role: str, path: Path) -> TrialBundle:
    trial = read_c3d(path)
    labels = [clean_label(label) for label in trial.labels]
    floor, height = estimate_floor_height(trial, labels)
    events = detect_events(trial, labels, floor)
    values = compute_values(trial, labels, events, floor, height)
    return TrialBundle(key, name, role, path, trial, labels, events, values, height, floor)


def fmt(value: float, unit: str) -> str:
    if not finite(value):
        return "N/A"
    if unit == "deg":
        return f"{value:.1f}°"
    if unit == "pct":
        return f"{value:.1f}%"
    if unit == "mm":
        return f"{value:.0f} mm"
    if unit == "cm":
        return f"{value:.1f} cm"
    if unit == "mps":
        return f"{value:.2f} m/s"
    if unit == "s":
        return f"{value:.2f}s"
    return f"{value:.1f}"


def score_metric(value: float, metric: dict[str, object], coach_value: float | None = None) -> float:
    if not finite(value):
        return 45
    ideal = metric.get("ideal")
    lo = metric.get("lo")
    hi = metric.get("hi")
    direction = metric.get("direction", "target")
    if finite(ideal):
        spread = float(metric.get("spread", max(abs(float(ideal)) * 0.35, 8)))
        return max(0, min(100, 100 - abs(value - float(ideal)) / spread * 45))
    if finite(lo) and finite(hi):
        lo_f, hi_f = float(lo), float(hi)
        if lo_f <= value <= hi_f:
            return 88
        dist = min(abs(value - lo_f), abs(value - hi_f))
        return max(35, 88 - dist / max(abs(hi_f - lo_f), 1) * 60)
    if direction == "higher":
        target = float(metric.get("target", coach_value if finite(coach_value) else value))
        return max(35, min(100, 60 + value / max(target, 1) * 35))
    if direction == "lower_abs":
        return max(35, min(100, 100 - abs(value) / float(metric.get("spread", 30)) * 60))
    return 72


def status_from_score(score: float) -> tuple[str, str]:
    if score >= 82:
        return "优秀", "good"
    if score >= 66:
        return "良好", "review"
    return "待提高", "risk"


METRICS = [
    {"key": "knee_height_pct", "event": "准备阶段", "section": "抬腿最高点", "name": "抬腿高度", "unit": "pct", "image": "peak_knee", "ideal": 50, "spread": 18, "copy": "抬腿高度接近身高一半，说明准备阶段有足够的节奏和空间。"},
    {"key": "front_knee_peak_deg", "event": "准备阶段", "section": "抬腿最高点", "name": "前腿收紧", "unit": "deg", "image": "peak_knee", "lo": 115, "hi": 155, "copy": "前膝角用来判断抬腿时前腿是否真正收住，而不是松散地向前摆。"},
    {"key": "rear_knee_peak_deg", "event": "准备阶段", "section": "抬腿最高点", "name": "后腿蓄力", "unit": "deg", "image": "peak_knee", "lo": -10, "hi": 25, "copy": "后腿在抬腿最高点承担支撑任务，角度越稳定，后续跨步越容易受控。"},
    {"key": "stride_distance_pct", "event": "前脚落地", "section": "落脚质量", "name": "跨步距离", "unit": "pct", "image": "foot_plant", "ideal": 55, "spread": 22, "copy": "跨步距离用身高归一化，帮助判断身体推进是否足够。"},
    {"key": "stride_direction_deg", "event": "前脚落地", "section": "落脚质量", "name": "跨步方向", "unit": "deg", "image": "foot_plant", "ideal": 0, "spread": 35, "copy": "跨步方向越接近目标线，身体越容易把力量送向投球方向。"},
    {"key": "front_knee_plant_deg", "event": "前脚落地", "section": "落地支撑", "name": "前膝屈曲", "unit": "deg", "image": "foot_plant", "lo": 40, "hi": 70, "copy": "前脚落地后的前膝角代表前腿支撑质量，过软或过硬都会影响传力。"},
    {"key": "rear_knee_plant_deg", "event": "前脚落地", "section": "落地支撑", "name": "后膝屈曲", "unit": "deg", "image": "foot_plant", "lo": 35, "hi": 75, "copy": "后膝角反映后腿是否还在参与推进，而不是提前失去下肢连接。"},
    {"key": "elbow_vs_shoulder_cm", "event": "前脚落地", "section": "手臂到位", "name": "投球肘相对肩线", "unit": "cm", "image": "foot_plant", "ideal": 0, "spread": 18, "copy": "负值表示肘低于肩线，前脚落地时肘的位置会影响后续出手路径。"},
    {"key": "shoulder_abduction_plant_deg", "event": "前脚落地", "section": "手臂到位", "name": "肩外展", "unit": "deg", "image": "foot_plant", "lo": 70, "hi": 100, "copy": "肩外展帮助判断投球手臂是否在落地时及时进入准备位置。"},
    {"key": "front_knee_release_deg", "event": "出手点", "section": "前腿制动", "name": "出手前膝角", "unit": "deg", "image": "release", "lo": 40, "hi": 75, "copy": "出手时前腿能否稳住，是身体传力到手臂的重要前提。"},
    {"key": "front_knee_change_plant_to_release_deg", "event": "出手点", "section": "前腿制动", "name": "落地到出手前膝变化", "unit": "deg", "image": "release", "ideal": 0, "spread": 18, "copy": "这个变化量越小，说明前腿在落地后越能保持支撑。"},
    {"key": "shoulder_abduction_release_deg", "event": "出手点", "section": "出手角度", "name": "出手肩外展", "unit": "deg", "image": "release", "lo": 80, "hi": 105, "copy": "出手时上臂抬起角度决定手臂路径和出手槽位。"},
    {"key": "elbow_flex_release_deg", "event": "出手点", "section": "出手角度", "name": "出手肘屈曲", "unit": "deg", "image": "release", "lo": 60, "hi": 95, "copy": "肘屈曲角用于观察出手时手臂是否有足够延展和控制。"},
    {"key": "arm_slot_deg", "event": "出手点", "section": "出手角度", "name": "Arm slot", "unit": "deg", "image": "release", "lo": 55, "hi": 85, "copy": "Arm slot 描述前臂抬升方向，是观察投球手臂槽位的核心指标。"},
    {"key": "release_height_pct", "event": "出手点", "section": "出手点", "name": "出手高度", "unit": "pct", "image": "release", "lo": 85, "hi": 105, "copy": "用右手手指 marker 近似出手点高度，后续有球 marker 时可再校准。"},
    {"key": "hand_speed_mps", "event": "出手点", "section": "出手点", "name": "手速", "unit": "mps", "image": "release", "direction": "higher", "copy": "手速不是球速，但能作为同一套 Vicon 数据中的出手强度参考。"},
    {"key": "max_hss_deg", "event": "专项问题", "section": "身体带动程度", "name": "最大髋肩分离", "unit": "deg", "image": "release", "lo": 15, "hi": 35, "copy": "最大髋肩分离越清楚，说明身体有更明显的先后顺序。"},
    {"key": "hss_release_amount_deg", "event": "专项问题", "section": "身体带动程度", "name": "髋肩分离释放量", "unit": "deg", "image": "release", "lo": 8, "hi": 24, "copy": "释放量表示从最大分离到出手时释放了多少躯干旋转空间。"},
]


def write_metric_csv(bundles: list[TrialBundle]) -> None:
    rows = []
    for b in bundles:
        for metric in METRICS:
            rows.append(
                {
                    "athlete": b.name,
                    "role": b.role,
                    "metric_key": metric["key"],
                    "event": metric["event"],
                    "section": metric["section"],
                    "metric_name": metric["name"],
                    "value": b.values.get(metric["key"], float("nan")),
                    "unit": metric["unit"],
                }
            )
    path = OUT_DIR / "pitch_metrics_all_players.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def copy_static_assets() -> None:
    (ASSET_DIR / "lineart_actions").mkdir(parents=True, exist_ok=True)
    if PREV_PITCH_ASSETS is None:
        return
    src_lineart = PREV_PITCH_ASSETS / "lineart_actions"
    for name in (
        "pitch_peak_knee_lineart.png",
        "pitch_foot_plant_lineart.png",
        "pitch_release_lineart.png",
        "pitch_peak_knee_lineart_metrics.png",
        "pitch_foot_plant_lineart_metrics.png",
        "pitch_release_lineart_metrics.png",
    ):
        if (src_lineart / name).exists():
            shutil.copy2(src_lineart / name, ASSET_DIR / "lineart_actions" / name)
    (ASSET_DIR / "vicon_reconstruction_events").mkdir(parents=True, exist_ok=True)
    prev_vicon = PREV_PITCH_ASSETS / "vicon_reconstruction_events"
    for name in ("julian_peak_knee.gif", "julian_foot_plant.gif", "julian_release.gif", "julian_peak_knee.png", "julian_foot_plant.png", "julian_release.png"):
        if (prev_vicon / name).exists():
            shutil.copy2(prev_vicon / name, ASSET_DIR / "vicon_reconstruction_events" / name)


def render_trial_png(bundle: TrialBundle, frame: int, out: Path, title: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    points = recon.trial_frame_points(bundle.trial, frame, smooth_radius=2)
    fig = plt.figure(figsize=recon.RENDER_FIGSIZE, dpi=recon.RENDER_DPI)
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_subplot(111, projection="3d")
    recon.draw_reconstruction(
        ax,
        points,
        zh_font_prop(),
        title,
        frame_label=f"frame {frame} / {frame / bundle.trial.rate_hz:.2f}s",
        show_labels=False,
        fixed_layout_legend=True,
    )
    fig.tight_layout(rect=[0.02, 0.02, 0.98, 0.94])
    fig.savefig(out, bbox_inches="tight", facecolor="#ffffff")
    plt.close(fig)


def render_reference_images(bundles: list[TrialBundle]) -> None:
    lookup = {b.key: b for b in bundles}
    render_trial_png(lookup["julian"], lookup["julian"].events["release"], ASSET_DIR / "vicon_reconstruction_events" / "julian_release_reference.png", "Julian pitching release reference")
    render_trial_png(lookup["coach"], lookup["coach"].events["release"], ASSET_DIR / "vicon_reconstruction_events" / "coach_release_reference.png", "Coach pitching release reference")


def metric_label(value: float, suffix: str) -> str:
    if not finite(value):
        return "N/A"
    sep = "" if suffix == "%" else " "
    return f"{value:.1f}{sep}{suffix}".strip()


def render_movement_panel(bundle: TrialBundle, frame: int, trajectory: np.ndarray, title: str, subtitle: str) -> Image.Image:
    points = recon.trial_frame_points(bundle.trial, frame, smooth_radius=2)
    fig = plt.figure(figsize=(10.8, 7.2), dpi=120)
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_subplot(111, projection="3d")
    recon.draw_reconstruction(
        ax,
        points,
        zh_font_prop(),
        title,
        frame_label=f"{subtitle} | frame {frame} / {frame / bundle.trial.rate_hz:.2f}s",
        show_labels=False,
        fixed_layout_legend=True,
    )
    visible_points = np.asarray([p for p in points.values() if np.isfinite(p).all()], dtype=float)
    if len(visible_points):
        ax.scatter(
            visible_points[:, 0],
            visible_points[:, 1],
            visible_points[:, 2],
            s=34,
            c="#0057ff",
            edgecolors="#ffffff",
            linewidths=0.55,
            depthshade=False,
            zorder=10,
        )
    if trajectory.size:
        trail = trajectory[np.isfinite(trajectory).all(axis=1)]
        if len(trail) >= 2:
            ax.plot(trail[:, 0], trail[:, 1], trail[:, 2], color="#16803a", linewidth=3.0, label="RFIN手部轨迹")
    handles = [
        Line2D([0], [0], color="#16803a", lw=3.0, label="RFIN手部轨迹"),
        Line2D([0], [0], color="red", lw=2.0, label="身体骨架"),
    ]
    ax.legend(handles=handles, loc="upper right", frameon=True, prop=zh_font_prop(), fontsize=9)
    fig.tight_layout(rect=[0.20, 0.03, 0.98, 0.94])
    canvas = FigureCanvasAgg(fig)
    canvas.draw()
    rgba = np.asarray(canvas.buffer_rgba())
    plot = Image.fromarray(rgba).convert("RGB")
    plt.close(fig)

    draw = ImageDraw.Draw(plot)
    title_font = pil_font(24)
    value_font = pil_font(28)
    small_font = pil_font(17)
    cards = (
        ("Hand speed", metric_label(bundle.values.get("hand_speed_mps", float("nan")) * 3.6, "km/h")),
        ("Rotation angle", metric_label(bundle.values.get("hss_release_deg", float("nan")), "deg")),
        ("Release height", metric_label(bundle.values.get("release_height_pct", float("nan")), "%")),
    )
    x0, y0, w, h = 26, 250, 250, 96
    for idx, (label, value) in enumerate(cards):
        y = y0 + idx * 124
        draw.rounded_rectangle((x0, y, x0 + w, y + h), radius=8, fill="#ffffff", outline="#cfd6e1", width=2)
        draw.text((x0 + 28, y + 17), label, font=title_font, fill="#667085")
        draw.text((x0 + 28, y + 42), value, font=value_font, fill="#111827")
        draw.text((x0 + 28, y + 73), f"frame {frame}", font=small_font, fill="#94a3b8")
    return plot


def render_movement_gif(bundle: TrialBundle, out: Path, title: str, subtitle: str) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    release = bundle.events["release"]
    start = max(0, release - int(0.55 * bundle.trial.rate_hz))
    frames = np.linspace(start, release, 18).astype(int)
    rfin = marker(bundle.trial, bundle.clean_labels, "RFIN")
    images: list[Image.Image] = []
    for frame in frames:
        trail_start = max(0, frame - int(0.45 * bundle.trial.rate_hz))
        trail = rfin[trail_start : frame + 1]
        images.append(render_movement_panel(bundle, int(frame), trail, title, subtitle))
    images[-1].save(out.with_suffix(".png"))
    images[0].save(out, save_all=True, append_images=images[1:], duration=110, loop=0, optimize=False)


def render_movement_gifs(bundles: list[TrialBundle]) -> None:
    lookup = {b.key: b for b in bundles}
    render_movement_gif(lookup["julian"], ASSET_DIR / "vicon_reconstruction_events" / "julian_player_movement.gif", "球员动作 Player Movement", "Julian / 投球 / C3D骨架动画")
    render_movement_gif(lookup["coach"], ASSET_DIR / "vicon_reconstruction_events" / "coach_player_movement.gif", "教练动作 Coach Movement", "Coach / 投球 / C3D骨架动画")


def make_metric_illustrations(bundles: list[TrialBundle]) -> None:
    out_dir = ASSET_DIR / "frontend_metric_illustrations_pitch"
    out_dir.mkdir(parents=True, exist_ok=True)
    source_map = {
        "peak_knee": ASSET_DIR / "lineart_actions" / "pitch_peak_knee_lineart_metrics.png",
        "foot_plant": ASSET_DIR / "lineart_actions" / "pitch_foot_plant_lineart_metrics.png",
        "release": ASSET_DIR / "lineart_actions" / "pitch_release_lineart_metrics.png",
    }
    missing = [path for path in source_map.values() if not path.exists()]
    if missing:
        print("Skipping pitching metric illustrations; missing line-art inputs:")
        for path in missing:
            print(" -", path)
        return
    julian = next(b for b in bundles if b.key == "julian")
    title_font = pil_font(32, bold=True)
    value_font = pil_font(28, bold=True)
    small_font = pil_font(22)
    for metric in METRICS:
        base = Image.open(source_map[str(metric["image"])]).convert("RGB")
        base.thumbnail((520, 360), Image.Resampling.LANCZOS)
        canvas = Image.new("RGB", (640, 640), "#fffdf8")
        draw = ImageDraw.Draw(canvas)
        x = (640 - base.width) // 2
        canvas.paste(base, (x, 104))
        color = BLUE if metric["image"] == "peak_knee" else ORANGE if metric["image"] == "foot_plant" else PURPLE
        draw.rounded_rectangle((28, 28, 612, 92), radius=18, fill="white", outline=color, width=3)
        draw.text((48, 42), str(metric["name"]), font=title_font, fill=INK)
        value = julian.values.get(str(metric["key"]), float("nan"))
        draw.text((390, 45), fmt(value, str(metric["unit"])), font=value_font, fill=color)
        draw.rounded_rectangle((34, 548, 606, 608), radius=16, fill="#f8fafc", outline="#d0d5dd", width=2)
        draw.text((54, 565), str(metric["section"]), font=small_font, fill=MID)
        canvas.save(out_dir / f"{metric['key']}.png")


def make_kinetic_chain(bundles: list[TrialBundle]) -> None:
    julian = next(b for b in bundles if b.key == "julian")
    out = ASSET_DIR / "kinetic_chain" / "julian_pitch_kinetic_chain_flow.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 760), "#ffffff")
    draw = ImageDraw.Draw(img)
    title_font = pil_font(48, bold=True)
    node_font = pil_font(30, bold=True)
    small_font = pil_font(24)
    draw.text((70, 58), "Julian 投球动力链", font=title_font, fill=INK)
    draw.text((72, 124), "后腿支撑 -> 骨盆/髋部 -> 躯干 -> 手臂 -> 手部速度。重点看顺序是否完整，以及髋肩分离是否形成后被释放。", font=small_font, fill=MID)
    nodes = [
        ("后腿", "抬腿蓄力", julian.values["rear_knee_peak_deg"], "deg", GREEN),
        ("骨盆", "跨步推进", julian.values["stride_distance_pct"], "pct", BLUE),
        ("躯干", "最大髋肩分离", julian.values["max_hss_deg"], "deg", PURPLE),
        ("手臂", "Arm slot", julian.values["arm_slot_deg"], "deg", ORANGE),
        ("手部", "手速", julian.values["hand_speed_mps"], "mps", RED),
    ]
    xs = [150, 460, 770, 1080, 1390]
    y = 330
    for i, (label, sub, val, unit, color) in enumerate(nodes):
        x = xs[i]
        draw.ellipse((x - 95, y - 95, x + 95, y + 95), fill="#f8fafc", outline=color, width=7)
        draw.text((x - 42, y - 42), label, font=node_font, fill=INK)
        draw.text((x - 66, y + 2), sub, font=small_font, fill=MID)
        draw.text((x - 54, y + 42), fmt(val, unit), font=small_font, fill=color)
        if i < len(xs) - 1:
            draw.line((x + 108, y, xs[i + 1] - 108, y), fill="#98a2b3", width=7)
            draw.polygon([(xs[i + 1] - 118, y - 16), (xs[i + 1] - 92, y), (xs[i + 1] - 118, y + 16)], fill="#98a2b3")
    callouts = [
        f"抬腿最高点 {fmt(julian.values['peak_knee_time_s'], 's')}",
        f"前脚落地 {fmt(julian.values['foot_plant_time_s'], 's')}",
        f"出手点 {fmt(julian.values['release_time_s'], 's')}",
        f"髋肩分离释放量 {fmt(julian.values['hss_release_amount_deg'], 'deg')}",
    ]
    cx = 88
    for item in callouts:
        w = draw.textlength(item, font=small_font) + 42
        draw.rounded_rectangle((cx, 610, cx + w, 662), radius=999, fill="#eef6ff", outline="#bfdbfe", width=2)
        draw.text((cx + 20, 624), item, font=small_font, fill="#1d4ed8")
        cx += int(w + 18)
    img.save(out)


def peer_stats(bundles: list[TrialBundle], metric_key: str) -> dict[str, float]:
    students = [b for b in bundles if b.role == "student"]
    values = [b.values.get(metric_key, float("nan")) for b in students]
    values = [float(v) for v in values if finite(v)]
    return {
        "min": min(values) if values else float("nan"),
        "max": max(values) if values else float("nan"),
        "mean": float(np.mean(values)) if values else float("nan"),
    }


def group_mean_all(bundles: list[TrialBundle], metric_key: str) -> float:
    vals = [b.values.get(metric_key, float("nan")) for b in bundles if b.role == "student"]
    vals = [float(v) for v in vals if finite(v)]
    return float(np.mean(vals)) if vals else float("nan")


def range_html(metric: dict[str, object], bundles: list[TrialBundle], show_all: bool = False) -> str:
    key = str(metric["key"])
    unit = str(metric["unit"])
    julian = next(b for b in bundles if b.key == "julian")
    stats = peer_stats(bundles, key)
    mn, mx, jv = stats["min"], stats["max"], julian.values.get(key, float("nan"))
    if not (finite(mn) and finite(mx) and finite(jv)):
        return '<div class="peer-empty">同组区间暂不可用</div>'
    span = max(mx - mn, 1e-6)
    left = max(0, min(100, (jv - mn) / span * 100))
    dots = [f'<span class="peer-dot julian" style="left:{left:.2f}%" title="Julian: {esc(fmt(jv, unit))}"></span>']
    if show_all:
        colors = [BLUE, GREEN, ORANGE, PURPLE, RED, "#0891b2", "#ca8a04"]
        for idx, b in enumerate(bundles):
            val = b.values.get(key, float("nan"))
            if not finite(val):
                continue
            pos = max(0, min(100, (val - mn) / span * 100))
            dots.append(f'<span class="peer-dot" style="left:{pos:.2f}%; background:{colors[idx % len(colors)]}" title="{esc(b.name)}: {esc(fmt(val, unit))}"></span>')
    return f"""
      <div class="peer-range">
        <div class="peer-label">同组区间</div>
        <div class="peer-min">{esc(fmt(mn, unit))}</div>
        <div class="peer-track"><span class="peer-span" style="left:0%; width:100%"></span>{''.join(dots)}</div>
        <div class="peer-max">{esc(fmt(mx, unit))}</div>
      </div>
    """


def metric_card(metric: dict[str, object], bundles: list[TrialBundle], coach: TrialBundle, coach_mode: bool = False) -> str:
    julian = next(b for b in bundles if b.key == "julian")
    key = str(metric["key"])
    unit = str(metric["unit"])
    value = julian.values.get(key, float("nan"))
    coach_value = coach.values.get(key, float("nan"))
    score = score_metric(value, metric, coach_value)
    label, klass = status_from_score(score)
    mean = group_mean_all(bundles, key)
    img = f"assets/frontend_metric_illustrations_pitch/{key}.png"
    compare = (
        f'<p class="metric-detail-en">测试组均值 {esc(fmt(mean, unit))} · Coach {esc(fmt(coach_value, unit))} · 优秀学员 Julian {esc(fmt(value, unit))}</p>'
        if coach_mode
        else ""
    )
    return f"""
    <article class="metric-card {klass}">
      <div class="metric-summary">
        <span class="badge {klass}">{esc(label)}</span>
        <div><h4>{esc(metric["name"])}</h4><p class="metric-en">{esc(metric["event"])} / {esc(metric["section"])}</p></div>
        <div class="metric-value">{esc(fmt(value, unit))}</div>
      </div>
      <figure class="metric-illustration"><img src="{esc(img)}" alt="{esc(metric['name'])} 指标示意图" loading="lazy"></figure>
      <div class="metric-detail">
        <p class="metric-detail-cn">{esc(metric["copy"])}</p>
        {compare}
        {range_html(metric, bundles, show_all=coach_mode)}
      </div>
    </article>
    """


def section_cards(section: str, bundles: list[TrialBundle], coach: TrialBundle, coach_mode: bool = False) -> str:
    return "\n".join(metric_card(m, bundles, coach, coach_mode) for m in METRICS if m["section"] == section or m["event"] == section)


def render_section(title: str, subtitle: str, metrics: list[dict[str, object]], bundles: list[TrialBundle], coach: TrialBundle, image: str | None = None) -> str:
    cards = "\n".join(metric_card(m, bundles, coach, False) for m in metrics)
    annotation = ""
    if image:
        annotation = f"""
        <figure class="section-annotation">
          <img src="{esc(image)}" alt="{esc(title)} 动作标注" loading="lazy">
          <figcaption><b>{esc(title)}动作参考</b><span>{esc(subtitle)}</span></figcaption>
        </figure>
        """
    return f"""
    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>投球动作与教练对照</h2></div>
      <div class="grid-2">
        <article class="visual-card">
          <h4>Julian 出手点 Vicon 标注</h4>
          <figure class="reconstruction-annotated">
            <img src="assets/vicon_reconstruction_events/julian_player_movement.gif" alt="Julian 投球出手点 Vicon 动画重建" loading="lazy">
            <figcaption>
              <b>Julian 投球动作出手点</b>
              <span class="caption-cn">当前出手点主要看前腿支撑、肩外展、肘屈曲、手臂槽位和手速。Julian 的动作链已经具备基础，重点是让前脚落地后的身体传力更清楚。</span>
            </figcaption>
          </figure>
        </article>
        <article class="visual-card">
          <h4>教练技术参考</h4>
          <figure class="reconstruction-annotated">
            <img src="assets/vicon_reconstruction_events/coach_player_movement.gif" alt="教练投球出手点 Vicon 动画重建" loading="lazy">
            <figcaption>
              <b>教练投球动作参考</b>
              <span class="caption-cn">教练画面用于理解目标动作节奏，不作为硬性复制标准。报告里的教练数值会在教练视角里作为参考列展示。</span>
            </figcaption>
          </figure>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>2D 视频与 Vicon 对齐</h2></div>
      <div class="motion-stage-list">
        <article class="motion-stage-card">
          <figure class="motion-3d-panel">
            <h4>动作姿态<span>Posture</span></h4>
            <img src="assets/vicon_reconstruction_events/julian_peak_knee.gif" alt="Julian 抬腿最高点 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/video_2d_alignment/julian_pitch_peak_knee_2d_overlay.png" alt="Julian 抬腿最高点 2D 几何标注" loading="lazy">
          </figure>
        </article>
        <article class="motion-stage-card">
          <figure class="motion-3d-panel">
            <h4>动作姿态<span>Posture</span></h4>
            <img src="assets/vicon_reconstruction_events/julian_foot_plant.gif" alt="Julian 前脚落地 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/video_2d_alignment/julian_pitch_foot_plant_2d_overlay.png" alt="Julian 前脚落地 2D 几何标注" loading="lazy">
          </figure>
        </article>
        <article class="motion-stage-card">
          <figure class="motion-3d-panel">
            <h4>动作姿态<span>Posture</span></h4>
            <img src="assets/vicon_reconstruction_events/julian_release.gif" alt="Julian 出手点 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/video_2d_alignment/julian_pitch_release_2d_overlay.png" alt="Julian 出手点 2D 几何标注" loading="lazy">
          </figure>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>Julian 投球动力链</h2></div>
      <article class="visual-card kinetic-chain-card">
        <h4>后腿 -> 骨盆 -> 躯干 -> 手臂 -> 手</h4>
        <figure class="kinetic-chain-figure">
          <img src="assets/kinetic_chain/julian_pitch_kinetic_chain_flow.png" alt="Julian 投球动力链图" loading="lazy">
        </figure>
        <p class="copy-cn">动力链解读：Julian 的抬腿高度和出手高度都比较清楚，说明动作有完整的准备和释放阶段。需要继续关注的是前脚落地后，髋肩分离能否更稳定地形成并释放，避免动作变成手臂先抢出手。</p>
        <p class="copy-en">Kinetic-chain read: Julian shows clear preparation and release positions. The next coaching focus is whether hip-shoulder separation forms and releases after foot plant instead of the arm rushing ahead.</p>
      </article>
    </section>

    {render_section("抬腿最高点", "准备阶段关键画面", event_groups["抬腿最高点"], bundles, coach, "assets/lineart_actions/pitch_peak_knee_lineart_metrics.png")}
    {render_section("前脚落地", "落脚质量、支撑和手臂到位", event_groups["前脚落地"], bundles, coach, "assets/lineart_actions/pitch_foot_plant_lineart_metrics.png")}
    {render_section("出手点", "前腿制动、出手角度和出手点", event_groups["出手点"], bundles, coach, "assets/lineart_actions/pitch_release_lineart_metrics.png")}

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>教练视角：专项问题</h2></div>
      <div class="module-note">
        <p class="module-note-cn">专项问题放在教练视角里：这里不再堆所有球员在球员视角的节点，而是把测试组均值、Coach 值、优秀学员 Julian 值和所有人节点集中展示，方便教练判断是否触发提醒。</p>
        <p class="module-note-en">Coach view keeps the detailed comparison nodes, group mean, Coach value, and Julian reference for issue diagnosis.</p>
      </div>
      <div class="grid issue-metrics">{coach_issue_cards(bundles, coach)}</div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>分析员视角：完整指标表</h2></div>
      <article class="visual-card">
        <h4>Julian、测试组均值与 Coach 对照</h4>
        <div class="table-wrap">
          <table>
            <thead><tr><th>事件</th><th>前端指标</th><th>Julian</th><th>测试组均值</th><th>Coach</th><th>解释</th></tr></thead>
            <tbody>{metric_rows_table(bundles)}</tbody>
          </table>
        </div>
        <p class="copy-cn">数据口径：全部来自用户提供的 C3D 文件。前脚接触/踏稳由 marker 高度和脚部速度近似，出手点由踏稳后投球手速度峰值近似，没有使用力板或球 marker。</p>
      </article>
    </section>
  </main>
</body>
</html>
"""


def write_json_summary(bundles: list[TrialBundle]) -> None:
    data = {
        "created_for": "Julian pitching report, template-matched coach metrics section",
        "assumptions": {
            "lead_leg": "L",
            "drive_leg": "R",
            "throwing_arm": "R",
            "coach_reference": "008-coach Cal 03 Pitch 07.c3d",
            "excellent_student_reference": "Julian",
            "events": "Peak knee height, foot contact/plant, release approximated from Vicon markers",
        },
        "athletes": [
            {
                "key": b.key,
                "name": b.name,
                "role": b.role,
                "source_file": str(b.path),
                "frames": int(b.trial.points.shape[0]),
                "rate_hz": float(b.trial.rate_hz),
                "height_estimate_mm": b.height_mm,
                "floor_estimate_mm": b.floor_mm,
                "events": b.events,
                "values": b.values,
            }
            for b in bundles
        ],
    }
    (OUT_DIR / "pitch_metrics_summary.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def render_html(bundles: list[TrialBundle]) -> str:
    existing = OUT_DIR / "index.html"
    if existing.exists():
        return existing.read_text(encoding="utf-8")
    raise RuntimeError("index.html is required for this template report rebuild")


def load_manifest(path: Path) -> list[tuple[str, str, str, Path]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data.get("athletes") if isinstance(data, dict) else data
    if not isinstance(rows, list) or not rows:
        raise ValueError("The pitching manifest must contain a non-empty athletes array.")
    result: list[tuple[str, str, str, Path]] = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            raise ValueError(f"athletes[{index}] must be an object")
        missing = [key for key in ("key", "name", "role", "c3d") if not row.get(key)]
        if missing:
            raise ValueError(f"athletes[{index}] is missing: {', '.join(missing)}")
        c3d = Path(str(row["c3d"]))
        if not c3d.is_absolute():
            c3d = (path.parent / c3d).resolve()
        if not c3d.exists():
            raise FileNotFoundError(f"C3D input not found: {c3d}")
        result.append((str(row["key"]), str(row["name"]), str(row["role"]), c3d))
    keys = {row[0] for row in result}
    if not {"julian", "coach"}.issubset(keys):
        raise ValueError("The current report schema requires athlete keys 'julian' and 'coach'.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the pitching C3D metrics/assets expected by the combined baseball report."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="JSON manifest describing athlete C3D inputs.")
    parser.add_argument("--template-dir", required=True, type=Path, help="Existing report template containing index.html and assets/.")
    parser.add_argument("--previous-assets", type=Path, default=None, help="Optional prior pitching assets to reuse.")
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "pitching")
    return parser.parse_args()


def main() -> None:
    global TEMPLATE_DIR, PREV_PITCH_ASSETS, OUT_DIR, ASSET_DIR, C3D_FILES
    args = parse_args()
    TEMPLATE_DIR = args.template_dir.resolve()
    PREV_PITCH_ASSETS = args.previous_assets.resolve() if args.previous_assets else None
    OUT_DIR = args.out_dir.resolve()
    ASSET_DIR = OUT_DIR / "assets"
    C3D_FILES = load_manifest(args.manifest.resolve())
    if not (TEMPLATE_DIR / "index.html").exists():
        raise FileNotFoundError(f"Template index.html not found under {TEMPLATE_DIR}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if TEMPLATE_DIR != OUT_DIR:
        shutil.copytree(TEMPLATE_DIR, OUT_DIR, dirs_exist_ok=True)
    copy_static_assets()
    bundles = [load_trial_bundle(*row) for row in C3D_FILES]
    render_reference_images(bundles)
    render_movement_gifs(bundles)
    make_metric_illustrations(bundles)
    make_kinetic_chain(bundles)
    write_metric_csv(bundles)
    write_json_summary(bundles)
    html_text = render_html(bundles)
    (OUT_DIR / "index.html").write_text(html_text, encoding="utf-8")
    prompt = ROOT / "prompts" / "pitch_report_generation.md"
    if prompt.exists():
        shutil.copy2(prompt, OUT_DIR / "PROMPT_USED.md")
    print(OUT_DIR / "index.html")


if __name__ == "__main__":
    main()
