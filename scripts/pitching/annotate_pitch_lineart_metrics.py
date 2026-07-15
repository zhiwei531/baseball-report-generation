from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[2]
ASSET_DIR = ROOT / "reports" / "pitching" / "assets" / "lineart_actions"
VALUES: dict[str, float] = {}

BLUE = "#1473e6"
ORANGE = "#f97316"
PURPLE = "#7c3aed"
GREEN = "#3f7d20"
GRAY = "#9aa4b2"
INK = "#101828"
PANEL = "#ffffff"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        Path(r"C:\Windows\Fonts\msyhbd.ttc") if bold else Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc") if bold else Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf") if bold else Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


FONT = font(30)
FONT_SMALL = font(24)
FONT_BOLD = font(32, bold=True)


def value(key: str, suffix: str = "", digits: int = 2) -> str:
    number = VALUES.get(key)
    if number is None or not math.isfinite(float(number)):
        return "N/A"
    return f"{float(number):.{digits}f}{suffix}"


def text_box(draw: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, color: str = INK) -> None:
    x, y = xy
    lines = text.split("\n")
    widths = []
    heights = []
    for line in lines:
        box = draw.textbbox((0, 0), line, font=FONT_SMALL)
        widths.append(box[2] - box[0])
        heights.append(box[3] - box[1])
    pad_x, pad_y = 18, 12
    w = max(widths) + pad_x * 2
    h = sum(heights) + (len(lines) - 1) * 8 + pad_y * 2
    draw.rounded_rectangle((x, y, x + w, y + h), radius=18, fill=PANEL, outline=color, width=3)
    yy = y + pad_y
    for line, lh in zip(lines, heights):
        draw.text((x + pad_x, yy), line, font=FONT_SMALL, fill=color)
        yy += lh + 8


def arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], color: str, width: int = 6) -> None:
    draw.line((start, end), fill=color, width=width)
    sx, sy = start
    ex, ey = end
    angle = math.atan2(ey - sy, ex - sx)
    head_len = 22
    head_ang = math.radians(28)
    for sign in (-1, 1):
        hx = ex - head_len * math.cos(angle + sign * head_ang)
        hy = ey - head_len * math.sin(angle + sign * head_ang)
        draw.line((ex, ey, hx, hy), fill=color, width=width)


def double_arrow(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], color: str, width: int = 6) -> None:
    arrow(draw, a, b, color, width)
    arrow(draw, b, a, color, width)


def dot(draw: ImageDraw.ImageDraw, center: tuple[int, int], color: str, r: int = 10) -> None:
    x, y = center
    draw.ellipse((x - r, y - r, x + r, y + r), fill=color, outline="white", width=3)


def arc(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], start: int, end: int, color: str, width: int = 7) -> None:
    draw.arc(box, start=start, end=end, fill=color, width=width)


def dashed(draw: ImageDraw.ImageDraw, a: tuple[int, int], b: tuple[int, int], color: str, width: int = 4, dash: int = 18) -> None:
    x1, y1 = a
    x2, y2 = b
    length = math.hypot(x2 - x1, y2 - y1)
    if length == 0:
        return
    steps = int(length // dash)
    for i in range(0, steps, 2):
        t1 = i / steps
        t2 = min((i + 1) / steps, 1)
        draw.line((x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1, x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2), fill=color, width=width)


def annotate_peak_knee() -> None:
    img = Image.open(ASSET_DIR / "pitch_peak_knee_lineart.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    # Knee-height measurement.
    ground_y = int(h * 0.855)
    knee = (int(w * 0.67), int(h * 0.50))
    draw.line((int(w * 0.15), ground_y, int(w * 0.86), ground_y), fill=GREEN, width=5)
    dashed(draw, (knee[0] + 35, knee[1]), (knee[0] + 145, knee[1]), BLUE, 4)
    double_arrow(draw, (knee[0] + 105, knee[1]), (knee[0] + 105, ground_y), BLUE, 6)
    dot(draw, knee, BLUE)
    text_box(draw, (int(w * 0.64), int(h * 0.26)), f"抬腿高度\n{value('knee_height_pct', '%')} 身高", BLUE)

    # Front-knee tuck angle.
    arc(draw, (int(w * 0.50), int(h * 0.43), int(w * 0.69), int(h * 0.62)), 300, 45, ORANGE, 8)
    text_box(draw, (int(w * 0.10), int(h * 0.22)), f"前膝角\n{value('front_knee_peak_deg', '°')}", ORANGE)

    # Back-leg load cue.
    arrow(draw, (int(w * 0.40), int(h * 0.80)), (int(w * 0.47), int(h * 0.68)), GREEN, 5)
    text_box(draw, (int(w * 0.08), int(h * 0.70)), f"后腿蓄力\n后膝角 {value('rear_knee_peak_deg', '°')}", GREEN)
    img.save(ASSET_DIR / "pitch_peak_knee_lineart_metrics.png")


def annotate_foot_plant() -> None:
    img = Image.open(ASSET_DIR / "pitch_foot_plant_lineart.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    ground_y = int(h * 0.80)
    rear_foot = (int(w * 0.27), int(h * 0.78))
    front_foot = (int(w * 0.73), int(h * 0.77))
    draw.line((int(w * 0.12), ground_y, int(w * 0.88), ground_y), fill=GREEN, width=5)
    double_arrow(draw, rear_foot, front_foot, BLUE, 6)
    text_box(draw, (int(w * 0.40), int(h * 0.82)), f"跨步距离\n{value('stride_distance_pct', '%')} 身高", BLUE)

    # Stride direction.
    direction_start = (int(w * 0.46), int(h * 0.86))
    direction_end = (int(w * 0.69), int(h * 0.90))
    arrow(draw, direction_start, direction_end, ORANGE, 5)
    dashed(draw, direction_start, (direction_start[0] + 210, direction_start[1]), GRAY, 3)
    text_box(draw, (int(w * 0.16), int(h * 0.84)), f"跨步方向\n{value('stride_direction_deg', '°')}", ORANGE)

    # Front-knee support.
    knee = (int(w * 0.64), int(h * 0.62))
    arc(draw, (knee[0] - 75, knee[1] - 70, knee[0] + 75, knee[1] + 75), 205, 312, ORANGE, 8)
    dot(draw, knee, ORANGE)
    text_box(draw, (int(w * 0.67), int(h * 0.53)), f"前膝角\n{value('front_knee_plant_deg', '°')}", ORANGE)

    rear_knee = (int(w * 0.31), int(h * 0.66))
    arc(draw, (rear_knee[0] - 70, rear_knee[1] - 70, rear_knee[0] + 75, rear_knee[1] + 75), 25, 138, GREEN, 8)
    dot(draw, rear_knee, GREEN)
    text_box(draw, (int(w * 0.05), int(h * 0.56)), f"后膝屈曲\n{value('rear_knee_plant_deg', '°')}", GREEN)

    # Shoulder line and elbow height.
    shoulder_l = (int(w * 0.42), int(h * 0.39))
    shoulder_r = (int(w * 0.63), int(h * 0.37))
    elbow = (int(w * 0.34), int(h * 0.48))
    draw.line((shoulder_l, shoulder_r), fill=PURPLE, width=6)
    dashed(draw, (elbow[0] - 15, shoulder_l[1]), (elbow[0] - 15, elbow[1]), BLUE, 4)
    double_arrow(draw, (elbow[0] - 42, shoulder_l[1]), (elbow[0] - 42, elbow[1]), BLUE, 5)
    dot(draw, elbow, BLUE)
    text_box(draw, (int(w * 0.09), int(h * 0.25)), f"投球肘相对肩线\n{value('elbow_vs_shoulder_cm', ' cm')}", BLUE)
    text_box(draw, (int(w * 0.62), int(h * 0.20)), f"肩线 / 手臂到位\n肩外展 {value('shoulder_abduction_plant_deg', '°')}", PURPLE)
    img.save(ASSET_DIR / "pitch_foot_plant_lineart_metrics.png")


def annotate_release() -> None:
    img = Image.open(ASSET_DIR / "pitch_release_lineart.png").convert("RGBA")
    draw = ImageDraw.Draw(img)
    w, h = img.size

    ground_y = int(h * 0.84)
    release = (int(w * 0.77), int(h * 0.16))
    shoulder = (int(w * 0.57), int(h * 0.43))
    knee = (int(w * 0.58), int(h * 0.61))

    draw.line((int(w * 0.12), ground_y, int(w * 0.88), ground_y), fill=GREEN, width=5)

    # Release height.
    dashed(draw, (release[0] - 36, release[1]), (release[0] + 58, release[1]), BLUE, 4)
    double_arrow(draw, (release[0] + 48, release[1]), (release[0] + 48, ground_y), BLUE, 6)
    dot(draw, release, BLUE)
    text_box(draw, (int(w * 0.69), int(h * 0.36)), f"出手高度\n{value('release_height_pct', '%')} 身高", BLUE)

    # Arm slot.
    draw.line((shoulder, release), fill=PURPLE, width=6)
    arc(draw, (shoulder[0] - 110, shoulder[1] - 110, shoulder[0] + 110, shoulder[1] + 110), 300, 350, PURPLE, 8)
    text_box(draw, (int(w * 0.34), int(h * 0.20)), f"出手手臂角度\n肩外展 {value('shoulder_abduction_release_deg', '°')}\n肘屈曲 {value('elbow_flex_release_deg', '°')}\n手臂角度 {value('arm_slot_deg', '°')}", PURPLE)

    # Ball path / hand speed.
    for offset, width_line in ((0, 7), (24, 4), (44, 3)):
        draw.arc((int(w * 0.63), int(h * 0.05) + offset, int(w * 0.91), int(h * 0.36) + offset), 205, 296, fill=BLUE, width=width_line)
    text_box(draw, (int(w * 0.68), int(h * 0.05)), f"出手点\n出手高度 {value('release_height_pct', '%')} 身高\n出手手速 {value('hand_speed_kmh', ' km/h', 1)}", BLUE)

    # Whole-body transfer, drawn on the release frame because it summarizes the action.
    hip = (int(w * 0.48), int(h * 0.56))
    chest = (int(w * 0.54), int(h * 0.40))
    draw.line((hip[0] - 65, hip[1] + 25, hip[0] + 65, hip[1] - 5), fill=GREEN, width=6)
    draw.line((chest[0] - 55, chest[1] + 22, chest[0] + 65, chest[1] - 18), fill=PURPLE, width=6)
    text_box(draw, (int(w * 0.05), int(h * 0.34)), f"身体带动程度\n最大髋肩分离 {value('max_hss_deg', '°')}\n释放量 {value('hss_release_amount_deg', '°')}", GREEN)

    # Front-leg block.
    arc(draw, (knee[0] - 80, knee[1] - 70, knee[0] + 70, knee[1] + 90), 210, 318, ORANGE, 8)
    dot(draw, knee, ORANGE)
    text_box(draw, (int(w * 0.16), int(h * 0.56)), f"前腿制动\n前膝角 {value('front_knee_release_deg', '°')}", ORANGE)
    img.save(ASSET_DIR / "pitch_release_lineart_metrics.png")


def main() -> None:
    global ASSET_DIR, VALUES
    parser = argparse.ArgumentParser(description="Annotate three pitching line-art images with computed metric values.")
    parser.add_argument("--summary", required=True, type=Path, help="pitch_metrics_summary.json")
    parser.add_argument("--asset-dir", required=True, type=Path, help="Directory containing the three base line-art PNG files.")
    parser.add_argument("--athlete-key", default="julian")
    args = parser.parse_args()
    ASSET_DIR = args.asset_dir.resolve()
    data = json.loads(args.summary.read_text(encoding="utf-8"))
    athlete = next((item for item in data.get("athletes", []) if item.get("key") == args.athlete_key), None)
    if athlete is None:
        raise ValueError(f"Athlete key not found in summary: {args.athlete_key}")
    VALUES = {key: float(number) for key, number in athlete.get("values", {}).items() if number is not None}
    annotate_peak_knee()
    annotate_foot_plant()
    annotate_release()
    print("Annotated line-art metric images written to", ASSET_DIR)


if __name__ == "__main__":
    main()
