from __future__ import annotations

from pathlib import Path
import shutil

from baseball_report.core.errors import ReportBuildError


def copy_report_asset_tree(source: Path, destination: Path) -> Path:
    """Copy a generated asset tree without allowing source/output overlap."""

    source_resolved = source.resolve()
    destination_resolved = destination.resolve()
    if not source_resolved.is_dir():
        raise ReportBuildError(f"report asset source directory does not exist: {source_resolved}")
    if source_resolved == destination_resolved:
        raise ReportBuildError("report asset source and destination must be different directories")
    if source_resolved in destination_resolved.parents or destination_resolved in source_resolved.parents:
        raise ReportBuildError("report asset source and destination must not contain one another")
    destination_resolved.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        source_resolved,
        destination_resolved,
        dirs_exist_ok=True,
        ignore=shutil.ignore_patterns("._*", ".DS_Store"),
    )
    return destination_resolved
