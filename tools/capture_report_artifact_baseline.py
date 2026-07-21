from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    return _sha256_bytes(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    )


def _files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and not path.name.startswith("._") and path.name != ".DS_Store"
    )


def _directory_summary(root: Path) -> dict[str, object]:
    files = _files(root)
    inventory = [
        {
            "relative": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
        }
        for path in files
    ]
    chart_files = [
        path
        for path in files
        if any(part in {"analyst_charts", "kinetic_chain"} for part in path.relative_to(root).parts)
    ]
    chart_inventory = [
        {
            "relative": path.relative_to(root).as_posix(),
            "size": path.stat().st_size,
            "sha256": _sha256_file(path),
        }
        for path in chart_files
    ]
    return {
        "file_count": len(files),
        "total_size_bytes": sum(path.stat().st_size for path in files),
        "extension_counts": dict(sorted(Counter(path.suffix.lower() or "<none>" for path in files).items())),
        "inventory_metadata_sha256": _canonical_sha256(inventory),
        "chart_artifact_count": len(chart_files),
        "chart_artifacts_sha256": _canonical_sha256(chart_inventory),
    }


def _html_summary(path: Path) -> dict[str, object]:
    html = path.read_text(encoding="utf-8")
    refs = re.findall(r'(?:src|href)=["\']([^"\']+)', html)
    local_refs = []
    missing = []
    for ref in refs:
        clean = ref.split("?", 1)[0].split("#", 1)[0]
        if not clean or clean.startswith(("data:", "http:", "https:", "mailto:", "javascript:")):
            continue
        local_refs.append(clean)
        if not (path.parent / clean).exists():
            missing.append(clean)
    return {
        "size_bytes": path.stat().st_size,
        "html_sha256": _sha256_file(path),
        "section_count": len(re.findall(r"<section\b", html)),
        "metric_card_count": len(re.findall(r'<article class="metric-card\b', html)),
        "peer_range_count": len(re.findall(r'class="peer-range\b', html)),
        "coach_reference_count": len(re.findall(r'class="pitch-coach-reference\b', html)),
        "image_count": len(re.findall(r"<img\b", html)),
        "local_reference_count": len(local_refs),
        "local_references_sha256": _canonical_sha256(local_refs),
        "missing_local_references": sorted(set(missing)),
    }


def _xlsx_summary(path: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    sheet_names = [
        sheet.attrib["name"] for sheet in workbook.findall("x:sheets/x:sheet", namespace)
    ]
    return {
        "size_bytes": path.stat().st_size,
        "sha256": _sha256_file(path),
        "sheet_names": sheet_names,
    }


def _batting_schema(path: Path) -> dict[str, object]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return {
        "columns": reader.fieldnames,
        "row_count": len(rows),
        "metric_ids": sorted({row["metric_key"] for row in rows}),
        "trial_count": len({row["trial_id"] for row in rows}),
    }


def _pitching_schema(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    athletes = payload.get("athletes", [])
    return {
        "top_level_keys": sorted(payload),
        "athlete_count": len(athletes),
        "event_ids": sorted({key for athlete in athletes for key in athlete.get("events", {})}),
        "value_ids": sorted({key for athlete in athletes for key in athlete.get("values", {})}),
    }


def capture_report_artifacts(
    *,
    pitching_dir: Path,
    combined_dir: Path,
    combined_html: Path,
    xlsx: Path,
) -> dict[str, object]:
    return {
        "schema_version": "characterization.v1",
        "case_id": "protected_report_case_a",
        "pitching_html": _html_summary(pitching_dir / "index.html"),
        "combined_html": _html_summary(combined_html),
        "pitching_directory": _directory_summary(pitching_dir),
        "combined_directory": _directory_summary(combined_dir),
        "batting_schema": _batting_schema(combined_dir / "batting_dashboard_metrics.csv"),
        "pitching_schema": _pitching_schema(pitching_dir / "pitch_metrics_summary.json"),
        "xlsx": _xlsx_summary(xlsx),
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture or verify an anonymized report artifact baseline.")
    parser.add_argument("--pitching-dir", required=True, type=Path)
    parser.add_argument("--combined-dir", required=True, type=Path)
    parser.add_argument("--combined-html", required=True, type=Path)
    parser.add_argument("--xlsx", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--verify", type=Path)
    args = parser.parse_args()
    if bool(args.output) == bool(args.verify):
        parser.error("choose exactly one of --output or --verify")
    manifest = capture_report_artifacts(
        pitching_dir=args.pitching_dir,
        combined_dir=args.combined_dir,
        combined_html=args.combined_html,
        xlsx=args.xlsx,
    )
    if args.verify:
        expected = _load_json(args.verify)
        if manifest != expected:
            raise SystemExit("report artifact baseline mismatch")
        print(f"baseline verified: {args.verify}")
        return
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)


if __name__ == "__main__":
    main()
