from __future__ import annotations

import math
from collections.abc import Mapping
from numbers import Real


def normalize_legacy_json(value: object, path: str = "value") -> tuple[object, tuple[str, ...]]:
    """Replace non-finite legacy JSON numbers with null and report their paths."""

    if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
        return value, ()
    if isinstance(value, Real):
        numeric = float(value)
        if math.isfinite(numeric):
            return value, ()
        return None, (path,)
    if isinstance(value, Mapping):
        normalized: dict[str, object] = {}
        paths: list[str] = []
        for key, item in value.items():
            child, child_paths = normalize_legacy_json(item, f"{path}.{key}")
            normalized[str(key)] = child
            paths.extend(child_paths)
        return normalized, tuple(paths)
    if isinstance(value, (list, tuple)):
        normalized_items: list[object] = []
        paths: list[str] = []
        for index, item in enumerate(value):
            child, child_paths = normalize_legacy_json(item, f"{path}[{index}]")
            normalized_items.append(child)
            paths.extend(child_paths)
        return normalized_items, tuple(paths)
    return value, ()
