#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


REPORT_DIR = Path(__file__).resolve().parents[1] / "reports" / "vicon_2026_julian_coach"
SRC_DIR = REPORT_DIR / "assets" / "frontend_metric_illustrations"
OUT_DIR = REPORT_DIR / "assets" / "frontend_metric_illustrations_annotated_standalone"
METRICS_CSV = REPORT_DIR / "batting_dashboard_metrics.csv"
FONT_PATH = Path("/System/Library/Fonts/PingFang.ttc")

BLUE = "#2563eb"
GREEN = "#00a85a"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
RED = "#ef4444"
GRAY = "#667085"
INK = "#101828"
LINE = "#d0d5dd"
SOFT_BLUE = "#eef6ff"
WARM = "#fffaf2"


def font(size: int, weight_index: int = 0) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_PATH), size=size, index=weight_index)


F_TITLE = font(54)
F_SUB = font(34)
F_BADGE = font(24)
F_LABEL = font(30)
F_LABEL_SMALL = font(24)
F_NOTE = font(28)


class OffsetDraw:
    """Draw using the old card-coordinate annotations on a standalone image."""

    def __init__(self, draw: ImageDraw.ImageDraw, dx: int, dy: int):
        self.draw = draw
        self.dx = dx
        self.dy = dy

    def _pt(self, pt):
        x, y = pt
        return (x + self.dx, y + self.dy)

    def _xy(self, xy):
        x1, y1, x2, y2 = xy
        return (x1 + self.dx, y1 + self.dy, x2 + self.dx, y2 + self.dy)

    def line(self, xy, **kwargs):
        if len(xy) == 2 and isinstance(xy[0], tuple):
            xy = (self._pt(xy[0]), self._pt(xy[1]))
        else:
            xy = [self._pt(pt) for pt in xy]
        return self.draw.line(xy, **kwargs)

    def ellipse(self, xy, **kwargs):
        return self.draw.ellipse(self._xy(xy), **kwargs)

    def arc(self, xy, **kwargs):
        return self.draw.arc(self._xy(xy), **kwargs)

    def polygon(self, xy, **kwargs):
        return self.draw.polygon([self._pt(pt) for pt in xy], **kwargs)

    def rounded_rectangle(self, xy, **kwargs):
        return self.draw.rounded_rectangle(self._xy(xy), **kwargs)

    def text(self, xy, *args, **kwargs):
        return self.draw.text(self._pt(xy), *args, **kwargs)

    def textbbox(self, xy, *args, **kwargs):
        return self.draw.textbbox(xy, *args, **kwargs)


def read_metric_values() -> dict[str, dict]:
    values = {}
    with METRICS_CSV.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["athlete"] != "julian":
                continue
            row["value_float"] = float(row["value"])
            try:
                row["components"] = json.loads(row["components_json"] or "{}")
            except json.JSONDecodeError:
                row["components"] = {}
            values[row["metric_key"]] = row
    return values


def fmt(metric: dict) -> str:
    value = metric["value_float"]
    unit = metric["unit"]
    if unit == "deg":
        return f"{value:.1f}°"
    if unit == "km/h":
        return f"{value:.1f} 公里/小时"
    if unit == "mm":
        return f"{value:.0f} 毫米"
    if unit == "deg/s":
        return f"{value:.0f}°/秒"
    if unit == "height_ratio":
        return f"{value:.2f} 身高"
    if "0-100" in unit:
        return f"{value:.0f}/100"
    return f"{value:.1f}"


def rounded_rect(draw: ImageDraw.ImageDraw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def label(draw: ImageDraw.ImageDraw, xy, text, color, anchor="la", small=False):
    f = F_LABEL_SMALL if small else F_LABEL
    pad_x, pad_y = 18, 12
    bbox = draw.textbbox((0, 0), text, font=f)
    w = bbox[2] - bbox[0] + pad_x * 2
    h = bbox[3] - bbox[1] + pad_y * 2
    x, y = xy
    if anchor == "ra":
        x -= w
    rounded_rect(draw, (x, y, x + w, y + h), 16, "white", color, 5)
    draw.text((x + pad_x, y + pad_y - 2), text, fill=color, font=f)


def line(draw, pts, color, width=10):
    draw.line(pts, fill=color, width=width, joint="curve")
    r = width // 2 + 3
    for x, y in pts:
        draw.ellipse((x - r, y - r, x + r, y + r), fill="white", outline=color, width=4)


def arrow(draw, p1, p2, color, width=9):
    draw.line((p1, p2), fill=color, width=width)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    size = 24
    a1 = ang + math.pi * 0.82
    a2 = ang - math.pi * 0.82
    draw.polygon(
        [
            p2,
            (p2[0] + size * math.cos(a1), p2[1] + size * math.sin(a1)),
            (p2[0] + size * math.cos(a2), p2[1] + size * math.sin(a2)),
        ],
        fill=color,
    )


def arc(draw, box, start, end, color, width=10):
    draw.arc(box, start=start, end=end, fill=color, width=width)


def dashed_line(draw, p1, p2, color=GRAY, width=5, dash=18):
    x1, y1 = p1
    x2, y2 = p2
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    steps = int(length // dash)
    for i in range(0, steps, 2):
        t1 = i / steps
        t2 = min((i + 1) / steps, 1)
        draw.line(
            (
                (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                (x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2),
            ),
            fill=color,
            width=width,
        )


def pose(kind: str):
    # Coordinates are in the final 1600x1200 card space after the 1000px figure paste.
    if kind == "ready":
        return {
            "head": (790, 450),
            "shoulder": (780, 565),
            "hands": (690, 610),
            "bat_top": (700, 330),
            "bat_low": (665, 650),
            "hip": (790, 720),
            "rear_hip": (850, 705),
            "rear_knee": (930, 850),
            "rear_ankle": (1000, 990),
            "front_knee": (625, 850),
            "front_ankle": (570, 990),
            "com": (780, 710),
            "ground_l": (540, 1035),
            "ground_r": (1040, 1035),
            "rear_elbow": (640, 625),
            "rear_shoulder": (760, 555),
        }
    return {
        "head": (690, 475),
        "shoulder": (745, 600),
        "hands": (825, 700),
        "bat_barrel": (1115, 735),
        "bat_knob": (760, 660),
        "ball": (1175, 755),
        "hip": (750, 760),
        "front_hip": (870, 785),
        "front_knee": (1010, 920),
        "front_ankle": (1110, 1010),
        "rear_knee": (560, 900),
        "rear_ankle": (480, 1030),
        "head_ready": (720, 445),
        "head_contact": (690, 475),
        "forearm": (910, 705),
        "ground_l": (450, 1040),
        "ground_r": (1135, 1040),
    }


def card(src_file: str, part: str, title: str, subtitle: str, note: str):
    canvas = Image.open(SRC_DIR / src_file).convert("RGBA").resize((1000, 1000), Image.Resampling.LANCZOS)
    # Previous annotations were authored in 1600x1200 card coordinates, where
    # the illustration tile started at (300, 235). Translate them back onto the
    # original standalone illustration and draw nothing else.
    return canvas, OffsetDraw(ImageDraw.Draw(canvas), -300, -235)


def annotate(metric_name: str, cfg: dict, values: dict[str, dict]):
    canvas, draw = card(
        cfg["src"],
        cfg["part"],
        metric_name,
        cfg["subtitle"](values),
        cfg["note"],
    )
    cfg["draw"](draw, values)
    out = OUT_DIR / cfg["out"]
    canvas.convert("RGB").save(out, quality=95)


def build_configs():
    return {
        "平衡": {
            "src": "ready_balance.png",
            "out": "ready_balance_annotated.png",
            "part": "Part 1 | Ready",
            "subtitle": lambda v: f"重心高度 {fmt(v['ready_com_height_ratio'])} + 头部位移 {fmt(v['ready_to_contact_head_displacement_mm'])}",
            "note": "重心位置越稳定、Ready 到 Contact 头部漂移越小，平衡越容易保持。",
            "draw": lambda d, v: draw_balance(d, v),
        },
        "下肢加载": {
            "src": "ready_lower_body_load.png",
            "out": "ready_lower_body_load_annotated.png",
            "part": "Part 1 | Ready",
            "subtitle": lambda v: f"后髋屈曲角 {fmt(v['ready_rear_hip_flexion_deg'])} + 后膝屈曲角 {fmt(v['ready_rear_knee_flexion_deg'])}",
            "note": "橙色/绿色夹角对应后髋和后膝加载，反映后侧下肢是否进入蓄力姿态。",
            "draw": lambda d, v: draw_lower_load(d, v),
        },
        "躯干蓄力": {
            "src": "ready_torso_coil.png",
            "out": "ready_torso_coil_annotated.png",
            "part": "Part 1 | Ready",
            "subtitle": lambda v: f"髋肩分离角 {fmt(v['ready_hip_shoulder_separation_deg'])}",
            "note": "骨盆线与肩线的预分离越清楚，后续旋转释放空间越大。",
            "draw": lambda d, v: draw_torso_coil(d, v),
        },
        "球棒准备": {
            "src": "ready_bat_readiness.png",
            "out": "ready_bat_readiness_annotated.png",
            "part": "Part 1 | Ready",
            "subtitle": lambda v: f"球棒倾角 {fmt(v['ready_bat_tilt_deg'])} + 握棒手高度 {fmt(v['ready_hand_height_ratio'])}",
            "note": "球棒角度和手部高度决定准备姿态是否处在可加载位置。",
            "draw": lambda d, v: draw_bat_ready(d, v),
        },
        "球棒效率": {
            "src": "contact_bat_efficiency.png",
            "out": "contact_bat_efficiency_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"棒头速度 {fmt(v['contact_bat_speed_kmh'])}",
            "note": "绿色大弧线是棒头运动轨迹，轨迹越长且速度越高，末端输出越充分。",
            "draw": lambda d, v: draw_bat_speed(d, v),
        },
        "挥棒轨迹": {
            "src": "contact_swing_path.png",
            "out": "contact_swing_path_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"攻击角 {fmt(v['contact_attack_angle_deg'])}",
            "note": "蓝色线表示接触瞬间棒头速度方向；接近水平说明攻击角较平。",
            "draw": lambda d, v: draw_attack_angle(d, v),
        },
        "下半身姿态": {
            "src": "contact_lower_body_posture.png",
            "out": "contact_lower_body_posture_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"骨盆旋转角 {fmt(v['contact_pelvis_rotation_open_deg'])}",
            "note": "绿色旋转弧显示 Ready 到 Contact 的骨盆打开幅度。",
            "draw": lambda d, v: draw_pelvis_rotation(d, v),
        },
        "上半身姿态": {
            "src": "contact_upper_body_posture.png",
            "out": "contact_upper_body_posture_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"躯干旋转角 {fmt(v['contact_torso_rotation_open_deg'])}",
            "note": "紫色旋转弧显示 Ready 到 Contact 的肩胸打开幅度。",
            "draw": lambda d, v: draw_torso_rotation(d, v),
        },
        "支撑能力": {
            "src": "contact_front_leg_support.png",
            "out": "contact_front_leg_support_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"前膝屈曲角 {fmt(v['contact_front_knee_flexion_deg'])}",
            "note": "橙色夹角对应前膝制动与支撑，前腿越稳越容易把旋转传到球棒。",
            "draw": lambda d, v: draw_front_knee(d, v),
        },
        "稳定性": {
            "src": "contact_stability.png",
            "out": "contact_stability_annotated.png",
            "part": "Part 2 | Contact",
            "subtitle": lambda v: f"Ready-to-Contact 头部位移 {fmt(v['ready_to_contact_head_displacement_mm'])}",
            "note": "虚线连接 Ready 与 Contact 的头部位置，用来观察挥棒过程中头部漂移。",
            "draw": lambda d, v: draw_head_displacement(d, v),
        },
        "重心偏高": {
            "src": "issue_high_center_of_mass.png",
            "out": "issue_high_center_of_mass_annotated.png",
            "part": "Part 3 | Coach Flag",
            "subtitle": lambda v: f"重心偏高指数 {fmt(v['coach_high_com_risk_index'])}；重心 {fmt(v['ready_com_height_ratio'])}",
            "note": "蓝色重心点结合后髋、后膝加载判断准备姿态是否偏高。",
            "draw": lambda d, v: draw_high_com(d, v),
        },
        "掉肘": {
            "src": "issue_dropped_rear_elbow.png",
            "out": "issue_dropped_rear_elbow_annotated.png",
            "part": "Part 3 | Coach Flag",
            "subtitle": lambda v: f"后肘相对后肩高度差 {fmt(v['coach_rear_elbow_height_diff_mm'])}",
            "note": "后肘低于后肩越多，准备阶段越容易出现掉肘风险。",
            "draw": lambda d, v: draw_dropped_elbow(d, v),
        },
        "引棒不足": {
            "src": "issue_insufficient_bat_load.png",
            "out": "issue_insufficient_bat_load_annotated.png",
            "part": "Part 3 | Coach Flag",
            "subtitle": lambda v: f"球棒加载角 {fmt(v['coach_bat_loading_angle_to_catcher_deg'])}",
            "note": "绿色方向线表示引棒方向；角度越小越接近捕手方向，加载越充分。",
            "draw": lambda d, v: draw_bat_load_angle(d, v),
        },
        "翻腕": {
            "src": "issue_early_wrist_roll.png",
            "out": "issue_early_wrist_roll_annotated.png",
            "part": "Part 3 | Coach Flag",
            "subtitle": lambda v: f"前臂翻转角速度峰值 {fmt(v['coach_rollover_forearm_roll_velocity_deg_s'])}",
            "note": "红色环形箭头表示接触附近前臂快速 roll，数值越大越需要关注翻腕。",
            "draw": lambda d, v: draw_wrist_roll(d, v),
        },
    }


def draw_balance(d, v):
    p = pose("ready")
    dashed_line(d, (p["head"][0], 390), (p["head"][0], 1010), BLUE, 5)
    d.ellipse((p["com"][0] - 22, p["com"][1] - 22, p["com"][0] + 22, p["com"][1] + 22), fill=BLUE, outline="white", width=5)
    arrow(d, (p["head"][0] + 165, 610), (p["head"][0] + 165, 715), GREEN, 8)
    label(d, (970, 520), f"重心高度 {fmt(v['ready_com_height_ratio'])}", BLUE)
    label(d, (935, 645), f"头部位移 {fmt(v['ready_to_contact_head_displacement_mm'])}", GREEN)


def draw_lower_load(d, v):
    # Match the generated ready-load pose: rear side is the viewer-right leg.
    shoulder = (790, 630)
    hip = (860, 755)
    knee = (955, 900)
    ankle = (1038, 1020)
    line(d, [shoulder, hip, knee], ORANGE)
    line(d, [hip, knee, ankle], GREEN)
    arc(d, (795, 682, 925, 812), 35, 118, ORANGE)
    arc(d, (887, 835, 1035, 985), 32, 112, GREEN)
    label(d, (990, 615), f"后髋屈曲角 {fmt(v['ready_rear_hip_flexion_deg'])}", ORANGE)
    label(d, (1010, 750), f"后膝屈曲角 {fmt(v['ready_rear_knee_flexion_deg'])}", GREEN)


def draw_torso_coil(d, v):
    p = pose("ready")
    line(d, [(660, 590), (900, 540)], PURPLE)
    line(d, [(660, 735), (910, 705)], BLUE)
    label(d, (960, 600), f"髋肩分离角 {fmt(v['ready_hip_shoulder_separation_deg'])}", BLUE)


def draw_bat_ready(d, v):
    handle = (665, 650)
    barrel = (735, 360)
    hands = (680, 640)
    line(d, [handle, barrel], BLUE)
    dashed_line(d, (560, handle[1]), (760, handle[1]), GRAY, 4)
    arc(d, (590, 520, 785, 715), 262, 350, BLUE)
    arrow(d, (850, 1035), (850, 615), GREEN, 8)
    label(d, (920, 515), f"球棒倾角 {fmt(v['ready_bat_tilt_deg'])}", BLUE)
    label(d, (930, 650), f"握棒手高度 {fmt(v['ready_hand_height_ratio'])}", GREEN)


def draw_bat_speed(d, v):
    p = pose("contact")
    line(d, [(845, 710), (1110, 790)], BLUE)
    arc(d, (635, 390, 1190, 780), 202, 327, GREEN, 12)
    arrow(d, (1070, 585), (1140, 705), GREEN, 9)
    label(d, (875, 475), f"球棒速度 {fmt(v['contact_bat_speed_kmh'])}", GREEN)


def draw_attack_angle(d, v):
    hands = (800, 725)
    barrel = (1135, 770)
    line(d, [hands, barrel], BLUE)
    dashed_line(d, (760, 760), (1190, 760), GRAY, 5)
    arrow(d, (815, 735), (1135, 770), GREEN, 9)
    arc(d, (1025, 695, 1190, 860), 338, 8, GREEN, 9)
    label(d, (975, 565), f"攻击角 {fmt(v['contact_attack_angle_deg'])}", GREEN)


def draw_pelvis_rotation(d, v):
    # Center the rotation cue on the belt/pelvis, not below the legs.
    line(d, [(650, 785), (900, 760)], GREEN)
    arc(d, (655, 665, 930, 900), 300, 70, GREEN, 12)
    arrow(d, (900, 735), (945, 770), GREEN, 9)
    label(d, (1000, 650), f"骨盆旋转角 {fmt(v['contact_pelvis_rotation_open_deg'])}", GREEN)


def draw_torso_rotation(d, v):
    # Shoulder/chest line should sit across the upper torso, not the forearms.
    line(d, [(805, 540), (875, 795)], PURPLE)
    arc(d, (685, 500, 955, 760), 295, 70, PURPLE, 12)
    arrow(d, (900, 590), (950, 630), PURPLE, 9)
    label(d, (1000, 520), f"躯干旋转角 {fmt(v['contact_torso_rotation_open_deg'])}", PURPLE)


def draw_front_knee(d, v):
    # Front side is viewer-right in this contact pose.
    hip = (815, 760)
    knee = (930, 900)
    ankle = (1010, 1030)
    line(d, [hip, knee, ankle], ORANGE)
    arc(d, (858, 840, 1000, 982), 220, 305, ORANGE, 10)
    label(d, (965, 780), f"前膝屈曲角 {fmt(v['contact_front_knee_flexion_deg'])}", ORANGE)


def draw_head_displacement(d, v):
    p = pose("contact")
    d.ellipse((p["head_ready"][0] - 18, p["head_ready"][1] - 18, p["head_ready"][0] + 18, p["head_ready"][1] + 18), fill=BLUE, outline="white", width=5)
    d.ellipse((p["head_contact"][0] - 18, p["head_contact"][1] - 18, p["head_contact"][0] + 18, p["head_contact"][1] + 18), fill=GREEN, outline="white", width=5)
    dashed_line(d, p["head_ready"], p["head_contact"], RED, 6)
    label(d, (930, 500), f"头部位移 {fmt(v['ready_to_contact_head_displacement_mm'])}", RED)


def draw_high_com(d, v):
    p = pose("ready")
    d.ellipse((p["com"][0] - 24, p["com"][1] - 24, p["com"][0] + 24, p["com"][1] + 24), fill=BLUE, outline="white", width=5)
    arrow(d, (p["com"][0] + 135, 1035), (p["com"][0] + 135, p["com"][1] - 35), BLUE, 8)
    label(d, (940, 560), f"重心 {fmt(v['ready_com_height_ratio'])}", BLUE)


def draw_dropped_elbow(d, v):
    shoulder = (705, 625)
    elbow = (640, 665)
    dashed_line(d, (shoulder[0] - 80, shoulder[1]), (shoulder[0] + 250, shoulder[1]), BLUE, 5)
    d.ellipse((shoulder[0] - 16, shoulder[1] - 16, shoulder[0] + 16, shoulder[1] + 16), fill=BLUE, outline="white", width=4)
    d.ellipse((elbow[0] - 18, elbow[1] - 18, elbow[0] + 18, elbow[1] + 18), fill=ORANGE, outline="white", width=4)
    arrow(d, (shoulder[0] + 65, shoulder[1]), (shoulder[0] + 65, elbow[1]), ORANGE, 8)
    label(d, (900, 570), f"后肘高度差 {fmt(v['coach_rear_elbow_height_diff_mm'])}", ORANGE)


def draw_bat_load_angle(d, v):
    p = pose("ready")
    line(d, [(665, 650), (735, 360)], BLUE)
    arrow(d, (p["hands"][0], p["hands"][1]), (500, 735), GREEN, 8)
    dashed_line(d, (p["hands"][0], p["hands"][1]), (470, 610), GRAY, 5)
    arc(d, (480, 545, 730, 790), 165, 210, GREEN, 10)
    label(d, (900, 595), f"球棒加载角 {fmt(v['coach_bat_loading_angle_to_catcher_deg'])}", GREEN)


def draw_wrist_roll(d, v):
    hands = (900, 700)
    barrel = (1120, 835)
    line(d, [hands, barrel], BLUE)
    arc(d, (805, 605, 995, 795), 300, 80, RED, 12)
    arrow(d, (965, 675), (970, 725), RED, 9)
    d.ellipse((hands[0] - 18, hands[1] - 18, hands[0] + 18, hands[1] + 18), fill=RED, outline="white", width=5)
    label(d, (955, 595), f"前臂翻转峰值 {fmt(v['coach_rollover_forearm_roll_velocity_deg_s'])}", RED)


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    values = read_metric_values()
    manifest = []
    configs = build_configs()
    for metric, cfg in configs.items():
        annotate(metric, cfg, values)
        manifest.append(
            {
                "module": cfg["part"].split("|", 1)[-1].strip(),
                "metric": metric,
                "source_file": cfg["src"],
                "annotated_file": cfg["out"],
                "subtitle": cfg["subtitle"](values),
            }
        )
    (OUT_DIR / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(manifest)} annotated illustrations to {OUT_DIR}")


if __name__ == "__main__":
    main()
