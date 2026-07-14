from __future__ import annotations

import argparse
import csv
import math
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from build_vicon_2026_metrics import clean_label, read_c3d
from render_vicon_reconstruction_images import (
    DEFAULT_GIF_AFTER_SEC,
    DEFAULT_GIF_BEFORE_SEC,
    RENDER_DPI,
    RENDER_FIGSIZE,
    bat1_tail_frame_indices,
    bat1_trajectory_points,
    draw_reconstruction,
    key_action_frame_indices,
    trial_axis_limits,
    trial_frame_points,
    zh_font,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics.csv"
DEFAULT_POINTS = ROOT / "reports" / "vicon_2026_julian_coach" / "vicon_2026_point_summary.csv"
DEFAULT_OUT_DIR = ROOT / "reports" / "vicon_2026_julian_coach" / "assets" / "vicon_reconstruction_annotated"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def point_series(trial, *names: str) -> np.ndarray:
    clean = [clean_label(label) for label in trial.labels]
    series = []
    for name in names:
        if name in clean:
            series.append(trial.points[:, clean.index(name), :3])
    if not series:
        return np.full((trial.points.shape[0], 3), np.nan)
    stacked = np.stack(series)
    valid = np.isfinite(stacked)
    counts = valid.sum(axis=0)
    total = np.nansum(stacked, axis=0)
    return np.divide(total, counts, out=np.full_like(total, np.nan, dtype=float), where=counts > 0)


def speed_kmh(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    diff_m = np.diff(points_mm, axis=0) / 1000.0
    speed = np.linalg.norm(diff_m, axis=1) * rate_hz * 3.6
    return np.concatenate([[np.nan], speed])


def velocity_mm_s(points_mm: np.ndarray, rate_hz: float) -> np.ndarray:
    return np.vstack([np.full(3, np.nan), np.diff(points_mm, axis=0) * rate_hz])


def signed_angle_about_axis(radial: np.ndarray, axis: np.ndarray, reference: np.ndarray) -> np.ndarray:
    axis_norm = np.linalg.norm(axis, axis=1, keepdims=True)
    axis_unit = np.divide(axis, axis_norm, out=np.full_like(axis, np.nan), where=axis_norm > 0)
    ref_proj = reference - axis_unit * np.einsum("ij,ij->i", reference, axis_unit)[:, None]
    radial_proj = radial - axis_unit * np.einsum("ij,ij->i", radial, axis_unit)[:, None]
    ref_norm = np.linalg.norm(ref_proj, axis=1, keepdims=True)
    radial_norm = np.linalg.norm(radial_proj, axis=1, keepdims=True)
    ref_unit = np.divide(ref_proj, ref_norm, out=np.full_like(ref_proj, np.nan), where=ref_norm > 0)
    radial_unit = np.divide(
        radial_proj, radial_norm, out=np.full_like(radial_proj, np.nan), where=radial_norm > 0
    )
    sin_v = np.einsum("ij,ij->i", np.cross(ref_unit, radial_unit), axis_unit)
    cos_v = np.einsum("ij,ij->i", ref_unit, radial_unit)
    return np.degrees(np.arctan2(sin_v, cos_v))


def frame_metrics(trial) -> dict[str, np.ndarray]:
    bat1 = point_series(trial, "Bat1")
    bat_speed = speed_kmh(bat1, trial.rate_hz)
    bat_velocity = velocity_mm_s(bat1, trial.rate_hz)
    attack_angle = np.degrees(
        np.arctan2(bat_velocity[:, 2], np.linalg.norm(bat_velocity[:, :2], axis=1))
    )
    relb = point_series(trial, "RELB")
    rwra = point_series(trial, "RWRA")
    rwrb = point_series(trial, "RWRB")
    forearm_axis = rwrb - relb
    wrist_radial = rwra - rwrb
    reference = np.tile(np.array([0.0, 0.0, 1.0]), (trial.points.shape[0], 1))
    roll = np.unwrap(np.radians(signed_angle_about_axis(wrist_radial, forearm_axis, reference)))
    roll_deg = np.degrees(roll)
    roll_velocity = np.concatenate([[np.nan], np.diff(roll_deg) * trial.rate_hz])
    return {
        "bat_speed": bat_speed,
        "attack_angle": attack_angle,
        "roll_velocity": np.abs(roll_velocity),
    }


def parse_segment(rule: str, fallback_frames: str) -> tuple[int, int]:
    match = re.search(r"expanded frames (\d+)-(\d+)", rule)
    if match:
        return int(match.group(1)), int(match.group(2))
    frames = [int(item) for item in fallback_frames.split(";") if item.strip()]
    if frames:
        return min(frames), max(frames)
    return 0, 0


def sample_indices(start: int, end: int, max_frames: int) -> np.ndarray:
    if end <= start:
        return np.array([start], dtype=int)
    count = min(max_frames, end - start + 1)
    return np.linspace(start, end, count, dtype=int)


def rows_for_trial(rows: list[dict[str, str]], trial_id: str) -> list[dict[str, str]]:
    return [row for row in rows if row.get("trial_id") == trial_id]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/System/Library/Fonts/STHeiti Medium.ttc"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
    ):
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fmt(value: float, unit: str) -> str:
    if not math.isfinite(value):
        return "NA"
    if unit == "km/h":
        return f"{value:.1f} km/h"
    if unit == "deg":
        return f"{value:.1f} deg"
    if unit == "deg/s":
        return f"{value:.0f} deg/s"
    return f"{value:.1f}"


def draw_metric_cards(image: Image.Image, frame_idx: int, metrics: dict[str, np.ndarray]) -> Image.Image:
    out = image.convert("RGBA")
    draw = ImageDraw.Draw(out, "RGBA")
    title_font = font(27)
    value_font = font(35)
    small_font = font(21)
    x = 42
    y = 250
    w = 320
    h = 116
    gap = 16
    cards = [
        ("Bat speed", fmt(float(metrics["bat_speed"][frame_idx]), "km/h")),
        ("Attack angle", fmt(float(metrics["attack_angle"][frame_idx]), "deg")),
        ("Forearm roll speed", fmt(float(metrics["roll_velocity"][frame_idx]), "deg/s")),
    ]
    for i, (label, value) in enumerate(cards):
        top = y + i * (h + gap)
        draw.rounded_rectangle(
            (x, top, x + w, top + h),
            radius=14,
            fill=(255, 255, 255, 238),
            outline=(208, 213, 221, 240),
            width=2,
        )
        draw.text((x + 18, top + 12), label, fill=(71, 84, 103, 255), font=title_font)
        draw.text((x + 18, top + 45), value, fill=(16, 24, 40, 255), font=value_font)
        draw.text((x + 18, top + 88), f"frame {frame_idx}", fill=(102, 112, 133, 255), font=small_font)
    return out.convert("P", palette=Image.Palette.ADAPTIVE)


def render_annotated_gif(trial, frame_indices: np.ndarray, out_path: Path, sample_name: str) -> None:
    metrics = frame_metrics(trial)
    limits = trial_axis_limits(trial, frame_indices=frame_indices)
    font_prop = zh_font()
    fig = plt.figure(figsize=RENDER_FIGSIZE, dpi=RENDER_DPI)
    fig.patch.set_facecolor("#ffffff")
    ax = fig.add_subplot(111, projection="3d")
    fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
    frames: list[Image.Image] = []
    title = f"{sample_name} / 打击 / C3D骨架动图"
    for frame_idx in frame_indices:
        frame_int = int(frame_idx)
        ax.clear()
        points = trial_frame_points(trial, frame_int, smooth_radius=2)
        trajectory = bat1_trajectory_points(trial, bat1_tail_frame_indices(trial, frame_int), smooth_radius=2)
        draw_reconstruction(
            ax,
            points,
            font_prop,
            title,
            frame_label=f"整段动作窗口逐帧速度 / 第{frame_int}帧 / {frame_int / trial.rate_hz:.2f}秒",
            show_labels=False,
            axis_limits=limits,
            fixed_layout_legend=True,
            bat1_trajectory=trajectory,
            recenter_limits=False,
        )
        fig.canvas.draw()
        width, height = fig.canvas.get_width_height()
        frame = Image.frombytes("RGBA", (width, height), fig.canvas.buffer_rgba())
        frames.append(draw_metric_cards(frame, frame_int, metrics))
    plt.close(fig)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        out_path,
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        optimize=True,
        disposal=2,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render frame-by-frame annotated speed GIFs for Julian/Coach.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--points", type=Path, default=DEFAULT_POINTS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--max-frames", type=int, default=140)
    parser.add_argument("--before-sec", type=float, default=DEFAULT_GIF_BEFORE_SEC)
    parser.add_argument("--after-sec", type=float, default=DEFAULT_GIF_AFTER_SEC)
    parser.add_argument("--samples", nargs="+", default=["julian", "coach"])
    args = parser.parse_args()

    metric_rows = read_csv(args.metrics)
    point_rows = read_csv(args.points)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    for sample in args.samples:
        contact = next(
            (
                row
                for row in metric_rows
                if row["sample_name"] == sample and row["metric_key"] == "contact_bat_speed_kmh"
            ),
            None,
        )
        if contact is None:
            raise SystemExit(f"Missing contact_bat_speed_kmh row for sample_name={sample}")
        c3d_path = ROOT.parent / contact["source_file"]
        trial = read_c3d(c3d_path)
        trial_rows = rows_for_trial(point_rows, contact["trial_id"])
        frame_indices, _event = key_action_frame_indices(
            trial,
            trial_rows,
            before_sec=args.before_sec,
            after_sec=args.after_sec,
            max_frames=args.max_frames,
        )
        out_path = args.out_dir / f"{sample}_speed_annotated.gif"
        render_annotated_gif(trial, frame_indices, out_path, sample)
        print(out_path)


if __name__ == "__main__":
    main()
