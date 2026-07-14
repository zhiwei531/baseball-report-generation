import argparse
import csv
import json
import math
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

import pose3d_report
import stabilize_pose_video as pose


ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "outputs" / "slymask_benchmark_latest"

VIDEOS: list[dict[str, object]] = []


def default_pose_args(video_path, output_dir):
    return SimpleNamespace(
        input=video_path,
        output_dir=output_dir,
        max_frames=0,
        min_detection_confidence=0.45,
        min_tracking_confidence=0.55,
        model_complexity=2,
        visibility_threshold=0.18,
        quality_fast_limb_visibility=0.30,
        quality_core_visibility=0.46,
        quality_other_visibility=0.40,
        quality_aux_visibility=0.24,
        static_fast_limb_visibility=0.28,
        static_other_visibility=0.40,
        fusion_fast_limb_distance=0.075,
        fusion_other_distance=0.095,
        fusion_visibility_margin=0.15,
        person_center_jump_abs=0.22,
        person_center_jump_scale=0.70,
        person_scale_ratio_min=0.48,
        person_scale_ratio_max=1.85,
        body_jump_abs=0.24,
        body_jump_scale=0.58,
        core_smooth_seconds=0.10,
        limb_smooth_seconds=0.065,
        fast_limb_smooth_seconds=0.035,
    )


LM = pose.mp_pose.PoseLandmark


def finite_point(xyz, visibility, idx, min_vis=0.18):
    return visibility[idx] >= min_vis and np.isfinite(xyz[idx, :2]).all()


def mean_points(xyz, visibility, indices, min_vis=0.18):
    pts = [xyz[idx, :2] for idx in indices if finite_point(xyz, visibility, idx, min_vis)]
    if not pts:
        return None
    return np.mean(pts, axis=0)


def series_point(xyz, visibility, indices, min_vis=0.18):
    out = np.full((len(xyz), 2), np.nan, dtype=np.float32)
    for i in range(len(xyz)):
        p = mean_points(xyz[i], visibility[i], indices, min_vis)
        if p is not None:
            out[i] = p
    return fill_2d(out)


def fill_2d(points):
    filled = points.copy()
    for dim in range(2):
        values = filled[:, dim]
        valid = np.isfinite(values)
        if valid.sum() == 0:
            values[:] = 0.0
        elif valid.sum() == 1:
            values[:] = values[valid][0]
        else:
            values[:] = np.interp(np.arange(len(values)), np.where(valid)[0], values[valid])
        filled[:, dim] = values
    return filled


def body_scale_series(xyz, visibility):
    scales = np.full(len(xyz), np.nan, dtype=np.float32)
    for i in range(len(xyz)):
        _, scale = pose.person_center_and_scale(xyz[i, :, :2], visibility[i])
        if scale:
            scales[i] = scale
    valid = np.isfinite(scales)
    if valid.sum() == 0:
        scales[:] = 1.0
    else:
        scales = pose.interpolate_1d(scales, valid)
    return np.maximum(scales, 1e-3)


def line_angle(a, b):
    if a is None or b is None:
        return None
    d = b - a
    return math.degrees(math.atan2(-float(d[1]), float(d[0])))


def angle_diff(a, b):
    if a is None or b is None:
        return None
    diff = (a - b + 180.0) % 360.0 - 180.0
    return abs(diff)


def joint_angle_frame(xyz, a, b, c):
    try:
        return pose.calculate_angle(xyz[a, :2], xyz[b, :2], xyz[c, :2])
    except Exception:
        return None


def torso_tilt_frame(xyz, visibility, frame_idx):
    shoulder = mean_points(
        xyz[frame_idx],
        visibility[frame_idx],
        [LM.LEFT_SHOULDER.value, LM.RIGHT_SHOULDER.value],
    )
    hip = mean_points(
        xyz[frame_idx],
        visibility[frame_idx],
        [LM.LEFT_HIP.value, LM.RIGHT_HIP.value],
    )
    if shoulder is None or hip is None:
        return None
    vec = shoulder - hip
    return abs(math.degrees(math.atan2(float(vec[0]), -float(vec[1]))))


def plane_stability_score(points, scales, idxs):
    if len(idxs) < 5:
        return None
    pts = points[idxs]
    x = pts[:, 0]
    y = pts[:, 1]
    if np.nanstd(x) < 1e-5:
        residual = float(np.nanstd(y))
    else:
        coef = np.polyfit(x, y, 1)
        pred = coef[0] * x + coef[1]
        residual = float(np.nanmedian(np.abs(y - pred)))
    scale = float(np.nanmedian(scales[idxs]))
    return int(np.clip(100.0 - residual / max(scale, 1e-3) * 320.0, 0.0, 100.0))


def path_angle(points, idxs):
    if len(idxs) < 2:
        return None
    p0 = points[idxs[0]]
    p1 = points[idxs[-1]]
    angle = line_angle(p0, p1)
    if angle is None:
        return None
    if angle > 90:
        angle -= 180
    if angle < -90:
        angle += 180
    return angle


def normalize_score(value, low, high):
    if value is None:
        return None
    return int(np.clip((value - low) / max(high - low, 1e-6) * 100.0, 0.0, 100.0))


def quality_summary(data, frame_quality):
    n = len(frame_quality)
    green = sum(1 for item in frame_quality if item["quality_label"] == "green")
    yellow = sum(1 for item in frame_quality if item["quality_label"] == "yellow")
    red = sum(1 for item in frame_quality if item["quality_label"] == "red")
    keypoint_conf = float(np.nanmean(data["raw_visibility"][:, pose.BODY_JOINTS])) * 100.0
    usable = (green + yellow) / max(n, 1) * 100.0
    return {
        "frames": n,
        "green": green,
        "yellow": yellow,
        "red": red,
        "keypoint_confidence_pct": round(keypoint_conf, 1),
        "report_confidence_pct": int(np.clip(0.65 * keypoint_conf + 0.35 * usable, 0, 100)),
        "usable_candidate_pct": round(usable, 1),
    }


def metric(rows, video, group, name, key, value, unit="", status="输出", reason="", event="", method=""):
    if value is None and status == "输出":
        status = "不能输出"
        reason = reason or "关键点不足或事件窗口不可判定"
        unit = ""
    rows.append(
        {
            "video": video,
            "group": group,
            "metric": name,
            "key": key,
            "value": "" if value is None else value,
            "unit": unit,
            "status": status,
            "reason": reason,
            "event": event,
            "method": method,
        }
    )


def unavailable(rows, video, group, name, key, reason):
    metric(rows, video, group, name, key, None, "", "不能输出", reason)


def detect_motion_events(points, scales, fps):
    if len(points) < 5:
        return {"start": 0, "launch": 0, "peak": 0, "end": max(len(points) - 1, 0), "speed": np.zeros(len(points))}
    speed = np.zeros(len(points), dtype=np.float32)
    speed[1:] = np.linalg.norm(np.diff(points, axis=0), axis=1) / np.maximum(scales[1:], 1e-3) * fps
    if len(speed) >= 5:
        kernel = np.array([0.12, 0.22, 0.32, 0.22, 0.12], dtype=np.float32)
        speed = np.convolve(np.pad(speed, (2, 2), mode="edge"), kernel, mode="valid").astype(np.float32)
    lo = max(1, int(len(speed) * 0.08))
    hi = max(lo + 1, int(len(speed) * 0.96))
    valid_slice = speed[lo:hi]
    if valid_slice.size == 0:
        peak = int(np.nanargmax(speed))
    else:
        peak = int(np.nanargmax(valid_slice) + lo)
    peak_speed = float(speed[peak])
    floor = max(float(np.nanpercentile(valid_slice, 58)) if valid_slice.size else 0.0, peak_speed * 0.34)
    launch = peak
    while launch > lo and speed[launch] >= floor and peak - launch < int(round(fps * 0.45)):
        launch -= 1
    end = peak
    while end < hi - 1 and speed[end] >= floor and end - peak < int(round(fps * 0.45)):
        end += 1
    start = max(0, launch - int(round(fps * 0.08)))
    end = min(len(points) - 1, end + int(round(fps * 0.08)))
    return {"start": start, "launch": launch, "peak": peak, "end": end, "speed": speed}


def get_stage_indices(events):
    start = events["launch"]
    end = events["end"]
    return list(range(max(0, start), min(end + 1, len(events["speed"]))))


def analyze_hit(video_meta, data, stable_xyz, stable_visibility, frame_quality):
    label = video_meta["label"]
    fps = data["fps"]
    scales = body_scale_series(stable_xyz, stable_visibility)
    wrist = series_point(
        stable_xyz,
        stable_visibility,
        [LM.LEFT_WRIST.value, LM.RIGHT_WRIST.value],
    )
    pelvis = series_point(
        stable_xyz,
        stable_visibility,
        [LM.LEFT_HIP.value, LM.RIGHT_HIP.value],
    )
    head = series_point(stable_xyz, stable_visibility, [LM.NOSE.value, LM.LEFT_EAR.value, LM.RIGHT_EAR.value])
    events = detect_motion_events(wrist, scales, fps)
    active = get_stage_indices(events)
    start = events["start"]
    launch = events["launch"]
    contact = events["peak"]
    finish = events["end"]
    q = quality_summary(data, frame_quality)

    rows = []
    attack = path_angle(wrist, list(range(max(0, contact - 4), min(len(wrist), contact + 5))))
    attack = None if attack is None else int(round(attack))
    plane_score = plane_stability_score(wrist, scales, active)
    speed_window = events["speed"][max(0, events["launch"]): min(len(events["speed"]), events["end"] + 1)]
    max_hand_speed = float(np.nanpercentile(speed_window, 92)) if len(speed_window) else None
    swing_speed_score = normalize_score(max_hand_speed, 2.0, 8.0)
    estimated_bat_speed = None if max_hand_speed is None else int(round(np.clip(max_hand_speed * 7.6, 0, 140)))
    hit_time_ms = int(round((contact - launch) / fps * 1000.0))
    com_shift = float(np.linalg.norm(pelvis[contact] - pelvis[start]) / scales[contact] * 100.0)
    head_move = float(np.nanmax(np.linalg.norm(head[active] - np.nanmedian(head[active], axis=0), axis=1)) / np.nanmedian(scales[active]) * 100.0) if active else None
    head_stability = None if head_move is None else int(np.clip(100.0 - head_move * 4.0, 0, 100))
    torso_tilt = torso_tilt_frame(stable_xyz, stable_visibility, contact)

    shoulder_angle = line_angle(
        mean_points(stable_xyz[launch], stable_visibility[launch], [LM.LEFT_SHOULDER.value], 0.1),
        mean_points(stable_xyz[launch], stable_visibility[launch], [LM.RIGHT_SHOULDER.value], 0.1),
    )
    hip_angle = line_angle(
        mean_points(stable_xyz[launch], stable_visibility[launch], [LM.LEFT_HIP.value], 0.1),
        mean_points(stable_xyz[launch], stable_visibility[launch], [LM.RIGHT_HIP.value], 0.1),
    )
    separation = angle_diff(shoulder_angle, hip_angle)
    hip_angle_start = line_angle(
        mean_points(stable_xyz[start], stable_visibility[start], [LM.LEFT_HIP.value], 0.1),
        mean_points(stable_xyz[start], stable_visibility[start], [LM.RIGHT_HIP.value], 0.1),
    )
    hip_angle_contact = line_angle(
        mean_points(stable_xyz[contact], stable_visibility[contact], [LM.LEFT_HIP.value], 0.1),
        mean_points(stable_xyz[contact], stable_visibility[contact], [LM.RIGHT_HIP.value], 0.1),
    )
    hip_rotation = angle_diff(hip_angle_contact, hip_angle_start)

    front = "LEFT" if video_meta["side"] == "right" else "RIGHT"
    front_knee = joint_angle_frame(
        stable_xyz[contact],
        getattr(LM, f"{front}_HIP").value,
        getattr(LM, f"{front}_KNEE").value,
        getattr(LM, f"{front}_ANKLE").value,
    )
    heel = getattr(LM, f"{front}_HEEL").value
    foot = getattr(LM, f"{front}_FOOT_INDEX").value
    front_foot_angle = line_angle(stable_xyz[contact, heel, :2], stable_xyz[contact, foot, :2])

    left_forearm = line_angle(stable_xyz[max(contact - 3, 0), LM.LEFT_ELBOW.value, :2], stable_xyz[max(contact - 3, 0), LM.LEFT_WRIST.value, :2])
    right_forearm = line_angle(stable_xyz[min(contact + 3, len(stable_xyz) - 1), LM.RIGHT_ELBOW.value, :2], stable_xyz[min(contact + 3, len(stable_xyz) - 1), LM.RIGHT_WRIST.value, :2])
    wrist_flip = angle_diff(right_forearm, left_forearm)

    lower_body_score = normalize_score(com_shift, 8, 45)
    load_quality = normalize_score(separation, 8, 45)
    start_efficiency = normalize_score(max_hand_speed, 2.5, 7.0)
    swing_path_score = plane_score
    hit_stability = int(np.nanmean([v for v in [head_stability, plane_score] if v is not None])) if any(v is not None for v in [head_stability, plane_score]) else None

    path_type = "偏下压" if attack is not None and attack < -5 else "上挑" if attack is not None and attack > 10 else "平扫"

    metric(rows, label, "动作指标", "报告可信度", "report_confidence", q["report_confidence_pct"], "%", method="绿色/黄色可用帧比例 + 关键点可见性")
    metric(rows, label, "动作指标", "路径类型", "path_type", path_type, "", method="击球近似窗口内手腕轨迹角度")
    metric(rows, label, "动作指标", "攻击角", "attack_angle", attack, "deg", method="击球近似点前后手腕路径斜率")
    metric(rows, label, "动作指标", "平面稳定性", "plane_stability", plane_score, "/100", method="挥棒窗口手腕轨迹对拟合平面的残差")
    metric(rows, label, "动作指标", "推算棒头速度", "estimated_bat_head_speed", estimated_bat_speed, "km/h", method="手腕峰值速度按身体尺度粗略换算，非真实雷达")
    metric(rows, label, "动作链评分", "蓄力质量", "load_quality", load_quality, "/100", method="髋肩分离与启动前身体空间")
    metric(rows, label, "动作链评分", "下肢启动", "lower_body_start", lower_body_score, "/100", method="骨盆/重心从准备到击球近似点的位移")
    metric(rows, label, "动作链评分", "启动效率", "start_efficiency", start_efficiency, "/100", method="手部速度与启动到击球近似点时间")
    metric(rows, label, "动作链评分", "挥棒路径", "swing_path", swing_path_score, "/100", method="攻击角与挥棒平面稳定性")
    metric(rows, label, "动作链评分", "击球稳定", "hit_stability", hit_stability, "/100", method="头部稳定 + 挥棒平面")
    metric(rows, label, "蓄力与跨步", "髋肩分离", "hip_shoulder_separation", None if separation is None else int(round(separation)), "deg", event=f"launch frame {launch}")
    metric(rows, label, "蓄力与跨步", "重心转移", "center_of_mass_shift", int(round(com_shift)), "% body-scale", event=f"frame {start}->{contact}")
    metric(rows, label, "蓄力与跨步", "髋旋转", "hip_rotation", None if hip_rotation is None else int(round(hip_rotation)), "deg", event=f"frame {start}->{contact}")
    metric(rows, label, "蓄力与跨步", "前脚朝向", "front_foot_direction", None if front_foot_angle is None else int(round(front_foot_angle)), "deg", event=f"contact frame {contact}")
    metric(rows, label, "启动与击球近似", "挥棒速度", "swing_speed", swing_speed_score, "%", method="2D 手腕速度 proxy")
    metric(rows, label, "启动与击球近似", "击球时间", "contact_timing", hit_time_ms, "ms", method="启动帧到手腕峰速帧，不等同真实触球")
    metric(rows, label, "启动与击球近似", "手腕翻转", "wrist_roll", None if wrist_flip is None else int(round(wrist_flip)), "deg", method="前后臂方向变化 proxy")
    metric(rows, label, "稳定与收尾", "前膝角度", "front_knee_angle", None if front_knee is None else int(round(front_knee)), "deg", event=f"contact frame {contact}")
    metric(rows, label, "稳定与收尾", "躯干倾斜", "torso_tilt", None if torso_tilt is None else int(round(torso_tilt)), "deg", event=f"contact frame {contact}")
    metric(rows, label, "稳定与收尾", "头部稳定性", "head_stability", head_stability, "%", method="挥棒窗口头部相对身体尺度的移动")
    unavailable(rows, label, "能力边界", "真实球速/转速", "true_ball_speed_spin", "单目视频没有雷达、球追踪或球缝旋转数据")
    unavailable(rows, label, "能力边界", "球种质量/位移", "pitch_type_quality_movement", "没有球轨迹和旋转数据，无法判断变化球质量和球路位移")
    unavailable(rows, label, "能力边界", "真实触球瞬间", "true_contact_frame", "当前只用人体关键点，无法确认球棒与球的真实碰撞帧")

    events_out = {"start": start, "launch": launch, "contact_or_peak": contact, "finish": finish}
    return rows, events_out, q


def analyze_pitch(video_meta, data, stable_xyz, stable_visibility, frame_quality):
    label = video_meta["label"]
    fps = data["fps"]
    scales = body_scale_series(stable_xyz, stable_visibility)
    throwing = "RIGHT" if video_meta["side"] == "right" else "LEFT"
    front = "LEFT" if throwing == "RIGHT" else "RIGHT"
    wrist_idx = getattr(LM, f"{throwing}_WRIST").value
    index_idx = getattr(LM, f"{throwing}_INDEX").value
    elbow_idx = getattr(LM, f"{throwing}_ELBOW").value
    shoulder_idx = getattr(LM, f"{throwing}_SHOULDER").value
    front_hip = getattr(LM, f"{front}_HIP").value
    front_knee = getattr(LM, f"{front}_KNEE").value
    front_ankle = getattr(LM, f"{front}_ANKLE").value
    front_heel = getattr(LM, f"{front}_HEEL").value
    front_foot = getattr(LM, f"{front}_FOOT_INDEX").value

    wrist = series_point(stable_xyz, stable_visibility, [wrist_idx, index_idx])
    front_ankle_path = series_point(stable_xyz, stable_visibility, [front_ankle])
    pelvis = series_point(stable_xyz, stable_visibility, [LM.LEFT_HIP.value, LM.RIGHT_HIP.value])
    head = series_point(stable_xyz, stable_visibility, [LM.NOSE.value, LM.LEFT_EAR.value, LM.RIGHT_EAR.value])
    events = detect_motion_events(wrist, scales, fps)
    release = events["peak"]
    start = events["start"]
    finish = events["end"]
    stride_dist = np.linalg.norm(front_ankle_path - front_ankle_path[start], axis=1)
    foot_land = int(np.nanargmax(stride_dist[: max(release, 1)])) if release > 1 else start
    foot_land_observable = foot_land >= start and not (foot_land <= 3 and release > int(len(stable_xyz) * 0.30))
    active = get_stage_indices(events)
    q = quality_summary(data, frame_quality)

    speed_window = events["speed"][max(0, events["launch"]): min(len(events["speed"]), events["end"] + 1)]
    max_wrist_speed = float(np.nanpercentile(speed_window, 92)) if len(speed_window) else None
    finger = series_point(stable_xyz, stable_visibility, [index_idx])
    finger_speed = np.zeros(len(finger), dtype=np.float32)
    finger_speed[1:] = np.linalg.norm(np.diff(finger, axis=0), axis=1) / np.maximum(scales[1:], 1e-3) * fps
    max_finger_speed = float(np.nanmax(finger_speed)) if len(finger_speed) else None
    release_speed_score = normalize_score(max_wrist_speed, 2.0, 7.5)
    finger_speed_score = normalize_score(max_finger_speed, 2.0, 8.5)
    stride_len = float(np.linalg.norm(front_ankle_path[foot_land] - front_ankle_path[start]) / scales[foot_land] * 100.0)
    stride_angle = line_angle(front_ankle_path[start], front_ankle_path[foot_land])
    com_shift = float(np.linalg.norm(pelvis[release] - pelvis[start]) / scales[release] * 100.0)
    head_move = float(np.nanmax(np.linalg.norm(head[active] - np.nanmedian(head[active], axis=0), axis=1)) / np.nanmedian(scales[active]) * 100.0) if active else None
    head_stability = None if head_move is None else int(np.clip(100.0 - head_move * 4.0, 0, 100))
    torso_forward = torso_tilt_frame(stable_xyz, stable_visibility, release)
    elbow_flexion = joint_angle_frame(stable_xyz[release], shoulder_idx, elbow_idx, wrist_idx)
    arm_abduction = angle_diff(
        line_angle(stable_xyz[release, shoulder_idx, :2], stable_xyz[release, elbow_idx, :2]),
        line_angle(
            mean_points(stable_xyz[release], stable_visibility[release], [LM.LEFT_HIP.value, LM.RIGHT_HIP.value], 0.1),
            stable_xyz[release, shoulder_idx, :2],
        ),
    )
    front_knee_angle = joint_angle_frame(stable_xyz[foot_land], front_hip, front_knee, front_ankle)
    front_foot_angle = line_angle(stable_xyz[foot_land, front_heel, :2], stable_xyz[foot_land, front_foot, :2])
    shoulder_angle = line_angle(stable_xyz[release, LM.LEFT_SHOULDER.value, :2], stable_xyz[release, LM.RIGHT_SHOULDER.value, :2])
    hip_angle = line_angle(stable_xyz[release, LM.LEFT_HIP.value, :2], stable_xyz[release, LM.RIGHT_HIP.value, :2])
    separation = angle_diff(shoulder_angle, hip_angle)

    target_line_score = None if not foot_land_observable else plane_stability_score(front_ankle_path, scales, list(range(start, max(foot_land + 1, start + 2))))
    arm_path_score = plane_stability_score(wrist, scales, active)
    lower_body_score = normalize_score(com_shift, 8, 50)
    release_quality = int(np.nanmean([v for v in [release_speed_score, finger_speed_score, arm_path_score] if v is not None]))
    finish_stability = int(np.nanmean([v for v in [head_stability, target_line_score] if v is not None]))
    landing_pct = int(round(foot_land / max(len(stable_xyz) - 1, 1) * 100)) if foot_land_observable else None
    release_pct = int(round(release / max(len(stable_xyz) - 1, 1) * 100))
    wrist_snap = None
    if release >= 3 and release + 3 < len(finger_speed):
        wrist_snap = normalize_score(float(np.nanmax(finger_speed[release : release + 4]) - np.nanmedian(finger_speed[max(0, release - 8) : release + 1])), 0.2, 3.5)

    rows = []
    metric(rows, label, "动作指标", "报告可信度", "report_confidence", q["report_confidence_pct"], "%", method="绿色/黄色可用帧比例 + 关键点可见性")
    metric(rows, label, "动作指标", "出手时刻", "release_timing", release_pct, "% video", event=f"release approx frame {release}", method="手腕/指尖峰速帧")
    metric(
        rows,
        label,
        "动作指标",
        "前脚落地",
        "front_foot_landing",
        landing_pct,
        "% video",
        reason="" if foot_land_observable else "视频开始时前脚可能已经接近落地/跨步末段，无法确认真实落地帧",
        event=f"landing approx frame {foot_land}",
        method="前脚跨步位移最大帧",
    )
    metric(rows, label, "动作链评分", "下肢启动", "lower_body_start", lower_body_score, "/100", method="骨盆/重心向前转移")
    metric(rows, label, "动作链评分", "目标线控制", "target_line_control", target_line_score, "/100", method="前脚路径直线稳定性")
    metric(rows, label, "动作链评分", "髋肩分离", "hip_shoulder_separation_score", normalize_score(separation, 5, 45), "/100")
    metric(rows, label, "动作链评分", "手臂路径", "arm_path", arm_path_score, "/100", method="投球臂路径平滑/直线稳定")
    metric(rows, label, "动作链评分", "释放质量", "release_quality", release_quality, "/100", method="出手速度 + 指尖速度 + 手臂路径")
    metric(rows, label, "动作链评分", "收尾稳定", "finish_stability", finish_stability, "/100", method="出手后头部和前脚路径稳定性")
    metric(
        rows,
        label,
        "跨步与方向",
        "跨步角度",
        "stride_angle",
        None if (stride_angle is None or not foot_land_observable) else int(round(stride_angle)),
        "deg",
        reason="" if foot_land_observable else "前脚落地事件不在可观察窗口内",
        event=f"frame {start}->{foot_land}",
    )
    metric(
        rows,
        label,
        "跨步与方向",
        "跨步比",
        "stride_ratio",
        None if not foot_land_observable else int(round(stride_len)),
        "% body-scale",
        reason="" if foot_land_observable else "前脚落地事件不在可观察窗口内",
    )
    metric(rows, label, "跨步与方向", "重心转移", "center_of_mass_shift", int(round(com_shift)), "% body-scale")
    metric(rows, label, "跨步与方向", "前脚朝向", "front_foot_direction", None if front_foot_angle is None else int(round(front_foot_angle)), "deg")
    metric(rows, label, "力量传递", "髋肩分离", "hip_shoulder_separation", None if separation is None else int(round(separation)), "deg", event=f"release frame {release}")
    metric(rows, label, "力量传递", "躯干前倾", "torso_forward_lean", None if torso_forward is None else int(round(torso_forward)), "deg", event=f"release frame {release}")
    metric(rows, label, "力量传递", "前膝弯曲", "front_knee_bend", None if front_knee_angle is None else int(round(front_knee_angle)), "deg", event=f"landing frame {foot_land}")
    metric(rows, label, "力量传递", "头部稳定性", "head_stability", head_stability, "%")
    metric(rows, label, "手臂与释放", "肘弯曲", "elbow_flexion", None if elbow_flexion is None else int(round(elbow_flexion)), "deg", event=f"release frame {release}")
    metric(rows, label, "手臂与释放", "手臂外展", "arm_abduction", None if arm_abduction is None else int(round(arm_abduction)), "deg")
    metric(rows, label, "手臂与释放", "出手速度", "release_speed", release_speed_score, "%", method="2D 手腕峰速 proxy，非真实球速")
    metric(rows, label, "手臂与释放", "手腕弹动", "wrist_snap", wrist_snap, "%", method="出手前后指尖速度增量")
    metric(rows, label, "手臂与释放", "指尖速度", "fingertip_speed", finger_speed_score, "%", method="2D 食指峰速 proxy")
    unavailable(rows, label, "能力边界", "真实球速/转速", "true_ball_speed_spin", "手机单目视频没有雷达或稳定球追踪，不能判断真实球速和转速")
    unavailable(rows, label, "能力边界", "球种质量/位移", "pitch_type_quality_movement", "没有球轨迹与旋转数据，不能判断变化球质量和球路位移")
    unavailable(rows, label, "能力边界", "出球速度/发射角", "exit_velocity_launch_angle", "没有击球后球追踪，不能判断真实出球速度和发射角")
    unavailable(rows, label, "能力边界", "真实触球/出手瞬间", "true_ball_release_or_contact", "当前事件来自人体峰速近似，不等于球离手或碰撞的真实帧")

    events_out = {"start": start, "front_foot_land": foot_land, "release": release, "finish": finish}
    return rows, events_out, q


def draw_event_sheet(video_dir, data, stable_xyz, stable_visibility, events):
    frames = data["frames"]
    width = data["width"]
    height = data["height"]
    tiles = []
    for name, idx in events.items():
        idx = max(0, min(int(idx), len(frames) - 1))
        frame = pose.draw_pose(frames[idx], stable_xyz[idx], stable_visibility[idx], width, height, pose.STABLE_COLOR, name)
        cv2.putText(frame, f"{name} f{idx}", (24, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 0), 5, cv2.LINE_AA)
        cv2.putText(frame, f"{name} f{idx}", (24, 44), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (255, 255, 255), 2, cv2.LINE_AA)
        thumb_w = 360
        thumb_h = int(frame.shape[0] * (thumb_w / frame.shape[1]))
        tiles.append(cv2.resize(frame, (thumb_w, thumb_h), interpolation=cv2.INTER_AREA))
    if not tiles:
        return None
    max_h = max(tile.shape[0] for tile in tiles)
    padded = []
    for tile in tiles:
        if tile.shape[0] < max_h:
            pad = np.full((max_h - tile.shape[0], tile.shape[1], 3), 255, dtype=np.uint8)
            tile = np.vstack([tile, pad])
        padded.append(tile)
    sheet = np.hstack(padded)
    path = video_dir / "event_contact_sheet.jpg"
    ok, encoded = cv2.imencode(".jpg", sheet)
    if ok:
        path.write_bytes(encoded.tobytes())
    return path


def run_video(video_meta, output_dir):
    video_path = video_meta["path"]
    video_dir = output_dir / video_path.stem
    video_dir.mkdir(parents=True, exist_ok=True)
    args = default_pose_args(video_path, video_dir)
    pose.apply_runtime_config(args)
    baseline_data = pose.detect_video(video_path, args, static_image_mode=True, smooth_landmarks=False)
    tracking_data = pose.detect_video(video_path, args, static_image_mode=False, smooth_landmarks=True)
    data, fusion_replacements = pose.fuse_static_and_tracking(baseline_data, tracking_data)
    accepted, reason, _, scales = pose.reject_bad_frames(data["raw_xyz"], data["raw_visibility"], data["detected"])
    stable_xyz, stable_visibility, smoothing = pose.stabilize_landmarks(data["raw_xyz"], data["raw_visibility"], accepted, data["fps"])
    frame_quality = pose.classify_all_frames(data)

    if video_meta["kind"] == "hit":
        rows, events, q = analyze_hit(video_meta, data, stable_xyz, stable_visibility, frame_quality)
    else:
        rows, events, q = analyze_pitch(video_meta, data, stable_xyz, stable_visibility, frame_quality)

    sheet_path = draw_event_sheet(video_dir, data, stable_xyz, stable_visibility, events)
    _, stable_video_path, quality_video_path, compare_video_path = pose.write_videos(
        data, stable_xyz, stable_visibility, frame_quality, video_dir
    )
    pose3d_assets = pose3d_report.write_pose3d_assets(video_dir, data, stable_xyz, stable_visibility, events, video_path)
    payload = {
        "video": video_meta["label"],
        "path": str(video_path),
        "kind": video_meta["kind"],
        "side_assumption": video_meta["side"],
        "width": data["width"],
        "height": data["height"],
        "fps": data["fps"],
        "frames": len(data["frames"]),
        "accepted_frames": int(accepted.sum()),
        "tracking_detected_frames": int(tracking_data["detected"].sum()),
        "fusion_replacements": int(fusion_replacements),
        "events": events,
        "quality": q,
        "smoothing": smoothing,
        "event_contact_sheet": str(sheet_path) if sheet_path else "",
        "stable_pose_video": str(stable_video_path),
        "quality_pose_video": str(quality_video_path),
        "raw_vs_stable_video": str(compare_video_path),
        **pose3d_assets,
    }
    (video_dir / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return rows, payload


def write_report(output_dir, all_rows, summaries):
    report = output_dir / "Slymask_video_AI_benchmark_report.md"
    lines = [
        "# Slymask APP 视频 AI 分析 Benchmark",
        "",
        "## 结论摘要",
        "",
        "- 本次使用刚调好的视频稳定版 2D 姿态模型，对 2 个挥棒视频和 2 个投球视频输出 Slymask 页面中可见的身体类 metrics；心理/节奏分析已排除。",
        "- 可输出的指标主要来自人体 33 点姿态、时间平滑、动作事件近似和 2D 轨迹 proxy；所有“速度 % / 推算速度 / 击球或出手时刻”均为单目视频估算，不等同雷达、传感器或球追踪结果。",
        "- 不能输出或不建议输出的能力边界集中在真实球速/转速、球种质量/位移、真实触球瞬间、真实出球速度/发射角。",
        "",
        "## 视频与质量概览",
        "",
        "| 视频 | 类型 | 分辨率/FPS | 有效候选帧 | 报告可信度 | 事件抽帧 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for summary in summaries:
        q = summary["quality"]
        rel_sheet = Path(summary["event_contact_sheet"])
        sheet_label = rel_sheet.name if rel_sheet else ""
        lines.append(
            f"| {summary['video']} | {summary['kind']} | {summary['width']}x{summary['height']} / {summary['fps']:.2f} | "
            f"{q['usable_candidate_pct']}% | {q['report_confidence_pct']}% | {sheet_label} |"
        )

    groups = {}
    for row in all_rows:
        groups.setdefault(row["video"], []).append(row)
    for video, rows in groups.items():
        lines += ["", f"## {video}", "", "| 分组 | 指标 | 值 | 状态 | 说明 |", "|---|---|---:|---|---|"]
        for row in rows:
            value = "不能输出" if row["status"] == "不能输出" else f"{row['value']}{row['unit']}"
            note = row["reason"] or row["method"] or row["event"]
            lines.append(f"| {row['group']} | {row['metric']} | {value} | {row['status']} | {note} |")

    lines += [
        "",
        "## 口径说明",
        "",
        "- 击球近似点：使用双手腕/手部速度峰值帧估算，不保证等于真实触球帧。",
        "- 出手近似点：使用投球臂手腕/食指速度峰值帧估算，不保证等于真实球离手帧。",
        "- 角度指标：均为 2D 画面坐标计算，侧拍、斜拍、遮挡和透视会影响数值。",
        "- 速度指标：除 `km/h` 的推算棒头速度外，其余速度为百分制 proxy；推算棒头速度也不是雷达实测。",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description="Benchmark Slymask physical metrics with the tuned 2D pose model.")
    parser.add_argument("--video", action="append", required=True, type=Path, help="Repeat for each input video.")
    parser.add_argument("--kind", choices=["auto", "hit", "pitch"], default="auto")
    parser.add_argument("--side", choices=["right", "left"], default="right")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    all_rows = []
    summaries = []
    videos = []
    for path in args.video:
        path = path.resolve()
        if not path.exists():
            parser.error(f"Video not found: {path}")
        kind = args.kind
        if kind == "auto":
            kind = "pitch" if any(token in path.stem.lower() for token in ("pitch", "throw", "投球")) else "hit"
        videos.append({"path": path, "kind": kind, "label": path.stem, "side": args.side})
    for video_meta in videos:
        print(f"Processing {video_meta['label']}")
        rows, summary = run_video(video_meta, args.output_dir)
        all_rows.extend(rows)
        summaries.append(summary)

    csv_path = args.output_dir / "slymask_physical_metrics.csv"
    fieldnames = ["video", "group", "metric", "key", "value", "unit", "status", "reason", "event", "method"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_rows)

    json_path = args.output_dir / "slymask_physical_metrics.json"
    json_path.write_text(
        json.dumps({"summaries": summaries, "metrics": all_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    report_path = write_report(args.output_dir, all_rows, summaries)
    print(json.dumps({"csv": str(csv_path), "json": str(json_path), "report": str(report_path)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
