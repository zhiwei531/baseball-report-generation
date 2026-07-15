from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import cv2
from PIL import Image, ImageDraw, ImageFont


SCRIPTS_DIR = Path(__file__).resolve().parents[1]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from render_aligned_2d_overlay import CONNECTIONS, load_pose  # noqa: E402


BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
INK = "#101828"
MID = "#667085"


EVENTS = {
    "peak_knee": {
        "label": "\u62ac\u819d\u6700\u9ad8\u70b9",
        "color": "#16a34a",
        "metrics": (
            ("\u62ac\u819d\u9ad8\u5ea6", "knee_height_pct", "pct", GREEN),
            ("\u524d\u817f\u6536\u7d27", "front_knee_peak_deg", "deg", ORANGE),
            ("\u540e\u817f\u84c4\u529b", "rear_knee_peak_deg", "deg", BLUE),
        ),
    },
    "foot_plant": {
        "label": "\u524d\u811a\u843d\u5730",
        "color": "#f97316",
        "metrics": (
            ("\u8de8\u6b65\u8ddd\u79bb", "stride_distance_pct", "pct", BLUE),
            ("\u524d\u819d\u5c48\u66f2", "front_knee_plant_deg", "deg", ORANGE),
            ("\u6295\u7403\u8098\u76f8\u5bf9\u80a9\u7ebf", "elbow_vs_shoulder_cm", "cm", PURPLE),
        ),
    },
    "release": {
        "label": "\u51fa\u624b\u70b9",
        "color": "#7c3aed",
        "metrics": (
            ("\u51fa\u624b\u80a9\u5916\u5c55", "shoulder_abduction_release_deg", "deg", PURPLE),
            ("\u51fa\u624b\u8098\u5c48\u66f2", "elbow_flex_release_deg", "deg", BLUE),
            ("\u624b\u81c2\u69fd\u4f4d", "arm_slot_deg", "deg", ORANGE),
            ("\u624b\u901f", "hand_speed_kmh", "kmh", PURPLE),
        ),
    },
}


def font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = (
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path("/System/Library/Fonts/PingFang.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
    )
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def fmt(value: Any, unit: str) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "N/A"
    if unit == "pct":
        return f"{number:.1f}%身高比"
    if unit == "deg":
        return f"{number:.1f}\u00b0"
    if unit == "cm":
        return f"{number:.1f} cm"
    if unit == "kmh":
        return f"{number:.1f} km/h"
    return f"{number:.2f}"


def metric_value(values: dict[str, Any], key: str) -> Any:
    """Use the current km/h field, while accepting older m/s summaries."""
    if key == "hand_speed_kmh" and key not in values:
        try:
            return float(values["hand_speed_mps"]) * 3.6
        except (KeyError, TypeError, ValueError):
            return None
    return values.get(key)


def athlete_record(summary: dict[str, Any], key: str) -> dict[str, Any]:
    for row in summary.get("athletes", []):
        if str(row.get("key", "")).casefold() == key.casefold():
            return row
    raise ValueError(f"Athlete {key!r} was not found in the pitching summary")


def read_frame(video: Path, frame_index: int) -> Image.Image:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise RuntimeError(f"Cannot open video: {video}")
    capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
    ok, frame = capture.read()
    capture.release()
    if not ok:
        raise RuntimeError(f"Cannot read frame {frame_index} from {video}")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)).convert("RGB")


def draw_skeleton(draw: ImageDraw.ImageDraw, landmarks: dict[str, tuple[int, int, float]]) -> None:
    for start, end in CONNECTIONS:
        if start in landmarks and end in landmarks:
            draw.line((landmarks[start][:2], landmarks[end][:2]), fill="#7c3aed", width=5)
    for x, y, visibility in landmarks.values():
        radius = 5 if visibility >= 0.75 else 4
        draw.ellipse((x - radius - 2, y - radius - 2, x + radius + 2, y + radius + 2), fill="#ffffff")
        draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill="#7c3aed")


def draw_metric_card(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    width: int,
    title: str,
    value: str,
    color: str,
) -> None:
    height = 92
    draw.rounded_rectangle((x + 8, y + 8, x + width + 8, y + height + 8), radius=16, fill="#111111")
    draw.rounded_rectangle((x, y, x + width, y + height), radius=16, fill="#ffffff", outline=color, width=5)
    draw.text((x + 18, y + 10), title, font=font(26, bold=True), fill=color)
    draw.text((x + 18, y + 44), value, font=font(25), fill=INK)
    draw.text((x + 190, y + 56), "Vicon 3D value", font=font(14), fill=MID)


def render_event(
    *,
    video: Path,
    frame_index: int,
    landmarks: dict[str, tuple[int, int, float]],
    event_key: str,
    values: dict[str, Any],
    output: Path,
) -> None:
    image = read_frame(video, frame_index)
    draw = ImageDraw.Draw(image)
    draw_skeleton(draw, landmarks)
    spec = EVENTS[event_key]
    color = str(spec["color"])
    label = str(spec["label"])
    draw.rounded_rectangle((28, 28, 286, 86), radius=16, fill="#ffffff", outline=color, width=5)
    draw.text((48, 42), label, font=font(28, bold=True), fill=color)
    metrics = spec["metrics"]
    card_width = 378
    start_y = 116 if len(metrics) == 4 else 172
    x = image.width - 412
    for index, (title, metric_key, unit, metric_color) in enumerate(metrics):
        draw_metric_card(
            draw,
            x=x,
            y=start_y + index * 108,
            width=card_width,
            title=title,
            value=fmt(metric_value(values, metric_key), unit),
            color=metric_color,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output, quality=95)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render report-ready pitching event geometry overlays from reviewed 2D/Vicon alignment."
    )
    parser.add_argument("--alignment-dir", required=True, type=Path)
    parser.add_argument("--pitch-summary", required=True, type=Path)
    parser.add_argument("--athlete-key", required=True)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--min-visibility", type=float, default=0.2)
    args = parser.parse_args()

    alignment_dir = args.alignment_dir.resolve()
    alignment = json.loads((alignment_dir / "alignment_summary.json").read_text(encoding="utf-8"))
    pitch_summary = json.loads(args.pitch_summary.resolve().read_text(encoding="utf-8"))
    athlete = athlete_record(pitch_summary, args.athlete_key)
    video = Path(alignment["video"]).resolve()
    poses = load_pose(alignment_dir / "pose2d_landmarks.csv", args.min_visibility)

    video_event_frame = int(alignment["video_event"]["frame_index"])
    # The reviewed video event is explicitly the release frame.  Anchor the
    # report screenshots to the report's release event rather than to the
    # alignment utility's nearby hand-speed peak (which can differ by a few
    # C3D frames).
    vicon_anchor_frame = int(athlete["events"]["release"])
    vicon_rate = float(alignment["vicon_meta"]["rate_hz"])
    capture_fps = float(alignment["alignment"]["video_capture_fps"])
    video_frame_count = int(alignment["video_meta"]["frames_read"])
    outputs: dict[str, Any] = {}

    for event_key in EVENTS:
        vicon_frame = int(athlete["events"][event_key])
        video_frame = int(round(video_event_frame + (vicon_frame - vicon_anchor_frame) / vicon_rate * capture_fps))
        if not 0 <= video_frame < video_frame_count:
            raise RuntimeError(
                f"{event_key} maps outside the video: Vicon frame {vicon_frame} -> video frame {video_frame}"
            )
        output = args.out_dir.resolve() / f"{args.athlete_key}_pitch_{event_key}_2d_overlay.png"
        render_event(
            video=video,
            frame_index=video_frame,
            landmarks=poses.get(video_frame, {}),
            event_key=event_key,
            values=athlete["values"],
            output=output,
        )
        outputs[event_key] = {
            "vicon_frame": vicon_frame,
            "video_frame": video_frame,
            "output": str(output),
            "pose_landmarks_present": bool(poses.get(video_frame)),
        }

    provenance = {
        "athlete_key": args.athlete_key,
        "video": str(video),
        "pitch_summary": str(args.pitch_summary.resolve()),
        "alignment_summary": str(alignment_dir / "alignment_summary.json"),
        "video_playback_fps": alignment["alignment"]["video_playback_fps"],
        "reviewed_video_capture_fps": capture_fps,
        "reviewed_video_event_frame": video_event_frame,
        "vicon_anchor_frame": vicon_anchor_frame,
        "vicon_alignment_peak_frame": int(alignment["vicon_event"]["frame_index"]),
        "anchor_definition": "reviewed 2D release frame = pitch-summary Vicon release event",
        "mapping": "video_frame = video_event_frame + (vicon_frame - vicon_anchor_frame) / vicon_rate * capture_fps",
        "events": outputs,
    }
    provenance_path = args.out_dir.resolve() / "pitch_event_overlay_provenance.json"
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(provenance, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
