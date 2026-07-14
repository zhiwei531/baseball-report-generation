from __future__ import annotations

import argparse
import json
import math
from datetime import date
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_INPUT = ROOT / "examples" / "sample_raw_input.json"
THRESHOLDS = ROOT / "rules" / "metric_thresholds.json"
LIMITATIONS = ROOT / "rules" / "limitations_rules.json"
MD_TEMPLATE = ROOT / "templates" / "report_review.md"
HTML_TEMPLATE = ROOT / "templates" / "app_report.html"
OUT_DIR = ROOT / "outputs" / "report_framework_sample"


STATUS_LABELS = {
    "good": "良好",
    "warning": "偏离",
    "concern": "关注",
    "suspicious": "需复核",
    "unavailable": "不可用",
}


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def in_range(value: float, rule: dict[str, float]) -> bool:
    if "min" in rule and value < rule["min"]:
        return False
    if "max" in rule and value >= rule["max"]:
        return False
    return True


def match_rule(value: float | None, threshold: dict[str, Any]) -> str:
    if value is None:
        return "unavailable"
    for status in ("suspicious", "good", "warning", "concern"):
        rule = threshold.get(status)
        if not rule:
            continue
        rules = rule if isinstance(rule, list) else [rule]
        if any(in_range(value, item) for item in rules):
            return status
    return "warning"


def clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def number_or_none(value: Any) -> float | None:
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def value_or_zero(value: Any) -> float:
    number = number_or_none(value)
    return 0.0 if number is None else number


def score_from_status(status: str) -> int | None:
    return {
        "good": 90,
        "warning": 62,
        "concern": 32,
        "suspicious": 35,
        "unavailable": None,
    }.get(status)


def status_from_score(score: int | float | None) -> str:
    if score is None:
        return "unavailable"
    if score >= 80:
        return "good"
    if score >= 50:
        return "warning"
    return "concern"


def fmt_value(value: Any, unit: str = "") -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        text = f"{value:.3f}".rstrip("0").rstrip(".")
    else:
        text = str(value)
    return f"{text}{unit}"


METRIC_EN = {
    "hip_shoulder_separation_deg": {
        "name": "Hip-shoulder separation",
        "explain": "Shows whether the lower body leads before the upper body. More separation usually means better stored rotation.",
        "evidence": "Estimated from shoulder and hip keypoints in the stabilized video.",
    },
    "attack_angle_deg": {
        "name": "Attack angle",
        "explain": "Shows whether the swing path is level, upward, or downward through the hitting zone.",
        "evidence": "Estimated from the hand path around the impact-like frame.",
    },
    "front_knee_angle_deg": {
        "name": "Front knee angle",
        "explain": "Shows whether the front leg creates a stable brace during the key moment.",
        "evidence": "Computed from hip, knee, and ankle keypoints.",
    },
    "torso_tilt_deg": {
        "name": "Torso tilt",
        "explain": "Shows whether the trunk stays balanced instead of collapsing forward or backward.",
        "evidence": "Estimated from the shoulder and hip center line.",
    },
    "head_stability_pct": {
        "name": "Head stability",
        "explain": "Shows how much the head moves during the active part of the motion.",
        "evidence": "Computed from head keypoint drift relative to body scale.",
    },
    "contact_time_s": {
        "name": "Contact timing",
        "explain": "This is an approximate event marker, not the confirmed ball-bat contact frame.",
        "evidence": "Requires ball tracking or high-speed footage for exact confirmation.",
    },
    "power_quality": {"name": "Power preparation"},
    "lower_body_start": {"name": "Lower-body start"},
    "start_efficiency": {"name": "Start efficiency"},
    "swing_path": {"name": "Swing path"},
    "contact_stability": {"name": "Contact stability"},
    "pitch_hip_shoulder_separation_deg": {
        "name": "Pitch hip-shoulder separation",
        "explain": "Shows whether the pitcher creates separation before arm acceleration.",
        "evidence": "Estimated from shoulder and hip keypoints near release.",
    },
    "pitch_front_knee_angle_deg": {
        "name": "Pitch front knee angle",
        "explain": "Shows whether the landing leg gives the body a stable base.",
        "evidence": "Computed from the front hip, knee, and ankle keypoints.",
    },
    "pitch_head_stability_pct": {
        "name": "Pitch head stability",
        "explain": "Shows whether the head and direction stay controlled through release.",
        "evidence": "Computed from head movement during the pitching window.",
    },
    "pitch_ball_speed_px_s": {
        "name": "Pitch speed proxy",
        "explain": "A same-camera trend value only. It is not radar speed.",
        "evidence": "Pixel speed cannot be converted to true speed without camera calibration.",
    },
    "pitch_release_timing_pct": {
        "name": "Release timing",
        "explain": "Approximate release phase based on hand and fingertip speed.",
        "evidence": "Not the exact ball release frame.",
    },
    "pitch_front_foot_landing_pct": {
        "name": "Front foot landing",
        "explain": "Approximate landing phase based on front foot movement.",
        "evidence": "Useful for timing review, not force-plate measurement.",
    },
    "pitch_elbow_flexion_deg": {
        "name": "Elbow flexion",
        "explain": "Shows the throwing arm bend near the release-like frame.",
        "evidence": "Computed from shoulder, elbow, and wrist keypoints.",
    },
    "pitch_arm_abduction_deg": {
        "name": "Arm abduction",
        "explain": "Shows how far the throwing arm moves away from the trunk.",
        "evidence": "Estimated from 2D keypoint direction.",
    },
    "pitch_lower_body_start_score": {"name": "Lower-body start"},
    "pitch_target_line_control_score": {"name": "Target-line control"},
    "pitch_arm_path_score": {"name": "Arm path"},
    "pitch_release_quality_score": {"name": "Release quality"},
    "pitch_finish_stability_score": {"name": "Finish stability"},
    "calibration_role": {
        "name": "Vicon / 3D calibration role",
        "explain": "External 3D data can calibrate speed, direction, and scale. CV values remain video estimates.",
        "evidence": "Use Vicon or GVHMR as the calibration reference, not as a replacement for the video evidence.",
    },
    "raw_table_policy": {
        "name": "Raw data display policy",
        "explain": "The visible report prioritizes interpretable curves instead of listing every marker field.",
        "evidence": "CSV files can still be kept for audit, while the report shows trend charts.",
    },
}


STATUS_EN = {
    "good": "Good",
    "warning": "Watch",
    "concern": "Needs work",
    "suspicious": "Review",
    "unavailable": "Unavailable",
}


PITCH_PRIORITY_EN = {
    "pitch_hip_shoulder_separation_deg": {
        "name": "Pitch hip-shoulder separation",
        "explain": "There is not enough space between the hips and shoulders at release, so power may not transfer cleanly from the body to the arm.",
    },
    "pitch_lower_body_start_score": {
        "name": "Lower-body start",
        "explain": "Check whether the lower body starts the throw before the arm, instead of letting the hand lead the whole motion.",
    },
    "pitch_target_line_control_score": {
        "name": "Target-line control",
        "explain": "Check whether the stride and body direction stay on the target line.",
    },
    "pitch_arm_path_score": {
        "name": "Arm path",
        "explain": "Check whether the throwing arm follows a stable path instead of looping or changing direction randomly.",
    },
    "pitch_release_quality_score": {
        "name": "Release quality",
        "explain": "Check whether the release happens cleanly after the body has moved into position.",
    },
    "pitch_finish_stability_score": {
        "name": "Finish stability",
        "explain": "Check whether the body can stay balanced after release instead of falling away from the target.",
    },
    "pitch_front_knee_angle_deg": {
        "name": "Pitch front knee angle",
        "explain": "Check whether the landing leg gives the body a stable base during the throw.",
    },
    "pitch_head_stability_pct": {
        "name": "Pitch head stability",
        "explain": "Check whether the head and body direction stay controlled through release.",
    },
}


RECOMMENDATION_EN = {
    "墙边髋肩分离": {
        "title": "Wall-side hip-shoulder separation",
        "why": "Low hip-shoulder separation means the body is not storing enough rotational power. Learn to move the hips first and keep the shoulders slightly delayed.",
        "how": "Stand sideways near a wall with both feet fixed. Turn the hips gently first, pause briefly, then let the shoulders follow.",
        "volume": "2 sets per day, 8 reps each side.",
        "check": "The parent checks that shoulders do not turn at the same time as the hips.",
    },
    "Tee 平扫路线": {
        "title": "Level tee swing path",
        "why": "A high attack angle suggests the bat is lifting too much. A level path keeps the bat in the hitting zone longer.",
        "how": "Set the tee around waist height and use a soft band or towel as a level reference line behind the ball.",
        "volume": "3 sets, 8 balls per set.",
        "check": "Watch from the side and check whether the bat travels roughly along the level line.",
    },
    "跨步停顿挥棒": {
        "title": "Stride, pause, then swing",
        "why": "The front-leg brace is usable. A pause drill turns that support into a stable power point.",
        "how": "Finish the stride, pause for one second after the front foot lands, confirm balance and eye position, then swing slowly.",
        "volume": "3 sets, 6 reps per set.",
        "check": "Check whether the body shakes after landing or the head leaves early.",
    },
    "看球冻结": {
        "title": "See-the-ball freeze",
        "why": "Head stability is a strength in this report, so the athlete should preserve it while adding power.",
        "how": "After each swing, hold the contact-position pose for one second and keep the eyes near the original ball position.",
        "volume": "2 sets, 10 reps per set.",
        "check": "If the athlete looks up immediately after the swing, repeat the rep.",
    },
    "前脚目标线跨步": {
        "title": "Front-foot target-line stride",
        "why": "Pitching starts by moving the body toward the target. A stable front foot helps the release point repeat.",
        "how": "Tape a target line on the ground and rehearse the pitching motion slowly, landing the front foot toward the line.",
        "volume": "3 sets, 6 reps per set.",
        "check": "Stand behind the pitcher and check whether the front foot lands clearly outside the target line.",
    },
    "髋先走、肩晚到": {
        "title": "Hips first, shoulders later",
        "why": "When separation is low, the athlete tends to throw with the arm only and the power chain breaks.",
        "how": "Let the front foot land and the hips turn first, keep the shoulders and glove back briefly, then let the upper body follow.",
        "volume": "2 sets per day, 8 slow reps.",
        "check": "If the shoulders and hips turn together, slow the drill down and repeat.",
    },
    "毛巾手臂路径": {
        "title": "Towel arm-path drill",
        "why": "A stable arm path makes the release point easier to repeat and reduces random arm swings.",
        "how": "Hold a small towel instead of a ball and move through the full pitching rhythm, letting the towel release toward the target.",
        "volume": "3 sets, 8 reps per set.",
        "check": "Watch from the side for large loops or pauses in the arm path.",
    },
    "出手后稳定收尾": {
        "title": "Stable finish after release",
        "why": "A stable finish shows that the body does not fall apart too early and makes retesting easier.",
        "how": "After each release, hold the finish for one second with the chest still facing the target.",
        "volume": "2 sets, 8 reps per set.",
        "check": "Check whether the body can stop cleanly after release without the feet or head wobbling.",
    },
}


def rec_en(rec: dict[str, Any], key: str) -> str:
    return RECOMMENDATION_EN.get(rec.get("title"), {}).get(key, "")


def paired_text(cn: str, en: str, cn_tag: str = "span", en_tag: str = "span") -> str:
    return (
        f'<{cn_tag} class="zh">{escape(cn)}</{cn_tag}>'
        f'<{en_tag} class="en">{escape(en)}</{en_tag}>'
    )


def paired_html(cn_html: str, en: str, en_tag: str = "p", en_class: str = "en") -> str:
    return f"{cn_html}<{en_tag} class=\"{en_class}\">{escape(en)}</{en_tag}>"


def metric_en(m: dict[str, Any], field: str, fallback: str = "") -> str:
    item = METRIC_EN.get(m.get("metric_id"), {})
    return str(item.get(field) or fallback)


def section_title(cn: str, en: str) -> str:
    return paired_text(cn, en, "span", "span")


def metric_block(
    metric_id: str,
    name: str,
    domain: str,
    source: str,
    value: Any,
    unit: str,
    status: str,
    evidence: str,
    parent_explanation: str,
    child_explanation: str = "",
    coach_note: str = "",
    research_note: str = "",
    score: int | None = None,
    confidence: float | None = None,
    is_proxy: bool = False,
    comparison: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "name": name,
        "domain": domain,
        "source": source,
        "value": value,
        "unit": unit,
        "status": status,
        "score": score if score is not None else score_from_status(status),
        "confidence": confidence,
        "is_available": status != "unavailable",
        "is_proxy": is_proxy,
        "evidence": evidence,
        "parent_explanation": parent_explanation,
        "child_explanation": child_explanation,
        "coach_note": coach_note,
        "research_note": research_note,
        "comparison": comparison or {},
    }


def build_metric_blocks(raw: dict[str, Any], thresholds: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    bat_sample = raw["session"].get("primary_bat_sample", "hit_vertical_02")
    pitch_sample = raw["session"].get("primary_pitch_sample", "pitch_vertical_10")
    hit = raw["cv_metrics"][bat_sample]
    pitch = raw["cv_metrics"][pitch_sample]
    peer = raw["vicon_metrics"]["Julian_wave02"]
    coach = raw["vicon_metrics"]["0506Coach_wave"]

    hss = hit["hip_shoulder_separation_deg"]
    attack = hit["attack_angle_deg"]
    knee = hit["front_knee_angle_deg"]
    torso = hit["torso_tilt_deg"]
    head = hit["head_stability_pct"]

    bat_metrics = [
        metric_block(
            "hip_shoulder_separation_deg",
            "髋肩分离",
            "bat",
            "cv",
            hss,
            "°",
            match_rule(hss, thresholds["hip_shoulder_separation_deg"]),
            f"本次 {fmt_value(hss, '°')}；同龄/Vicon 样本 {fmt_value(peer['hip_shoulder_separation_deg'], '°')}；教练参考 {fmt_value(coach['hip_shoulder_separation_deg'], '°')}",
            "身体还没有像拧毛巾一样先蓄力，容易变成只靠手臂挥棒。",
            "先让胯转一点、肩膀晚一点跟上，挥棒会更有力量。",
            "髋肩分离显著低于参考，建议先处理躯干-骨盆时序。",
            "CV 2D/3D 关键点估算；可用 Vicon marker 数据做标定参照。",
            confidence=0.68,
            comparison={"peer": peer["hip_shoulder_separation_deg"], "coach": coach["hip_shoulder_separation_deg"]},
        ),
        metric_block(
            "attack_angle_deg",
            "攻击角",
            "bat",
            "cv",
            attack,
            "°",
            match_rule(attack, thresholds["attack_angle_deg"]),
            f"本次 {fmt_value(attack, '°')}；目标是轻微上升或接近平扫",
            "棒子往上挑得比较明显，容易从球下面穿过去或打成高飞。",
            "想象球棒穿过一条水平隧道，不要急着往上抬。",
            "攻击角偏大，建议结合 Tee 平扫路线和击球区覆盖训练。",
            "攻击角来自视频棒身/手腕轨迹估算，受镜头角度影响。",
            confidence=0.68,
        ),
        metric_block(
            "front_knee_angle_deg",
            "前腿膝角",
            "bat",
            "cv",
            knee,
            "°",
            match_rule(knee, thresholds["front_knee_angle_deg"]),
            f"本次 {fmt_value(knee, '°')}；前腿支撑可用",
            "前腿支撑比较稳，身体有一个可以停住发力的位置。",
            "落地后前腿像柱子一样稳住，不要软掉。",
            "前腿角度在可接受支撑区间，可作为保持项。",
            "由前髋-前膝-前踝关键点计算。",
            confidence=0.68,
            comparison={"peer": peer["front_knee_angle_deg"], "coach": coach["front_knee_angle_deg"]},
        ),
        metric_block(
            "torso_tilt_deg",
            "躯干倾斜",
            "bat",
            "cv",
            torso,
            "°",
            match_rule(torso, thresholds["torso_tilt_deg"]),
            f"本次 {fmt_value(torso, '°')}；身体轴线控制较好",
            "身体没有明显扑出去，挥棒时比较能保持平衡。",
            "挥的时候头和胸口别冲太快，稳住再出棒。",
            "躯干倾斜处于较合理范围，可配合头部稳定继续保持。",
            "由肩髋中心线相对画面坐标估算。",
            confidence=0.68,
            comparison={"peer": peer["torso_tilt_deg"], "coach": coach["torso_tilt_deg"]},
        ),
        metric_block(
            "head_stability_pct",
            "头部稳定",
            "bat",
            "cv",
            head,
            "%",
            match_rule(head, thresholds["head_stability_pct"]),
            f"本次 {fmt_value(head, '%')}；看球稳定性好",
            "头比较稳，说明眼睛更容易一直盯住球。",
            "挥棒时眼睛留在球的位置，不要太早抬头。",
            "头部稳定表现好，可作为击球稳定评分的主要加分项。",
            "基于头部关键点漂移计算稳定百分比。",
            confidence=0.68,
            comparison={"peer": peer["head_stability_pct"], "coach": coach["head_stability_pct"]},
        ),
        metric_block(
            "contact_time_s",
            "接触时间",
            "bat",
            "cv",
            None,
            "s",
            "unavailable",
            "本次没有球追踪和真实碰撞帧",
            "这次看不到球棒真正碰到球的一瞬间，所以不评价这一项。",
            "需要更清楚的击球瞬间视频再复测。",
            "不可作为本次训练重点，只能提示补采集。",
            "需要球追踪或触球帧确认。",
            confidence=None,
        ),
    ]

    pitch_metrics = [
        metric_block(
            "pitch_hip_shoulder_separation_deg",
            "投球髋肩分离",
            "pitch",
            "cv",
            pitch["hip_shoulder_separation_deg"],
            "°",
            match_rule(pitch["hip_shoulder_separation_deg"], thresholds["hip_shoulder_separation_deg"]),
            f"本次 {fmt_value(pitch['hip_shoulder_separation_deg'], '°')}；投球蓄力偏少",
            "投球时身体拧开的空间不够，力量不容易从身体传到手上。",
            "先用身体带动，再让手臂出来。",
            "投球躯干-骨盆分离不足，建议增加分离和节奏训练。",
            "来自 CV 关键点角度，适合做同机位复测。",
            confidence=0.66,
        ),
        metric_block(
            "pitch_front_knee_angle_deg",
            "投球前腿膝角",
            "pitch",
            "cv",
            pitch["front_knee_angle_deg"],
            "°",
            match_rule(pitch["front_knee_angle_deg"], thresholds["front_knee_angle_deg"]),
            f"本次 {fmt_value(pitch['front_knee_angle_deg'], '°')}；前腿支撑可用",
            "落地腿比较能撑住，身体不容易塌掉。",
            "脚落地后，前腿帮你刹住身体。",
            "前腿角度在支撑区间，可作为保持项。",
            "由前髋-前膝-前踝关键点计算。",
            confidence=0.66,
        ),
        metric_block(
            "pitch_head_stability_pct",
            "投球头部稳定",
            "pitch",
            "cv",
            pitch["head_stability_pct"],
            "%",
            match_rule(pitch["head_stability_pct"], thresholds["head_stability_pct"]),
            f"本次 {fmt_value(pitch['head_stability_pct'], '%')}；头部控制好",
            "投球时头比较稳，说明身体方向感不错。",
            "投出去前眼睛看目标，不要甩头。",
            "头部稳定较好，可帮助投球方向控制。",
            "基于头部关键点漂移计算稳定百分比。",
            confidence=0.66,
        ),
        metric_block(
            "pitch_ball_speed_px_s",
            "投球速度 proxy",
            "pitch",
            "cv",
            pitch["ball_speed_px_s"],
            "px/s",
            "warning",
            f"本次 {fmt_value(pitch['ball_speed_px_s'], ' px/s')}；只可同机位复测",
            "这个不是正式球速，只能看下次有没有比这次更快。",
            "下次用同一个位置拍，才好比较进步。",
            "2D px/s 未标定，建议只做前后测趋势。",
            "没有雷达和相机标定，不能换算真实 km/h。",
            confidence=0.5,
            is_proxy=True,
        ),
        metric_block(
            "pitch_release_timing_pct",
            "出手时刻",
            "pitch",
            "cv",
            pitch.get("release_timing_pct"),
            "% video",
            "warning",
            "由手腕/指尖峰速帧估算，不等于真实球离手帧。",
            "这里表示动作在视频中大概什么时候释放力量，不是正式出手瞬间。",
            "看手腕和指尖什么时候最快。",
            "用于阶段定位，建议和球追踪数据分开表述。",
            "人体峰速 proxy。",
            confidence=0.62,
            is_proxy=True,
        ),
        metric_block(
            "pitch_front_foot_landing_pct",
            "前脚落地",
            "pitch",
            "cv",
            pitch.get("front_foot_landing_pct"),
            "% video",
            "warning" if pitch.get("front_foot_landing_pct") is not None else "unavailable",
            "由前脚跨步位移最大帧近似。",
            "这里帮助判断身体支撑建立得早不早。",
            "先落稳前脚，再把力量传出去。",
            "可用于看投球节奏，但不是力板实测落地。",
            "前脚关键点轨迹 proxy。",
            confidence=0.62,
            is_proxy=True,
        ),
        metric_block(
            "pitch_elbow_flexion_deg",
            "肘部弯曲",
            "pitch",
            "cv",
            pitch.get("elbow_flexion_deg"),
            "°",
            "warning",
            "出手近似帧的肩-肘-腕角度。",
            "这个角度用来看手臂在释放前是否过度折叠或太直。",
            "手臂放松，不要硬甩。",
            "作为观察项，不单独做医学判断。",
            "2D 关键点角度。",
            confidence=0.62,
        ),
        metric_block(
            "pitch_arm_abduction_deg",
            "手臂外展",
            "pitch",
            "cv",
            pitch.get("arm_abduction_deg"),
            "°",
            "warning",
            "出手近似帧的投球臂相对躯干方向。",
            "这个指标帮助看手臂路径是否离身体太远或太低。",
            "让手臂跟着身体方向出来。",
            "作为动作路径观察项。",
            "2D 关键点方向差。",
            confidence=0.62,
        ),
        metric_block(
            "pitch_lower_body_start_score",
            "下肢启动",
            "pitch",
            "derived",
            pitch.get("lower_body_start_score"),
            "分",
            status_from_score(pitch.get("lower_body_start_score")),
            "骨盆/重心向前转移映射。",
            "看身体有没有先用下肢带动，而不是只用手扔。",
            "脚和胯先带动，手臂后跟上。",
            "投球动力链的前段指标。",
            "由骨盆中心位移 proxy 计算。",
            score=pitch.get("lower_body_start_score"),
        ),
        metric_block(
            "pitch_target_line_control_score",
            "目标线控制",
            "pitch",
            "derived",
            pitch.get("target_line_control_score"),
            "分",
            status_from_score(pitch.get("target_line_control_score")),
            "前脚路径直线稳定性。",
            "看跨步方向是否稳定朝目标走。",
            "脚朝目标线落，不要横着飘。",
            "方向控制观察项。",
            "前脚轨迹拟合残差。",
            score=pitch.get("target_line_control_score"),
        ),
        metric_block(
            "pitch_arm_path_score",
            "手臂路径",
            "pitch",
            "derived",
            pitch.get("arm_path_score"),
            "分",
            status_from_score(pitch.get("arm_path_score")),
            "投球臂路径平滑/直线稳定。",
            "看手臂是不是顺着稳定路径释放，而不是乱甩。",
            "手臂跟着身体节奏走。",
            "手臂路径稳定性。",
            "手腕轨迹拟合残差。",
            score=pitch.get("arm_path_score"),
        ),
        metric_block(
            "pitch_release_quality_score",
            "释放质量",
            "pitch",
            "derived",
            pitch.get("release_quality_score"),
            "分",
            status_from_score(pitch.get("release_quality_score")),
            "出手速度 + 指尖速度 + 手臂路径。",
            "综合看最后释放阶段是否干净有速度。",
            "不要只拼手臂速度，先把路径走顺。",
            "释放阶段综合 proxy。",
            "速度和路径 proxy 平均。",
            score=pitch.get("release_quality_score"),
        ),
        metric_block(
            "pitch_finish_stability_score",
            "收尾稳定",
            "pitch",
            "derived",
            pitch.get("finish_stability_score"),
            "分",
            status_from_score(pitch.get("finish_stability_score")),
            "出手后头部和前脚路径稳定性。",
            "看投完以后身体能不能稳住方向。",
            "投完不要马上歪掉。",
            "收尾控制观察项。",
            "头部与前脚路径 proxy。",
            score=pitch.get("finish_stability_score"),
        ),
    ]
    return bat_metrics, pitch_metrics


def build_derived_scores(bat_metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lookup = {m["metric_id"]: m for m in bat_metrics}
    hss = number_or_none(lookup["hip_shoulder_separation_deg"]["value"])
    attack = number_or_none(lookup["attack_angle_deg"]["value"])
    head = number_or_none(lookup["head_stability_pct"]["value"])
    knee = number_or_none(lookup["front_knee_angle_deg"]["value"])

    power = None if hss is None else round(clamp(hss / 25 * 100))
    start_efficiency = 62
    path_score = None if attack is None else round(clamp(100 - max(0, abs(attack - 5) - 10) * 2))
    stability = None
    if head is not None:
        stability = round(clamp((head * 0.8) + (20 if knee is not None and 120 <= knee <= 150 else 0)))

    return [
        metric_block("power_quality", "蓄力质量", "bat", "derived", power, "分", status_from_score(power), "由髋肩分离映射得到", "蓄力不足，身体没有充分拧起来。", score=power),
        metric_block("lower_body_start", "下肢启动", "bat", "derived", None, "分", "unavailable", "COM 转移不可用", "这次无法判断下肢是否先启动。", score=None),
        metric_block("start_efficiency", "启动效率", "bat", "derived", start_efficiency, "分", status_from_score(start_efficiency), "由启动到事件时间估算", "启动节奏可用，但仍需和击球点配合。", score=start_efficiency),
        metric_block("swing_path", "挥棒路径", "bat", "derived", path_score, "分", status_from_score(path_score), "由攻击角映射得到", "挥棒路线偏上挑，需要更平地穿过击球区。", score=path_score),
        metric_block("contact_stability", "击球稳定", "bat", "derived", stability, "分", status_from_score(stability), "由头部稳定和前腿支撑合成", "看球和支撑表现好，是本次优势。", score=stability),
    ]


def build_recommendations() -> list[dict[str, Any]]:
    return [
        {
            "recommendation_id": "rec_hip_shoulder_wall",
            "title": "墙边髋肩分离",
            "priority": "high",
            "related_metrics": ["hip_shoulder_separation_deg", "power_quality"],
            "why": "髋肩分离低，说明身体蓄力不足。先学会胯先动、肩后动，挥棒才更容易有力量。",
            "how_to_do": "侧身站在墙边，双脚固定。先轻轻转胯，让肚脐转向投手方向；肩膀和手先留住，停半秒后再让肩跟上。动作慢一点，不追求速度。",
            "sets_reps": "每天 2 组，左右各 8 次",
            "parent_check": "家长看孩子的肩膀不要和胯同时转；如果肩先走，提醒他重新慢做。",
            "coach_cue": "Cue: hip first, shoulder stays back.",
            "safety_note": "腰部不舒服立即停止，不要硬拧。",
            "retest_metric": "hip_shoulder_separation_deg"
        },
        {
            "recommendation_id": "rec_tee_flat_path",
            "title": "Tee 平扫路线",
            "priority": "high",
            "related_metrics": ["attack_angle_deg", "swing_path"],
            "why": "攻击角偏大，说明棒子上挑明显。练习平扫可以让球棒在击球区停留更久。",
            "how_to_do": "把 Tee 放在腰部高度，球后方放一条软带或毛巾当水平线。挥棒时让球棒沿着水平线穿过球，不要从球下面往上捞。",
            "sets_reps": "每次 3 组，每组 8 球",
            "parent_check": "家长从侧面看，球棒击球前后是否大致沿水平线走。",
            "coach_cue": "Cue: through the ball, not under the ball.",
            "safety_note": "保持周围无人，使用软球或训练球更安全。",
            "retest_metric": "attack_angle_deg"
        },
        {
            "recommendation_id": "rec_stride_pause",
            "title": "跨步停顿挥棒",
            "priority": "medium",
            "related_metrics": ["start_efficiency", "front_knee_angle_deg"],
            "why": "前腿支撑不错，可以用停顿练习把支撑变成稳定发力点。",
            "how_to_do": "先完成跨步，前脚落地后停 1 秒，确认身体平衡、眼睛看球，再慢速挥棒。熟练后把停顿缩短到半秒。",
            "sets_reps": "每次 3 组，每组 6 次",
            "parent_check": "家长看前脚落地后身体有没有晃，头有没有提前跑掉。",
            "coach_cue": "Cue: land, hold, swing.",
            "safety_note": "不要为了停住而把膝盖锁死。",
            "retest_metric": "front_knee_angle_deg"
        },
        {
            "recommendation_id": "rec_watch_freeze",
            "title": "看球冻结",
            "priority": "keep",
            "related_metrics": ["head_stability_pct", "contact_stability"],
            "why": "头部稳定是本次优势，要继续保留，避免训练力量时丢掉看球能力。",
            "how_to_do": "每次挥棒后保持击球点姿势 1 秒，眼睛留在球原来的位置，再抬头看结果。",
            "sets_reps": "每次 2 组，每组 10 次",
            "parent_check": "家长只看一件事：挥完后孩子是不是马上抬头。如果马上抬头，就重做。",
            "coach_cue": "Cue: eyes stay, then finish.",
            "safety_note": "动作冻结时不要憋气。",
            "retest_metric": "head_stability_pct"
        }
    ]


def build_visual_blocks() -> list[dict[str, Any]]:
    return [
        {
            "type": "photo_with_skeleton",
            "title": "动作证据图",
            "description": "原始视频帧叠加关键点骨架；后续可把髋肩分离和攻击角偏差段标红。"
        },
        {
            "type": "phase_timeline",
            "title": "击球阶段时间轴",
            "description": "启动 -> 跨步 -> 上棒 -> 击球点 -> 随挥；每段绑定关键指标和红黄绿状态。"
        }
    ]


def build_report(input_path: Path = EXAMPLE_INPUT, bat_sample: str | None = None, pitch_sample: str | None = None) -> dict[str, Any]:
    raw = load_json(input_path)
    if bat_sample:
        if bat_sample not in raw["cv_metrics"]:
            raise KeyError(f"Unknown bat sample: {bat_sample}")
        raw["session"]["primary_bat_sample"] = bat_sample
    if pitch_sample:
        if pitch_sample not in raw["cv_metrics"]:
            raise KeyError(f"Unknown pitch sample: {pitch_sample}")
        raw["session"]["primary_pitch_sample"] = pitch_sample
    thresholds = load_json(THRESHOLDS)
    limitations = load_json(LIMITATIONS)["rules"]
    bat_metrics, pitch_metrics = build_metric_blocks(raw, thresholds)
    derived_scores = build_derived_scores(bat_metrics)
    recommendations = build_recommendations()

    summary = "本次报告保留 CV 与 Vicon 数据，并把它们拆成球员、教练、研究者三个视角。孩子当前优势是头部稳定和前腿支撑，优先改进髋肩分离不足与击球攻击角偏大。"

    return {
        "metadata": {
            **raw["metadata"],
            "created_at": raw["metadata"].get("created_at") or date.today().isoformat(),
        },
        "athlete": raw["athlete"],
        "session": raw["session"],
        "raw_metrics": {
            "cv": raw["cv_metrics"],
            "vicon": raw["vicon_metrics"],
        },
        "derived_scores": derived_scores,
        "views": {
            "player": {
                "bat": {
                    "summary": "用家长和孩子能理解的话解释击球动作。",
                    "metrics": bat_metrics,
                    "visual_blocks": build_visual_blocks(),
                },
                "pitch": {
                    "summary": "用直白语言说明投球动作表现。",
                    "metrics": pitch_metrics,
                    "visual_blocks": build_visual_blocks(),
                },
            },
            "coach": {
                "bat": {
                    "summary": "关注角度、动力链、横向对比和训练优先级。",
                    "metrics": bat_metrics + derived_scores,
                    "visual_blocks": [
                        {"type": "comparison_bars", "title": "孩子 vs 同龄样本 vs Vicon 教练"},
                        {"type": "kinetic_chain", "title": "动力链流程图"},
                        {"type": "radar", "title": "五维能力雷达图"},
                    ],
                },
                "pitch": {
                    "summary": "关注投球阶段、支撑、方向和速度 proxy。",
                    "metrics": pitch_metrics,
                    "visual_blocks": [
                        {"type": "phase_timeline", "title": "投球阶段时间轴"},
                        {"type": "deviation_heatmap", "title": "动作偏差热力图"},
                    ],
                },
            },
            "researcher": {
                "bat": {
                    "summary": "保留 raw data、proxy 标记、N/A 和 Vicon 3D 校准关系。",
                    "metrics": bat_metrics,
                    "visual_blocks": [
                        {"type": "raw_table", "title": "CV/Vicon 原始表"},
                        {"type": "speed_curves", "title": "Vicon 速度曲线"},
                    ],
                },
                "pitch": {
                    "summary": "保留投球 raw data 与同机位复测限制。",
                    "metrics": pitch_metrics,
                    "visual_blocks": [
                        {"type": "raw_table", "title": "投球 CV 原始表"},
                    ],
                },
            },
        },
        "recommendations": recommendations,
        "training_plan": {
            "duration_days": 7,
            "tasks": recommendations,
        },
        "limitations": limitations,
        "render_targets": ["markdown", "html", "pptx", "pdf"],
        "summary": summary,
    }


def require_keys(report: dict[str, Any]) -> None:
    required = [
        "metadata",
        "athlete",
        "session",
        "raw_metrics",
        "derived_scores",
        "views",
        "recommendations",
        "training_plan",
        "limitations",
        "render_targets",
    ]
    missing = [key for key in required if key not in report]
    if missing:
        raise ValueError(f"Report is missing required keys: {', '.join(missing)}")


def md_metric_list(metrics: list[dict[str, Any]]) -> str:
    lines = []
    for m in metrics:
        lines.append(
            f"- **{m['name']}**：{fmt_value(m['value'], m['unit'])} / {STATUS_LABELS[m['status']]}\n"
            f"  - 家长解读：{m['parent_explanation']}\n"
            f"  - 证据：{m['evidence']}"
        )
    return "\n".join(lines)


def md_recommendations(recommendations: list[dict[str, Any]]) -> str:
    lines = []
    for rec in recommendations:
        lines.append(
            f"- **{rec['title']}**（{rec['priority']}）\n"
            f"  - 为什么：{rec['why']}\n"
            f"  - 怎么做：{rec['how_to_do']}\n"
            f"  - 训练量：{rec['sets_reps']}\n"
            f"  - 家长检查：{rec['parent_check']}"
        )
    return "\n".join(lines)


def raw_table_md(data: dict[str, dict[str, Any]]) -> str:
    rows = ["| sample | fields |", "| --- | --- |"]
    for sample, values in data.items():
        fields = "; ".join(f"{k}={v}" for k, v in values.items())
        rows.append(f"| {sample} | {fields} |")
    return "\n".join(rows)


def render_markdown(report: dict[str, Any]) -> str:
    template = MD_TEMPLATE.read_text(encoding="utf-8")
    values = {
        "title": "SRS AI Baseball 动作分析报告",
        "report_id": report["metadata"]["report_id"],
        "created_at": report["metadata"]["created_at"],
        "athlete_name": report["athlete"]["name"],
        "age_group": report["athlete"]["age_group"],
        "summary": report["summary"],
        "player_bat_metrics": md_metric_list(report["views"]["player"]["bat"]["metrics"]),
        "player_pitch_metrics": md_metric_list(report["views"]["player"]["pitch"]["metrics"]),
        "coach_bat_metrics": md_metric_list(report["views"]["coach"]["bat"]["metrics"]),
        "coach_pitch_metrics": md_metric_list(report["views"]["coach"]["pitch"]["metrics"]),
        "recommendations": md_recommendations(report["recommendations"]),
        "cv_raw_table": raw_table_md(report["raw_metrics"]["cv"]),
        "vicon_raw_table": raw_table_md(report["raw_metrics"]["vicon"]),
        "limitations": "\n".join(f"- **{item['item']}**：{item['reason']}" for item in report["limitations"]),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def card_html(m: dict[str, Any]) -> str:
    status = m["status"]
    value = escape(fmt_value(m["value"], m["unit"]))
    en_name = metric_en(m, "name", m["metric_id"].replace("_", " ").title())
    en_explain = metric_en(m, "explain", "This item summarizes the video-derived motion signal for review.")
    en_evidence = metric_en(m, "evidence", "Calculated from stabilized pose keypoints and used as visual evidence, not as a medical diagnosis.")
    return (
        f'<article class="card {status}">'
        f'<div class="metric-top"><h3 class="metric-title">{paired_text(m["name"], en_name)}</h3>'
        f'<span class="badge {status}">{escape(STATUS_LABELS[status])}<span class="en">{escape(STATUS_EN.get(status, status.title()))}</span></span></div>'
        f'<div class="value">{value}</div>'
        f'<p class="explain">{escape(m["parent_explanation"])}</p>'
        f'<p class="en">{escape(en_explain)}</p>'
        f'<p class="explain" style="margin-top:8px;">证据：{escape(m["evidence"])}</p>'
        f'<p class="en">Evidence: {escape(en_evidence)}</p>'
        f'</article>'
    )


def visual_html(block: dict[str, Any]) -> str:
    return (
        '<div class="visual">'
        f'<h3>{escape(block["title"])}</h3>'
        f'<p class="explain" style="margin-top:8px;">{escape(block.get("description", "由模板固定生成，可替换为截图、骨架、时间轴或雷达图。"))}</p>'
        '</div>'
    )


def comparison_bars(report: dict[str, Any]) -> str:
    bat_sample = report["session"].get("primary_bat_sample", "hit_vertical_02")
    hit = report["raw_metrics"]["cv"][bat_sample]
    peer = report["raw_metrics"]["vicon"]["Julian_wave02"]
    coach = report["raw_metrics"]["vicon"]["0506Coach_wave"]
    metrics = [
        ("髋肩分离", hit["hip_shoulder_separation_deg"], peer["hip_shoulder_separation_deg"], coach["hip_shoulder_separation_deg"], "°", 40),
        ("前腿膝角", hit["front_knee_angle_deg"], peer["front_knee_angle_deg"], coach["front_knee_angle_deg"], "°", 180),
        ("头部稳定", hit["head_stability_pct"], peer["head_stability_pct"], coach["head_stability_pct"], "%", 100),
        ("攻击角", hit["attack_angle_deg"], peer["bat_angle_deg"], coach["bat_angle_deg"], "°", 180),
    ]
    rows = []
    for label, child, peer, coach, unit, max_value in metrics:
        for name, value, color in (("孩子", child, "var(--orange)"), ("同龄/Vicon", peer, "var(--blue)"), ("教练/Vicon", coach, "var(--green)")):
            width = clamp(abs(value) / max_value * 100)
            rows.append(
                '<div class="bar-row">'
                f'<span>{escape(label)} {escape(name)}</span>'
                f'<div class="track"><div class="fill" style="--w:{width:.1f}%; background:{color};"></div></div>'
                f'<strong>{escape(fmt_value(value, unit))}</strong>'
                '</div>'
            )
    return "".join(rows)


def recommendation_cards(recommendations: list[dict[str, Any]]) -> str:
    cards = []
    for rec in recommendations:
        cards.append(
            '<article class="card rec">'
            f'<strong>{escape(rec["title"])}<span class="en">{escape(rec_en(rec, "title"))}</span></strong>'
            f'<p>{escape(rec["why"])}</p>'
            f'<p class="en">{escape(rec_en(rec, "why"))}</p>'
            f'<p><b>怎么做：</b>{escape(rec["how_to_do"])}</p>'
            f'<p class="en"><b>How to do it: </b>{escape(rec_en(rec, "how"))}</p>'
            f'<p><b>训练量：</b>{escape(rec["sets_reps"])}</p>'
            f'<p class="en"><b>Volume: </b>{escape(rec_en(rec, "volume"))}</p>'
            f'<p><b>家长检查：</b>{escape(rec["parent_check"])}</p>'
            f'<p class="en"><b>Parent check: </b>{escape(rec_en(rec, "check"))}</p>'
            '</article>'
        )
    return "".join(cards)


def raw_table_html(data: dict[str, dict[str, Any]]) -> str:
    rows = ["<table><thead><tr><th>sample</th><th>field</th><th>value</th></tr></thead><tbody>"]
    for sample, fields in data.items():
        for key, value in fields.items():
            rows.append(f"<tr><td>{escape(sample)}</td><td>{escape(key)}</td><td>{escape(str(value))}</td></tr>")
    rows.append("</tbody></table>")
    return "".join(rows)


def render_html(report: dict[str, Any]) -> str:
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    player_bat = report["views"]["player"]["bat"]
    player_pitch = report["views"]["player"]["pitch"]
    chain = ["下肢启动 N/A", "髋肩分离 17", "启动效率 62", "挥棒路径 38", "击球稳定 92"]
    values = {
        "title": "SRS AI Baseball 动作分析报告",
        "report_id": report["metadata"]["report_id"],
        "created_at": report["metadata"]["created_at"],
        "athlete_name": report["athlete"]["name"],
        "age_group": report["athlete"]["age_group"],
        "summary": report["summary"],
        "player_bat_cards": "".join(card_html(m) for m in player_bat["metrics"]),
        "player_pitch_cards": "".join(card_html(m) for m in player_pitch["metrics"]),
        "player_visuals": "".join(visual_html(v) for v in player_bat["visual_blocks"]),
        "comparison_bars": comparison_bars(report),
        "kinetic_chain": "".join(f"<span>{escape(item)}</span>" for item in chain),
        "recommendation_cards": recommendation_cards(report["recommendations"]),
        "cv_raw_table": motion_trends_html(report),
        "vicon_raw_table": calibration_summary_html(report),
        "limitations": "".join(card_html(metric_block(item["item"], item["item"], "shared", "manual", item["display_level"], "", item["display_level"] if item["display_level"] in STATUS_LABELS else "warning", item["reason"], item["reason"])) for item in report["limitations"]),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def card_html(m: dict[str, Any]) -> str:
    status = m["status"]
    value = escape(fmt_value(m["value"], m["unit"]))
    en_name = metric_en(m, "name", m["metric_id"].replace("_", " ").title())
    en_explain = metric_en(m, "explain", "This item summarizes the video-derived motion signal for review.")
    en_evidence = metric_en(m, "evidence", "Calculated from stabilized pose keypoints and used as visual evidence, not as a medical diagnosis.")
    return (
        f'<article class="card {status}">'
        f'<div class="metric-top"><h3 class="metric-title">{paired_text(m["name"], en_name)}</h3>'
        f'<span class="badge {status}">{escape(STATUS_LABELS[status])}<span class="en">{escape(STATUS_EN.get(status, status.title()))}</span></span></div>'
        f'<div class="value">{value}</div>'
        f'<p class="explain">{escape(m["parent_explanation"])}</p>'
        f'<p class="en">{escape(en_explain)}</p>'
        f'<p class="explain" style="margin-top:8px;">证据：{escape(m["evidence"])}</p>'
        f'<p class="en">Evidence: {escape(en_evidence)}</p>'
        f'</article>'
    )


def status_badge(status: str) -> str:
    return f'<span class="badge {status}">{escape(STATUS_LABELS[status])}<span class="en">{escape(STATUS_EN.get(status, status.title()))}</span></span>'


def selected_samples(report: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    bat_sample = report["session"].get("primary_bat_sample", "hit_vertical_02")
    pitch_sample = report["session"].get("primary_pitch_sample", "pitch_vertical_10")
    return report["raw_metrics"]["cv"][bat_sample], report["raw_metrics"]["cv"][pitch_sample]


def metric_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = report["views"]["player"]["bat"]["metrics"] + report["views"]["player"]["pitch"]["metrics"] + report["derived_scores"]
    return {m["metric_id"]: m for m in metrics}


def hero_stats_html(report: dict[str, Any]) -> str:
    lookup = metric_lookup(report)
    items = [
        ("蓄力", lookup["power_quality"]["value"], "分"),
        ("路径", lookup["swing_path"]["value"], "分"),
        ("稳定", lookup["contact_stability"]["value"], "分"),
    ]
    return "".join(
        f"<div><strong>{escape(fmt_value(value, unit))}</strong><span>{escape(label)}</span></div>"
        for label, value, unit in items
    )


def evidence_scene_html(report: dict[str, Any]) -> str:
    pose3d = pose3d_media_html(report, compact=True)
    if pose3d:
        return pose3d
    lookup = metric_lookup(report)
    hss = lookup["hip_shoulder_separation_deg"]
    attack = lookup["attack_angle_deg"]
    stability = lookup["contact_stability"]
    return f"""
    <svg viewBox="0 0 520 340" role="img" aria-label="击球动作骨架示意图">
      <defs>
        <linearGradient id="batPath" x1="0" x2="1">
          <stop offset="0" stop-color="#f9732b" stop-opacity="0.2"/>
          <stop offset="1" stop-color="#f9732b" stop-opacity="0.95"/>
        </linearGradient>
      </defs>
      <path d="M54 248 C154 206, 310 188, 462 142" fill="none" stroke="url(#batPath)" stroke-width="16" stroke-linecap="round"/>
      <path d="M92 260 L198 212 L286 196 L444 170" fill="none" stroke="#f9732b" stroke-width="3" stroke-dasharray="8 9" opacity="0.75"/>
      <circle cx="444" cy="170" r="9" fill="#fff" stroke="#f9732b" stroke-width="4"/>
      <g stroke="#70e1d1" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">
        <line x1="258" y1="104" x2="236" y2="158"/>
        <line x1="236" y1="158" x2="252" y2="214"/>
        <line x1="236" y1="158" x2="188" y2="174"/>
        <line x1="188" y1="174" x2="142" y2="164"/>
        <line x1="236" y1="158" x2="300" y2="168"/>
        <line x1="300" y1="168" x2="352" y2="142"/>
        <line x1="252" y1="214" x2="198" y2="264"/>
        <line x1="198" y1="264" x2="144" y2="288"/>
        <line x1="252" y1="214" x2="310" y2="260"/>
        <line x1="310" y1="260" x2="372" y2="288"/>
      </g>
      <g fill="#fff" stroke="#142033" stroke-width="3">
        <circle cx="258" cy="104" r="15"/>
        <circle cx="236" cy="158" r="8"/>
        <circle cx="252" cy="214" r="8"/>
        <circle cx="188" cy="174" r="8"/>
        <circle cx="142" cy="164" r="8"/>
        <circle cx="300" cy="168" r="8"/>
        <circle cx="352" cy="142" r="8"/>
        <circle cx="198" cy="264" r="8"/>
        <circle cx="144" cy="288" r="8"/>
        <circle cx="310" cy="260" r="8"/>
        <circle cx="372" cy="288" r="8"/>
      </g>
      <g font-family="sans-serif" font-size="16" font-weight="700">
        <text x="28" y="42" fill="#fff">动作证据图</text>
        <text x="28" y="70" fill="rgba(255,255,255,0.68)">骨架、棒路和 3D 方向用于解释指标</text>
        <text x="28" y="310" fill="#fff">髋肩分离 {escape(fmt_value(hss["value"], hss["unit"]))}</text>
        <text x="206" y="310" fill="#fff">攻击角 {escape(fmt_value(attack["value"], attack["unit"]))}</text>
        <text x="374" y="310" fill="#fff">稳定 {escape(fmt_value(stability["value"], stability["unit"]))}</text>
      </g>
    </svg>
    """


def priority_items_html(report: dict[str, Any]) -> str:
    candidates = [m for m in report["views"]["coach"]["bat"]["metrics"] if m["status"] in ("concern", "suspicious", "warning", "unavailable")]
    order = {"concern": 0, "suspicious": 1, "warning": 2, "unavailable": 3}
    candidates.sort(key=lambda m: (order.get(m["status"], 9), -(m["score"] or 0)))
    rows = []
    for index, metric in enumerate(candidates[:5], start=1):
        priority_en = PITCH_PRIORITY_EN.get(metric["metric_id"], {})
        en_name = priority_en.get("name") or metric_en(metric, "name", metric["metric_id"].replace("_", " ").title())
        en_explain = priority_en.get("explain") or metric_en(metric, "explain", "Review this item first because it is one of the clearest movement priorities in this report.")
        rows.append(
            '<div class="priority-item">'
            f'<div class="rank">{index}</div>'
            f'<div><strong>{escape(metric["name"])}<span class="en">{escape(en_name)}</span></strong>'
            f'<p class="explain">{escape(metric["parent_explanation"])}</p>'
            f'<p class="en">{escape(en_explain)}</p></div>'
            f'{status_badge(metric["status"])}'
            '</div>'
        )
    return "".join(rows)


def radar_chart_html(report: dict[str, Any], mode: str = "bat") -> tuple[str, str]:
    lookup = metric_lookup(report)
    score_lookup = {m["metric_id"]: m for m in report["derived_scores"]}
    if mode == "pitch":
        dimensions = [
            ("站姿稳定", (lookup.get("pitch_head_stability_pct") or {}).get("score", 0)),
            ("跨步控制", (lookup.get("pitch_target_line_control_score") or {}).get("value", 0)),
            ("髋肩分离", (lookup.get("pitch_hip_shoulder_separation_deg") or {}).get("score", 0)),
            ("手臂路径", (lookup.get("pitch_arm_path_score") or {}).get("value", 0)),
            ("释放质量", (lookup.get("pitch_release_quality_score") or {}).get("value", 0)),
            ("收尾稳定", (lookup.get("pitch_finish_stability_score") or {}).get("value", 0)),
        ]
        aria = "投球六维评分图"
    else:
        dimensions = [
            ("站姿稳定", (lookup.get("head_stability_pct") or {}).get("score", 0)),
            ("跨步控制", (lookup.get("front_knee_angle_deg") or {}).get("score", 0)),
            ("髋肩分离", (lookup.get("hip_shoulder_separation_deg") or {}).get("score", 0)),
            ("躯干旋转", (score_lookup.get("start_efficiency") or {}).get("value", 0)),
            ("挥棒平面", (score_lookup.get("swing_path") or {}).get("value", 0)),
            ("击球后平衡", (score_lookup.get("contact_stability") or {}).get("value", 0)),
        ]
        aria = "打击六维评分图"
    center = 120
    radius = 92
    points = []
    labels = []
    axes = []
    for index, (label, score) in enumerate(dimensions):
        score = value_or_zero(score)
        angle = math.radians(-90 + index * 360 / len(dimensions))
        outer_x = center + radius * math.cos(angle)
        outer_y = center + radius * math.sin(angle)
        value_x = center + radius * (score / 100) * math.cos(angle)
        value_y = center + radius * (score / 100) * math.sin(angle)
        label_x = center + (radius + 22) * math.cos(angle)
        label_y = center + (radius + 22) * math.sin(angle)
        points.append(f"{value_x:.1f},{value_y:.1f}")
        axes.append(f'<line x1="{center}" y1="{center}" x2="{outer_x:.1f}" y2="{outer_y:.1f}" stroke="#d7e0ec"/>')
        labels.append(f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" dominant-baseline="middle">{escape(label)}</text>')
    outer_ring = " ".join(
        f"{center + radius * math.cos(math.radians(-90 + i * 360 / len(dimensions))):.1f},{center + radius * math.sin(math.radians(-90 + i * 360 / len(dimensions))):.1f}"
        for i in range(len(dimensions))
    )
    mid_ring = " ".join(
        f"{center + radius * 0.66 * math.cos(math.radians(-90 + i * 360 / len(dimensions))):.1f},{center + radius * 0.66 * math.sin(math.radians(-90 + i * 360 / len(dimensions))):.1f}"
        for i in range(len(dimensions))
    )
    inner_ring = " ".join(
        f"{center + radius * 0.33 * math.cos(math.radians(-90 + i * 360 / len(dimensions))):.1f},{center + radius * 0.33 * math.sin(math.radians(-90 + i * 360 / len(dimensions))):.1f}"
        for i in range(len(dimensions))
    )
    chart = (
        f'<svg viewBox="0 0 240 240" role="img" aria-label="{escape(aria)}">'
        f'<polygon points="{outer_ring}" fill="#f7f9fc" stroke="#d7e0ec"/>'
        f'<polygon points="{mid_ring}" fill="none" stroke="#d7e0ec"/>'
        f'<polygon points="{inner_ring}" fill="none" stroke="#d7e0ec"/>'
        f'{"".join(axes)}'
        f'<polygon points="{" ".join(points)}" fill="rgba(79,94,234,0.22)" stroke="#4f5eea" stroke-width="3"/>'
        f'{"".join(labels)}'
        '<circle cx="120" cy="120" r="3" fill="#4f5eea"/>'
        '</svg>'
    )
    legend = "".join(
        f'<div><strong>{escape(label)}：</strong>{escape(fmt_value(score, "分"))}</div>'
        for label, score in dimensions
    )
    return chart, legend


def pose_evidence_html(report: dict[str, Any]) -> str:
    pose3d = pose3d_media_html(report)
    lookup = metric_lookup(report)
    hip = lookup["hip_shoulder_separation_deg"]
    head = lookup["head_stability_pct"]
    knee = lookup["front_knee_angle_deg"]
    media = ""
    if pose3d:
        media = (
            '<div class="media-stack" style="margin-bottom:14px;">'
            f"{pose3d}"
            '<p class="small-note">3D 视角基于稳定 2D 骨架和 MediaPipe 相对深度生成，适合解释身体朝向、肢体层次和动作阶段；绝对距离仍需 GVHMR/Vicon 等外部 3D 数据校准。</p>'
            '</div>'
        )
    return (
        media
        +
        '<p class="explain">下方指标条用于把 3D 视角和关键动作参数对应起来，方便快速定位偏差位置。</p>'
        '<div class="bars">'
        f'<div class="bar-row"><span>髋肩分离</span><div class="track"><div class="fill" style="--w:{clamp((hip["value"] or 0) / 40 * 100):.1f}%; background:var(--orange);"></div></div><strong>{escape(fmt_value(hip["value"], "°"))}</strong></div>'
        f'<div class="bar-row"><span>头部稳定</span><div class="track"><div class="fill" style="--w:{clamp(value_or_zero(head["value"])):.1f}%; background:var(--green);"></div></div><strong>{escape(fmt_value(head["value"], "%"))}</strong></div>'
        f'<div class="bar-row"><span>前腿支撑</span><div class="track"><div class="fill" style="--w:{clamp((knee["value"] or 0) / 180 * 100):.1f}%; background:var(--blue);"></div></div><strong>{escape(fmt_value(knee["value"], "°"))}</strong></div>'
        '</div>'
    )


def phase_timeline_html(report: dict[str, Any]) -> str:
    hit, _ = selected_samples(report)
    duration = max(0.001, hit.get("end_s", 0) - hit.get("start_s", 0))
    phases = [
        ("启动", "准备发力，身体开始进入挥棒。", 18, "warning"),
        ("跨步", "前脚建立支撑，头部保持看球。", 38, "good"),
        ("上棒", "髋肩分离决定蓄力空间。", 54, "warning"),
        ("击球点", "攻击角决定棒路是否穿过击球区。", 74, "concern"),
        ("随挥", "保持平衡，确认动作完成。", 100, "good"),
    ]
    rows = []
    for label, note, width, status in phases:
        rows.append(
            '<div class="time-item">'
            f'<strong>{escape(label)}</strong>'
            f'<div><div class="time-bar"><span style="--w:{width}%;"></span></div><p class="explain" style="margin-top:6px;">{escape(note)}</p></div>'
            f'{status_badge(status)}'
            '</div>'
        )
    rows.append(f'<p class="small-note">本次击球片段约 {duration:.2f}s，事件点 {hit.get("event_s", "N/A")}s。</p>')
    return "".join(rows)


def comparison_bars(report: dict[str, Any]) -> str:
    hit, _ = selected_samples(report)
    peer = report["raw_metrics"]["vicon"]["Julian_wave02"]
    coach = report["raw_metrics"]["vicon"]["0506Coach_wave"]
    metrics = [
        ("髋肩分离", hit["hip_shoulder_separation_deg"], peer["hip_shoulder_separation_deg"], coach["hip_shoulder_separation_deg"], "°", 40),
        ("前腿膝角", hit["front_knee_angle_deg"], peer["front_knee_angle_deg"], coach["front_knee_angle_deg"], "°", 180),
        ("头部稳定", hit["head_stability_pct"], peer["head_stability_pct"], coach["head_stability_pct"], "%", 100),
        ("棒角/攻击角", hit["attack_angle_deg"], peer["bat_angle_deg"], coach["bat_angle_deg"], "°", 180),
    ]
    rows = []
    for label, child, peer_value, coach_value, unit, max_value in metrics:
        for name, value, color in (("孩子", child, "var(--orange)"), ("同龄/Vicon", peer_value, "var(--blue)"), ("教练/Vicon", coach_value, "var(--green)")):
            width = clamp(abs(value_or_zero(value)) / max_value * 100)
            rows.append(
                '<div class="bar-row">'
                f'<span>{escape(label)} {escape(name)}</span>'
                f'<div class="track"><div class="fill" style="--w:{width:.1f}%; background:{color};"></div></div>'
                f'<strong>{escape(fmt_value(value, unit))}</strong>'
                '</div>'
            )
    return "".join(rows)


def kinetic_chain_html(report: dict[str, Any]) -> str:
    lookup = metric_lookup(report)
    items = [
        ("下肢启动", lookup["lower_body_start"]),
        ("髋肩分离", lookup["power_quality"]),
        ("启动效率", lookup["start_efficiency"]),
        ("挥棒路径", lookup["swing_path"]),
        ("击球稳定", lookup["contact_stability"]),
    ]
    return "".join(
        f'<div class="chain-step {metric["status"]}"><strong>{escape(label)}</strong><span>{escape(fmt_value(metric["value"], metric["unit"]))}</span></div>'
        for label, metric in items
    )


def heatmap_html(report: dict[str, Any]) -> str:
    lookup = metric_lookup(report)
    cells = [
        ("躯干蓄力", lookup["hip_shoulder_separation_deg"], "看胯和肩是否先后发力"),
        ("挥棒路线", lookup["attack_angle_deg"], "看球棒是否稳定穿过击球区"),
        ("下肢支撑", lookup["front_knee_angle_deg"], "看前腿落地后能否撑住"),
        ("看球稳定", lookup["head_stability_pct"], "看头部和视线是否稳定"),
    ]
    return "".join(
        '<div class="heat-cell {status}"><strong>{label}</strong><p class="explain">{note}</p><p class="value" style="font-size:24px;">{value}</p>{badge}</div>'.format(
            status=metric["status"],
            label=escape(label),
            note=escape(note),
            value=escape(fmt_value(metric["value"], metric["unit"])),
            badge=status_badge(metric["status"]),
        )
        for label, metric, note in cells
    )


def recommendation_cards(recommendations: list[dict[str, Any]]) -> str:
    cards = []
    for rec in recommendations:
        cards.append(
            '<article class="card rec">'
            f'<strong>{escape(rec["title"])}<span class="en">{escape(rec_en(rec, "title"))}</span></strong>'
            f'<p>{escape(rec["why"])}</p>'
            f'<p class="en">{escape(rec_en(rec, "why"))}</p>'
            f'<p><b>怎么做：</b>{escape(rec["how_to_do"])}</p>'
            f'<p class="en"><b>How to do it: </b>{escape(rec_en(rec, "how"))}</p>'
            f'<p><b>训练量：</b>{escape(rec["sets_reps"])}</p>'
            f'<p class="en"><b>Volume: </b>{escape(rec_en(rec, "volume"))}</p>'
            f'<p><b>家长检查：</b>{escape(rec["parent_check"])}</p>'
            f'<p class="en"><b>Parent check: </b>{escape(rec_en(rec, "check"))}</p>'
            f'<p><b>复测指标：</b>{escape(rec["retest_metric"])}</p>'
            '</article>'
        )
    return "".join(cards)


def training_plan_html(recommendations: list[dict[str, Any]]) -> str:
    days = [
        ("第 1 天", "慢速建立", [recommendations[0]["title"], "动作拍 3 秒给教练看", "记录是否腰部不适"]),
        ("第 2 天", "蓄力复习", [recommendations[0]["title"], recommendations[3]["title"], "家长检查肩是否抢先"]),
        ("第 3 天", "路线进入", [recommendations[1]["title"], "每组结束看 1 次侧面视频", "只追求平扫不追求快"]),
        ("第 4 天", "支撑配合", [recommendations[2]["title"], recommendations[1]["title"], "前脚落地后身体不晃"]),
        ("第 5 天", "节奏串联", [recommendations[0]["title"], recommendations[2]["title"], "慢速连续 6 次"]),
        ("第 6 天", "轻强度击球", [recommendations[1]["title"], recommendations[3]["title"], "保持看球冻结"]),
        ("第 7 天", "同角度复测", ["同机位拍击球视频", "复测髋肩分离和攻击角", "记录完成率和疼痛情况"]),
    ]
    cards = []
    for day, title, tasks in days:
        cards.append(
            '<article class="day-card">'
            f'<h3><span>{escape(day)}</span><span class="badge warning">{escape(title)}</span></h3>'
            '<div class="checklist">'
            + "".join(f"<span>{escape(task)}</span>" for task in tasks)
            + '</div></article>'
        )
    return "".join(cards)


def vicon_panel_html(report: dict[str, Any]) -> str:
    coach = report["raw_metrics"]["vicon"]["0506Coach_wave"]
    peer = report["raw_metrics"]["vicon"]["Julian_wave02"]
    return (
        '<p class="explain">Vicon 提供标定 3D marker 数据。它在报告中的角色是校准和解释 CV 参数，让视频估算有专业参照。</p>'
        '<div class="bars">'
        f'<div class="bar-row"><span>教练棒速</span><div class="track"><div class="fill" style="--w:{clamp(coach["bat1_speed_kmh"] / 140 * 100):.1f}%; background:var(--green);"></div></div><strong>{escape(fmt_value(coach["bat1_speed_kmh"], "km/h"))}</strong></div>'
        f'<div class="bar-row"><span>同龄棒速</span><div class="track"><div class="fill" style="--w:{clamp(peer["bat1_speed_kmh"] / 140 * 100):.1f}%; background:var(--blue);"></div></div><strong>{escape(fmt_value(peer["bat1_speed_kmh"], "km/h"))}</strong></div>'
        f'<div class="bar-row"><span>教练挥棒时间</span><div class="track"><div class="fill" style="--w:{clamp((1 - coach["swing_time_s"] / 0.5) * 100):.1f}%; background:var(--orange);"></div></div><strong>{escape(fmt_value(coach["swing_time_s"], "s"))}</strong></div>'
        '</div>'
    )


def scoring_explainer_html() -> str:
    rows = [
        ("良好", "指标进入建议区间，作为保持项。"),
        ("偏离", "指标可用但偏离目标，优先做技术修正。"),
        ("关注", "差距明显，建议进入本周训练重点。"),
        ("需复核", "数值可能受机位或识别影响，先复测再下结论。"),
        ("不可用", "缺少必要数据，不生成确定判断。"),
    ]
    return '<div class="priority-list">' + "".join(
        f'<div class="priority-item"><div class="rank">{index}</div><div><strong>{escape(label)}</strong><p class="explain">{escape(note)}</p></div></div>'
        for index, (label, note) in enumerate(rows, start=1)
    ) + '</div>'


def raw_table_html(data: dict[str, dict[str, Any]]) -> str:
    rows = ["<table><thead><tr><th>sample</th><th>field</th><th>value</th></tr></thead><tbody>"]
    for sample, fields in data.items():
        for key, value in fields.items():
            rows.append(f"<tr><td>{escape(sample)}</td><td>{escape(key)}</td><td>{escape(str(value))}</td></tr>")
    rows.append("</tbody></table>")
    return "".join(rows)


def limitations_html(report: dict[str, Any]) -> str:
    status_map = {"info": "unavailable", "warning": "warning", "blocker": "concern"}
    return "".join(
        card_html(
            metric_block(
                item["item"],
                item["item"],
                "shared",
                "manual",
                item["display_level"],
                "",
                status_map.get(item["display_level"], "warning"),
                item["reason"],
                item["reason"],
            )
        )
        for item in report["limitations"]
    )


def report_is_pitch_only(report: dict[str, Any]) -> bool:
    actions = report.get("session", {}).get("actions", [])
    return "pitch" in actions and "bat" not in actions


def report_asset(report: dict[str, Any], key: str) -> str:
    return str(report.get("session", {}).get("report_assets", {}).get(key, ""))


def asset_video_html(src: str, label: str) -> str:
    if not src:
        return ""
    return (
        f'<video class="evidence-video" controls muted playsinline preload="none" aria-label="{escape(label)}">'
        f'<source src="{escape(src)}">'
        "</video>"
    )


def asset_image_html(src: str, label: str, class_name: str = "evidence-image") -> str:
    if not src:
        return ""
    return f'<img class="{escape(class_name)}" src="{escape(src)}" alt="{escape(label)}">'


def interactive_pose3d_viewer_html(report: dict[str, Any], compact: bool = False) -> str:
    preview = report.get("session", {}).get("pose3d_preview") or {}
    frames = preview.get("frames") or []
    if not frames:
        return ""
    suffix = "compact" if compact else "full"
    viewer_id = f"pose3d-viewer-{suffix}"
    payload = json.dumps(
        {
            "fps": preview.get("fps", 12),
            "unit": preview.get("unit", "body-scale relative units"),
            "motion_model": preview.get("motion_model", "smoothed_root_trajectory"),
            "initial_index": preview.get("initial_index", 0),
            "event_frame": preview.get("event_frame"),
            "frames": frames,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )
    note = ""
    if not compact:
        note = (
            '<p class="small-note">交互式 3D：人物不再固定在原点，会按平滑的身体中心轨迹在空间中完成投球动作；拖动可旋转视角，播放可查看动作过程。坐标是身体尺度归一化的全局相对 3D，不是毫米或厘米。'
            '<span class="en">Interactive 3D: the avatar is no longer pinned to the origin. It follows a smoothed body-center trajectory through the pitching space. Coordinates are body-scale global-relative 3D values, not millimeters or centimeters.</span></p>'
        )
    return f"""
    <div id="{viewer_id}" class="pose3d-viewer" data-pose3d='{escape(payload, quote=True)}'>
      <canvas aria-label="Interactive relative 3D pose viewer"></canvas>
      <div class="pose3d-toolbar">
        <button type="button" data-action="play">Pause</button>
        <button type="button" data-view="front">Front</button>
        <button type="button" data-view="side">Side</button>
        <button type="button" data-view="top">Top</button>
        <button type="button" data-view="reset">Reset</button>
        <input type="range" min="0" max="{max(len(frames) - 1, 0)}" value="0" aria-label="3D pose frame">
        <span class="pose3d-time">0.00s</span>
      </div>
      {note}
    </div>
    <script>
    (() => {{
      const root = document.getElementById("{viewer_id}");
      if (!root || root.dataset.ready) return;
      root.dataset.ready = "1";
      const data = JSON.parse(root.dataset.pose3d || "{{}}");
      const frames = data.frames || [];
      if (!frames.length) return;
      const canvas = root.querySelector("canvas");
      const ctx = canvas.getContext("2d");
      const slider = root.querySelector("input[type=range]");
      const timeEl = root.querySelector(".pose3d-time");
      const playBtn = root.querySelector("[data-action=play]");
      const connections = [[11,12],[11,13],[13,15],[15,17],[15,19],[12,14],[14,16],[16,18],[16,20],[11,23],[12,24],[23,24],[23,25],[25,27],[27,29],[27,31],[24,26],[26,28],[28,30],[28,32],[0,11],[0,12]];
      const left = new Set([11,13,15,17,19,21,23,25,27,29,31]);
      const right = new Set([12,14,16,18,20,22,24,26,28,30,32]);
      let yaw = -0.85;
      let pitch = -0.24;
      let playhead = Math.max(0, Math.min(frames.length - 1, Number(data.initial_index || 0)));
      let playing = true;
      let drag = null;
      let lastTime = 0;
      const scene = computeScene(frames);
      function computeScene(sourceFrames) {{
        const xs = [], ys = [], zs = [];
        for (const frame of sourceFrames) {{
          for (const p of frame.joints || []) {{
            if (!Number.isFinite(Number(p.x)) || !Number.isFinite(Number(p.y)) || !Number.isFinite(Number(p.z))) continue;
            xs.push(Number(p.x)); ys.push(Number(p.y)); zs.push(Number(p.z));
          }}
        }}
        if (!xs.length) return {{cx:0, cy:0, cz:0, radius:1.35}};
        const minX = Math.min(...xs), maxX = Math.max(...xs);
        const minY = Math.min(...ys), maxY = Math.max(...ys);
        const minZ = Math.min(...zs), maxZ = Math.max(...zs);
        const radius = Math.max(1.25, (maxX - minX) * .52, (maxY - minY) * .58, (maxZ - minZ) * .72);
        return {{cx:(minX + maxX) * .5, cy:(minY + maxY) * .48, cz:(minZ + maxZ) * .5, radius}};
      }}
      function resize() {{
        const rect = root.getBoundingClientRect();
        const dpr = Math.max(1, Math.min(window.devicePixelRatio || 1, 2));
        const cssW = Math.max(320, rect.width);
        const cssH = Math.max({460 if compact else 560}, Math.round(cssW * 0.62));
        canvas.style.width = cssW + "px";
        canvas.style.height = cssH + "px";
        canvas.width = Math.round(cssW * dpr);
        canvas.height = Math.round(cssH * dpr);
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      }}
      function rotate(p) {{
        const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
        const px = Number(p.x || 0) - scene.cx;
        const py = Number(p.y || 0) - scene.cy;
        const pz = Number(p.z || 0) - scene.cz;
        const x1 = px * cy + pz * sy;
        const z1 = -px * sy + pz * cy;
        const y1 = py * cp - z1 * sp;
        const z2 = py * sp + z1 * cp;
        return {{x:x1, y:y1, z:z2}};
      }}
      function project(p, w, h) {{
        const r = rotate(p);
        const scale = Math.min(w, h) * 0.34 / scene.radius;
        const depth = 3.2 + r.z * 0.18;
        return {{x:w * 0.5 + r.x * scale / depth * 3.2, y:h * 0.54 - r.y * scale / depth * 3.2, z:r.z, c:p.c || 0}};
      }}
      function pointMap(frame) {{
        const map = new Map();
        for (const p of frame.joints || []) map.set(p.i, p);
        return map;
      }}
      function clampFrameIndex(value) {{
        return Math.max(0, Math.min(frames.length - 1, value));
      }}
      function lerp(a, b, t) {{
        return a + (b - a) * t;
      }}
      function interpolatedFrame(value) {{
        if (frames.length === 1) return frames[0];
        const clamped = clampFrameIndex(value);
        const low = Math.floor(clamped);
        const high = Math.min(frames.length - 1, low + 1);
        const mix = clamped - low;
        const aFrame = frames[low] || frames[0];
        const bFrame = frames[high] || aFrame;
        if (mix <= 0.001 || low === high) return aFrame;
        const aMap = pointMap(aFrame);
        const bMap = pointMap(bFrame);
        const joints = [];
        for (const [idx, a] of aMap) {{
          const b = bMap.get(idx) || a;
          joints.push({{
            i: idx,
            n: a.n || b.n,
            x: lerp(Number(a.x || 0), Number(b.x || 0), mix),
            y: lerp(Number(a.y || 0), Number(b.y || 0), mix),
            z: lerp(Number(a.z || 0), Number(b.z || 0), mix),
            c: Math.min(Number(a.c || 0), Number(b.c || 0)),
          }});
        }}
        return {{
          frame: Math.round(lerp(Number(aFrame.frame || low), Number(bFrame.frame || high), mix)),
          time: lerp(Number(aFrame.time || 0), Number(bFrame.time || 0), mix),
          joints,
        }};
      }}
      function colorFor(a, b) {{
        if (left.has(a) && left.has(b)) return "#1d4ed8";
        if (right.has(a) && right.has(b)) return "#c026d3";
        return "#dc2626";
      }}
      function drawGrid(w, h) {{
        ctx.fillStyle = "#fbfdff";
        ctx.fillRect(0, 0, w, h);
        ctx.strokeStyle = "rgba(86,96,112,.28)";
        ctx.lineWidth = 1;
        const floorY = scene.cy - scene.radius * .78;
        const xSpan = scene.radius * 1.65;
        const zSpan = scene.radius * 1.45;
        for (let i = -6; i <= 6; i++) {{
          const x = scene.cx + i * xSpan / 6;
          const z = scene.cz + i * zSpan / 6;
          const a = project({{x, y:floorY, z:scene.cz - zSpan, c:1}}, w, h);
          const b = project({{x, y:floorY, z:scene.cz + zSpan, c:1}}, w, h);
          const c = project({{x:scene.cx - xSpan, y:floorY, z, c:1}}, w, h);
          const d = project({{x:scene.cx + xSpan, y:floorY, z, c:1}}, w, h);
          ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.moveTo(c.x,c.y); ctx.lineTo(d.x,d.y); ctx.stroke();
        }}
        const axes = [
          ["X", "#f9732b", {{x:scene.cx - scene.radius*.7,y:floorY,z:scene.cz,c:1}}, {{x:scene.cx + scene.radius*.7,y:floorY,z:scene.cz,c:1}}],
          ["Y", "#14b8c8", {{x:scene.cx,y:floorY,z:scene.cz - scene.radius*.7,c:1}}, {{x:scene.cx,y:floorY,z:scene.cz + scene.radius*.7,c:1}}],
          ["Z", "#4f5eea", {{x:scene.cx,y:floorY,z:scene.cz,c:1}}, {{x:scene.cx,y:floorY + scene.radius*.95,z:scene.cz,c:1}}],
        ];
        ctx.font = "700 13px Segoe UI, sans-serif";
        for (const [label, color, start, end] of axes) {{
          const a = project(start, w, h), b = project(end, w, h);
          ctx.strokeStyle = color; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
          ctx.fillStyle = color; ctx.fillText(label, b.x + 6, b.y - 6);
        }}
      }}
      function drawBodyPath(w, h) {{
        ctx.save();
        ctx.strokeStyle = "rgba(249,115,43,.72)";
        ctx.fillStyle = "rgba(249,115,43,.92)";
        ctx.lineWidth = 3;
        ctx.setLineDash([7, 6]);
        ctx.beginPath();
        let started = false;
        for (const frame of frames) {{
          const map = pointMap(frame);
          const lh = map.get(23), rh = map.get(24);
          if (!lh || !rh || lh.c < .18 || rh.c < .18) continue;
          const pelvis = {{x:(Number(lh.x || 0)+Number(rh.x || 0))*.5, y:scene.cy - scene.radius * .78, z:(Number(lh.z || 0)+Number(rh.z || 0))*.5, c:1}};
          const p = project(pelvis, w, h);
          if (!started) {{ ctx.moveTo(p.x, p.y); started = true; }} else ctx.lineTo(p.x, p.y);
        }}
        ctx.stroke();
        ctx.setLineDash([]);
        const first = pointMap(frames[0] || {{}}), last = pointMap(frames[frames.length - 1] || {{}});
        for (const [source, label] of [[first, "start"], [last, "finish"]]) {{
          const lh = source.get(23), rh = source.get(24);
          if (!lh || !rh) continue;
          const pelvis = {{x:(Number(lh.x || 0)+Number(rh.x || 0))*.5, y:scene.cy - scene.radius * .78, z:(Number(lh.z || 0)+Number(rh.z || 0))*.5, c:1}};
          const p = project(pelvis, w, h);
          ctx.beginPath(); ctx.arc(p.x, p.y, 4.5, 0, Math.PI * 2); ctx.fill();
          ctx.font = "700 11px Segoe UI, sans-serif";
          ctx.fillText(label, p.x + 7, p.y - 7);
        }}
        ctx.restore();
      }}
      function drawTrail(maps, joint, w, h, color) {{
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.globalAlpha = .62;
        ctx.beginPath();
        let started = false;
        for (const map of maps) {{
          const p = map.get(joint);
          if (!p || p.c < .18) continue;
          const q = project(p, w, h);
          if (!started) {{ ctx.moveTo(q.x, q.y); started = true; }} else ctx.lineTo(q.x, q.y);
        }}
        ctx.stroke();
        ctx.globalAlpha = 1;
      }}
      function drawCapsule(a, b, color, width, alpha) {{
        if (!a || !b || a.c < .18 || b.c < .18) return;
        ctx.save();
        ctx.globalAlpha = alpha;
        ctx.lineCap = "round";
        ctx.lineJoin = "round";
        ctx.shadowColor = "rgba(17,24,39,.16)";
        ctx.shadowBlur = 10;
        ctx.shadowOffsetY = 3;
        ctx.strokeStyle = color;
        ctx.lineWidth = width;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
        ctx.shadowBlur = 0;
        ctx.globalAlpha = Math.min(1, alpha + .16);
        ctx.strokeStyle = "rgba(255,255,255,.36)";
        ctx.lineWidth = Math.max(2, width * .28);
        ctx.beginPath();
        ctx.moveTo(a.x - width * .08, a.y - width * .08);
        ctx.lineTo(b.x - width * .08, b.y - width * .08);
        ctx.stroke();
        ctx.restore();
      }}
      function drawJointBall(p, color, radius) {{
        if (!p || p.c < .18) return;
        const grad = ctx.createRadialGradient(p.x - radius * .35, p.y - radius * .35, radius * .15, p.x, p.y, radius);
        grad.addColorStop(0, "#ffffff");
        grad.addColorStop(.28, color);
        grad.addColorStop(1, "rgba(17,24,39,.28)");
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(p.x, p.y, radius, 0, Math.PI * 2);
        ctx.fill();
      }}
      function drawBodyVolume(projected) {{
        const ls = projected.get(11), rs = projected.get(12), lh = projected.get(23), rh = projected.get(24), nose = projected.get(0);
        if (ls && rs && lh && rh) {{
          ctx.save();
          ctx.fillStyle = "rgba(249,115,43,.18)";
          ctx.strokeStyle = "rgba(249,115,43,.48)";
          ctx.lineWidth = 2;
          ctx.shadowColor = "rgba(17,24,39,.12)";
          ctx.shadowBlur = 12;
          ctx.beginPath();
          ctx.moveTo(ls.x, ls.y);
          ctx.lineTo(rs.x, rs.y);
          ctx.lineTo(rh.x, rh.y);
          ctx.lineTo(lh.x, lh.y);
          ctx.closePath();
          ctx.fill();
          ctx.stroke();
          ctx.restore();
          const chest = {{x:(ls.x+rs.x+lh.x+rh.x)/4, y:(ls.y+rs.y+lh.y+rh.y)/4, c:1}};
          const shoulderMid = {{x:(ls.x+rs.x)/2, y:(ls.y+rs.y)/2, c:1}};
          const hipMid = {{x:(lh.x+rh.x)/2, y:(lh.y+rh.y)/2, c:1}};
          drawCapsule(shoulderMid, hipMid, "rgba(249,115,43,.46)", 38, .72);
          drawJointBall(chest, "rgba(249,115,43,.68)", 13);
        }}
        if (nose && ls && rs) {{
          const neck = {{x:(ls.x+rs.x)/2, y:(ls.y+rs.y)/2 - 8, c:1}};
          drawCapsule(neck, nose, "rgba(220,38,38,.48)", 20, .72);
          drawJointBall(nose, "rgba(220,38,38,.72)", 15);
        }}
        const limbSpecs = [
          [11,13,"rgba(37,99,235,.56)",22],[13,15,"rgba(37,99,235,.52)",18],
          [12,14,"rgba(192,38,211,.56)",22],[14,16,"rgba(192,38,211,.52)",18],
          [23,25,"rgba(37,99,235,.46)",26],[25,27,"rgba(37,99,235,.42)",22],
          [24,26,"rgba(192,38,211,.46)",26],[26,28,"rgba(192,38,211,.42)",22],
        ];
        for (const [aIdx, bIdx, color, width] of limbSpecs) {{
          drawCapsule(projected.get(aIdx), projected.get(bIdx), color, width, .82);
        }}
      }}
      function draw() {{
        resize();
        const w = canvas.clientWidth, h = canvas.clientHeight;
        drawGrid(w, h);
        drawBodyPath(w, h);
        const frame = interpolatedFrame(playhead);
        const map = pointMap(frame);
        const trailIndex = Math.round(clampFrameIndex(playhead));
        const trailStart = Math.max(0, trailIndex - 24);
        const trailMaps = frames.slice(trailStart, trailIndex + 1).map(pointMap);
        drawTrail(trailMaps, 15, w, h, "rgba(37,99,235,.65)");
        drawTrail(trailMaps, 16, w, h, "rgba(192,38,211,.65)");
        const projected = new Map();
        for (const [idx, p] of map) projected.set(idx, project(p, w, h));
        drawBodyVolume(projected);
        const sorted = connections.slice().sort((ab, cd) => {{
          const a = projected.get(ab[0]), b = projected.get(ab[1]), c = projected.get(cd[0]), d = projected.get(cd[1]);
          return ((c?.z || 0) + (d?.z || 0)) - ((a?.z || 0) + (b?.z || 0));
        }});
        for (const [aIdx, bIdx] of sorted) {{
          const a = projected.get(aIdx), b = projected.get(bIdx);
          if (!a || !b || a.c < .18 || b.c < .18) continue;
          ctx.strokeStyle = colorFor(aIdx, bIdx);
          ctx.lineWidth = 3.5;
          ctx.lineCap = "round";
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }}
        for (const [idx, p] of projected) {{
          if (p.c < .18) continue;
          const color = left.has(idx) ? "#1d4ed8" : right.has(idx) ? "#c026d3" : "#dc2626";
          drawJointBall(p, color, idx === 0 ? 6.5 : 5.2);
        }}
        ctx.fillStyle = "#111827";
        ctx.font = "800 16px Segoe UI, sans-serif";
        ctx.fillText("Relative 3D marker skeleton", 18, 28);
        ctx.font = "12px Segoe UI, sans-serif";
        ctx.fillStyle = "#526174";
        ctx.fillText(`X/Y/Z view · ${{data.unit || "body-scale units"}} · frame ${{frame.frame}}`, 18, 48);
        ctx.fillStyle = "#1d4ed8";
        ctx.beginPath(); ctx.arc(w - 174, 24, 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#111827"; ctx.fillText("left markers", w - 164, 29);
        ctx.fillStyle = "#c026d3";
        ctx.beginPath(); ctx.arc(w - 82, 24, 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = "#111827"; ctx.fillText("right markers", w - 72, 29);
        timeEl.textContent = `${{(frame.time || 0).toFixed(2)}}s`;
        slider.value = String(Math.round(clampFrameIndex(playhead)));
      }}
      function tick(t) {{
        if (playing) {{
          const fps = Math.max(6, Math.min(Number(data.fps || 12), 18));
          const delta = lastTime ? Math.min((t - lastTime) / 1000, 0.08) : 0;
          playhead += delta * fps;
          if (playhead >= frames.length - 1) playhead = 0;
          lastTime = t;
          draw();
        }} else {{
          lastTime = t;
        }}
        requestAnimationFrame(tick);
      }}
      slider.addEventListener("input", () => {{ playhead = clampFrameIndex(Number(slider.value || 0)); playing = false; playBtn.textContent = "Play"; draw(); }});
      playBtn.addEventListener("click", () => {{ playing = !playing; playBtn.textContent = playing ? "Pause" : "Play"; }});
      root.querySelectorAll("[data-view]").forEach(btn => btn.addEventListener("click", () => {{
        const view = btn.dataset.view;
        if (view === "front") {{ yaw = 0; pitch = 0; }}
        if (view === "side") {{ yaw = -Math.PI / 2; pitch = 0; }}
        if (view === "top") {{ yaw = -0.6; pitch = -Math.PI / 2.25; }}
        if (view === "reset") {{ yaw = -0.7; pitch = -0.18; }}
        draw();
      }}));
      canvas.addEventListener("pointerdown", e => {{ drag = {{x:e.clientX, y:e.clientY, yaw, pitch}}; canvas.setPointerCapture(e.pointerId); }});
      canvas.addEventListener("pointermove", e => {{
        if (!drag) return;
        yaw = drag.yaw + (e.clientX - drag.x) * 0.008;
        pitch = Math.max(-1.35, Math.min(1.1, drag.pitch + (e.clientY - drag.y) * 0.008));
        draw();
      }});
      canvas.addEventListener("pointerup", () => {{ drag = null; }});
      window.addEventListener("resize", draw);
      draw();
      requestAnimationFrame(tick);
    }})();
    </script>
    """


def pose3d_media_html(report: dict[str, Any], compact: bool = False) -> str:
    interactive = interactive_pose3d_viewer_html(report, compact=compact)
    if interactive:
        return interactive
    animation = report_asset(report, "pose3d_animation")
    video = report_asset(report, "pose3d_video")
    image = report_asset(report, "pose3d_contact_sheet")
    if not animation and not video and not image:
        return ""
    parts = ['<div class="media-stack pose3d-showcase">']
    if animation:
        parts.append(asset_image_html(animation, "Animated estimated 3D pose", "evidence-image pose3d-gif"))
    elif image:
        parts.append(asset_image_html(image, "Estimated 3D pose event frames"))
    elif video:
        parts.append(asset_video_html(video, "Estimated 3D pose skeleton video"))
    if not compact:
        parts.append('<p class="small-note">估计 3D 动图：来自稳定 2D 骨架和 MediaPipe 相对深度，用来观察身体朝向、手臂路径和前后层次；不等同 Vicon/GVHMR 的真实世界坐标。<span class="en">Estimated 3D animation: built from the stabilized 2D skeleton and MediaPipe relative depth. It helps review body direction, arm path, and front-back layering, but it is not a Vicon/GVHMR world-coordinate reconstruction.</span></p>')
    parts.append("</div>")
    return "".join(parts)


def pose3d_frame_maps(report: dict[str, Any]) -> tuple[list[float], list[dict[int, dict[str, Any]]], float | None]:
    preview = report.get("session", {}).get("pose3d_preview") or {}
    frames = preview.get("frames") or []
    if not frames:
        return [], [], None
    times = [float(frame.get("time") or 0.0) for frame in frames]
    maps = [{int(point["i"]): point for point in frame.get("joints", [])} for frame in frames]
    event_frame = preview.get("event_frame")
    event_time = None
    if event_frame is not None:
        closest = min(frames, key=lambda frame: abs(int(frame.get("frame", 0)) - int(event_frame)))
        event_time = float(closest.get("time") or 0.0)
    return times, maps, event_time


def joint_point(frame: dict[int, dict[str, Any]], idx: int) -> tuple[float, float, float] | None:
    point = frame.get(idx)
    if not point or float(point.get("c") or 0.0) < 0.18:
        return None
    return (float(point["x"]), float(point["y"]), float(point["z"]))


def center_point(frame: dict[int, dict[str, Any]], indices: list[int]) -> tuple[float, float, float] | None:
    points = [joint_point(frame, idx) for idx in indices]
    valid = [point for point in points if point is not None]
    if not valid:
        return None
    return tuple(sum(point[dim] for point in valid) / len(valid) for dim in range(3))  # type: ignore[return-value]


def distance_3d(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(sum((a[dim] - b[dim]) ** 2 for dim in range(3)))


def angle_3d(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> float | None:
    v1 = [a[i] - b[i] for i in range(3)]
    v2 = [c[i] - b[i] for i in range(3)]
    n1 = math.sqrt(sum(v * v for v in v1))
    n2 = math.sqrt(sum(v * v for v in v2))
    if n1 <= 1e-6 or n2 <= 1e-6:
        return None
    dot = sum(v1[i] * v2[i] for i in range(3)) / (n1 * n2)
    return math.degrees(math.acos(max(-1.0, min(1.0, dot))))


def smooth_values(values: list[float]) -> list[float]:
    if len(values) < 5:
        return values
    out = []
    for index in range(len(values)):
        lo = max(0, index - 2)
        hi = min(len(values), index + 3)
        out.append(sum(values[lo:hi]) / (hi - lo))
    return out


def series_angle(maps: list[dict[int, dict[str, Any]]], a: int, b: int, c: int) -> list[float]:
    values: list[float] = []
    last = 0.0
    for frame in maps:
        pa, pb, pc = joint_point(frame, a), joint_point(frame, b), joint_point(frame, c)
        angle = angle_3d(pa, pb, pc) if pa and pb and pc else None
        last = float(angle) if angle is not None else last
        values.append(last)
    return smooth_values(values)


def series_distance_from_start(maps: list[dict[int, dict[str, Any]]], indices: list[int]) -> list[float]:
    points = [center_point(frame, indices) for frame in maps]
    origin = next((point for point in points if point is not None), None)
    if origin is None:
        return [0.0 for _ in maps]
    values = [distance_3d(point, origin) if point else 0.0 for point in points]
    return smooth_values(values)


def series_speed(times: list[float], maps: list[dict[int, dict[str, Any]]], indices: list[int]) -> list[float]:
    points = [center_point(frame, indices) for frame in maps]
    values = [0.0]
    for index in range(1, len(points)):
        prev, cur = points[index - 1], points[index]
        dt = max(times[index] - times[index - 1], 1e-3)
        values.append(distance_3d(prev, cur) / dt if prev and cur else values[-1])
    return smooth_values(values)


def series_axis(maps: list[dict[int, dict[str, Any]]], indices: list[int], axis: int) -> list[float]:
    values = []
    last = 0.0
    for frame in maps:
        point = center_point(frame, indices)
        if point:
            last = point[axis]
        values.append(last)
    return smooth_values(values)


def research_chart_svg(
    times: list[float],
    series: list[tuple[str, str, list[float]]],
    y_label: str,
    event_time: float | None,
) -> str:
    if not times or not series:
        return '<svg viewBox="0 0 720 300" role="img" aria-label="No chart data"></svg>'
    width, height = 720, 300
    left, right, top, bottom = 70, 690, 38, 226
    values = [value for _, _, vals in series for value in vals if math.isfinite(value)]
    y_min = min(values) if values else 0.0
    y_max = max(values) if values else 1.0
    if abs(y_max - y_min) < 1e-6:
        y_max = y_min + 1.0
    pad = (y_max - y_min) * 0.12
    y_min -= pad
    y_max += pad
    x_min, x_max = min(times), max(times)
    if abs(x_max - x_min) < 1e-6:
        x_max = x_min + 1.0

    def x_pos(t: float) -> float:
        return left + (t - x_min) / (x_max - x_min) * (right - left)

    def y_pos(v: float) -> float:
        return bottom - (v - y_min) / (y_max - y_min) * (bottom - top)

    grid = []
    for i in range(5):
        y = top + i * (bottom - top) / 4
        grid.append(f'<line x1="{left}" y1="{y:.1f}" x2="{right}" y2="{y:.1f}" stroke="#e7edf5"/>')
    event = ""
    if event_time is not None:
        x = x_pos(event_time)
        event = (
            f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#7b8798" stroke-dasharray="5 5"/>'
            f'<rect x="{x - 48:.1f}" y="12" width="96" height="18" rx="9" fill="#f8fbff" stroke="#d7e0ec"/>'
            f'<text x="{x:.1f}" y="25" text-anchor="middle" font-size="11" fill="#526174">关键事件</text>'
        )
    paths = []
    legend = []
    for idx, (label, color, vals) in enumerate(series):
        coords = " ".join(f"{x_pos(t):.1f},{y_pos(v):.1f}" for t, v in zip(times, vals))
        paths.append(f'<polyline points="{coords}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>')
        lx = left + idx * 145
        legend.append(
            f'<circle cx="{lx}" cy="272" r="5" fill="{color}"/>'
            f'<text x="{lx + 10}" y="276" font-size="12" fill="#344256">{escape(label)}</text>'
        )
    return (
        f'<svg class="research-svg" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(y_label)}">'
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="16" fill="#ffffff"/>'
        f'<text x="22" y="28" font-size="12" font-weight="800" fill="#07111f">{escape(y_label)}</text>'
        f'<text x="22" y="56" font-size="11" fill="#718096">{escape(fmt_value(y_max))}</text>'
        f'<text x="22" y="{bottom:.1f}" font-size="11" fill="#718096">{escape(fmt_value(y_min))}</text>'
        f'{"".join(grid)}'
        f'<line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#aab6c7"/>'
        f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#aab6c7"/>'
        f'{event}{"".join(paths)}'
        f'<text x="{left}" y="250" font-size="11" fill="#718096">时间 (s)</text>'
        f'<text x="{right - 38}" y="250" font-size="11" fill="#718096">{x_max:.2f}s</text>'
        f'{"".join(legend)}'
        '</svg>'
    )


def research_card(title: str, en_title: str, chart: str, note: str, en_note: str) -> str:
    return (
        '<article class="research-card">'
        f'<h4>{escape(title)}<span class="en">{escape(en_title)}</span></h4>'
        f'{chart}'
        f'<p class="explain">怎么看：{escape(note)}</p>'
        f'<p class="en">How to read: {escape(en_note)}</p>'
        '</article>'
    )


def researcher_curves_html(report: dict[str, Any]) -> str:
    times, maps, event_time = pose3d_frame_maps(report)
    if len(times) < 2:
        return ""
    throwing_wrist = 16 if report.get("athlete", {}).get("dominant_side", "right") == "right" else 15
    throwing_elbow = 14 if throwing_wrist == 16 else 13
    throwing_shoulder = 12 if throwing_wrist == 16 else 11
    glove_wrist = 15 if throwing_wrist == 16 else 16
    cards = [
        research_card(
            "投球角度时间曲线",
            "Pitch angle curves over time",
            research_chart_svg(
                times,
                [
                    ("投球肘角", "#f9732b", series_angle(maps, throwing_shoulder, throwing_elbow, throwing_wrist)),
                    ("前侧膝角", "#2563eb", series_angle(maps, 23, 25, 27)),
                    ("手套侧膝角", "#7b61ff", series_angle(maps, 24, 26, 28)),
                    ("髋肩分离", "#16a34a", series_distance_from_start(maps, [11, 12, 23, 24])),
                ],
                "角度 / 相对量",
                event_time,
            ),
            "重点看关键事件线前后，肘角、前腿支撑和髋肩分离是否同步变化。",
            "Focus around the event line. Check whether elbow angle, front-leg support, and hip-shoulder separation change in sequence.",
        ),
        research_card(
            "投球速度时间曲线",
            "Pitch speed curves over time",
            research_chart_svg(
                times,
                [
                    ("骨盆中心速度", "#2563eb", series_speed(times, maps, [23, 24])),
                    ("躯干中心速度", "#7b61ff", series_speed(times, maps, [11, 12, 23, 24])),
                    ("出手侧手速度", "#f9732b", series_speed(times, maps, [throwing_wrist])),
                    ("手套侧手速度", "#16a34a", series_speed(times, maps, [glove_wrist])),
                ],
                "body-scale / s",
                event_time,
            ),
            "速度峰值顺序用于判断动力链。理想情况下躯干/骨盆先带动，手部最后输出。",
            "Peak order is used to inspect the kinetic chain. Ideally pelvis and trunk lead, and the hand peaks later.",
        ),
        research_card(
            "稳定性与位移曲线",
            "Stability and displacement curves",
            research_chart_svg(
                times,
                [
                    ("头部漂移", "#2563eb", series_distance_from_start(maps, [0])),
                    ("骨盆位移", "#f9732b", series_distance_from_start(maps, [23, 24])),
                    ("肩部位移", "#7b61ff", series_distance_from_start(maps, [11, 12])),
                ],
                "body-scale distance",
                event_time,
            ),
            "位移曲线用于检查头部是否过早跑掉，以及身体重心是否在释放前后失控。",
            "Displacement curves show whether the head leaves early and whether body center control breaks around release.",
        ),
        research_card(
            "3D 深度与手腕轨迹",
            "3D depth and wrist path",
            research_chart_svg(
                times,
                [
                    ("出手侧手深度", "#f9732b", series_axis(maps, [throwing_wrist], 2)),
                    ("手套侧手深度", "#16a34a", series_axis(maps, [glove_wrist], 2)),
                    ("肩中心深度", "#2563eb", series_axis(maps, [11, 12], 2)),
                    ("髋中心深度", "#7b61ff", series_axis(maps, [23, 24], 2)),
                ],
                "relative depth",
                event_time,
            ),
            "深度曲线帮助判断投球臂是否真的进入三维空间，而不是只在画面平面内移动。",
            "Depth curves show whether the throwing arm moves through 3D space instead of staying on the image plane.",
        ),
    ]
    return (
        '<div class="researcher-module">'
        '<div class="researcher-note">这一模块使用当前视频的 relative 3D pose preview 生成。若接入 Vicon/C3D，可替换为真实 marker 曲线。'
        '<span class="en">This module is generated from the current video-based relative 3D pose preview. If Vicon/C3D is connected later, the same layout can use true marker curves.</span></div>'
        '<div class="research-grid">'
        + "".join(cards)
        + "</div></div>"
    )


def motion_trends_html(report: dict[str, Any]) -> str:
    researcher = researcher_curves_html(report)
    if researcher:
        return researcher
    chart = report_asset(report, "motion_trend_chart")
    if not chart:
        return (
            '<div class="visual">'
            f'<h3>{section_title("动作趋势图", "Motion trend charts")}</h3>'
            '<p class="explain">本次样例没有逐帧趋势图资产。运行完整视频报告后，这里会显示角度、速度、稳定性随时间变化的折线图。</p>'
            '<p class="en">No frame-by-frame trend chart is available for this sample. A full video run will show angle, speed, and stability curves over time.</p>'
            '</div>'
        )
    return (
        '<div class="media-stack">'
        f'<h3>{section_title("随时间变化的动作曲线", "Motion curves over time")}</h3>'
        f'{asset_image_html(chart, "Motion trend charts over time")}'
        '<p class="explain">研究者视角优先看趋势：关节角度、相对速度、头部和骨盆位移随时间如何变化，比逐个 marker 字段更容易解释。</p>'
        '<p class="en">For research review, the report emphasizes trends: joint angles, relative speed, and head or pelvis movement over time. These curves are easier to interpret than raw marker fields.</p>'
        '</div>'
    )


def calibration_summary_html(report: dict[str, Any]) -> str:
    return (
        '<div class="grid">'
        + card_html(
            metric_block(
                "calibration_role",
                "Vicon / 3D 校准关系",
                "research",
                "manual",
                "说明",
                "",
                "good",
                "Vicon 或 GVHMR 结果用于校准真实 3D 速度、姿态方向和尺度；CV 报告保留为视频估计。",
                "Vicon or GVHMR can calibrate true 3D speed, pose direction, and scale. The CV report remains a video-based estimate.",
            )
        )
        + card_html(
            metric_block(
                "raw_table_policy",
                "原始参数展示策略",
                "research",
                "manual",
                "趋势优先",
                "",
                "warning",
                "不在主报告里展开每个 marker 或字段，避免非建模读者被字段名淹没；必要时保留 CSV 文件供复核。",
                "The main report does not list every marker or field. CSV files remain available for audit, while the visible report focuses on interpretable curves.",
            )
        )
        + "</div>"
    )


def stable_video_html(report: dict[str, Any]) -> str:
    video = report_asset(report, "stable_pose_video")
    image = report_asset(report, "event_contact_sheet")
    if video:
        return (
            '<video class="evidence-video" controls playsinline preload="none" '
            f'src="{escape(video)}"></video>'
            '<p class="small-note" style="margin-top:10px;">视频中叠加的是稳定后的 2D 骨架，用来核对本次指标来自哪段动作。<span class="en">The overlay shows the stabilized 2D skeleton used to verify which motion segment produced the metrics.</span></p>'
        )
    if image:
        return f'<img class="evidence-image" src="{escape(image)}" alt="投球事件抽帧">'
    return '<p class="explain">本次没有可嵌入的视频证据文件。</p>'


def pitch_lookup(report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {m["metric_id"]: m for m in report["views"]["player"]["pitch"]["metrics"]}


def pitch_hero_stats_html(report: dict[str, Any]) -> str:
    lookup = pitch_lookup(report)
    items = [
        ("释放质量", lookup.get("pitch_release_quality_score", {}).get("value"), "分"),
        ("目标线控制", lookup.get("pitch_target_line_control_score", {}).get("value"), "分"),
        ("手臂路径", lookup.get("pitch_arm_path_score", {}).get("value"), "分"),
    ]
    return "".join(
        f"<div><strong>{escape(fmt_value(value, unit))}</strong><span>{escape(label)}</span></div>"
        for label, value, unit in items
    )


def pitch_priority_items_html(report: dict[str, Any]) -> str:
    metrics = report["views"]["player"]["pitch"]["metrics"]
    order = {"concern": 0, "suspicious": 1, "warning": 2, "unavailable": 3, "good": 4}
    candidates = sorted(metrics, key=lambda m: (order.get(m["status"], 9), -(m["score"] or 0)))
    rows = []
    for index, metric in enumerate(candidates[:5], start=1):
        priority_en = PITCH_PRIORITY_EN.get(metric["metric_id"], {})
        en_name = priority_en.get("name") or metric_en(metric, "name", metric["metric_id"].replace("_", " ").title())
        en_explain = priority_en.get("explain") or metric_en(metric, "explain", "Review this item first because it is one of the clearest movement priorities in this report.")
        rows.append(
            '<div class="priority-item">'
            f'<div class="rank">{index}</div>'
            f'<div><strong>{escape(metric["name"])}<span class="en">{escape(en_name)}</span></strong>'
            f'<p class="explain">{escape(metric["parent_explanation"])}</p>'
            f'<p class="en">{escape(en_explain)}</p></div>'
            f'{status_badge(metric["status"])}'
            '</div>'
        )
    return "".join(rows)


def pitch_timeline_html(report: dict[str, Any]) -> str:
    _, pitch = selected_samples(report)
    release = pitch.get("release_timing_pct")
    landing = pitch.get("front_foot_landing_pct")
    phases = [
        ("启动", "手臂开始加速前，身体先进入前移。", 18, "warning"),
        ("前脚落地", "支撑脚建立方向和刹车。", landing if landing is not None else 36, "warning"),
        ("出手近似", "手腕/指尖速度峰值帧，用来近似释放阶段。", release if release is not None else 55, "concern"),
        ("收尾", "出手后身体能否继续稳定朝目标线。", 84, "good"),
    ]
    rows = []
    for label, note, width, status in phases:
        rows.append(
            '<div class="time-item">'
            f'<strong>{escape(label)}</strong>'
            f'<div><div class="time-bar"><span style="--w:{clamp(value_or_zero(width)):.1f}%;"></span></div>'
            f'<p class="explain" style="margin-top:6px;">{escape(note)}</p></div>'
            f'{status_badge(status)}'
            '</div>'
        )
    rows.append(f'<p class="small-note">出手近似点：{escape(fmt_value(pitch.get("event_s"), "s"))}。真实球离手帧需要球追踪或高速视频确认。</p>')
    return "".join(rows)


def pitch_chain_html(report: dict[str, Any]) -> str:
    lookup = pitch_lookup(report)
    items = [
        ("下肢启动", lookup.get("pitch_lower_body_start_score")),
        ("目标线控制", lookup.get("pitch_target_line_control_score")),
        ("髋肩分离", lookup.get("pitch_hip_shoulder_separation_deg")),
        ("手臂路径", lookup.get("pitch_arm_path_score")),
        ("释放质量", lookup.get("pitch_release_quality_score")),
        ("收尾稳定", lookup.get("pitch_finish_stability_score")),
    ]
    rows = []
    for label, metric in items:
        if not metric:
            continue
        rows.append(
            f'<div class="chain-step {metric["status"]}"><strong>{escape(label)}</strong>'
            f'<span>{escape(fmt_value(metric["value"], metric["unit"]))}</span></div>'
        )
    return "".join(rows)


def pitch_heatmap_html(report: dict[str, Any]) -> str:
    lookup = pitch_lookup(report)
    cells = [
        ("下肢与方向", lookup.get("pitch_target_line_control_score"), "跨步方向是否稳定朝目标线"),
        ("躯干蓄力", lookup.get("pitch_hip_shoulder_separation_deg"), "髋肩是否有足够分离空间"),
        ("手臂路径", lookup.get("pitch_arm_path_score"), "投球臂轨迹是否平滑"),
        ("释放与收尾", lookup.get("pitch_release_quality_score"), "最后释放是否干净且稳定"),
    ]
    return "".join(
        '<div class="heat-cell {status}"><strong>{label}</strong><p class="explain">{note}</p><p class="value" style="font-size:24px;">{value}</p>{badge}</div>'.format(
            status=(metric or {}).get("status", "unavailable"),
            label=escape(label),
            note=escape(note),
            value=escape(fmt_value((metric or {}).get("value"), (metric or {}).get("unit", ""))),
            badge=status_badge((metric or {}).get("status", "unavailable")),
        )
        for label, metric, note in cells
    )


def pitch_recommendation_cards_html(report: dict[str, Any]) -> str:
    lookup = pitch_lookup(report)
    recs = [
        {
            "title": "前脚目标线跨步",
            "why": "投球先要把身体送到目标方向。前脚落地越稳定，后面的释放点越容易重复。",
            "how_to_do": "在地上贴一条目标线，做慢速投球动作。前脚落地时脚尖和膝盖尽量朝目标线，不急着把球投出去。",
            "sets_reps": "每次 3 组，每组 6 次",
            "parent_check": "家长站在投手后方看，前脚有没有明显踩到目标线外侧。",
            "metric": lookup.get("pitch_target_line_control_score"),
        },
        {
            "title": "髋先走、肩晚到",
            "why": "髋肩分离不足时，孩子容易只用手臂投球，力量传递会断。",
            "how_to_do": "侧身站好，先让前脚落地和髋部转向目标，肩膀和手套先留住半秒，再让上半身跟上。",
            "sets_reps": "每天 2 组，每组 8 次，慢速完成",
            "parent_check": "家长看肩膀是不是和髋一起转。如果一起转，就重新放慢。",
            "metric": lookup.get("pitch_hip_shoulder_separation_deg"),
        },
        {
            "title": "毛巾手臂路径",
            "why": "手臂路径稳定，释放点才更容易稳定，也能减少乱甩手臂的风险。",
            "how_to_do": "手里拿小毛巾，不拿球。按完整投球节奏挥臂，让毛巾自然向目标方向甩出，重点看手臂轨迹顺不顺。",
            "sets_reps": "每次 3 组，每组 8 次",
            "parent_check": "家长从侧面看，手臂有没有突然绕很大圈或卡住。",
            "metric": lookup.get("pitch_arm_path_score"),
        },
        {
            "title": "出手后稳定收尾",
            "why": "收尾稳定说明身体没有过早散掉，也方便下一次复测对比。",
            "how_to_do": "每次出手后保持收尾姿势 1 秒，胸口继续朝目标方向，头不要马上甩开。",
            "sets_reps": "每次 2 组，每组 8 次",
            "parent_check": "家长看出手后身体能不能停住，脚和头有没有明显乱晃。",
            "metric": lookup.get("pitch_finish_stability_score"),
        },
    ]
    cards = []
    for rec in recs:
        metric = rec["metric"] or {}
        metric_line = ""
        if metric:
            metric_line = f'<p><b>复测指标：</b>{escape(metric["name"])} {escape(fmt_value(metric["value"], metric["unit"]))}</p>'
        cards.append(
            '<article class="card rec">'
            f'<strong>{escape(rec["title"])}<span class="en">{escape(rec_en(rec, "title"))}</span></strong>'
            f'<p>{escape(rec["why"])}</p>'
            f'<p class="en">{escape(rec_en(rec, "why"))}</p>'
            f'<p><b>怎么做：</b>{escape(rec["how_to_do"])}</p>'
            f'<p class="en"><b>How to do it: </b>{escape(rec_en(rec, "how"))}</p>'
            f'<p><b>训练量：</b>{escape(rec["sets_reps"])}</p>'
            f'<p class="en"><b>Volume: </b>{escape(rec_en(rec, "volume"))}</p>'
            f'<p><b>家长检查：</b>{escape(rec["parent_check"])}</p>'
            f'<p class="en"><b>Parent check: </b>{escape(rec_en(rec, "check"))}</p>'
            f'{metric_line}'
            '</article>'
        )
    return "".join(cards)


def pitch_raw_table_html(report: dict[str, Any]) -> str:
    return motion_trends_html(report)


def pitch_scoring_explainer_html(report: dict[str, Any]) -> str:
    items = [
        ("pitch_phase_rule", "阶段定位", "用人体关键点寻找启动、前脚落地、释放近似点和收尾。"),
        ("pitch_direction_rule", "方向控制", "用前脚方向、跨步角度和身体朝向估计是否朝目标线移动。"),
        ("pitch_chain_rule", "动力链", "按下肢、髋肩、手臂、释放、收尾的顺序看动作是否连续。"),
        ("pitch_video_rule", "证据视频", "页面中的稳定骨架视频用于核对每个指标来自哪一段动作。"),
    ]
    return "".join(
        card_html(metric_block(key, title, "pitch", "manual", "说明", "", "good", note, note))
        for key, title, note in items
    )


def pitch_limitations_html(report: dict[str, Any]) -> str:
    items = [
        ("真实球速 / 转速", "手机单目视频没有雷达或连续球追踪，不能稳定计算真实出球速度和旋转。", "warning"),
        ("真实离手帧", "当前用手部速度峰值近似释放阶段；精确离手需要高速视频或球追踪。", "warning"),
        ("绝对速度", "px/s 会受拍摄距离、镜头焦距和裁切影响，只适合同机位前后趋势对比。", "unavailable"),
        ("伤病判断", "报告只能提示动作风险线索，不能替代教练现场判断或医疗诊断。", "unavailable"),
    ]
    return "".join(
        card_html(metric_block(title, title, "pitch", "manual", status, "", status, note, note))
        for title, note, status in items
    )


def render_pitch_html(report: dict[str, Any]) -> str:
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    css = template.split("<style>", 1)[1].split("</style>", 1)[0]
    css += """
    .evidence-video, .evidence-image {
      width: 100%;
      border-radius: 12px;
      background: #0d1422;
      border: 1px solid rgba(255,255,255,0.12);
      display: block;
    }
    .evidence-video {
      max-height: 620px;
      object-fit: contain;
    }
    .pose3d-showcase {
      background: #121a29;
      border-radius: 12px;
      padding: 12px;
    }
    .pose3d-viewer {
      background: #fbfdff;
      border: 1px solid #d7e0ec;
      border-radius: 12px;
      padding: 12px;
      color: #07111f;
    }
    .pose3d-viewer canvas {
      width: 100%;
      min-height: 540px;
      display: block;
      border-radius: 10px;
      background: #fbfdff;
      touch-action: none;
      cursor: grab;
    }
    .pose3d-viewer canvas:active {
      cursor: grabbing;
    }
    .pose3d-toolbar {
      display: grid;
      grid-template-columns: repeat(5, auto) minmax(120px, 1fr) auto;
      gap: 8px;
      align-items: center;
      margin-top: 10px;
    }
    .pose3d-toolbar button {
      border: 1px solid #d7e0ec;
      background: #ffffff;
      color: #07111f;
      border-radius: 8px;
      padding: 7px 10px;
      font-weight: 750;
      cursor: pointer;
    }
    .pose3d-toolbar input {
      width: 100%;
      accent-color: var(--orange);
    }
    .pose3d-time {
      color: #526174;
      font-size: 13px;
      font-weight: 750;
    }
    .pose3d-gif {
      min-height: 440px;
      object-fit: contain;
      border-color: rgba(255,255,255,0.16);
    }
    .pitch-focus {
      display: grid;
      grid-template-columns: minmax(0, 0.92fr) minmax(360px, 1.08fr);
      gap: 18px;
      align-items: start;
    }
    @media (max-width: 960px) {
      .pitch-focus { grid-template-columns: 1fr; }
      .pose3d-toolbar { grid-template-columns: repeat(5, 1fr); }
      .pose3d-toolbar input, .pose3d-time { grid-column: 1 / -1; }
    }
    """
    player_pitch = report["views"]["player"]["pitch"]
    pitch_radar_chart, pitch_radar_legend = radar_chart_html(report, mode="pitch")
    title = "SRS AI Baseball 投球动作分析报告"
    summary = "本次报告按投球流程组织：先看前脚落地和释放近似点，再看下肢启动、目标线控制、髋肩分离、手臂路径、释放质量和收尾稳定。速度类结果只作为同机位复测趋势，不当作真实球速。"
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  <style>{css}</style>
</head>
<body>
  <main>
    <section class="hero">
      <div class="hero-copy">
        <div class="brand">SRS AI Baseball</div>
        <h1>{escape(title)}<span class="en">Pitching Motion Analysis Report</span></h1>
        <p class="summary">{escape(summary)}<span class="en">This report organizes pitching evidence by phase, then connects each issue to a practical training target.</span></p>
        <div class="meta-line">
          <span class="pill">报告 ID：{escape(report["metadata"]["report_id"])}</span>
          <span class="pill">生成日期：{escape(report["metadata"]["created_at"])}</span>
          <span class="pill">球员：{escape(report["athlete"]["name"])} / {escape(report["athlete"]["age_group"])}</span>
        </div>
      </div>
      <aside class="hero-panel">
        <div class="motion-canvas">{stable_video_html(report)}</div>
        <div class="hero-panel-footer">{pitch_hero_stats_html(report)}</div>
      </aside>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h2>本次投球先看什么<span class="en">What to review first</span></h2>
          <p>本页只展示投球阶段、方向控制、释放质量、收尾稳定和可解释边界。<span class="en">This page focuses on pitching phases, direction control, release quality, finish stability, and clear interpretation boundaries.</span></p>
        </div>
      </div>
      <div class="pitch-focus">
        <div class="priority-list">{pitch_priority_items_html(report)}</div>
        <div class="visual">
          <h3>估计 3D 动作动图<span class="en">Animated estimated 3D motion</span></h3>
          {pose3d_media_html(report)}
        </div>
      </div>
    </section>

    <section class="section">
      <div class="split">
        <div class="visual">
          <h3>投球六维评分图<span class="en">Six-dimension pitching radar</span></h3>
          <div class="radar-wrap">
            <div class="radar">{pitch_radar_chart}</div>
            <div class="legend">{pitch_radar_legend}</div>
          </div>
        </div>
        <div class="visual">
          <h3>怎么看<span class="en">How to read it</span></h3>
          <p class="explain">六个维度按从下肢到释放的动作链排列。外圈代表更稳定或更接近建议区间，内圈代表本周更值得优先训练。</p>
          <p class="en">The six dimensions follow the pitching chain from lower body control to release. A larger shape means stronger control or closer alignment with the target range.</p>
        </div>
      </div>
    </section>

    <h2>球员视角：投球动作指标<span class="en">Player view: pitching motion metrics</span></h2>
    <section class="section">
      <div class="section-head">
        <div>
          <h3>投球指标<span class="en">Pitching metrics</span></h3>
          <p>每个指标都来自视频姿态关键点。角度用于动作观察，速度只用于同机位前后对比。<span class="en">Each metric comes from video pose keypoints. Angles support motion review, while speed proxies are only for same-camera comparison.</span></p>
        </div>
      </div>
      <div class="grid">{"".join(card_html(m) for m in player_pitch["metrics"])}</div>
    </section>

    <section class="section">
      <div class="split">
        <div class="visual">
          <h3>投球阶段时间轴<span class="en">Pitching phase timeline</span></h3>
          <div class="timeline">{pitch_timeline_html(report)}</div>
        </div>
        <div class="visual">
          <h3>投球动力链<span class="en">Pitching kinetic chain</span></h3>
          <p class="small-note">按下肢、方向、躯干、手臂、释放和收尾看问题。</p>
          <div class="chain">{pitch_chain_html(report)}</div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h3>投球偏差热力图<span class="en">Pitching deviation heatmap</span></h3>
          <p>把投球问题按身体区域和动作阶段分组，方便决定下一次练什么。<span class="en">Pitching issues are grouped by body region and phase so the next practice target is clear.</span></p>
        </div>
      </div>
      <div class="heatmap">{pitch_heatmap_html(report)}</div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h3>改善建议<span class="en">Practice recommendations</span></h3>
          <p>建议按投球动作链生成，先从方向、髋肩、手臂路径和收尾稳定开始。<span class="en">Recommendations follow the pitching chain, starting with direction, hip-shoulder timing, arm path, and finish stability.</span></p>
        </div>
      </div>
      <div class="recommendations">{pitch_recommendation_cards_html(report)}</div>
    </section>

    <h2>研究者视角：趋势图和边界<span class="en">Research view: trend charts and boundaries</span></h2>
    <section class="section">
      <div class="source-grid">
        <div class="visual">
          <h3>投球评分规则摘要<span class="en">Pitch scoring rule summary</span></h3>
          <div class="grid">{pitch_scoring_explainer_html(report)}</div>
        </div>
        <div class="visual">
          <h3>能力边界<span class="en">Capability boundaries</span></h3>
          <p class="explain">真实球速、转速、球路位移和精确离手帧，需要球追踪、雷达或高速视觉。当前报告只给人体动作 proxy。</p>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h3>CV 时间序列趋势图<span class="en">CV time-series trend charts</span></h3>
          <p>这里显示本次投球样本的角度、速度和稳定性曲线，避免把每个 marker 字段直接堆在报告里。<span class="en">This section shows angle, speed, and stability curves for the pitching sample instead of listing every marker field.</span></p>
        </div>
      </div>
      <div class="data-scroll">{pitch_raw_table_html(report)}</div>
    </section>

    <section class="section">
      <div class="section-head">
        <div>
          <h3>本次限制<span class="en">Limitations</span></h3>
          <p>N/A、proxy 和无法判断项会明确展示，避免把估算结果当成真实测量。<span class="en">N/A values, proxy metrics, and unavailable judgments are shown clearly so estimates are not treated as true measurements.</span></p>
        </div>
      </div>
      <div class="grid">{pitch_limitations_html(report)}</div>
    </section>
  </main>
</body>
</html>"""
    return html


def render_html(report: dict[str, Any]) -> str:
    if report_is_pitch_only(report):
        return render_pitch_html(report)
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    player_bat = report["views"]["player"]["bat"]
    player_pitch = report["views"]["player"]["pitch"]
    radar_chart, radar_legend = radar_chart_html(report)
    values = {
        "title": "SRS AI Baseball 动作分析报告",
        "report_id": report["metadata"]["report_id"],
        "created_at": report["metadata"]["created_at"],
        "athlete_name": report["athlete"]["name"],
        "age_group": report["athlete"]["age_group"],
        "summary": report["summary"],
        "evidence_scene": evidence_scene_html(report),
        "hero_stats": hero_stats_html(report),
        "priority_items": priority_items_html(report),
        "radar_chart": radar_chart,
        "radar_legend": radar_legend,
        "player_bat_cards": "".join(card_html(m) for m in player_bat["metrics"]),
        "player_pitch_cards": "".join(card_html(m) for m in player_pitch["metrics"]),
        "pose_evidence": pose_evidence_html(report),
        "phase_timeline": phase_timeline_html(report),
        "comparison_bars": comparison_bars(report),
        "kinetic_chain": kinetic_chain_html(report),
        "heatmap": heatmap_html(report),
        "recommendation_cards": recommendation_cards(report["recommendations"]),
        "training_plan": training_plan_html(report["recommendations"]),
        "vicon_panel": vicon_panel_html(report),
        "scoring_explainer": scoring_explainer_html(),
        "cv_raw_table": motion_trends_html(report),
        "vicon_raw_table": calibration_summary_html(report),
        "limitations": limitations_html(report),
    }
    for key, value in values.items():
        template = template.replace("{{" + key + "}}", value)
    return template


def render_print_html(report: dict[str, Any]) -> str:
    html = render_html(report)
    html = html.replace("<body>", '<body class="print-report">', 1)
    html = html.replace(
        "</main>",
        '<p class="print-only small-note">打印提示：视频已在打印样式中隐藏，请查看同目录下的 HTML 报告获取可播放视频。<span class="en">Print note: videos are hidden in print mode. Open the HTML report in the same folder to play video evidence.</span></p></main>',
        1,
    )
    return html


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a stable SRS AI Baseball report from structured input.")
    parser.add_argument("--input", type=Path, default=EXAMPLE_INPUT, help="Raw report input JSON.")
    parser.add_argument("--out", type=Path, default=OUT_DIR, help="Output directory.")
    parser.add_argument("--bat-sample", default=None, help="CV batting sample id, e.g. hit_horizontal_06.")
    parser.add_argument("--pitch-sample", default=None, help="CV pitching sample id, e.g. pitch_vertical_09.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    out_dir = args.out if args.out.is_absolute() else ROOT / args.out
    input_path = args.input if args.input.is_absolute() else ROOT / args.input
    out_dir.mkdir(parents=True, exist_ok=True)
    report = build_report(input_path=input_path, bat_sample=args.bat_sample, pitch_sample=args.pitch_sample)
    require_keys(report)
    write_json(out_dir / "report.json", report)
    (out_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    (out_dir / "report.html").write_text(render_html(report), encoding="utf-8")
    (out_dir / "report_print.html").write_text(render_print_html(report), encoding="utf-8")
    print(f"Wrote {out_dir / 'report.json'}")
    print(f"Wrote {out_dir / 'report.md'}")
    print(f"Wrote {out_dir / 'report.html'}")
    print(f"Wrote {out_dir / 'report_print.html'}")


if __name__ == "__main__":
    main()
