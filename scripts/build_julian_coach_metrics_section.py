from __future__ import annotations

import argparse
import csv
import html
import json
import math
import re
import shutil
import zipfile
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics.csv"
DEFAULT_OUT = ROOT / "reports" / "vicon_2026_julian_coach" / "julian_coach_metrics_section.html"
DEFAULT_PEERS = ROOT / "outputs" / "batting_metrics_excel" / "all_players"
DEFAULT_PEER_METRICS_GLOB = "vicon_2026_*/batting_dashboard_metrics.csv"
DEFAULT_POSE3D = ROOT / "reports" / "vicon_2026_julian_coach" / "vicon_2026_pose3d.csv"
DEFAULT_PITCH_REPORT = ROOT.parent / "julian_pitch_template_report_2026-07-06" / "index.html"
PITCH_ASSET_PREFIX = "pitch_assets"
ACTIVE_OUT_DIR = DEFAULT_OUT.parent
ACTIVE_PLAYER_SAMPLE = "julian"
ACTIVE_COACH_SAMPLE = "coach"
ACTIVE_PLAYER_SLUG = "julian"
ACTIVE_PLAYER_LABEL = "Julian"


UNIT_CN = {
    "deg": "°",
    "deg/s": "°/s",
    "km/h": "km/h",
    "mm": "mm",
    "height_ratio": "身高比",
    "0-100 risk": "风险分",
    "0-100 score": "分",
}


BACKEND_ORDER = [
    "ready_com_height_ratio",
    "ready_rear_hip_flexion_deg",
    "ready_rear_knee_flexion_deg",
    "ready_hip_shoulder_separation_deg",
    "ready_bat_tilt_deg",
    "ready_hand_height_ratio",
    "contact_bat_speed_kmh",
    "contact_attack_angle_deg",
    "contact_pelvis_rotation_open_deg",
    "contact_torso_rotation_open_deg",
    "contact_front_knee_flexion_deg",
    "ready_to_contact_head_displacement_mm",
    "coach_high_com_risk_index",
    "coach_rear_elbow_height_diff_mm",
    "coach_bat_loading_angle_to_catcher_deg",
    "coach_rollover_forearm_roll_velocity_deg_s",
    "coach_hitting_zone_stability_score",
]


FRONT_METRICS = [
    ("Ready Position", "平衡", [("ready_com_height_ratio", 0.6), ("ready_to_contact_head_displacement_mm", 0.4)], "ready_com_height_ratio"),
    ("Ready Position", "下肢加载", [("ready_rear_hip_flexion_deg", 0.5), ("ready_rear_knee_flexion_deg", 0.5)], "ready_rear_hip_flexion_deg"),
    ("Ready Position", "躯干蓄力", [("ready_hip_shoulder_separation_deg", 1.0)], "ready_hip_shoulder_separation_deg"),
    ("Ready Position", "球棒准备", [("ready_bat_tilt_deg", 0.55), ("ready_hand_height_ratio", 0.45)], "ready_bat_tilt_deg"),
    ("Contact Position", "球棒效率", [("contact_bat_speed_kmh", 1.0)], "contact_bat_speed_kmh"),
    ("Contact Position", "挥棒轨迹", [("contact_attack_angle_deg", 1.0)], "contact_attack_angle_deg"),
    ("Contact Position", "下半身姿态", [("contact_pelvis_rotation_open_deg", 1.0)], "contact_pelvis_rotation_open_deg"),
    ("Contact Position", "上半身姿态", [("contact_torso_rotation_open_deg", 1.0)], "contact_torso_rotation_open_deg"),
    ("Contact Position", "支撑能力", [("contact_front_knee_flexion_deg", 1.0)], "contact_front_knee_flexion_deg"),
    ("Contact Position", "稳定性", [("ready_to_contact_head_displacement_mm", 1.0)], "ready_to_contact_head_displacement_mm"),
    ("专项问题", "重心偏高", [("coach_high_com_risk_index", 1.0)], "coach_high_com_risk_index"),
    ("专项问题", "掉肘", [("coach_rear_elbow_height_diff_mm", 1.0)], "coach_rear_elbow_height_diff_mm"),
    ("专项问题", "引棒不足", [("coach_bat_loading_angle_to_catcher_deg", 1.0)], "coach_bat_loading_angle_to_catcher_deg"),
    ("专项问题", "翻腕", [("coach_rollover_forearm_roll_velocity_deg_s", 1.0)], "coach_rollover_forearm_roll_velocity_deg_s"),
]


FRONT_EXPLANATIONS = {
    "平衡": "准备姿态和启动过程中的身体控制会直接影响看球稳定性。",
    "下肢加载": "后腿和髋部是否提前进入可发力姿态，会影响后续挥棒力量。",
    "躯干蓄力": "上、下半身能否形成适当的扭转，是身体储存力量的重要环节。",
    "球棒准备": "球棒和双手是否处在合适位置，会影响启动空间和加速距离。",
    "球棒效率": "击球瞬间球棒速度越稳定，越说明身体力量传递得顺畅。",
    "挥棒轨迹": "球棒进入击球区的方式会影响击球容错和击球质量。",
    "下半身姿态": "下半身打开和支撑顺序决定力量能否顺利传到上半身。",
    "上半身姿态": "上半身稳定打开有助于维持击球点、视线和旋转传递。",
    "支撑能力": "前腿落地后的支撑质量，会影响身体制动和力量释放。",
    "稳定性": "从准备到击球的身体稳定性，会直接影响看球和击球准确性。",
    "重心偏高": "准备姿态如果站得过高，通常会影响下肢蓄力和启动速度。",
    "掉肘": "后肘位置会影响引棒空间和挥棒平面是否稳定。",
    "引棒不足": "引棒空间不足时，后续加速距离会变短，挥棒力量不容易完全释放。",
    "翻腕": "手腕过早翻转会影响击球面稳定，容易降低击球质量。",
}


BACKEND_EN = {
    "ready_com_height_ratio": "Ready Body Height",
    "ready_rear_hip_flexion_deg": "Rear Hip Load",
    "ready_rear_knee_flexion_deg": "Rear Knee Load",
    "ready_hip_shoulder_separation_deg": "Hip-shoulder Separation Angle",
    "ready_bat_tilt_deg": "Bat Angle at Ready",
    "ready_hand_height_ratio": "Hand Height",
    "contact_bat_speed_kmh": "Bat Speed",
    "contact_attack_angle_deg": "Attack Angle",
    "contact_pelvis_rotation_open_deg": "Pelvis Rotation",
    "contact_torso_rotation_open_deg": "Torso Rotation",
    "contact_front_knee_flexion_deg": "Front Knee Support",
    "ready_to_contact_head_displacement_mm": "Head Stability",
    "coach_high_com_risk_index": "High Center of Mass",
    "coach_rear_elbow_height_diff_mm": "Dropped Rear Elbow",
    "coach_bat_loading_angle_to_catcher_deg": "Bat Load",
    "coach_rollover_forearm_roll_velocity_deg_s": "Early Wrist Roll",
    "coach_hitting_zone_stability_score": "Hitting Zone Stability",
}


EXPLANATIONS_EN = {
    "ready_com_height_ratio": "The ready stance is close to the coach example, and the next priority is keeping that athletic height without standing up during the move to contact.",
    "ready_rear_hip_flexion_deg": "The rear hip is already loading well. Training should keep the player feeling pressure in the back leg before the swing starts.",
    "ready_rear_knee_flexion_deg": "The rear knee is in a useful athletic position. Keeping this flexion stable will help the player start with better rhythm and balance.",
    "ready_hip_shoulder_separation_deg": "The upper body is following the lower body too quickly. Holding the shoulders back a little longer will help store more rotational power.",
    "ready_bat_tilt_deg": "The bat is prepared in a position that still limits loading space. A cleaner bat angle will give the player a smoother acceleration path.",
    "ready_hand_height_ratio": "The hands can be held a little more usefully before launch. Better hand height helps protect rear-elbow space and keeps the swing path cleaner.",
    "contact_bat_speed_kmh": "Bat speed is within the U8-U10 reference range, with room to move toward the upper end as the lower body, trunk, and arms connect more smoothly.",
    "contact_attack_angle_deg": "The bat path through the hitting zone can become more repeatable. A steadier entry gives the player more room for timing differences.",
    "contact_pelvis_rotation_open_deg": "The hips are opening actively, but the timing still needs to match the front-side support so lower-body force can move upward.",
    "contact_torso_rotation_open_deg": "The trunk is active at contact. The next step is keeping chest direction and vision stable while rotating.",
    "contact_front_knee_flexion_deg": "Front-side support needs to become stronger. A firmer front leg helps the body brake and release rotational force into the bat.",
    "ready_to_contact_head_displacement_mm": "The head and upper body can stay quieter during the swing. Better stability helps the eyes track the ball and repeat the contact point.",
    "coach_high_com_risk_index": "Body height is controlled well in the ready stance. The player should keep the knees and hips flexed under game pressure.",
    "coach_rear_elbow_height_diff_mm": "The rear elbow is acceptable, but the habit needs to become more consistent so the player keeps loading room before launch.",
    "coach_bat_loading_angle_to_catcher_deg": "The player has basic loading space. A more complete load will give the bat a longer and smoother acceleration path.",
    "coach_rollover_forearm_roll_velocity_deg_s": "The wrist tends to roll a little early near contact. Keeping the barrel face through the ball will improve contact quality.",
    "coach_hitting_zone_stability_score": "The bat can stay available through the hitting zone a little longer. This will help the player make more solid contact on timing variations.",
}


FRONT_FEEDBACK = {
    "平衡": "该球员准备时身体控制总体不错，但启动到击球过程中还要继续减少头部和身体的多余晃动。这样有助于稳定看球视线，让挥棒更容易找到准确的击球点。",
    "下肢加载": "该球员后侧腿已经能较好地进入蓄力姿态，这是一个很好的基础。后续训练可以继续保持后腿承重和髋部坐入的感觉，把下半身力量更稳定地送到挥棒里。",
    "躯干蓄力": "目前下半身启动后，上半身跟进得较快，身体储存力量的时间略短。建议训练中多做髋部先启动、肩膀稍微保留的练习，让身体旋转力量有更多时间传到球棒。",
    "球棒准备": "球棒和双手已经有基本准备位置，但引棒空间还可以更充分。训练时要注意双手高度、后肘空间和球棒角度，让启动时球棒有更顺畅的加速距离。",
    "球棒效率": "击球瞬间的球棒速度还有提升空间，主要需要让下肢、髋部、躯干和手臂衔接得更顺。训练重点不是单纯加快手，而是让身体先带动，再把力量传到球棒。",
    "挥棒轨迹": "该球员的挥棒进入击球区时，球棒路径还可以更稳定。建议通过固定击球区挥棒、T 座不同高度击球等练习，减少过度下砍或过度上挑，让球棒在好球带里停留更久。",
    "下半身姿态": "击球时下半身打开和支撑顺序还不够理想，部分力量没有充分向上半身传递。训练中可以重点练习前脚落地后髋部继续旋转，避免身体过早被手臂带走。",
    "上半身姿态": "上半身在击球阶段表现比较积极，能够参与旋转和完成挥棒。接下来要继续保持胸口方向和视线稳定，避免为了发力而出现上身后仰或提前拉开。",
    "支撑能力": "前腿落地后的支撑还需要加强。前腿如果不能稳定制动，身体旋转力量就容易散掉，建议增加前脚落地定住、前膝稳定和髋部继续转动的分解练习。",
    "稳定性": "从准备到击球过程中，该球员的身体移动幅度还可以再控制。头部和上身越稳定，眼睛越容易跟住球，击球点也会更稳定。",
    "重心偏高": "该球员准备姿态的重心控制较好，没有明显站得过高的问题。后续要继续保持膝髋微屈、后腿有承重的准备状态，避免比赛中因为紧张而站直。",
    "掉肘": "该球员后肘位置整体可以接受，但还需要稳定成习惯。训练中保持后肘有空间、双手不过早掉低，可以让引棒更顺，也能减少挥棒平面被压低的情况。",
    "引棒不足": "该球员的引棒已经具备基本空间，但仍可以做得更完整。建议让球棒在启动前有更充分的向后加载，给后续加速留出更长、更顺的发力距离。",
    "翻腕": "该球员击球附近手腕有偏早翻转的倾向，这会影响击球面稳定。训练时应强调手掌控制球棒面、延长穿过球的感觉，先把球打扎实，再追求更快的挥棒。",
}


FRONT_FEEDBACK_EN = {
    "平衡": "The player shows generally solid body control in the ready position, but should continue reducing extra head and body movement during the move into contact. A steadier body helps keep the eyes on the ball and makes it easier to find a consistent contact point.",
    "下肢加载": "The player's back side already loads well, which gives a strong foundation. Future training should keep reinforcing back-leg pressure and hip loading so lower-body power can transfer more consistently into the swing.",
    "躯干蓄力": "At the moment, the player's upper body follows the lower-body start a little quickly, so the body has less time to store rotational power. Training should emphasize the hips starting first while the shoulders stay back slightly, giving the rotation more time to move into the bat.",
    "球棒准备": "The bat and hands are in a basic ready position, but the player can still create more loading space. In training, attention should stay on hand height, rear-elbow room, and bat angle so the bat has a smoother path to accelerate.",
    "球棒效率": "Bat speed at contact still has room to improve, mainly by making the lower body, hips, trunk, and arms connect more smoothly. The priority is not simply swinging the hands faster, but letting the body lead and then transferring that force into the bat.",
    "挥棒轨迹": "The player's bat path through the hitting zone can become more stable. Tee work at different heights and controlled zone-swing drills can help reduce excessive chopping or lifting, keeping the barrel in the strike zone longer.",
    "下半身姿态": "At contact, the lower-body opening and support sequence are not yet ideal, so some force is not fully transferred upward. Training should focus on letting the hips continue rotating after the front foot lands, instead of allowing the arms to take over too early.",
    "上半身姿态": "The player's upper body is active through contact and contributes to the swing. The next step is to keep the chest direction and vision stable, avoiding leaning back or opening too early when trying to generate power.",
    "支撑能力": "Front-leg support after landing needs to become stronger. If the front leg cannot brace well, rotational force can leak away, so drills should include front-foot landing control, front-knee stability, and continued hip rotation.",
    "稳定性": "The player can still control body movement better from the ready position to contact. The steadier the head and upper body are, the easier it is to track the ball and repeat the contact point.",
    "重心偏高": "The player controls body height well in the ready position and does not show a clear issue of standing too tall. The player should continue keeping the knees and hips slightly flexed with weight loaded into the back leg, especially when game pressure rises.",
    "掉肘": "The player's rear-elbow position is generally acceptable, but it still needs to become a stable habit. Keeping space around the rear elbow and preventing the hands from dropping too early will support a smoother load and a cleaner swing plane.",
    "引棒不足": "The player already has basic loading space, but the load can still become more complete. The bat should load farther back before launch, giving the player a longer and smoother acceleration path.",
    "翻腕": "The player shows a tendency for the wrist to roll a little early around contact, which can affect barrel stability. Training should emphasize controlling the barrel face with the hands and extending through the ball, prioritizing solid contact before chasing more bat speed.",
}


PEER_COLORS = ["#2563eb", "#16a34a", "#f97316", "#a855f7", "#ef4444", "#0891b2", "#ca8a04", "#db2777", "#475569"]
PEER_COLOR_BY_NAME = {
    "bryan": "#2563eb",
    "7zai": "#16a34a",
    "xuanxuan": "#f97316",
    "green": "#a855f7",
    "julian": "#ef4444",
    "youyou": "#0891b2",
    "james": "#ca8a04",
    "branden": "#db2777",
    "brandon": "#db2777",
}
PEER_DISPLAY_BY_NAME = {
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
PEER_LEGEND_ORDER = (
    "bryan",
    "7zai",
    "xuanxuan",
    "green",
    "julian",
    "youyou",
    "james",
    "branden",
    "brandon",
)
BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#f97316"
RED = "#ef4444"
PURPLE = "#7c3aed"
INK = "#101828"
MID = "#667085"


def peer_key(name: object) -> str:
    return str(name or "").strip().casefold().replace(" ", "")


def peer_color(name: object, fallback_index: int = 0) -> str:
    return PEER_COLOR_BY_NAME.get(peer_key(name), PEER_COLORS[fallback_index % len(PEER_COLORS)])


def peer_display_name(name: object) -> str:
    raw_name = str(name or "peer")
    return PEER_DISPLAY_BY_NAME.get(peer_key(raw_name), raw_name)

BAT_SPEED_U8_U10_GOOD_MIN_KMH = 48.0
BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH = 72.0


def pil_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    )
    for path in candidates:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def anonymous_peer_label(index: int) -> str:
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if index < len(alphabet):
        return f"球员{alphabet[index]}"
    return f"球员{index + 1}"


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def linear_score(value: float, low: float, high: float, higher_is_better: bool = True) -> float:
    if high == low:
        return 50.0
    ratio = (value - low) / (high - low)
    if not higher_is_better:
        ratio = 1.0 - ratio
    return clamp(ratio * 100.0)


def target_score(value: float, target: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 50.0
    return clamp(100.0 - abs(value - target) / tolerance * 100.0)


def safe_float(value: str | None) -> float | None:
    x = num(value)
    if x is None or not math.isfinite(x):
        return None
    return x


PEER_SCORE_SOURCES = {
    "平衡": "其他球员使用 ready_com_height_ratio + ready_to_contact_head_displacement_mm",
    "下肢加载": "其他球员使用 ready_rear_hip_flexion_deg + ready_rear_knee_flexion_deg",
    "躯干蓄力": "其他球员使用 ready_hip_shoulder_separation_deg",
    "球棒准备": "其他球员使用 ready_bat_tilt_deg + ready_hand_height_ratio",
    "球棒效率": "其他球员使用 contact_bat_speed_kmh",
    "挥棒轨迹": "其他球员使用 contact_attack_angle_deg",
    "下半身姿态": "其他球员使用 contact_pelvis_rotation_open_deg",
    "上半身姿态": "其他球员使用 contact_torso_rotation_open_deg",
    "支撑能力": "其他球员使用 contact_front_knee_flexion_deg",
    "稳定性": "其他球员使用 ready_to_contact_head_displacement_mm",
    "重心偏高": "其他球员使用 coach_high_com_risk_index",
    "掉肘": "其他球员使用 coach_rear_elbow_height_diff_mm",
    "引棒不足": "其他球员使用 coach_bat_loading_angle_to_catcher_deg",
    "翻腕": "其他球员使用 coach_rollover_forearm_roll_velocity_deg_s",
}


PEER_AXIS_KEYS = {
    "平衡": "ready_com_height_ratio",
    "下肢加载": "ready_rear_hip_flexion_deg",
    "躯干蓄力": "ready_hip_shoulder_separation_deg",
    "球棒准备": "ready_bat_tilt_deg",
    "球棒效率": "contact_bat_speed_kmh",
    "挥棒轨迹": "contact_attack_angle_deg",
    "下半身姿态": "contact_pelvis_rotation_open_deg",
    "上半身姿态": "contact_torso_rotation_open_deg",
    "支撑能力": "contact_front_knee_flexion_deg",
    "稳定性": "ready_to_contact_head_displacement_mm",
    "重心偏高": "coach_high_com_risk_index",
    "掉肘": "coach_rear_elbow_height_diff_mm",
    "引棒不足": "coach_bat_loading_angle_to_catcher_deg",
    "翻腕": "coach_rollover_forearm_roll_velocity_deg_s",
}


BACKEND_FIELD_KEYS = {
    "重心高度": "ready_com_height_ratio",
    "后髋屈曲角": "ready_rear_hip_flexion_deg",
    "后膝屈曲角": "ready_rear_knee_flexion_deg",
    "髋肩分离角": "ready_hip_shoulder_separation_deg",
    "球棒倾角": "ready_bat_tilt_deg",
    "握棒手高度": "ready_hand_height_ratio",
    "球棒速度": "contact_bat_speed_kmh",
    "挥棒路径角": "contact_attack_angle_deg",
    "骨盆旋转角": "contact_pelvis_rotation_open_deg",
    "躯干旋转角": "contact_torso_rotation_open_deg",
    "前膝屈曲角": "contact_front_knee_flexion_deg",
    "头部位移": "ready_to_contact_head_displacement_mm",
    "重心偏高指数": "coach_high_com_risk_index",
    "后肘高度差（掉肘）": "coach_rear_elbow_height_diff_mm",
    "球棒加载角（引棒不足）": "coach_bat_loading_angle_to_catcher_deg",
    "手腕翻转角速度（翻腕）": "coach_rollover_forearm_roll_velocity_deg_s",
    "击球区稳定性": "coach_hitting_zone_stability_score",
}


XLSX_UNIT_KEYS = {
    "%身高": "height_ratio",
    "风险分": "0-100 risk",
    "分": "0-100 score",
}


METRIC_ILLUSTRATIONS = {
    "平衡": "ready_balance_annotated.png",
    "下肢加载": "ready_lower_body_load_annotated.png",
    "躯干蓄力": "ready_torso_coil_annotated.png",
    "球棒准备": "ready_bat_readiness_annotated.png",
    "球棒效率": "contact_bat_efficiency_annotated.png",
    "挥棒轨迹": "contact_swing_path_annotated.png",
    "下半身姿态": "contact_lower_body_posture_annotated.png",
    "上半身姿态": "contact_upper_body_posture_annotated.png",
    "支撑能力": "contact_front_leg_support_annotated.png",
    "稳定性": "contact_stability_annotated.png",
    "重心偏高": "issue_high_center_of_mass_annotated.png",
    "掉肘": "issue_dropped_rear_elbow_annotated.png",
    "引棒不足": "issue_insufficient_bat_load_annotated.png",
    "翻腕": "issue_early_wrist_roll_annotated.png",
}


BACKEND_ILLUSTRATION_NAMES = {
    "ready_com_height_ratio": "平衡",
    "ready_rear_hip_flexion_deg": "下肢加载",
    "ready_rear_knee_flexion_deg": "下肢加载",
    "ready_hip_shoulder_separation_deg": "躯干蓄力",
    "ready_bat_tilt_deg": "球棒准备",
    "ready_hand_height_ratio": "球棒准备",
    "contact_bat_speed_kmh": "球棒效率",
    "contact_attack_angle_deg": "挥棒轨迹",
    "contact_pelvis_rotation_open_deg": "下半身姿态",
    "contact_torso_rotation_open_deg": "上半身姿态",
    "contact_front_knee_flexion_deg": "支撑能力",
    "ready_to_contact_head_displacement_mm": "稳定性",
    "coach_high_com_risk_index": "重心偏高",
    "coach_rear_elbow_height_diff_mm": "掉肘",
    "coach_bat_loading_angle_to_catcher_deg": "引棒不足",
    "coach_rollover_forearm_roll_velocity_deg_s": "翻腕",
    "coach_hitting_zone_stability_score": "挥棒轨迹",
}


ISSUE_BACKEND_KEYS = {
    "coach_high_com_risk_index",
    "coach_rear_elbow_height_diff_mm",
    "coach_bat_loading_angle_to_catcher_deg",
    "coach_rollover_forearm_roll_velocity_deg_s",
}


EXPLANATIONS = {
    "ready_com_height_ratio": "准备姿态整体接近教练示范，说明孩子已经有较好的站姿基础。后续要注意启动时不要突然站高，继续保持膝髋微屈，让下半身随时能发力。",
    "ready_rear_hip_flexion_deg": "后侧髋部已经能够较好地坐入，这是形成下半身力量的好基础。训练中要继续保持后腿承重感，让启动更稳、更有弹性。",
    "ready_rear_knee_flexion_deg": "后膝保持在比较有运动感的位置，有利于启动时快速发力。接下来重点是把这个姿态稳定成习惯，避免比赛中因为紧张而站直。",
    "ready_hip_shoulder_separation_deg": "下半身启动后，上半身跟进得较快，身体储存力量的时间略短。建议多练髋部先走、肩膀稍微保留，让旋转力量更充分地传到球棒。",
    "ready_bat_tilt_deg": "球棒准备角度还有调整空间，目前容易让引棒和加速路线变短。训练时要让双手、后肘和球棒形成更舒服的启动空间。",
    "ready_hand_height_ratio": "握棒手位置还可以更稳定一些。双手保持在合适高度，能给后肘留出空间，也能让球棒启动时更顺。",
    "contact_bat_speed_kmh": "击球附近的球棒速度已经处在 U8-U10 调研参考范围内，后续重点是继续向区间上沿提升，让下肢、躯干和手臂的发力衔接更顺。",
    "contact_attack_angle_deg": "球棒进入击球区的路线还可以更稳定。路径稳定后，孩子面对不同高低和时机的球，会更容易把球打扎实。",
    "contact_pelvis_rotation_open_deg": "髋部打开比较积极，但还需要和前侧支撑配合得更好。前脚落地后髋部继续带动身体，力量才不容易提前散掉。",
    "contact_torso_rotation_open_deg": "上半身在击球阶段参与得比较主动，这是积极的一面。后续要继续保持胸口方向和视线稳定，避免为了发力而过早拉开。",
    "contact_front_knee_flexion_deg": "前腿支撑还有提升空间。前侧如果不能稳定顶住，身体旋转力量就不容易完整传到球棒，建议加强前脚落地定住和前膝稳定练习。",
    "ready_to_contact_head_displacement_mm": "从准备到击球，头部和上身移动还可以再安静一些。身体越稳，眼睛越容易跟住球，击球点也越容易重复。",
    "coach_high_com_risk_index": "准备姿态的重心控制较好，没有明显站得过高的问题。继续保持膝髋微屈、后腿有承重的准备状态即可。",
    "coach_rear_elbow_height_diff_mm": "后肘位置整体可以接受，但需要更稳定地形成习惯。保持后肘有空间，可以让引棒更顺，也能减少挥棒平面被压低。",
    "coach_bat_loading_angle_to_catcher_deg": "孩子已经具备基本引棒空间，后续可以做得更完整。启动前让球棒有更充分的向后加载，会给加速留出更长、更顺的距离。",
    "coach_rollover_forearm_roll_velocity_deg_s": "击球附近有偏早翻腕的倾向，容易让球棒面不够稳定。训练时要强调手掌控制球棒面，延长穿过球的感觉。",
    "coach_hitting_zone_stability_score": "球棒在好球带里的停留还可以更稳定。让球棒更久地穿过击球区，有助于提高扎实击球的机会。",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def col_to_index(cell_ref: str) -> int:
    letters = re.sub(r"\d", "", cell_ref)
    value = 0
    for char in letters:
        value = value * 26 + (ord(char.upper()) - 64)
    return value - 1


def read_xlsx_rows(path: Path, sheet_name: str) -> list[list[object]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as zf:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in zf.namelist():
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall("m:si", ns):
                shared.append("".join(t.text or "" for t in si.findall(".//m:t", ns)))

        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        rel_targets = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels
        }
        sheet_path = None
        rel_key = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in workbook.findall("m:sheets/m:sheet", ns):
            if sheet.attrib.get("name") == sheet_name:
                target = rel_targets[sheet.attrib[rel_key]]
                target = target.lstrip("/")
                sheet_path = target if target.startswith("xl/") else "xl/" + target
                break
        if not sheet_path:
            return []

        sheet_root = ET.fromstring(zf.read(sheet_path))
        rows: list[list[object]] = []
        for row in sheet_root.findall(".//m:sheetData/m:row", ns):
            cells: list[object] = []
            for cell in row.findall("m:c", ns):
                idx = col_to_index(cell.attrib.get("r", "A1"))
                while len(cells) <= idx:
                    cells.append(None)
                cell_type = cell.attrib.get("t")
                value_node = cell.find("m:v", ns)
                inline_node = cell.find("m:is/m:t", ns)
                value: object = ""
                if cell_type == "s" and value_node is not None:
                    value = shared[int(value_node.text or 0)]
                elif cell_type == "inlineStr" and inline_node is not None:
                    value = inline_node.text or ""
                elif value_node is not None:
                    raw = value_node.text or ""
                    try:
                        value = float(raw)
                        if value.is_integer():
                            value = int(value)
                    except ValueError:
                        value = raw
                cells[idx] = value
            rows.append(cells)
        return rows


def cell_at(row: list[object], idx: int) -> object:
    return row[idx] if idx < len(row) else None


def athlete_from_xlsx(path: Path) -> str:
    for row in read_xlsx_rows(path, "说明"):
        if cell_at(row, 0) == "数据来源":
            source = str(cell_at(row, 1) or "")
            parts = source.split("/")
            if len(parts) >= 2:
                return parts[1]
    return path.name.replace("_batting_report_metrics.xlsx", "")


def xlsx_metric_record(path: Path) -> dict[str, object]:
    athlete = athlete_from_xlsx(path)
    rows_by_key: dict[str, dict[str, str]] = {}
    for row in read_xlsx_rows(path, "报告指标"):
        backend = cell_at(row, 2)
        backend_name = normalize_metric_name(backend)
        key = BACKEND_FIELD_KEYS.get(backend_name)
        value = safe_float(str(cell_at(row, 3))) if cell_at(row, 3) not in (None, "") else None
        if not key or value is None:
            continue
        unit = str(cell_at(row, 4) or "")
        if unit == "%身高":
            value = value / 100.0
        rows_by_key[key] = {
            "metric_key": key,
            "metric_name_zh": backend_name,
            "value": str(value),
            "unit": XLSX_UNIT_KEYS.get(unit, unit),
        }
    return {"name": athlete, "rows": rows_by_key}


def csv_peer_metric_records() -> dict[str, dict[str, object]]:
    records: dict[str, dict[str, object]] = {}
    for csv_path in sorted((ROOT / "reports").glob(DEFAULT_PEER_METRICS_GLOB)):
        for row in read_csv(csv_path):
            name = row.get("sample_name") or row.get("athlete") or ""
            key = row.get("metric_key") or ""
            value = row.get("value")
            if not name or name == "coach" or key not in BACKEND_ORDER or value in (None, ""):
                continue
            record = records.setdefault(name, {"name": name, "rows": {}})
            metric_rows = record["rows"]
            if not isinstance(metric_rows, dict):
                continue
            metric_rows[key] = {
                "metric_key": key,
                "metric_name_zh": row.get("metric_name_zh") or key,
                "value": str(value),
                "unit": row.get("unit") or "",
            }
    return records


def supplement_peer_records_from_csv(records: list[dict[str, object]]) -> list[dict[str, object]]:
    csv_records = csv_peer_metric_records()
    records_by_name = {str(record.get("name") or ""): record for record in records}
    for name, csv_record in csv_records.items():
        record = records_by_name.get(name)
        if record is None:
            record = {"name": name, "rows": {}}
            records.append(record)
            records_by_name[name] = record
        rows = record.get("rows")
        csv_rows = csv_record.get("rows")
        if not isinstance(rows, dict) or not isinstance(csv_rows, dict):
            continue
        for key, metric_row in csv_rows.items():
            rows.setdefault(key, metric_row)
    return records


def read_peer_metrics(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return list(csv_peer_metric_records().values())
    if path.is_dir():
        files = sorted(p for p in path.glob("*_batting_report_metrics.xlsx") if not p.name.startswith("._"))
    else:
        files = [path]
    records = []
    for file_path in files:
        record = xlsx_metric_record(file_path)
        if record["name"] == "coach":
            continue
        if record["rows"]:
            records.append(record)
    return supplement_peer_records_from_csv(records)


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def num(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def unit_cn(unit: str | None) -> str:
    return UNIT_CN.get(unit or "", unit or "")


def fmt(value: str | float | None, unit: str | None) -> str:
    x = num(str(value)) if value is not None else None
    if x is None:
        return "暂无"
    if unit == "height_ratio":
        text = f"{x:.3f}"
    elif unit in {"0-100 risk", "0-100 score"}:
        text = f"{x:.1f}"
    elif abs(x) >= 100:
        text = f"{x:.0f}"
    elif abs(x) >= 10:
        text = f"{x:.1f}"
    else:
        text = f"{x:.2f}"
    label = unit_cn(unit)
    return f"{text}{label}" if label in {"度", "毫米", "分"} else f"{text} {label}".strip()


def delta_text(julian: dict[str, str], coach: dict[str, str] | None) -> str:
    jv = num(julian.get("value"))
    cv = num(coach.get("value")) if coach else None
    unit = julian.get("unit", "")
    if jv is None or cv is None:
        return "暂无对照"
    diff = jv - cv
    sign = "+" if diff > 0 else ""
    return f"{sign}{fmt(diff, unit)}"


def status_for(metric_key: str, julian: dict[str, str], coach: dict[str, str] | None) -> tuple[str, str]:
    jv = num(julian.get("value"))
    if jv is None:
        return "良好", "review"
    if metric_key == "contact_bat_speed_kmh":
        if jv >= BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH:
            return "优秀", "good"
        if jv >= BAT_SPEED_U8_U10_GOOD_MIN_KMH:
            return "良好", "review"
        return "待提高", "risk"
    cv = num(coach.get("value")) if coach else None
    if cv is None:
        return "良好", "review"
    diff = abs(jv - cv)
    scale = max(abs(cv), 1.0)
    ratio = diff / scale
    if metric_key in {"coach_high_com_risk_index", "coach_rollover_forearm_roll_velocity_deg_s", "ready_to_contact_head_displacement_mm"}:
        return ("优秀", "good") if jv <= cv else ("待提高", "risk")
    if metric_key == "coach_hitting_zone_stability_score":
        return ("优秀", "good") if jv >= cv else ("待提高", "risk")
    if ratio <= 0.12:
        return "优秀", "good"
    if ratio <= 0.30:
        return "良好", "review"
    return "待提高", "risk"


def score_for_status(klass: str) -> float:
    return {"good": 100.0, "review": 70.0, "risk": 40.0}.get(klass, 60.0)


def front_metric_score(
    front_metric: tuple[str, str, list[tuple[str, float]], str],
    julian_rows: dict[str, dict[str, str]],
    coach_rows: dict[str, dict[str, str]],
) -> tuple[float | None, str, str]:
    _, _, components, _ = front_metric
    weighted_total = 0.0
    weight_total = 0.0
    for key, weight in components:
        row = julian_rows.get(key)
        coach_row = coach_rows.get(key)
        value = safe_float(row.get("value") if row else None)
        standard = safe_float(coach_row.get("value") if isinstance(coach_row, dict) else None)
        if value is None or standard is None:
            continue
        weighted_total += component_score_against_standard(key, value, standard) * weight
        weight_total += weight
    if weight_total <= 0:
        return None, "良好", "review"
    score = weighted_total / weight_total
    if score >= 85:
        return score, "优秀", "good"
    if score >= 65:
        return score, "良好", "review"
    return score, "待提高", "risk"


def score_text(score: float | None) -> str:
    return "暂无" if score is None else f"{score:.0f}分"


def score_number(score: float | None) -> str:
    return "暂无" if score is None else f"{score:.0f}"


def card_status_label(label: str, klass: str) -> str:
    return {"good": "优秀", "review": "良好", "risk": "待提高"}.get(klass, label)


def display_metric_name(metric_name: str) -> str:
    return normalize_metric_name(metric_name)


def normalize_metric_name(metric_name: object) -> str:
    return str(metric_name or "").replace("（Attack Angle）", "")


LOWER_IS_BETTER_KEYS = {
    "coach_high_com_risk_index",
    "coach_rollover_forearm_roll_velocity_deg_s",
    "ready_to_contact_head_displacement_mm",
}


def component_score_against_standard(metric_key: str, value: float, standard: float) -> float:
    if metric_key == "contact_bat_speed_kmh":
        if value >= BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH:
            return 100.0
        if value >= BAT_SPEED_U8_U10_GOOD_MIN_KMH:
            ratio = (value - BAT_SPEED_U8_U10_GOOD_MIN_KMH) / (
                BAT_SPEED_U8_U10_EXCELLENT_MIN_KMH - BAT_SPEED_U8_U10_GOOD_MIN_KMH
            )
            return 70.0 + ratio * 14.0
        return max(20.0, 70.0 * max(value, 0.0) / BAT_SPEED_U8_U10_GOOD_MIN_KMH)
    scale = max(abs(standard), 1.0)
    if metric_key in LOWER_IS_BETTER_KEYS:
        diff_ratio = max(0.0, (value - standard) / scale)
    else:
        diff_ratio = abs(value - standard) / scale
    if diff_ratio <= 0.12:
        return 100.0 - diff_ratio / 0.12 * 8.0
    if diff_ratio <= 0.30:
        return 92.0 - (diff_ratio - 0.12) / 0.18 * 22.0
    if diff_ratio <= 0.60:
        return 70.0 - (diff_ratio - 0.30) / 0.30 * 30.0
    return max(20.0, 40.0 - (diff_ratio - 0.60) / 0.40 * 20.0)


def peer_scores_for(
    front_metric: tuple[str, str, list[tuple[str, float]], str],
    peer_rows: list[dict[str, object]],
    coach_rows: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    _, name, components, _ = front_metric
    scores = []
    for peer_idx, row in enumerate(peer_rows):
        metric_rows = row.get("rows")
        if not isinstance(metric_rows, dict):
            continue
        weighted_total = 0.0
        weight_total = 0.0
        component_parts = []
        for key, weight in components:
            metric_row = metric_rows.get(key)
            value = safe_float(metric_row.get("value") if isinstance(metric_row, dict) else None)
            standard = safe_float(coach_rows.get(key, {}).get("value") if isinstance(coach_rows.get(key), dict) else None)
            if value is None or standard is None:
                continue
            component_score = component_score_against_standard(key, value, standard)
            weighted_total += component_score * weight
            weight_total += weight
            component_parts.append(f"{key}: {component_score:.1f}分")
        if weight_total <= 0:
            continue
        score = weighted_total / weight_total
        scores.append(
            {
                "name": row.get("name") or "peer",
                "score": score,
                "color_index": peer_idx,
                "components": "; ".join(component_parts),
            }
        )
    return scores


def nice_step(span: float) -> float:
    if span <= 0 or not math.isfinite(span):
        return 1.0
    raw = span / 5.0
    magnitude = 10 ** math.floor(math.log10(raw))
    normalized = raw / magnitude
    if normalized <= 1:
        nice = 1
    elif normalized <= 2:
        nice = 2
    elif normalized <= 5:
        nice = 5
    else:
        nice = 10
    return nice * magnitude


def peer_axis_number_text(value: float, unit: str | None) -> str:
    if unit in {"score", "0-100 score", "0-100 risk"}:
        return f"{value:.0f}" if unit == "score" else f"{value:.1f}".rstrip("0").rstrip(".")
    if unit == "height_ratio":
        return f"{value * 100:.0f}%"
    if unit == "mm":
        return f"{value / 10:.1f}".rstrip("0").rstrip(".")
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}".rstrip("0").rstrip(".")
    return f"{value:.2f}".rstrip("0").rstrip(".")


def peer_axis_unit_text(unit: str | None) -> str:
    if unit == "score":
        return "分"
    if unit == "height_ratio":
        return "身高比"
    if unit == "mm":
        return "cm"
    if unit == "0-100 score":
        return "分"
    if unit == "0-100 risk":
        return "风险分"
    return UNIT_CN.get(unit or "", unit or "")


def peer_axis_text(value: float, unit: str | None) -> str:
    number = peer_axis_number_text(value, unit)
    unit_text = peer_axis_unit_text(unit)
    if unit == "deg":
        return f"{number}{unit_text}"
    return f"{number} {unit_text}".strip() if unit_text else number


def peer_axis_html(value: float, unit: str | None) -> str:
    number = peer_axis_number_text(value, unit)
    unit_text = peer_axis_unit_text(unit)
    if not unit_text:
        return esc(number)
    if unit == "deg":
        return esc(f"{number}{unit_text}")
    return (
        '<span class="unit-stack">'
        f'<span class="unit-number">{esc(number)}</span>'
        f'<span class="unit-label">{esc(unit_text)}</span>'
        '</span>'
    )


def peer_range_bar(
    front_metric: tuple[str, str, list[tuple[str, float]], str],
    peer_rows: list[dict[str, object]],
    coach_rows: dict[str, dict[str, str]],
    show_markers: bool = True,
    anonymize_names: bool = True,
    current_score: float | None = None,
) -> str:
    _, name, _, _ = front_metric
    peer_scores = peer_scores_for(front_metric, peer_rows, coach_rows)
    if not peer_scores:
        return """
        <div class="peer-range empty">
          <div class="peer-label">其他球员<br>表现区间</div>
          <div class="peer-empty">暂无可用区间</div>
        </div>
        """
    values = [float(item["score"]) for item in peer_scores]
    unit = "score"
    low = min(values)
    high = max(values)
    step = nice_step(high - low)
    axis_low = low
    axis_high = high
    if axis_high <= axis_low:
        axis_low -= step
        axis_high += step
    axis_span = axis_high - axis_low
    if axis_span <= 0 or not math.isfinite(axis_span):
        axis_span = 1.0
    span_left = 0.0
    span_width = 100.0
    dots = []
    lanes_by_bucket: dict[int, int] = {}
    scored_names = {str(item["name"]) for item in peer_scores}

    def dot_html(item: dict[str, object], pos: float, title: str, missing: bool = False) -> str:
        bucket = round(pos / 3.5)
        lane = lanes_by_bucket.get(bucket, 0)
        lanes_by_bucket[bucket] = lane + 1
        x_offsets = [0.0, -1.1, 1.1, -2.2, 2.2, -3.3, 3.3, 4.4]
        y_offsets = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        offset_idx = min(lane, len(x_offsets) - 1)
        pos = clamp(pos + x_offsets[offset_idx], 2.0, 98.0)
        top = 50 + y_offsets[offset_idx]
        color = peer_color(item.get("name"), int(item.get("color_index", 0)))
        is_current_player = not missing and peer_key(item.get("name")) == peer_key(ACTIVE_PLAYER_SAMPLE)
        klass = "peer-dot missing" if missing else "peer-dot current-player" if is_current_player else "peer-dot"
        current_marker = f"; --marker-color:{esc(color)}" if is_current_player else ""
        return (
            f'<span class="{klass}" style="left:{pos:.2f}%; top:{top:.1f}%; background:{esc(color)}{current_marker}" '
            f'title="{esc(title)}"></span>'
        )

    if show_markers:
        for item in peer_scores:
            score = float(item["score"])
            pos = 2.0 + clamp((score - axis_low) / axis_span * 100.0) * 0.96
            peer_label = anonymous_peer_label(int(item.get("color_index", 0))) if anonymize_names else str(item["name"])
            dots.append(
                dot_html(
                    item,
                    pos,
                    f"{peer_label}: {peer_axis_text(score, unit)}",
                )
            )

        for peer_idx, row in enumerate(peer_rows):
            name = str(row.get("name") or "peer")
            if name in scored_names:
                continue
            peer_label = anonymous_peer_label(peer_idx) if anonymize_names else name
            dots.append(
                dot_html(
                    {"name": name, "score": axis_low, "color_index": peer_idx},
                    2.0,
                    f"{peer_label}: 暂无可对照表现",
                    missing=True,
                )
            )
    elif current_score is not None and math.isfinite(current_score):
        pos = 2.0 + clamp((current_score - axis_low) / axis_span * 100.0) * 0.96
        dots.append(
            f'<span class="peer-dot current-player" style="left:{pos:.2f}%; top:50.0%" '
            f'title="该球员: {peer_axis_text(current_score, unit)}"></span>'
        )
    klass = "peer-range" if show_markers else "peer-range no-markers"
    return f"""
        <div class="{klass}">
        <div class="peer-label">其他球员<br>表现区间</div>
        <div class="peer-min">{peer_axis_html(low, unit)}</div>
        <div class="peer-track" title="其他球员在同一训练评估标准下的表现区间">
          <span class="peer-span" style="left:{span_left:.2f}%; width:{span_width:.2f}%"></span>
          {''.join(dots)}
        </div>
        <div class="peer-max">{peer_axis_html(high, unit)}</div>
      </div>
    """


def peer_metric_values_for(metric_key: str, peer_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    values = []
    for peer_idx, row in enumerate(peer_rows):
        metric_rows = row.get("rows")
        if not isinstance(metric_rows, dict):
            continue
        metric_row = metric_rows.get(metric_key)
        value = safe_float(metric_row.get("value") if isinstance(metric_row, dict) else None)
        if value is None:
            continue
        values.append(
            {
                "name": row.get("name") or "peer",
                "value": value,
                "unit": metric_row.get("unit", "") if isinstance(metric_row, dict) else "",
                "color_index": peer_idx,
            }
        )
    return values


def peer_metric_mean(metric_key: str, peer_rows: list[dict[str, object]]) -> float | None:
    values = [float(item["value"]) for item in peer_metric_values_for(metric_key, peer_rows)]
    if not values:
        return None
    return sum(values) / len(values)


def issue_compare_pills(
    metric: dict[str, str],
    coach: dict[str, str] | None,
    peer_rows: list[dict[str, object]],
) -> str:
    key = metric["metric_key"]
    unit = metric.get("unit")
    group_mean = peer_metric_mean(key, peer_rows)
    coach_value = coach.get("value") if coach else None
    player_value = metric.get("value")
    return f"""
        <div class="compare-pills">
          <span class="compare-pill"><b>乐风U9均值</b>{esc(fmt(group_mean, unit))}</span>
          <span class="compare-pill"><b>阿楽教练参考</b>{esc(fmt(coach_value, coach.get("unit") if coach else unit))}</span>
          <span class="compare-pill"><b>球员{esc(ACTIVE_PLAYER_LABEL)}</b>{esc(fmt(player_value, unit))}</span>
        </div>
    """


def peer_metric_range_bar(
    metric_key: str,
    unit: str | None,
    peer_rows: list[dict[str, object]],
    show_markers: bool = True,
    anonymize_names: bool = True,
    current_value: float | None = None,
) -> str:
    peer_values = peer_metric_values_for(metric_key, peer_rows)
    if not peer_values:
        return """
        <div class="peer-range empty">
          <div class="peer-label">其他球员<br>后端区间</div>
          <div class="peer-empty">暂无可用区间</div>
        </div>
        """
    values = [float(item["value"]) for item in peer_values]
    low = min(values)
    high = max(values)
    step = nice_step(high - low)
    axis_low = low
    axis_high = high
    if axis_high <= axis_low:
        axis_low -= step
        axis_high += step
    axis_span = axis_high - axis_low
    if axis_span <= 0 or not math.isfinite(axis_span):
        axis_span = 1.0
    dots = []
    lanes_by_bucket: dict[int, int] = {}
    valued_names = {str(item["name"]) for item in peer_values}

    def dot_html(item: dict[str, object], pos: float, title: str, missing: bool = False) -> str:
        bucket = round(pos / 3.5)
        lane = lanes_by_bucket.get(bucket, 0)
        lanes_by_bucket[bucket] = lane + 1
        x_offsets = [0.0, -1.1, 1.1, -2.2, 2.2, -3.3, 3.3, 4.4]
        offset_idx = min(lane, len(x_offsets) - 1)
        pos = clamp(pos + x_offsets[offset_idx], 2.0, 98.0)
        color = peer_color(item.get("name"), int(item.get("color_index", 0)))
        is_current_player = not missing and peer_key(item.get("name")) == peer_key(ACTIVE_PLAYER_SAMPLE)
        klass = "peer-dot missing" if missing else "peer-dot current-player" if is_current_player else "peer-dot"
        current_marker = f"; --marker-color:{esc(color)}" if is_current_player else ""
        return (
            f'<span class="{klass}" style="left:{pos:.2f}%; top:50.0%; background:{esc(color)}{current_marker}" '
            f'title="{esc(title)}"></span>'
        )

    if show_markers:
        for item in peer_values:
            value = float(item["value"])
            pos = 2.0 + clamp((value - axis_low) / axis_span * 100.0) * 0.96
            peer_label = anonymous_peer_label(int(item.get("color_index", 0))) if anonymize_names else str(item["name"])
            dots.append(dot_html(item, pos, f"{peer_label}: {peer_axis_text(value, unit)}"))

        for peer_idx, row in enumerate(peer_rows):
            name = str(row.get("name") or "peer")
            if name in valued_names:
                continue
            peer_label = anonymous_peer_label(peer_idx) if anonymize_names else name
            dots.append(
                dot_html(
                    {"name": name, "value": axis_low, "color_index": peer_idx},
                    2.0,
                    f"{peer_label}: 暂无可对照表现",
                    missing=True,
                )
            )
    elif current_value is not None and math.isfinite(current_value):
        pos = 2.0 + clamp((current_value - axis_low) / axis_span * 100.0) * 0.96
        dots.append(
            f'<span class="peer-dot current-player" style="left:{pos:.2f}%; top:50.0%" '
            f'title="该球员: {peer_axis_text(current_value, unit)}"></span>'
        )

    klass = "peer-range" if show_markers else "peer-range no-markers"
    return f"""
        <div class="{klass}">
        <div class="peer-label">其他球员<br>表现区间</div>
        <div class="peer-min">{peer_axis_html(low, unit)}</div>
        <div class="peer-track" title="其他球员在同一训练评估标准下的表现区间">
          <span class="peer-span" style="left:0.00%; width:100.00%"></span>
          {''.join(dots)}
        </div>
        <div class="peer-max">{peer_axis_html(high, unit)}</div>
      </div>
    """


def front_metric_card(
    front_metric: tuple[str, str, list[tuple[str, float]], str],
    julian_rows: dict[str, dict[str, str]],
    coach_rows: dict[str, dict[str, str]],
    peer_rows: list[dict[str, object]],
    show_peer_markers: bool,
    anonymize_peer_names: bool = True,
) -> str:
    _, name, components, event_key = front_metric
    score, label, klass = front_metric_score(front_metric, julian_rows, coach_rows)
    display_label = card_status_label(label, klass)
    event_row = julian_rows[event_key]
    body = FRONT_FEEDBACK.get(name, FRONT_EXPLANATIONS.get(name, ""))
    body_en = FRONT_FEEDBACK_EN.get(name, "")
    return f"""
    <article class="metric-card {klass}">
      <div class="metric-summary">
          <span class="badge {klass}">{esc(display_label)}</span>
        <div>
          <h4>{esc(name)}</h4>
        </div>
        <div class="metric-value">{esc(score_number(score))}</div>
      </div>
      {metric_illustration(name)}
      <div class="metric-detail">
        <p class="metric-detail-cn">{esc(body)}</p>
        <p class="metric-detail-en">{esc(body_en)}</p>
        {peer_range_bar(front_metric, peer_rows, coach_rows, show_peer_markers, anonymize_peer_names, score if not show_peer_markers else None)}
      </div>
    </article>
    """


def metric_card(
    metric: dict[str, str],
    coach: dict[str, str] | None,
    peer_rows: list[dict[str, object]],
    illustration_name: str,
    show_peer_markers: bool,
    anonymize_peer_names: bool = True,
) -> str:
    key = metric["metric_key"]
    label, klass = status_for(key, metric, coach)
    coach_value = fmt(coach.get("value"), coach.get("unit")) if coach else "暂无"
    body = (
        f"{EXPLANATIONS.get(key, metric.get('formula', ''))}"
        f"本次记录为 {fmt(metric.get('value'), metric.get('unit'))}；"
        f"教练示范为 {coach_value}，相差 {delta_text(metric, coach)}。"
    )
    body_en = (
        f"Player: {fmt(metric.get('value'), metric.get('unit'))}. Coach reference: {coach_value}. Gap: {delta_text(metric, coach)}. "
        f"{EXPLANATIONS_EN.get(key, '')}"
    )
    current_value = safe_float(metric.get("value"))
    compare = issue_compare_pills(metric, coach, peer_rows) if key in ISSUE_BACKEND_KEYS else ""
    coach_reference = ""
    if key not in ISSUE_BACKEND_KEYS:
        coach_reference = (
            f'<div class="pitch-coach-reference"><b>阿楽教练</b>'
            f'<span>{esc(coach_value)}</span></div>'
        )
    return f"""
    <article class="metric-card {klass}">
      <div class="metric-summary">
          <span class="badge {klass}">{esc(label)}</span>
        <div>
          <h4>{esc(display_metric_name(metric["metric_name_zh"]))}</h4>
          <div class="metric-en">{esc(BACKEND_EN.get(key, ""))}</div>
        </div>
        <div class="metric-value">{esc(fmt(metric.get("value"), metric.get("unit")))}</div>
        {coach_reference}
      </div>
      {metric_illustration(illustration_name)}
      <div class="metric-detail">
        <p class="metric-detail-cn">{esc(body)}</p>
        <p class="metric-detail-en">{esc(body_en)}</p>
        {compare}
        {peer_metric_range_bar(key, metric.get("unit"), peer_rows, show_peer_markers, anonymize_peer_names, current_value if not show_peer_markers else None)}
      </div>
    </article>
    """


def row_value(rows_by_key: dict[str, dict[str, str]], key: str) -> float | None:
    row = rows_by_key.get(key)
    return safe_float(row.get("value") if row else None)


def parse_frame_list(value: object) -> list[int]:
    if value in (None, ""):
        return []
    return [int(part) for part in str(value).split(";") if part.strip().isdigit()]


def json_dict(value: str | None) -> dict[str, object]:
    if not value:
        return {}
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def load_bat_series(pose_path: Path, clip_id: str) -> list[dict[str, object]]:
    if not pose_path.exists():
        return []
    frames: dict[int, dict[str, object]] = {}
    with pose_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("clip_id") != clip_id or row.get("joint_name") not in {"Bat1", "Bat5"}:
                continue
            frame = int(float(row["frame_index"]))
            item = frames.setdefault(frame, {"frame": frame, "time": safe_float(row.get("timestamp_sec")), "points": {}})
            points = item["points"]
            if not isinstance(points, dict):
                continue
            points[row["joint_name"]] = (
                float(row["x_3d"]),
                float(row["y_3d"]),
                float(row["z_3d"]),
            )
    series = []
    for frame in sorted(frames):
        item = frames[frame]
        points = item.get("points")
        if not isinstance(points, dict) or "Bat1" not in points or "Bat5" not in points:
            continue
        series.append(item)
    return series


def load_clip_marker_frames(pose_path: Path, clip_id: str) -> list[dict[str, object]]:
    if not pose_path.exists():
        return []
    frames: dict[int, dict[str, object]] = {}
    with pose_path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("clip_id") != clip_id:
                continue
            frame = int(float(row["frame_index"]))
            item = frames.setdefault(frame, {"frame": frame, "time": safe_float(row.get("timestamp_sec")), "points": {}})
            points = item["points"]
            if not isinstance(points, dict):
                continue
            points[row["joint_name"]] = (
                float(row["x_3d"]),
                float(row["y_3d"]),
                float(row["z_3d"]),
            )
    return [frames[frame] for frame in sorted(frames)]


def vector_len(vec: tuple[float, float, float]) -> float:
    return math.sqrt(vec[0] ** 2 + vec[1] ** 2 + vec[2] ** 2)


def angle_between_vectors(a: tuple[float, float, float], b: tuple[float, float, float]) -> float | None:
    denom = vector_len(a) * vector_len(b)
    if denom <= 1e-9:
        return None
    cos_v = max(-1.0, min(1.0, (a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) / denom))
    return math.degrees(math.acos(cos_v))


def wrap_angle_delta(current: float, previous: float) -> float:
    return (current - previous + 180.0) % 360.0 - 180.0


def horizontal_line_angle(points: dict[str, tuple[float, float, float]], a: str, b: str) -> float | None:
    if a not in points or b not in points:
        return None
    pa = points[a]
    pb = points[b]
    return math.degrees(math.atan2(pa[1] - pb[1], pa[0] - pb[0]))


def joint_angle(points: dict[str, tuple[float, float, float]], a: str, b: str, c: str) -> float | None:
    if a not in points or b not in points or c not in points:
        return None
    pa = points[a]
    pb = points[b]
    pc = points[c]
    return angle_between_vectors(
        (pa[0] - pb[0], pa[1] - pb[1], pa[2] - pb[2]),
        (pc[0] - pb[0], pc[1] - pb[1], pc[2] - pb[2]),
    )


def moving_average(values: list[float | None], radius: int = 2) -> list[float | None]:
    out: list[float | None] = []
    for idx in range(len(values)):
        window = [v for v in values[max(0, idx - radius): idx + radius + 1] if v is not None and math.isfinite(v)]
        out.append(sum(window) / len(window) if window else None)
    return out


def batting_time_series(rows_by_key: dict[str, dict[str, str]], clip_id: str) -> dict[str, object]:
    raw = load_bat_series(DEFAULT_POSE3D, clip_id)
    if not raw:
        return {"speed": [], "angle": [], "contact_time": None, "peak_time": None}
    speed_values: list[float | None] = [None]
    angle_values: list[float | None] = []
    for idx, item in enumerate(raw):
        points = item["points"]
        bat1 = points["Bat1"]  # type: ignore[index]
        bat5 = points["Bat5"]  # type: ignore[index]
        axis = (bat1[0] - bat5[0], bat1[1] - bat5[1], bat1[2] - bat5[2])
        angle_values.append(math.degrees(math.atan2(axis[2], math.hypot(axis[0], axis[1]))))
        if idx > 0:
            prev = raw[idx - 1]
            prev_points = prev["points"]
            prev_bat1 = prev_points["Bat1"]  # type: ignore[index]
            dt = float(item["time"]) - float(prev["time"])
            if dt > 0:
                diff = (bat1[0] - prev_bat1[0], bat1[1] - prev_bat1[1], bat1[2] - prev_bat1[2])
                speed_values.append(vector_len(diff) / dt * 3.6 / 1000.0)
            else:
                speed_values.append(None)
    speed_values = moving_average(speed_values, 2)
    angle_values = moving_average(angle_values, 2)
    speed = [(float(item["time"]), value, int(item["frame"])) for item, value in zip(raw, speed_values) if value is not None]
    angle = [(float(item["time"]), value, int(item["frame"])) for item, value in zip(raw, angle_values) if value is not None]

    contact = rows_by_key.get("contact_bat_speed_kmh", {})
    issue = rows_by_key.get("coach_high_com_risk_index", {})
    components = json_dict(issue.get("components_json"))
    swing_frames = parse_frame_list(components.get("swing_segment_frames"))
    frame_times = {int(item["frame"]): float(item["time"]) for item in raw}
    contact_time = frame_times.get(int(contact.get("event_frame", -1))) if contact.get("event_frame") else None
    peak_time = frame_times.get(int(components.get("swing_peak_frame", -1))) if components.get("swing_peak_frame") else None
    if swing_frames:
        lo_frame = min(swing_frames) - 18
        hi_frame = max(swing_frames) + 18
        speed = [item for item in speed if lo_frame <= item[2] <= hi_frame]
        angle = [item for item in angle if lo_frame <= item[2] <= hi_frame]
    if contact_time is not None:
        speed = [(time - contact_time, value, frame) for time, value, frame in speed]
        angle = [(time - contact_time, value, frame) for time, value, frame in angle]
        if peak_time is not None:
            peak_time -= contact_time
    return {"speed": speed, "angle": angle, "contact_time": 0.0 if contact_time is not None else None, "peak_time": peak_time}


def point_center(points: dict[str, tuple[float, float, float]], names: list[str]) -> tuple[float, float, float] | None:
    available = [points[name] for name in names if name in points]
    if not available:
        return None
    count = float(len(available))
    return (
        sum(point[0] for point in available) / count,
        sum(point[1] for point in available) / count,
        sum(point[2] for point in available) / count,
    )


def kinetic_speed_series(rows_by_key: dict[str, dict[str, str]], clip_id: str) -> list[dict[str, object]]:
    raw = load_clip_marker_frames(DEFAULT_POSE3D, clip_id)
    if not raw:
        return []
    issue = rows_by_key.get("coach_high_com_risk_index", {})
    contact = rows_by_key.get("contact_bat_speed_kmh", {})
    components = json_dict(issue.get("components_json"))
    swing_frames = parse_frame_list(components.get("swing_segment_frames"))
    contact_frame = int(contact.get("event_frame", -1)) if contact.get("event_frame") else None
    frame_times = {int(item["frame"]): float(item["time"]) for item in raw if item.get("time") is not None}
    contact_time = frame_times.get(contact_frame) if contact_frame is not None else None
    if swing_frames:
        lo_frame = min(swing_frames) - 18
        hi_frame = max(swing_frames) + 18
        raw = [item for item in raw if lo_frame <= int(item["frame"]) <= hi_frame]

    angle_defs = [
        ("下肢", GREEN, lambda pts: joint_angle(pts, "RASI", "RKNE", "RANK"), False),
        ("髋部", BLUE, lambda pts: horizontal_line_angle(pts, "RASI", "LASI"), True),
        ("躯干", PURPLE, lambda pts: horizontal_line_angle(pts, "RSHO", "LSHO"), True),
        ("手腕", ORANGE, lambda pts: horizontal_line_angle(pts, "RWRA", "RELB"), True),
    ]
    series: list[dict[str, object]] = []
    for label, color, angle_fn, wrap in angle_defs:
        samples: list[tuple[float, float, int, float] | None] = []
        for item in raw:
            points = item.get("points")
            if not isinstance(points, dict) or item.get("time") is None:
                samples.append(None)
                continue
            value = angle_fn(points)
            if value is None:
                samples.append(None)
            else:
                samples.append((float(item["time"]), float(item["time"]) - contact_time if contact_time is not None else float(item["time"]), int(item["frame"]), value))
        values: list[float | None] = [None]
        for idx in range(1, len(samples)):
            current = samples[idx]
            prev = samples[idx - 1]
            if current is None or prev is None:
                values.append(None)
                continue
            dt = current[0] - prev[0]
            if dt <= 0:
                values.append(None)
                continue
            delta = wrap_angle_delta(current[3], prev[3]) if wrap else current[3] - prev[3]
            values.append(abs(delta) / dt)
        values = moving_average(values, 2)
        points = [
            (sample[1], value, sample[2])
            for sample, value in zip(samples, values)
            if sample is not None and value is not None
        ]
        series.append({"label": label, "color": color, "points": points, "axis": "angular"})

    centers: list[tuple[float, float, int, tuple[float, float, float]] | None] = []
    for item in raw:
        points = item.get("points")
        if not isinstance(points, dict):
            centers.append(None)
            continue
        center = point_center(points, ["Bat1"])
        if center is None or item.get("time") is None:
            centers.append(None)
        else:
            centers.append((float(item["time"]), float(item["time"]) - contact_time if contact_time is not None else float(item["time"]), int(item["frame"]), center))
    values = [None]
    for idx in range(1, len(centers)):
        current = centers[idx]
        prev = centers[idx - 1]
        if current is None or prev is None:
            values.append(None)
            continue
        dt = current[0] - prev[0]
        if dt <= 0:
            values.append(None)
            continue
        diff = (
            current[3][0] - prev[3][0],
            current[3][1] - prev[3][1],
            current[3][2] - prev[3][2],
        )
        values.append(vector_len(diff) / dt * 3.6 / 1000.0)
    values = moving_average(values, 2)
    bat_points = [
        (center[1], value, center[2])
        for center, value in zip(centers, values)
        if center is not None and value is not None
    ]
    series.append({"label": "球棒", "color": RED, "points": bat_points, "axis": "speed"})
    return series


def draw_line_chart(
    curves: list[dict[str, object]],
    title: str,
    y_label: str,
    output: Path,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 720), "#ffffff")
    draw = ImageDraw.Draw(img)
    title_font = pil_font(32, bold=True)
    label_font = pil_font(22)
    small_font = pil_font(20)
    tick_font = pil_font(18)
    left, right, top, bottom = 148, 1508, 116, 558
    if "速度" in title or "角度" in title:
        top += 34
        bottom += 34
    draw.text((56, 42), title, font=title_font, fill=INK)

    all_points = [
        point
        for curve in curves
        for point in curve.get("points", [])
        if isinstance(point, tuple) and len(point) == 3
    ]
    if len(all_points) < 2:
        draw.text((left, 320), "暂无足够数据生成曲线", font=label_font, fill=MID)
        img.save(output)
        return
    times = [float(p[0]) for p in all_points]
    values = [float(p[1]) for p in all_points]
    t0, t1 = min(times), max(times)
    lo, hi = min(values), max(values)
    pad = max((hi - lo) * 0.16, 1.0)
    lo -= pad
    hi += pad
    if t0 == t1:
        t1 += 1.0
    if lo == hi:
        hi += 1.0

    def x_for(t: float) -> float:
        return left + (t - t0) / (t1 - t0) * (right - left)

    def y_for(v: float) -> float:
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    def draw_horizontal_axis_marker(px: float, py: float, value: float) -> None:
        x1, x2 = left, px
        if x2 < x1:
            x1, x2 = x2, x1
        cursor = x1
        while cursor < x2:
            draw.line((cursor, py, min(cursor + 10, x2), py), fill="#98a2b3", width=2)
            cursor += 18
        draw.text((left - 20, py), f"{value:.1f}", font=tick_font, fill="#667085", anchor="rm")

    for i in range(5):
        y = top + i * (bottom - top) / 4
        draw.line((left, y, right, y), fill="#e4e7ec", width=2 if i in {0, 4} else 1)
    draw.line((left, bottom, right, bottom), fill="#667085", width=2)
    draw.line((left, top, left, bottom), fill="#667085", width=2)
    draw.text((left, bottom + 34), "相对击球窗口（秒）", font=small_font, fill=MID)
    draw.text((56, top - 36), y_label, font=small_font, fill=MID)
    draw.text((left - 18, bottom - 9), fmt(lo, ""), font=tick_font, fill="#98a2b3", anchor="ra")
    draw.text((left - 18, top - 2), fmt(hi, ""), font=tick_font, fill="#98a2b3", anchor="ra")

    if t0 <= 0.0 <= t1:
        x0 = x_for(0.0)
        for y in range(int(top), int(bottom), 14):
            draw.line((x0, y, x0, min(y + 7, bottom)), fill="#101828", width=2)
        draw.text((x0, bottom + 35), "击球窗口", font=tick_font, fill=INK, anchor="ma")

    value_unit = "km/h" if "km/h" in y_label else "°"
    peak_rows: list[tuple[str, str, float, float, float, float]] = []
    for curve in curves:
        points = curve.get("points", [])
        color = str(curve.get("color", BLUE))
        label = str(curve.get("label", ""))
        if not isinstance(points, list) or len(points) < 2:
            continue
        xy = [(x_for(float(t)), y_for(float(v))) for t, v, _ in points]
        draw.line(xy, fill=color, width=7, joint="curve")
        peak = max(points, key=lambda item: item[1])
        px, py = x_for(float(peak[0])), y_for(float(peak[1]))
        draw.ellipse((px - 8, py - 8, px + 8, py + 8), fill=color, outline="#ffffff", width=3)
        peak_rows.append((label, color, float(peak[1]), float(peak[0]), px, py))

    label_offsets = [(-250, -76), (34, -72)]
    placed_boxes: list[tuple[float, float, float, float]] = []
    pill_font = pil_font(16, bold=True)
    for idx, (label, color, value, time_sec, px, py) in enumerate(peak_rows):
        draw_horizontal_axis_marker(px, py, value)
        line1 = f"{label}峰值"
        box_w = max(116, int(draw.textlength(line1, font=pill_font) + 38))
        box_h = 34
        off_x, off_y = label_offsets[idx % len(label_offsets)]
        box_x = min(max(px + off_x, left + 6), right - box_w - 6)
        box_y = min(max(py + off_y, top + 6), bottom - box_h - 6)
        for other in placed_boxes:
            if not (box_x + box_w < other[0] or box_x > other[2] or box_y + box_h < other[1] or box_y > other[3]):
                box_y = min(bottom - box_h - 6, other[3] + 8)
        placed_boxes.append((box_x, box_y, box_x + box_w, box_y + box_h))
        anchor_x = box_x + box_w / 2
        anchor_y = box_y + box_h if box_y < py else box_y
        draw.line((anchor_x, anchor_y, px, py), fill="#98a2b3", width=2)
        draw.rounded_rectangle((box_x, box_y, box_x + box_w, box_y + box_h), radius=17, fill="#f8fafc", outline="#cbd5e1", width=2)
        draw.ellipse((box_x + 14, box_y + 11, box_x + 26, box_y + 23), fill=color)
        draw.text((box_x + 34, box_y + 7), line1, font=pill_font, fill=INK)

    legend_items = [(str(curve.get("label", "")), str(curve.get("color", BLUE))) for curve in curves if curve.get("points")]
    legend_w, legend_h = 274, 34 + 28 * len(legend_items)
    legend_x, legend_y = right - legend_w - 12, 38 + (34 if ("速度" in title or "角度" in title) else 0)
    draw.rounded_rectangle((legend_x, legend_y, legend_x + legend_w, legend_y + legend_h), radius=14, fill="#ffffff", outline="#d0d5dd", width=2)
    draw.text((legend_x + 16, legend_y + 10), "图例", font=tick_font, fill=INK)
    for idx, (label, color) in enumerate(legend_items):
        y = legend_y + 38 + idx * 28
        draw.ellipse((legend_x + 18, y + 5, legend_x + 34, y + 21), fill=color)
        draw.text((legend_x + 44, y), label, font=small_font, fill="#344054")
    img.save(output)


def draw_kinetic_speed_chart(curves: list[dict[str, object]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 760), "#ffffff")
    draw = ImageDraw.Draw(img)
    title_font = pil_font(32, bold=True)
    label_font = pil_font(22)
    small_font = pil_font(20)
    tick_font = pil_font(18)
    pill_font = pil_font(17, bold=True)
    left, right, top, bottom = 148, 1452, 194, 632
    draw.text((56, 42), "动力链速度时间曲线", font=title_font, fill=INK)

    angular_points = [
        point
        for curve in curves
        if curve.get("axis") == "angular"
        for point in curve.get("points", [])
        if isinstance(point, tuple) and len(point) == 3
    ]
    speed_points = [
        point
        for curve in curves
        if curve.get("axis") == "speed"
        for point in curve.get("points", [])
        if isinstance(point, tuple) and len(point) == 3
    ]
    all_points = angular_points + speed_points
    if len(all_points) < 2 or not angular_points or not speed_points:
        draw.text((left, 330), "暂无足够数据生成曲线", font=label_font, fill=MID)
        img.save(output)
        return
    times = [float(point[0]) for point in all_points]
    t0, t1 = min(times), max(times)
    speed_hi = max(float(point[1]) for point in speed_points)
    angular_hi = max(float(point[1]) for point in angular_points)
    speed_lo, angular_lo = 0.0, 0.0
    speed_hi += max(speed_hi * 0.16, 1.0)
    angular_hi += max(angular_hi * 0.16, 10.0)
    if t0 == t1:
        t1 += 1.0
    if speed_hi <= 0:
        speed_hi = 1.0
    if angular_hi <= 0:
        angular_hi = 1.0

    def x_for(t: float) -> float:
        return left + (t - t0) / (t1 - t0) * (right - left)

    def y_for_speed(v: float) -> float:
        return bottom - (v - speed_lo) / (speed_hi - speed_lo) * (bottom - top)

    def y_for_angular(v: float) -> float:
        return bottom - (v - angular_lo) / (angular_hi - angular_lo) * (bottom - top)

    def draw_horizontal_axis_marker(px: float, py: float, value: float, axis: str, unit: str) -> None:
        axis_x = left if axis == "speed" else right
        x1, x2 = sorted((px, axis_x))
        cursor = x1
        while cursor < x2:
            draw.line((cursor, py, min(cursor + 10, x2), py), fill="#98a2b3", width=2)
            cursor += 18
        peak_label = f"{value:.1f}"
        if axis == "speed":
            draw.text((left - 20, py), peak_label, font=tick_font, fill="#667085", anchor="rm")
        else:
            draw.text((right + 20, py), peak_label, font=tick_font, fill="#667085", anchor="lm")

    for i in range(5):
        y = top + i * (bottom - top) / 4
        draw.line((left, y, right, y), fill="#e4e7ec", width=2 if i in {0, 4} else 1)
    draw.line((left, bottom, right, bottom), fill="#667085", width=2)
    draw.line((left, top, left, bottom), fill="#667085", width=2)
    draw.line((right, top, right, bottom), fill="#667085", width=2)
    draw.text((left, bottom + 34), "相对击球窗口（秒）", font=small_font, fill=MID)
    draw.text((56, top - 36), "球棒速度（km/h）", font=small_font, fill=MID)
    draw.text((right - 10, top - 36), "角速度（°/s）", font=small_font, fill=MID, anchor="ra")
    draw.text((left - 18, bottom - 9), fmt(speed_lo, ""), font=tick_font, fill="#98a2b3", anchor="ra")
    draw.text((left - 18, top - 2), fmt(speed_hi, ""), font=tick_font, fill="#98a2b3", anchor="ra")
    draw.text((right + 18, bottom - 9), fmt(angular_lo, ""), font=tick_font, fill="#98a2b3")
    draw.text((right + 18, top - 2), fmt(angular_hi, ""), font=tick_font, fill="#98a2b3")

    if t0 <= 0.0 <= t1:
        x0 = x_for(0.0)
        for y in range(int(top), int(bottom), 14):
            draw.line((x0, y, x0, min(y + 7, bottom)), fill="#101828", width=2)
        draw.text((x0, bottom + 35), "击球窗口", font=tick_font, fill=INK, anchor="ma")

    peak_rows: list[tuple[str, str, float, float, float, float, str]] = []
    for idx, curve in enumerate(curves):
        points = curve.get("points", [])
        color = str(curve.get("color", BLUE))
        label = str(curve.get("label", ""))
        axis = str(curve.get("axis", "angular"))
        if not isinstance(points, list) or len(points) < 2:
            continue
        y_for = y_for_speed if axis == "speed" else y_for_angular
        xy = [(x_for(float(t)), y_for(float(v))) for t, v, _ in points]
        draw.line(xy, fill=color, width=7, joint="curve")
        peak = max(points, key=lambda item: item[1])
        px, py = x_for(float(peak[0])), y_for(float(peak[1]))
        draw.ellipse((px - 11, py - 11, px + 11, py + 11), fill=color, outline="#ffffff", width=4)
        draw.ellipse((px - 5, py - 5, px + 5, py + 5), fill="#ffffff")
        unit = "km/h" if axis == "speed" else "°/s"
        peak_rows.append((label, color, float(peak[1]), float(peak[0]), px, py, unit))

    label_offsets = [(-96, -58), (-150, -72), (32, -76), (40, -62), (36, -52)]
    label_offset_overrides = {
        "躯干": (-90, -102),
        "球棒": (270, -100),
    }
    placed_boxes: list[tuple[float, float, float, float]] = []
    for idx, (label, color, value, time_sec, px, py, unit) in enumerate(peak_rows):
        axis = "speed" if unit == "km/h" else "angular"
        draw_horizontal_axis_marker(px, py, value, axis, unit)
        pill_text = f"{label}峰值"
        pill_w = max(104, int(draw.textlength(pill_text, font=pill_font) + 36))
        pill_h = 34
        off_x, off_y = label_offset_overrides.get(label, label_offsets[idx % len(label_offsets)])
        pill_x = min(max(px + off_x, left + 6), right - pill_w - 6)
        pill_y = min(max(py + off_y, top + 6), bottom - pill_h - 6)
        for box in placed_boxes:
            if not (pill_x + pill_w < box[0] or pill_x > box[2] or pill_y + pill_h < box[1] or pill_y > box[3]):
                pill_y = min(bottom - pill_h - 6, box[3] + 8)
        placed_boxes.append((pill_x, pill_y, pill_x + pill_w, pill_y + pill_h))
        anchor_x = pill_x + pill_w / 2
        anchor_y = pill_y + pill_h if pill_y < py else pill_y
        draw.line((anchor_x, anchor_y, px, py), fill="#98a2b3", width=2)
        draw.rounded_rectangle((pill_x, pill_y, pill_x + pill_w, pill_y + pill_h), radius=17, fill="#f8fafc", outline="#cbd5e1", width=2)
        draw.ellipse((pill_x + 14, pill_y + 11, pill_x + 26, pill_y + 23), fill=color)
        draw.text((pill_x + 34, pill_y + 7), pill_text, font=pill_font, fill=INK)

    legend_x = left
    legend_y = 690
    for label, color, _, _, _, _, _ in peak_rows:
        draw.ellipse((legend_x, legend_y + 6, legend_x + 22, legend_y + 28), fill=color)
        draw.text((legend_x + 34, legend_y + 2), label, font=small_font, fill="#344054")
        legend_x += 250

    img.save(output)


def draw_batting_kinetic_chain(rows_by_key: dict[str, dict[str, str]], series: dict[str, object], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (1600, 360), "#ffffff")
    draw = ImageDraw.Draw(img)
    node_font = pil_font(30, bold=True)
    small_font = pil_font(24)
    nodes = [
        ("下肢", "后腿准备", row_value(rows_by_key, "ready_rear_knee_flexion_deg"), "deg", GREEN),
        ("髋部", "击球打开", row_value(rows_by_key, "contact_pelvis_rotation_open_deg"), "deg", BLUE),
        ("躯干", "身体旋转", row_value(rows_by_key, "contact_torso_rotation_open_deg"), "deg", PURPLE),
        ("手腕", "翻腕速度", row_value(rows_by_key, "coach_rollover_forearm_roll_velocity_deg_s"), "deg/s", ORANGE),
        ("棒头", "球棒速度", row_value(rows_by_key, "contact_bat_speed_kmh"), "km/h", RED),
    ]
    xs = [150, 460, 770, 1080, 1390]
    y = 180
    for i, (label, sub, value, unit, color) in enumerate(nodes):
        x = xs[i]
        draw.ellipse((x - 95, y - 95, x + 95, y + 95), fill="#f8fafc", outline=color, width=7)
        draw.text((x, y - 42), label, font=node_font, fill=INK, anchor="ma")
        draw.text((x, y + 2), sub, font=small_font, fill=MID, anchor="ma")
        draw.text((x, y + 42), fmt(value, unit), font=small_font, fill=color, anchor="ma")
        if i < len(xs) - 1:
            draw.line((x + 108, y, xs[i + 1] - 108, y), fill="#98a2b3", width=7)
            draw.polygon([(xs[i + 1] - 118, y - 16), (xs[i + 1] - 92, y), (xs[i + 1] - 118, y + 16)], fill="#98a2b3")

    img.save(output)


def sample_trial_id(rows_by_key: dict[str, dict[str, str]]) -> str:
    for row in rows_by_key.values():
        trial = row.get("trial_id")
        if trial:
            return trial
    raise ValueError("No trial_id found for sample metrics.")


def make_research_assets(rows_by_key: dict[str, dict[str, str]], coach_rows: dict[str, dict[str, str]], out_dir: Path) -> dict[str, str]:
    player_trial_id = sample_trial_id(rows_by_key)
    coach_trial_id = sample_trial_id(coach_rows)
    series = batting_time_series(rows_by_key, player_trial_id)
    coach_series = batting_time_series(coach_rows, coach_trial_id)
    kinetic_speed_series_data = kinetic_speed_series(rows_by_key, player_trial_id)
    kinetic = f"assets/kinetic_chain/{ACTIVE_PLAYER_SLUG}_batting_kinetic_chain_flow.png"
    kinetic_speed = f"assets/kinetic_chain/{ACTIVE_PLAYER_SLUG}_batting_kinetic_speed_time_curve.png"
    speed = f"assets/analyst_charts/{ACTIVE_PLAYER_SLUG}_batting_bat1_speed_time_curve.png"
    angle = f"assets/analyst_charts/{ACTIVE_PLAYER_SLUG}_batting_bat_axis_angle_time_curve.png"
    draw_batting_kinetic_chain(rows_by_key, series, out_dir / kinetic)
    draw_kinetic_speed_chart(kinetic_speed_series_data, out_dir / kinetic_speed)
    draw_line_chart(
        [
            {"label": ACTIVE_PLAYER_LABEL, "color": ORANGE, "points": series.get("speed", [])},
            {"label": "阿楽教练", "color": BLUE, "points": coach_series.get("speed", [])},
        ],
        "挥棒速度时间曲线",
        "速度（km/h）",
        out_dir / speed,
    )
    draw_line_chart(
        [
            {"label": ACTIVE_PLAYER_LABEL, "color": ORANGE, "points": series.get("angle", [])},
            {"label": "阿楽教练", "color": BLUE, "points": coach_series.get("angle", [])},
        ],
        "挥棒角度时间曲线",
        "角度（度）",
        out_dir / angle,
    )
    return {"kinetic": kinetic, "kinetic_speed": kinetic_speed, "speed": speed, "angle": angle}


def split_css_selectors(selector_text: str) -> list[str]:
    selectors: list[str] = []
    current: list[str] = []
    depth = 0
    for char in selector_text:
        if char == "(":
            depth += 1
        elif char == ")" and depth:
            depth -= 1
        if char == "," and depth == 0:
            selectors.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if current:
        selectors.append("".join(current).strip())
    return [selector for selector in selectors if selector]


def scope_css_selector(selector: str, scope: str) -> str:
    if selector == ":root":
        return scope
    if selector == "*":
        return f"{scope} *"
    if selector.startswith(f"{scope} ") or selector == scope:
        return selector
    return f"{scope} {selector}"


def find_matching_brace(css_text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(css_text)):
        char = css_text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def scope_css(css_text: str, scope: str = ".pitch-report") -> str:
    scoped_rules: list[str] = []
    index = 0
    while index < len(css_text):
        open_index = css_text.find("{", index)
        if open_index == -1:
            break
        prelude = css_text[index:open_index].strip()
        close_index = find_matching_brace(css_text, open_index)
        if close_index == -1:
            break
        block = css_text[open_index + 1 : close_index].strip()
        if not prelude:
            index = close_index + 1
            continue
        if prelude.startswith("@media"):
            inner = scope_css(block, scope)
            scoped_rules.append(f"{prelude} {{ {inner} }}")
        elif prelude.startswith("@"):
            scoped_rules.append(f"{prelude} {{{block}}}")
        else:
            selectors = ", ".join(scope_css_selector(selector, scope) for selector in split_css_selectors(prelude))
            scoped_rules.append(f"{selectors} {{{block}}}")
        index = close_index + 1
    return "\n    ".join(scoped_rules)


def extract_html_block(html_text: str, tag: str) -> str:
    match = re.search(rf"<{tag}\b[^>]*>(.*?)</{tag}>", html_text, re.DOTALL | re.IGNORECASE)
    return match.group(1) if match else ""


def extract_sections(html_text: str) -> list[str]:
    main_html = extract_html_block(html_text, "main")
    return re.findall(r"<section\b.*?</section>", main_html, re.DOTALL | re.IGNORECASE)


def section_title_text(section_html: str) -> str:
    match = re.search(r"<h[1-6]\b[^>]*>(.*?)</h[1-6]>", section_html, re.DOTALL | re.IGNORECASE)
    if not match:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", match.group(1))).strip()


def rewrite_pitch_asset_paths(section_html: str) -> str:
    return re.sub(r'((?:src|href)=["\'])assets/', rf"\1{PITCH_ASSET_PREFIX}/", section_html)


def set_section_heading(section_html: str, level: int, title: str) -> str:
    return re.sub(
        r"(<div class=\"section-title\"><span class=\"mark\"></span>)<h[1-6]\b[^>]*>.*?</h[1-6]>(</div>)",
        rf"\1<h{level}>{html.escape(title)}</h{level}>\2",
        section_html,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )


def copy_pitch_assets(pitch_report: Path, out_dir: Path) -> None:
    src_assets = pitch_report.parent / "assets"
    if not src_assets.exists():
        return
    dst_assets = out_dir / PITCH_ASSET_PREFIX
    shutil.copytree(
        src_assets,
        dst_assets,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("._*", ".DS_Store"),
    )


def load_pitch_report_parts(pitch_report: Path, out_dir: Path) -> tuple[str, dict[str, list[str]]]:
    if not pitch_report.exists():
        return "", {"player": [], "coach": [], "researcher": []}

    copy_pitch_assets(pitch_report, out_dir)
    pitch_html = pitch_report.read_text(encoding="utf-8")
    pitch_style = extract_html_block(pitch_html, "style")
    pitch_css = scope_css(pitch_style)
    groups: dict[str, list[str]] = {"player": [], "coach": [], "researcher": []}
    for section in extract_sections(pitch_html):
        title = section_title_text(section)
        if not title or "球员投球表现报告" in title:
            continue
        clean_title = title.replace("教练视角：", "").replace("研究者视角：", "")
        section = rewrite_pitch_asset_paths(section)
        section = set_section_heading(section, 4, clean_title)
        if title.startswith("教练视角"):
            groups["coach"].append(section)
        elif title.startswith("研究者视角"):
            groups["researcher"].append(section)
        else:
            groups["player"].append(section)
    return pitch_css, groups


def wrap_pitch_sections(sections: list[str]) -> str:
    if not sections:
        return ""
    return '<div class="pitch-report">\n' + "\n".join(sections) + "\n</div>"


PITCH_COACH_ALIGNMENT_CSS = """
    .pitch-report .coach-issues-layout { display:grid; grid-template-columns:minmax(0,1fr) 150px; gap:14px; align-items:start; }
    .pitch-report .coach-issue-list { display:grid; grid-template-columns:1fr; gap:18px; min-width:0; }
    .pitch-report .coach-issue-card { display:grid; grid-template-columns:minmax(180px,220px) minmax(118px,150px) minmax(0,1fr); gap:18px; align-items:center; max-width:100%; min-height:220px; padding:22px 26px; border:2px solid #d2d2d2; border-radius:26px; background:#fffefa; min-width:0; overflow:hidden; }
    .pitch-report .coach-issue-summary { min-width:0; display:grid; align-content:center; gap:14px; }
    .pitch-report .coach-issue-detail { min-width:0; display:grid; gap:10px; }
    .pitch-report .coach-issue-visual { margin:0; width:100%; aspect-ratio:1; border-radius:16px; overflow:hidden; background:transparent; }
    .pitch-report .coach-issue-visual img { width:100%; height:100%; object-fit:contain; display:block; }
    .pitch-report .coach-issue-card h4 { font-size:18px; line-height:23px; font-weight:800; margin:0; overflow-wrap:anywhere; }
    .pitch-report .coach-issue-card .metric-en { color:#667085; font-size:13px; line-height:17px; font-weight:700; margin-top:0; overflow-wrap:anywhere; }
    .pitch-report .coach-issue-card .metric-value { font-size:32px; line-height:1.05; white-space:nowrap; overflow-wrap:normal; word-break:keep-all; }
    .pitch-report .coach-issue-card .metric-detail-cn { font-size:13px; line-height:20px; font-weight:700; }
    .pitch-report .coach-issue-card .metric-detail-en { font-size:11px; line-height:17px; font-weight:600; }
    .pitch-report .coach-issue-card .compare-pills { display:flex; flex-wrap:wrap; gap:8px; min-width:0; }
    .pitch-report .coach-issue-card .compare-pill { display:inline-grid; gap:2px; border:1px solid #d0d5dd; border-radius:12px; padding:8px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; min-width:0; }
    .pitch-report .coach-issue-card .compare-pill b { color:#667085; font-size:11px; line-height:14px; }
    .pitch-report .coach-issue-card .peer-range-with-legend { display:block; min-width:0; }
    .pitch-report .coach-issue-card .peer-range { display:grid; grid-template-columns:max-content 58px minmax(90px,1fr) 58px; gap:7px; align-items:center; min-width:0; }
    .pitch-report .coach-issue-card .peer-label { color:#000; font-size:12px; line-height:15px; font-weight:800; }
    .pitch-report .coach-issue-card .peer-min,
    .pitch-report .coach-issue-card .peer-max { color:#344054; font-size:13px; line-height:16px; font-weight:800; text-align:center; white-space:nowrap; }
    .pitch-report .coach-issue-card .peer-track { position:relative; height:28px; border-radius:999px; background:linear-gradient(180deg,transparent 0 11px,#eef2f7 11px 17px,transparent 17px); min-width:0; }
    .pitch-report .coach-issue-card .peer-span { position:absolute; top:11px; height:6px; border-radius:999px; background:linear-gradient(90deg,#dcfce7,#bae6fd); }
    .pitch-report .coach-issue-card .peer-dot { position:absolute; top:50%; width:10px; height:10px; border:2px solid #fff; border-radius:999px; transform:translate(-50%,-50%); box-shadow:0 0 0 1px rgba(16,24,40,.12); }
    .pitch-report .coach-issue-card .peer-dot.julian { width:12px; height:12px; background:#101828; box-shadow:0 0 0 2px rgba(37,99,235,.28),0 0 0 1px rgba(16,24,40,.18); }
    .pitch-report .coach-legend { position:sticky; top:18px; align-self:start; margin-top:0; padding:12px 10px; border:1px solid #d0d5dd; border-radius:14px; background:#fff; display:grid; gap:7px; }
    .pitch-report .coach-legend .peer-legend-title { color:#101828; font-size:14px; line-height:18px; font-weight:800; margin:0 0 1px; }
    .pitch-report .coach-legend .peer-legend-item { display:flex; align-items:center; gap:7px; color:#344054; font-size:12px; line-height:16px; font-weight:700; white-space:normal; min-width:0; }
    .pitch-report .coach-legend .peer-legend-dot { width:10px; height:10px; border-radius:999px; box-shadow:0 0 0 1px rgba(16,24,40,.12); flex:0 0 auto; }
    @media (max-width:960px) { .pitch-report .coach-issues-layout { grid-template-columns:1fr; } .pitch-report .coach-issue-card { grid-template-columns:170px minmax(160px,210px); } .pitch-report .coach-issue-detail { grid-column:1 / -1; } .pitch-report .coach-legend { position:static; grid-template-columns:repeat(4,minmax(0,1fr)); } .pitch-report .coach-legend .peer-legend-title { grid-column:1 / -1; } }
    @media (max-width:640px) { .pitch-report .coach-issue-card { grid-template-columns:1fr; min-height:0; gap:18px; padding:22px 18px; } .pitch-report .coach-issue-visual { max-width:260px; justify-self:center; } .pitch-report .coach-issue-card .peer-range { grid-template-columns:1fr 56px minmax(100px,1fr) 56px; gap:8px; } .pitch-report .coach-legend { grid-template-columns:repeat(2,minmax(0,1fr)); } }
"""


SECTION_TITLE_LEVEL_CSS = """
    .section-title { position:relative; }
    .section-title:has(h1) { display:block; margin:0 0 34px; padding:0; }
    .section-title:has(h1) .mark { display:none; }
    .section-title:has(h1) h1 { font-size:42px; line-height:52px; font-weight:800; margin:0; letter-spacing:0; }
    .section-title:has(h2) { display:flex; align-items:center; gap:12px; width:100%; min-height:38px; margin:0 0 28px; padding:0 18px 0 0; background:#dbeafe; }
    .section-title:has(h2) .mark { display:block; width:12px; height:38px; background:#60a5fa; border-radius:999px; flex:0 0 auto; }
    .section-title:has(h2) h2 { font-size:22px; line-height:30px; font-weight:800; margin:0; color:#000; }
    .section-title:has(h3) { display:flex; align-items:center; gap:12px; margin:0 0 28px; padding:0; }
    .section-title:has(h3) .mark { width:0; height:0; border-left:9px solid transparent; border-right:9px solid transparent; border-top:18px solid #ef4444; border-radius:0; background:transparent; flex:0 0 auto; transform:translateY(-1px); }
    .section-title:has(h3) h3 { font-size:24px; line-height:34px; font-weight:800; margin:0; color:#101828; }
    .section-title:has(h4) { display:flex; align-items:center; gap:14px; margin:0 0 18px; padding:0; }
    .section-title:has(h4) .mark { width:12px; height:40px; background:#2563eb; border-radius:999px; flex:0 0 auto; }
    .section-title:has(h4) h4 { font-size:22px; line-height:32px; font-weight:800; margin:0; color:#101828; }
    .pitch-report .section-title:has(h1) { display:block; margin:0 0 34px; padding:0; }
    .pitch-report .section-title:has(h1) .mark { display:none; }
    .pitch-report .section-title:has(h1) h1 { font-size:42px; line-height:52px; font-weight:800; margin:0; letter-spacing:0; }
    .pitch-report .section-title:has(h2) { display:flex; align-items:center; gap:12px; width:100%; min-height:38px; margin:0 0 28px; padding:0 18px 0 0; background:#dbeafe; }
    .pitch-report .section-title:has(h2) .mark { display:block; width:12px; height:38px; background:#60a5fa; border-radius:999px; flex:0 0 auto; }
    .pitch-report .section-title:has(h2) h2 { font-size:22px; line-height:30px; font-weight:800; margin:0; color:#000; }
    .pitch-report .section-title:has(h3) { display:flex; align-items:center; gap:12px; margin:0 0 28px; padding:0; }
    .pitch-report .section-title:has(h3) .mark { width:0; height:0; border-left:9px solid transparent; border-right:9px solid transparent; border-top:18px solid #ef4444; border-radius:0; background:transparent; flex:0 0 auto; transform:translateY(-1px); }
    .pitch-report .section-title:has(h3) h3 { font-size:24px; line-height:34px; font-weight:800; margin:0; color:#101828; }
    .pitch-report .section-title:has(h4) { display:flex; align-items:center; gap:14px; margin:0 0 18px; padding:0; }
    .pitch-report .section-title:has(h4) .mark { width:12px; height:40px; background:#2563eb; border-radius:999px; flex:0 0 auto; }
    .pitch-report .section-title:has(h4) h4 { font-size:22px; line-height:32px; font-weight:800; margin:0; color:#101828; }
    @media (max-width:640px) {
      .section-title:has(h1) h1,
      .pitch-report .section-title:has(h1) h1 { font-size:32px; line-height:40px; }
      .section-title:has(h2),
      .pitch-report .section-title:has(h2) { min-height:36px; margin-bottom:24px; }
      .section-title:has(h2) h2,
      .pitch-report .section-title:has(h2) h2 { font-size:19px; line-height:27px; }
      .section-title:has(h3) h3,
      .pitch-report .section-title:has(h3) h3 { font-size:22px; line-height:30px; }
      .section-title:has(h4) h4,
      .pitch-report .section-title:has(h4) h4 { font-size:20px; line-height:28px; }
    }
"""


def reconstruction_media(src: str, alt: str) -> str:
    return f'<img src="{esc(src)}" alt="{esc(alt)}" loading="lazy">'


def versioned_asset(src: str) -> str:
    path = ACTIVE_OUT_DIR / src
    if not path.exists():
        return src
    return f"{src}?v={int(path.stat().st_mtime)}"


def metric_illustration(name: str) -> str:
    file_name = METRIC_ILLUSTRATIONS.get(name)
    if not file_name:
        return ""
    src = versioned_asset(f"assets/frontend_metric_illustrations_annotated_standalone/{file_name}")
    return f"""
      <figure class="metric-illustration">
        <img src="{esc(src)}" alt="{esc(name)}动作示意图" loading="lazy">
      </figure>
    """


def speed_annotation_panel(rows: dict[str, dict[str, str]], sample: str) -> str:
    media_path = versioned_asset(f"assets/vicon_reconstruction_annotated/{sample}_speed_annotated.gif")
    display_name = "球员" if sample == ACTIVE_PLAYER_SAMPLE else "教练示范"
    return f"""
    <figure class="reconstruction-annotated">
      {reconstruction_media(media_path, f"{display_name}打击动作观察")}
      <figcaption>
        <b>{esc(display_name)} 打击动作速度与挥棒方向</b>
        <span class="caption-cn">这段画面重点看速度释放、球棒进入击球区的方式，以及手腕是否能把球棒面稳定住。</span>
        <span class="caption-en">This clip focuses on speed release, how the bat enters the hitting zone, and whether the hands keep the barrel face stable.</span>
      </figcaption>
    </figure>
    """


def kinetic_chain_panel(src: str, title: str, note: str, note_en: str) -> str:
    media_path = versioned_asset(src)
    return f"""
    <article class="visual-card kinetic-chain-card">
      <h4>{esc(title)}</h4>
      <figure class="kinetic-chain-figure">
        <img src="{esc(media_path)}" alt="{esc(title)}" loading="lazy">
      </figure>
      <p class="copy-cn">{esc(note)}</p>
      <p class="copy-en">{esc(note_en)}</p>
    </article>
    """


def event_gif_panel(
    title: str,
    julian_rows: dict[str, dict[str, str]],
    metric_key: str,
    event_slug: str,
    peer_rows: list[dict[str, object]] | None = None,
) -> str:
    julian_metric = julian_rows[metric_key]
    gif_src = versioned_asset(f"assets/vicon_reconstruction_events/{ACTIVE_PLAYER_SAMPLE}_{event_slug}.gif")
    legend = peer_legend(peer_rows or [], embedded=True)
    notes = {
        "ready": (
            "这个模型展示的是孩子准备开始挥棒前的代表画面，方便家长观察站姿是否稳定、身体是否已经准备好发力。",
            "This model shows a representative moment before the swing begins, helping families see whether the player is balanced and ready to move.",
        ),
        "contact": (
            "这个模型展示的是孩子接近击球时的代表画面，方便家长理解身体位置、球棒方向和击球稳定性之间的关系。",
            "This model shows a representative moment near contact, helping families understand how body position, bat direction, and contact stability connect.",
        ),
    }
    note_cn, note_en = notes.get(event_slug, ("", ""))
    note_html = ""
    if note_cn or note_en:
        note_html = f"""
      <p class="copy-cn">{esc(note_cn)}</p>
      <p class="copy-en">{esc(note_en)}</p>"""
    return f"""
    <article class="visual-card event-gifs">
      <h4>{esc(title)}</h4>
      <figure class="event-gif-figure">
        <img src="{esc(gif_src)}" alt="球员{esc(title)}" loading="lazy">
        <figcaption><b>球员</b><span>代表动作片段</span></figcaption>
      </figure>
      {legend}
      {note_html}
    </article>
    """


def peer_legend(peer_rows: list[dict[str, object]], embedded: bool = False, anonymize_names: bool = True) -> str:
    if not peer_rows:
        return ""
    legend_rank = {name: index for index, name in enumerate(PEER_LEGEND_ORDER)}
    ordered_rows = sorted(
        peer_rows,
        key=lambda row: legend_rank.get(peer_key(row.get("name")), len(legend_rank)),
    )
    items = []
    for idx, row in enumerate(ordered_rows):
        name = row.get("name", "peer")
        color = peer_color(name, idx)
        label = anonymous_peer_label(idx) if anonymize_names else peer_display_name(name)
        items.append(
            f'<li><span class="legend-dot" style="background:{esc(color)}"></span>{esc(label)}</li>'
        )
    tag = "div" if embedded else "aside"
    klass = "peer-legend embedded" if embedded else "peer-legend"
    return f"""
    <{tag} class="{klass}" aria-label="其他球员颜色图例">
      <h4>颜色图例</h4>
      <ul>{''.join(items)}</ul>
    </{tag}>
    """


def render(
    rows: list[dict[str, str]],
    peer_rows: list[dict[str, object]],
    out_dir: Path,
    pitch_report: Path = DEFAULT_PITCH_REPORT,
    player_sample_name: str = "julian",
    coach_sample_name: str = "coach",
    player_slug: str | None = None,
    player_label: str | None = None,
) -> str:
    global ACTIVE_OUT_DIR, ACTIVE_PLAYER_SAMPLE, ACTIVE_COACH_SAMPLE, ACTIVE_PLAYER_SLUG, ACTIVE_PLAYER_LABEL
    ACTIVE_OUT_DIR = out_dir
    ACTIVE_PLAYER_SAMPLE = player_sample_name
    ACTIVE_COACH_SAMPLE = coach_sample_name
    ACTIVE_PLAYER_SLUG = player_slug or player_sample_name
    ACTIVE_PLAYER_LABEL = player_label or player_sample_name.title()
    by_sample: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in rows:
        by_sample[row["sample_name"]][row["metric_key"]] = row
    if player_sample_name not in by_sample:
        raise ValueError(f"Metrics CSV is missing player sample_name={player_sample_name!r}. Found: {', '.join(sorted(by_sample))}")
    if coach_sample_name not in by_sample:
        raise ValueError(f"Metrics CSV is missing coach sample_name={coach_sample_name!r}. Found: {', '.join(sorted(by_sample))}")
    julian = by_sample[player_sample_name]
    coach = by_sample[coach_sample_name]

    grouped: dict[str, list[str]] = defaultdict(list)
    for metric_key in BACKEND_ORDER:
        metric = julian.get(metric_key)
        if not metric:
            continue
        if metric_key in ISSUE_BACKEND_KEYS:
            module = "专项问题"
        elif metric_key.startswith("ready_"):
            module = "Ready Position"
        else:
            module = "Contact Position"
        grouped[module].append(
            metric_card(
                metric,
                coach.get(metric_key),
                peer_rows,
                BACKEND_ILLUSTRATION_NAMES.get(metric_key, metric["metric_name_zh"]),
                module == "专项问题",
                module != "专项问题",
            )
        )
    ready_cards = "".join(grouped["Ready Position"])
    contact_cards = "".join(grouped["Contact Position"])
    issue_cards = "".join(grouped["专项问题"])
    research_assets = make_research_assets(julian, coach, out_dir)
    pitch_css, pitch_sections = load_pitch_report_parts(pitch_report, out_dir)
    pitch_player_sections = wrap_pitch_sections(pitch_sections["player"])
    pitch_coach_sections = wrap_pitch_sections(pitch_sections["coach"])
    pitch_researcher_sections = wrap_pitch_sections(pitch_sections["researcher"])

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>球员综合表现报告</title>
  <style>
    :root {{
      --primary:#2563eb; --ink:#101828; --body:#344054; --mid:#667085; --mute:#98a2b3;
      --line:#d0d5dd; --canvas:#f5f7fb; --soft:#eef6ff; --card:#fff; --dusk:#101828;
      --orange:#f97316; --success:#16a34a; --red:#ef4444; --review:#e89918;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--canvas); color:var(--ink); font-family:STHeiti,"PingFang SC","Microsoft YaHei",system-ui,sans-serif; line-height:1.5; letter-spacing:0; }}
    main {{ max-width:1180px; margin:auto; padding:32px 24px 72px; }}
    h1 {{ font-size:42px; line-height:52px; font-weight:500; margin:0 0 12px; }}
    h2 {{ font-size:30px; line-height:40px; font-weight:500; margin:0; }}
    h3 {{ font-size:24px; line-height:34px; font-weight:500; margin:0; }}
    h4 {{ font-size:20px; line-height:30px; margin:0; }}
    .section-title h4 {{ font-size:22px; line-height:32px; font-weight:500; }}
    p {{ margin:0; color:var(--body); font-size:18px; overflow-wrap:anywhere; }}
    .section {{ margin-top:34px; min-width:0; }}
    .section-title {{ display:flex; align-items:center; gap:14px; margin-bottom:18px; }}
    .mark {{ width:12px; height:40px; background:var(--primary); border-radius:999px; flex:0 0 auto; }}
    .module-note {{ background:var(--soft); border:1px solid #bfdbfe; border-radius:12px; padding:16px 18px; margin-bottom:18px; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }}
    .grid-2 {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
    .metrics-with-media {{ display:grid; grid-template-columns:minmax(0,2fr) minmax(300px,1fr); gap:18px; align-items:start; }}
    .metrics-with-media .grid {{ grid-template-columns:1fr; }}
    .card,.metric-card,.visual-card {{ background:#fffefa; border:2px solid #d2d2d2; border-radius:24px; padding:24px; min-width:0; }}
    .card.good,.metric-card.good,
    .card.review,.metric-card.review,
    .card.risk,.metric-card.risk {{ background:#fffefa; }}
    .metric-card {{ display:grid; grid-template-columns:minmax(110px,145px) minmax(130px,165px) minmax(0,1fr); gap:18px; align-items:center; min-height:236px; border-color:#d2d2d2; border-radius:26px; background:#fffefa; }}
    .metric-summary {{ min-width:0; display:grid; align-content:center; gap:14px; }}
    .metric-en {{ color:#667085; font-size:13px; line-height:17px; font-weight:700; margin-top:0; }}
    .metric-detail {{ min-width:0; display:grid; gap:12px; }}
    .metric-detail-cn,.copy-cn,.module-note-cn,.caption-cn {{ color:#344054; font-size:15px; line-height:22px; font-weight:700; }}
    .metric-detail-en,.copy-en,.module-note-en,.caption-en {{ color:#7a8494; font-size:12px; line-height:18px; font-weight:600; }}
    .card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
    .badge {{ display:inline-flex; align-items:center; justify-content:center; width:max-content; min-width:70px; border-radius:999px; padding:4px 12px; font-size:14px; line-height:20px; font-weight:700; white-space:nowrap; }}
    .badge.good {{ background:#dcfce7; color:#166534; }}
    .badge.review {{ background:#fff7ed; color:#9a3412; }}
    .badge.risk {{ background:#fef2f2; color:#b91c1c; }}
    .metric-value {{ font-size:38px; line-height:1; font-weight:800; margin:0; color:#000; overflow-wrap:anywhere; }}
    .pitch-coach-reference {{ display:inline-grid; gap:2px; justify-self:start; min-width:92px; border:1px solid #d0d5dd; border-radius:10px; padding:7px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; }}
    .pitch-coach-reference b {{ color:#101828; font-size:12px; line-height:16px; font-weight:800; }}
    .pitch-coach-reference span {{ color:#667085; font-size:12px; line-height:15px; font-weight:800; }}
    .compact-metrics {{ grid-template-columns:1fr; gap:18px; }}
    .compact-metrics .metric-card {{ padding:22px 26px; }}
    .compact-metrics .metric-card h4 {{ font-size:18px; line-height:23px; font-weight:800; }}
    .issue-with-legend {{ display:grid; grid-template-columns:minmax(0,1fr) 150px; gap:14px; align-items:start; }}
    .issue-metrics {{ grid-template-columns:1fr; }}
    .issue-metrics .metric-card {{ max-width:100%; min-height:220px; padding:22px 26px; grid-template-columns:minmax(180px,220px) minmax(118px,150px) minmax(0,1fr); gap:18px; }}
    .issue-metrics .metric-card h4 {{ font-size:18px; line-height:23px; }}
    .issue-metrics .metric-value {{ font-size:32px; line-height:1.05; white-space:nowrap; overflow-wrap:normal; word-break:keep-all; }}
    .issue-metrics .metric-detail {{ gap:10px; }}
    .issue-metrics .metric-detail-cn {{ font-size:13px; line-height:20px; }}
    .issue-metrics .metric-detail-en {{ font-size:11px; line-height:17px; }}
    .issue-metrics .compare-pills {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .issue-metrics .compare-pill {{ display:inline-grid; gap:2px; border:1px solid #d0d5dd; border-radius:12px; padding:8px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; }}
    .issue-metrics .compare-pill b {{ color:#667085; font-size:11px; line-height:14px; }}
    .metric-illustration {{ margin:0; width:100%; aspect-ratio:1; border-radius:16px; overflow:hidden; background:transparent; }}
    .metric-illustration img {{ width:100%; height:100%; object-fit:contain; display:block; }}
    .peer-range {{ display:grid; grid-template-columns:max-content 28px minmax(90px,1fr) 28px; gap:7px; align-items:center; margin-top:0; }}
    .peer-label {{ color:#000; font-size:12px; line-height:15px; font-weight:800; }}
    .peer-min,.peer-max {{ color:#344054; font-size:13px; line-height:16px; font-weight:800; text-align:center; }}
    .unit-stack {{ display:inline-grid; gap:0; line-height:1.05; vertical-align:baseline; white-space:normal; }}
    .unit-stack .unit-number, .unit-stack .unit-label {{ display:block; }}
    .metric-value .unit-stack, .pitch-report .metric-value .unit-stack {{ display:grid; justify-items:start; }}
    .peer-min .unit-stack, .peer-max .unit-stack,
    .pitch-report .peer-min .unit-stack, .pitch-report .peer-max .unit-stack {{ justify-items:center; text-align:center; }}
    .peer-track {{ position:relative; height:28px; border-radius:999px; background:linear-gradient(180deg,transparent 0 11px,#eef2f7 11px 17px,transparent 17px); }}
    .peer-span {{ position:absolute; top:11px; height:6px; border-radius:999px; background:linear-gradient(90deg,#dcfce7,#bae6fd); }}
    .peer-dot {{ position:absolute; top:50%; width:10px; height:10px; border:2px solid #fff; border-radius:999px; transform:translate(-50%,-50%); box-shadow:0 0 0 1px rgba(16,24,40,.12); }}
    .peer-dot.current-player {{ z-index:4; width:16px; height:16px; background:#ef4444; border:3px solid #fff; box-shadow:0 0 0 2px #fff,0 0 0 6px color-mix(in srgb, var(--marker-color,#ef4444) 20%, transparent),0 0 0 1px rgba(16,24,40,.15); }}
    .peer-range.no-markers .peer-track {{ height:18px; background:linear-gradient(180deg,transparent 0 6px,#eef2f7 6px 12px,transparent 12px); }}
    .peer-range.no-markers .peer-span {{ top:6px; }}
    .peer-dot.missing {{ opacity:.45; box-shadow:0 0 0 1px rgba(16,24,40,.22),0 0 0 4px rgba(16,24,40,.04); }}
    .peer-empty {{ color:var(--mid); font-size:16px; font-weight:700; }}
    .peer-legend {{ margin-top:12px; padding:12px 10px; border:1px solid #d0d5dd; border-radius:14px; background:#fff; }}
    .peer-legend h4 {{ font-size:14px; line-height:18px; margin:0 0 8px; }}
    .peer-legend ul {{ list-style:none; margin:0; padding:0; display:grid; gap:7px; }}
    .issue-with-legend > .peer-legend {{ position:sticky; top:18px; margin-top:0; }}
    .issue-with-legend > .peer-legend ul {{ grid-template-columns:1fr; }}
    .peer-legend li {{ display:flex; align-items:center; gap:7px; color:#344054; font-size:12px; line-height:16px; font-weight:700; }}
    .legend-dot {{ width:10px; height:10px; border-radius:999px; box-shadow:0 0 0 1px rgba(16,24,40,.12); flex:0 0 auto; }}
    .visual-card p,.metric-card p,.card p {{ margin-top:8px; }}
    .reconstruction-annotated {{ position:relative; margin:0; background:#fff; border:1px solid var(--line); border-radius:18px; overflow:hidden; }}
    .reconstruction-annotated img {{ width:100%; aspect-ratio:16/10; object-fit:contain; display:block; background:#fff; }}
    .reconstruction-annotated figcaption {{ display:grid; gap:4px; padding:12px 14px; border-top:1px solid #e4e7ec; }}
    .reconstruction-annotated figcaption b {{ color:var(--ink); font-size:15px; line-height:20px; }}
    .reconstruction-annotated figcaption span {{ display:block; }}
    .event-gifs {{ position:sticky; top:18px; }}
    .event-gif-figure {{ margin:12px 0 0; border:1px solid var(--line); border-radius:14px; overflow:hidden; background:#fff; }}
    .event-gif-figure img {{ width:100%; aspect-ratio:16/10; object-fit:contain; display:block; background:#fff; }}
    .event-gif-figure figcaption {{ display:flex; justify-content:space-between; gap:8px; padding:8px 10px; border-top:1px solid #e4e7ec; }}
    .event-gif-figure b {{ color:var(--ink); font-size:13px; }}
    .event-gif-figure span {{ color:var(--mid); font-size:12px; text-align:right; }}
    .event-comparison {{ display:grid; grid-template-columns:minmax(260px,.9fr) minmax(0,1.8fr); gap:18px; align-items:stretch; margin:0 0 18px; }}
    .event-comparison .event-gifs {{ position:static; }}
    .event-comparison .visual-card {{ display:grid; align-content:start; }}
    .event-comparison .visual-card p {{ font-size:13px; line-height:18px; }}
    .event-comparison .section-annotation {{ width:100%; margin:0; }}
    .two-column-metrics {{ grid-template-columns:repeat(2,minmax(0,1fr)); }}
    .two-column-metrics .metric-card {{ min-height:304px; padding:20px; grid-template-columns:minmax(100px,126px) minmax(104px,132px) minmax(0,1fr); gap:12px; }}
    .two-column-metrics .metric-card h4 {{ font-size:17px; line-height:22px; }}
    .two-column-metrics .metric-value {{ font-size:34px; }}
    .two-column-metrics .metric-detail {{ gap:8px; }}
    .two-column-metrics .metric-detail-cn {{ font-size:13px; line-height:19px; }}
    .two-column-metrics .metric-detail-en {{ font-size:11px; line-height:16px; }}
    .section-annotation {{ width:calc((100% - 18px) / 1.46); margin:0 0 18px; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; }}
    .section-annotation img {{ width:100%; aspect-ratio:16/9; object-fit:contain; display:block; background:#fff; }}
    .section-annotation figcaption {{ display:flex; justify-content:space-between; gap:10px; padding:10px 12px; border-top:1px solid #e4e7ec; }}
    .section-annotation b {{ color:var(--ink); font-size:14px; }}
    .section-annotation span {{ color:var(--mid); font-size:13px; text-align:right; }}
    .kinetic-chain-card {{ padding:22px; }}
    .kinetic-chain-card p {{ max-width:920px; }}
    .kinetic-chain-figure {{ margin:8px 0 0; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; }}
    .kinetic-chain-figure img {{ width:100%; aspect-ratio:1600/360; object-fit:contain; display:block; background:#fff; }}
    .kinetic-speed-figure {{ margin:16px 0 0; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; }}
    .kinetic-speed-figure img {{ width:100%; aspect-ratio:1600/760; object-fit:contain; display:block; background:#fff; }}
    .researcher-stack .kinetic-chain-card {{ margin:0; }}
    .kinetic-node-notes {{ display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:12px; margin-top:16px; }}
    .kinetic-node-note {{ border:1px solid #d0d5dd; border-radius:14px; padding:12px 12px 14px; background:#fff; min-width:0; }}
    .kinetic-node-note b {{ display:block; color:#101828; font-size:15px; line-height:20px; margin-bottom:5px; }}
    .kinetic-node-note span {{ display:block; color:#667085; font-size:12px; line-height:18px; font-weight:700; }}
    .kinetic-analysis {{ margin-top:22px; display:grid; gap:12px; padding:18px; border:1px solid #e4e7ec; border-radius:18px; background:#f9fafb; }}
    .kinetic-analysis h4 {{ font-size:20px; line-height:28px; margin:0; }}
    .analyst-chart-grid {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin-top:18px; }}
    .analyst-chart-card {{ display:grid; gap:14px; padding:22px; }}
    .analyst-chart-figure {{ margin:0; border:1px solid var(--line); border-radius:18px; overflow:hidden; background:#fff; }}
    .analyst-chart-figure img {{ width:100%; aspect-ratio:1600/720; object-fit:contain; display:block; background:#fff; }}
    .analyst-chart-copy {{ color:#667085; font-size:15px; line-height:24px; font-weight:600; }}
    @media (max-width:1100px) {{ .metric-card {{ grid-template-columns:minmax(100px,130px) minmax(120px,150px) minmax(0,1fr); gap:14px; }} .metric-detail-cn,.copy-cn,.module-note-cn,.caption-cn {{ font-size:14px; line-height:21px; }} .metric-detail-en,.copy-en,.module-note-en,.caption-en {{ font-size:11px; line-height:17px; }} .compact-metrics .metric-card {{ padding:20px 22px; }} }}
    @media (max-width:960px) {{ .grid-2,.metrics-with-media,.issue-with-legend,.event-comparison,.analyst-chart-grid {{ grid-template-columns:1fr; }} .grid,.compact-metrics,.metrics-with-media .grid,.issue-metrics,.two-column-metrics {{ grid-template-columns:1fr; }} .section-annotation {{ width:100%; }} .event-gifs {{ position:static; }} h1 {{ font-size:36px; line-height:44px; }} .metric-card,.issue-metrics .metric-card {{ grid-template-columns:170px minmax(160px,210px); }} .metric-detail {{ grid-column:1 / -1; }} .kinetic-node-notes {{ grid-template-columns:1fr 1fr; }} }}
    @media (max-width:640px) {{ main {{ padding-left:16px; padding-right:16px; }} .metric-card {{ grid-template-columns:1fr; min-height:0; gap:18px; }} .compact-metrics .metric-card {{ padding:22px 18px; }} .metric-illustration {{ max-width:260px; justify-self:center; }} .peer-range {{ grid-template-columns:1fr 32px minmax(100px,1fr) 32px; gap:8px; }} .kinetic-node-notes {{ grid-template-columns:1fr; }} }}
    {pitch_css}
    {PITCH_COACH_ALIGNMENT_CSS}
    {SECTION_TITLE_LEVEL_CSS}
  </style>
</head>
<body>
  <main>
    <section class="section" id="player-coach-batting-report">
      <div class="section-title"><span class="mark"></span><h1>球员综合表现报告</h1></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>球员视角</h2></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>打击</h3></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h4>挥棒速度与动作对照</h4></div>
      <div class="grid-2">
        <article class="visual-card">
          <h4>球员速度与挥棒方向</h4>
          {speed_annotation_panel(julian, ACTIVE_PLAYER_SAMPLE)}
        </article>
        <article class="visual-card">
          <h4>教练示范动作对照</h4>
          {speed_annotation_panel(coach, "coach")}
        </article>
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h4>准备姿态</h4></div>
      <div class="event-comparison">
        {event_gif_panel("准备姿态动作片段", julian, "ready_com_height_ratio", "ready")}
        <figure class="section-annotation">
          <img src="{esc(versioned_asset("assets/vicon_2d_geometry_annotations/ready_position_vicon_geometry_on_2d.png"))}" alt="球员准备姿态动作观察" loading="lazy">
          <figcaption><b>准备姿态动作参考</b><span>启动前代表画面</span></figcaption>
        </figure>
      </div>
      <div class="grid compact-metrics two-column-metrics">
        {ready_cards}
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h4>击球瞬间</h4></div>
      <div class="event-comparison">
        {event_gif_panel("击球瞬间动作片段", julian, "contact_bat_speed_kmh", "contact")}
        <figure class="section-annotation">
          <img src="{esc(versioned_asset("assets/vicon_2d_geometry_annotations/contact_position_vicon_geometry_on_2d.png"))}" alt="球员击球瞬间动作观察" loading="lazy">
          <figcaption><b>击球瞬间动作参考</b><span>击球附近代表画面</span></figcaption>
        </figure>
      </div>
      <div class="grid compact-metrics two-column-metrics">
        {contact_cards}
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>投球</h3></div>
    </section>
    {pitch_player_sections}

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>教练视角</h2></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>打击</h3></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h4>专项问题</h4></div>
      <div class="issue-with-legend">
        <div class="grid compact-metrics issue-metrics">{issue_cards}</div>
        {peer_legend(peer_rows, anonymize_names=False)}
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>投球</h3></div>
    </section>
    {pitch_coach_sections}

    <section class="section">
      <div class="section-title"><span class="mark"></span><h2>研究者视角</h2></div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>打击</h3></div>
    </section>

    <section class="section" id="batting-c3d-curves">
      <div class="section-title"><span class="mark"></span><h4>动力链与时间曲线</h4></div>
      <div class="researcher-stack">
        <article class="visual-card kinetic-chain-card">
          <h4>下肢 -> 髋部 -> 躯干 -> 手腕 -> 球棒</h4>
          <figure class="kinetic-chain-figure">
            <img src="{esc(versioned_asset(research_assets["kinetic"]))}" alt="{esc(ACTIVE_PLAYER_LABEL)} 打击动力链图" loading="lazy">
          </figure>
          <figure class="kinetic-speed-figure">
            <img src="{esc(versioned_asset(research_assets["kinetic_speed"]))}" alt="动力链速度时间曲线" loading="lazy">
          </figure>
          <div class="kinetic-node-notes">
            <div class="kinetic-node-note"><b>下肢</b><span>后腿和重心先把身体稳定住，给挥棒留出发力基础。</span></div>
            <div class="kinetic-node-note"><b>髋部</b><span>髋部打开把下半身力量送向身体中段。</span></div>
            <div class="kinetic-node-note"><b>躯干</b><span>躯干旋转承接髋部动作，并影响球棒进入击球区的时机。</span></div>
            <div class="kinetic-node-note"><b>手腕</b><span>手腕重点看球棒面能否稳定，不是越快越好。</span></div>
            <div class="kinetic-node-note"><b>球棒</b><span>球棒速度是动作链末端输出，需要和路径稳定性一起看。</span></div>
          </div>
          <div class="kinetic-analysis">
            <h4>详细解读</h4>
            <p class="copy-cn">研究者模块把准备、髋部打开、躯干旋转、手腕控制和球棒速度放在同一条线上，便于检查力量是否顺着身体释放到球棒。</p>
            <p class="copy-en">This researcher view puts preparation, hip opening, trunk rotation, wrist control, and bat speed into one sequence to show whether the swing releases smoothly into the bat.</p>
          </div>
        </article>
        <div class="analyst-chart-grid">
          <article class="visual-card analyst-chart-card">
            <figure class="analyst-chart-figure"><img src="{esc(versioned_asset(research_assets["speed"]))}" alt="挥棒速度时间曲线" loading="eager"></figure>
            <p class="analyst-chart-copy">怎么看：速度曲线用来比较球员和 Coach 的挥棒加速节奏。重点看速度最高点是否靠近击球窗口，以及速度是否集中释放。</p>
            <p class="analyst-chart-copy">How to read it: the speed graph compares the player's swing rhythm with the Coach reference. Look for whether the fastest moment happens near contact and whether speed is released in one clear burst.</p>
          </article>
          <article class="visual-card analyst-chart-card">
            <figure class="analyst-chart-figure"><img src="{esc(versioned_asset(research_assets["angle"]))}" alt="挥棒角度时间曲线" loading="eager"></figure>
            <p class="analyst-chart-copy">怎么看：角度曲线用来比较球员和 Coach 的球棒方向变化。重点不是角度越大越好，而是击球窗口前后方向是否稳定。</p>
            <p class="analyst-chart-copy">How to read it: the angle graph compares how the bat direction changes for the player and the Coach reference. Around contact, steadiness matters more than a bigger number.</p>
          </article>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-title"><span class="mark"></span><h3>投球</h3></div>
    </section>
    {pitch_researcher_sections}

  </main>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a standalone player-vs-coach batting report section.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--peers", type=Path, default=DEFAULT_PEERS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--pitch-report",
        type=Path,
        default=DEFAULT_PITCH_REPORT,
        help="Existing pitching-template index.html whose sections and assets are copied into pitch_assets/.",
    )
    parser.add_argument("--player-sample-name", default="julian")
    parser.add_argument("--coach-sample-name", default="coach")
    parser.add_argument("--player-slug", default=None)
    parser.add_argument("--player-label", default=None)
    args = parser.parse_args()

    rows = read_csv(args.metrics)
    peer_rows = read_peer_metrics(args.peers)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    html_text = "\n".join(
        line.rstrip()
        for line in render(
            rows,
            peer_rows,
            args.out.parent,
            args.pitch_report,
            args.player_sample_name,
            args.coach_sample_name,
            args.player_slug,
            args.player_label,
        ).splitlines()
    ) + "\n"
    args.out.write_text(html_text, encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
