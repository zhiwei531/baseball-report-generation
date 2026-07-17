from __future__ import annotations

import math
from collections.abc import Mapping
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import TypeVar, cast

T = TypeVar("T")


def require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def require_finite(value: float, field_name: str, *, positive: bool = False) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    if positive and number <= 0:
        raise ValueError(f"{field_name} must be positive")
    return number


def optional_finite(value: float | None, field_name: str) -> float | None:
    if value is None:
        return None
    return require_finite(value, field_name)


def _frozen_value(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _frozen_value(item) for key, item in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_frozen_value(item) for item in value)
    if isinstance(value, set):
        return frozenset(_frozen_value(item) for item in value)
    return value


def frozen_mapping(value: Mapping[str, T] | None) -> Mapping[str, T]:
    return cast(Mapping[str, T], _frozen_value(value or {}))


def portable_report_ref(value: str, field_name: str) -> str:
    require_text(value, field_name)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError(f"{field_name} must be report-root-relative POSIX path")
    return value
