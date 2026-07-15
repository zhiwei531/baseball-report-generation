from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from render_vicon_reconstruction_images import (  # noqa: E402
    RENDER_DPI,
    RENDER_FIGSIZE,
    bat1_tail_frame_indices,
    bat1_trajectory_points,
    draw_reconstruction,
    read_c3d,
    trial_axis_limits,
    trial_frame_points,
    zh_font,
)


DEFAULT_SUMMARY = ROOT / "reports" / "vicon_2026_julian_coach" / "alignment_2d" / "alignment_summary.json"

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/Library/Fonts/Arial Unicode.ttf",
]


def load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in FONT_CANDIDATES:
        if Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


def fit_image(image: np.ndarray, size: tuple[int, int]) -> np.ndarray:
    target_w, target_h = size
    h, w = image.shape[:2]
    scale = min(target_w / w, target_h / h)
    new_w = int(round(w * scale))
    new_h = int(round(h * scale))
    resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
    canvas = np.full((target_h, target_w, 3), 245, dtype=np.uint8)
    x = (target_w - new_w) // 2
    y = (target_h - new_h) // 2
    canvas[y : y + new_h, x : x + new_w] = resized
    return canvas


def draw_panel_header(image: np.ndarray, title: str, subtitle: str) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
    draw = ImageDraw.Draw(pil, "RGBA")
    title_font = load_font(30)
    sub_font = load_font(20)
    draw.rounded_rectangle((16, 14, image.shape[1] - 16, 86), radius=12, fill=(14, 22, 36, 210))
    draw.text((34, 24), title, font=title_font, fill=(255, 255, 255, 255))
    draw.text((36, 58), subtitle, font=sub_font, fill=(218, 226, 238, 255))
    return cv2.cvtColor(np.asarray(pil.convert("RGB")), cv2.COLOR_RGB2BGR)


def draw_center_banner(image: np.ndarray, text: str) -> np.ndarray:
    pil = Image.fromarray(cv2.cvtColor(image, cv2.COLOR_BGR2RGB)).convert("RGBA")
    draw = ImageDraw.Draw(pil, "RGBA")
    font = load_font(24)
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    draw.rounded_rectangle((image.shape[1] // 2 - w // 2 - 20, 650, image.shape[1] // 2 + w // 2 + 20, 704), radius=12, fill=(14, 22, 36, 210))
    draw.text((image.shape[1] // 2 - w // 2, 664), text, font=font, fill=(255, 255, 255, 245))
    return cv2.cvtColor(np.asarray(pil.convert("RGB")), cv2.COLOR_RGB2BGR)


class ViconRenderer:
    def __init__(self, c3d_path: Path, frame_indices: np.ndarray, player_label: str) -> None:
        self.trial = read_c3d(c3d_path)
        self.axis_limits = trial_axis_limits(self.trial, frame_indices=frame_indices)
        self.font_prop = zh_font()
        self.fig = plt.figure(figsize=RENDER_FIGSIZE, dpi=RENDER_DPI)
        self.fig.patch.set_facecolor("#ffffff")
        self.ax = self.fig.add_subplot(111, projection="3d")
        self.fig.subplots_adjust(left=0.02, right=0.98, bottom=0.02, top=0.94)
        self.player_label = player_label

    def close(self) -> None:
        plt.close(self.fig)

    def render(self, frame_idx: int) -> np.ndarray:
        self.ax.clear()
        points = trial_frame_points(self.trial, frame_idx, smooth_radius=2)
        trajectory = bat1_trajectory_points(self.trial, bat1_tail_frame_indices(self.trial, frame_idx), smooth_radius=2)
        draw_reconstruction(
            self.ax,
            points,
            self.font_prop,
            f"{self.player_label} / Vicon C3D 3D reconstruction",
            frame_label=f"Vicon frame {frame_idx} / {frame_idx / self.trial.rate_hz:.2f}s",
            show_labels=False,
            axis_limits=self.axis_limits,
            fixed_layout_legend=True,
            bat1_trajectory=trajectory,
            recenter_limits=False,
        )
        self.fig.canvas.draw()
        w, h = self.fig.canvas.get_width_height()
        rgba = np.asarray(Image.frombytes("RGBA", (w, h), self.fig.canvas.buffer_rgba()).convert("RGB"))
        return cv2.cvtColor(rgba, cv2.COLOR_RGB2BGR)


def video_frame_to_vicon(video_frame: int, video_fps: float, offset_sec: float, vicon_rate_hz: float, scale: float) -> int:
    video_time = video_frame / video_fps
    return int(round(((video_time - offset_sec) / scale) * vicon_rate_hz))


def main() -> None:
    parser = argparse.ArgumentParser(description="Render side-by-side 2D video frame and aligned Vicon 3D reconstruction.")
    parser.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--player-slug", required=True)
    parser.add_argument("--player-label", required=True)
    parser.add_argument("--sample-step", type=int, default=3, help="Use every Nth source video frame.")
    parser.add_argument("--max-frames", type=int, default=160)
    args = parser.parse_args()

    summary: dict[str, Any] = json.loads(args.summary.read_text(encoding="utf-8"))
    video_path = Path(summary["video"])
    c3d_path = Path(summary["c3d"])
    video_fps = float(summary["video_meta"]["fps"])
    vicon_rate = float(summary["vicon_meta"]["rate_hz"])
    vicon_count = int(summary["vicon_meta"]["frames"])
    alignment = summary["alignment"]
    scale = float(alignment.get("slow_motion_factor", 1.0))
    offset = float(
        alignment.get(
            "time_offset_sec_add_to_scaled_vicon_time",
            alignment.get("time_offset_sec_add_to_vicon_time", 0.0),
        )
    )

    start_video = max(0, int(round(offset * video_fps)))
    end_video = min(
        int(summary["video_meta"]["frames_read"]) - 1,
        int(round(((vicon_count - 1) / vicon_rate * scale + offset) * video_fps)),
    )
    video_frames = list(range(start_video, end_video + 1, max(1, args.sample_step)))
    if len(video_frames) > args.max_frames:
        idx = np.linspace(0, len(video_frames) - 1, args.max_frames, dtype=int)
        video_frames = [video_frames[i] for i in idx]
    vicon_frames = np.array(
        [video_frame_to_vicon(frame, video_fps, offset, vicon_rate, scale) for frame in video_frames],
        dtype=int,
    )
    vicon_frames = np.clip(vicon_frames, 0, vicon_count - 1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_path = args.out_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction.mp4"
    preview_path = args.out_dir / f"{args.player_slug}_2d_video_vs_vicon_3d_reconstruction_preview.jpg"

    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open 2D video: {video_path}")
    out_fps = video_fps / max(1, args.sample_step)
    panel_size = (960, 540)
    canvas_size = (1920, 720)
    writer = cv2.VideoWriter(str(out_path), cv2.VideoWriter_fourcc(*"mp4v"), out_fps, canvas_size)
    if not writer.isOpened():
        raise RuntimeError(f"Cannot create output: {out_path}")

    renderer = ViconRenderer(c3d_path, frame_indices=vicon_frames, player_label=args.player_label)
    preview_written = False
    try:
        for video_frame, vicon_frame in zip(video_frames, vicon_frames):
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(video_frame))
            ok, frame2d = cap.read()
            if not ok:
                continue
            vicon_img = renderer.render(int(vicon_frame))
            left = fit_image(frame2d, panel_size)
            right = fit_image(vicon_img, panel_size)
            left = draw_panel_header(left, "2D video frame", f"video frame {video_frame} / {video_frame / video_fps:.2f}s")
            right = draw_panel_header(right, "Vicon 3D model reconstruction", f"Vicon frame {int(vicon_frame)} / {int(vicon_frame) / vicon_rate:.2f}s")
            canvas = np.full((canvas_size[1], canvas_size[0], 3), 238, dtype=np.uint8)
            canvas[90 : 90 + panel_size[1], 0 : panel_size[0]] = left
            canvas[90 : 90 + panel_size[1], panel_size[0] : panel_size[0] * 2] = right
            cv2.line(canvas, (panel_size[0], 90), (panel_size[0], 90 + panel_size[1]), (208, 213, 221), 2)
            canvas = draw_center_banner(
                canvas,
                f"alignment: video_time = vicon_time * {scale:.3f} + {offset:.3f}s | event: 2D frame {summary['video_event']['frame_index']} = Vicon frame {summary['vicon_event']['frame_index']}",
            )
            writer.write(canvas)
            if not preview_written and abs(int(vicon_frame) - int(summary["vicon_event"]["frame_index"])) <= 2:
                cv2.imwrite(str(preview_path), canvas)
                preview_written = True
    finally:
        renderer.close()
        cap.release()
        writer.release()

    if not preview_written:
        cap2 = cv2.VideoCapture(str(out_path))
        ok, preview = cap2.read()
        if ok:
            cv2.imwrite(str(preview_path), preview)
        cap2.release()

    report = {
        "output": str(out_path),
        "preview": str(preview_path),
        "sample_step": args.sample_step,
        "fps": out_fps,
        "frames_written": len(video_frames),
        "video_frame_range": [video_frames[0], video_frames[-1]],
        "vicon_frame_range": [int(vicon_frames[0]), int(vicon_frames[-1])],
        "alignment_offset_sec": offset,
        "slow_motion_factor": scale,
    }
    (args.out_dir / "alignment_comparison_summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
