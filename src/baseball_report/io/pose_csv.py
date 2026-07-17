from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

import numpy as np

from baseball_report.core.enums import CoordinateProfile, MotionType, SourceType
from baseball_report.core.motion import MotionSequence
from baseball_report.core.provenance import AnalysisWarning, Provenance


@dataclass(frozen=True)
class PoseMotionData:
    motion: MotionSequence
    backend: str
    source_frame_numbers: tuple[int, ...]
    landmark_names: tuple[str, ...]
    supports_depth: bool
    native_landmark_count: int | None


def _number(value: object) -> float:
    if value in (None, ""):
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"pose row contains a non-numeric coordinate: {value!r}") from exc


def adapt_pose_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    sequence_id: str,
    motion_type: MotionType,
    backend: str,
    frame_rate_hz: float | None = None,
) -> PoseMotionData:
    if not rows:
        raise ValueError("pose rows must not be empty")
    grouped: dict[int, dict[str, Mapping[str, object]]] = {}
    frame_timestamps: dict[int, float] = {}
    landmark_order: list[str] = []
    for row in rows:
        try:
            frame = int(row["frame_index"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("pose row requires an integer frame_index") from exc
        if frame < 0:
            raise ValueError("pose frame_index must be non-negative")
        landmark = str(row.get("landmark") or "").strip()
        if not landmark:
            raise ValueError("pose row requires landmark")
        by_landmark = grouped.setdefault(frame, {})
        if landmark in by_landmark:
            raise ValueError(f"duplicate pose row for frame={frame}, landmark={landmark}")
        by_landmark[landmark] = row
        if landmark not in landmark_order:
            landmark_order.append(landmark)
        timestamp = _number(row.get("timestamp_sec"))
        if not np.isfinite(timestamp) or timestamp < 0:
            raise ValueError("pose timestamp_sec must be finite and non-negative")
        previous = frame_timestamps.setdefault(frame, timestamp)
        if not np.isclose(previous, timestamp):
            raise ValueError(f"pose rows disagree on timestamp for frame {frame}")

    source_frames = tuple(sorted(grouped))
    expected_landmarks = set(landmark_order)
    for frame in source_frames:
        if set(grouped[frame]) != expected_landmarks:
            raise ValueError(f"pose frame {frame} does not contain the common landmark set")
    timestamps = np.asarray([frame_timestamps[frame] for frame in source_frames], dtype=float)
    if frame_rate_hz is not None:
        frame_rate = float(frame_rate_hz)
        if not np.isfinite(frame_rate) or frame_rate <= 0:
            raise ValueError("frame_rate_hz must be finite and positive")
    elif len(timestamps) > 1:
        deltas = np.diff(timestamps)
        if not np.isfinite(deltas).all() or np.any(deltas <= 0):
            raise ValueError("pose timestamps must be strictly increasing")
        frame_rate = float(1.0 / np.median(deltas / np.diff(source_frames)))
    else:
        raise ValueError("frame_rate_hz is required when pose rows contain one frame")

    normalized_points: dict[str, np.ndarray] = {}
    confidence: dict[str, np.ndarray] = {}
    valid: dict[str, np.ndarray] = {}
    observed_depth = False
    for landmark in landmark_order:
        values = np.asarray(
            [
                [
                    _number(grouped[frame][landmark].get("x_norm")),
                    _number(grouped[frame][landmark].get("y_norm")),
                    _number(grouped[frame][landmark].get("z_norm")),
                ]
                for frame in source_frames
            ],
            dtype=float,
        )
        normalized_points[landmark] = values
        observed_depth = observed_depth or bool(np.isfinite(values[:, 2]).any())
        confidence[landmark] = np.asarray(
            [_number(grouped[frame][landmark].get("visibility")) for frame in source_frames],
            dtype=float,
        )
        valid[landmark] = np.isfinite(values[:, :2]).all(axis=1)

    backend_key = backend.casefold()
    is_rtmpose = "rtmpose" in backend_key
    supports_depth = not is_rtmpose
    source_type = SourceType.RTMPOSE if is_rtmpose else SourceType.MEDIAPIPE
    coordinate = (
        CoordinateProfile.RTMPOSE_IMAGE
        if is_rtmpose
        else CoordinateProfile.MEDIAPIPE_IMAGE_NORMALIZED
    )
    native_count = 17 if is_rtmpose else len(landmark_order)
    warnings: tuple[AnalysisWarning, ...] = ()
    if is_rtmpose:
        warnings = (
            AnalysisWarning(
                code="pose.rtmpose_transport_mapping",
                message=(
                    "RTMPose COCO17 points are duplicated into the report's 33-row "
                    "transport schema and do not provide depth."
                ),
                context={"native_landmark_count": 17, "transport_landmark_count": len(landmark_order)},
            ),
        )
    motion = MotionSequence(
        sequence_id=sequence_id,
        source_type=source_type,
        motion_type=motion_type,
        frame_rate_hz=frame_rate,
        frame_count=len(source_frames),
        first_source_frame=source_frames[0],
        points=normalized_points,
        timestamps_seconds=timestamps,
        coordinate_system=coordinate,
        length_unit="normalized_image",
        provenance=Provenance(
            source_type=source_type.value,
            source_id=sequence_id,
            algorithm_id=backend,
        ),
        valid=valid,
        confidence=confidence,
        metadata={
            "backend": backend,
            "source_frame_numbers": source_frames,
            "native_landmark_count": native_count,
            "transport_landmark_count": len(landmark_order),
            "supports_depth": supports_depth,
            "observed_depth": observed_depth,
        },
        warnings=warnings,
    )
    return PoseMotionData(
        motion=motion,
        backend=backend,
        source_frame_numbers=source_frames,
        landmark_names=tuple(landmark_order),
        supports_depth=supports_depth,
        native_landmark_count=native_count,
    )
