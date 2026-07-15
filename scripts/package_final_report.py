from __future__ import annotations

import argparse
import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


IGNORED_SCHEMES = {"data", "http", "https", "mailto", "javascript"}
SMALL_RESEARCH_FILES = (
    "batting_dashboard_metrics.csv",
    "batting_dashboard_metrics_wide.csv",
    "alignment_2d/alignment_summary.json",
    "assets/vicon_2d_geometry_annotations/vicon_geometry_metric_annotations.json",
    "pitch_assets/video_2d_alignment/pitch_event_overlay_provenance.json",
)


class ReferenceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.references: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        for attribute in ("src", "href", "poster"):
            value = values.get(attribute)
            if not value or value.startswith("#"):
                continue
            parsed = urlsplit(value)
            if parsed.scheme.casefold() in IGNORED_SCHEMES or parsed.netloc or not parsed.path:
                continue
            self.references.add(unquote(parsed.path))


def referenced_files(html: Path) -> list[Path]:
    parser = ReferenceParser()
    parser.feed(html.read_text(encoding="utf-8-sig"))
    files: list[Path] = []
    for relative in sorted(parser.references):
        path = (html.parent / relative).resolve()
        if not path.is_file() or path.stat().st_size == 0:
            raise FileNotFoundError(f"Referenced report asset is missing or empty: {relative} -> {path}")
        files.append(path)
    return files


def archive_name(root: Path, path: Path, package_root: str) -> str:
    return str(Path(package_root) / path.relative_to(root)).replace("\\", "/")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a compact, self-contained final-report delivery ZIP.")
    parser.add_argument("html", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--package-root", default="bryan_final_report")
    parser.add_argument("--without-research-metadata", action="store_true")
    args = parser.parse_args()

    html = args.html.resolve()
    root = html.parent
    files = [html, *referenced_files(html)]
    if not args.without_research_metadata:
        for relative in SMALL_RESEARCH_FILES:
            candidate = root / relative
            if candidate.is_file() and candidate.stat().st_size > 0:
                files.append(candidate)
    files = sorted(set(files), key=lambda path: str(path.relative_to(root)).casefold())

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "entry_html": f"{args.package_root}/{html.name}",
        "source_root": str(root),
        "file_count": len(files),
        "files": [str(path.relative_to(root)).replace("\\", "/") for path in files],
    }
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in files:
            archive.write(path, archive_name(root, path, args.package_root))
        archive.writestr(
            f"{args.package_root}/DELIVERY_MANIFEST.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    print(json.dumps({**manifest, "archive": str(out), "archive_bytes": out.stat().st_size}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
