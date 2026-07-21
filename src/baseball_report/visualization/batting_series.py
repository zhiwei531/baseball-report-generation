from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import TypedDict

Point3D = tuple[float, float, float]
SeriesPoint = tuple[float, float, int]


class MarkerFrame(TypedDict):
    frame: int
    time: float | None
    points: dict[str, Point3D]


class BattingTimeSeries(TypedDict):
    speed: list[SeriesPoint]
    angle: list[SeriesPoint]
    contact_time: float | None
    peak_time: float | None


class KineticCurve(TypedDict):
    label: str
    points: list[SeriesPoint]
    axis: str


def _optional_float(value: object) -> float | None:
    try:
        parsed = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def load_pose3d_marker_frames(
    pose_path: Path,
    clip_id: str,
    *,
    required_points: frozenset[str] = frozenset(),
) -> list[MarkerFrame]:
    if not pose_path.exists():
        return []
    frames: dict[int, MarkerFrame] = {}
    with pose_path.open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            joint_name = row.get("joint_name") or ""
            if row.get("clip_id") != clip_id:
                continue
            if required_points and joint_name not in required_points:
                continue
            frame = int(float(row["frame_index"]))
            item = frames.setdefault(
                frame,
                {
                    "frame": frame,
                    "time": _optional_float(row.get("timestamp_sec")),
                    "points": {},
                },
            )
            item["points"][joint_name] = (
                float(row["x_3d"]),
                float(row["y_3d"]),
                float(row["z_3d"]),
            )
    return [
        frames[frame]
        for frame in sorted(frames)
        if not required_points or required_points <= frames[frame]["points"].keys()
    ]


def _parse_frame_list(value: object) -> list[int]:
    if value in (None, ""):
        return []
    return [int(part) for part in str(value).split(";") if part.strip().isdigit()]


def _json_object(value: object) -> dict[str, object]:
    if not isinstance(value, str) or not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _vector_length(vector: Point3D) -> float:
    return math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)


def _moving_average(values: list[float | None], radius: int = 2) -> list[float | None]:
    output: list[float | None] = []
    for index in range(len(values)):
        window = [
            value
            for value in values[max(0, index - radius) : index + radius + 1]
            if value is not None and math.isfinite(value)
        ]
        output.append(sum(window) / len(window) if window else None)
    return output


def build_batting_time_series(
    pose_path: Path,
    rows_by_key: dict[str, dict[str, str]],
    clip_id: str,
) -> BattingTimeSeries:
    raw = load_pose3d_marker_frames(
        pose_path,
        clip_id,
        required_points=frozenset({"Bat1", "Bat5"}),
    )
    if not raw:
        return {"speed": [], "angle": [], "contact_time": None, "peak_time": None}
    speed_values: list[float | None] = [None]
    angle_values: list[float | None] = []
    for index, item in enumerate(raw):
        bat1 = item["points"]["Bat1"]
        bat5 = item["points"]["Bat5"]
        axis = (bat1[0] - bat5[0], bat1[1] - bat5[1], bat1[2] - bat5[2])
        angle_values.append(math.degrees(math.atan2(axis[2], math.hypot(axis[0], axis[1]))))
        if index > 0:
            previous = raw[index - 1]
            previous_bat1 = previous["points"]["Bat1"]
            delta_time = float(item["time"]) - float(previous["time"])
            if delta_time > 0:
                difference = (
                    bat1[0] - previous_bat1[0],
                    bat1[1] - previous_bat1[1],
                    bat1[2] - previous_bat1[2],
                )
                speed_values.append(_vector_length(difference) / delta_time * 3.6 / 1000.0)
            else:
                speed_values.append(None)
    speed_values = _moving_average(speed_values, 2)
    angle_values = _moving_average(angle_values, 2)
    speed = [
        (float(item["time"]), value, item["frame"])
        for item, value in zip(raw, speed_values)
        if value is not None
    ]
    angle = [
        (float(item["time"]), value, item["frame"])
        for item, value in zip(raw, angle_values)
        if value is not None
    ]

    contact = rows_by_key.get("contact_bat_speed_kmh", {})
    issue = rows_by_key.get("coach_high_com_risk_index", {})
    components = _json_object(issue.get("components_json"))
    swing_frames = _parse_frame_list(components.get("swing_segment_frames"))
    frame_times = {item["frame"]: float(item["time"]) for item in raw}
    contact_time = (
        frame_times.get(int(contact.get("event_frame", -1)))
        if contact.get("event_frame")
        else None
    )
    peak_time = (
        frame_times.get(int(components.get("swing_peak_frame", -1)))
        if components.get("swing_peak_frame")
        else None
    )
    if swing_frames:
        lower = min(swing_frames) - 18
        upper = max(swing_frames) + 18
        speed = [item for item in speed if lower <= item[2] <= upper]
        angle = [item for item in angle if lower <= item[2] <= upper]
    if contact_time is not None:
        speed = [(time - contact_time, value, frame) for time, value, frame in speed]
        angle = [(time - contact_time, value, frame) for time, value, frame in angle]
        if peak_time is not None:
            peak_time -= contact_time
    return {
        "speed": speed,
        "angle": angle,
        "contact_time": 0.0 if contact_time is not None else None,
        "peak_time": peak_time,
    }


def _angle_between_vectors(first: Point3D, second: Point3D) -> float | None:
    denominator = _vector_length(first) * _vector_length(second)
    if denominator <= 1e-9:
        return None
    cosine = max(
        -1.0,
        min(
            1.0,
            (first[0] * second[0] + first[1] * second[1] + first[2] * second[2])
            / denominator,
        ),
    )
    return math.degrees(math.acos(cosine))


def _horizontal_line_angle(points: dict[str, Point3D], first: str, second: str) -> float | None:
    if first not in points or second not in points:
        return None
    point_a = points[first]
    point_b = points[second]
    return math.degrees(math.atan2(point_a[1] - point_b[1], point_a[0] - point_b[0]))


def _joint_angle(
    points: dict[str, Point3D], first: str, vertex: str, third: str
) -> float | None:
    if first not in points or vertex not in points or third not in points:
        return None
    point_a = points[first]
    point_b = points[vertex]
    point_c = points[third]
    return _angle_between_vectors(
        (point_a[0] - point_b[0], point_a[1] - point_b[1], point_a[2] - point_b[2]),
        (point_c[0] - point_b[0], point_c[1] - point_b[1], point_c[2] - point_b[2]),
    )


def _wrap_angle_delta(current: float, previous: float) -> float:
    return (current - previous + 180.0) % 360.0 - 180.0


def build_kinetic_speed_series(
    pose_path: Path,
    rows_by_key: dict[str, dict[str, str]],
    clip_id: str,
) -> list[KineticCurve]:
    raw = load_pose3d_marker_frames(pose_path, clip_id)
    if not raw:
        return []
    issue = rows_by_key.get("coach_high_com_risk_index", {})
    contact = rows_by_key.get("contact_bat_speed_kmh", {})
    components = _json_object(issue.get("components_json"))
    swing_frames = _parse_frame_list(components.get("swing_segment_frames"))
    contact_frame = int(contact.get("event_frame", -1)) if contact.get("event_frame") else None
    frame_times = {
        item["frame"]: float(item["time"])
        for item in raw
        if item.get("time") is not None
    }
    contact_time = frame_times.get(contact_frame) if contact_frame is not None else None
    if swing_frames:
        lower = min(swing_frames) - 18
        upper = max(swing_frames) + 18
        raw = [item for item in raw if lower <= item["frame"] <= upper]

    angle_definitions = (
        ("下肢", lambda points: _joint_angle(points, "RASI", "RKNE", "RANK"), False),
        ("髋部", lambda points: _horizontal_line_angle(points, "RASI", "LASI"), True),
        ("躯干", lambda points: _horizontal_line_angle(points, "RSHO", "LSHO"), True),
        ("手腕", lambda points: _horizontal_line_angle(points, "RWRA", "RELB"), True),
    )
    series: list[KineticCurve] = []
    for label, angle_function, wraps in angle_definitions:
        samples: list[tuple[float, float, int, float] | None] = []
        for item in raw:
            if item.get("time") is None:
                samples.append(None)
                continue
            value = angle_function(item["points"])
            if value is None:
                samples.append(None)
            else:
                time = float(item["time"])
                samples.append(
                    (
                        time,
                        time - contact_time if contact_time is not None else time,
                        item["frame"],
                        value,
                    )
                )
        values: list[float | None] = [None]
        for index in range(1, len(samples)):
            current = samples[index]
            previous = samples[index - 1]
            if current is None or previous is None:
                values.append(None)
                continue
            delta_time = current[0] - previous[0]
            if delta_time <= 0:
                values.append(None)
                continue
            delta = (
                _wrap_angle_delta(current[3], previous[3])
                if wraps
                else current[3] - previous[3]
            )
            values.append(abs(delta) / delta_time)
        values = _moving_average(values, 2)
        points = [
            (sample[1], value, sample[2])
            for sample, value in zip(samples, values)
            if sample is not None and value is not None
        ]
        series.append({"label": label, "points": points, "axis": "angular"})

    centers: list[tuple[float, float, int, Point3D] | None] = []
    for item in raw:
        center = item["points"].get("Bat1")
        if center is None or item.get("time") is None:
            centers.append(None)
        else:
            time = float(item["time"])
            centers.append(
                (
                    time,
                    time - contact_time if contact_time is not None else time,
                    item["frame"],
                    center,
                )
            )
    linear_values: list[float | None] = [None]
    for index in range(1, len(centers)):
        current = centers[index]
        previous = centers[index - 1]
        if current is None or previous is None:
            linear_values.append(None)
            continue
        delta_time = current[0] - previous[0]
        if delta_time <= 0:
            linear_values.append(None)
            continue
        difference = (
            current[3][0] - previous[3][0],
            current[3][1] - previous[3][1],
            current[3][2] - previous[3][2],
        )
        linear_values.append(_vector_length(difference) / delta_time * 3.6 / 1000.0)
    linear_values = _moving_average(linear_values, 2)
    bat_points = [
        (center[1], value, center[2])
        for center, value in zip(centers, linear_values)
        if center is not None and value is not None
    ]
    series.append({"label": "球棒", "points": bat_points, "axis": "speed"})
    return series
