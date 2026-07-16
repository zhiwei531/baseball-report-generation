from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import shutil
import subprocess
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
BUNDLED_LINEART_DIR = ROOT / "assets" / "pitching" / "lineart_actions"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
TEMPLATE_DIR: Path | None = None
PREV_PITCH_ASSETS: Path | None = None
OUT_DIR = ROOT / "reports" / "pitching"
ASSET_DIR = OUT_DIR / "assets"
PLAYER_KEY = "julian"
PLAYER_NAME = "Julian"
PLAYER_SLUG = "julian"

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

PEER_DISPLAY_NAMES = {
    "bryan": "Bryan陈柏谚",
    "7zai": "席启源",
    "xuanxuan": "姚槿宏",
    "green": "杜子墨",
    "julian": "Julian",
    "youyou": "费怡然",
    "james": "桑禹诚",
    "branden": "缪炜昱",
    "brandon": "缪炜昱",
}
PEER_COLORS = {
    "bryan": BLUE,
    "7zai": GREEN,
    "xuanxuan": ORANGE,
    "green": "#a855f7",
    "julian": RED,
    "youyou": "#0891b2",
    "james": "#ca8a04",
    "branden": "#344054",
    "brandon": "#344054",
}
PEER_KEY_ALIASES = {"brandon": "branden"}
PEER_LEGEND_ORDER = ("bryan", "7zai", "xuanxuan", "green", "julian", "youyou", "james", "branden")


def zh_font_prop() -> FontProperties | None:
    for path in (
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
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
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/PingFang.ttc"),
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
        # Store the report-facing release hand speed in km/h.  The source
        # derivative is mm/s, so speed_mps returns m/s and requires 3.6 here.
        "hand_speed_kmh": frame_value(hand_speed, rel) * 3.6,
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
        # Pitching distance/height measures are normalized by the athlete's
        # height.  Keep that meaning visible everywhere this formatter is
        # reused (cards, comparison pills, ranges, and issue summaries).
        return f"{value:.1f}%身高比"
    if unit == "mm":
        return f"{value:.0f} mm"
    if unit == "cm":
        return f"{value:.1f} cm"
    if unit == "kmh":
        return f"{value:.1f} km/h"
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
    {"key": "knee_height_pct", "event": "准备阶段", "section": "抬腿最高点", "name": "抬腿高度", "en": "Knee Lift Height", "unit": "pct", "image": "peak_knee", "ideal": 50, "spread": 18, "copy": "抬腿高度接近身高一半，说明准备阶段有足够的节奏和空间。"},
    {"key": "front_knee_peak_deg", "event": "准备阶段", "section": "抬腿最高点", "name": "前腿收紧", "en": "Lead-Knee Tuck", "unit": "deg", "image": "peak_knee", "lo": 115, "hi": 155, "copy": "前膝角用来判断抬腿时前腿是否真正收住，而不是松散地向前摆。"},
    {"key": "rear_knee_peak_deg", "event": "准备阶段", "section": "抬腿最高点", "name": "后腿蓄力", "en": "Rear-Leg Load", "unit": "deg", "image": "peak_knee", "lo": -10, "hi": 25, "copy": "后腿在抬腿最高点承担支撑任务，角度越稳定，后续跨步越容易受控。"},
    {"key": "stride_distance_pct", "event": "前脚落地", "section": "落脚质量", "name": "跨步距离", "en": "Stride Distance", "unit": "pct", "image": "foot_plant", "ideal": 55, "spread": 22, "copy": "跨步距离用身高归一化，帮助判断身体推进是否足够。"},
    {"key": "stride_direction_deg", "event": "前脚落地", "section": "落脚质量", "name": "跨步方向", "en": "Stride Direction", "unit": "deg", "image": "foot_plant", "ideal": 0, "spread": 35, "copy": "跨步方向越接近目标线，身体越容易把力量送向投球方向。"},
    {"key": "front_knee_plant_deg", "event": "前脚落地", "section": "落地支撑", "name": "前膝屈曲", "en": "Lead-Knee Flexion", "unit": "deg", "image": "foot_plant", "lo": 40, "hi": 70, "copy": "前脚落地后的前膝角代表前腿支撑质量，过软或过硬都会影响传力。"},
    {"key": "rear_knee_plant_deg", "event": "前脚落地", "section": "落地支撑", "name": "后膝屈曲", "en": "Rear-Knee Flexion", "unit": "deg", "image": "foot_plant", "lo": 35, "hi": 75, "copy": "后膝角反映后腿是否还在参与推进，而不是提前失去下肢连接。"},
    {"key": "elbow_vs_shoulder_cm", "event": "前脚落地", "section": "手臂到位", "name": "投球肘相对肩线", "en": "Throwing-Elbow Height", "unit": "cm", "image": "foot_plant", "ideal": 0, "spread": 18, "copy": "负值表示肘低于肩线，前脚落地时肘的位置会影响后续出手路径。"},
    {"key": "shoulder_abduction_plant_deg", "event": "前脚落地", "section": "手臂到位", "name": "肩外展", "en": "Shoulder Abduction", "unit": "deg", "image": "foot_plant", "lo": 70, "hi": 100, "copy": "肩外展帮助判断投球手臂是否在落地时及时进入准备位置。"},
    {"key": "front_knee_release_deg", "event": "出手点", "section": "前腿制动", "name": "出手前膝角", "en": "Release Lead-Knee Angle", "unit": "deg", "image": "release", "lo": 40, "hi": 75, "copy": "出手时前腿能否稳住，是身体传力到手臂的重要前提。"},
    {"key": "front_knee_change_plant_to_release_deg", "event": "出手点", "section": "前腿制动", "name": "落地到出手前膝变化", "en": "Lead-Knee Change: Plant to Release", "unit": "deg", "image": "release", "ideal": 0, "spread": 18, "copy": "这个变化量越小，说明前腿在落地后越能保持支撑。"},
    {"key": "shoulder_abduction_release_deg", "event": "出手点", "section": "出手角度", "name": "出手肩外展", "en": "Release Shoulder Abduction", "unit": "deg", "image": "release", "lo": 80, "hi": 105, "copy": "出手时上臂抬起角度决定手臂路径和出手槽位。"},
    {"key": "elbow_flex_release_deg", "event": "出手点", "section": "出手角度", "name": "出手肘屈曲", "en": "Release Elbow Flexion", "unit": "deg", "image": "release", "lo": 60, "hi": 95, "copy": "肘屈曲角用于观察出手时手臂是否有足够延展和控制。"},
    {"key": "arm_slot_deg", "event": "出手点", "section": "出手角度", "name": "出手手臂角度", "en": "Release Arm Angle", "unit": "deg", "image": "release", "lo": 55, "hi": 85, "copy": "出手手臂角度描述前臂抬升方向，是观察投球手臂出手路径的核心指标。"},
    {"key": "release_height_pct", "event": "出手点", "section": "出手点", "name": "出手高度", "en": "Release Height", "unit": "pct", "image": "release", "lo": 85, "hi": 105, "copy": "以投球手手部位置近似出手点高度；后续可结合实际出手位置继续校准。"},
    {"key": "hand_speed_kmh", "event": "出手点", "section": "出手点", "name": "出手手速", "en": "Release Hand Speed", "unit": "kmh", "image": "release", "direction": "higher", "copy": "出手手速不是球速，但能作为同一套 Vicon 数据中的出手强度参考。"},
    {"key": "max_hss_deg", "event": "专项问题", "section": "身体带动程度", "name": "最大髋肩分离", "en": "Maximum Hip-Shoulder Separation", "unit": "deg", "image": "release", "lo": 15, "hi": 35, "copy": "最大髋肩分离越清楚，说明身体有更明显的先后顺序。"},
    {"key": "hss_release_amount_deg", "event": "专项问题", "section": "身体带动程度", "name": "髋肩分离释放量", "en": "Hip-Shoulder Separation Release", "unit": "deg", "image": "release", "lo": 8, "hi": 24, "copy": "释放量表示从最大分离到出手时释放了多少躯干旋转空间。"},
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
    """Copy only generic line-art sources; never copy another report's assets."""
    target_dir = ASSET_DIR / "lineart_actions"
    target_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "pitch_peak_knee_lineart.png",
        "pitch_foot_plant_lineart.png",
        "pitch_release_lineart.png",
    ):
        source = BUNDLED_LINEART_DIR / name
        if not source.is_file():
            raise FileNotFoundError(f"Missing bundled generic pitching illustration: {source}")
        shutil.copy2(source, target_dir / name)


def annotate_lineart_metrics() -> None:
    script = SCRIPTS_DIR / "pitching" / "annotate_pitch_lineart_metrics.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "--summary",
            str(OUT_DIR / "pitch_metrics_summary.json"),
            "--asset-dir",
            str(ASSET_DIR / "lineart_actions"),
            "--athlete-key",
            PLAYER_KEY,
        ],
        check=True,
    )


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
    player = lookup[PLAYER_KEY]
    render_trial_png(player, player.events["release"], ASSET_DIR / "vicon_reconstruction_events" / f"{PLAYER_SLUG}_release_reference.png", f"{PLAYER_NAME} pitching release reference")
    render_trial_png(lookup["coach"], lookup["coach"].events["release"], ASSET_DIR / "vicon_reconstruction_events" / "coach_release_reference.png", "Coach pitching release reference")
    event_titles = {
        "peak_knee": "抬腿最高点 Peak knee",
        "foot_plant": "前脚落地 Foot plant",
        "release": "出手点 Release",
    }
    for event_key, title in event_titles.items():
        png_out = ASSET_DIR / "vicon_reconstruction_events" / f"{PLAYER_SLUG}_{event_key}.png"
        gif_out = ASSET_DIR / "vicon_reconstruction_events" / f"{PLAYER_SLUG}_{event_key}.gif"
        render_trial_png(player, player.events[event_key], png_out, f"{PLAYER_NAME} {title}")
        Image.open(png_out).save(gif_out, save_all=True, duration=400, loop=0)


def metric_label(value: float, suffix: str) -> str:
    if not finite(value):
        return "N/A"
    sep = "" if suffix.startswith("%") else " "
    return f"{value:.1f}{sep}{suffix}".strip()


def render_movement_panel(
    bundle: TrialBundle,
    frame: int,
    trajectory: np.ndarray,
    title: str,
    subtitle: str,
    axis_limits: recon.AxisLimits,
) -> Image.Image:
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
        axis_limits=axis_limits,
        fixed_layout_legend=True,
        recenter_limits=False,
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
            ax.plot(
                trail[:, 0],
                trail[:, 1],
                trail[:, 2],
                color=recon.TRAJECTORY_COLOR,
                linewidth=0.85,
                linestyle=(0, (3, 4)),
                label="RFIN手部轨迹",
            )
    handles = [
        Line2D(
            [0],
            [0],
            color=recon.TRAJECTORY_COLOR,
            lw=0.85,
            linestyle=(0, (3, 4)),
            label="RFIN手部轨迹",
        ),
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
        ("Hand speed", metric_label(bundle.values.get("hand_speed_kmh", float("nan")), "km/h")),
        ("Rotation angle", metric_label(bundle.values.get("hss_release_deg", float("nan")), "deg")),
        ("Release height", metric_label(bundle.values.get("release_height_pct", float("nan")), "%身高比")),
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
    end = min(bundle.trial.points.shape[0] - 1, release + int(0.30 * bundle.trial.rate_hz))
    frames = np.linspace(start, end, 24).astype(int)
    # Keep the coordinate extent fixed for the complete animation.  Deriving
    # limits from each pose makes Matplotlib rescale the grid every frame.
    limits = recon.trial_axis_limits(bundle.trial, frame_indices=frames)
    release_points = recon.trial_frame_points(bundle.trial, release, smooth_radius=2)
    animation_limits = recon.recenter_display_limits(limits, release_points)
    rfin = marker(bundle.trial, bundle.clean_labels, "RFIN")
    images: list[Image.Image] = []
    for frame in frames:
        trail_start = max(0, frame - int(0.45 * bundle.trial.rate_hz))
        trail = rfin[trail_start : frame + 1]
        images.append(
            render_movement_panel(
                bundle,
                int(frame),
                trail,
                title,
                subtitle,
                animation_limits,
            )
        )
    images[-1].save(out.with_suffix(".png"))
    images[0].save(out, save_all=True, append_images=images[1:], duration=110, loop=0, optimize=False)


def render_movement_gifs(bundles: list[TrialBundle]) -> None:
    lookup = {b.key: b for b in bundles}
    render_movement_gif(lookup[PLAYER_KEY], ASSET_DIR / "vicon_reconstruction_events" / f"{PLAYER_SLUG}_player_movement.gif", "球员动作 Player Movement", f"{PLAYER_NAME} / 投球 / 动作重建动画")
    render_movement_gif(lookup["coach"], ASSET_DIR / "vicon_reconstruction_events" / "coach_player_movement.gif", "教练动作 Coach Movement", "教练 / 投球 / 动作重建动画")


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
    julian = next(b for b in bundles if b.key == PLAYER_KEY)
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
    julian = next(b for b in bundles if b.key == PLAYER_KEY)
    out = ASSET_DIR / "kinetic_chain" / f"{PLAYER_SLUG}_pitch_kinetic_chain_flow.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Keep the pitching researcher flow visually aligned with the compact
    # batting flow: five equal transfer nodes on a single line.
    img = Image.new("RGB", (1600, 360), "#ffffff")
    draw = ImageDraw.Draw(img)
    node_font = pil_font(30, bold=True)
    small_font = pil_font(24)
    nodes = [
        ("后腿", "抬腿蓄力", julian.values["rear_knee_peak_deg"], "deg", GREEN),
        ("骨盆", "右腿蹬伸推进", julian.values["stride_distance_pct"], "pct", BLUE),
        ("躯干", "最大髋肩分离", julian.values["max_hss_deg"], "deg", PURPLE),
        ("手臂", "出手手臂角度", julian.values["arm_slot_deg"], "deg", ORANGE),
        ("手部", "出手手速", julian.values["hand_speed_kmh"], "kmh", RED),
    ]
    xs = [150, 460, 770, 1080, 1390]
    y = 180
    for i, (label, sub, val, unit, color) in enumerate(nodes):
        x = xs[i]
        draw.ellipse((x - 95, y - 95, x + 95, y + 95), fill="#f8fafc", outline=color, width=7)
        draw.text((x, y - 42), label, font=node_font, fill=INK, anchor="ma")
        draw.text((x, y + 2), sub, font=small_font, fill=MID, anchor="ma")
        draw.text((x, y + 42), fmt(val, unit), font=small_font, fill=color, anchor="ma")
        if i < len(xs) - 1:
            draw.line((x + 108, y, xs[i + 1] - 108, y), fill="#98a2b3", width=7)
            draw.polygon([(xs[i + 1] - 118, y - 16), (xs[i + 1] - 92, y), (xs[i + 1] - 118, y + 16)], fill="#98a2b3")
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
    julian = next(b for b in bundles if b.key == PLAYER_KEY)
    stats = peer_stats(bundles, key)
    mn, mx, jv = stats["min"], stats["max"], julian.values.get(key, float("nan"))
    if not (finite(mn) and finite(mx) and finite(jv)):
        return '<div class="peer-empty">乐风U9同组表现暂不可用</div>'
    span = max(mx - mn, 1e-6)
    left = max(0, min(100, (jv - mn) / span * 100))
    player_color = PEER_COLORS.get(peer_key(PLAYER_KEY), BLUE)
    player_marker_style = f'; background:{player_color}; --marker-color:{player_color}' if show_all else ''
    dots = [f'<span class="peer-dot current-player" style="left:{left:.2f}%{player_marker_style}" title="{esc(PLAYER_NAME)}: {esc(fmt(jv, unit))}"></span>']
    if show_all:
        for b in bundles:
            if b.key == PLAYER_KEY or b.role != "student":
                continue
            val = b.values.get(key, float("nan"))
            if not finite(val):
                continue
            pos = max(0, min(100, (val - mn) / span * 100))
            color = PEER_COLORS.get(peer_key(b.key), MID)
            dots.append(f'<span class="peer-dot" style="left:{pos:.2f}%; background:{color}" title="{esc(b.name)}: {esc(fmt(val, unit))}"></span>')
    range_class = "peer-range height-ratio-range" if unit == "pct" else "peer-range"
    endpoint = lambda value: (
        f'<span class="unit-stack"><span class="unit-number">{value:.1f}%</span>'
        '<span class="unit-label">身高比</span></span>'
        if unit == "pct"
        else esc(fmt(value, unit))
    )
    return f"""
      <div class="{range_class}">
        <div class="peer-label">乐风U9同组表现</div>
        <div class="peer-min">{endpoint(mn)}</div>
        <div class="peer-track"><span class="peer-span" style="left:0%; width:100%"></span>{''.join(dots)}</div>
        <div class="peer-max">{endpoint(mx)}</div>
      </div>
    """


def replace_balanced_div(html_text: str, class_name: str, replacement: str) -> str:
    """Replace the first complete div/aside carrying class_name, including nesting."""
    start_match = re.search(
        rf'<(?P<tag>div|aside)\b[^>]*class="[^"]*\b{re.escape(class_name)}\b[^"]*"[^>]*>',
        html_text,
        flags=re.IGNORECASE,
    )
    if not start_match:
        return html_text
    tag_name = start_match.group("tag")
    depth = 1
    for tag in re.finditer(rf'</?{tag_name}\b[^>]*>', html_text[start_match.end() :], flags=re.IGNORECASE):
        depth += -1 if tag.group(0).startswith("</") else 1
        if depth == 0:
            end = start_match.end() + tag.end()
            return html_text[: start_match.start()] + replacement + html_text[end:]
    raise ValueError(f"Unbalanced div while replacing class={class_name!r}")


def coach_comparison_pills(metric: dict[str, object], bundles: list[TrialBundle], coach: TrialBundle) -> str:
    player = next(bundle for bundle in bundles if bundle.key == PLAYER_KEY)
    key, unit = str(metric["key"]), str(metric["unit"])
    mean = group_mean_all(bundles, key)
    return (
        '<div class="compare-pills">'
        f'<span class="compare-pill"><b>乐风U9均值</b>{esc(fmt(mean, unit))}</span>'
        f'<span class="compare-pill"><b>阿楽教练参考</b>{esc(fmt(coach.values.get(key, float("nan")), unit))}</span>'
        f'<span class="compare-pill"><b>球员{esc(PLAYER_NAME)}</b>{esc(fmt(player.values.get(key, float("nan")), unit))}</span>'
        '</div>'
    )


def player_coach_reference(metric: dict[str, object], coach: TrialBundle) -> str:
    key, unit = str(metric["key"]), str(metric["unit"])
    return (
        '<div class="pitch-coach-reference"><b>阿楽教练</b>'
        f'<span>{esc(fmt(coach.values.get(key, float("nan")), unit))}</span></div>'
    )


def refresh_template_cards(html_text: str, bundles: list[TrialBundle]) -> str:
    """Rebind every template card to active Vicon values and fresh peer tracks."""
    player = next(bundle for bundle in bundles if bundle.key == PLAYER_KEY)
    coach = next(bundle for bundle in bundles if bundle.key == "coach")
    by_name = {str(metric["name"]): metric for metric in METRICS}
    coach_specs: dict[str, dict[str, object]] = {
        "抬腿平稳过渡": {**next(m for m in METRICS if m["key"] == "knee_height_pct"), "name": "抬腿平稳过渡", "en": "Knee-Lift Transition"},
        "跨步距离与稳定": {**next(m for m in METRICS if m["key"] == "stride_distance_pct"), "name": "跨步距离与稳定", "en": "Stride Distance and Stability"},
        "拉弓式髋肩分离": {**next(m for m in METRICS if m["key"] == "max_hss_deg"), "name": "拉弓式髋肩分离", "en": "Hip-Shoulder Separation"},
        "右腿蹬伸推进": {
            "key": "rear_knee_drive_extension_deg", "name": "右腿蹬伸推进", "en": "Rear-Leg Drive",
            "unit": "deg", "direction": "higher", "image_key": "rear_knee_plant_deg",
            "copy": "以后膝从前脚落地到出手的伸展变化作为推进线索；它不是力板测得的蹬地力量。",
        },
        "出手手臂角度": {**next(m for m in METRICS if m["key"] == "arm_slot_deg"), "name": "出手手臂角度", "en": "Release Arm Angle"},
        "出手手速": {**next(m for m in METRICS if m["key"] == "hand_speed_kmh"), "name": "出手手速", "en": "Release Hand Speed"},
    }
    aliases = {"右腿蹬地伸展线索": "右腿蹬伸推进", "手臂槽位": "出手手臂角度", "手臂链条槽位": "出手手臂角度", "手速": "出手手速"}

    def rewrite_card(match: re.Match[str]) -> str:
        card = match.group(0)
        is_coach = "coach-issue-card" in card
        name_match = re.search(r'<h4>([^<]+)</h4>', card)
        if not name_match:
            return card
        old_name = aliases.get(name_match.group(1).strip(), name_match.group(1).strip())
        metric = coach_specs.get(old_name) if is_coach else by_name.get(old_name)
        if metric is None:
            return card
        key, unit = str(metric["key"]), str(metric["unit"])
        value = player.values.get(key, float("nan"))
        score = score_metric(value, metric, coach.values.get(key, float("nan")))
        status, status_class = status_from_score(score)
        card = re.sub(
            r'(<article class="(?:metric-card|coach-issue-card)\s+)(?:good|review|risk)(")',
            rf'\g<1>{status_class}\2', card, count=1,
        )
        card = re.sub(r'(<span class="badge\s+)(?:good|review|risk)(">)[^<]*(</span>)', rf'\g<1>{status_class}\2{status}\3', card, count=1)
        card = re.sub(
            r'<h4>[^<]*</h4>',
            f'<h4>{esc(str(metric["name"]))}</h4>',
            card,
            count=1,
        )
        card = re.sub(r'(<p class="metric-en">)[^<]*(</p>)', rf'\g<1>{esc(str(metric["en"]))}\g<2>', card, count=1)
        card = re.sub(r'(<div class="metric-value">)[^<]*(</div>)', rf'\g<1>{esc(fmt(value, unit))}\g<2>', card, count=1)
        image_key = str(metric.get("image_key") or key)
        card = re.sub(r'(src="assets/frontend_metric_illustrations_pitch/)[^"?]+(?:\?v=[^"]*)?("[^>]*>)', rf'\g<1>{image_key}.png\2', card, count=1)
        card = re.sub(r'(<p class="metric-detail-cn">).*?(</p>)', rf'\g<1>{esc(str(metric["copy"]))}\g<2>', card, count=1, flags=re.DOTALL)
        english = f'Player: {fmt(value, unit)}. Read this value with the movement sequence and coach reference rather than as a medical or pass/fail threshold.'
        card = re.sub(r'(<p class="metric-detail-en">).*?(</p>)', rf'\g<1>{esc(english)}\g<2>', card, count=1, flags=re.DOTALL)
        if is_coach:
            card = replace_balanced_div(card, "compare-pills", coach_comparison_pills(metric, bundles, coach))
            card = replace_balanced_div(card, "peer-range-with-legend", f'<div class="peer-range-with-legend">{range_html(metric, bundles, show_all=True)}</div>')
        else:
            card = replace_balanced_div(card, "pitch-compare-pills", "")
            card = re.sub(
                r'(<div class="metric-value">[^<]*</div>)',
                rf'\1{player_coach_reference(metric, coach)}',
                card,
                count=1,
            )
            card = replace_balanced_div(card, "peer-range", range_html(metric, bundles, show_all=False))
        return card

    return re.sub(
        r'<article class="(?:metric-card|coach-issue-card)\b[^>]*>.*?</article>',
        rewrite_card,
        html_text,
        flags=re.DOTALL,
    )


def fresh_peer_legend(bundles: list[TrialBundle]) -> str:
    students = {peer_key(bundle.key): bundle for bundle in bundles if bundle.role == "student"}
    items = []
    for key in PEER_LEGEND_ORDER:
        if key not in students:
            continue
        items.append(
            f'<span class="peer-legend-item"><i class="peer-legend-dot" style="background:{PEER_COLORS[key]}"></i>{esc(peer_display_name(key))}</span>'
        )
    return '<aside class="peer-legend coach-legend" aria-label="颜色图例"><span class="peer-legend-title">颜色图例</span>' + "".join(items) + '</aside>'


def refresh_researcher_copy(html_text: str, bundles: list[TrialBundle]) -> str:
    player = next(bundle for bundle in bundles if bundle.key == PLAYER_KEY)
    v = player.values
    cn1 = (
        f'球员{PLAYER_NAME}本次投球呈现“后腿准备 → 骨盆推进 → 躯干旋转 → 手臂与手部输出”的动作顺序。'
        f'{v["peak_knee_time_s"]:.2f}s 抬腿最高点、{v["foot_plant_time_s"]:.2f}s 前脚落地、{v["release_time_s"]:.2f}s 出手，'
        f'落地到出手约 {v["release_time_s"] - v["foot_plant_time_s"]:.2f}s。'
    )
    cn2 = (
        f'最大髋肩分离 {fmt(v["max_hss_deg"], "deg")}，分离释放量 {fmt(v["hss_release_amount_deg"], "deg")}；'
        f'出手手臂角度 {fmt(v["arm_slot_deg"], "deg")}、出手手速 {fmt(v["hand_speed_kmh"], "kmh")}。'
        '这些指标用于观察传力顺序与重复性，出手手速是手部位置速度代理，不是球速。'
    )
    replacement = (
        '<div class="kinetic-analysis"><h4>详细解读</h4>'
        f'<p class="copy-cn">{esc(cn1)}</p><p class="copy-en">The timing view summarizes the active player’s lower-body-to-hand sequence from the current motion record.</p>'
        f'<p class="copy-cn">{esc(cn2)}</p><p class="copy-en">Use the curves to review sequencing and repeatability; release hand speed is a hand-motion proxy, not ball speed.</p></div>'
    )
    return replace_balanced_div(html_text, "kinetic-analysis", replacement)


def metric_card(metric: dict[str, object], bundles: list[TrialBundle], coach: TrialBundle, coach_mode: bool = False) -> str:
    julian = next(b for b in bundles if b.key == PLAYER_KEY)
    key = str(metric["key"])
    unit = str(metric["unit"])
    value = julian.values.get(key, float("nan"))
    coach_value = coach.values.get(key, float("nan"))
    score = score_metric(value, metric, coach_value)
    label, klass = status_from_score(score)
    mean = group_mean_all(bundles, key)
    img = f"assets/frontend_metric_illustrations_pitch/{key}.png"
    compare = (
        f'<p class="metric-detail-en">测试组均值 {esc(fmt(mean, unit))} · Coach {esc(fmt(coach_value, unit))} · 球员 {esc(PLAYER_NAME)} {esc(fmt(value, unit))}</p>'
        if coach_mode
        else ""
    )
    return f"""
    <article class="metric-card {klass}">
      <div class="metric-summary">
        <span class="badge {klass}">{esc(label)}</span>
        <div><h4>{esc(metric["name"])}</h4><p class="metric-en">{esc(metric["en"])}</p></div>
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
          <h4>球员{esc(PLAYER_NAME)} 出手点动作对照</h4>
          <figure class="reconstruction-annotated">
            <img src="assets/vicon_reconstruction_events/{esc(PLAYER_SLUG)}_player_movement.gif" alt="球员{esc(PLAYER_NAME)} 投球出手点动作重建" loading="lazy">
            <figcaption>
              <b>球员{esc(PLAYER_NAME)} 投球动作出手点</b>
              <span class="caption-cn">当前出手点主要看前腿支撑、肩外展、肘屈曲、手臂槽位和手速。球员动作链已经具备基础，重点是让前脚落地后的身体传力更清楚。</span>
            </figcaption>
          </figure>
        </article>
        <article class="visual-card">
          <h4>阿楽教练 动作参考</h4>
          <figure class="reconstruction-annotated">
            <img src="assets/vicon_reconstruction_events/coach_player_movement.gif" alt="阿楽教练 投球出手点动作重建" loading="lazy">
            <figcaption>
              <b>阿楽教练 投球动作参考</b>
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
            <img src="assets/vicon_reconstruction_events/{esc(PLAYER_SLUG)}_peak_knee.gif" alt="{esc(PLAYER_NAME)} 抬腿最高点 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/vicon_2d_geometry_annotations/peak_knee_position_vicon_geometry_on_2d.png" alt="{esc(PLAYER_NAME)} 抬腿最高点 2D 几何标注" loading="lazy">
          </figure>
        </article>
        <article class="motion-stage-card">
          <figure class="motion-3d-panel">
            <h4>动作姿态<span>Posture</span></h4>
            <img src="assets/vicon_reconstruction_events/{esc(PLAYER_SLUG)}_foot_plant.gif" alt="{esc(PLAYER_NAME)} 前脚落地 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/vicon_2d_geometry_annotations/foot_plant_position_vicon_geometry_on_2d.png" alt="{esc(PLAYER_NAME)} 前脚落地 2D 几何标注" loading="lazy">
          </figure>
        </article>
        <article class="motion-stage-card">
          <figure class="motion-3d-panel">
            <h4>动作姿态<span>Posture</span></h4>
            <img src="assets/vicon_reconstruction_events/{esc(PLAYER_SLUG)}_release.gif" alt="{esc(PLAYER_NAME)} 出手点 3D 动图" loading="lazy">
          </figure>
          <figure class="motion-2d-panel">
            <img src="assets/vicon_2d_geometry_annotations/release_position_vicon_geometry_on_2d.png" alt="{esc(PLAYER_NAME)} 出手点 2D 几何标注" loading="lazy">
          </figure>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>{esc(PLAYER_NAME)} 投球动力链</h2></div>
      <article class="visual-card kinetic-chain-card">
        <h4>后腿 -> 骨盆 -> 躯干 -> 手臂 -> 手</h4>
        <figure class="kinetic-chain-figure">
          <img src="assets/kinetic_chain/{esc(PLAYER_SLUG)}_pitch_kinetic_chain_flow.png" alt="{esc(PLAYER_NAME)} 投球动力链图" loading="lazy">
        </figure>
        <p class="copy-cn">动力链解读：球员的抬腿高度和出手高度都比较清楚，说明动作有完整的准备和释放阶段。需要继续关注的是前脚落地后，髋肩分离能否更稳定地形成并释放，避免动作变成手臂先抢出手。</p>
        <p class="copy-en">Kinetic-chain read: the player shows clear preparation and release positions. The next coaching focus is whether hip-shoulder separation forms and releases after foot plant instead of the arm rushing ahead.</p>
      </article>
    </section>

    {render_section("抬腿最高点", "准备阶段关键画面", event_groups["抬腿最高点"], bundles, coach, "assets/lineart_actions/pitch_peak_knee_lineart_metrics.png")}
    {render_section("前脚落地", "落脚质量、支撑和手臂到位", event_groups["前脚落地"], bundles, coach, "assets/lineart_actions/pitch_foot_plant_lineart_metrics.png")}
    {render_section("出手点", "前腿制动、出手角度和出手点", event_groups["出手点"], bundles, coach, "assets/lineart_actions/pitch_release_lineart_metrics.png")}

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>教练视角：专项问题</h2></div>
      <div class="grid issue-metrics">{coach_issue_cards(bundles, coach)}</div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>分析员视角：完整指标表</h2></div>
      <article class="visual-card">
        <h4>{esc(PLAYER_NAME)}、测试组均值与阿楽教练对照</h4>
        <div class="table-wrap">
          <table>
            <thead><tr><th>事件</th><th>前端指标</th><th>{esc(PLAYER_NAME)}</th><th>测试组均值</th><th>阿楽教练</th><th>解释</th></tr></thead>
            <tbody>{metric_rows_table(bundles)}</tbody>
          </table>
        </div>
        <p class="copy-cn">数据说明：本报告根据本次投球动作的连续记录整理。前脚接触、踏稳和出手点按动作过程的变化定位；未使用力板或球速数据。</p>
      </article>
    </section>
  </main>
</body>
</html>
"""


def write_json_summary(bundles: list[TrialBundle]) -> None:
    data = {
        "created_for": f"{PLAYER_NAME} pitching report, template-matched coach metrics section",
        "assumptions": {
            "lead_leg": "L",
            "drive_leg": "R",
            "throwing_arm": "R",
            "coach_reference": "008-coach Cal 03 Pitch 07.c3d",
            "player_reference": PLAYER_NAME,
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


def peer_key(name: str) -> str:
    key = name.strip().casefold().replace(" ", "")
    return PEER_KEY_ALIASES.get(key, key)


def peer_display_name(name: str) -> str:
    return PEER_DISPLAY_NAMES.get(peer_key(name), name)


def reference_metric_values(metric_key: str, bundles: list[TrialBundle], coach: TrialBundle) -> tuple[float, float]:
    # Template CSVs are deliberately excluded: all comparison values must
    # come from the active manifest's Vicon trials.
    return group_mean_all(bundles, metric_key), coach.values.get(metric_key, float("nan"))


def comparison_pills(
    metric: dict[str, object],
    bundles: list[TrialBundle],
    coach: TrialBundle,
    displayed_player_value: str,
) -> str:
    key = str(metric["key"])
    unit = str(metric["unit"])
    mean, coach_value = reference_metric_values(key, bundles, coach)
    return (
        '<div class="pitch-compare-pills">'
        f'<span><b>乐风U9均值</b>{esc(fmt(mean, unit))}</span>'
        f'<span><b>阿楽教练参考</b>{esc(fmt(coach_value, unit))}</span>'
        f'<span><b>球员{esc(PLAYER_NAME)}</b>{esc(displayed_player_value)}</span>'
        '</div>'
    )


def add_pitch_comparisons(html_text: str, bundles: list[TrialBundle], coach: TrialBundle) -> str:
    by_name = {str(metric["name"]): metric for metric in METRICS}

    def replace_card(match: re.Match[str]) -> str:
        card = match.group(0)
        name_match = re.search(r"<h4>([^<]+)</h4>", card)
        if not name_match or "pitch-compare-pills" in card:
            return card
        metric = by_name.get(name_match.group(1).strip())
        if metric is None:
            return card
        value_match = re.search(r'<div class="metric-value">([^<]+)</div>', card)
        if not value_match:
            return card
        pills = comparison_pills(metric, bundles, coach, value_match.group(1).strip())
        return card.replace('<div class="peer-range">', pills + '<div class="peer-range">', 1)

    return re.sub(r'<article class="metric-card\b[^>]*>.*?</article>', replace_card, html_text, flags=re.DOTALL)


def refresh_metric_card_summaries(html_text: str, bundles: list[TrialBundle]) -> str:
    """Bring legacy player and coach cards onto the batting-style metric header contract."""
    player = next(bundle for bundle in bundles if bundle.key == PLAYER_KEY)
    aliases = {
        "Arm slot": "arm_slot_deg",
        "手臂槽位": "arm_slot_deg",
        "手臂链条槽位": "arm_slot_deg",
        "手速": "hand_speed_kmh",
        "出手手速": "hand_speed_kmh",
        "右腿蹬地伸展线索": "rear_knee_drive_extension_deg",
    }
    coach_card_english = {
        "抬腿平稳过渡": "Knee-Lift Transition",
        "跨步距离与稳定": "Stride Distance and Stability",
        "拉弓式髋肩分离": "Hip-Shoulder Separation",
        "右腿蹬地伸展线索": "Rear-Leg Drive",
    }
    by_name = {str(metric["name"]): metric for metric in METRICS}
    by_key = {str(metric["key"]): metric for metric in METRICS}

    def replace_card(match: re.Match[str]) -> str:
        card = match.group(0)
        name_match = re.search(r"<h4>([^<]+)</h4>", card)
        if not name_match:
            return card
        old_name = name_match.group(1).strip()
        metric = by_name.get(old_name)
        if metric is None:
            metric = by_key.get(aliases.get(old_name, ""))
        if metric is None:
            english = coach_card_english.get(old_name)
            if english is not None:
                title = "右腿蹬伸推进" if old_name == "右腿蹬地伸展线索" else old_name
                card = card[: name_match.start()] + f"<h4>{esc(title)}</h4>" + card[name_match.end() :]
                return re.sub(
                    r'(<p class="metric-en">)[^<]*(</p>)',
                    rf'\g<1>{esc(english)}\g<2>',
                    card,
                    count=1,
                )
            return card
        key = str(metric["key"])
        display_value = esc(fmt(player.values.get(key, float("nan")), str(metric["unit"])))
        card = card[: name_match.start()] + f"<h4>{esc(metric['name'])}</h4>" + card[name_match.end() :]
        card = re.sub(
            r'(<p class="metric-en">)[^<]*(</p>)',
            rf'\g<1>{esc(str(metric["en"]))}\g<2>',
            card,
            count=1,
        )
        card = re.sub(
            r'(<div class="metric-value">)[^<]*(</div>)',
            rf'\g<1>{display_value}\g<2>',
            card,
            count=1,
        )
        return card

    html_text = re.sub(
        r'<article class="(?:metric-card|coach-issue-card)\b[^>]*>.*?</article>',
        replace_card,
        html_text,
        flags=re.DOTALL,
    )
    html_text = html_text.replace("右腿蹬地伸展线索", "右腿蹬伸推进")
    html_text = html_text.replace("手臂链条槽位", "出手手臂角度")
    html_text = html_text.replace("手臂槽位", "出手手臂角度")
    # Keep every legacy and newly generated three-pill comparison card on the
    # same naming contract, without retaining a hard-coded Julian label.
    html_text = html_text.replace("<b>测试组均值</b>", "<b>乐风U9均值</b>")
    html_text = html_text.replace("<b>教练参考</b>", "<b>阿楽教练参考</b>")
    html_text = html_text.replace("<b>球员</b>", f"<b>球员{esc(PLAYER_NAME)}</b>")
    html_text = re.sub(r"(?<!出手)手速", "出手手速", html_text)
    html_text = html_text.replace("hand_speed_mps.png", "hand_speed_kmh.png")
    html_text = html_text.replace(
        "assets/frontend_metric_illustrations_pitch_event/hand_speed_kmh.png",
        "assets/frontend_metric_illustrations_pitch/hand_speed_kmh.png",
    )

    def convert_mps(match: re.Match[str]) -> str:
        return f"{float(match.group(1)) * 3.6:.1f} km/h"

    # Legacy templates carry hand-speed notes and comparison ranges as m/s.
    # Convert every displayed value while the report is being rewritten so all
    # player, coach, and researcher views share the report's km/h contract.
    return re.sub(r"(?<![\w.])(\d+(?:\.\d+)?)\s*m/s\b", convert_mps, html_text)


def apply_peer_display_mapping(html_text: str) -> str:
    def dot_replacement(match: re.Match[str]) -> str:
        prefix, _old_color, between, raw_name, suffix = match.groups()
        key = peer_key(raw_name)
        return f"{prefix}{PEER_COLORS.get(key, _old_color)}{between}{peer_display_name(raw_name)}{suffix}"

    html_text = re.sub(
        r'(<span class="peer-dot(?![^>]*current-player)[^>]*style="[^"]*background:)(#[0-9a-fA-F]+)([^"]*"[^>]*title=")([^":]+)(:)',
        dot_replacement,
        html_text,
    )
    return re.sub(
        r'(title=")([^":]+)(:)',
        lambda match: f'{match.group(1)}{peer_display_name(match.group(2))}{match.group(3)}',
        html_text,
    )


def inject_pitch_card_styles(html_text: str) -> str:
    marker = "/* pitching-card-alignment */"
    css = f"""
    {marker}
    .compact-metrics.two-column-metrics {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    /* Height-ratio endpoints need extra room.  Tighten the summary/illustration
       columns and side padding so the visual and explanatory copy sit left of
       the card edge instead of being clipped on narrower report canvases. */
    .two-column-metrics .metric-card {{ grid-template-columns:minmax(94px,110px) minmax(94px,116px) minmax(0,1fr); min-height:304px; padding:18px 16px; gap:8px; overflow:hidden; }}
    .two-column-metrics .metric-card h4 {{ font-size:17px; line-height:22px; }}
    .two-column-metrics .metric-value {{ font-size:34px; }}
    .two-column-metrics .metric-detail {{ gap:8px; }}
    .two-column-metrics .metric-detail-cn {{ font-size:13px; line-height:20px; }}
    .two-column-metrics .peer-range {{ grid-template-columns:max-content 34px minmax(52px,76px) 34px; gap:6px; max-width:100%; justify-self:start; }}
    .peer-range.height-ratio-range,.peer-range:has(.unit-stack) {{ grid-template-columns:max-content minmax(48px,max-content) minmax(72px,1fr) minmax(48px,max-content); align-items:center; }}
    .peer-range.height-ratio-range .peer-min,.peer-range.height-ratio-range .peer-max,.peer-range:has(.unit-stack) .peer-min,.peer-range:has(.unit-stack) .peer-max {{ min-width:48px; white-space:normal; }}
    .peer-range.height-ratio-range .unit-stack,.peer-range:has(.unit-stack) .unit-stack {{ display:inline-grid; gap:2px; line-height:1.05; justify-items:center; text-align:center; }}
    .peer-range.height-ratio-range .unit-number,.peer-range.height-ratio-range .unit-label,.peer-range:has(.unit-stack) .unit-number,.peer-range:has(.unit-stack) .unit-label {{ display:block; white-space:nowrap; }}
    .coach-issue-card {{ grid-template-columns:minmax(148px,.62fr) minmax(176px,270px) minmax(0,1.2fr); gap:16px; padding:20px 16px; }}
    .analyst-chart-grid {{ grid-template-columns:1fr; }}
    /* The pitching flow now shares batting's compact five-node layout. */
    .kinetic-chain-figure img {{ aspect-ratio:1600/360; }}
    .pitch-compare-pills {{ display:flex; flex-wrap:wrap; gap:8px; margin:2px 0 4px; }}
    .pitch-compare-pills span {{ display:inline-grid; gap:2px; min-width:112px; border:1px solid #d0d5dd; border-radius:12px; padding:8px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; }}
    .pitch-compare-pills span b {{ color:#667085; font-size:11px; line-height:14px; }}
    .peer-dot.current-player {{ z-index:4; width:16px; height:16px; background:#ef4444; border:3px solid #fff; box-shadow:0 0 0 2px #fff,0 0 0 6px color-mix(in srgb, var(--marker-color,#ef4444) 20%, transparent),0 0 0 1px rgba(16,24,40,.15); }}
    .coach-issue-card .peer-dot.current-player {{ z-index:4 !important; width:16px !important; height:16px !important; border:3px solid #fff !important; box-shadow:0 0 0 2px #fff,0 0 0 6px color-mix(in srgb, var(--marker-color,#ef4444) 20%, transparent),0 0 0 1px rgba(16,24,40,.15) !important; }}
    @media (max-width:640px) {{ .pitch-compare-pills span {{ min-width:0; flex:1 1 110px; }} }}
    """
    html_text = re.sub(rf"\s*/\* {re.escape(marker[3:-3])} \*/.*?(?=\s*</style>)", "", html_text, flags=re.DOTALL)
    return html_text.replace("</style>", css + "\n  </style>", 1)


def rewrite_legacy_template_html(html_text: str, bundles: list[TrialBundle]) -> str:
    html_text = html_text.replace("julian_", f"{PLAYER_SLUG}_")
    html_text = html_text.replace("julian:", f"{PLAYER_SLUG}:")
    html_text = html_text.replace("Julian", PLAYER_NAME)

    # The reconstruction cards are reused from a report template.  Rebind all
    # four visible labels on every rebuild so no generic player/coach wording
    # or old template instruction can leak into another athlete's report.
    player_reconstruction_label = f"球员{PLAYER_NAME}"
    coach_reconstruction_label = "阿楽教练"
    html_text = re.sub(
        r'<h4>(?:球员)?[^<]*出手点 Vicon 标注</h4>',
        f'<h4>{esc(player_reconstruction_label)} 出手点动作对照</h4>',
        html_text,
        count=1,
    )
    html_text = html_text.replace(
        '<h4>教练技术参考</h4>',
        f'<h4>{esc(coach_reconstruction_label)} 动作参考</h4>',
        1,
    )
    html_text = re.sub(
        r'alt="[^"]*投球出手点 Vicon 动画重建"',
        f'alt="{esc(player_reconstruction_label)} 投球出手点动作重建"',
        html_text,
        count=1,
    )
    html_text = html_text.replace(
        'alt="教练投球出手点 Vicon 动画重建"',
        f'alt="{esc(coach_reconstruction_label)} 投球出手点动作重建"',
        1,
    )
    html_text = re.sub(
        r'<b>(?:球员)?[^<]*投球动作出手点</b>',
        f'<b>{esc(player_reconstruction_label)} 投球动作出手点</b>',
        html_text,
        count=1,
    )
    html_text = html_text.replace(
        '<b>教练投球动作参考</b>',
        f'<b>{esc(coach_reconstruction_label)} 投球动作参考</b>',
        1,
    )
    html_text = re.sub(r'HTML模板此处更改为[^<]*', '', html_text)

    # Existing report templates already contain rendered card values.  Upgrade
    # visible percentage text nodes during migration as well as new values
    # emitted through fmt(), while leaving CSS percentages untouched.
    # Normalize an earlier rebuild's stacked endpoint back to one canonical
    # text value before applying the current migration below.
    html_text = re.sub(
        r'<span class="unit-stack"><span class="unit-number">(-?\d+(?:\.\d+)?)%(?:身高比)?</span><span class="unit-label">身高比</span></span>',
        r'\1%身高比',
        html_text,
    )
    html_text = re.sub(
        r'(?<!class="unit-number")>(-?\d+(?:\.\d+)?)%(?=<)',
        r'>\1%身高比',
        html_text,
    )
    html_text = re.sub(
        r'(<div class="peer-(?:min|max)">)(-?\d+(?:\.\d+)?)%身高比(</div>)',
        r'\1<span class="unit-stack"><span class="unit-number">\2%</span><span class="unit-label">身高比</span></span>\3',
        html_text,
    )
    # Legacy templates contain user-visible provenance jargon in captions and
    # researcher explanations. Keep the implementation details in source/JSON,
    # while presenting the report in plain movement language.
    for old, new in {
        "球员和 Coach": "球员和教练",
        "球员与 Coach": "球员与教练",
        "C3D骨架动画": "动作重建动画",
        "C3D/Vicon": "本次动作记录",
        "C3D marker": "本次动作变化",
        "C3D 文件": "本次动作记录",
        "C3D数据": "本次动作记录",
        "Vicon markers": "动作变化",
        "main release markers": "key release positions",
        "手部 marker": "手部位置",
        "球 marker": "球的位置",
    }.items():
        html_text = html_text.replace(old, new)
    html_text = re.sub(
        r"曲线来自[^<。]*?(?:C3D|marker)[^<。]*?逐帧计算。",
        "曲线展示本次投球过程中各项动作随时间的变化。",
        html_text,
        flags=re.IGNORECASE,
    )
    # Never inherit a prior athlete's researcher assets when the template is
    # reused. Both flow and timing figures must be rebound to this player.
    html_text = re.sub(
        r'(src="assets/kinetic_chain/)[^"]*_pitch_kinetic_chain_flow\.png(" alt="球员投球动力链图")',
        rf'\g<1>{PLAYER_SLUG}_pitch_kinetic_chain_flow.png\2',
        html_text,
    )
    # Some older templates put the generic timing-curve filename in the
    # flow-card slot. Preserve the intended flow-card asset during migration.
    html_text = re.sub(
        r'(src="assets/kinetic_chain/)[^"]*_kinetic_chain_time_curves\.png(" alt="球员投球动力链时间曲线")',
        rf'\g<1>{PLAYER_SLUG}_pitch_kinetic_chain_flow.png\2',
        html_text,
    )
    html_text = re.sub(
        r'(src="assets/kinetic_chain/)[^"]*_kinetic_chain_time_curves\.png(" alt="球员投球动力链五指标时间曲线")',
        rf'\g<1>{PLAYER_SLUG}_kinetic_chain_time_curves.png\2',
        html_text,
    )
    html_text = re.sub(
        r'(src="assets/analyst_charts/)[^"]*_pitch_angle_time_curve\.png(?:\?v=[^"]*)?(" alt="球员投球角度时间曲线")',
        rf'\g<1>{PLAYER_SLUG}_pitch_angle_time_curve.png\2',
        html_text,
    )
    html_text = re.sub(
        r'(src="assets/analyst_charts/)[^"]*_pitch_speed_time_curve\.png(?:\?v=[^"]*)?(" alt="球员投球速度时间曲线")',
        rf'\g<1>{PLAYER_SLUG}_pitch_speed_time_curve.png\2',
        html_text,
    )
    html_text = html_text.replace("优秀学员 Bryan", f"球员 {PLAYER_NAME}")
    html_text = html_text.replace("优秀学员 julian", f"球员 {PLAYER_SLUG}")
    html_text = html_text.replace("peer-dot julian", "peer-dot current-player")
    for event_key in ("peak_knee", "foot_plant", "release"):
        html_text = html_text.replace(
            f"assets/vicon_2d_geometry_annotations/{event_key}_position_vicon_geometry_on_2d.png",
            f"assets/video_2d_alignment/{PLAYER_SLUG}_pitch_{event_key}_2d_overlay.png",
        )
    html_text = re.sub(
        r'(src="assets/video_2d_alignment/)[^"]*_pitch_(peak_knee|foot_plant|release)_2d_overlay\.png(?:\?v=[^"]*)?(")',
        lambda match: f"{match.group(1)}{PLAYER_SLUG}_pitch_{match.group(2)}_2d_overlay.png{match.group(3)}",
        html_text,
    )
    html_text = re.sub(
        r'(<div class="section-title"><span class="mark"></span><h2>教练视角：专项问题</h2></div>)\s*<div class="module-note">.*?</div>',
        r'\1',
        html_text,
        count=1,
        flags=re.DOTALL,
    )

    coach_heading = '<div class="section-title"><span class="mark"></span><h2>教练视角：专项问题</h2></div>'
    player_html, coach_html = html_text.split(coach_heading, 1)
    active_player_names = {
        PLAYER_KEY.casefold(),
        PLAYER_NAME.casefold(),
        peer_display_name(PLAYER_KEY).casefold(),
    }

    def marker_style(style: str, color: str) -> str:
        style = re.sub(r';?\s*background:[^;\"]*', '', style)
        style = re.sub(r';?\s*--marker-color:[^;\"]*', '', style).strip().rstrip(';')
        return f"{style}; background:{color}; --marker-color:{color}".strip("; ")

    def is_active_player(name: str) -> bool:
        return name.strip().casefold() in active_player_names

    def highlight_player_marker(match: re.Match[str]) -> str:
        style, name, suffix = match.groups()
        if not is_active_player(name):
            return match.group(0)
        return (
            f'<span class="peer-dot current-player" '
            f'style="{marker_style(style, RED)}" title="{name}{suffix}'
        )

    player_html = re.sub(
        r'<span class="peer-dot(?:\s+current-player)?" style="([^\"]*)" title="([^":]+)(:)',
        highlight_player_marker,
        player_html,
    )
    html_text = player_html + coach_heading + coach_html

    player_color = PEER_COLORS.get(peer_key(PLAYER_KEY), BLUE)

    def focus_coach_player_marker(track_match: re.Match[str]) -> str:
        """Highlight only the active test point in a coach comparison track.

        Some legacy tracks retain a same-name peer reference before the active
        test point.  The active point is the final same-name marker in that
        track; leave earlier references at their normal legend color.
        """
        track = track_match.group(0)
        marker_pattern = re.compile(
            r'<span class="peer-dot(?:\s+current-player)?" style="([^\"]*)" title="([^":]+)(:)'
        )
        active_matches = [match for match in marker_pattern.finditer(track) if is_active_player(match.group(2))]
        if not active_matches:
            return track
        active_index = len(active_matches) - 1
        seen_active = -1

        def rewrite_marker(match: re.Match[str]) -> str:
            nonlocal seen_active
            style, name, suffix = match.groups()
            if not is_active_player(name):
                return match.group(0)
            seen_active += 1
            if seen_active == active_index:
                return (
                    f'<span class="peer-dot current-player" '
                    f'style="{marker_style(style, player_color)}" title="{name}{suffix}'
                )
            normal_style = re.sub(r';?\s*--marker-color:[^;\"]*', '', style).strip().rstrip(';')
            return f'<span class="peer-dot" style="{normal_style}" title="{name}{suffix}'

        return marker_pattern.sub(rewrite_marker, track)

    html_text = re.sub(
        r'(<article class="coach-issue-card\b[^>]*>.*?</article>)',
        lambda match: re.sub(
            r'<div class="peer-track">.*?</div>',
            focus_coach_player_marker,
            match.group(1),
            flags=re.DOTALL,
        ),
        html_text,
        flags=re.DOTALL,
    )
    for filename in (f"{PLAYER_SLUG}_player_movement.gif", "coach_player_movement.gif"):
        asset = ASSET_DIR / "vicon_reconstruction_events" / filename
        if not asset.exists():
            continue
        relative_path = f"assets/vicon_reconstruction_events/{filename}"
        versioned_path = f"{relative_path}?v={asset.stat().st_mtime_ns}"
        html_text = re.sub(
            rf"{re.escape(relative_path)}(?:\?v=[^\"']*)?",
            versioned_path,
            html_text,
        )
    coach = next(bundle for bundle in bundles if bundle.key == "coach")
    html_text = refresh_metric_card_summaries(html_text, bundles)
    # Legacy player and coach cards come from the existing pitching template,
    # so normalize their group-range label here as well as in range_html().
    html_text = html_text.replace(
        '<div class="peer-label">同组区间</div>',
        '<div class="peer-label">乐风U9同组表现</div>',
    )
    html_text = re.sub(
        r'\s*<div class="pitch-compare-pills">.*?</div>(?=\s*<div class="peer-range">)',
        "",
        html_text,
        flags=re.DOTALL,
    )
    html_text = add_pitch_comparisons(html_text, bundles, coach)
    html_text = apply_peer_display_mapping(html_text)
    html_text = re.sub(r'\s*<div class="pitch-peer-color-legend">.*?</div></div>', "", html_text, flags=re.DOTALL)
    return inject_pitch_card_styles(html_text)


def remove_legacy_julian_assets() -> None:
    if PLAYER_SLUG == "julian" or not ASSET_DIR.exists():
        return
    for path in ASSET_DIR.rglob("*julian*"):
        if path.is_file():
            path.unlink()


def build_template_report_html(template_html: str, bundles: list[TrialBundle]) -> str:
    """Keep the reference DOM/CSS contract while rebinding every dynamic field."""
    html_text = template_html
    html_text = html_text.replace('id="julian-pitching-metrics"', f'id="{PLAYER_SLUG}-pitching-metrics"')
    html_text = html_text.replace("球员Bryan", f"球员{esc(PLAYER_NAME)}")
    html_text = html_text.replace("球员Julian", f"球员{esc(PLAYER_NAME)}")
    html_text = re.sub(
        r'assets/vicon_reconstruction_events/(?!coach_)[^/"?]+_player_movement\.gif(?:\?v=[^"]*)?',
        f'assets/vicon_reconstruction_events/{PLAYER_SLUG}_player_movement.gif',
        html_text,
    )
    html_text = re.sub(
        r'assets/vicon_reconstruction_events/coach_player_movement\.gif(?:\?v=[^"]*)?',
        'assets/vicon_reconstruction_events/coach_player_movement.gif',
        html_text,
    )
    for event_key in ("peak_knee", "foot_plant", "release"):
        html_text = re.sub(
            rf'assets/vicon_reconstruction_events/[^/"?]+_{event_key}\.gif(?:\?v=[^"]*)?',
            f'assets/vicon_reconstruction_events/{PLAYER_SLUG}_{event_key}.gif',
            html_text,
        )
        html_text = re.sub(
            rf'assets/video_2d_alignment/[^/"?]+_pitch_{event_key}_2d_overlay\.png(?:\?v=[^"]*)?',
            f'assets/video_2d_alignment/{PLAYER_SLUG}_pitch_{event_key}_2d_overlay.png',
            html_text,
        )
    html_text = re.sub(
        r'assets/kinetic_chain/[^/"?]+_pitch_kinetic_chain_flow\.png(?:\?v=[^"]*)?',
        f'assets/kinetic_chain/{PLAYER_SLUG}_pitch_kinetic_chain_flow.png',
        html_text,
    )
    html_text = re.sub(
        r'assets/kinetic_chain/[^/"?]+_kinetic_chain_time_curves\.png(?:\?v=[^"]*)?',
        f'assets/kinetic_chain/{PLAYER_SLUG}_kinetic_chain_time_curves.png',
        html_text,
    )
    for chart in ("angle", "speed"):
        html_text = re.sub(
            rf'assets/analyst_charts/[^/"?]+_pitch_{chart}_time_curve\.png(?:\?v=[^"]*)?',
            f'assets/analyst_charts/{PLAYER_SLUG}_pitch_{chart}_time_curve.png',
            html_text,
        )
    html_text = refresh_template_cards(html_text, bundles)
    html_text = replace_balanced_div(html_text, "coach-legend", fresh_peer_legend(bundles))
    html_text = refresh_researcher_copy(html_text, bundles)
    html_text = apply_peer_display_mapping(html_text)
    for old, new in {
        "球员和 Coach": "球员和教练", "球员与 Coach": "球员与教练",
        "C3D骨架动画": "动作重建动画", "C3D/Vicon": "本次动作记录",
        "C3D marker": "本次动作变化", "C3D 文件": "本次动作记录",
        "C3D数据": "本次动作记录", "Vicon markers": "动作变化",
        "main release markers": "key release positions", "手部 marker": "手部位置",
        "球 marker": "球的位置", "同组区间": "乐风U9同组表现",
    }.items():
        html_text = html_text.replace(old, new)
    player_reference_css = """
    .pitch-coach-reference { display:inline-grid; gap:2px; justify-self:start; min-width:92px; border:1px solid #d0d5dd; border-radius:10px; padding:7px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; }
    .pitch-coach-reference b { color:#101828; font-size:12px; line-height:16px; font-weight:800; }
    .pitch-coach-reference span { color:#667085; font-size:12px; line-height:15px; font-weight:800; }
    """
    html_text = html_text.replace("</style>", player_reference_css + "\n</style>", 1)
    return html_text


def validate_template_contract(template_html: str, report_html: str) -> None:
    selectors = {
        "sections": r'<section\b',
        "section titles": r'class="[^"]*\bsection-title\b',
        "visual cards": r'class="[^"]*\bvisual-card\b',
        "metric cards": r'class="[^"]*\bmetric-card\b',
        "coach issue cards": r'class="[^"]*\bcoach-issue-card\b',
    }
    mismatches = []
    for label, pattern in selectors.items():
        expected = len(re.findall(pattern, template_html))
        actual = len(re.findall(pattern, report_html))
        if actual != expected:
            mismatches.append(f"{label}: expected {expected}, got {actual}")
    stale = [token for token in ("bryan_player_movement", "球员Bryan", "球员Julian") if token in report_html]
    if stale:
        mismatches.append("stale subject references: " + ", ".join(stale))
    malformed_tokens = [token for token in ("<div<h4", "<h4><h4", ">lass=", "</h4>>") if token in report_html]
    if malformed_tokens:
        mismatches.append("malformed card markup: " + ", ".join(malformed_tokens))
    player_section = report_html.split("教练视角：专项问题", 1)[0]
    player_cards = len(re.findall(r'class="[^"]*\bmetric-card\b', player_section))
    player_references = len(re.findall(r'class="pitch-coach-reference"', player_section))
    if player_references != player_cards:
        mismatches.append(f"player coach-reference boxes: expected {player_cards}, got {player_references}")
    if 'class="pitch-compare-pills"' in player_section:
        mismatches.append("player cards retain three-way comparison pills")
    legend_match = re.search(r'<aside class="peer-legend coach-legend".*?</aside>', report_html, flags=re.DOTALL)
    expected_legend = [(PEER_COLORS[key], PEER_DISPLAY_NAMES[key]) for key in PEER_LEGEND_ORDER]
    actual_legend = [] if legend_match is None else re.findall(
        r'background:([^;\"]+)[^\"]*"[^>]*></i>([^<]+)', legend_match.group(0)
    )
    if actual_legend != expected_legend:
        mismatches.append(f"coach legend mismatch: expected {expected_legend}, got {actual_legend}")
    movement_assets = {
        f"{PLAYER_SLUG}_player_movement.gif": 1,
        "coach_player_movement.gif": 1,
    }
    for filename, expected in movement_assets.items():
        actual = report_html.count(f"assets/vicon_reconstruction_events/{filename}")
        if actual != expected:
            mismatches.append(f"movement asset {filename}: expected {expected}, got {actual}")
    coach_section = report_html.split("教练视角：专项问题", 1)[-1].split("研究者视角", 1)[0]
    active_titles = {PLAYER_NAME.casefold(), peer_display_name(PLAYER_KEY).casefold(), PLAYER_KEY.casefold()}
    for index, match in enumerate(
        re.finditer(r'<article class="coach-issue-card\b[^>]*>.*?</article>', coach_section, flags=re.DOTALL),
        start=1,
    ):
        card = match.group(0)
        current_titles = re.findall(
            r'class="peer-dot current-player"[^>]*title="([^":]+):', card
        )
        expected = 0 if "peer-empty" in card else 1
        if len(current_titles) != expected:
            mismatches.append(
                f"coach card {index} highlighted markers: expected {expected}, got {len(current_titles)}"
            )
        wrong_titles = [title for title in current_titles if title.strip().casefold() not in active_titles]
        if wrong_titles:
            mismatches.append(f"coach card {index} highlights a non-active player: {', '.join(wrong_titles)}")
    if mismatches:
        raise RuntimeError("Pitch template contract validation failed: " + "; ".join(mismatches))


def render_html(bundles: list[TrialBundle]) -> str:
    if TEMPLATE_DIR is None or not (TEMPLATE_DIR / "index.html").is_file():
        raise FileNotFoundError("Pitching template index.html is required for the report DOM/CSS contract.")
    template_html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
    report_html = build_template_report_html(template_html, bundles)
    validate_template_contract(template_html, report_html)
    return report_html

    # The standalone fallback below is retained temporarily for source-history
    # readability but is intentionally unreachable: final reports must honor
    # the complete template DOM contract above.
    player = next(bundle for bundle in bundles if bundle.key == PLAYER_KEY)
    coach = next(bundle for bundle in bundles if bundle.key == "coach")
    event_groups = {
        "抬腿最高点": [metric for metric in METRICS if metric["event"] == "准备阶段"],
        "前脚落地": [metric for metric in METRICS if metric["event"] == "前脚落地"],
        "出手点": [metric for metric in METRICS if metric["event"] == "出手点"],
    }

    def cards(metrics: list[dict[str, object]]) -> str:
        return "".join(metric_card(metric, bundles, coach) for metric in metrics)

    def stage(title: str, key: str) -> str:
        return f'''<section><h2>{esc(title)}</h2><div class="stage"><img src="assets/vicon_reconstruction_events/{PLAYER_SLUG}_{key}.gif" alt="{esc(PLAYER_NAME)} {esc(title)} 动作重建"><img src="assets/video_2d_alignment/{PLAYER_SLUG}_pitch_{key}_2d_overlay.png" alt="{esc(PLAYER_NAME)} {esc(title)} 2D 对齐"></div><div class="cards">{cards(event_groups[title])}</div></section>'''

    table_rows = "".join(
        f"<tr><td>{esc(metric['event'])}</td><td>{esc(metric['name'])}<br><small>{esc(metric['en'])}</small></td><td>{esc(fmt(player.values.get(str(metric['key']), float('nan')), str(metric['unit'])))}</td><td>{esc(fmt(group_mean_all(bundles, str(metric['key'])), str(metric['unit'])))}</td><td>{esc(fmt(coach.values.get(str(metric['key']), float('nan')), str(metric['unit'])))}</td><td>{esc(metric['copy'])}</td></tr>"
        for metric in METRICS
    )
    # The template is a presentation contract only.  Its body, numbers, and
    # assets are never copied into a clean-room report; only its CSS keeps the
    # standalone pitching section visually compatible with the final report.
    template_css = ""
    if TEMPLATE_DIR is not None:
        template_html = (TEMPLATE_DIR / "index.html").read_text(encoding="utf-8")
        style_match = re.search(r"<style[^>]*>(.*?)</style>", template_html, flags=re.DOTALL | re.IGNORECASE)
        if style_match:
            template_css = style_match.group(1)

    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(PLAYER_NAME)} 投球报告</title>
<style>{template_css}body{{margin:0;background:#f7f8fa;color:#101828;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1220px;margin:auto;padding:40px 24px}}h1{{font-size:40px}}h2{{margin-top:48px;border-left:8px solid #2563eb;padding-left:12px}}h3{{margin:4px 0;color:#667085}}.grid,.stage,.cards{{display:grid;gap:18px}}.grid,.stage{{grid-template-columns:repeat(2,minmax(0,1fr))}}.cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}.visual,.metric-card{{background:#fff;border:1px solid #d0d5dd;border-radius:20px;padding:18px;box-sizing:border-box}}img{{display:block;width:100%;border-radius:12px;background:#fff}}.metric-card{{display:grid;grid-template-columns:1fr 130px;gap:12px}}.metric-summary{{display:flex;flex-direction:column;gap:8px}}.metric-value{{font-size:28px;font-weight:800}}.metric-en,.metric-detail-en{{color:#667085}}.metric-detail{{grid-column:1/-1}}.peer-range{{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center}}.peer-track{{height:8px;background:#dbeafe;border-radius:99px;position:relative}}.peer-dot{{position:absolute;top:50%;transform:translate(-50%,-50%);width:11px;height:11px;border-radius:50%}}.peer-dot.current-player{{width:16px;height:16px;border:3px solid #fff;box-shadow:0 0 0 4px color-mix(in srgb,var(--marker-color,#0891b2) 25%,transparent)}}.badge{{width:max-content;padding:3px 8px;border-radius:99px;background:#dbeafe}}table{{width:100%;border-collapse:collapse;background:#fff}}td,th{{padding:10px;border:1px solid #d0d5dd;text-align:left}}@media(max-width:720px){{.grid,.stage,.cards,.metric-card{{grid-template-columns:1fr}}}}</style></head>
<body><main><h1>{esc(PLAYER_NAME)} 球员综合表现报告</h1><h3>投球 · Player / Coach / Researcher</h3>
<section><h2>球员与教练动作对照</h2><div class="grid"><article class="visual"><h3>球员{esc(PLAYER_NAME)}</h3><img src="assets/vicon_reconstruction_events/{PLAYER_SLUG}_player_movement.gif" alt="球员投球动作重建"></article><article class="visual"><h3>阿楽教练</h3><img src="assets/vicon_reconstruction_events/coach_player_movement.gif" alt="教练投球动作重建"></article></div></section>
{stage("抬腿最高点", "peak_knee")}{stage("前脚落地", "foot_plant")}{stage("出手点", "release")}
<section><h2>教练视角：专项问题</h2><div class="cards">{''.join(metric_card(metric, bundles, coach, coach_mode=True) for metric in METRICS if metric["event"] == "专项问题")}</div></section>
<section><h2>研究者视角：动力链与时间曲线</h2><div class="grid"><article class="visual"><img src="assets/kinetic_chain/{PLAYER_SLUG}_pitch_kinetic_chain_flow.png" alt="投球动力链"></article><article class="visual"><img src="assets/kinetic_chain/{PLAYER_SLUG}_kinetic_chain_time_curves.png" alt="投球动力链时间曲线"></article><article class="visual"><img src="assets/analyst_charts/{PLAYER_SLUG}_pitch_angle_time_curve.png" alt="投球角度时间曲线"></article><article class="visual"><img src="assets/analyst_charts/{PLAYER_SLUG}_pitch_speed_time_curve.png" alt="投球速度时间曲线"></article></div></section>
<section><h2>完整指标表</h2><table><thead><tr><th>事件</th><th>指标</th><th>{esc(PLAYER_NAME)}</th><th>乐风U9均值</th><th>阿楽教练</th><th>说明</th></tr></thead><tbody>{table_rows}</tbody></table></section></main></body></html>'''


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
    if "coach" not in keys:
        raise ValueError("The pitching manifest must include a coach entry with key 'coach'.")
    if not any(role == "student" and key != "coach" for key, _name, role, _c3d in result):
        raise ValueError("The pitching manifest must include at least one student/player entry.")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the pitching C3D metrics/assets expected by the combined baseball report."
    )
    parser.add_argument("--manifest", required=True, type=Path, help="JSON manifest describing athlete C3D inputs.")
    parser.add_argument(
        "--template-dir",
        required=True,
        type=Path,
        help="Pitching HTML DOM/CSS contract; all athlete values and generated asset paths are rebound.",
    )
    parser.add_argument(
        "--previous-assets",
        type=Path,
        default=None,
        help="Deprecated and rejected: pitching builds must regenerate their own assets.",
    )
    parser.add_argument("--out-dir", type=Path, default=ROOT / "reports" / "pitching")
    return parser.parse_args()


def main() -> None:
    global TEMPLATE_DIR, PREV_PITCH_ASSETS, OUT_DIR, ASSET_DIR, C3D_FILES, PLAYER_KEY, PLAYER_NAME, PLAYER_SLUG
    args = parse_args()
    TEMPLATE_DIR = args.template_dir.resolve()
    if not (TEMPLATE_DIR / "index.html").is_file():
        raise FileNotFoundError(f"Pitching template is missing index.html: {TEMPLATE_DIR}")
    if args.previous_assets is not None:
        raise ValueError("--previous-assets is no longer supported; all pitching assets must be regenerated.")
    PREV_PITCH_ASSETS = None
    OUT_DIR = args.out_dir.resolve()
    ASSET_DIR = OUT_DIR / "assets"
    C3D_FILES = load_manifest(args.manifest.resolve())
    player_rows = [row for row in C3D_FILES if row[2] == "student" and row[0] != "coach"]
    PLAYER_KEY, PLAYER_NAME, _role, _path = player_rows[0]
    PLAYER_SLUG = PLAYER_KEY.lower().replace(" ", "_")
    if OUT_DIR.exists():
        # macOS Finder sidecars can disappear between scandir and unlink.
        # The output directory is a generated clean-room target, so a vanished
        # sidecar must not make its cleanup fail.
        shutil.rmtree(OUT_DIR, ignore_errors=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    copy_static_assets()
    bundles = [load_trial_bundle(*row) for row in C3D_FILES]
    write_metric_csv(bundles)
    write_json_summary(bundles)
    annotate_lineart_metrics()
    render_reference_images(bundles)
    render_movement_gifs(bundles)
    make_metric_illustrations(bundles)
    make_kinetic_chain(bundles)
    remove_legacy_julian_assets()
    html_text = render_html(bundles)
    (OUT_DIR / "index.html").write_text(html_text, encoding="utf-8")
    prompt = ROOT / "prompts" / "pitch_report_generation.md"
    if prompt.exists():
        shutil.copy2(prompt, OUT_DIR / "PROMPT_USED.md")
    print(OUT_DIR / "index.html")


if __name__ == "__main__":
    main()
