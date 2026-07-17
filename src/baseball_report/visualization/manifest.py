from __future__ import annotations

import hashlib
import mimetypes
from pathlib import Path
import re

from baseball_report.core.enums import QualityStatus
from baseball_report.core.provenance import Provenance
from baseball_report.reporting.models import ReportAsset


SUPPORTED_ASSET_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".svg", ".json", ".csv"}
)
IGNORED_NAMES = frozenset({".DS_Store"})


def discover_report_assets(report_root: Path) -> tuple[ReportAsset, ...]:
    """Inventory existing report artifacts without interpreting their numbers."""

    root = report_root.resolve()
    if not root.is_dir():
        return ()
    assets: list[ReportAsset] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in IGNORED_NAMES or path.name.startswith("._"):
            continue
        if path.suffix.lower() not in SUPPORTED_ASSET_SUFFIXES:
            continue
        relative = path.relative_to(root).as_posix()
        if relative in {"analysis_report_data.json", "analysis_report_view.json"}:
            continue
        mime_type, _encoding = mimetypes.guess_type(path.name)
        kind = _asset_kind(path.suffix.lower())
        assets.append(
            ReportAsset(
                asset_id=(
                    "asset."
                    + re.sub(r"[^a-zA-Z0-9_.-]+", "_", relative)
                    + "."
                    + hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
                ),
                kind=kind,
                file_ref=relative,
                mime_type=mime_type,
                quality=QualityStatus.VALID,
                provenance=Provenance(
                    source_type="generated_report_artifact",
                    source_id=relative,
                    algorithm_id="baseball_report.visualization.manifest.discovery",
                ),
                metadata={"size_bytes": path.stat().st_size, "suffix": path.suffix.lower()},
            )
        )
    return tuple(assets)


def _asset_kind(suffix: str) -> str:
    if suffix in {".png", ".jpg", ".jpeg", ".svg"}:
        return "image"
    if suffix == ".gif":
        return "animation"
    if suffix == ".mp4":
        return "video"
    return "data"
