from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


METRIC_REGISTRY_VERSION = "legacy_v1"


@dataclass(frozen=True)
class LegacyMetricDefinition:
    metric_id: str
    display_name_zh: str
    display_name_en: str
    unit: str
    motion_type: str
    event_id: str | None
    section: str
    formula: str
    required_points: tuple[str, ...]
    side_rule: str | None
    missing_data_policy: str = "preserve_nan"
    report_options: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.metric_id or not self.display_name_zh or not self.display_name_en:
            raise ValueError("metric ID and display names are required")
        object.__setattr__(self, "required_points", tuple(self.required_points))
        object.__setattr__(self, "report_options", MappingProxyType(dict(self.report_options)))


def _batting(
    metric_id: str,
    name_zh: str,
    name_en: str,
    unit: str,
    event_id: str,
    section: str,
    formula: str,
    points: tuple[str, ...],
    side_rule: str | None = None,
) -> LegacyMetricDefinition:
    return LegacyMetricDefinition(
        metric_id=metric_id,
        display_name_zh=name_zh,
        display_name_en=name_en,
        unit=unit,
        motion_type="batting",
        event_id=event_id,
        section=section,
        formula=formula,
        required_points=points,
        side_rule=side_rule,
    )


BATTING_METRICS = (
    _batting("ready_com_height_ratio", "重心高度", "Ready Body Height", "height_ratio", "Ready Position", "Ready Position", "mean(COM_Z_ready_event) / height_proxy", ("CentreOfMass", "pelvis", "trunk", "head", "feet")),
    _batting("ready_rear_hip_flexion_deg", "后髋屈曲角", "Rear Hip Flexion", "deg", "Ready Position", "Ready Position", "180 - angle(shoulder_mid, rear_hip, rear_knee)", ("shoulder_mid", "rear_hip", "rear_knee"), "right-handed legacy: rear=R"),
    _batting("ready_rear_knee_flexion_deg", "后膝屈曲角", "Rear Knee Flexion", "deg", "Ready Position", "Ready Position", "180 - angle(rear_hip, rear_knee, rear_ankle)", ("rear_hip", "rear_knee", "rear_ankle"), "right-handed legacy: rear=R"),
    _batting("ready_hip_shoulder_separation_deg", "髋肩分离角", "Hip-Shoulder Separation", "deg", "Ready Position", "Ready Position", "abs(wrap_to_180(torso_rotation_xy - pelvis_rotation_xy))", ("pelvis", "shoulders")),
    _batting("ready_bat_tilt_deg", "球棒倾角", "Bat Angle at Ready", "deg", "Ready Position", "Ready Position", "atan2(abs(bat_axis_z), norm(bat_axis_xy))", ("Bat1", "Bat5")),
    _batting("ready_hand_height_ratio", "握棒手高度", "Hand Height at Ready", "height_ratio", "Ready Position", "Ready Position", "mean(grip_hand_center_Z_ready) / height_proxy", ("left_wrist", "right_wrist", "head", "feet")),
    _batting("contact_bat_speed_kmh", "球棒速度", "Bat Speed", "km/h", "Contact Position", "Contact Position", "mean(norm(diff(Bat1_xyz)/dt))*3.6/1000", ("Bat1",)),
    _batting("contact_attack_angle_deg", "挥棒路径角（Attack Angle）", "Attack Angle", "deg", "Contact Position", "Contact Position", "atan2(Bat1_velocity_Z, norm(Bat1_velocity_XY))", ("Bat1",)),
    _batting("contact_pelvis_rotation_open_deg", "骨盆旋转角", "Pelvis Rotation", "deg", "Contact Position", "Contact Position", "abs(wrap_to_180(pelvis_contact - pelvis_ready))", ("pelvis",)),
    _batting("contact_torso_rotation_open_deg", "躯干旋转角", "Torso Rotation", "deg", "Contact Position", "Contact Position", "abs(wrap_to_180(torso_contact - torso_ready))", ("shoulders",)),
    _batting("contact_front_knee_flexion_deg", "前膝屈曲角", "Front Knee Flexion", "deg", "Contact Position", "Contact Position", "180 - angle(front_hip, front_knee, front_ankle)", ("front_hip", "front_knee", "front_ankle"), "right-handed legacy: front=L"),
    _batting("ready_to_contact_head_displacement_mm", "头部位移", "Ready-to-Contact Head Displacement", "mm", "Ready to Contact", "Contact Position", "norm(mean(head_contact) - mean(head_ready))", ("head",)),
    _batting("coach_high_com_risk_index", "重心偏高指数", "High Center of Mass Risk", "0-100 risk", "Ready Position", "Coach Flag", "100*mean(clipped COM, rear hip, rear knee risks)", ("center_of_mass", "rear_hip", "rear_knee")),
    _batting("coach_rear_elbow_height_diff_mm", "后肘高度差（掉肘）", "Rear Elbow Height Difference", "mm", "Ready Position", "Coach Flag", "mean(rear_elbow_Z - rear_shoulder_Z)", ("rear_elbow", "rear_shoulder"), "right-handed legacy: rear=R"),
    _batting("coach_bat_loading_angle_to_catcher_deg", "球棒加载角（引棒不足）", "Bat Loading Angle", "deg", "Ready Position", "Coach Flag", "angle(project_xy(Bat5-Bat1), inferred_catcher_direction)", ("Bat1", "Bat5")),
    _batting("coach_rollover_forearm_roll_velocity_deg_s", "手腕翻转角速度（翻腕）", "Forearm Roll Velocity", "deg/s", "Contact Position", "Coach Flag", "max(abs(d/dt signed forearm roll angle))", ("rear_elbow", "rear_wrist_a", "rear_wrist_b"), "right-handed legacy: rear=R"),
    _batting("coach_hitting_zone_stability_score", "击球区稳定性", "Hitting Zone Stability", "0-100 score", "High-Speed Hitting Zone", "Coach Flag", "100*mean(path length, attack plane, curvature scores)", ("Bat1",)),
)
BATTING_METRICS_BY_ID = MappingProxyType({item.metric_id: item for item in BATTING_METRICS})


_PITCHING_ROWS = (
    ("knee_height_pct", "准备阶段", "抬腿最高点", "抬腿高度", "Knee Lift Height", "pct", "peak_knee", {"image": "peak_knee", "ideal": 50, "spread": 18, "copy": "抬腿高度接近身高一半，说明准备阶段有足够的节奏和空间。"}),
    ("front_knee_peak_deg", "准备阶段", "抬腿最高点", "前腿收紧", "Lead-Knee Tuck", "deg", "peak_knee", {"image": "peak_knee", "lo": 115, "hi": 155, "copy": "前膝角用来判断抬腿时前腿是否真正收住，而不是松散地向前摆。"}),
    ("rear_knee_peak_deg", "准备阶段", "抬腿最高点", "后腿蓄力", "Rear-Leg Load", "deg", "peak_knee", {"image": "peak_knee", "lo": -10, "hi": 25, "copy": "后腿在抬腿最高点承担支撑任务，角度越稳定，后续跨步越容易受控。"}),
    ("stride_distance_pct", "前脚落地", "落脚质量", "跨步距离", "Stride Distance", "pct", "foot_plant", {"image": "foot_plant", "ideal": 55, "spread": 22, "copy": "跨步距离用身高归一化，帮助判断身体推进是否足够。"}),
    ("stride_direction_deg", "前脚落地", "落脚质量", "跨步方向", "Stride Direction", "deg", "foot_plant", {"image": "foot_plant", "ideal": 0, "spread": 35, "copy": "跨步方向越接近目标线，身体越容易把力量送向投球方向。"}),
    ("front_knee_plant_deg", "前脚落地", "落地支撑", "前膝屈曲", "Lead-Knee Flexion", "deg", "foot_plant", {"image": "foot_plant", "lo": 40, "hi": 70, "copy": "前脚落地后的前膝角代表前腿支撑质量，过软或过硬都会影响传力。"}),
    ("rear_knee_plant_deg", "前脚落地", "落地支撑", "后膝屈曲", "Rear-Knee Flexion", "deg", "foot_plant", {"image": "foot_plant", "lo": 35, "hi": 75, "copy": "后膝角反映后腿是否还在参与推进，而不是提前失去下肢连接。"}),
    ("elbow_vs_shoulder_cm", "前脚落地", "手臂到位", "投球肘相对肩线", "Throwing-Elbow Height", "cm", "foot_plant", {"image": "foot_plant", "ideal": 0, "spread": 18, "copy": "负值表示肘低于肩线，前脚落地时肘的位置会影响后续出手路径。"}),
    ("shoulder_abduction_plant_deg", "前脚落地", "手臂到位", "肩外展", "Shoulder Abduction", "deg", "foot_plant", {"image": "foot_plant", "lo": 70, "hi": 100, "copy": "肩外展帮助判断投球手臂是否在落地时及时进入准备位置。"}),
    ("front_knee_release_deg", "出手点", "前腿制动", "出手前膝角", "Release Lead-Knee Angle", "deg", "release", {"image": "release", "lo": 40, "hi": 75, "copy": "出手时前腿能否稳住，是身体传力到手臂的重要前提。"}),
    ("front_knee_change_plant_to_release_deg", "出手点", "前腿制动", "落地到出手前膝变化", "Lead-Knee Change: Plant to Release", "deg", "release", {"image": "release", "ideal": 0, "spread": 18, "copy": "这个变化量越小，说明前腿在落地后越能保持支撑。"}),
    ("shoulder_abduction_release_deg", "出手点", "出手角度", "出手肩外展", "Release Shoulder Abduction", "deg", "release", {"image": "release", "lo": 80, "hi": 105, "copy": "出手时上臂抬起角度决定手臂路径和出手槽位。"}),
    ("elbow_flex_release_deg", "出手点", "出手角度", "出手肘屈曲", "Release Elbow Flexion", "deg", "release", {"image": "release", "lo": 60, "hi": 95, "copy": "肘屈曲角用于观察出手时手臂是否有足够延展和控制。"}),
    ("arm_slot_deg", "出手点", "出手角度", "出手手臂角度", "Release Arm Angle", "deg", "release", {"image": "release", "lo": 55, "hi": 85, "copy": "出手手臂角度描述前臂抬升方向，是观察投球手臂出手路径的核心指标。"}),
    ("release_height_pct", "出手点", "出手点", "出手高度", "Release Height", "pct", "release", {"image": "release", "lo": 85, "hi": 105, "copy": "以投球手手部位置近似出手点高度；后续可结合实际出手位置继续校准。"}),
    ("hand_speed_kmh", "出手点", "出手点", "出手手速", "Release Hand Speed", "kmh", "release", {"image": "release", "direction": "higher", "copy": "出手手速不是球速，但能作为同一套 Vicon 数据中的出手强度参考。"}),
    ("max_hss_deg", "专项问题", "身体带动程度", "最大髋肩分离", "Maximum Hip-Shoulder Separation", "deg", None, {"image": "release", "lo": 15, "hi": 35, "copy": "最大髋肩分离越清楚，说明身体有更明显的先后顺序。"}),
    ("hss_release_amount_deg", "专项问题", "身体带动程度", "髋肩分离释放量", "Hip-Shoulder Separation Release", "deg", None, {"image": "release", "lo": 8, "hi": 24, "copy": "释放量表示从最大分离到出手时释放了多少躯干旋转空间。"}),
)

PITCHING_METRICS = tuple(
    LegacyMetricDefinition(
        metric_id=metric_id,
        display_name_zh=name_zh,
        display_name_en=name_en,
        unit=unit,
        motion_type="pitching",
        event_id=event_id,
        section=section,
        formula="legacy pitching calculation; detailed formula retained in compute_values",
        required_points=(),
        side_rule="right-handed legacy: lead=L, drive/throwing=R",
        report_options={"event": event, **options},
    )
    for metric_id, event, section, name_zh, name_en, unit, event_id, options in _PITCHING_ROWS
)
PITCHING_METRICS_BY_ID = MappingProxyType({item.metric_id: item for item in PITCHING_METRICS})

PITCHING_AUXILIARY_UNITS = MappingProxyType(
    {
        "elbow_flex_plant_deg": "deg",
        "foot_contact_time_s": "s",
        "foot_plant_time_s": "s",
        "front_hip_peak_deg": "deg",
        "front_knee_change_contact_to_release_deg": "deg",
        "front_toe_direction_deg": "deg",
        "hss_peak_knee_deg": "deg",
        "hss_plant_deg": "deg",
        "hss_release_deg": "deg",
        "knee_height_mm": "mm",
        "max_hss_time_s": "s",
        "peak_knee_time_s": "s",
        "rear_ankle_peak_deg": "deg",
        "rear_knee_drive_extension_deg": "deg",
        "rear_knee_release_deg": "deg",
        "release_forward_mm": "mm",
        "release_height_mm": "mm",
        "release_lateral_mm": "mm",
        "release_time_s": "s",
        "shoulder_rotation_release_deg": "deg",
        "stride_distance_mm": "mm",
        "wrist_flex_release_deg": "deg",
        "wrist_vs_shoulder_cm": "cm",
    }
)

PITCHING_ALL_UNITS = MappingProxyType(
    {
        **{definition.metric_id: definition.unit for definition in PITCHING_METRICS},
        **PITCHING_AUXILIARY_UNITS,
    }
)

GENERIC_VICON_METRIC_UNITS = MappingProxyType(
    {
        "hip_shoulder_sep_deg": "deg",
        "lead_knee_angle_deg": "deg",
        "right_elbow_angle_deg": "deg",
        "left_elbow_angle_deg": "deg",
        "trunk_tilt_deg": "deg",
        "hand_speed_kmh": "km/h",
        "trunk_speed_kmh": "km/h",
        "hip_speed_kmh": "km/h",
        "bat_speed_kmh": "km/h",
        "swing_time_sec": "s",
        "bat_angle_deg": "deg",
    }
)


def pitching_metric_dicts() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for definition in PITCHING_METRICS:
        options = dict(definition.report_options)
        event = options.pop("event")
        rows.append(
            {
                "key": definition.metric_id,
                "event": event,
                "section": definition.section,
                "name": definition.display_name_zh,
                "en": definition.display_name_en,
                "unit": definition.unit,
                **options,
            }
        )
    return rows
