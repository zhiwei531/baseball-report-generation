from __future__ import annotations

import struct
from collections.abc import Sequence

import numpy as np


def _group_record(name: str, group_id: int) -> bytes:
    encoded = name.encode("latin1")
    return struct.pack("bb", len(encoded), -group_id) + encoded + struct.pack("<h", 2)


def _parameter_record(name: str, group_id: int, payload: bytes) -> bytes:
    encoded = name.encode("latin1")
    return (
        struct.pack("bb", len(encoded), group_id)
        + encoded
        + struct.pack("<h", len(payload) + 2)
        + payload
    )


def _string_payload(values: Sequence[str]) -> bytes:
    width = max(len(value.encode("latin1")) for value in values)
    raw = b"".join(value.encode("latin1").ljust(width, b" ") for value in values)
    return struct.pack("bb", -1, 2) + bytes((width, len(values))) + raw


def make_c3d_bytes(
    *,
    labels: Sequence[str],
    points: np.ndarray,
    first_frame: int = 42,
    rate_hz: float = 100.0,
    units: str = "mm",
    scale: float = -1.0,
) -> bytes:
    """Create the small C3D subset understood by both current custom readers.

    ``points`` has shape ``frames x points x 4``. XYZ values are physical
    values; the fourth component is the legacy residual/camera field.
    """

    values = np.asarray(points, dtype=float)
    if values.ndim != 3 or values.shape[2] != 4:
        raise ValueError("points must have shape frames x points x 4")
    if values.shape[1] != len(labels):
        raise ValueError("label count must equal point count")
    if not labels or values.shape[0] == 0:
        raise ValueError("at least one point and frame are required")
    if not 0 <= first_frame <= 65535:
        raise ValueError("first_frame must fit the legacy uint16 header")

    frame_count, point_count = values.shape[:2]
    last_frame = first_frame + frame_count - 1
    header = bytearray(512)
    header[0] = 2
    header[1] = 80
    struct.pack_into("<H", header, 2, point_count)
    struct.pack_into("<H", header, 6, first_frame)
    struct.pack_into("<H", header, 8, last_frame)
    struct.pack_into("<f", header, 12, scale)
    struct.pack_into("<H", header, 16, 3)
    struct.pack_into("<f", header, 20, rate_hz)

    params = bytearray(512)
    params[:4] = bytes((1, 80, 1, 84))
    records = b"".join(
        (
            _group_record("POINT", 1),
            _parameter_record("LABELS", 1, _string_payload(labels)),
            _parameter_record("UNITS", 1, _string_payload((units,))),
            _parameter_record("RATE", 1, struct.pack("bbf", 4, 0, rate_hz)),
            b"\x00",
        )
    )
    if len(records) > len(params) - 4:
        raise ValueError("synthetic parameter block is too large")
    params[4 : 4 + len(records)] = records

    if scale < 0:
        point_bytes = np.asarray(values, dtype="<f4").tobytes()
    else:
        stored = values.copy()
        stored[:, :, :3] /= scale
        if not np.allclose(stored, np.rint(stored)):
            raise ValueError("positive-scale XYZ values must be exact scale multiples")
        point_bytes = np.asarray(np.rint(stored), dtype="<i2").tobytes()
    return bytes(header + params) + point_bytes
