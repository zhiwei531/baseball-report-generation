from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import numpy as np
from numpy.typing import NDArray

from baseball_report.core.enums import CoordinateProfile, MotionType, SourceType
from baseball_report.core.motion import MotionSequence
from baseball_report.core.provenance import AnalysisWarning, Provenance


class LegacyC3DTrial(Protocol):
    path: Path
    labels: list[str]
    points: NDArray[np.floating]
    rate_hz: float
    units: str


@dataclass(frozen=True)
class C3DHeaderMetadata:
    parameter_block: int
    point_count: int
    analog_measurements_per_frame: int
    first_frame: int
    last_frame: int
    data_block: int
    rate_hz: float
    scale_factor: float
    storage_type: str

    @property
    def frame_count(self) -> int:
        return self.last_frame - self.first_frame + 1


@dataclass(frozen=True)
class C3DMotionData:
    motion: MotionSequence
    header: C3DHeaderMetadata
    legacy_points: NDArray[np.floating]
    residuals: NDArray[np.floating]
    point_keys: tuple[str, ...]
    raw_labels: tuple[str, ...]
    clean_labels: tuple[str, ...]

    def __post_init__(self) -> None:
        legacy = np.array(self.legacy_points, dtype=float, copy=True)
        residuals = np.array(self.residuals, dtype=float, copy=True)
        expected = (self.motion.frame_count, len(self.point_keys), 4)
        if legacy.shape != expected:
            raise ValueError(f"legacy_points must have shape {expected}")
        if residuals.shape != expected[:2]:
            raise ValueError(f"residuals must have shape {expected[:2]}")
        legacy.setflags(write=False)
        residuals.setflags(write=False)
        object.__setattr__(self, "legacy_points", legacy)
        object.__setattr__(self, "residuals", residuals)
        object.__setattr__(self, "point_keys", tuple(self.point_keys))
        object.__setattr__(self, "raw_labels", tuple(self.raw_labels))
        object.__setattr__(self, "clean_labels", tuple(self.clean_labels))


def inspect_c3d_header(path: Path) -> C3DHeaderMetadata:
    with path.open("rb") as handle:
        header = handle.read(512)
    if len(header) < 512:
        raise ValueError(f"C3D header is shorter than 512 bytes: {path}")
    scale = struct.unpack_from("<f", header, 12)[0]
    first_frame = struct.unpack_from("<H", header, 6)[0]
    last_frame = struct.unpack_from("<H", header, 8)[0]
    if last_frame < first_frame:
        raise ValueError(f"C3D last frame precedes first frame: {path}")
    return C3DHeaderMetadata(
        parameter_block=header[0],
        point_count=struct.unpack_from("<H", header, 2)[0],
        analog_measurements_per_frame=struct.unpack_from("<H", header, 4)[0],
        first_frame=first_frame,
        last_frame=last_frame,
        data_block=struct.unpack_from("<H", header, 16)[0],
        rate_hz=float(struct.unpack_from("<f", header, 20)[0]),
        scale_factor=float(scale),
        storage_type="float32" if scale < 0 else "int16_scaled",
    )


def _clean_label(label: str) -> str:
    return label.split(":", 1)[-1].strip()


def _point_keys(labels: list[str]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    keys: list[str] = []
    for index, raw_label in enumerate(labels):
        base = raw_label.strip() or f"point_{index}"
        occurrence = counts.get(base, 0) + 1
        counts[base] = occurrence
        keys.append(base if occurrence == 1 else f"{base}#{occurrence}")
    return tuple(keys)


def _default_sequence_id(path: Path) -> str:
    value = f"{path.parent.name}_{path.stem}".strip("_").lower()
    return re.sub(r"[^a-z0-9_-]+", "_", value).strip("_") or "c3d_sequence"


def _infer_motion_type(path: Path) -> MotionType:
    return MotionType.BATTING if "bat" in path.name.casefold() else MotionType.PITCHING


def adapt_legacy_c3d(
    trial: LegacyC3DTrial,
    *,
    motion_type: MotionType | None = None,
    sequence_id: str | None = None,
) -> C3DMotionData:
    header = inspect_c3d_header(trial.path)
    legacy = np.asarray(trial.points, dtype=float)
    if legacy.ndim != 3 or legacy.shape[2] != 4:
        raise ValueError("legacy C3D points must have shape frames x points x 4")
    if legacy.shape[:2] != (header.frame_count, header.point_count):
        raise ValueError(
            "legacy C3D point shape does not match header: "
            f"{legacy.shape[:2]} != {(header.frame_count, header.point_count)}"
        )
    if len(trial.labels) != header.point_count:
        raise ValueError("legacy C3D label count does not match header point count")
    if not np.isclose(float(trial.rate_hz), header.rate_hz):
        raise ValueError("legacy C3D rate does not match header point rate")

    keys = _point_keys(trial.labels)
    points = {key: legacy[:, index, :3] for index, key in enumerate(keys)}
    valid = {
        key: np.isfinite(legacy[:, index, :3]).all(axis=1)
        for index, key in enumerate(keys)
    }
    unit = str(trial.units)
    warnings: tuple[AnalysisWarning, ...] = ()
    coordinate = CoordinateProfile.LEGACY_VICON_Z_UP_MM
    if unit.casefold() != "mm":
        coordinate = CoordinateProfile.UNKNOWN
        warnings = (
            AnalysisWarning(
                code="c3d.non_mm_coordinate_profile",
                message="Legacy Vicon Z-up profile is only declared for millimetre point data.",
                context={"length_unit": unit},
            ),
        )
    timestamps = np.arange(header.frame_count, dtype=float) / float(trial.rate_hz)
    raw_labels = tuple(str(label) for label in trial.labels)
    clean_labels = tuple(_clean_label(label) for label in raw_labels)
    motion = MotionSequence(
        sequence_id=sequence_id or _default_sequence_id(trial.path),
        source_type=SourceType.C3D,
        motion_type=motion_type or _infer_motion_type(trial.path),
        frame_rate_hz=float(trial.rate_hz),
        frame_count=header.frame_count,
        first_source_frame=header.first_frame,
        points=points,
        timestamps_seconds=timestamps,
        coordinate_system=coordinate,
        length_unit=unit,
        provenance=Provenance(
            source_type=SourceType.C3D.value,
            source_id=str(trial.path),
            algorithm_id="build_vicon_2026_metrics.read_c3d",
            details={
                "storage_type": header.storage_type,
                "scale_factor": header.scale_factor,
            },
        ),
        valid=valid,
        metadata={
            "first_source_frame": header.first_frame,
            "last_source_frame": header.last_frame,
            "point_count": header.point_count,
            "analog_measurements_per_frame": header.analog_measurements_per_frame,
            "raw_labels": raw_labels,
            "clean_labels": clean_labels,
            "point_keys": keys,
            "frame_index_convention": "zero_based_loaded_array",
            "source_frame_convention": "c3d_header_frame_number",
        },
        warnings=warnings,
    )
    return C3DMotionData(
        motion=motion,
        header=header,
        legacy_points=legacy,
        residuals=legacy[:, :, 3],
        point_keys=keys,
        raw_labels=raw_labels,
        clean_labels=clean_labels,
    )
