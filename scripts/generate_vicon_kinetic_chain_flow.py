"""Generate a kinetic-chain flow PNG directly from Vicon point data."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POINTS = ROOT / "reports/vicon_2026_julian_coach/vicon_2026_points_all.csv"
DEFAULT_METRICS = ROOT / "reports/vicon_2026_julian_coach/batting_dashboard_metrics.csv"
DEFAULT_OUTPUT = ROOT / "output/figures/vicon_kinetic_chain_flow.png"
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/Library/Fonts/Arial Unicode.ttf"),
]


def cn_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def valid_points(df: pd.DataFrame) -> pd.DataFrame:
    required = {"trial_id", "frame_index", "timestamp_sec", "point", "x_mm", "y_mm", "z_mm"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    out = df.copy()
    if "valid" in out.columns:
        out = out[out["valid"].fillna(0).astype(float) > 0]
    return out.dropna(subset=["frame_index", "timestamp_sec", "point", "x_mm", "y_mm", "z_mm"])


def select_trial(df: pd.DataFrame, trial_id: str | None, action_type: str) -> str:
    if trial_id:
        if trial_id not in set(df["trial_id"].astype(str)):
            raise ValueError(f"Trial id not found: {trial_id}")
        return trial_id
    candidates = df
    if "action_type" in candidates.columns:
        candidates = candidates[candidates["action_type"].astype(str).str.lower().eq(action_type.lower())]
    ids = candidates["trial_id"].dropna().astype(str).drop_duplicates().tolist()
    if not ids:
        raise ValueError(f"No trial found for action_type={action_type!r}")
    return ids[0]


def pivot_points(df: pd.DataFrame, trial_id: str) -> pd.DataFrame:
    sub = df[df["trial_id"].astype(str).eq(trial_id)].copy()
    if sub.empty:
        raise ValueError(f"No rows for trial_id={trial_id}")
    sub["frame_index"] = sub["frame_index"].astype(int)
    for axis in ("x_mm", "y_mm", "z_mm"):
        sub[axis] = sub[axis].astype(float) / 1000.0
    wide = sub.pivot_table(
        index=["frame_index", "timestamp_sec"],
        columns="point",
        values=["x_mm", "y_mm", "z_mm"],
        aggfunc="mean",
    )
    wide.columns = [f"{point}_{axis[:-3]}" for axis, point in wide.columns]
    wide = wide.reset_index().sort_values("frame_index").set_index("frame_index")
    return wide.interpolate(limit_direction="both")


def first_existing(wide: pd.DataFrame, names: list[str]) -> str:
    for name in names:
        if all(f"{name}_{axis}" in wide.columns for axis in ("x", "y", "z")):
            return name
    raise ValueError(f"None of these points are available: {', '.join(names)}")


def midpoint(wide: pd.DataFrame, left: str, right: str) -> pd.DataFrame:
    return pd.DataFrame(
        {
            axis: (wide[f"{left}_{axis}"].astype(float) + wide[f"{right}_{axis}"].astype(float)) / 2.0
            for axis in ("x", "y", "z")
        },
        index=wide.index,
    )


def line_yaw_deg(wide: pd.DataFrame, left: str, right: str) -> np.ndarray:
    dx = wide[f"{right}_x"].to_numpy(dtype=float) - wide[f"{left}_x"].to_numpy(dtype=float)
    dz = wide[f"{right}_z"].to_numpy(dtype=float) - wide[f"{left}_z"].to_numpy(dtype=float)
    return np.degrees(np.arctan2(dz, dx))


def angular_velocity_deg_s(angle_deg: np.ndarray, time_s: np.ndarray) -> np.ndarray:
    keep = np.isfinite(angle_deg) & np.isfinite(time_s)
    out = np.full_like(angle_deg, np.nan, dtype=float)
    if int(keep.sum()) < 3:
        return out
    unwrapped = np.unwrap(np.radians(angle_deg[keep]))
    out[keep] = np.degrees(np.gradient(unwrapped, time_s[keep]))
    return out


def point_speed_m_s(wide: pd.DataFrame, point: str, time_s: np.ndarray) -> np.ndarray:
    cols = [f"{point}_{axis}" for axis in ("x", "y", "z")]
    values = [wide[col].to_numpy(dtype=float) for col in cols]
    keep = np.isfinite(time_s)
    for arr in values:
        keep &= np.isfinite(arr)
    out = np.full(len(wide), np.nan, dtype=float)
    if int(keep.sum()) < 3:
        return out
    gradients = [np.gradient(arr[keep], time_s[keep]) for arr in values]
    out[keep] = np.sqrt(sum(g * g for g in gradients))
    return out


def robust_peak(values: np.ndarray) -> float:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan")
    return float(np.nanpercentile(np.abs(finite), 95))


def parse_frame_list(text: object) -> list[int]:
    if text is None or (isinstance(text, float) and np.isnan(text)):
        return []
    return [int(item) for item in str(text).split(";") if item.strip().isdigit()]


def infer_window_from_metrics(metrics_csv: Path, trial_id: str) -> tuple[int, int, str] | None:
    if not metrics_csv.exists():
        return None
    rows = pd.read_csv(metrics_csv)
    rows = rows[rows["trial_id"].astype(str).eq(trial_id)]
    if rows.empty:
        return None

    for _, row in rows.iterrows():
        try:
            components = json.loads(row.get("components_json") or "{}")
        except json.JSONDecodeError:
            components = {}
        frames = parse_frame_list(components.get("swing_segment_frames"))
        if frames:
            return min(frames), max(frames), "swing_segment_frames"

    for _, row in rows.iterrows():
        match = re.search(r"expanded frames\s+(\d+)-(\d+)", str(row.get("event_rule", "")))
        if match:
            return int(match.group(1)), int(match.group(2)), "event_rule expanded frames"
    return None


def frame_mask(frames: np.ndarray, window: tuple[int, int] | None) -> np.ndarray:
    keep = np.ones(frames.shape, dtype=bool)
    if window is not None:
        keep &= frames >= window[0]
        keep &= frames <= window[1]
    return keep


def peak_value_and_frame(values: np.ndarray, frames: np.ndarray, keep: np.ndarray) -> tuple[float, int | None]:
    valid = keep & np.isfinite(values)
    if int(valid.sum()) == 0:
        return float("nan"), None
    scoped_values = np.abs(values[valid])
    scoped_frames = frames[valid]
    idx = int(np.nanargmax(scoped_values))
    return float(scoped_values[idx]), int(scoped_frames[idx])


def compute_chain_metrics(wide: pd.DataFrame, window: tuple[int, int] | None = None) -> dict[str, float | str | int | None]:
    time_s = wide["timestamp_sec"].to_numpy(dtype=float)
    if len(np.unique(time_s[np.isfinite(time_s)])) < 3:
        frames = wide.index.to_numpy(dtype=float)
        time_s = (frames - frames.min()) / 100.0
    frames = wide.index.to_numpy(dtype=int)
    keep = frame_mask(frames, window)
    if int(keep.sum()) < 3:
        raise ValueError(f"Frame window {window} has fewer than 3 usable frames")

    left_pelvis = first_existing(wide, ["LASI", "LPSI", "PELA", "PELL"])
    right_pelvis = first_existing(wide, ["RASI", "RPSI", "PELA", "PELP"])
    left_shoulder = first_existing(wide, ["LSHO", "LUPA", "LCLA"])
    right_shoulder = first_existing(wide, ["RSHO", "RUPA", "RCLA"])
    shoulder_point = first_existing(wide, ["RSHO", "RUPA", "RCLA"])
    elbow_point = first_existing(wide, ["RELB", "RFRM", "RUPA"])
    hand_point = first_existing(wide, ["RWRA", "RWRB", "RFIN", "RFRM"])

    pelvis_yaw = line_yaw_deg(wide, left_pelvis, right_pelvis)
    trunk_yaw = line_yaw_deg(wide, left_shoulder, right_shoulder)
    pelvis_vel_series = angular_velocity_deg_s(pelvis_yaw, time_s)
    trunk_vel_series = angular_velocity_deg_s(trunk_yaw, time_s)
    shoulder_speed_series = point_speed_m_s(wide, shoulder_point, time_s)
    elbow_speed_series = point_speed_m_s(wide, elbow_point, time_s)
    hand_speed_series = point_speed_m_s(wide, hand_point, time_s)

    pelvis_vel, pelvis_frame = peak_value_and_frame(pelvis_vel_series, frames, keep)
    trunk_vel, trunk_frame = peak_value_and_frame(trunk_vel_series, frames, keep)
    shoulder_speed, shoulder_frame = peak_value_and_frame(shoulder_speed_series, frames, keep)
    elbow_speed, elbow_frame = peak_value_and_frame(elbow_speed_series, frames, keep)
    hand_speed, hand_frame = peak_value_and_frame(hand_speed_series, frames, keep)

    return {
        "pelvis_velocity_deg_s": pelvis_vel,
        "trunk_velocity_deg_s": trunk_vel,
        "shoulder_speed_m_s": shoulder_speed,
        "elbow_speed_m_s": elbow_speed,
        "hand_speed_m_s": hand_speed,
        "pelvis_peak_frame": pelvis_frame,
        "trunk_peak_frame": trunk_frame,
        "shoulder_peak_frame": shoulder_frame,
        "elbow_peak_frame": elbow_frame,
        "hand_peak_frame": hand_frame,
        "window_start_frame": int(frames[keep].min()) if int(keep.sum()) else None,
        "window_end_frame": int(frames[keep].max()) if int(keep.sum()) else None,
        "pelvis_points": f"{left_pelvis}-{right_pelvis}",
        "trunk_points": f"{left_shoulder}-{right_shoulder}",
        "shoulder_point": shoulder_point,
        "elbow_point": elbow_point,
        "hand_point": hand_point,
    }


def fmt(value: float, decimals: int) -> str:
    if not np.isfinite(value):
        return "N/A"
    return f"{value:.{decimals}f}"


def frame_text(frame: object) -> str:
    if frame is None or (isinstance(frame, float) and np.isnan(frame)):
        return "峰值帧 N/A"
    return f"峰值帧 {int(frame)}"


def draw_kinetic_chain_flow(metrics: dict[str, float | str | int | None], path: Path, title_suffix: str = "") -> Path:
    w, h = 1600, 760
    im = Image.new("RGB", (w, h), "#ffffff")
    d = ImageDraw.Draw(im)
    title = cn_font(48)
    label = cn_font(28)
    small = cn_font(22)
    value_font = cn_font(34)

    title_text = "动力链流：力量是否从下往上传"
    if title_suffix:
        title_text += f" · {title_suffix}"
    d.text((60, 38), title_text, font=title, fill="#172033")
    window_text = ""
    if metrics.get("window_start_frame") is not None and metrics.get("window_end_frame") is not None:
        window_text = f"计算窗口：Vicon帧 {metrics['window_start_frame']}-{metrics['window_end_frame']}；"
    d.text((60, 100), f"{window_text}近端看旋转速度，远端看关节线速度；每个节点标出窗口内峰值帧。", font=small, fill="#526070")

    nodes = [
        ("骨盆", fmt(float(metrics["pelvis_velocity_deg_s"]), 0), "deg/s", "#dbeafe", "髋部爆发", frame_text(metrics["pelvis_peak_frame"])),
        ("躯干", fmt(float(metrics["trunk_velocity_deg_s"]), 0), "deg/s", "#dbeafe", "上肢传递", frame_text(metrics["trunk_peak_frame"])),
        ("肩部", fmt(float(metrics["shoulder_speed_m_s"]), 1), "m/s", "#dcfce7", "肩部移动", frame_text(metrics["shoulder_peak_frame"])),
        ("肘部", fmt(float(metrics["elbow_speed_m_s"]), 1), "m/s", "#fff7ed", "末端加速", frame_text(metrics["elbow_peak_frame"])),
        ("手部", fmt(float(metrics["hand_speed_m_s"]), 1), "m/s", "#fee2e2", "出手速度", frame_text(metrics["hand_peak_frame"])),
    ]
    xs = [120, 420, 720, 1020, 1320]
    y = 300
    for i, (name, val, unit, fill, desc, peak_frame) in enumerate(nodes):
        x = xs[i]
        d.rounded_rectangle((x, y, x + 210, y + 210), radius=28, fill=fill, outline="#d0d5dd", width=2)
        d.text((x + 38, y + 28), name, font=label, fill="#172033")
        d.text((x + 38, y + 76), val, font=value_font, fill="#2563eb")
        d.text((x + 125, y + 88), unit, font=small, fill="#667085")
        d.text((x + 38, y + 142), desc, font=small, fill="#344054")
        d.text((x + 38, y + 174), peak_frame, font=small, fill="#667085")
        if i < len(nodes) - 1:
            d.line((x + 225, y + 105, xs[i + 1] - 18, y + 105), fill="#98a2b3", width=7)
            d.polygon([(xs[i + 1] - 24, y + 84), (xs[i + 1] + 8, y + 105), (xs[i + 1] - 24, y + 126)], fill="#98a2b3")

    d.rounded_rectangle((80, 610, 1520, 700), radius=20, fill="#eff6ff", outline="#bfdbfe")
    d.text((108, 632), "读图方法：先看各段峰值是否按骨盆、躯干、肩肘手顺序出现，再看远端速度是否继续放大。", font=small, fill="#344054")
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path)
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--points-csv", type=Path, default=DEFAULT_POINTS, help="Vicon points CSV with x_mm/y_mm/z_mm columns.")
    parser.add_argument("--metrics-csv", type=Path, default=DEFAULT_METRICS, help="Optional dashboard metrics CSV used to infer the swing window.")
    parser.add_argument("--trial-id", default=None, help="Trial id to render. Defaults to the first matching action type.")
    parser.add_argument("--action-type", default="pitching", help="Action type used when --trial-id is omitted.")
    parser.add_argument("--window-start-frame", type=int, default=None, help="Override start frame for the calculation window.")
    parser.add_argument("--window-end-frame", type=int, default=None, help="Override end frame for the calculation window.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output PNG path.")
    parser.add_argument("--title-trial", action="store_true", help="Append the trial id to the chart title.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = valid_points(pd.read_csv(args.points_csv))
    trial_id = select_trial(df, args.trial_id, args.action_type)
    wide = pivot_points(df, trial_id)
    inferred = infer_window_from_metrics(args.metrics_csv, trial_id)
    if args.window_start_frame is not None or args.window_end_frame is not None:
        if args.window_start_frame is None or args.window_end_frame is None:
            raise ValueError("--window-start-frame and --window-end-frame must be provided together")
        window = (args.window_start_frame, args.window_end_frame)
        window_source = "cli"
    elif inferred is not None:
        window = (inferred[0], inferred[1])
        window_source = inferred[2]
    else:
        window = None
        window_source = "full_trial"
    metrics = compute_chain_metrics(wide, window)
    output = draw_kinetic_chain_flow(metrics, args.output, trial_id if args.title_trial else "")

    print(f"Wrote {output}")
    print(f"trial_id={trial_id}")
    print(f"window={metrics['window_start_frame']}-{metrics['window_end_frame']} source={window_source}")
    print(
        "metrics="
        f"pelvis {metrics['pelvis_velocity_deg_s']:.1f} deg/s @ frame {metrics['pelvis_peak_frame']}, "
        f"trunk {metrics['trunk_velocity_deg_s']:.1f} deg/s @ frame {metrics['trunk_peak_frame']}, "
        f"shoulder {metrics['shoulder_speed_m_s']:.2f} m/s @ frame {metrics['shoulder_peak_frame']}, "
        f"elbow {metrics['elbow_speed_m_s']:.2f} m/s @ frame {metrics['elbow_peak_frame']}, "
        f"hand {metrics['hand_speed_m_s']:.2f} m/s @ frame {metrics['hand_peak_frame']}"
    )


if __name__ == "__main__":
    main()
