from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

from build_vicon_2026_metrics import trial_id
from render_vicon_reconstruction_images import read_c3d, render_trial_gif


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METRICS = ROOT / "reports" / "vicon_2026_julian_coach" / "batting_dashboard_metrics.csv"
DEFAULT_OUT_DIR = ROOT / "reports" / "vicon_2026_julian_coach" / "assets" / "vicon_reconstruction_events"


EVENT_SPECS = {
    "ready_com_height_ratio": ("ready", "Ready Position"),
    "contact_bat_speed_kmh": ("contact", "Contact Position"),
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def fake_row(metric: dict[str, str], frame_index: int, event_name: str) -> dict[str, str]:
    return {
        "trial_id": metric["trial_id"],
        "sample_name": metric["sample_name"],
        "athlete": metric["athlete"],
        "action_type": metric["action_type"],
        "key_event": event_name,
        "key_rule": metric.get("event_rule", ""),
        "key_frame_index": str(frame_index),
        "key_time_sec": "",
    }


def center_frame(metric: dict[str, str]) -> int:
    frames = [int(item) for item in metric.get("event_frames", "").split(";") if item.strip()]
    if frames:
        return frames[len(frames) // 2]
    return int(metric.get("event_frame") or 0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render Ready/Contact short GIFs for Julian-vs-Coach metric section.")
    parser.add_argument("--metrics", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--samples", nargs="+", default=["julian", "coach"])
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows = read_csv(args.metrics)
    sample_names = set(args.samples)
    selected = [row for row in rows if row.get("metric_key") in EVENT_SPECS and row.get("sample_name") in sample_names]
    for metric in selected:
        event_slug, event_name = EVENT_SPECS[metric["metric_key"]]
        c3d_path = ROOT.parent / metric["source_file"]
        trial = read_c3d(c3d_path)
        frame = center_frame(metric)
        temp_dir = args.out_dir / f"_tmp_{metric['sample_name']}_{event_slug}"
        temp_dir.mkdir(parents=True, exist_ok=True)
        render_trial_gif(
            trial,
            [fake_row(metric, frame, event_name)],
            temp_dir,
            max_frames=9,
            frame_duration_ms=140,
            smooth_radius=1,
            before_sec=0.04,
            after_sec=0.04,
            pitch_before_sec=0.04,
        )
        source = temp_dir / f"{trial_id(c3d_path)}.gif"
        if not source.exists():
            continue
        out_path = args.out_dir / f"{metric['sample_name']}_{event_slug}.gif"
        shutil.copyfile(source, out_path)
        print(out_path)


if __name__ == "__main__":
    main()
