from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


IGNORED_SCHEMES = {"data", "http", "https", "mailto", "javascript"}
REQUIRED_TEXT = ("球员", "教练", "研究者", "投球", "打击")
DYNAMIC_CLASSES = {"good", "review", "risk", "current-player"}


class ReportParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[tuple[str, str]] = []
        self.text_parts: list[str] = []
        self.tags: Counter[str] = Counter()
        self.classes: Counter[str] = Counter()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags[tag] += 1
        values = dict(attrs)
        for name in ("src", "href", "poster"):
            value = values.get(name)
            if value:
                self.refs.append((name, value))
        for token in (values.get("class") or "").split():
            self.classes[token] += 1

    def handle_data(self, data: str) -> None:
        text = " ".join(data.split())
        if text:
            self.text_parts.append(text)


def parse_html(path: Path) -> tuple[ReportParser, str, str]:
    source = path.read_text(encoding="utf-8-sig")
    parser = ReportParser()
    parser.feed(source)
    return parser, " ".join(parser.text_parts), source


def local_target(html: Path, value: str) -> Path | None:
    value = value.strip()
    if not value or value.startswith("#"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme.casefold() in IGNORED_SCHEMES or parsed.netloc:
        return None
    path = unquote(parsed.path)
    if not path:
        return None
    return (html.parent / path).resolve()


def structure_delta(current: ReportParser, gold: ReportParser) -> dict[str, dict[str, int]]:
    def delta(left: Counter[str], right: Counter[str], *, ignored: set[str] | None = None) -> dict[str, int]:
        ignored = ignored or set()
        keys = left.keys() | right.keys()
        return {
            key: left[key] - right[key]
            for key in sorted(keys)
            if key not in ignored and left[key] != right[key]
        }

    return {
        "tags": delta(current.tags, gold.tags),
        "classes": delta(current.classes, gold.classes, ignored=DYNAMIC_CLASSES),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a combined final baseball report before delivery.")
    parser.add_argument("html", type=Path)
    parser.add_argument("--athlete", required=True, help="Primary athlete name, for example Bryan")
    parser.add_argument("--gold-html", type=Path)
    parser.add_argument("--forbidden-subject", action="append", default=[])
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    html = args.html.resolve()
    parsed, text, source = parse_html(html)
    errors: list[str] = []
    warnings: list[str] = []

    missing_refs: list[dict[str, str]] = []
    for attribute, value in parsed.refs:
        target = local_target(html, value)
        if target is not None and (not target.is_file() or target.stat().st_size == 0):
            missing_refs.append({"attribute": attribute, "value": value, "resolved": str(target)})
    if missing_refs:
        errors.append(f"{len(missing_refs)} local src/href/poster targets are missing")

    for label in REQUIRED_TEXT:
        if label not in text:
            errors.append(f"required report label is missing: {label}")
    if args.athlete.casefold() not in text.casefold():
        errors.append(f"primary athlete name does not appear in visible text: {args.athlete}")

    for forbidden in args.forbidden_subject:
        patterns = (
            rf"\b{re.escape(forbidden)}\s*的",
            rf"\b{re.escape(forbidden)}(?:'s|\s+is|\s+has)\b",
        )
        matches = sorted({m.group(0) for pattern in patterns for m in re.finditer(pattern, text, re.IGNORECASE)})
        if matches:
            warnings.append(f"possible subject leakage for {forbidden}: {', '.join(matches)}")

    expected_pitch_assets = (
        f"{args.athlete.casefold()}_pitch_peak_knee_2d_overlay.png",
        f"{args.athlete.casefold()}_pitch_foot_plant_2d_overlay.png",
        f"{args.athlete.casefold()}_pitch_release_2d_overlay.png",
        f"{args.athlete.casefold()}_pitch_angle_time_curve.png",
        f"{args.athlete.casefold()}_pitch_speed_time_curve.png",
        f"{args.athlete.casefold()}_kinetic_chain_time_curves.png",
    )
    referenced_names = {Path(urlsplit(value).path).name.casefold() for _, value in parsed.refs}
    for asset in expected_pitch_assets:
        if asset.casefold() not in referenced_names:
            errors.append(f"required pitching asset is not referenced: {asset}")

    if "其他球员表现区间" in text:
        errors.append("legacy age-band label is still present: 其他球员表现区间")
    if "U9" not in text.upper():
        errors.append("approved U9 label is missing")
    if re.search(r"头部位移.{0,20}\b\d+(?:\.\d+)?\s*mm\b", text, re.IGNORECASE):
        warnings.append("user-facing head displacement may still be displayed in mm")
    if re.search(r"analyst[^}]{0,160}grid-template-columns\s*:\s*repeat\(2", source, re.IGNORECASE | re.DOTALL):
        warnings.append("researcher chart CSS may still use a two-column layout")

    comparison: dict[str, object] | None = None
    if args.gold_html:
        gold_parser, _, _ = parse_html(args.gold_html.resolve())
        comparison = structure_delta(parsed, gold_parser)
        changed_tags = sum(abs(value) for value in comparison["tags"].values())
        changed_classes = sum(abs(value) for value in comparison["classes"].values())
        if changed_tags or changed_classes:
            warnings.append(
                f"gold-template structure differs: tag delta magnitude {changed_tags}, class delta magnitude {changed_classes}"
            )

    result = {
        "html": str(html),
        "athlete": args.athlete,
        "status": "error" if errors else "ok",
        "errors": errors,
        "warnings": warnings,
        "local_reference_count": sum(1 for _, value in parsed.refs if local_target(html, value) is not None),
        "missing_references": missing_refs,
        "gold_structure_delta": comparison,
    }
    payload = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json_out:
        args.json_out.resolve().parent.mkdir(parents=True, exist_ok=True)
        args.json_out.resolve().write_text(payload, encoding="utf-8")
    print(payload)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
