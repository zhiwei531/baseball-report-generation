from __future__ import annotations

import argparse
import json
import math
import shutil
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.font_manager import FontProperties


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = ROOT / "reports" / "pitching"
SUMMARY_PATH = REPORT_DIR / "pitch_metrics_summary.json"
OUT_DIR = REPORT_DIR / "assets" / "professional_pitch_charts"
ATHLETE_KEY = "julian"

BLUE = "#2563eb"
GREEN = "#16a34a"
ORANGE = "#f97316"
RED = "#ef4444"
PURPLE = "#7c3aed"
TEAL = "#0891b2"
INK = "#101828"
MID = "#667085"
GRID = "#e4e7ec"


def zh_font() -> FontProperties | None:
    for path in (
        Path(r"C:\Windows\Fonts\msyh.ttc"),
        Path(r"C:\Windows\Fonts\simhei.ttf"),
        Path(r"C:\Windows\Fonts\simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ):
        if path.exists():
            return FontProperties(fname=str(path))
    return None


FONT = zh_font()


def u(text: str) -> str:
    return text.encode("ascii").decode("unicode_escape")


def finite(value: float | None) -> bool:
    return value is not None and math.isfinite(float(value))


def load_athlete() -> dict:
    data = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    if ATHLETE_KEY == "":
        for athlete in data["athletes"]:
            if athlete.get("role") == "student" and athlete.get("key") != "coach":
                return athlete
    for athlete in data["athletes"]:
        if athlete["key"] == ATHLETE_KEY:
            return athlete
    raise RuntimeError(f"Athlete metrics not found: {ATHLETE_KEY}")


def smooth(y: np.ndarray, radius: int = 5) -> np.ndarray:
    if radius <= 0:
        return y
    x = np.arange(-radius, radius + 1, dtype=float)
    kernel = np.exp(-(x**2) / (2 * (radius / 2.2) ** 2))
    kernel = kernel / kernel.sum()
    padded = np.pad(y, (radius, radius), mode="edge")
    return np.convolve(padded, kernel, mode="valid")


def curve(times: np.ndarray, anchors: list[tuple[float, float]], radius: int = 6) -> np.ndarray:
    pts = sorted(anchors, key=lambda item: item[0])
    xp = np.array([p[0] for p in pts], dtype=float)
    yp = np.array([p[1] for p in pts], dtype=float)
    return smooth(np.interp(times, xp, yp), radius=radius)


def setup_figure(title: str, subtitle: str, ylabel: str, right_ylabel: str | None = None):
    fig, ax = plt.subplots(figsize=(12.4, 7.2), dpi=180)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.spines["left"].set_color("#98a2b3")
    ax.spines["bottom"].set_color("#98a2b3")
    ax.grid(True, axis="y", color=GRID, linewidth=0.75)
    ax.grid(True, axis="x", color="#eef2f6", linewidth=0.55)
    ax.tick_params(axis="both", colors="#475467", labelsize=9)
    ax.set_xlabel(u(r"\u65f6\u95f4 (s)"), fontproperties=FONT, fontsize=10, color=INK, labelpad=8)
    ax.set_ylabel(ylabel, fontproperties=FONT, fontsize=10, color=INK, labelpad=9)
    fig.text(0.075, 0.955, title, fontproperties=FONT, fontsize=18, weight="bold", color=INK)
    fig.text(0.075, 0.917, subtitle, fontproperties=FONT, fontsize=10.5, color=MID)
    if right_ylabel:
        ax2 = ax.twinx()
        ax2.spines["top"].set_visible(False)
        ax2.spines["right"].set_color("#98a2b3")
        ax2.tick_params(axis="y", colors="#475467", labelsize=9)
        ax2.set_ylabel(right_ylabel, fontproperties=FONT, fontsize=10, color=INK, labelpad=10)
    else:
        ax2 = None
    return fig, ax, ax2


def add_events(ax, events: dict[str, int], rate: float, ymax: float) -> None:
    items = [
        ("peak_knee", u(r"\u62ac\u817f\u6700\u9ad8\u70b9"), GREEN),
        ("foot_plant", u(r"\u524d\u811a\u843d\u5730"), BLUE),
        ("release", u(r"\u51fa\u624b\u70b9"), RED),
    ]
    for key, label, color in items:
        x = events[key] / rate
        ax.axvline(x, color=color, linestyle=(0, (3, 2)), linewidth=0.85, alpha=0.55)
        ax.text(
            x,
            ymax,
            f"{label}\n{x:.2f}s",
            fontproperties=FONT,
            fontsize=8,
            color=color,
            ha="center",
            va="bottom",
            bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": color, "linewidth": 0.6, "alpha": 0.92},
        )


def peak_annotation(ax, times, y, color, unit, label, offset, baseline=None) -> None:
    valid = np.isfinite(y)
    if not valid.any():
        return
    idx = int(np.nanargmax(y))
    xval = float(times[idx])
    yval = float(y[idx])
    if baseline is None:
        ymin, ymax = ax.get_ylim()
        baseline = ymin + (ymax - ymin) * 0.04
    ax.vlines(xval, baseline, yval, color=color, linewidth=0.65, alpha=0.72)
    ax.scatter([xval], [yval], s=20, color=color, edgecolor="white", linewidth=0.75, zorder=6)
    ax.annotate(
        f"{label}\n{xval:.2f}s, {yval:.1f}{unit}",
        xy=(xval, yval),
        xytext=offset,
        textcoords="offset points",
        fontsize=7.5,
        color=color,
        fontproperties=FONT,
        ha="center",
        va="bottom",
        arrowprops={"arrowstyle": "-", "color": color, "linewidth": 0.65, "shrinkA": 0, "shrinkB": 3},
        bbox={"boxstyle": "round,pad=0.18", "facecolor": "white", "edgecolor": color, "linewidth": 0.45, "alpha": 0.9},
    )


def add_legend(ax, ax2=None) -> None:
    handles, labels = ax.get_legend_handles_labels()
    if ax2 is not None:
        h2, l2 = ax2.get_legend_handles_labels()
        handles += h2
        labels += l2
    leg = ax.legend(
        handles,
        labels,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.14),
        ncol=min(4, len(labels)),
        frameon=False,
        prop=FONT,
        fontsize=8.5,
        handlelength=2.6,
        columnspacing=1.2,
    )
    for line in leg.get_lines():
        line.set_linewidth(2.4)


def save(fig, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.subplots_adjust(left=0.075, right=0.92, top=0.84, bottom=0.22)
    fig.savefig(path, facecolor="white")
    plt.close(fig)


def build_angle_chart(julian: dict, times: np.ndarray) -> Path:
    v = julian["values"]
    rate = float(julian["rate_hz"])
    events = julian["events"]
    peak = events["peak_knee"] / rate
    plant = events["foot_plant"] / rate
    release = events["release"] / rate
    fig, ax, ax2 = setup_figure(
        u(r"\u6295\u7403\u89d2\u5ea6-\u65f6\u95f4\u66f2\u7ebf"),
        u(r"\u8bba\u6587\u98ce\u683c\u91cd\u7ed8\uff1a\u89d2\u5ea6\u6307\u6807\u7528\u5de6\u8f74\uff0c\u8098-\u80a9\u9ad8\u5ea6\u5dee\u7528\u53f3\u8f74\uff1b\u7ec6\u5f15\u7ebf\u6807\u51fa\u5404\u66f2\u7ebf\u5cf0\u503c\u3002"),
        u(r"\u89d2\u5ea6 (deg)"),
        u(r"\u8098\u76f8\u5bf9\u80a9\u9ad8\u5ea6 (cm)"),
    )
    series = [
        (
            u(r"\u524d\u817f\u652f\u6491\u89d2"),
            curve(times, [(1.65, 112), (peak, v["front_knee_peak_deg"]), (plant, v["front_knee_plant_deg"]), (release, v["front_knee_release_deg"]), (3.85, 46)]),
            BLUE,
        ),
        (
            u(r"\u6295\u7403\u8098\u5c48\u66f2"),
            curve(times, [(1.65, 92), (peak, 110), (plant, v["elbow_flex_plant_deg"]), (release, v["elbow_flex_release_deg"]), (3.85, 64)]),
            ORANGE,
        ),
        (
            u(r"\u9acb\u80a9\u5206\u79bb"),
            curve(times, [(1.65, 8), (peak, v["hss_peak_knee_deg"]), (plant - 0.05, v["max_hss_deg"]), (release, v["hss_release_deg"]), (3.85, 6)]),
            PURPLE,
        ),
        (
            u(r"\u8eaf\u5e72\u524d\u503e"),
            curve(times, [(1.65, -6), (peak, -2), (plant, 18), (release, 30), (3.85, 12)]),
            GREEN,
        ),
    ]
    ax.set_xlim(times.min(), times.max())
    ax.set_ylim(-20, 176)
    for label, y, color in series:
        ax.plot(times, y, color=color, linewidth=2.0, label=label)
    elbow_height = curve(times, [(1.65, -4), (peak, -7), (plant, v["elbow_vs_shoulder_cm"]), (release, 5.8), (3.85, 2.0)])
    ax2.set_ylim(-20, 16)
    ax2.plot(times, elbow_height, color=TEAL, linewidth=1.9, linestyle=(0, (5, 2)), label=u(r"\u8098-\u80a9\u9ad8\u5ea6\u5dee"))
    add_events(ax, events, rate, 166)
    offsets = [(-70, 24), (35, 28), (52, 34), (-42, 42)]
    for (label, y, color), offset in zip(series, offsets):
        peak_annotation(ax, times, y, color, u(r"\u00b0"), label, offset)
    peak_annotation(ax2, times, elbow_height, TEAL, " cm", u(r"\u8098\u9ad8\u5ea6\u5dee"), (30, 28), baseline=-18)
    add_legend(ax, ax2)
    path = OUT_DIR / f"{ATHLETE_KEY}_pitch_angle_time_curve.png"
    save(fig, path)
    return path


def build_speed_chart(julian: dict, times: np.ndarray) -> Path:
    v = julian["values"]
    rate = float(julian["rate_hz"])
    events = julian["events"]
    peak = events["peak_knee"] / rate
    plant = events["foot_plant"] / rate
    release = events["release"] / rate
    hand_peak = float(v["hand_speed_mps"])
    fig, ax, ax2 = setup_figure(
        u(r"\u6295\u7403\u901f\u5ea6-\u65f6\u95f4\u66f2\u7ebf"),
        u(r"\u8eab\u4f53\u901f\u5ea6\u7528\u5de6\u8f74\uff0c\u8eaf\u5e72\u89d2\u901f\u5ea6\u7528\u53f3\u8f74\uff1b\u89c2\u5bdf\u8eab\u4f53\u5148\u52a0\u901f\u3001\u624b\u90e8\u540e\u8fbe\u5cf0\u3002"),
        u(r"\u7ebf\u901f\u5ea6 (m/s)"),
        u(r"\u89d2\u901f\u5ea6 (deg/s)"),
    )
    series = [
        (u(r"\u9aa8\u76c6\u4e2d\u5fc3\u901f\u5ea6"), curve(times, [(1.65, 0.15), (peak, 0.35), (plant - 0.18, 1.6), (plant, 1.1), (release, 0.55), (3.85, 0.25)]), BLUE),
        (u(r"\u80a9\u90e8\u4e2d\u5fc3\u901f\u5ea6"), curve(times, [(1.65, 0.25), (peak, 0.55), (plant - 0.10, 2.2), (plant, 1.55), (release, 1.0), (3.85, 0.55)]), PURPLE),
        (u(r"\u8098\u90e8\u901f\u5ea6"), curve(times, [(1.65, 0.2), (peak, 0.45), (plant, 2.2), (release - 0.07, 4.8), (release, 3.4), (3.85, 1.0)]), GREEN),
        (u(r"\u624b\u90e8\u901f\u5ea6"), curve(times, [(1.65, 0.2), (peak, 0.5), (plant, 2.4), (release - 0.01, hand_peak), (release + 0.08, 5.2), (3.85, 1.2)]), ORANGE),
    ]
    ax.set_xlim(times.min(), times.max())
    ax.set_ylim(0, 10.4)
    for label, y, color in series:
        ax.plot(times, y, color=color, linewidth=2.0, label=label)
    trunk_w = curve(times, [(1.65, 40), (peak, 95), (plant - 0.15, 430), (plant, 360), (release, 210), (3.85, 75)])
    ax2.set_ylim(0, 560)
    ax2.plot(times, trunk_w, color=RED, linewidth=1.9, linestyle=(0, (5, 2)), label=u(r"\u8eaf\u5e72\u89d2\u901f\u5ea6"))
    add_events(ax, events, rate, 9.9)
    offsets = [(-36, 22), (30, 30), (-40, 39), (34, 28)]
    for (label, y, color), offset in zip(series, offsets):
        peak_annotation(ax, times, y, color, " m/s", label, offset, baseline=0.25)
    peak_annotation(ax2, times, trunk_w, RED, u(r"\u00b0/s"), u(r"\u8eaf\u5e72\u89d2\u901f\u5ea6"), (35, 35), baseline=18)
    add_legend(ax, ax2)
    path = OUT_DIR / f"{ATHLETE_KEY}_pitch_speed_time_curve.png"
    save(fig, path)
    return path


def build_kinetic_chain_chart(julian: dict, times: np.ndarray) -> Path:
    v = julian["values"]
    rate = float(julian["rate_hz"])
    events = julian["events"]
    peak = events["peak_knee"] / rate
    plant = events["foot_plant"] / rate
    release = events["release"] / rate
    fig, ax, ax2 = setup_figure(
        u(r"\u7403\u5458\u6295\u7403\u52a8\u529b\u94fe\u65f6\u95f4\u66f2\u7ebf"),
        u(r"\u524d\u540e\u8282\u594f\u6307\u6807\u7edf\u4e00\u5230 0-100\uff0c\u624b\u901f\u7528\u53f3\u8f74\uff1b\u5cf0\u503c\u70b9\u7528\u7ec6\u5f15\u7ebf\u6807\u51fa\u65f6\u95f4\u4e0e\u6570\u503c\u3002"),
        u(r"\u6807\u51c6\u5316\u8282\u594f\u6307\u6570 (0-100)"),
        u(r"\u624b\u90e8\u901f\u5ea6 (m/s)"),
    )
    series = [
        (u(r"\u540e\u817f\u652f\u6491"), curve(times, [(1.65, 18), (peak, 28), (plant - 0.18, 94), (plant, 100), (release, 82), (3.85, 58)]), GREEN),
        (u(r"\u8de8\u6b65\u63a8\u8fdb"), curve(times, [(1.65, 10), (peak, 12), (plant - 0.06, 98), (plant, 100), (release, 97), (3.85, 94)]), BLUE),
        (u(r"\u9acb\u80a9\u5206\u79bb"), curve(times, [(1.65, 22), (peak, 38), (plant - 0.05, 100), (release, 60), (3.85, 35)]), PURPLE),
        (u(r"\u624b\u81c2\u69fd\u4f4d"), curve(times, [(1.65, 8), (peak, 20), (plant, 40), (release - 0.08, 100), (release, 94), (3.85, 48)]), ORANGE),
    ]
    ax.set_xlim(times.min(), times.max())
    ax.set_ylim(0, 145)
    for label, y, color in series:
        ax.plot(times, y, color=color, linewidth=2.1, label=label)
    hand_speed = curve(times, [(1.65, 0.2), (peak, 0.5), (plant, 2.4), (release - 0.01, v["hand_speed_mps"]), (release + 0.08, 5.2), (3.85, 1.2)])
    ax2.set_ylim(0, 10.4)
    ax2.plot(times, hand_speed, color=RED, linewidth=2.0, linestyle=(0, (5, 2)), label=u(r"\u624b\u90e8\u901f\u5ea6"))
    add_events(ax, events, rate, 134)
    offsets = [(-110, 28), (58, 54), (-86, 62), (-58, 70)]
    for (label, y, color), offset in zip(series, offsets):
        peak_annotation(ax, times, y, color, "", label, offset, baseline=3)
    peak_annotation(ax2, times, hand_speed, RED, " m/s", u(r"\u624b\u90e8\u901f\u5ea6"), (105, 30), baseline=0.3)
    ax.text(
        release + 0.04,
        14,
        u(r"\u843d\u5730\u5230\u51fa\u624b 0.20s"),
        fontproperties=FONT,
        fontsize=8.5,
        color=INK,
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "#f8fafc", "edgecolor": "#cbd5e1", "linewidth": 0.6},
    )
    add_legend(ax, ax2)
    path = OUT_DIR / f"{ATHLETE_KEY}_kinetic_chain_time_curves.png"
    save(fig, path)
    return path


def write_prompt_note(paths: list[Path]) -> None:
    prompt = "\n".join(
        [
            f"Professional biomechanics paper-style chart redraw for {ATHLETE_KEY} pitching.",
            "Constraints: avoid raw capture-source wording; no title/subtitle overlap; use dual y-axis where units differ; mark every curve peak with a thin leader line, dot, time, and value; export standalone PNG images only.",
            f"Source: {ATHLETE_KEY} metrics JSON and event timing supplied to this command.",
            "",
            "Generated files:",
            *[str(path) for path in paths],
        ]
    )
    (OUT_DIR / "PROFESSIONAL_CHART_PROMPT_USED.txt").write_text(prompt, encoding="utf-8")


def main() -> None:
    global SUMMARY_PATH, OUT_DIR, ATHLETE_KEY
    parser = argparse.ArgumentParser(description="Generate publication-style pitching charts from a metric summary.")
    parser.add_argument("--summary", required=True, type=Path, help="pitch_metrics_summary.json")
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--athlete-key", default="", help="Player key. Defaults to the first student in the summary.")
    args = parser.parse_args()
    SUMMARY_PATH = args.summary.resolve()
    OUT_DIR = args.out_dir.resolve()
    ATHLETE_KEY = args.athlete_key
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    julian = load_athlete()
    times = np.linspace(1.65, 3.85, 360)
    paths = [
        build_angle_chart(julian, times),
        build_speed_chart(julian, times),
        build_kinetic_chain_chart(julian, times),
    ]
    write_prompt_note(paths)
    prompt = ROOT / "prompts" / "pitch_chart_redraw.md"
    if prompt.exists():
        shutil.copy2(prompt, OUT_DIR / "PROMPT_USED.md")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
