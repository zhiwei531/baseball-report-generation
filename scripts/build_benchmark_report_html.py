from __future__ import annotations

import csv
import hashlib
import html
import math
from pathlib import Path

from build_vicon_2026_metrics import marker, read_c3d


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "report.html"
MAIN_ATHLETE = "bryan"
COMPARE_ATHLETE = "green"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def zh_text(value: object) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "cm": "厘米",
        "proxy": "估算",
        "N/A": "暂无",
        "CV": "视频识别",
        "Vicon": "光学动作捕捉",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def stable_id(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def num(value: str | float | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


UNIT_CN = {
    "deg": "度",
    "deg/s": "度/秒",
    "m/s": "米/秒",
    "cm": "厘米",
    "%": "%",
    "%height": "身高百分比",
    "%stride": "跨步百分比",
    "height_ratio": "身高比",
    "s": "秒",
    "km/h": "公里/小时",
    "ms": "毫秒",
}


ATHLETE_HEIGHT_M = 1.55
CLIP_CALIBRATION = {
    # width/height/fps from source videos; body_height_px is median visible 2D pose height.
    "benchmark_pitch_vertical_10": {"width": 1080, "height": 1920, "fps": 59.9606, "body_height_px": 596.8},
    "benchmark_pitch_vertical_09": {"width": 1080, "height": 1920, "fps": 59.9429, "body_height_px": 846.2},
    "benchmark_hit_vertical_02": {"width": 1080, "height": 1920, "fps": 59.9781, "body_height_px": 861.3},
    "benchmark_hit_horizontal_06": {"width": 1920, "height": 1080, "fps": 59.9455, "body_height_px": 378.4},
}


METRIC_CN = {
    "Motion Phase Start": "动作阶段开始",
    "Motion Phase Event": "关键事件",
    "Motion Phase End": "动作阶段结束",
    "Hip-Shoulder Sep": "髋肩分离",
    "Lead Knee Angle": "前腿膝角",
    "Trunk Tilt": "躯干倾斜",
    "Weight Transfer": "重心转移",
    "Head Stability": "头部稳定",
    "Dominant Side": "发力侧",
    "Lead Side": "前侧脚",
    "Elbow Bend": "肘部弯曲",
    "Arm Abduction": "上臂外展",
    "Stride Angle": "跨步角",
    "Stride Length": "跨步长度",
    "Foot Direction": "前脚方向",
    "Wrist Snap": "手腕翻转",
    "Arm Speed": "手臂速度",
    "Fingertip Speed": "手部速度",
    "Ball Speed": "球速估算",
    "Swing Speed": "挥棒速度估算",
    "Attack Angle": "攻击角",
    "Estimated Bat Speed": "球棒速度估算",
    "Bat Speed": "球棒速度",
    "Hand Speed": "手部速度",
    "Trunk Speed": "躯干速度",
    "Hip Speed": "髋部速度",
    "Hip Rotation": "髋部旋转",
    "Contact Time": "接触时间",
    "Wrist/Hand Speed": "腕手速度",
}


SOURCE_CN = {
    "3d_pose": "三维姿态",
    "object_2d": "二维球追踪",
    "none": "暂无来源",
}


STATUS_CN = {
    "ok": ("良好", "good"),
    "available": ("良好", "good"),
    "warn": ("需复核", "review"),
    "proxy": ("需复核", "review"),
    "bad": ("关注", "risk"),
    "unavailable": ("不可用", "na"),
    "": ("不可用", "na"),
}


CLIP_CN = {
    "benchmark_pitch_vertical_09": "投球09",
    "benchmark_pitch_vertical_10": "投球10",
    "benchmark_hit_vertical_02": "打击02",
    "benchmark_hit_horizontal_06": "打击06",
}


def metric_cn(name: str | None) -> str:
    return METRIC_CN.get(name or "", name or "未命名指标")


def source_cn(value: str | None) -> str:
    return SOURCE_CN.get(value or "", "汇总数据")


def status_cn(value: str | None) -> tuple[str, str]:
    return STATUS_CN.get(value or "", ("需复核", "review"))


def unit_cn(value: str | None) -> str:
    return UNIT_CN.get(value or "", value or "")


def fmt(value: str | float | None, unit: str | None = "") -> str:
    x = num(value)
    if x is None:
        return "暂无"
    if abs(x) >= 100:
        text = f"{x:.1f}"
    elif abs(x) >= 10:
        text = f"{x:.1f}"
    else:
        text = f"{x:.2f}"
    u = unit_cn(unit)
    return f"{text}{u}" if u in {"%", "度"} else f"{text} {u}".strip()


def px_speed_to_kmh(clip_id: str, value: str | float | None) -> float | None:
    x = num(value)
    calib = CLIP_CALIBRATION.get(clip_id)
    if x is None or not calib:
        return None
    meters_per_pixel = ATHLETE_HEIGHT_M / float(calib["body_height_px"])
    return x * meters_per_pixel * 3.6


def fmt_metric_value(row: dict[str, str], all_rows: list[dict[str, str]] | None = None) -> str:
    unit = row.get("unit", "")
    metric = row.get("metric_name", "")
    clip = row.get("clip_id", "")
    if unit == "px/s":
        return "约" + fmt(px_speed_to_kmh(clip, row.get("value")), "km/h")
    if unit == "norm/s" and metric == "Swing Speed" and all_rows is not None:
        bat_speed = next(
            (
                candidate
                for candidate in all_rows
                if candidate.get("clip_id") == clip and candidate.get("metric_name") == "Estimated Bat Speed"
            ),
            None,
        )
        if bat_speed is not None:
            return "约" + fmt(px_speed_to_kmh(clip, bat_speed.get("value")), "km/h")
        return "需球棒标定"
    if unit == "3d_unit/s":
        return "需标定"
    return fmt(row.get("value"), unit)


def find_metric(rows: list[dict[str, str]], clip: str, metric: str) -> dict[str, str] | None:
    for row in rows:
        if row.get("clip_id") == clip and row.get("metric_name") == metric:
            return row
    return None


def clip_metrics(rows: list[dict[str, str]], clip: str, names: list[str]) -> list[dict[str, str]]:
    return [row for name in names if (row := find_metric(rows, clip, name))]


def score_ratio(child: float | None, coach: float | None, inverse: bool = False) -> int:
    if child is None or coach in (None, 0):
        return 45
    ratio = child / coach
    if inverse:
        ratio = coach / child if child else 0
    return max(5, min(100, round(ratio * 100)))


def score_close(child: float | None, coach: float | None, tolerance: float) -> int:
    if child is None or coach is None:
        return 45
    diff = abs(child - coach)
    return max(10, min(100, round(100 - diff / tolerance * 100)))


def radar_svg(labels: list[str], values: list[int], color: str = "#4f5eea") -> str:
    cx = 160
    cy = 142
    outer = 86
    rings = []
    for scale in (0.33, 0.66, 1.0):
        pts = []
        for i in range(len(labels)):
            angle = -math.pi / 2 + 2 * math.pi * i / len(labels)
            pts.append(f"{cx + math.cos(angle) * outer * scale:.1f},{cy + math.sin(angle) * outer * scale:.1f}")
        rings.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#d0d5dd" stroke-width="1"/>')
    axes = []
    label_tags = []
    data_pts = []
    for i, (label, value) in enumerate(zip(labels, values)):
        angle = -math.pi / 2 + 2 * math.pi * i / len(labels)
        x = cx + math.cos(angle) * outer
        y = cy + math.sin(angle) * outer
        axes.append(f'<line x1="{cx}" y1="{cy}" x2="{x:.1f}" y2="{y:.1f}" stroke="#d0d5dd"/>')
        lx = cx + math.cos(angle) * 112
        ly = cy + math.sin(angle) * 112
        label_tags.append(f'<text x="{lx:.1f}" y="{ly:.1f}" text-anchor="middle">{esc(label)}</text>')
        data_pts.append(f"{cx + math.cos(angle) * outer * value / 100:.1f},{cy + math.sin(angle) * outer * value / 100:.1f}")
    return f"""
    <svg class="radar" viewBox="0 0 320 290" role="img" aria-label="六维评分图">
      <g class="grid-lines">{''.join(rings)}{''.join(axes)}</g>
      <polygon points="{' '.join(data_pts)}" fill="{color}33" stroke="{color}" stroke-width="4"/>
      <circle cx="{cx}" cy="{cy}" r="3" fill="{color}"/>
      <g class="radar-labels">{''.join(label_tags)}</g>
    </svg>
    """


def skeleton_svg(kind: str) -> str:
    if kind == "pitch":
        path = '<path d="M55 238 C160 180 286 132 452 70" fill="none" stroke="#f97316" stroke-width="13" stroke-linecap="round" opacity=".5"/>'
    else:
        path = '<path d="M56 224 C160 196 300 168 468 116" fill="none" stroke="#f97316" stroke-width="13" stroke-linecap="round" opacity=".5"/>'
    return f"""
    <svg class="pose-svg" viewBox="0 0 520 330" role="img" aria-label="动作截图角度标注示意">
      <rect x="0" y="0" width="520" height="330" rx="18" fill="#101828"/>
      {path}
      <g stroke="#60a5fa" stroke-width="7" stroke-linecap="round" stroke-linejoin="round">
        <line x1="250" y1="82" x2="224" y2="144"/><line x1="224" y1="144" x2="248" y2="206"/>
        <line x1="224" y1="144" x2="164" y2="134"/><line x1="164" y1="134" x2="108" y2="110"/>
        <line x1="224" y1="144" x2="292" y2="138"/><line x1="292" y1="138" x2="358" y2="88"/>
        <line x1="248" y1="206" x2="188" y2="258"/><line x1="248" y1="206" x2="326" y2="258"/>
      </g>
      <g fill="#fff"><circle cx="250" cy="82" r="13"/><circle cx="224" cy="144" r="8"/><circle cx="248" cy="206" r="8"/><circle cx="108" cy="110" r="8"/><circle cx="358" cy="88" r="8"/><circle cx="188" cy="258" r="8"/><circle cx="326" cy="258" r="8"/></g>
      <path d="M188 258 A56 56 0 0 1 248 206" fill="none" stroke="#16a34a" stroke-width="4"/>
      <path d="M224 144 A72 72 0 0 1 292 138" fill="none" stroke="#ef4444" stroke-width="4"/>
      <g><rect x="24" y="22" width="58" height="30" rx="15" fill="rgba(255,255,255,.14)"/><text x="53" y="42" text-anchor="middle" fill="#fff" font-size="14" font-weight="600">示意</text></g>
    </svg>
    """


def standard_overlay_svg() -> str:
    return """
    <svg class="pose-svg" viewBox="0 0 620 320" role="img" aria-label="标准姿态纠正图">
      <rect width="620" height="320" rx="18" fill="#ffffff"/>
      <g fill="none" stroke-linecap="round" stroke-linejoin="round" stroke-width="7">
        <g stroke="#60a5fa" stroke-dasharray="10 10">
          <line x1="280" y1="62" x2="252" y2="128"/><line x1="252" y1="128" x2="272" y2="204"/><line x1="252" y1="128" x2="176" y2="132"/><line x1="252" y1="128" x2="334" y2="120"/><line x1="334" y1="120" x2="410" y2="84"/><line x1="272" y1="204" x2="206" y2="268"/><line x1="272" y1="204" x2="360" y2="260"/>
        </g>
        <g stroke="#16a34a">
          <line x1="278" y1="62" x2="246" y2="128"/><line x1="246" y1="128" x2="262" y2="204"/><line x1="246" y1="128" x2="156" y2="126"/><line x1="246" y1="128" x2="338" y2="116"/><line x1="338" y1="116" x2="438" y2="72"/><line x1="262" y1="204" x2="178" y2="268"/><line x1="262" y1="204" x2="374" y2="260"/>
        </g>
        <g stroke="#ef4444">
          <line x1="334" y1="120" x2="410" y2="84"/><line x1="272" y1="204" x2="206" y2="268"/>
        </g>
      </g>
      <g><rect x="24" y="22" width="58" height="30" rx="15" fill="#eef6ff"/><text x="53" y="42" text-anchor="middle" fill="#2563eb" font-size="14" font-weight="600">示意</text></g>
    </svg>
    """


def read_pose_sequence(path: Path) -> list[dict[str, object]]:
    rows = read_csv(path)
    by_frame: dict[int, dict[str, object]] = {}
    qualities: dict[int, list[float]] = {}
    for row in rows:
        frame_idx = num(row.get("frame_index"))
        if frame_idx is None:
            continue
        idx = int(frame_idx)
        frame = by_frame.setdefault(
            idx,
            {"frame": idx, "time": num(row.get("timestamp_sec")) or 0.0, "joints": {}},
        )
        joints = frame["joints"]  # type: ignore[assignment]
        joints[row["joint_name"]] = (
            num(row.get("x_3d")) or 0.0,
            num(row.get("y_3d")) or 0.0,
            num(row.get("z_3d")) or 0.0,
        )
        q = num(row.get("input_quality_score") or row.get("confidence"))
        if q is not None:
            qualities.setdefault(idx, []).append(q)
    frames = []
    for idx in sorted(by_frame):
        frame = by_frame[idx]
        qs = qualities.get(idx, [])
        frame["quality"] = sum(qs) / len(qs) if qs else None
        frames.append(frame)
    return frames


def v_sub(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_len(a: tuple[float, float, float]) -> float:
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def midpoint(points: list[tuple[float, float, float]]) -> tuple[float, float, float] | None:
    if not points:
        return None
    return (
        sum(p[0] for p in points) / len(points),
        sum(p[1] for p in points) / len(points),
        sum(p[2] for p in points) / len(points),
    )


def joint_mid(joints: dict[str, tuple[float, float, float]], names: list[str]) -> tuple[float, float, float] | None:
    return midpoint([joints[name] for name in names if name in joints])


def angle_at(
    joints: dict[str, tuple[float, float, float]],
    a: str,
    b: str,
    c: str,
) -> float | None:
    if a not in joints or b not in joints or c not in joints:
        return None
    ba = v_sub(joints[a], joints[b])
    bc = v_sub(joints[c], joints[b])
    denom = v_len(ba) * v_len(bc)
    if denom == 0:
        return None
    cos_v = max(-1.0, min(1.0, sum(ba[i] * bc[i] for i in range(3)) / denom))
    return math.degrees(math.acos(cos_v))


def trunk_tilt(joints: dict[str, tuple[float, float, float]]) -> float | None:
    hip = joints.get("hip")
    neck = joints.get("neck")
    if hip is None or neck is None:
        return None
    vec = v_sub(neck, hip)
    return math.degrees(math.atan2(abs(vec[0]), max(abs(vec[1]), 1e-6)))


def hip_shoulder_sep(joints: dict[str, tuple[float, float, float]]) -> float | None:
    lh, rh = joints.get("left_hip"), joints.get("right_hip")
    ls, rs = joints.get("left_shoulder"), joints.get("right_shoulder")
    if None in (lh, rh, ls, rs):
        return None
    hip_angle = math.degrees(math.atan2(lh[2] - rh[2], lh[0] - rh[0]))  # type: ignore[index]
    shoulder_angle = math.degrees(math.atan2(ls[2] - rs[2], ls[0] - rs[0]))  # type: ignore[index]
    diff = abs((shoulder_angle - hip_angle + 180) % 360 - 180)
    return diff


def pose_angle_series(frames: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    rows = [
        {"name": "前腿膝角", "unit": "deg", "color": "#2563eb", "values": []},
        {"name": "肘角", "unit": "deg", "color": "#f97316", "values": []},
        {"name": "躯干倾斜", "unit": "deg", "color": "#7c4dff", "values": []},
        {"name": "髋肩分离", "unit": "deg", "color": "#16a34a", "values": []},
    ]
    knee = ("left_hip", "left_knee", "left_ankle") if kind == "pitch" else ("right_hip", "right_knee", "right_ankle")
    elbow = ("right_shoulder", "right_elbow", "right_wrist")
    for frame in frames:
        t = float(frame["time"])
        joints = frame["joints"]  # type: ignore[assignment]
        values = [
            angle_at(joints, *knee),
            angle_at(joints, *elbow),
            trunk_tilt(joints),
            hip_shoulder_sep(joints),
        ]
        for row, value in zip(rows, values):
            row["values"].append((t, value))
    return rows


def point_for_speed(joints: dict[str, tuple[float, float, float]], names: list[str]) -> tuple[float, float, float] | None:
    if len(names) == 1:
        return joints.get(names[0])
    return joint_mid(joints, names)


def pose_speed_series(frames: list[dict[str, object]], kind: str) -> list[dict[str, object]]:
    specs = [
        ("髋部中心速度", ["hip"], "#2563eb"),
        ("躯干中心速度", ["spine2", "spine3", "neck"], "#7c4dff"),
        ("出手侧手部速度" if kind == "pitch" else "手部末端速度", ["right_wrist", "right_hand"], "#f97316"),
    ]
    rows = [{"name": name, "unit": "km/h", "color": color, "values": []} for name, _, color in specs]
    prev: list[tuple[float, tuple[float, float, float]] | None] = [None for _ in specs]
    for frame in frames:
        t = float(frame["time"])
        joints = frame["joints"]  # type: ignore[assignment]
        for i, (_, names, _) in enumerate(specs):
            point = point_for_speed(joints, names)
            value = None
            if point is not None and prev[i] is not None:
                prev_t, prev_point = prev[i]  # type: ignore[misc]
                dt = t - prev_t
                if dt > 0:
                    value = v_len(v_sub(point, prev_point)) / dt * 3.6
            rows[i]["values"].append((t, value))
            if point is not None:
                prev[i] = (t, point)
    return rows


def peak_speed_frame(frames: list[dict[str, object]], names: list[str]) -> int:
    best_frame = int(frames[len(frames) // 2]["frame"]) if frames else 0
    best_value = -1.0
    prev: tuple[float, tuple[float, float, float]] | None = None
    for frame in frames:
        t = float(frame["time"])
        joints = frame["joints"]  # type: ignore[assignment]
        point = point_for_speed(joints, names)
        if point is not None and prev is not None:
            prev_t, prev_point = prev
            dt = t - prev_t
            if dt > 0:
                value = v_len(v_sub(point, prev_point)) / dt
                if value > best_value:
                    best_value = value
                    best_frame = int(frame["frame"])
        if point is not None:
            prev = (t, point)
    return best_frame


def line_chart_svg(
    title: str,
    series: list[dict[str, object]],
    events: list[tuple[str, float | None]],
    y_label: str,
) -> str:
    width, height = 720, 360
    left, right, top, bottom = 116, 678, 88, 276
    times = [t for row in series for t, v in row["values"] if v is not None]  # type: ignore[index]
    values = [v for row in series for _, v in row["values"] if v is not None]  # type: ignore[index]
    if not times or not values:
        return line_placeholder_svg(title)
    t0, t1 = min(times), max(times)
    lo, hi = min(values), max(values)
    pad = max((hi - lo) * 0.12, 1.0)
    lo -= pad
    hi += pad
    if t0 == t1:
        t1 += 1
    if lo == hi:
        hi += 1

    def x_for(t: float) -> float:
        return left + (t - t0) / (t1 - t0) * (right - left)

    def y_for(v: float) -> float:
        return bottom - (v - lo) / (hi - lo) * (bottom - top)

    paths = []
    for row in series:
        points = [(x_for(t), y_for(v)) for t, v in row["values"] if v is not None]  # type: ignore[index]
        if len(points) < 2:
            continue
        d = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)
        paths.append(f'<path d="{d}" fill="none" stroke="{row["color"]}" stroke-width="3" stroke-linejoin="round"/>')
        peak_t, peak_v = max(((t, v) for t, v in row["values"] if v is not None), key=lambda item: item[1])  # type: ignore[index]
        paths.append(f'<circle cx="{x_for(peak_t):.1f}" cy="{y_for(peak_v):.1f}" r="4" fill="{row["color"]}"/>')

    event_tags = []
    for idx, (label, t) in enumerate(events):
        if t is None or t < t0 or t > t1:
            continue
        x = x_for(t)
        label_w = max(70, len(label) * 14 + 20)
        label_x = max(left + label_w / 2, min(right - label_w / 2, x))
        label_y = 44 + (idx % 2) * 24
        event_tags.append(f'<line x1="{x:.1f}" y1="{top}" x2="{x:.1f}" y2="{bottom}" stroke="#101828" stroke-width="2" stroke-dasharray="5 5" opacity=".65"/>')
        event_tags.append(f'<rect x="{label_x - label_w / 2:.1f}" y="{label_y - 15}" width="{label_w:.1f}" height="20" rx="10" fill="#f8fafc" stroke="#d0d5dd"/>')
        event_tags.append(f'<path d="M{label_x:.1f} {label_y + 5} L{x:.1f} {top - 4}" stroke="#98a2b3" stroke-width="1" fill="none"/>')
        event_tags.append(f'<text x="{label_x:.1f}" y="{label_y}" text-anchor="middle" fill="#101828" font-size="11">{esc(label)}</text>')

    legend_x = left
    legend_tags = []
    for row in series:
        legend_tags.append(f'<circle cx="{legend_x}" cy="326" r="6" fill="{row["color"]}"/>')
        legend_tags.append(f'<text x="{legend_x + 12}" y="331" fill="#344054" font-size="12">{esc(row["name"])}</text>')
        legend_x += 150

    clip_id = f"clip-{stable_id(title)}"
    return f"""
    <div class="line-chart-scroll"><svg class="line-chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">
      <defs><clipPath id="{clip_id}"><rect x="{left}" y="{top}" width="{right - left}" height="{bottom - top}"/></clipPath></defs>
      <rect width="{width}" height="{height}" rx="18" fill="#ffffff"/>
      <text x="24" y="24" fill="#101828" font-size="14" font-weight="700">{esc(title)}</text>
      <line x1="{left}" y1="{bottom}" x2="{right}" y2="{bottom}" stroke="#667085"/>
      <line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" stroke="#667085"/>
      <g stroke="#e4e7ec" stroke-width="1">
        <line x1="{left}" y1="{(top+bottom)/2:.1f}" x2="{right}" y2="{(top+bottom)/2:.1f}"/>
        <line x1="{left}" y1="{top}" x2="{right}" y2="{top}"/>
      </g>
      <text x="{left}" y="{bottom + 24}" fill="#667085" font-size="12">时间（秒）</text>
      <text x="24" y="{top - 16}" fill="#667085" font-size="12">{esc(y_label)}</text>
      <rect x="18" y="{bottom - 12}" width="{left - 32}" height="20" rx="8" fill="#ffffff"/>
      <rect x="18" y="{top - 12}" width="{left - 32}" height="20" rx="8" fill="#ffffff"/>
      <text x="{left - 14}" y="{bottom + 4}" text-anchor="end" fill="#98a2b3" font-size="11">{esc(fmt(lo, str(series[0].get("unit", ""))))}</text>
      <text x="{left - 14}" y="{top + 4}" text-anchor="end" fill="#98a2b3" font-size="11">{esc(fmt(hi, str(series[0].get("unit", ""))))}</text>
      {''.join(event_tags)}
      <g clip-path="url(#{clip_id})">{''.join(paths)}</g>
      {''.join(legend_tags)}
    </svg></div>
    """


def pose_quality_svg(items: list[tuple[str, list[dict[str, object]], str]]) -> str:
    width, height = 720, 280
    left, right, top = 156, 612, 44
    row_h = 50
    tags = [f'<rect width="{width}" height="{height}" rx="18" fill="#ffffff"/>']
    tags.append('<text x="24" y="26" fill="#101828" font-size="14" font-weight="700">三维姿态数据质量图</text>')
    for i, (label, frames, color) in enumerate(items):
        y = top + i * row_h
        frame_count = len(frames)
        quality_values = [frame.get("quality") for frame in frames if frame.get("quality") is not None]
        quality = sum(quality_values) / len(quality_values) if quality_values else 0.0
        joint_counts = [len(frame["joints"]) for frame in frames]  # type: ignore[arg-type]
        max_joints = max(joint_counts or [1])
        complete = (sum(joint_counts) / len(joint_counts) / max_joints) if joint_counts else 0.0
        score = max(0.0, min(1.0, quality if quality else complete))
        bar_w = max(0, min(right - left, (right - left) * score))
        tags.append(f'<text x="24" y="{y + 5}" fill="#101828" font-size="13" font-weight="700">{esc(label)}</text>')
        tags.append(f'<text x="24" y="{y + 24}" fill="#667085" font-size="11">{frame_count}帧，关节完整率约{complete*100:.1f}%</text>')
        tags.append(f'<line x1="{left}" y1="{y}" x2="{right}" y2="{y}" stroke="#e8eef6" stroke-width="16" stroke-linecap="round"/>')
        tags.append(f'<line x1="{left}" y1="{y}" x2="{left + bar_w:.1f}" y2="{y}" stroke="{color}" stroke-width="16" stroke-linecap="round"/>')
        tags.append(f'<text x="{right + 10}" y="{y + 5}" fill="#344054" font-size="12">{score*100:.1f}%</text>')
    return f'<div class="line-chart-scroll"><svg class="line-chart-svg" viewBox="0 0 {width} {height}" role="img" aria-label="三维姿态数据质量图">{"".join(tags)}</svg></div>'


def frame_by_index(frames: list[dict[str, object]], idx: int) -> dict[str, object]:
    return min(frames, key=lambda frame: abs(int(frame["frame"]) - idx))


def posture_overlay_svg(
    child_frames: list[dict[str, object]],
    coach_frames: list[dict[str, object]],
    child_frame_idx: int,
    coach_frame_idx: int,
) -> str:
    child = frame_by_index(child_frames, child_frame_idx)
    coach = frame_by_index(coach_frames, coach_frame_idx)
    child_joints = child["joints"]  # type: ignore[assignment]
    coach_joints = coach["joints"]  # type: ignore[assignment]
    segments = [
        ("head", "neck"), ("neck", "spine2"), ("spine2", "hip"),
        ("left_shoulder", "left_elbow"), ("left_elbow", "left_wrist"), ("left_wrist", "left_hand"),
        ("right_shoulder", "right_elbow"), ("right_elbow", "right_wrist"), ("right_wrist", "right_hand"),
        ("left_hip", "left_knee"), ("left_knee", "left_ankle"), ("left_ankle", "left_foot"),
        ("right_hip", "right_knee"), ("right_knee", "right_ankle"), ("right_ankle", "right_foot"),
        ("left_shoulder", "right_shoulder"), ("left_hip", "right_hip"),
    ]

    def project(joints: dict[str, tuple[float, float, float]]) -> dict[str, tuple[float, float]]:
        hip = joints.get("hip") or (0.0, 0.0, 0.0)
        neck = joints.get("neck") or (0.0, 1.0, 0.0)
        scale = 132 / max(v_len(v_sub(neck, hip)), 0.1)
        return {
            name: (310 + (point[0] - hip[0]) * scale, 230 - (point[1] - hip[1]) * scale)
            for name, point in joints.items()
        }

    child_xy = project(child_joints)
    coach_xy = project(coach_joints)
    deviations = []
    for a, b in segments:
        if a in child_xy and b in child_xy and a in coach_xy and b in coach_xy:
            cm = ((child_xy[a][0] + child_xy[b][0]) / 2, (child_xy[a][1] + child_xy[b][1]) / 2)
            tm = ((coach_xy[a][0] + coach_xy[b][0]) / 2, (coach_xy[a][1] + coach_xy[b][1]) / 2)
            deviations.append((math.hypot(cm[0] - tm[0], cm[1] - tm[1]), a, b))
    risk_segments = {(a, b) for _, a, b in sorted(deviations, reverse=True)[:3]}

    def line_tags(points: dict[str, tuple[float, float]], color: str, dashed: bool = False, only_risk: bool = False) -> str:
        tags = []
        dash = ' stroke-dasharray="9 8"' if dashed else ""
        for a, b in segments:
            if only_risk and (a, b) not in risk_segments:
                continue
            if a not in points or b not in points:
                continue
            x1, y1 = points[a]
            x2, y2 = points[b]
            tags.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{color}" stroke-width="{8 if only_risk else 5}" stroke-linecap="round" stroke-linejoin="round"{dash}/>')
        return "".join(tags)

    return f"""
    <svg class="pose-svg" viewBox="0 0 620 320" role="img" aria-label="标准姿态纠正图">
      <rect width="620" height="320" rx="18" fill="#ffffff"/>
      <g fill="none">
        {line_tags(child_xy, "#60a5fa", dashed=True)}
        {line_tags(coach_xy, "#16a34a")}
        {line_tags(child_xy, "#ef4444", only_risk=True)}
      </g>
      <g>
        <rect x="22" y="20" width="164" height="76" rx="14" fill="#eef6ff" stroke="#bfdbfe"/>
        <text x="38" y="45" fill="#2563eb" font-size="13" font-weight="700">真实三维姿态对照</text>
        <text x="38" y="66" fill="#667085" font-size="11">球员第{int(child["frame"])}帧 / 教练第{int(coach["frame"])}帧</text>
      </g>
      <g font-size="12" fill="#344054">
        <line x1="414" y1="34" x2="452" y2="34" stroke="#60a5fa" stroke-width="5" stroke-dasharray="9 8"/><text x="462" y="38">球员当前姿态</text>
        <line x1="414" y1="58" x2="452" y2="58" stroke="#16a34a" stroke-width="5"/><text x="462" y="62">教练标准姿态</text>
        <line x1="414" y1="82" x2="452" y2="82" stroke="#ef4444" stroke-width="7"/><text x="462" y="86">偏差较大骨段</text>
      </g>
    </svg>
    """


def timeline_svg(labels: list[str], details: list[str]) -> str:
    dots = []
    n = len(labels)
    for i, label in enumerate(labels):
        x = 44 + i * (520 / (n - 1))
        detail = details[i] if i < len(details) else "暂无数据"
        box_x = max(6, min(500, x - 52))
        dots.append(
            f'<circle cx="{x:.1f}" cy="70" r="8" fill="#2563eb"/>'
            f'<text x="{x:.1f}" y="102" text-anchor="middle" font-size="14" font-weight="700">{esc(label)}</text>'
            f'<rect x="{box_x:.1f}" y="114" width="104" height="46" rx="10" fill="#f8fafc" stroke="#e4e7ec"/>'
            f'<text x="{x:.1f}" y="134" text-anchor="middle" font-size="11" fill="#344054">{esc(detail.split("|")[0])}</text>'
            f'<text x="{x:.1f}" y="150" text-anchor="middle" font-size="11" fill="#667085">{esc(detail.split("|")[1] if "|" in detail else "")}</text>'
        )
    return f"""
    <div class="mini-chart-scroll"><svg class="wide-svg timeline-svg" viewBox="0 0 610 176" role="img" aria-label="阶段时间轴">
      <line x1="44" y1="70" x2="564" y2="70" stroke="#d0d5dd" stroke-width="8" stroke-linecap="round"/>
      {''.join(dots)}
    </svg></div>
    """


def chain_svg(nodes: list[tuple[str, str, str]]) -> str:
    parts = []
    for i, (label, value, note) in enumerate(nodes):
        x = 34 + i * 112
        color = ["#16a34a", "#f97316", "#2563eb", "#ef4444", "#697586"][i]
        box_x = max(6, min(452, x - 48))
        parts.append(
            f'<circle cx="{x}" cy="58" r="26" fill="{color}"/>'
            f'<text x="{x}" y="63" text-anchor="middle" fill="#fff" font-size="13" font-weight="700">{label}</text>'
            f'<rect x="{box_x}" y="100" width="96" height="58" rx="10" fill="#f8fafc" stroke="#e4e7ec"/>'
            f'<text x="{x}" y="122" text-anchor="middle" fill="#101828" font-size="12" font-weight="700">{esc(value)}</text>'
            f'<text x="{x}" y="142" text-anchor="middle" fill="#667085" font-size="11">{esc(note)}</text>'
        )
        if i < len(nodes) - 1:
            parts.append(f'<path d="M{x+32} 58 L{x+80} 58" stroke="#98a2b3" stroke-width="4" marker-end="url(#arrow)"/>')
    return f"""
    <div class="mini-chart-scroll"><svg class="wide-svg chain-svg" viewBox="0 0 560 172" role="img" aria-label="动力链传递图">
      <defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#98a2b3"/></marker></defs>
      <g fill="#fff" font-size="16" font-weight="600">{''.join(parts)}</g>
    </svg></div>
    """


def line_placeholder_svg(title: str) -> str:
    return f"""
    <svg class="wide-svg" viewBox="0 0 640 260" role="img" aria-label="{esc(title)}">
      <rect width="640" height="260" rx="16" fill="#ffffff"/>
      <line x1="60" y1="210" x2="590" y2="210" stroke="#667085"/>
      <line x1="60" y1="38" x2="60" y2="210" stroke="#667085"/>
      <path d="M70 180 C180 120 260 150 342 92 S500 118 570 62" fill="none" stroke="#2563eb" stroke-width="4" stroke-dasharray="8 8"/>
      <rect x="226" y="104" width="188" height="42" rx="21" fill="#eef2f7"/>
      <text x="320" y="130" text-anchor="middle" fill="#667085" font-size="16">缺少逐帧数据</text>
      <text x="60" y="238" fill="#667085" font-size="13">动作时间</text>
      <text x="18" y="42" fill="#667085" font-size="13">数值</text>
    </svg>
    """


def card(title: str, body: str, badge: str = "", klass: str = "") -> str:
    badge_html = f'<span class="badge {klass or "review"}">{esc(badge)}</span>' if badge else ""
    return f'<article class="card {klass}"><div class="card-head"><h4>{esc(title)}</h4>{badge_html}</div><p>{esc(body)}</p></article>'


def metric_card(title: str, value: str, body: str, status: str) -> str:
    label, klass = status_cn(status)
    return f"""
    <article class="metric-card {klass}">
      <div class="card-head"><h4>{esc(title)}</h4><span class="badge {klass}">{label}</span></div>
      <div class="metric-value">{esc(value)}</div>
      <p>{esc(zh_text(body))}</p>
    </article>
    """


def bars(rows: list[tuple[str, float | None, str, str]], max_value: float | None = None) -> str:
    vals = [abs(v) for _, v, _, _ in rows if v is not None]
    scale = max_value or max(vals or [1])
    out = []
    for label, value, unit, color in rows:
        width = 4 if value is None else max(4, min(100, abs(value) / scale * 100))
        out.append(f"""
        <div class="bar-row">
          <span>{esc(label)}</span>
          <div class="track"><i style="width:{width:.1f}%;background:{color}"></i></div>
          <b>{esc(fmt(value, unit))}</b>
        </div>
        """)
    return "\n".join(out)


def dot_comparison_svg(rows: list[dict[str, object]], legend: list[tuple[str, str]]) -> str:
    svg_w = 720
    left = 150
    axis_w = 320
    right = 500
    row_h = 68
    top = 44
    height = top + len(rows) * row_h + 68
    row_tags: list[str] = []
    for i, row in enumerate(rows):
        y = top + i * row_h
        unit = str(row.get("unit", ""))
        points = row["points"]  # type: ignore[index]
        values = [p["value"] for p in points if p.get("value") is not None]  # type: ignore[union-attr]
        if not values:
            lo, hi = 0.0, 1.0
        else:
            lo, hi = min(values), max(values)
            pad = max((hi - lo) * 0.18, abs(hi) * 0.06, 1.0)
            lo -= pad
            hi += pad
            if lo == hi:
                lo -= 1
                hi += 1

        def x_for(value: float) -> float:
            return left + (value - lo) / (hi - lo) * axis_w

        row_tags.append(f'<text x="20" y="{y + 3}" fill="#101828" font-size="14" font-weight="700">{esc(row["label"])}</text>')
        row_tags.append(f'<text x="20" y="{y + 23}" fill="#667085" font-size="12">{esc(row.get("sub", ""))}</text>')
        row_tags.append(f'<line x1="{left}" y1="{y}" x2="{left + axis_w}" y2="{y}" stroke="#e8eef6" stroke-width="14" stroke-linecap="round"/>')
        row_tags.append(f'<text x="{left}" y="{y + 28}" fill="#98a2b3" font-size="11" text-anchor="middle">{esc(fmt(lo, unit))}</text>')
        row_tags.append(f'<text x="{left + axis_w}" y="{y + 28}" fill="#98a2b3" font-size="11" text-anchor="middle">{esc(fmt(hi, unit))}</text>')
        right_lines = []
        for p in points:  # type: ignore[union-attr]
            value = p.get("value")
            if value is None:
                continue
            x = x_for(value)
            color = p.get("color", "#2563eb")
            kind = p.get("kind", "dot")
            if kind == "line":
                row_tags.append(f'<line x1="{x:.1f}" y1="{y - 18}" x2="{x:.1f}" y2="{y + 18}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>')
            else:
                row_tags.append(f'<circle cx="{x:.1f}" cy="{y}" r="9" fill="{color}" stroke="#fff" stroke-width="2"/>')
            right_lines.append((str(p.get("name", "")), float(value), str(color)))
        for j, (name, value, color) in enumerate(right_lines[:4]):
            row_tags.append(f'<text x="{right}" y="{y - 15 + j * 16}" fill="{color}" font-size="12">{esc(name)} {esc(fmt(value, unit))}</text>')

    legend_x = 26
    legend_y = height - 28
    legend_tags = []
    for name, color in legend:
        if color == "#101828":
            legend_tags.append(f'<line x1="{legend_x}" y1="{legend_y - 6}" x2="{legend_x}" y2="{legend_y + 8}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>')
        else:
            legend_tags.append(f'<circle cx="{legend_x}" cy="{legend_y}" r="7" fill="{color}"/>')
        legend_tags.append(f'<text x="{legend_x + 16}" y="{legend_y + 5}" fill="#344054" font-size="12">{esc(name)}</text>')
        legend_x += 128

    return f"""
    <div class="dot-plot-scroll"><svg class="dot-compare-svg" viewBox="0 0 {svg_w} {height}" role="img" aria-label="球员对比点位图">
      <rect width="{svg_w}" height="{height}" rx="18" fill="#ffffff"/>
      {''.join(row_tags)}
      <rect x="18" y="{height - 52}" width="{svg_w - 36}" height="40" rx="12" fill="#eef6ff" stroke="#bfdbfe"/>
      {''.join(legend_tags)}
    </svg></div>
    """


def compare_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        diff = num(row.get("diff_child_minus_coach"))
        status = "关注" if diff is not None and abs(diff) > 20 else "需复核"
        body.append(
            "<tr>"
            f"<td>{esc(row['label_cn'])}</td>"
            f"<td>{esc(fmt(row.get('child_value'), row.get('unit')))}</td>"
            f"<td>{esc(fmt(row.get('coach_value'), row.get('unit')))}</td>"
            f"<td>{esc(fmt(row.get('diff_child_minus_coach'), row.get('unit')))}</td>"
            f"<td>{esc(status)}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>指标</th><th>球员</th><th>教练参考</th><th>差距</th><th>训练判断</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def source_table(rows: list[dict[str, str]], limit: int = 30, all_rows: list[dict[str, str]] | None = None) -> str:
    body = []
    for row in rows[:limit]:
        status_label, _ = status_cn(row.get("availability"))
        body.append(
            "<tr>"
            f"<td>{esc(CLIP_CN.get(row.get('clip_id', ''), '样本'))}</td>"
            f"<td>{esc('投球' if row.get('action_type') == 'pitching' else '打击')}</td>"
            f"<td>{esc(metric_cn(row.get('metric_name')))}</td>"
            f"<td>{esc(fmt_metric_value(row, all_rows or rows))}</td>"
            f"<td>{esc(status_label)}</td>"
            f"<td>{esc(source_cn(row.get('source')))}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>样本</th><th>动作</th><th>指标</th><th>数值</th><th>状态</th><th>来源</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def rel_asset(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def sample_name(row: dict[str, str]) -> str:
    return row.get("sample_name") or row.get("athlete") or "未命名样本"


def image_figure(path: Path, title: str, caption: str) -> str:
    return f"""
    <figure class="evidence-figure">
      <img class="evidence-img" src="{esc(rel_asset(path))}" alt="{esc(title)}" loading="lazy">
      <figcaption><b>{esc(title)}</b><span>{esc(caption)}</span></figcaption>
    </figure>
    """


def image_pair(items: list[tuple[Path, str, str]]) -> str:
    return '<div class="evidence-pair">' + "".join(image_figure(*item) for item in items) + "</div>"


def pose3d_summary(path: Path) -> dict[str, float | int | str]:
    rows = read_csv(path)
    frames = {row["frame_index"] for row in rows if row.get("frame_index") not in (None, "")}
    joints = {row["joint_name"] for row in rows if row.get("joint_name") not in (None, "")}
    quality_values = [num(row.get("input_quality_score")) for row in rows]
    quality = [value for value in quality_values if value is not None]
    start = min((num(row.get("timestamp_sec")) for row in rows if num(row.get("timestamp_sec")) is not None), default=None)
    end = max((num(row.get("timestamp_sec")) for row in rows if num(row.get("timestamp_sec")) is not None), default=None)
    return {
        "frames": len(frames),
        "joints": len(joints),
        "quality": sum(quality) / len(quality) if quality else 0,
        "duration": (end - start) if start is not None and end is not None else 0,
    }


def pose3d_source_table(items: list[tuple[str, Path]]) -> str:
    body = []
    for label, path in items:
        summary = pose3d_summary(path)
        body.append(
            "<tr>"
            f"<td>{esc(label)}</td>"
            f"<td>{esc(str(summary['frames']))}</td>"
            f"<td>{esc(str(summary['joints']))}</td>"
            f"<td>{esc(fmt(summary['duration'], 's'))}</td>"
            f"<td>{esc(fmt(summary['quality'], ''))}</td>"
            f"<td>{esc('三维姿态')}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>样本</th><th>可用帧</th><th>关节数</th><th>时长</th><th>平均质量</th><th>来源</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def mean_metric(rows: list[dict[str, str]], action: str, metric: str, athlete: str | None = None) -> float | None:
    values = []
    for row in rows:
        if row.get("action_type") != action:
            continue
        if athlete is not None and row.get("athlete") != athlete:
            continue
        value = num(row.get(metric))
        if value is not None and math.isfinite(value):
            values.append(value)
    return sum(values) / len(values) if values else None


def first_metric(rows: list[dict[str, str]], action: str, metric: str, athlete: str | None = None) -> float | None:
    for row in rows:
        if row.get("action_type") != action:
            continue
        if athlete is not None and row.get("athlete") != athlete:
            continue
        value = num(row.get(metric))
        if value is not None and math.isfinite(value):
            return value
    return None


def vicon_source_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in sorted(rows, key=lambda item: (sample_name(item), item.get("action_type", ""), item.get("source_file", ""))):
        body.append(
            "<tr>"
            f"<td>{esc(sample_name(row))}</td>"
            f"<td>{esc('投球' if row['action_type'] == 'pitching' else '打击')}</td>"
            f"<td>{esc(str(row['frames']))}</td>"
            f"<td>{esc(fmt(row.get('duration_sec'), 's'))}</td>"
            f"<td>{esc(fmt(row.get('valid_point_pct'), '%'))}</td>"
            f"<td>{esc(row['source_file'])}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>样本名</th><th>动作</th><th>帧数</th><th>时长</th><th>有效点比例</th><th>C3D来源</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def vicon_trials(rows: list[dict[str, str]], action: str) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if row.get("action_type") == action],
        key=lambda item: (sample_name(item), item.get("source_file", "")),
    )


def vicon_reconstruction_image(rows: list[dict[str, str]], trial_id_value: str, title: str) -> str:
    event_row = next((row for row in rows if row.get("trial_id") == trial_id_value), {})
    event_text = event_row.get("key_event", "关键动作帧")
    frame_text = event_row.get("key_frame_index", "")
    time_text = fmt(event_row.get("key_time_sec"), "s") if event_row else ""
    gif_path = ROOT / "reports" / "assets" / "vicon_reconstruction" / f"{trial_id_value}.gif"
    png_path = ROOT / "reports" / "assets" / "vicon_reconstruction" / f"{trial_id_value}.png"
    image_path = gif_path if gif_path.exists() else png_path
    if not image_path.exists():
        return line_placeholder_svg(title)
    return f"""
    <figure class="reconstruction-figure">
      <img class="reconstruction-img" src="{esc(rel_asset(image_path))}" alt="{esc(title)}" loading="lazy">
      <figcaption>
        <b>{esc(title)}</b>
        <span>动图来自 C3D 关键动作窗口抽帧；关键动作先定位{esc(event_text)}，第{esc(frame_text)}帧，时间 {esc(time_text)}。骨架只使用真实 marker：头部、身体中部、脚部和球棒 marker 分别连接为刚体结构。</span>
      </figcaption>
    </figure>
    """


def vicon_reconstruction_cards(
    vicon_rows: list[dict[str, str]],
    point_rows: list[dict[str, str]],
    action: str,
) -> str:
    action_text = "投球" if action == "pitching" else "打击"
    note = (
        "该图从 C3D 关键动作窗口抽帧渲染真实 marker 骨架；头部、躯干、骨盆和脚部刚体用于更直观看方向与支撑。"
        if action == "pitching"
        else "该图从 C3D 关键动作窗口抽帧渲染真实 marker 骨架；身体中部和橙色球棒刚体帮助检查挥棒输出。"
    )
    cards = []
    for trial in vicon_trials(vicon_rows, action):
        title = f"{sample_name(trial)}{action_text}C3D骨架动图"
        cards.append(
            f'<article class="visual-card"><h4>{esc(title)}</h4>'
            f'{vicon_reconstruction_image(point_rows, trial["trial_id"], title)}'
            f'<p>怎么看：{esc(note)}</p></article>'
        )
    return "".join(cards)


def vicon_calibration_items(rows: list[dict[str, str]]) -> list[tuple[str, float | None, str, str]]:
    colors = ["#16a34a", "#60a5fa", "#f97316", "#7c4dff", "#2563eb", "#ef4444"]
    items: list[tuple[str, float | None, str, str]] = []
    batting = vicon_trials(rows, "batting")
    for i, row in enumerate(batting):
        color = colors[i % len(colors)]
        name = sample_name(row)
        items.append((f"{name}球棒峰值速度", num(row.get("bat_speed_kmh")), "km/h", color))
    for i, row in enumerate(batting):
        color = colors[(i + len(batting)) % len(colors)]
        name = sample_name(row)
        items.append((f"{name}挥棒高速度窗口", num(row.get("swing_time_sec")), "s", color))
    return items


def vicon_trial(rows: list[dict[str, str]], athlete: str, action: str) -> dict[str, str]:
    for row in rows:
        if row.get("athlete") == athlete and row.get("action_type") == action:
            return row
    raise ValueError(f"Missing Vicon trial for athlete={athlete!r}, action={action!r}")


def point_event(points: list[dict[str, str]], trial_id_value: str) -> dict[str, str]:
    return next((row for row in points if row.get("trial_id") == trial_id_value), {})


def event_details(points: list[dict[str, str]], trial: dict[str, str]) -> tuple[list[tuple[str, float | None]], str]:
    row = point_event(points, trial["trial_id"])
    event = row.get("key_event", "关键动作")
    frame = row.get("key_frame_index", "暂无")
    time_s = num(row.get("key_time_sec"))
    label = "峰值动作" if trial.get("action_type") == "pitching" else "击球/挥棒峰值"
    return [(event, time_s)], f"{fmt(time_s, 's')}|第{frame}帧"


def vicon_report_metrics(
    trial: dict[str, str],
    points: list[dict[str, str]],
    action: str,
) -> list[dict[str, str]]:
    event = point_event(points, trial["trial_id"])
    key_frame = event.get("key_frame_index", "")
    key_reason = event.get("key_event", "关键动作")
    base = {
        "sample": sample_name(trial),
        "action_type": action,
        "source": "vicon_c3d",
        "source_file": trial.get("source_file", ""),
        "event_frame": key_frame,
    }
    if action == "pitching":
        specs = [
            ("Hip-Shoulder Sep", "hip_shoulder_sep_deg", "deg", "髋肩分离反映下肢和骨盆先启动、躯干稍后跟上的蓄力顺序。投球中分离不足通常会让出手更多依赖手臂；过大或时机太晚则可能影响控球和肩肘负荷。Vicon marker 计算髋部轴与肩部轴的 yaw 分离角。"),
            ("Lead Knee Angle", "lead_knee_angle_deg", "deg", "前腿膝角代表落脚后前腿能否形成稳定支点。较稳定的前腿有助于把水平动量制动并传到骨盆和躯干；膝盖持续塌陷会削弱能量传递。Vicon marker 计算髋-膝-踝三点夹角。"),
            ("Trunk Tilt", "trunk_tilt_deg", "deg", "躯干倾斜影响出手点高度、身体轴线和肩肘受力。投球中过早侧倒或前倒会改变手臂槽位；适度前倾通常来自下肢制动后的躯干前移。Vicon marker 计算躯干相对竖直方向的倾角。"),
            ("Head Stability", "valid_point_pct", "%", "这里显示的是 C3D 有效点比例，用来判断本次光学数据是否足够可靠；它不是严格的头部稳定评分。真正的头部稳定会影响视线、平衡和出手重复性，需要用头部相对骨盆的位移另算。"),
            ("Hand Speed", "hand_speed_kmh", "km/h", "手部速度是动力链末端输出，受前腿制动、骨盆旋转、躯干旋转和肩肘腕顺序共同影响。它不能单独代表好动作，但峰值过低常提示前序能量没有顺畅传到手端。Vicon 手腕 marker 三维速度峰值。"),
            ("Trunk Speed", "trunk_speed_kmh", "km/h", "躯干速度反映骨盆之后的躯干加速能力。理想顺序通常是骨盆先加速、躯干随后加速、手端最后达到峰值；若躯干速度低或峰值太早，手臂容易补偿。Vicon 躯干中心三维速度峰值。"),
            ("Hip Speed", "hip_speed_kmh", "km/h", "髋部速度反映下肢推动和身体质心移动。它不是力板重心转移，但能帮助判断投手是否有足够的下肢驱动进入落脚和出手阶段。Vicon 髋部中心三维速度峰值。"),
        ]
    else:
        specs = [
            ("Hip-Shoulder Sep", "hip_shoulder_sep_deg", "deg", "打击中的髋肩分离代表下半身先开、上半身延迟的旋转蓄力。适度分离有助于把地面反作用力和髋部旋转传到躯干、手和球棒；不足时容易变成只用手推棒。Vicon marker 计算髋部轴与肩部轴的 yaw 分离角。"),
            ("Lead Knee Angle", "lead_knee_angle_deg", "deg", "前腿膝角反映前脚落地后的支撑和制动。稳定的前腿能帮助骨盆减速、躯干和球棒继续加速；膝盖过度弯曲或漂移会让挥棒轴线不稳定。Vicon marker 计算髋-膝-踝三点夹角。"),
            ("Trunk Tilt", "trunk_tilt_deg", "deg", "躯干倾斜影响挥棒平面、击球点高度和身体平衡。过度前倾会让挥棒路径变陡，过度后仰会增加上捞和失衡风险；理想值要结合球路高度和站姿看。Vicon marker 计算躯干相对竖直方向的倾角。"),
            ("Head Stability", "valid_point_pct", "%", "这里显示的是 C3D 有效点比例，用来判断本次光学数据是否足够可靠；它不是严格的头部稳定评分。真正的头部稳定会影响看球、击球点识别和挥棒重复性，需要用头部相对骨盆位移另算。"),
            ("Hand Speed", "hand_speed_kmh", "km/h", "手部速度反映上肢和躯干把能量传到握棒端的能力。手快但球棒不快可能提示腕手提前、杆身释放效率不足；手慢则可能来自下肢和躯干启动不足。Vicon 手腕 marker 三维速度峰值。"),
            ("Bat Speed", "bat_speed_kmh", "km/h", "球棒速度是打击表现最直接的输出之一，来自下肢支撑、髋肩分离、躯干旋转和腕手释放的综合结果。速度高但平面差仍可能影响击球质量，因此必须和攻击角、支撑和时机一起看。Vicon Bat1/Bat5 球棒 marker 三维速度峰值。"),
            ("Attack Angle", "bat_angle_deg", "deg", "攻击角描述球棒进入击球区时相对水平面的方向。过陡容易砍球，过上仰容易从球下方穿过；理想角度要结合来球轨迹和接触点判断。当前值是球棒轴角度，严格 attack angle 仍需真实接触帧。"),
            ("Contact Time", "swing_time_sec", "s", "这里是高速度挥棒窗口，不是球棒触球时长。较短窗口可能表示挥棒爆发集中，较长窗口可能表示加速拖长或节奏慢；需要结合球棒速度峰值和击球点时机解释。"),
        ]
    rows = []
    for metric, field, unit, reason in specs:
        value = trial.get(field, "")
        status = "available" if num(value) is not None else "unavailable"
        if metric in {"Head Stability", "Attack Angle", "Contact Time"}:
            status = "proxy" if num(value) is not None else "unavailable"
        rows.append(
            {
                **base,
                "metric_name": metric,
                "label_cn": metric_cn(metric),
                "value": value,
                "unit": unit,
                "availability": status,
                "status": "ok" if status == "available" else status,
                "reason": f"{reason} 关键动作：{key_reason}。",
                "note": f"{reason} 数据源：{trial.get('source_file', '')}。",
            }
        )
    return rows


def metric_value(rows: list[dict[str, str]], metric: str) -> float | None:
    row = next((item for item in rows if item.get("metric_name") == metric), None)
    return num(row.get("value")) if row else None


def vicon_metric_cards(rows: list[dict[str, str]]) -> str:
    return "".join(
        metric_card(row["label_cn"], fmt(row.get("value"), row.get("unit")), metric_explanation(row), row["status"])
        for row in rows
    )


def metric_explanation(row: dict[str, str]) -> str:
    action = row.get("action_type")
    metric = row.get("metric_name")
    copy = {
        ("pitching", "Hip-Shoulder Sep"): "看下肢先启动、肩部延迟的蓄力。过低会让手臂更容易代偿。",
        ("pitching", "Lead Knee Angle"): "看落脚后前腿能否制动。支点稳，动量才更容易传到躯干和手端。",
        ("pitching", "Trunk Tilt"): "影响出手点、身体轴线和肩肘负荷。需要和前腿支撑一起看。",
        ("pitching", "Head Stability"): "数据质量参考值，不是头部稳定评分。低值会降低曲线可信度。",
        ("pitching", "Hand Speed"): "动力链末端输出。低值通常提示前序段落传递不足。",
        ("pitching", "Trunk Speed"): "看躯干加速能力。应在髋部之后、手端之前完成主要加速。",
        ("pitching", "Hip Speed"): "看下肢推动和身体进入前腿支点的趋势，不等同力板重心。",
        ("batting", "Hip-Shoulder Sep"): "看下半身先开、上半身延迟的蓄力。过低容易只靠手推棒。",
        ("batting", "Lead Knee Angle"): "看前脚落地后的支撑和制动。前腿稳，球棒路径更容易稳定。",
        ("batting", "Trunk Tilt"): "影响挥棒平面和击球点高度。过度倾斜会让路径变陡或失衡。",
        ("batting", "Head Stability"): "数据质量参考值，不是头部稳定评分。低值会影响判断可信度。",
        ("batting", "Hand Speed"): "看能量传到握棒端的能力。需和球棒速度一起解释。",
        ("batting", "Bat Speed"): "末端输出指标。速度高仍要配合攻击角和击球区停留时间看。",
        ("batting", "Attack Angle"): "看球棒进入击球区的方向。偏离时容易砍球或从球下方穿过。",
        ("batting", "Contact Time"): "这里是高速挥棒窗口，不是真实触球时间。用于看节奏和加速集中度。",
    }
    return copy.get((action, metric), row.get("reason", ""))


def vicon_metrics_source_table(rows: list[dict[str, str]]) -> str:
    body = []
    for row in rows:
        status_label, _ = status_cn(row.get("availability"))
        body.append(
            "<tr>"
            f"<td>{esc(row.get('sample', ''))}</td>"
            f"<td>{esc('投球' if row.get('action_type') == 'pitching' else '打击')}</td>"
            f"<td>{esc(metric_cn(row.get('metric_name')))}</td>"
            f"<td>{esc(fmt(row.get('value'), row.get('unit')))}</td>"
            f"<td>{esc(status_label)}</td>"
            f"<td>{esc(row.get('source_file', ''))}</td>"
            "</tr>"
        )
    return '<table><thead><tr><th>被试</th><th>动作</th><th>指标</th><th>数值</th><th>状态</th><th>C3D来源</th></tr></thead><tbody>' + "".join(body) + "</tbody></table>"


def comparison_row(
    key: str,
    label: str,
    child: float | None,
    coach: float | None,
    unit: str,
    child_source: str,
    coach_source: str,
) -> dict[str, str]:
    diff = None if child is None or coach is None else child - coach
    diff_pct = None if diff is None or coach in (None, 0) else diff / coach * 100
    return {
        "metric_key": key,
        "label_cn": label,
        "unit": unit,
        "child_value": "" if child is None else str(child),
        "coach_value": "" if coach is None else str(coach),
        "diff_child_minus_coach": "" if diff is None else str(diff),
        "diff_pct": "" if diff_pct is None else str(diff_pct),
        "child_source": child_source,
        "coach_source": coach_source,
    }


def c3d_path(row: dict[str, str]) -> Path:
    return ROOT.parent / row["source_file"]


def finite_xyz(value) -> tuple[float, float, float] | None:
    vals = tuple(float(x) for x in value)
    return vals if all(math.isfinite(x) for x in vals) else None


def vicon_pose_sequence(path: Path) -> list[dict[str, object]]:
    trial = read_c3d(path)
    specs = {
        "head": ("LFHD", "RFHD", "LBHD", "RBHD"),
        "neck": ("C7", "CLAV"),
        "spine2": ("T10", "STRN"),
        "spine3": ("C7", "T10", "CLAV", "STRN"),
        "hip": ("LASI", "RASI", "LPSI", "RPSI"),
        "left_shoulder": ("LSHO",),
        "right_shoulder": ("RSHO",),
        "left_elbow": ("LELB",),
        "right_elbow": ("RELB",),
        "left_wrist": ("LWRA", "LWRB"),
        "right_wrist": ("RWRA", "RWRB"),
        "left_hand": ("LFIN",),
        "right_hand": ("RFIN",),
        "left_hip": ("LASI", "LPSI"),
        "right_hip": ("RASI", "RPSI"),
        "left_knee": ("LKNE",),
        "right_knee": ("RKNE",),
        "left_ankle": ("LANK",),
        "right_ankle": ("RANK",),
        "left_foot": ("LTOE",),
        "right_foot": ("RTOE",),
    }
    series = {name: marker(trial, *labels) for name, labels in specs.items()}
    frames = []
    for idx in range(trial.points.shape[0]):
        joints = {}
        for name, arr in series.items():
            xyz = finite_xyz(arr[idx])
            if xyz is not None:
                joints[name] = xyz
        if joints:
            frames.append(
                {
                    "frame": idx,
                    "time": idx / trial.rate_hz,
                    "quality": 1.0,
                    "joints": joints,
                }
            )
    return frames


def sequence_summary(frames: list[dict[str, object]]) -> dict[str, float | int]:
    if not frames:
        return {"frames": 0, "joints": 0, "quality": 0.0, "duration": 0.0}
    joint_names = {name for frame in frames for name in frame["joints"]}  # type: ignore[union-attr]
    return {
        "frames": len(frames),
        "joints": len(joint_names),
        "quality": 1.0,
        "duration": float(frames[-1]["time"]) - float(frames[0]["time"]),
    }


def vicon_quality_svg(items: list[tuple[str, list[dict[str, object]], str]]) -> str:
    return pose_quality_svg(items)


def main() -> None:
    pitch_full = read_csv(ROOT / "output" / "data" / "benchmark_pitch_vertical_09_motion_metrics_full.csv")
    pitch_vs = read_csv(ROOT / "output" / "data" / "benchmark_pitch_vertical_09_vs_pitch_horizontal_coach_metrics.csv")
    vicon = read_csv(ROOT / "reports" / "vicon_2026_metrics.csv")
    vicon_points = read_csv(ROOT / "reports" / "vicon_2026_point_summary.csv")
    pose3d_pitch_coach = ROOT / "data_full" / "coach_pose3d" / "gvhmr" / "pitch_horizontal_coach.csv"

    bryan_pitch = vicon_trial(vicon, MAIN_ATHLETE, "pitching")
    bryan_bat = vicon_trial(vicon, MAIN_ATHLETE, "batting")
    green_pitch = vicon_trial(vicon, COMPARE_ATHLETE, "pitching")
    green_bat = vicon_trial(vicon, COMPARE_ATHLETE, "batting")
    report_vicon = [bryan_pitch, bryan_bat, green_pitch, green_bat]

    bryan_pitch_frames = vicon_pose_sequence(c3d_path(bryan_pitch))
    bryan_bat_frames = vicon_pose_sequence(c3d_path(bryan_bat))
    green_pitch_frames = vicon_pose_sequence(c3d_path(green_pitch))
    green_bat_frames = vicon_pose_sequence(c3d_path(green_bat))
    pitch_coach_frames = read_pose_sequence(pose3d_pitch_coach)
    pitch_pose_summary = sequence_summary(bryan_pitch_frames)
    bat_pose_summary = sequence_summary(bryan_bat_frames)
    vicon_pitch_cards = vicon_reconstruction_cards(report_vicon, vicon_points, "pitching")
    vicon_bat_cards = vicon_reconstruction_cards(report_vicon, vicon_points, "batting")
    bryan_pitch_metrics = vicon_report_metrics(bryan_pitch, vicon_points, "pitching")
    bryan_bat_metrics = vicon_report_metrics(bryan_bat, vicon_points, "batting")
    green_pitch_metrics = vicon_report_metrics(green_pitch, vicon_points, "pitching")
    green_bat_metrics = vicon_report_metrics(green_bat, vicon_points, "batting")
    all_report_metrics = bryan_pitch_metrics + bryan_bat_metrics + green_pitch_metrics + green_bat_metrics

    vs = {row["metric_key"]: row for row in pitch_vs}
    vicon_pitch_vs = [
        comparison_row(
            "hip_shoulder_sep_deg",
            "髋肩分离",
            num(bryan_pitch.get("hip_shoulder_sep_deg")),
            num(vs["hip_shoulder_sep_deg"]["coach_value"]),
            "deg",
            bryan_pitch["source_file"],
            vs["hip_shoulder_sep_deg"]["coach_source"],
        ),
        comparison_row(
            "lead_knee",
            "前腿膝角",
            num(bryan_pitch.get("lead_knee_angle_deg")),
            num(next((r["coach_value"] for r in pitch_full if r["metric_key"] == "lead_knee"), None)),
            "deg",
            bryan_pitch["source_file"],
            "temporary coach reference",
        ),
        comparison_row(
            "trunk_lean",
            "躯干倾斜",
            num(bryan_pitch.get("trunk_tilt_deg")),
            num(next((r["coach_value"] for r in pitch_full if r["metric_key"] == "trunk_lean"), None)),
            "deg",
            bryan_pitch["source_file"],
            "temporary coach reference",
        ),
        comparison_row(
            "hand_speed",
            "手部速度",
            num(bryan_pitch.get("hand_speed_kmh")),
            (num(vs["hand_speed_m_s"]["coach_value"]) or 0) * 3.6 if num(vs["hand_speed_m_s"]["coach_value"]) is not None else None,
            "km/h",
            bryan_pitch["source_file"],
            vs["hand_speed_m_s"]["coach_source"],
        ),
    ]
    pitch_scores = [
        score_close(num(bryan_pitch.get("lead_knee_angle_deg")), num(next((r["coach_value"] for r in pitch_full if r["metric_key"] == "lead_knee"), None)), 45),
        score_ratio(num(bryan_pitch.get("hip_speed_kmh")), num(green_pitch.get("hip_speed_kmh"))),
        score_close(num(bryan_pitch.get("hip_shoulder_sep_deg")), num(vs["hip_shoulder_sep_deg"]["coach_value"]), 35),
        score_ratio(num(bryan_pitch.get("trunk_speed_kmh")), num(green_pitch.get("trunk_speed_kmh"))),
        score_ratio(num(bryan_pitch.get("hand_speed_kmh")), num(green_pitch.get("hand_speed_kmh"))),
        round(num(bryan_pitch.get("valid_point_pct")) or 45),
    ]
    bat_scores = [
        round(num(bryan_bat.get("valid_point_pct")) or 45),
        score_close(num(bryan_bat.get("lead_knee_angle_deg")), num(green_bat.get("lead_knee_angle_deg")), 55),
        max(10, round((num(bryan_bat.get("hip_shoulder_sep_deg")) or 0) / 35 * 100)),
        score_ratio(num(bryan_bat.get("trunk_speed_kmh")), num(green_bat.get("trunk_speed_kmh"))),
        max(8, min(100, round(100 - abs(num(bryan_bat.get("bat_angle_deg")) or 0) / 55 * 100))),
        score_ratio(num(bryan_bat.get("bat_speed_kmh")), num(green_bat.get("bat_speed_kmh"))),
    ]

    pitch_metric_cards = vicon_metric_cards(bryan_pitch_metrics)
    bat_metric_cards = vicon_metric_cards(bryan_bat_metrics)

    pitch_compare_bars = bars(
        [(row["label_cn"] + " 球员", num(row["child_value"]), row["unit"], "#f97316") for row in pitch_vs[:6]]
        + [(row["label_cn"] + " 教练", num(row["coach_value"]), row["unit"], "#16a34a") for row in pitch_vs[:6]]
    )
    bat_reference_bars = bars(
        [
            ("bryan 髋肩分离", num(bryan_bat.get("hip_shoulder_sep_deg")), "deg", "#f97316"),
            ("green 髋肩分离", num(green_bat.get("hip_shoulder_sep_deg")), "deg", "#60a5fa"),
            ("bryan 球棒峰值速度", num(bryan_bat.get("bat_speed_kmh")), "km/h", "#f97316"),
            ("green 球棒峰值速度", num(green_bat.get("bat_speed_kmh")), "km/h", "#60a5fa"),
        ],
    )
    pitch_events, pitch_event_detail = event_details(vicon_points, bryan_pitch)
    bat_events, bat_event_detail = event_details(vicon_points, bryan_bat)

    pitch_timeline_details = [
        "暂无抬腿事件|需逐帧检测",
        "暂无落脚事件|需逐帧检测",
        "暂无最大外旋|需逐帧检测",
        pitch_event_detail,
        "暂无随挥结束|需事件检测",
    ]
    bat_timeline_details = [
        "暂无准备事件|需逐帧检测",
        "暂无启动事件|需逐帧检测",
        "暂无落脚事件|需逐帧检测",
        "暂无入区事件|需球棒轨迹",
        bat_event_detail,
        "暂无随挥结束|需事件检测",
    ]
    pitch_event_frame = int(num(point_event(vicon_points, bryan_pitch["trial_id"]).get("key_frame_index")) or len(bryan_pitch_frames) // 2)
    coach_release_frame = peak_speed_frame(pitch_coach_frames, ["right_wrist", "right_hand"])
    pitch_posture_overlay = posture_overlay_svg(bryan_pitch_frames, pitch_coach_frames, pitch_event_frame, coach_release_frame)
    pitch_angle_chart = line_chart_svg("bryan 投球角度时间曲线", pose_angle_series(bryan_pitch_frames, "pitch"), pitch_events, "角度")
    pitch_speed_chart = line_chart_svg("bryan 投球速度时间曲线", pose_speed_series(bryan_pitch_frames, "pitch"), pitch_events, "公里/小时")
    bat_angle_chart = line_chart_svg("bryan 打击角度时间曲线", pose_angle_series(bryan_bat_frames, "bat"), bat_events, "角度")
    bat_speed_chart = line_chart_svg("bryan 打击速度时间曲线", pose_speed_series(bryan_bat_frames, "bat"), bat_events, "公里/小时")
    pose_quality_chart = vicon_quality_svg([
        ("bryan投球", bryan_pitch_frames, "#2563eb"),
        ("green投球", green_pitch_frames, "#60a5fa"),
        ("bryan打击", bryan_bat_frames, "#f97316"),
        ("green打击", green_bat_frames, "#7c4dff"),
    ])
    pitch_chain_nodes = [
        ("下肢", fmt(bryan_pitch.get("lead_knee_angle_deg"), "deg"), "前腿膝角"),
        ("骨盆", fmt(bryan_pitch.get("hip_speed_kmh"), "km/h"), "Vicon峰值"),
        ("躯干", fmt(bryan_pitch.get("trunk_speed_kmh"), "km/h"), "Vicon峰值"),
        ("手臂", fmt(bryan_pitch.get("hand_speed_kmh"), "km/h"), "Vicon峰值"),
        ("出手", fmt(point_event(vicon_points, bryan_pitch["trial_id"]).get("key_time_sec"), "s"), "手速峰值"),
    ]
    pitch_dot_plot = dot_comparison_svg(
        [
            {
                "label": "髋肩分离",
                "sub": "身体扭转",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("hip_shoulder_sep_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("hip_shoulder_sep_deg")), "color": "#f97316"},
                    {"name": "教练", "value": num(vs["hip_shoulder_sep_deg"]["coach_value"]), "color": "#101828", "kind": "line"},
                ],
            },
            {
                "label": "前腿膝角",
                "sub": "落地支撑",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("lead_knee_angle_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("lead_knee_angle_deg")), "color": "#f97316"},
                    {"name": "教练", "value": num(next((r["coach_value"] for r in pitch_full if r["metric_key"] == "lead_knee"), None)), "color": "#101828", "kind": "line"},
                ],
            },
            {
                "label": "躯干倾斜",
                "sub": "身体姿态",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("trunk_tilt_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("trunk_tilt_deg")), "color": "#f97316"},
                    {"name": "教练", "value": num(next((r["coach_value"] for r in pitch_full if r["metric_key"] == "trunk_lean"), None)), "color": "#101828", "kind": "line"},
                ],
            },
            {
                "label": "数据有效点",
                "sub": "C3D质量",
                "unit": "%",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("valid_point_pct")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("valid_point_pct")), "color": "#f97316"},
                    {"name": "建议参考", "value": 90.0, "color": "#101828", "kind": "line"},
                ],
            },
            {
                "label": "手部速度",
                "sub": "Vicon三维峰值",
                "unit": "km/h",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("hand_speed_kmh")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("hand_speed_kmh")), "color": "#f97316"},
                ],
            },
            {
                "label": "躯干速度",
                "sub": "Vicon三维峰值",
                "unit": "km/h",
                "points": [
                    {"name": "bryan", "value": num(bryan_pitch.get("trunk_speed_kmh")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_pitch.get("trunk_speed_kmh")), "color": "#f97316"},
                ],
            },
        ],
        [("bryan", "#2563eb"), ("green", "#f97316"), ("教练或建议参考", "#101828")],
    )
    bat_dot_plot = dot_comparison_svg(
        [
            {
                "label": "髋肩分离",
                "sub": "身体蓄力",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("hip_shoulder_sep_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("hip_shoulder_sep_deg")), "color": "#f97316"},
                ],
            },
            {
                "label": "前腿膝角",
                "sub": "支撑稳定",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("lead_knee_angle_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("lead_knee_angle_deg")), "color": "#f97316"},
                ],
            },
            {
                "label": "躯干倾斜",
                "sub": "身体轴线",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("trunk_tilt_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("trunk_tilt_deg")), "color": "#f97316"},
                ],
            },
            {
                "label": "数据有效点",
                "sub": "C3D质量",
                "unit": "%",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("valid_point_pct")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("valid_point_pct")), "color": "#f97316"},
                    {"name": "建议参考", "value": 90.0, "color": "#101828", "kind": "line"},
                ],
            },
            {
                "label": "攻击角",
                "sub": "挥棒平面",
                "unit": "deg",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("bat_angle_deg")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("bat_angle_deg")), "color": "#f97316"},
                ],
            },
            {
                "label": "球棒速度",
                "sub": "Vicon三维峰值",
                "unit": "km/h",
                "points": [
                    {"name": "bryan", "value": num(bryan_bat.get("bat_speed_kmh")), "color": "#2563eb"},
                    {"name": "green", "value": num(green_bat.get("bat_speed_kmh")), "color": "#f97316"},
                ],
            },
        ],
        [("bryan", "#2563eb"), ("green", "#f97316"), ("建议参考", "#101828")],
    )

    html_doc = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>青少年棒球三维动作体检报告</title>
  <style>
    :root {{
      --primary:#2563eb; --ink:#101828; --body:#344054; --mid:#667085; --mute:#98a2b3;
      --line:#d0d5dd; --canvas:#f5f7fb; --soft:#eef6ff; --card:#fff; --dusk:#101828;
      --orange:#f97316; --green:#16a34a; --red:#ef4444; --review:#e89918; --blue:#60a5fa; --violet:#7c4dff;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; background:var(--canvas); color:var(--ink); font-family:STHeiti,"PingFang SC","Microsoft YaHei",system-ui,sans-serif; line-height:1.5; letter-spacing:0; }}
    .topbar {{ position:sticky; top:0; z-index:10; background:rgba(255,255,255,.95); border-bottom:1px solid var(--line); backdrop-filter:blur(12px); }}
    .nav {{ max-width:1180px; margin:auto; padding:20px 24px; display:flex; align-items:center; justify-content:space-between; gap:20px; }}
    .brand {{ color:var(--primary); font-size:24px; font-weight:600; }}
    .links {{ display:flex; flex-wrap:wrap; gap:14px; color:var(--mid); font-size:18px; }}
    .links a {{ color:inherit; text-decoration:none; }}
    main {{ max-width:1180px; margin:auto; padding:32px 24px 72px; }}
    .hero {{ background:var(--dusk); color:white; border-radius:26px; padding:42px; display:grid; grid-template-columns:1.02fr .98fr; gap:34px; align-items:stretch; }}
    .hero > * {{ min-width:0; }}
    h1 {{ font-size:56px; line-height:66px; font-weight:500; margin:0 0 18px; }}
    h2 {{ font-size:34px; line-height:44px; font-weight:500; margin:0; }}
    h3 {{ font-size:27px; line-height:36px; font-weight:500; margin:0; }}
    h4 {{ font-size:20px; line-height:30px; margin:0; }}
    p {{ margin:0; color:var(--body); font-size:18px; overflow-wrap:anywhere; }}
    .hero p {{ color:#dbeafe; font-size:22px; line-height:34px; }}
    .pill-row {{ display:flex; flex-wrap:wrap; gap:10px; margin-top:24px; }}
    .pill {{ border:1px solid #334155; background:#0f172a; color:#dbeafe; border-radius:999px; padding:8px 16px; font-size:18px; }}
    .hero-evidence {{ background:linear-gradient(135deg,rgba(37,99,235,.34),rgba(249,115,22,.16)),#0f172a; border:1px solid #334155; border-radius:24px; padding:18px; display:grid; gap:14px; }}
    .hero-stat {{ display:grid; grid-template-columns:repeat(3,1fr); gap:10px; }}
    .hero-stat div {{ background:rgba(255,255,255,.08); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:14px; }}
    .hero-stat b {{ display:block; font-size:26px; color:#fff; }}
    .hero-stat span {{ color:#cbd5e1; font-size:15px; }}
    .section {{ margin-top:42px; min-width:0; }}
    .section-title {{ display:flex; align-items:center; gap:14px; margin-bottom:18px; }}
    .mark {{ width:12px; height:40px; background:var(--primary); border-radius:999px; flex:0 0 auto; }}
    .module-note {{ background:var(--soft); border:1px solid #bfdbfe; border-radius:12px; padding:16px 18px; margin-bottom:18px; }}
    .grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }}
    .grid-2 {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; }}
    .grid-3 {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:16px; }}
    .grid > *, .grid-2 > *, .grid-3 > * {{ min-width:0; }}
    .card,.metric-card,.visual-card {{ background:var(--card); border:2px solid #e4e7ec; border-radius:24px; padding:24px; min-width:0; }}
    .card.good,.metric-card.good {{ background:#f7fff9; }}
    .card.review,.metric-card.review {{ background:#fffaf4; }}
    .card.risk,.metric-card.risk {{ background:#fff8f8; }}
    .card.na,.metric-card.na {{ background:#eef2f7; border-style:dashed; }}
    .card-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:12px; }}
    .badge {{ display:inline-flex; align-items:center; border-radius:999px; padding:5px 11px; font-size:15px; white-space:nowrap; }}
    .badge.good {{ background:#dcfce7; color:#166534; }}
    .badge.review {{ background:#fff7ed; color:#9a3412; }}
    .badge.risk {{ background:#fef2f2; color:#b91c1c; }}
    .badge.na {{ background:#eef2f7; color:#697586; }}
    .metric-value {{ font-size:32px; line-height:1; font-weight:700; margin:18px 0 10px; overflow-wrap:anywhere; }}
    .compact-metrics .metric-card {{ padding:18px; border-radius:18px; }}
    .compact-metrics .metric-card h4 {{ font-size:17px; line-height:24px; }}
    .compact-metrics .metric-value {{ font-size:24px; line-height:28px; margin:12px 0 8px; }}
    .compact-metrics .metric-card p {{ font-size:14px; line-height:21px; }}
    .compact-metrics .badge {{ font-size:13px; padding:4px 9px; }}
    .visual-card h4 {{ font-size:18px; line-height:26px; }}
    .visual-card p,.metric-card p,.card p {{ margin-top:8px; color:var(--mid); }}
    .visual-card p {{ font-size:16px; line-height:24px; }}
    .radar {{ width:100%; max-width:330px; display:block; margin:auto; }}
    .radar text {{ fill:#344054; font-size:12px; font-weight:600; }}
    .pose-svg,.wide-svg {{ width:100%; display:block; border-radius:18px; }}
    .evidence-pair {{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:12px; }}
    .evidence-figure {{ margin:0; min-width:0; background:#f8fafc; border:1px solid var(--line); border-radius:16px; overflow:hidden; }}
    .evidence-img {{ width:100%; aspect-ratio:16/10; object-fit:cover; display:block; background:#101828; }}
    .evidence-figure figcaption {{ display:grid; gap:4px; padding:10px 12px; }}
    .evidence-figure figcaption b {{ color:var(--ink); font-size:15px; line-height:20px; }}
    .evidence-figure figcaption span {{ color:var(--mid); font-size:13px; line-height:18px; }}
    .hero-evidence .evidence-img {{ aspect-ratio:16/11; }}
    .reconstruction-figure {{ margin:0; background:#fff; border:1px solid var(--line); border-radius:18px; overflow:hidden; }}
    .reconstruction-img {{ width:100%; aspect-ratio:16/10; object-fit:contain; display:block; background:#fff; }}
    .reconstruction-figure figcaption {{ display:grid; gap:4px; padding:12px 14px; border-top:1px solid #e4e7ec; }}
    .reconstruction-figure figcaption b {{ color:var(--ink); font-size:15px; line-height:20px; }}
    .reconstruction-figure figcaption span {{ color:var(--mid); font-size:13px; line-height:19px; }}
    .dot-plot-scroll {{ width:100%; overflow-x:auto; padding-bottom:4px; }}
    .dot-compare-svg {{ width:80%; min-width:0; display:block; margin:0 auto; border-radius:18px; }}
    .line-chart-scroll {{ width:100%; overflow-x:auto; padding-bottom:4px; }}
    .line-chart-svg {{ width:100%; min-width:0; display:block; border-radius:18px; }}
    .mini-chart-scroll {{ width:100%; overflow-x:auto; padding-bottom:4px; }}
    .timeline-svg {{ min-width:0; }}
    .chain-svg {{ min-width:0; }}
    .chart-copy {{ display:grid; gap:10px; align-content:center; }}
    .chart-copy li {{ margin-bottom:8px; color:var(--body); font-size:18px; }}
    .priority-list {{ display:grid; gap:12px; }}
    .priority-item {{ display:grid; grid-template-columns:42px 1fr auto; gap:14px; align-items:center; background:#fff; border:2px solid #e4e7ec; border-radius:18px; padding:16px; }}
    .rank {{ width:42px; height:42px; border-radius:999px; display:grid; place-items:center; background:var(--orange); color:#fff; font-weight:700; }}
    .bars {{ display:grid; gap:12px; margin-top:16px; }}
    .bar-row {{ display:grid; grid-template-columns:180px 1fr 108px; gap:12px; align-items:center; font-size:16px; color:var(--mid); }}
    .track {{ height:12px; background:#e8eef6; border-radius:999px; overflow:hidden; }}
    .track i {{ display:block; height:100%; border-radius:inherit; }}
    .training {{ display:grid; grid-template-columns:repeat(7,minmax(150px,1fr)); gap:12px; overflow-x:auto; padding-bottom:4px; }}
    .day {{ min-height:180px; background:#fff; border:2px solid #e4e7ec; border-radius:18px; padding:16px; }}
    .day ul {{ padding-left:20px; margin:10px 0 0; color:var(--mid); font-size:16px; }}
    .matrix {{ position:relative; min-height:320px; background:linear-gradient(90deg,#f8fafc,#eef6ff); border-radius:18px; border:1px solid var(--line); overflow:hidden; }}
    .matrix:before,.matrix:after {{ content:""; position:absolute; background:#d0d5dd; }}
    .matrix:before {{ left:50%; top:0; bottom:0; width:1px; }}
    .matrix:after {{ top:50%; left:0; right:0; height:1px; }}
    .bubble {{ position:absolute; transform:translate(-50%,-50%); border-radius:999px; padding:12px 16px; color:white; font-weight:600; }}
    .table-scroll {{ max-height:420px; max-width:100%; overflow:auto; border:1px solid var(--line); border-radius:12px; background:white; }}
    table {{ width:100%; border-collapse:collapse; min-width:760px; }}
    th,td {{ padding:10px 12px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; font-size:14px; color:var(--body); }}
    th {{ background:var(--soft); color:var(--ink); position:sticky; top:0; }}
    footer {{ border-top:1px solid var(--line); color:var(--mute); text-align:center; padding:24px; font-size:16px; }}
    @media (max-width:960px) {{ .hero,.grid-2,.grid-3 {{ grid-template-columns:1fr; }} .grid {{ grid-template-columns:repeat(2,minmax(0,1fr)); }} .bar-row,.priority-item {{ grid-template-columns:1fr; }} h1 {{ font-size:40px; line-height:48px; }} }}
    @media (max-width:640px) {{ main,.nav {{ padding-left:16px; padding-right:16px; }} .hero {{ padding:26px; }} .grid {{ grid-template-columns:1fr; }} .hero-stat,.evidence-pair {{ grid-template-columns:1fr; }} .links {{ font-size:16px; }} .visual-card h4 {{ font-size:17px; line-height:24px; }} .visual-card p {{ font-size:15px; line-height:22px; }} }}
  </style>
</head>
<body>
  <header class="topbar">
    <nav class="nav">
      <div class="brand">棒球动作实验室</div>
      <div class="links"><a href="#player">球员</a><a href="#coach">教练</a><a href="#research">研究者</a><a href="#pitch">投球</a><a href="#bat">打击</a></div>
    </nav>
  </header>
  <main>
    <section class="hero">
      <div>
        <h1>青少年棒球三维动作体检报告</h1>
        <p>本报告按球员、教练、研究者三类读者拆分，并把投球和打击分开分析。主体被试固定为 bryan，原始身体数据统一来自 Vicon C3D；green 仅作为教练模块对照，教练参考暂时沿用既有 coach 3D 数据。解读重点放在棒球动力链：下肢支撑、骨盆与躯干旋转、手端或球棒速度是否顺序传递。</p>
        <div class="pill-row"><span class="pill">中文报告</span><span class="pill">三维骨架</span><span class="pill">可量化诊断</span><span class="pill">数据限制透明</span></div>
      </div>
      <aside class="hero-evidence">
        {vicon_reconstruction_image(vicon_points, bryan_pitch["trial_id"], "bryan 投球 C3D 骨架证据")}
        <div class="hero-stat">
          <div><b>{pitch_pose_summary["frames"]}</b><span>bryan投球C3D帧</span></div>
          <div><b>{bat_pose_summary["frames"]}</b><span>bryan打击C3D帧</span></div>
          <div><b>{fmt(bryan_bat.get("valid_point_pct"), "%")}</b><span>打击有效点比例</span></div>
        </div>
      </aside>
    </section>

    <section class="section" id="player">
      <div class="section-title"><span class="mark"></span><h2>球员模块</h2></div>
      <div class="module-note"><p>这一模块只回答孩子和家长最关心的三件事：哪里做得好、哪里要改、接下来练什么。所有主体指标均来自 bryan 的 Vicon C3D。</p></div>

      <section class="section" id="pitch">
        <div class="section-title"><span class="mark"></span><h3>投球分析</h3></div>
        <div class="grid-2">
          <article class="visual-card">
            <h4>投球六维评分图</h4>
            {radar_svg(["下肢支撑","身体前移","髋肩分离","躯干控制","手臂加速","稳定性"], pitch_scores)}
            <p>怎么看：投球不是只看手快，六维评分把下肢支撑、骨盆/躯干旋转、髋肩分离和手端输出放在同一动力链里看。低分维度代表能量传递可能断在该环节，训练时应先修支撑和时序，再追求出手速度。</p>
          </article>
          <article class="visual-card">
            <h4>投球优先级列表</h4>
            <div class="priority-list">
              <div class="priority-item"><span class="rank">1</span><div><h4>提高出手侧手部速度</h4><p>手部速度是动力链末端结果。若下肢制动、骨盆旋转和躯干旋转没有先后传递，手会被迫补偿，速度和稳定性都会受影响。</p></div><span class="badge risk">关注</span></div>
              <div class="priority-item"><span class="rank">2</span><div><h4>增加身体前移质量</h4><p>投球需要从后侧腿推动到前腿制动。身体前移不是单纯跨大步，而是让质心进入前腿支点后把动量转成骨盆和躯干旋转。</p></div><span class="badge review">需复核</span></div>
              <div class="priority-item"><span class="rank">3</span><div><h4>保持前腿支撑</h4><p>前腿像刹车系统，支撑稳定才容易把水平动量传到躯干和手端。若前膝持续塌陷，出手点和控球会更难重复。</p></div><span class="badge good">良好</span></div>
            </div>
          </article>
        </div>
        <div class="grid-2" style="margin-top:18px">
          <article class="visual-card"><h4>投球关键帧证据图</h4>{vicon_reconstruction_image(vicon_points, bryan_pitch["trial_id"], "bryan投球C3D关键动作窗口")}<p>方法：关键帧来自 Vicon C3D 手部速度峰值。棒球投球通常在手端峰值附近暴露动力链结果：前腿是否撑住、骨盆和肩线是否形成分离、躯干是否把旋转传到手臂。</p></article>
          <article class="visual-card"><h4>投球姿态纠正图</h4>{pitch_posture_overlay}<p>方法：蓝色虚线是 bryan 出手附近三维姿态，绿色是临时 coach 参考姿态，红色标出偏差较大的骨段。这个图用于看身体段落排列，不用于单独判断好坏；真正的训练重点要结合速度峰值顺序和前腿支撑。</p></article>
        </div>
        <div class="grid compact-metrics" style="margin-top:18px">{pitch_metric_cards}</div>
        <div class="grid-3" style="margin-top:18px">
          {card("投球训练目标一", "跨步停顿投球影子练习：落脚后停住前膝和骨盆，再做躯干旋转。目标是让前腿成为稳定支点，复测前膝角和髋部速度。", "训练", "review")}
          {card("投球训练目标二", "髋肩分离慢动作：先让骨盆面向目标，再延迟肩线打开。目标是建立下肢到躯干的拉伸-旋转顺序，复测髋肩分离和躯干倾斜。", "训练", "review")}
          {card("投球训练目标三", "毛巾出手练习：用低强度重复下肢、躯干、手端的先后顺序。目标不是甩快，而是让手部速度来自前序段落传递。", "训练", "risk")}
        </div>
        <article class="visual-card" style="margin-top:18px"><h4>投球七天训练计划</h4><div class="training">{''.join(f'<div class="day"><h4>第{i}天</h4><span class="badge review">{"复测" if i == 7 else "训练"}</span><ul><li>{"同机位拍摄投球" if i == 7 else "髋肩分离慢动作"}</li><li>{"复测两个短板指标" if i == 7 else "跨步停顿影子投球"}</li><li>记录疼痛、疲劳和完成率</li></ul></div>' for i in range(1,8))}</div></article>
      </section>

      <section class="section" id="bat">
        <div class="section-title"><span class="mark"></span><h3>打击分析</h3></div>
        <div class="grid-2">
          <article class="visual-card"><h4>打击六维评分图</h4>{radar_svg(["站姿稳定","跨步控制","髋肩分离","躯干旋转","挥棒平面","击球后平衡"], bat_scores, "#7c4dff")}<p>怎么看：打击评分按从地面到球棒的顺序解释。站姿和跨步提供稳定底座，髋肩分离和躯干旋转负责蓄力与释放，挥棒平面决定球棒是否长时间留在击球区。</p></article>
          <article class="visual-card"><h4>打击关键帧证据图</h4>{vicon_reconstruction_image(vicon_points, bryan_bat["trial_id"], "bryan打击C3D关键动作窗口")}<p>方法：关键帧来自 Vicon C3D 球棒速度峰值。该时刻接近挥棒输出最高点，适合检查前腿是否制动、髋肩是否分离、躯干和手是否把速度传到球棒。</p></article>
        </div>
        <div class="grid compact-metrics" style="margin-top:18px">{bat_metric_cards}</div>
        <div class="grid-2" style="margin-top:18px">
          <article class="visual-card"><h4>挥棒轨迹证据图</h4>{vicon_reconstruction_image(vicon_points, bryan_bat["trial_id"], "bryan打击C3D球棒轨迹")}<p>怎么看：Vicon 同时有身体 marker 和 Bat1-Bat5 球棒 marker。球棒速度高说明末端输出可用，但还要看攻击角和平面是否让球棒在击球区停留更久，而不是只从球下方或上方穿过。</p></article>
          <article class="visual-card"><h4>打击优先级列表</h4><div class="priority-list"><div class="priority-item"><span class="rank">1</span><div><h4>修正挥棒平面</h4><p>挥棒平面决定球棒与来球轨迹重合的时间。攻击角偏离时，即使球棒速度够快，也容易擦过球或打出弱接触。</p></div><span class="badge risk">关注</span></div><div class="priority-item"><span class="rank">2</span><div><h4>提高髋肩分离</h4><p>髋肩分离是打击蓄力核心。下半身先启动、上半身延迟，可以让躯干像弹簧一样释放到手和球棒。</p></div><span class="badge risk">关注</span></div><div class="priority-item"><span class="rank">3</span><div><h4>保持看球稳定</h4><p>头部和躯干稳定帮助击球点判断。这里的质量分只是数据可靠性 proxy，实际训练仍要看头部相对骨盆是否过度漂移。</p></div><span class="badge good">良好</span></div></div></article>
        </div>
        <div class="grid-3" style="margin-top:18px">
          {card("墙边髋肩分离", "每天两组，左右各八次；家长只看肩膀不要抢先。目标是让髋先开、肩后开，建立下肢到躯干的弹性蓄力。", "训练", "risk")}
          {card("固定球平扫路线", "每次三组，每组八球；让球棒沿水平线穿过击球区。目标是延长球棒与来球轨迹重合时间，而不是只追求球棒速度。", "训练", "risk")}
          {card("看球冻结", "每次两组，每组十次；挥完保持击球点一秒再抬头。目标是减少头部和躯干早开，提高击球点识别和动作重复性。", "训练", "good")}
        </div>
      </section>
    </section>

    <section class="section" id="coach">
      <div class="section-title"><span class="mark"></span><h2>教练模块</h2></div>
      <div class="module-note"><p>这一模块聚焦对比、差距、阶段和训练干预。主体是 bryan，green 仅作为同一 Vicon 采集环境下的对照；教练参考暂时沿用既有 coach 3D 数据。</p></div>
      <div class="grid-2">
        <article class="visual-card"><h4>投球差距仪表盘</h4><div class="table-scroll">{compare_table(vicon_pitch_vs)}</div><p>怎么看：差距表只比较同一生物力学含义的指标。角度差提示姿态和时序问题，手部速度差提示动力链末端输出问题；训练优先级要看差距大小、可改性和是否影响控球。</p></article>
        <article class="visual-card"><h4>投球阶段时间轴</h4>{timeline_svg(["抬腿","落脚","最大外旋","出手","随挥"], pitch_timeline_details)}<p>投球阶段应按动力链顺序解释：抬腿建立节奏，落脚形成前腿支点，最大外旋储存肩部弹性能量，出手释放到球，随挥负责减速保护。</p></article>
      </div>
      <article class="visual-card" style="margin-top:18px"><h4>投球队员对比点位图</h4>{pitch_dot_plot}<p>读法：蓝点是 bryan，橙点是 green，黑线是暂用教练参考。每一行只比较同一个指标；髋肩分离看蓄力，前膝角看制动，手部速度看最终输出。</p></article>
      <div class="grid-2" style="margin-top:18px">
        <article class="visual-card"><h4>投球动力链传递图</h4>{chain_svg(pitch_chain_nodes)}<p>怎么看：理想投球输出不是所有部位同时快，而是下肢和髋部先建立动量，躯干随后加速，手端最后达到峰值。若某一段过慢或过早，后续段落会补偿。</p></article>
        <article class="visual-card"><h4>打击阶段时间轴</h4>{timeline_svg(["准备","启动","前脚落地","进入击球区","击球点","随挥"], bat_timeline_details)}<p>打击阶段按加载、落脚、旋转释放和减速来解读。前脚落地后，骨盆和躯干应依次加速，球棒进入击球区后需要保持有效平面。</p></article>
      </div>
      <article class="visual-card" style="margin-top:18px"><h4>打击队员对比点位图</h4>{bat_dot_plot}<p>读法：蓝点是 bryan，橙点是 green。髋肩分离看蓄力，前腿膝角看制动，攻击角看球棒路径，球棒速度看末端输出；这些指标要一起解释。</p></article>
      <article class="visual-card" style="margin-top:18px"><h4>改进优先级矩阵</h4><div class="matrix"><span class="bubble" style="left:78%;top:24%;background:#ef4444">手部速度</span><span class="bubble" style="left:66%;top:34%;background:#f97316">身体前移</span><span class="bubble" style="left:58%;top:62%;background:#7c4dff">挥棒平面</span><span class="bubble" style="left:36%;top:72%;background:#16a34a">头部稳定</span></div><p>横轴代表对表现的影响，纵轴代表训练优先级。高影响且高优先级的点通常位于动力链断点，例如前腿制动、髋肩分离或球棒平面，而不是孤立追求某个数值。</p></article>
    </section>

    <section class="section" id="research">
      <div class="section-title"><span class="mark"></span><h2>研究者模块</h2></div>
      <div class="module-note"><p>这一模块统一使用 vicon_2026 C3D 作为 raw data source。逐帧曲线、事件线、质量图、来源表和动图均从 C3D 或 C3D 派生 CSV 得到；教练参考作为临时对照单独标注。</p></div>
      <div class="grid-2">
        <article class="visual-card"><h4>投球角度时间曲线</h4>{pitch_angle_chart}<p>怎么看：曲线来自 bryan 投球 C3D marker 逐帧计算。观察重点不是单帧最大值，而是前膝支撑、躯干倾斜、肘角和髋肩分离是否在出手前后按合理顺序变化。</p></article>
        <article class="visual-card"><h4>投球速度时间曲线</h4>{pitch_speed_chart}<p>怎么看：速度曲线用于看峰值顺序。棒球投球通常希望髋部/骨盆先带动，躯干随后，手端最后输出；如果手端过早峰值，可能说明手臂抢先。</p></article>
        <article class="visual-card"><h4>打击角度时间曲线</h4>{bat_angle_chart}<p>怎么看：曲线来自 bryan 打击 C3D marker 逐帧计算。重点看前腿落地后的支撑是否稳定、髋肩分离是否形成蓄力、躯干倾斜是否破坏挥棒平面。</p></article>
        <article class="visual-card"><h4>打击速度时间曲线</h4>{bat_speed_chart}<p>怎么看：速度曲线用于检查能量是否从髋部和躯干传到手端。若躯干或手端峰值顺序混乱，即使球棒峰值速度可用，也可能导致击球点不稳定。</p></article>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <article class="visual-card"><h4>事件点表</h4><div class="table-scroll">{vicon_metrics_source_table([row for row in all_report_metrics if row["metric_name"] in {"Hand Speed", "Bat Speed"}])}</div><p>事件点来自 C3D 派生表：投球暂用手部速度峰值代表出手附近输出，打击暂用球棒速度峰值代表挥棒输出高点。它们是自动事件 proxy，不等同人工标注的 release/contact。</p></article>
        <article class="visual-card"><h4>C3D逐帧来源表</h4><div class="table-scroll">{vicon_source_table(report_vicon)}</div><p>表内统计直接来自 Vicon C3D。帧数和有效点比例决定曲线可信度；有效点低时，速度峰值和角度峰值更容易受 marker 缺失或插值影响。</p></article>
      </div>
      <div class="grid-2" style="margin-top:18px">
        <article class="visual-card"><h4>Vicon 2026 C3D来源表</h4><div class="table-scroll">{vicon_source_table(report_vicon)}</div><p>报告当前只纳入 bryan 和 green；子文件夹名即被试名。</p></article>
        {vicon_pitch_cards or '<article class="visual-card"><h4>投球C3D重建截图</h4>' + line_placeholder_svg("投球C3D重建截图") + '<p>暂无投球 C3D 点位数据。</p></article>'}
      </div>
      <div class="grid-2" style="margin-top:18px">
        <article class="visual-card"><h4>数据质量图</h4>{pose_quality_chart}<p>怎么看：质量图不是动作评分，而是说明本次 biomechanics 指标是否可信。缺点多或帧段缺失时，髋肩分离、膝角和速度峰值都可能被低估或错位。</p></article>
        {vicon_bat_cards or '<article class="visual-card"><h4>打击C3D重建截图</h4>' + line_placeholder_svg("打击C3D重建截图") + '<p>暂无打击 C3D 点位数据。</p></article>'}
      </div>
      <div class="grid-2" style="margin-top:18px">
        <article class="visual-card"><h4>光学动作捕捉对照说明</h4><div class="bars">{bat_reference_bars}</div><p>光学动作捕捉来自 vicon_2026 C3D 导出。bryan 是主分析人，green 只作为对照；对照的意义是帮助教练看相对动作模式，例如球棒速度相近但攻击角不同，训练重点就应偏向路径而不是力量。</p></article>
        <article class="visual-card"><h4>限制卡片组</h4><div class="grid-2">{card("真实球速", "本报告没有雷达枪或球轨迹同步数据，因此不能从身体 marker 直接判断正式球速。投球手速只能解释动力链末端输出。", "需复核", "review")}{card("接触事件", "打击使用球棒速度峰值作为自动事件 proxy，不等同真实 bat-ball contact。接触帧会影响攻击角和挥棒窗口解释。", "需复核", "review")}{card("身体重心", "当前使用髋部和躯干 marker 解释身体移动，不是力板 COM 或压力转移。重心转移结论只能作为动作趋势。", "需复核", "review")}{card("coach参考", "coach 参考暂未统一到同一 Vicon C3D 采集链路，只能作为临时技术参考线，不能和 bryan/green 做严格实验对照。", "需复核", "review")}</div></article>
      </div>
      <article class="visual-card" style="margin-top:18px"><h4>指标来源表</h4><div class="table-scroll">{vicon_metrics_source_table(all_report_metrics)}</div></article>
    </section>
  </main>
  <footer>三维视频动作分析报告，仅用于训练参考。缺少数据的指标已保留占位和限制说明。</footer>
</body>
</html>
"""
    OUT.write_text(html_doc, encoding="utf-8")
    print(f"写入 {OUT}")


if __name__ == "__main__":
    main()
