from __future__ import annotations

import argparse
import csv
import json
import math
import re
import shutil
from datetime import date
from pathlib import Path
from typing import Any

import benchmark_slymask_metrics as motion
from renderers import build_report as report_renderer


ROOT = Path(__file__).resolve().parent
EXAMPLE_INPUT = ROOT / "examples" / "sample_raw_input.json"
DEFAULT_OUT = ROOT / "outputs" / "end_to_end_reports"


def slugify(text: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", text).strip("_")
    return slug or "video"


def infer_kind(path: Path, requested: str) -> str:
    if requested != "auto":
        return requested
    name = path.stem.lower()
    if any(token in name for token in ("pitch", "throw", "投球")):
        return "pitch"
    return "hit"


def number_or_none(value: Any) -> float | None:
    if value in ("", None):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value


def rounded(value: float | None, digits: int = 3) -> float | None:
    if value is None:
        return None
    return round(value, digits)


def row_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["key"]: row for row in rows}


def row_value(rows_by_key: dict[str, dict[str, Any]], key: str) -> float | None:
    row = rows_by_key.get(key)
    if not row:
        return None
    return number_or_none(row.get("value"))


def seconds(frame: int | None, fps: float | None) -> float | None:
    if frame is None or not fps:
        return None
    return round(frame / fps, 3)


def placeholder_hit() -> dict[str, Any]:
    return {
        "action": "bat",
        "start_s": 0,
        "event_s": None,
        "end_s": 0,
        "hip_shoulder_separation_deg": None,
        "front_knee_angle_deg": None,
        "torso_tilt_deg": None,
        "com_transfer": None,
        "head_stability_pct": None,
        "swing_speed_norm_s": None,
        "estimated_bat_speed_px_s": None,
        "hip_rotation_deg": None,
        "attack_angle_deg": None,
        "wrist_speed_3d_units_s": None,
        "contact_time_s": None,
    }


def placeholder_pitch() -> dict[str, Any]:
    return {
        "action": "pitch",
        "event_s": None,
        "release_timing_pct": None,
        "front_foot_landing_pct": None,
        "hip_shoulder_separation_deg": None,
        "front_knee_angle_deg": None,
        "torso_tilt_deg": None,
        "head_stability_pct": None,
        "elbow_flexion_deg": None,
        "arm_abduction_deg": None,
        "stride_angle_deg": None,
        "stride_length_body_ratio": None,
        "foot_direction_deg": None,
        "wrist_release_deg": None,
        "arm_speed_3d_units_s": None,
        "fingertip_speed_3d_units_s": None,
        "ball_speed_px_s": None,
        "lower_body_start_score": None,
        "target_line_control_score": None,
        "hip_shoulder_separation_score": None,
        "arm_path_score": None,
        "release_quality_score": None,
        "finish_stability_score": None,
    }


def hit_metrics(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    by_key = row_lookup(rows)
    fps = summary.get("fps")
    events = summary.get("events", {})
    start = events.get("start")
    event = events.get("contact_or_peak")
    finish = events.get("finish")
    return {
        "action": "bat",
        "start_s": seconds(start, fps) or 0,
        "event_s": seconds(event, fps),
        "end_s": seconds(finish, fps) or seconds(event, fps) or 0,
        "hip_shoulder_separation_deg": rounded(row_value(by_key, "hip_shoulder_separation")),
        "front_knee_angle_deg": rounded(row_value(by_key, "front_knee_angle")),
        "torso_tilt_deg": rounded(row_value(by_key, "torso_tilt")),
        "com_transfer": rounded(row_value(by_key, "center_of_mass_shift")),
        "head_stability_pct": rounded(row_value(by_key, "head_stability")),
        "swing_speed_norm_s": rounded(row_value(by_key, "swing_speed")),
        "estimated_bat_speed_px_s": rounded(row_value(by_key, "estimated_bat_head_speed")),
        "hip_rotation_deg": rounded(row_value(by_key, "hip_rotation")),
        "attack_angle_deg": rounded(row_value(by_key, "attack_angle")),
        "wrist_speed_3d_units_s": rounded(row_value(by_key, "wrist_roll")),
        "contact_time_s": rounded((row_value(by_key, "contact_timing") or 0) / 1000, 3)
        if row_value(by_key, "contact_timing") is not None
        else None,
    }


def pitch_metrics(rows: list[dict[str, Any]], summary: dict[str, Any]) -> dict[str, Any]:
    by_key = row_lookup(rows)
    fps = summary.get("fps")
    release = summary.get("events", {}).get("release")
    return {
        "action": "pitch",
        "event_s": seconds(release, fps),
        "release_timing_pct": rounded(row_value(by_key, "release_timing")),
        "front_foot_landing_pct": rounded(row_value(by_key, "front_foot_landing")),
        "hip_shoulder_separation_deg": rounded(row_value(by_key, "hip_shoulder_separation")),
        "front_knee_angle_deg": rounded(row_value(by_key, "front_knee_bend")),
        "torso_tilt_deg": rounded(row_value(by_key, "torso_forward_lean")),
        "head_stability_pct": rounded(row_value(by_key, "head_stability")),
        "elbow_flexion_deg": rounded(row_value(by_key, "elbow_flexion")),
        "arm_abduction_deg": rounded(row_value(by_key, "arm_abduction")),
        "stride_angle_deg": rounded(row_value(by_key, "stride_angle")),
        "stride_length_body_ratio": rounded(row_value(by_key, "stride_ratio")),
        "foot_direction_deg": rounded(row_value(by_key, "front_foot_direction")),
        "wrist_release_deg": rounded(row_value(by_key, "wrist_snap")),
        "arm_speed_3d_units_s": rounded(row_value(by_key, "release_speed")),
        "fingertip_speed_3d_units_s": rounded(row_value(by_key, "fingertip_speed")),
        "ball_speed_px_s": None,
        "lower_body_start_score": rounded(row_value(by_key, "lower_body_start")),
        "target_line_control_score": rounded(row_value(by_key, "target_line_control")),
        "hip_shoulder_separation_score": rounded(row_value(by_key, "hip_shoulder_separation_score")),
        "arm_path_score": rounded(row_value(by_key, "arm_path")),
        "release_quality_score": rounded(row_value(by_key, "release_quality")),
        "finish_stability_score": rounded(row_value(by_key, "finish_stability")),
    }


def load_default_vicon() -> dict[str, Any]:
    sample = json.loads(EXAMPLE_INPUT.read_text(encoding="utf-8"))
    return sample["vicon_metrics"]


def build_raw_report_input(
    *,
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    sample_id: str,
    kind: str,
    athlete_name: str,
    age_group: str,
) -> dict[str, Any]:
    cv_metrics: dict[str, dict[str, Any]] = {}
    actions: list[str] = []
    session: dict[str, Any] = {
        "session_id": f"end-to-end-{sample_id}",
        "capture_note": "由一键脚本从输入视频自动生成",
        "actions": actions,
    }

    if kind == "hit":
        cv_metrics[sample_id] = hit_metrics(rows, summary)
        pitch_id = f"{sample_id}_pitch_unavailable"
        cv_metrics[pitch_id] = placeholder_pitch()
        session["primary_bat_sample"] = sample_id
        session["primary_pitch_sample"] = pitch_id
        actions.append("bat")
    else:
        hit_id = f"{sample_id}_hit_unavailable"
        cv_metrics[hit_id] = placeholder_hit()
        cv_metrics[sample_id] = pitch_metrics(rows, summary)
        session["primary_bat_sample"] = hit_id
        session["primary_pitch_sample"] = sample_id
        actions.append("pitch")

    return {
        "metadata": {
            "report_id": f"srs-end-to-end-{sample_id}",
            "schema_version": "0.1.0",
            "created_at": date.today().isoformat(),
            "language": "zh-CN",
        },
        "athlete": {
            "name": athlete_name,
            "age_group": age_group,
            "dominant_side": summary.get("side_assumption", "right"),
        },
        "session": session,
        "cv_metrics": cv_metrics,
        "vicon_metrics": load_default_vicon(),
    }


def copy_report_assets(summary: dict[str, Any], report_dir: Path) -> dict[str, str]:
    assets_dir = report_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for key, filename_base in (
        ("stable_pose_video", "stable_pose"),
        ("quality_pose_video", "stable_pose_quality"),
        ("raw_vs_stable_video", "raw_vs_stable"),
        ("event_contact_sheet", "event_contact_sheet.jpg"),
        ("pose3d_video", "pose3d_relative_skeleton"),
        ("pose3d_animation", "pose3d_animation.gif"),
        ("pose3d_contact_sheet", "pose3d_event_contact_sheet.jpg"),
        ("pose3d_csv", "pose3d_relative_landmarks.csv"),
        ("motion_trend_chart", "motion_trend_charts.jpg"),
    ):
        src_text = summary.get(key)
        if not src_text:
            continue
        src = Path(src_text)
        if not src.exists():
            continue
        filename = filename_base if "." in filename_base else f"{filename_base}{src.suffix}"
        dst = assets_dir / filename
        shutil.copy2(src, dst)
        copied[key] = f"assets/{filename}"
    return copied


def smooth_pose3d_preview_frames(frames: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if len(frames) < 3:
        return frames

    joint_ids = sorted({joint.get("i") for frame in frames for joint in frame.get("joints", []) if joint.get("i") is not None})
    joint_names = {
        joint.get("i"): joint.get("n", "")
        for frame in frames
        for joint in frame.get("joints", [])
        if joint.get("i") is not None
    }
    fast_names = ("wrist", "elbow", "index", "pinky", "thumb")
    core_names = ("shoulder", "hip", "nose")

    def max_step(name: str) -> float:
        lower = name.lower()
        if any(token in lower for token in fast_names):
            return 0.18
        if any(token in lower for token in core_names):
            return 0.075
        return 0.12

    maps = [{joint.get("i"): dict(joint) for joint in frame.get("joints", []) if joint.get("i") is not None} for frame in frames]

    for joint_id in joint_ids:
        name = str(joint_names.get(joint_id, ""))
        series: list[dict[str, Any] | None] = [frame_map.get(joint_id) for frame_map in maps]
        for idx in range(1, len(series)):
            prev = series[idx - 1]
            cur = series[idx]
            if not prev or not cur:
                continue
            dx = float(cur.get("x") or 0) - float(prev.get("x") or 0)
            dy = float(cur.get("y") or 0) - float(prev.get("y") or 0)
            dz = float(cur.get("z") or 0) - float(prev.get("z") or 0)
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            limit = max_step(name)
            if dist > limit and dist > 1e-9:
                ratio = limit / dist
                cur["x"] = round(float(prev.get("x") or 0) + dx * ratio, 4)
                cur["y"] = round(float(prev.get("y") or 0) + dy * ratio, 4)
                cur["z"] = round(float(prev.get("z") or 0) + dz * ratio, 4)

        original = [dict(item) if item else None for item in series]
        for idx, cur in enumerate(series):
            if not cur:
                continue
            neighbors = [original[j] for j in (idx - 1, idx, idx + 1) if 0 <= j < len(original) and original[j]]
            if not neighbors:
                continue
            weights = [0.22, 0.56, 0.22] if len(neighbors) == 3 else [1 / len(neighbors)] * len(neighbors)
            for axis in ("x", "y", "z"):
                cur[axis] = round(sum(float(item.get(axis) or 0) * weight for item, weight in zip(neighbors, weights)), 4)

    smoothed = []
    for frame_idx, frame in enumerate(frames):
        frame_map = maps[frame_idx]
        smoothed.append(
            {
                **frame,
                "joints": [frame_map.get(joint.get("i"), joint) for joint in frame.get("joints", [])],
            }
        )
    return smoothed


def build_pose3d_preview(summary: dict[str, Any], max_frames: int = 120) -> dict[str, Any]:
    csv_text = summary.get("pose3d_csv")
    if not csv_text:
        return {}
    csv_path = Path(csv_text)
    if not csv_path.exists():
        return {}

    frames: dict[int, list[dict[str, Any]]] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                frame_idx = int(row["frame_index"])
                joint_idx = len(frames.setdefault(frame_idx, []))
                frames[frame_idx].append(
                    {
                        "i": joint_idx,
                        "n": row["joint_name"],
                        "x": rounded(number_or_none(row["x_3d"]), 4),
                        "y": rounded(number_or_none(row["y_3d"]), 4),
                        "z": rounded(number_or_none(row["z_3d"]), 4),
                        "c": rounded(number_or_none(row["confidence"]), 3),
                    }
                )
            except (KeyError, ValueError):
                continue

    if not frames:
        return {}

    frame_ids = sorted(frames)
    step = max(1, len(frame_ids) // max_frames)
    sampled_ids = frame_ids[::step][:max_frames]
    fps = float(summary.get("fps") or 30.0)
    events = summary.get("events", {}) or {}
    event_frame = (
        events.get("release")
        or events.get("contact_or_peak")
        or events.get("front_foot_land")
        or events.get("finish")
        or sampled_ids[len(sampled_ids) // 2]
    )
    initial_index = min(range(len(sampled_ids)), key=lambda i: abs(sampled_ids[i] - int(event_frame)))
    preview_frames = [
        {
            "frame": frame_idx,
            "time": rounded(frame_idx / fps, 3),
            "joints": frames[frame_idx],
        }
        for frame_idx in sampled_ids
    ]
    method = str(summary.get("pose3d_method") or "")
    is_advanced = any(token in method.lower() for token in ("gvhmr", "wham", "hmr2", "4dhumans", "external"))
    return {
        "fps": fps / step,
        "unit": "world-grounded body-scale units" if is_advanced else "body-scale global-relative units",
        "motion_model": method or "smoothed_root_trajectory",
        "source": summary.get("pose3d_source", ""),
        "event_frame": int(event_frame),
        "initial_index": int(initial_index),
        "frames": smooth_pose3d_preview_frames(preview_frames),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run video -> motion metrics -> stable HTML report.")
    parser.add_argument("--input", required=True, type=Path, help="Input baseball video.")
    parser.add_argument("--kind", choices=["auto", "hit", "pitch"], default="auto", help="Video action type.")
    parser.add_argument("--side", choices=["right", "left"], default="right", help="Throwing/batting side assumption.")
    parser.add_argument("--athlete-name", default="示例球员")
    parser.add_argument("--age-group", default="U12")
    parser.add_argument("--out", type=Path, default=None, help="Output directory. Defaults to outputs/end_to_end_reports/<video>.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    video_path = args.input.resolve()
    if not video_path.exists():
        raise FileNotFoundError(video_path)

    kind = infer_kind(video_path, args.kind)
    sample_id = f"{kind}_{slugify(video_path.stem)}"
    out_dir = args.out.resolve() if args.out else DEFAULT_OUT / slugify(video_path.stem)
    analysis_dir = out_dir / "analysis"
    report_dir = out_dir / "report"
    analysis_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    video_meta = {
        "path": video_path,
        "kind": kind,
        "label": video_path.stem,
        "side": args.side,
    }
    rows, summary = motion.run_video(video_meta, analysis_dir)

    raw_input = build_raw_report_input(
        rows=rows,
        summary=summary,
        sample_id=sample_id,
        kind=kind,
        athlete_name=args.athlete_name,
        age_group=args.age_group,
    )
    raw_input["session"]["report_assets"] = copy_report_assets(summary, report_dir)
    raw_input["session"]["pose3d_preview"] = build_pose3d_preview(summary)
    raw_input_path = report_dir / "raw_report_input.json"
    raw_input_path.write_text(json.dumps(raw_input, ensure_ascii=False, indent=2), encoding="utf-8")

    report = report_renderer.build_report(
        input_path=raw_input_path,
        bat_sample=raw_input["session"].get("primary_bat_sample"),
        pitch_sample=raw_input["session"].get("primary_pitch_sample"),
    )
    report_renderer.require_keys(report)
    (report_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (report_dir / "report.md").write_text(report_renderer.render_markdown(report), encoding="utf-8")
    (report_dir / "report.html").write_text(report_renderer.render_html(report), encoding="utf-8")
    (report_dir / "report_print.html").write_text(report_renderer.render_print_html(report), encoding="utf-8")

    print(
        json.dumps(
            {
                "kind": kind,
                "analysis_summary": str(Path(summary["event_contact_sheet"]).parent / "summary.json"),
                "raw_report_input": str(raw_input_path),
                "report_json": str(report_dir / "report.json"),
                "report_md": str(report_dir / "report.md"),
                "report_html": str(report_dir / "report.html"),
                "report_print_html": str(report_dir / "report_print.html"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
