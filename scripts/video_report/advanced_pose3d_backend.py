from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass
class AdvancedPose3DResult:
    coords: np.ndarray
    visibility: np.ndarray
    source_path: Path
    backend: str


SMPL_24_NAMES = [
    "pelvis",
    "left_hip",
    "right_hip",
    "spine1",
    "left_knee",
    "right_knee",
    "spine2",
    "left_ankle",
    "right_ankle",
    "spine3",
    "left_foot",
    "right_foot",
    "neck",
    "left_collar",
    "right_collar",
    "head",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_hand",
    "right_hand",
]


def load_advanced_pose3d(
    video_path: Path | None,
    output_dir: Path,
    target_names: list[str],
    expected_frames: int | None = None,
) -> AdvancedPose3DResult | None:
    for path in candidate_paths(video_path, output_dir):
        if not path.exists() or not path.is_file():
            continue
        try:
            result = load_pose_file(path, target_names, expected_frames)
        except Exception:
            continue
        if result is not None:
            return result
    return None


def candidate_paths(video_path: Path | None, output_dir: Path) -> list[Path]:
    candidates: list[Path] = []
    exact = os.environ.get("SRS_ADVANCED_3D_FILE")
    if exact:
        candidates.append(Path(exact))

    search_dirs = [output_dir, output_dir.parent]
    configured_dir = os.environ.get("SRS_3D_MODEL_OUTPUT_DIR")
    if configured_dir:
        search_dirs.insert(0, Path(configured_dir))
    if video_path:
        search_dirs.extend([video_path.parent, video_path.parent / "advanced_3d"])

    stems = ["advanced_pose3d", "gvhmr", "wham", "hmr2", "4dhumans"]
    if video_path:
        stems.extend(
            [
                f"{video_path.stem}.advanced_pose3d",
                f"{video_path.stem}.gvhmr",
                f"{video_path.stem}.wham",
                f"{video_path.stem}.hmr2",
                f"{video_path.stem}.4dhumans",
            ]
        )
    for directory in search_dirs:
        for stem in stems:
            for suffix in (".npz", ".json", ".csv"):
                candidates.append(directory / f"{stem}{suffix}")
    return dedupe_paths(candidates)


def dedupe_paths(paths: list[Path]) -> list[Path]:
    seen = set()
    result = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def load_pose_file(path: Path, target_names: list[str], expected_frames: int | None) -> AdvancedPose3DResult | None:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        coords, visibility, source_names = read_csv_pose(path)
    elif suffix == ".json":
        coords, visibility, source_names = read_json_pose(path)
    elif suffix == ".npz":
        coords, visibility, source_names = read_npz_pose(path)
    else:
        return None
    if coords is None or coords.ndim != 3 or coords.shape[2] < 3 or coords.shape[0] < 2:
        return None

    mapped, mapped_visibility = map_to_target_landmarks(coords[:, :, :3], visibility, source_names, target_names)
    mapped = normalize_global_pose(mapped, mapped_visibility, target_names)
    if expected_frames and expected_frames > 1 and abs(len(mapped) - expected_frames) > max(4, expected_frames * 0.35):
        mapped, mapped_visibility = resample_sequence(mapped, mapped_visibility, expected_frames)

    backend = infer_backend_name(path)
    return AdvancedPose3DResult(mapped.astype(np.float32), mapped_visibility.astype(np.float32), path, backend)


def read_csv_pose(path: Path) -> tuple[np.ndarray | None, np.ndarray, list[str]]:
    frames: dict[int, list[dict[str, Any]]] = {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            frame = int(float(first_value(row, "frame_index", "frame", "t") or 0))
            frames.setdefault(frame, []).append(row)
    if not frames:
        return None, np.empty((0, 0), dtype=np.float32), []

    frame_ids = sorted(frames)
    max_joints = max(len(rows) for rows in frames.values())
    names = []
    coords = np.full((len(frame_ids), max_joints, 3), np.nan, dtype=np.float32)
    visibility = np.zeros((len(frame_ids), max_joints), dtype=np.float32)
    for frame_pos, frame_id in enumerate(frame_ids):
        for joint_pos, row in enumerate(frames[frame_id]):
            name = str(first_value(row, "joint_name", "name", "joint", "landmark") or joint_pos)
            if len(names) <= joint_pos:
                names.append(name)
            coords[frame_pos, joint_pos] = [
                float(first_value(row, "x_3d", "x", "X") or 0),
                float(first_value(row, "y_3d", "y", "Y") or 0),
                float(first_value(row, "z_3d", "z", "Z") or 0),
            ]
            visibility[frame_pos, joint_pos] = float(first_value(row, "confidence", "visibility", "c", "score") or 1.0)
    return coords, visibility, names


def read_json_pose(path: Path) -> tuple[np.ndarray | None, np.ndarray, list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    frames = data.get("frames") if isinstance(data, dict) else data
    if not isinstance(frames, list) or not frames:
        return None, np.empty((0, 0), dtype=np.float32), []
    joints_by_frame = [frame.get("joints", frame.get("keypoints_3d", [])) if isinstance(frame, dict) else frame for frame in frames]
    max_joints = max(len(joints) for joints in joints_by_frame)
    coords = np.full((len(frames), max_joints, 3), np.nan, dtype=np.float32)
    visibility = np.zeros((len(frames), max_joints), dtype=np.float32)
    names: list[str] = []
    for frame_idx, joints in enumerate(joints_by_frame):
        for joint_idx, joint in enumerate(joints):
            if isinstance(joint, dict):
                coords[frame_idx, joint_idx] = [float(joint.get("x", 0)), float(joint.get("y", 0)), float(joint.get("z", 0))]
                visibility[frame_idx, joint_idx] = float(joint.get("c", joint.get("confidence", 1.0)))
                if len(names) <= joint_idx:
                    names.append(str(joint.get("n", joint.get("name", joint_idx))))
            else:
                coords[frame_idx, joint_idx] = [float(joint[0]), float(joint[1]), float(joint[2])]
                visibility[frame_idx, joint_idx] = 1.0
                if len(names) <= joint_idx:
                    names.append(str(joint_idx))
    return coords, visibility, names


def read_npz_pose(path: Path) -> tuple[np.ndarray | None, np.ndarray, list[str]]:
    with np.load(path, allow_pickle=True) as data:
        keys = set(data.files)
        pose_key = next((key for key in ("world_joints", "joints", "joints3d", "keypoints_3d", "pred_joints", "smpl_joints") if key in keys), None)
        if not pose_key:
            return None, np.empty((0, 0), dtype=np.float32), []
        coords = np.asarray(data[pose_key], dtype=np.float32)
        while coords.ndim > 3:
            coords = coords[0]
        confidence_key = next((key for key in ("confidence", "visibility", "scores", "joint_confidence") if key in keys), None)
        if confidence_key:
            visibility = np.asarray(data[confidence_key], dtype=np.float32)
            while visibility.ndim > 2:
                visibility = visibility[0]
        else:
            visibility = np.ones(coords.shape[:2], dtype=np.float32)
        names_key = next((key for key in ("joint_names", "joints_name", "names") if key in keys), None)
        names = [str(item) for item in data[names_key].tolist()] if names_key else []
    return coords, visibility, names


def map_to_target_landmarks(
    coords: np.ndarray,
    visibility: np.ndarray,
    source_names: list[str],
    target_names: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    if coords.shape[1] == len(target_names):
        return coords.copy(), visibility.copy()
    if not source_names:
        source_names = SMPL_24_NAMES if coords.shape[1] == 24 else [str(idx) for idx in range(coords.shape[1])]

    source_lookup = {normalize_name(name): idx for idx, name in enumerate(source_names)}
    mapped = np.zeros((coords.shape[0], len(target_names), 3), dtype=np.float32)
    mapped_visibility = np.zeros((coords.shape[0], len(target_names)), dtype=np.float32)

    for target_idx, target_name in enumerate(target_names):
        candidates = source_candidates(target_name)
        source_idx = next((source_lookup[name] for name in candidates if name in source_lookup), None)
        if source_idx is None and target_idx < coords.shape[1] and str(target_idx) in source_lookup:
            source_idx = source_lookup[str(target_idx)]
        if source_idx is None:
            continue
        mapped[:, target_idx] = coords[:, source_idx]
        mapped_visibility[:, target_idx] = visibility[:, source_idx] if source_idx < visibility.shape[1] else 1.0

    fill_head_points(mapped, mapped_visibility, target_names)
    return mapped, mapped_visibility


def source_candidates(target_name: str) -> list[str]:
    name = normalize_name(target_name)
    aliases = {
        "nose": ["nose", "head"],
        "left_eye_inner": ["left_eye", "head"],
        "left_eye": ["left_eye", "head"],
        "left_eye_outer": ["left_eye", "head"],
        "right_eye_inner": ["right_eye", "head"],
        "right_eye": ["right_eye", "head"],
        "right_eye_outer": ["right_eye", "head"],
        "left_ear": ["left_ear", "head"],
        "right_ear": ["right_ear", "head"],
        "mouth_left": ["head"],
        "mouth_right": ["head"],
        "left_foot_index": ["left_foot", "left_toe", "left_ankle"],
        "right_foot_index": ["right_foot", "right_toe", "right_ankle"],
        "left_index": ["left_hand", "left_wrist"],
        "right_index": ["right_hand", "right_wrist"],
        "left_pinky": ["left_hand", "left_wrist"],
        "right_pinky": ["right_hand", "right_wrist"],
        "left_thumb": ["left_hand", "left_wrist"],
        "right_thumb": ["right_hand", "right_wrist"],
    }
    return [name, *aliases.get(name, [])]


def fill_head_points(coords: np.ndarray, visibility: np.ndarray, target_names: list[str]) -> None:
    lookup = {name: idx for idx, name in enumerate(target_names)}
    nose = lookup.get("nose")
    if nose is None or visibility[:, nose].max() <= 0:
        return
    for name in ("left_eye_inner", "left_eye", "left_eye_outer", "right_eye_inner", "right_eye", "right_eye_outer", "left_ear", "right_ear", "mouth_left", "mouth_right"):
        idx = lookup.get(name)
        if idx is not None and visibility[:, idx].max() <= 0:
            coords[:, idx] = coords[:, nose]
            visibility[:, idx] = visibility[:, nose] * 0.82


def normalize_global_pose(coords: np.ndarray, visibility: np.ndarray, target_names: list[str]) -> np.ndarray:
    out = coords.copy()
    lookup = {name: idx for idx, name in enumerate(target_names)}
    left_shoulder = lookup.get("left_shoulder")
    right_shoulder = lookup.get("right_shoulder")
    left_hip = lookup.get("left_hip")
    right_hip = lookup.get("right_hip")
    pelvis_indices = [idx for idx in (left_hip, right_hip) if idx is not None]

    scale_values = []
    if left_shoulder is not None and right_shoulder is not None:
        shoulder_width = np.linalg.norm(out[:, left_shoulder] - out[:, right_shoulder], axis=1)
        valid = (visibility[:, left_shoulder] > 0.1) & (visibility[:, right_shoulder] > 0.1) & np.isfinite(shoulder_width)
        scale_values.extend(shoulder_width[valid].tolist())
    scale = float(np.nanmedian(scale_values)) / 0.34 if scale_values else 1.0
    if not np.isfinite(scale) or scale <= 1e-5:
        scale = 1.0
    out /= scale

    if pelvis_indices:
        root = np.nanmean(out[0, pelvis_indices], axis=0)
    else:
        root = np.nanmean(out[0], axis=0)
    out -= root
    return out


def resample_sequence(coords: np.ndarray, visibility: np.ndarray, frames: int) -> tuple[np.ndarray, np.ndarray]:
    source_x = np.linspace(0.0, 1.0, len(coords))
    target_x = np.linspace(0.0, 1.0, frames)
    out = np.zeros((frames, coords.shape[1], 3), dtype=np.float32)
    out_visibility = np.zeros((frames, visibility.shape[1]), dtype=np.float32)
    for joint_idx in range(coords.shape[1]):
        for dim in range(3):
            out[:, joint_idx, dim] = np.interp(target_x, source_x, coords[:, joint_idx, dim])
        out_visibility[:, joint_idx] = np.interp(target_x, source_x, visibility[:, joint_idx])
    return out, out_visibility


def normalize_name(name: str) -> str:
    return str(name).strip().lower().replace(" ", "_").replace("-", "_")


def first_value(row: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in row and row[key] not in ("", None):
            return row[key]
    return None


def infer_backend_name(path: Path) -> str:
    text = path.stem.lower()
    if "gvhmr" in text:
        return "GVHMR"
    if "wham" in text:
        return "WHAM"
    if "4dhuman" in text or "hmr2" in text:
        return "4D-Humans/HMR2"
    return "external_human_mesh_recovery"
