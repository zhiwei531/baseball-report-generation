from __future__ import annotations

import csv
import argparse
import importlib.util
import re
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
REPORT_DIR = PROJECT_DIR / "reports" / "vicon_2026_julian_coach"
HTML_PATH = REPORT_DIR / "julian_coach_metrics_section.html"
METRICS_PATH = REPORT_DIR / "batting_dashboard_metrics.csv"
POSE3D_PATH = REPORT_DIR / "vicon_2026_pose3d.csv"
PEERS_DIR = PROJECT_DIR / "outputs" / "batting_metrics_excel" / "all_players"
BUILDER_PATH = PROJECT_DIR / "scripts" / "build_julian_coach_metrics_section.py"
PLAYER_SAMPLE_NAME = "julian"
COACH_SAMPLE_NAME = "coach"
PLAYER_SLUG = "julian"
PLAYER_LABEL = "Julian"

PEER_COLOR_BY_NAME = {
    "bryan": "#2563eb",
    "7zai": "#16a34a",
    "xuanxuan": "#f97316",
    "green": "#a855f7",
    "julian": "#ef4444",
    "youyou": "#0891b2",
    "james": "#ca8a04",
    "branden": "#344054",
    "brandon": "#344054",
}
PEER_KEY_ALIASES = {"brandon": "branden"}
PEER_DISPLAY_BY_NAME = {
    "bryan": "Bryan陈柏谚",
    "7zai": "席启源",
    "xuanxuan": "姚槿宏",
    "green": "杜子墨",
    "julian": "Julian",
    "youyou": "费怡然",
    "james": "桑禹诚",
    "branden": "缪炜昱",
    "brandon": "缪炜昱",
}

PLAYER_CARD_METRIC_KEYS = [
    "ready_com_height_ratio",
    "ready_rear_hip_flexion_deg",
    "ready_rear_knee_flexion_deg",
    "ready_hip_shoulder_separation_deg",
    "ready_bat_tilt_deg",
    "ready_hand_height_ratio",
    "ready_to_contact_head_displacement_mm",
    "contact_bat_speed_kmh",
    "contact_attack_angle_deg",
    "contact_pelvis_rotation_open_deg",
    "contact_torso_rotation_open_deg",
    "contact_front_knee_flexion_deg",
    "coach_hitting_zone_stability_score",
]

SECTION_TITLE_LEVEL_CSS = """
    .section-title { position:relative; }
    .section-title:has(h1) { display:block; margin:0 0 34px; padding:0; }
    .section-title:has(h1) .mark { display:none; }
    .section-title:has(h1) h1 { font-size:42px; line-height:52px; font-weight:800; margin:0; letter-spacing:0; }
    .section-title:has(h2) { display:flex; align-items:center; gap:12px; width:100%; min-height:38px; margin:0 0 28px; padding:0 18px 0 0; background:#dbeafe; }
    .section-title:has(h2) .mark { display:block; width:12px; height:38px; background:#60a5fa; border-radius:999px; flex:0 0 auto; }
    .section-title:has(h2) h2 { font-size:22px; line-height:30px; font-weight:800; margin:0; color:#000; }
    .section-title:has(h3) { display:flex; align-items:center; gap:12px; margin:0 0 28px; padding:0; }
    .section-title:has(h3) .mark { width:0; height:0; border-left:9px solid transparent; border-right:9px solid transparent; border-top:18px solid #ef4444; border-radius:0; background:transparent; flex:0 0 auto; transform:translateY(-1px); }
    .section-title:has(h3) h3 { font-size:24px; line-height:34px; font-weight:800; margin:0; color:#101828; }
    .section-title:has(h4) { display:flex; align-items:center; gap:14px; margin:0 0 18px; padding:0; }
    .section-title:has(h4) .mark { width:12px; height:40px; background:#2563eb; border-radius:999px; flex:0 0 auto; }
    .section-title:has(h4) h4 { font-size:22px; line-height:32px; font-weight:800; margin:0; color:#101828; }
    .pitch-report .section-title:has(h1) { display:block; margin:0 0 34px; padding:0; }
    .pitch-report .section-title:has(h1) .mark { display:none; }
    .pitch-report .section-title:has(h1) h1 { font-size:42px; line-height:52px; font-weight:800; margin:0; letter-spacing:0; }
    .pitch-report .section-title:has(h2) { display:flex; align-items:center; gap:12px; width:100%; min-height:38px; margin:0 0 28px; padding:0 18px 0 0; background:#dbeafe; }
    .pitch-report .section-title:has(h2) .mark { display:block; width:12px; height:38px; background:#60a5fa; border-radius:999px; flex:0 0 auto; }
    .pitch-report .section-title:has(h2) h2 { font-size:22px; line-height:30px; font-weight:800; margin:0; color:#000; }
    .pitch-report .section-title:has(h3) { display:flex; align-items:center; gap:12px; margin:0 0 28px; padding:0; }
    .pitch-report .section-title:has(h3) .mark { width:0; height:0; border-left:9px solid transparent; border-right:9px solid transparent; border-top:18px solid #ef4444; border-radius:0; background:transparent; flex:0 0 auto; transform:translateY(-1px); }
    .pitch-report .section-title:has(h3) h3 { font-size:24px; line-height:34px; font-weight:800; margin:0; color:#101828; }
    .pitch-report .section-title:has(h4) { display:flex; align-items:center; gap:14px; margin:0 0 18px; padding:0; }
    .pitch-report .section-title:has(h4) .mark { width:12px; height:40px; background:#2563eb; border-radius:999px; flex:0 0 auto; }
    .pitch-report .section-title:has(h4) h4 { font-size:22px; line-height:32px; font-weight:800; margin:0; color:#101828; }
    @media (max-width:640px) {
      .section-title:has(h1) h1,
      .pitch-report .section-title:has(h1) h1 { font-size:32px; line-height:40px; }
      .section-title:has(h2),
      .pitch-report .section-title:has(h2) { min-height:36px; margin-bottom:24px; }
      .section-title:has(h2) h2,
      .pitch-report .section-title:has(h2) h2 { font-size:19px; line-height:27px; }
      .section-title:has(h3) h3,
      .pitch-report .section-title:has(h3) h3 { font-size:22px; line-height:30px; }
      .section-title:has(h4) h4,
      .pitch-report .section-title:has(h4) h4 { font-size:20px; line-height:28px; }
    }
"""

UNIT_CN = {
    "deg": "°",
    "deg/s": "°/s",
    "km/h": "km/h",
    "mm": "mm",
    "height_ratio": "身高比",
    "0-100 risk": "风险分",
    "0-100 score": "分",
}


def fmt(value: str | float | None, unit: str | None) -> str:
    if value in (None, ""):
        return "暂无"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "暂无"
    if unit == "height_ratio":
        rounded = round(number * 100, 1)
        text = f"{rounded:.0f}%" if rounded.is_integer() else f"{rounded:.1f}%"
        return f"{text} 身高比"
    if unit == "mm":
        return f"{number / 10:.1f} cm"
    elif unit in {"0-100 risk", "0-100 score"}:
        text = f"{number:.1f}"
    elif abs(number) >= 100:
        text = f"{number:.0f}"
    elif abs(number) >= 10:
        text = f"{number:.1f}"
    else:
        text = f"{number:.2f}"
    label = UNIT_CN.get(unit or "", unit or "")
    return f"{text}{label}" if label in {"度", "毫米", "分"} else f"{text} {label}".strip()


def axis_unit_label(unit: str | None) -> str:
    if unit == "height_ratio":
        return "身高比"
    if unit == "mm":
        return "cm"
    if unit == "0-100 score":
        return "分"
    if unit == "0-100 risk":
        return "风险分"
    return UNIT_CN.get(unit or "", unit or "")


def has_axis_unit(text: str, unit: str | None) -> bool:
    label = axis_unit_label(unit)
    if not label:
        return True
    return label in text or (unit == "deg" and "°" in text)


def split_axis_number(text: str, unit: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip()
    label = axis_unit_label(unit)
    if unit == "height_ratio":
        match = re.search(r"[+-]?\d+(?:\.\d+)?%", text)
        if match:
            return match.group(0)
    if unit == "mm":
        match = re.search(r"[+-]?\d+(?:\.\d+)?", text)
        if match:
            return match.group(0)
    if label:
        text = text.replace(label, "").strip()
    if unit == "deg":
        text = text.replace("°", "").strip()
    return text


def axis_html(text: str, unit: str | None) -> str:
    if "unit-stack" in text or not axis_unit_label(unit):
        return text
    number = split_axis_number(text, unit)
    if unit == "deg":
        return f"{number}°"
    return (
        '<span class="unit-stack">'
        f'<span class="unit-number">{number}</span>'
        f'<span class="unit-label">{axis_unit_label(unit)}</span>'
        '</span>'
    )


def axis_text(text: str, unit: str | None) -> str:
    text = re.sub(r"<[^>]+>", "", text).strip()
    if unit == "deg":
        return f"{split_axis_number(text, unit)}°"
    if has_axis_unit(text, unit):
        return text
    return f"{split_axis_number(text, unit)} {axis_unit_label(unit)}".strip()


def metric_units() -> dict[str, str]:
    units: dict[str, str] = {}
    with METRICS_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = row.get("metric_key") or ""
            if key in PLAYER_CARD_METRIC_KEYS:
                units[key] = row.get("unit") or ""
    missing = [key for key in PLAYER_CARD_METRIC_KEYS if key not in units]
    if missing:
        raise RuntimeError(f"Missing metric units: {', '.join(missing)}")
    return units


def player_metric_values() -> dict[str, float]:
    values: dict[str, float] = {}
    with METRICS_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("sample_name") != PLAYER_SAMPLE_NAME:
                continue
            key = row.get("metric_key") or ""
            if key not in PLAYER_CARD_METRIC_KEYS:
                continue
            try:
                values[key] = float(row.get("value") or "")
            except ValueError:
                continue
    missing = [key for key in PLAYER_CARD_METRIC_KEYS if key not in values]
    if missing:
        raise RuntimeError(f"Missing player metric values: {', '.join(missing)}")
    return values


def peer_metric_bounds() -> dict[str, tuple[float, float]]:
    builder = load_builder_module()
    peer_rows = builder.read_peer_metrics(PEERS_DIR)
    bounds: dict[str, tuple[float, float]] = {}
    for key in PLAYER_CARD_METRIC_KEYS:
        peer_values = builder.peer_metric_values_for(key, peer_rows)
        values = [float(item["value"]) for item in peer_values]
        if values:
            bounds[key] = (min(values), max(values))
    return bounds


def marker_position(value: float, low: float, high: float) -> float:
    span = high - low
    if span <= 0:
        return 50.0
    normalized = max(0.0, min(100.0, (value - low) / span * 100.0))
    return 2.0 + normalized * 0.96


def coach_values() -> dict[str, str]:
    values: dict[str, str] = {}
    with METRICS_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("sample_name") != COACH_SAMPLE_NAME:
                continue
            key = row.get("metric_key") or ""
            if key in PLAYER_CARD_METRIC_KEYS:
                values[key] = fmt(row.get("value"), row.get("unit"))
    missing = [key for key in PLAYER_CARD_METRIC_KEYS if key not in values]
    if missing:
        raise RuntimeError(f"Missing coach metric values: {', '.join(missing)}")
    return values


def sample_metric_rows(sample_name: str) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with METRICS_PATH.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("sample_name") != sample_name:
                continue
            key = row.get("metric_key") or ""
            if key in PLAYER_CARD_METRIC_KEYS:
                rows[key] = row
    missing = [key for key in PLAYER_CARD_METRIC_KEYS if key not in rows]
    if missing:
        raise RuntimeError(f"Missing {sample_name} metric rows: {', '.join(missing)}")
    return rows


def update_player_batting_statuses(html: str) -> str:
    builder = load_builder_module()
    player_rows = sample_metric_rows(PLAYER_SAMPLE_NAME)
    coach_rows = sample_metric_rows(COACH_SAMPLE_NAME)
    pitch_start = html.index('<div class="section-title"><span class="mark"></span><h3>投球</h3></div>')
    before_pitch = html[:pitch_start]
    after_pitch = html[pitch_start:]
    articles = list(re.finditer(r'<article class="metric-card [^"]+">.*?</article>', before_pitch, flags=re.S))
    if len(articles) < len(PLAYER_CARD_METRIC_KEYS):
        raise RuntimeError(f"Expected at least {len(PLAYER_CARD_METRIC_KEYS)} batting player cards before pitching, found {len(articles)}")

    pieces: list[str] = []
    cursor = 0
    for match, key in zip(articles, PLAYER_CARD_METRIC_KEYS):
        pieces.append(before_pitch[cursor:match.start()])
        article = match.group(0)
        label, klass = builder.status_for(key, player_rows[key], coach_rows.get(key))
        article = re.sub(
            r'<article class="metric-card [^"]+">',
            f'<article class="metric-card {klass}">',
            article,
            count=1,
        )
        article = re.sub(
            r'<span class="badge [^"]+">[^<]+</span>',
            f'<span class="badge {klass}">{label}</span>',
            article,
            count=1,
        )
        pieces.append(article)
        cursor = match.end()
    pieces.append(before_pitch[cursor:])
    return "".join(pieces) + after_pitch


def apply_css(html: str) -> str:
    html = html.replace(
        ".metric-summary { min-width:0; display:grid; align-content:center; gap:12px; }",
        ".metric-summary { min-width:0; display:grid; align-content:center; gap:14px; }",
    )
    html = html.replace(
        ".two-column-metrics .metric-card { min-height:256px; padding:20px; grid-template-columns:minmax(88px,112px) minmax(104px,132px) minmax(0,1fr); gap:12px; }",
        ".two-column-metrics .metric-card { min-height:304px; padding:20px; grid-template-columns:minmax(100px,126px) minmax(104px,132px) minmax(0,1fr); gap:12px; }",
    )
    html = html.replace(
        "    .peer-dot.current-player { width:12px; height:12px; background:#101828; box-shadow:0 0 0 2px rgba(37,99,235,.28),0 0 0 1px rgba(16,24,40,.18); }\n",
        "    .peer-dot.current-player { z-index:4; width:16px; height:16px; background:#ef4444; border:3px solid #fff; box-shadow:0 0 0 2px #fff,0 0 0 6px color-mix(in srgb, var(--marker-color,#ef4444) 20%, transparent),0 0 0 1px rgba(16,24,40,.15); }\n",
    )
    html = re.sub(
        r"\n\s*\.two-column-metrics \.peer-range \{[^\n]*\}"
        r"\n\s*\.two-column-metrics \.peer-min,\s*\.two-column-metrics \.peer-max \{[^\n]*\}"
        r"\n\s*\.two-column-metrics \.peer-track \{[^\n]*\}",
        "",
        html,
    )
    if "    .two-column-metrics .peer-range {" not in html:
        html = html.replace(
            "    .two-column-metrics .metric-detail-en { font-size:11px; line-height:16px; }\n",
            (
                "    .two-column-metrics .metric-detail-en { font-size:11px; line-height:16px; }\n"
                "    .two-column-metrics .peer-range { grid-template-columns:max-content 34px minmax(52px,76px) 34px; gap:6px; max-width:100%; justify-self:start; }\n"
                "    .two-column-metrics .peer-min, .two-column-metrics .peer-max { font-size:11px; line-height:13px; white-space:normal; overflow-wrap:normal; word-break:keep-all; }\n"
                "    .two-column-metrics .peer-track { min-width:52px; max-width:76px; width:100%; }\n"
            ),
        )
    html = re.sub(r"\n\s*\.issue-metrics \.peer-dot(?:\[style\*=\"background:#ef4444\"\]|\.julian|\.current-player) \{[^\n]*\}", "", html)
    if "    .issue-metrics .peer-dot.current-player {" not in html:
        html = html.replace(
            "    .issue-metrics .compare-pill b { color:#667085; font-size:11px; line-height:14px; }\n",
            (
                "    .issue-metrics .compare-pill b { color:#667085; font-size:11px; line-height:14px; }\n"
                "    .issue-metrics .peer-dot.current-player { z-index:4; width:16px; height:16px; border:3px solid #fff; box-shadow:0 0 0 2px #fff,0 0 0 6px color-mix(in srgb, var(--marker-color,#ef4444) 20%, transparent),0 0 0 1px rgba(16,24,40,.15); }\n"
            ),
        )
    html = re.sub(r"\n\s*\.batting-coach-reference[^\n]*", "", html)
    if "    .pitch-coach-reference {" not in html:
        html = html.replace(
            "    .metric-value { font-size:38px; line-height:1; font-weight:800; margin:0; color:#000; overflow-wrap:anywhere; }\n",
            (
                "    .metric-value { font-size:38px; line-height:1; font-weight:800; margin:0; color:#000; overflow-wrap:anywhere; }\n"
                "    .pitch-coach-reference { display:inline-grid; gap:2px; justify-self:start; min-width:92px; border:1px solid #d0d5dd; border-radius:10px; padding:7px 10px; background:#fff; color:#344054; font-size:12px; line-height:16px; font-weight:800; }\n"
                "    .pitch-coach-reference b { color:#101828; font-size:12px; line-height:16px; font-weight:800; }\n"
                "    .pitch-coach-reference span { color:#667085; font-size:12px; line-height:15px; font-weight:800; }\n"
            ),
        )
    html = html.replace(
        "    .analyst-chart-grid { display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:18px; margin-top:18px; }",
        "    .analyst-chart-grid { display:grid; grid-template-columns:1fr; gap:18px; margin-top:18px; }",
    )
    html = re.sub(
        r"\n\s*/\* section-title-level-ui:start \*/.*?/\* section-title-level-ui:end \*/\n",
        "\n",
        html,
        flags=re.S,
    )
    html = html.replace(
        "\n  </style>",
        f"\n    /* section-title-level-ui:start */\n{SECTION_TITLE_LEVEL_CSS.rstrip()}\n    /* section-title-level-ui:end */\n  </style>",
    )
    return html


def update_article(article: str, value: str) -> str:
    article = re.sub(
        r'\n\s*<div class="(?:batting-coach-reference|pitch-coach-reference)"><b>阿楽教练</b><span>.*?</span></div>',
        "",
        article,
    )
    reference = f'<div class="pitch-coach-reference"><b>阿楽教练</b><span>{value}</span></div>'
    return re.sub(r'(<div class="peer-range[^"]*">)', rf"      {reference}\n      \1", article, count=1)


def update_player_batting_cards(html: str, values: dict[str, str]) -> str:
    pitch_start = html.index('<div class="section-title"><span class="mark"></span><h3>投球</h3></div>')
    before_pitch = html[:pitch_start]
    after_pitch = html[pitch_start:]
    articles = list(re.finditer(r'<article class="metric-card [^"]+">.*?</article>', before_pitch, flags=re.S))
    if len(articles) != len(PLAYER_CARD_METRIC_KEYS):
        raise RuntimeError(f"Expected {len(PLAYER_CARD_METRIC_KEYS)} batting player cards before pitching, found {len(articles)}")

    pieces: list[str] = []
    cursor = 0
    for match, key in zip(articles, PLAYER_CARD_METRIC_KEYS):
        pieces.append(before_pitch[cursor:match.start()])
        pieces.append(update_article(match.group(0), values[key]))
        cursor = match.end()
    pieces.append(before_pitch[cursor:])
    return "".join(pieces) + after_pitch


def update_legend_names(html: str) -> str:
    def key(name: str) -> str:
        normalized = name.strip().casefold().replace(" ", "")
        return PEER_KEY_ALIASES.get(normalized, normalized)

    def display(name: str) -> str:
        return PEER_DISPLAY_BY_NAME.get(key(name), name)

    def dot_replacement(match: re.Match[str]) -> str:
        prefix, old_color, between, raw_name, suffix = match.groups()
        return f"{prefix}{PEER_COLOR_BY_NAME.get(key(raw_name), old_color)}{between}{display(raw_name)}{suffix}"

    html = re.sub(
        r'(<span class="peer-dot[^>]*style="[^"]*background:)(#[0-9a-fA-F]+)([^"]*" title=")([^":]+)(:)',
        dot_replacement,
        html,
    )

    def legend_replacement(match: re.Match[str]) -> str:
        prefix, old_color, between, raw_name, suffix = match.groups()
        return f"{prefix}{PEER_COLOR_BY_NAME.get(key(raw_name), old_color)}{between}{display(raw_name)}{suffix}"

    html = re.sub(
        r'(<li><span class="legend-dot" style="background:)(#[0-9a-fA-F]+)(\"></span>)([^<]+)(</li>)',
        legend_replacement,
        html,
    )

    def compact_legend_replacement(match: re.Match[str]) -> str:
        prefix, old_color, between, raw_name, suffix = match.groups()
        return f"{prefix}{PEER_COLOR_BY_NAME.get(key(raw_name), old_color)}{between}{display(raw_name)}{suffix}"

    return re.sub(
        r'(<span class="peer-legend-item"><i class="peer-legend-dot" style="background:)(#[0-9a-fA-F]+)(\"></i>)([^<]+)(</span>)',
        compact_legend_replacement,
        html,
    )


def update_peer_range_labels(html: str) -> str:
    html = html.replace('<div class="peer-label">其他球员<br>表现区间</div>', '<div class="peer-label">乐风U9同组表现</div>')
    html = html.replace('<div class="peer-label"><span>乐风U9</span><span>同组表现</span></div>', '<div class="peer-label">乐风U9同组表现</div>')
    html = html.replace(
        'title="其他球员在同一训练评估标准下的表现区间"',
        'title="乐风U9同组在同一训练评估标准下的表现区间"',
    )
    return html


def update_coach_batting_main_player_markers(html: str) -> str:
    def replace_marker(match: re.Match[str]) -> str:
        style = re.sub(r"\s*;?\s*background:#ef4444\s*;?", ";", match.group(1)).strip()
        style = re.sub(r";{2,}", ";", style).strip(" ;")
        if style:
            style = f' style="{style}"'
        return f'<span class="peer-dot current-player"{style} title="黄炜宸:'

    return re.sub(
        r'<span class="peer-dot" style="([^"]*background:#ef4444[^"]*)" title="黄炜宸:',
        replace_marker,
        html,
    )


def format_percent(value: float) -> str:
    rounded = round(value * 100, 1)
    if abs(rounded) < 0.05:
        rounded = 0.0
    return f"{rounded:.0f}%" if rounded.is_integer() else f"{rounded:.1f}%"


def format_cm(value: float) -> str:
    rounded = round(value / 10, 1)
    if abs(rounded) < 0.05:
        rounded = 0.0
    return f"{rounded:.1f} cm"


def normalize_units_fragment(fragment: str) -> str:
    def height_ratio_repl(match: re.Match[str]) -> str:
        return f"{format_percent(float(match.group(1)))} 身高比"

    def mm_repl(match: re.Match[str]) -> str:
        text = format_cm(float(match.group(1)))
        return f"+{text}" if match.group(1).startswith("+") else text

    fragment = re.sub(r'([+-]?\d+(?:\.\d+)?)\s*身高比', height_ratio_repl, fragment)
    fragment = re.sub(r'([+-]?\d+(?:\.\d+)?)\s*mm\b', mm_repl, fragment)
    return fragment


def normalize_mm_peer_axis(article: str) -> str:
    def label_repl(match: re.Match[str]) -> str:
        inner = match.group(2)
        if "cm" in inner:
            return match.group(0)
        number_match = re.search(r"[+-]?\d+(?:\.\d+)?", re.sub(r"<[^>]+>", " ", inner))
        if not number_match:
            return match.group(0)
        return f'{match.group(1)}{format_cm(float(number_match.group(0)))}{match.group(3)}'

    def title_repl(match: re.Match[str]) -> str:
        if "cm" in match.group(2):
            return match.group(0)
        return f'title="{match.group(1)}: {format_cm(float(match.group(2)))}"'

    article = re.sub(r'(<div class="peer-(?:min|max)">)(.*?)(</div>)', label_repl, article, flags=re.S)
    article = re.sub(r'title="([^"]+):\s*([^"]*?[+-]?\d+(?:\.\d+)?(?:\s*cm)?)"', title_repl, article)
    return article


def normalize_batting_mm_peer_axes(html: str) -> str:
    for title in ("头部位移", "后肘高度差（掉肘）"):
        title_idx = html.find(f"<h4>{title}</h4>")
        if title_idx == -1:
            continue
        article_start = html.rfind('<article class="metric-card', 0, title_idx)
        article_end = html.find("</article>", title_idx)
        if article_start == -1 or article_end == -1:
            continue
        article_end += len("</article>")
        html = html[:article_start] + normalize_mm_peer_axis(html[article_start:article_end]) + html[article_end:]
    return html


def update_player_batting_peer_axis_units(html: str) -> str:
    units = metric_units()
    pitch_start = html.index('<div class="section-title"><span class="mark"></span><h3>投球</h3></div>')
    before_pitch = html[:pitch_start]
    after_pitch = html[pitch_start:]
    articles = list(re.finditer(r'<article class="metric-card [^"]+">.*?</article>', before_pitch, flags=re.S))
    if len(articles) < len(PLAYER_CARD_METRIC_KEYS):
        raise RuntimeError(f"Expected at least {len(PLAYER_CARD_METRIC_KEYS)} batting player cards before pitching, found {len(articles)}")

    pieces: list[str] = []
    cursor = 0
    for match, key in zip(articles, PLAYER_CARD_METRIC_KEYS):
        pieces.append(before_pitch[cursor:match.start()])
        article = match.group(0)
        unit = units[key]

        def label_repl(label_match: re.Match[str]) -> str:
            return f'{label_match.group(1)}{axis_html(label_match.group(2), unit)}{label_match.group(3)}'

        def title_repl(title_match: re.Match[str]) -> str:
            return f'title="{title_match.group(1)}: {axis_text(title_match.group(2), unit)}"'

        article = re.sub(r'(<div class="peer-(?:min|max)">)(.*?)(</div>)', label_repl, article, flags=re.S)
        article = re.sub(r'title="([^"]+):\s*([^"]*?\d(?:\.\d+)?(?:%| °| cm|分|风险分| 身高比)?)"', title_repl, article)
        pieces.append(article)
        cursor = match.end()
    pieces.append(before_pitch[cursor:])
    return "".join(pieces) + after_pitch


def update_player_batting_marker_positions(html: str) -> str:
    values = player_metric_values()
    bounds = peer_metric_bounds()
    pitch_start = html.index('<div class="section-title"><span class="mark"></span><h3>投球</h3></div>')
    before_pitch = html[:pitch_start]
    after_pitch = html[pitch_start:]
    articles = list(re.finditer(r'<article class="metric-card [^"]+">.*?</article>', before_pitch, flags=re.S))
    if len(articles) < len(PLAYER_CARD_METRIC_KEYS):
        raise RuntimeError(f"Expected at least {len(PLAYER_CARD_METRIC_KEYS)} batting player cards before pitching, found {len(articles)}")

    pieces: list[str] = []
    cursor = 0
    for match, key in zip(articles, PLAYER_CARD_METRIC_KEYS):
        pieces.append(before_pitch[cursor:match.start()])
        article = match.group(0)
        if key in bounds:
            low, high = bounds[key]
            pos = marker_position(values[key], low, high)
            article = re.sub(
                r'(<span class="peer-dot current-player" style="left:)[^%;]+%(;\s*top:50\.0%" title=")',
                rf"\g<1>{pos:.2f}%\2",
                article,
                count=1,
            )
        pieces.append(article)
        cursor = match.end()
    pieces.append(before_pitch[cursor:])
    return "".join(pieces) + after_pitch


def normalize_unit_stacks(html: str) -> str:
    units = ("身高比", "km/h", "cm", "°", "风险分", "分")
    for unit in units:
        html = re.sub(
            rf'(<span class="unit-number">)([^<]*?)\s*{re.escape(unit)}(</span><span class="unit-label">{re.escape(unit)}</span>)',
            r"\1\2\3",
            html,
        )
    return html


def normalize_angle_axis_units(html: str) -> str:
    return re.sub(
        r'<span class="unit-stack"><span class="unit-number">([^<]+)</span><span class="unit-label">°</span></span>',
        r"\1°",
        html,
    )


def restore_height_ratio_unit(article: str) -> str:
    style_attrs: list[str] = []

    def stash_style(match: re.Match[str]) -> str:
        style = match.group(0).replace("% 身高比", "%")
        style_attrs.append(style)
        return f"__STYLE_ATTR_{len(style_attrs) - 1}__"

    article = re.sub(r'style="[^"]*"', stash_style, article)
    article = re.sub(r'([+-]?\d+(?:\.\d+)?%)\s*(?!\s*身高比)', r'\1 身高比', article)
    for idx, style in enumerate(style_attrs):
        article = article.replace(f"__STYLE_ATTR_{idx}__", style)
    return article


def restore_batting_height_ratio_units(html: str) -> str:
    for title in ("重心高度", "握棒手高度"):
        title_idx = html.find(f"<h4>{title}</h4>")
        if title_idx == -1:
            continue
        article_start = html.rfind('<article class="metric-card', 0, title_idx)
        article_end = html.find("</article>", title_idx)
        if article_start == -1 or article_end == -1:
            continue
        article_end += len("</article>")
        html = html[:article_start] + restore_height_ratio_unit(html[article_start:article_end]) + html[article_end:]
    return html


def update_between(html: str, start: str, end: str, update: callable[[str], str]) -> str:
    start_idx = html.index(start)
    end_idx = html.index(end, start_idx + len(start))
    return html[:start_idx] + update(html[start_idx:end_idx]) + html[end_idx:]


def find_first_section_title(html: str, titles: tuple[str, ...]) -> int:
    candidates = [
        html.find(f'<div class="section-title"><span class="mark"></span><h2>{title}</h2></div>')
        for title in titles
    ]
    candidates = [idx for idx in candidates if idx != -1]
    if not candidates:
        raise ValueError(f"None of the section titles were found: {', '.join(titles)}")
    return min(candidates)


def update_batting_units(html: str) -> str:
    html = update_between(
        html,
        '<div class="section-title"><span class="mark"></span><h3>打击</h3></div>',
        '<div class="section-title"><span class="mark"></span><h3>投球</h3></div>',
        normalize_units_fragment,
    )
    coach_start = find_first_section_title(html, ("阿楽教练视角", "教练视角"))
    batting_start = html.index('<div class="section-title"><span class="mark"></span><h3>打击</h3></div>', coach_start)
    pitching_start = html.index('<div class="section-title"><span class="mark"></span><h3>投球</h3></div>', batting_start)
    html = html[:batting_start] + normalize_units_fragment(html[batting_start:pitching_start]) + html[pitching_start:]
    html = normalize_batting_mm_peer_axes(html)
    return restore_batting_height_ratio_units(html)


def load_builder_module():
    spec = importlib.util.spec_from_file_location("julian_coach_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load builder script: {BUILDER_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def regenerate_research_assets() -> None:
    builder = load_builder_module()
    builder.DEFAULT_POSE3D = POSE3D_PATH
    builder.ACTIVE_PLAYER_SAMPLE = PLAYER_SAMPLE_NAME
    builder.ACTIVE_COACH_SAMPLE = COACH_SAMPLE_NAME
    builder.ACTIVE_PLAYER_SLUG = PLAYER_SLUG
    builder.ACTIVE_PLAYER_LABEL = PLAYER_LABEL
    rows = builder.read_csv(METRICS_PATH)
    by_sample: dict[str, dict[str, dict[str, str]]] = {}
    for row in rows:
        by_sample.setdefault(row["sample_name"], {})[row["metric_key"]] = row
    builder.make_research_assets(by_sample[PLAYER_SAMPLE_NAME], by_sample[COACH_SAMPLE_NAME], REPORT_DIR)


def versioned_asset(path: str) -> str:
    asset = REPORT_DIR / path
    return f"{path}?v={int(asset.stat().st_mtime)}"


def update_research_section(html: str) -> str:
    player = PLAYER_LABEL
    html = html.replace(
        '<p class="copy-cn">研究者模块把准备、髋部打开、躯干旋转、手腕控制和球棒速度放在同一条线上，便于检查力量是否顺着身体释放到球棒。</p>',
        f'<p class="copy-cn">从本次曲线看，{player} 的挥棒输出主要集中在击球窗口附近：髋部和躯干先建立旋转，手腕随后出现较高峰值，球棒速度在接近击球时释放。后续研究者复盘时，重点不是单个峰值越大越好，而是观察峰值顺序是否稳定、手腕峰值是否过早，以及球棒速度能否在击球窗口附近集中出现。</p>',
    )
    html = html.replace(
        '<p class="copy-en">This researcher view puts preparation, hip opening, trunk rotation, wrist control, and bat speed into one sequence to show whether the swing releases smoothly into the bat.</p>',
        f'<p class="copy-en">The curves suggest that {player} releases most of the swing output near the contact window: the hips and trunk build the rotation first, the wrist peaks later, and bat speed rises close to contact. For review, the key question is not whether one peak is large, but whether the sequence is repeatable, whether the wrist peaks too early, and whether bat speed is concentrated around contact.</p>',
    )
    html = html.replace(
        '<p class="analyst-chart-copy">怎么看：速度曲线用来比较 Julian 和阿楽教练的挥棒加速节奏。重点看速度最高点是否靠近击球窗口，以及速度是否集中释放。</p>',
        f'<p class="analyst-chart-copy">怎么看：速度曲线现在标出 {player} 和阿楽教练各自峰值对应的时间与速度。重点看 {player} 的最高速度是否靠近击球窗口，以及峰值是否比教练示范更早或更晚。</p>',
    )
    html = html.replace(
        "<p class=\"analyst-chart-copy\">How to read it: the speed graph compares Julian's swing rhythm with the 阿楽教练 reference. Look for whether the fastest moment happens near contact and whether speed is released in one clear burst.</p>",
        f"<p class=\"analyst-chart-copy\">How to read it: the speed chart now labels each peak with its time and speed. Check whether {player}'s fastest moment is close to contact and whether that peak arrives earlier or later than the coach reference.</p>",
    )
    html = html.replace(
        '<p class="analyst-chart-copy">怎么看：角度曲线用来比较 Julian 和阿楽教练的球棒方向变化。重点不是角度越大越好，而是击球窗口前后方向是否稳定。</p>',
        f'<p class="analyst-chart-copy">怎么看：角度曲线现在标出 {player} 和阿楽教练各自峰值对应的时间与角度。重点看击球窗口前后球棒方向是否稳定，而不是追求更大的角度峰值。</p>',
    )
    html = html.replace(
        '<p class="analyst-chart-copy">How to read it: the angle graph compares how the bat direction changes for Julian and the 阿楽教练 reference. Around contact, steadiness matters more than a bigger number.</p>',
        '<p class="analyst-chart-copy">How to read it: the angle chart now labels each peak with its time and value. Around contact, the useful signal is bat-direction stability rather than simply producing a larger angle peak.</p>',
    )
    # Rewrite reports already polished with the former Julian-only researcher
    # copy, without touching Julian's legitimate peer-legend entry.
    html = re.sub(
        r'(<p class="copy-cn">从本次曲线看，)[^<]*?( 的挥棒输出)',
        rf'\g<1>{player}\2',
        html,
    )
    html = re.sub(
        r'(The curves suggest that )[^ ]+( releases most of the swing output)',
        rf'\g<1>{player}\2',
        html,
    )
    html = re.sub(r'(速度曲线现在标出 )[^ 和<]+( 和阿楽教练)', rf'\g<1>{player}\2', html)
    html = re.sub(r'(重点看 )[^ 的<]+( 的最高速度)', rf'\g<1>{player}\2', html)
    html = re.sub(r"(Check whether )[^']+('s fastest moment)", rf'\g<1>{player}\2', html)
    html = re.sub(r'(角度曲线现在标出 )[^ 和<]+( 和阿楽教练)', rf'\g<1>{player}\2', html)
    for path in (
        f"assets/kinetic_chain/{PLAYER_SLUG}_batting_kinetic_chain_flow.png",
        f"assets/kinetic_chain/{PLAYER_SLUG}_batting_kinetic_speed_time_curve.png",
        f"assets/analyst_charts/{PLAYER_SLUG}_batting_bat1_speed_time_curve.png",
        f"assets/analyst_charts/{PLAYER_SLUG}_batting_bat_axis_angle_time_curve.png",
    ):
        if (REPORT_DIR / path).exists():
            html = re.sub(rf'{re.escape(path)}\?v=\d+', versioned_asset(path), html)
    # The final polish also receives imported pitching sections. Keep all
    # player-facing researcher copy free of implementation jargon.
    for old, new in {
        "球员和 Coach": "球员和教练",
        "球员与 Coach": "球员与教练",
        "C3D骨架动画": "动作重建动画",
        "C3D/Vicon": "本次动作记录",
        "C3D marker": "本次动作变化",
        "C3D 文件": "本次动作记录",
        "C3D数据": "本次动作记录",
        "Vicon markers": "动作变化",
        "main release markers": "key release positions",
        "手部 marker": "手部位置",
        "球 marker": "球的位置",
    }.items():
        html = html.replace(old, new)
    return re.sub(
        r"曲线来自[^<。]*?(?:C3D|marker)[^<。]*?逐帧计算。",
        "曲线展示本次投球过程中各项动作随时间的变化。",
        html,
        flags=re.IGNORECASE,
    )


def update_bat_speed_copy(html: str) -> str:
    html = html.replace(
        "击球附近的球棒速度还有提升空间，重点不是单纯加快手，而是让下肢、躯干和手臂的发力衔接更顺。本次记录为 61.1 km/h；阿楽教练示范为 93.9 km/h，相差 -32.8 km/h。",
        "击球附近的球棒速度已经处在 U8-U10 调研参考范围内，后续重点是继续向区间上沿提升，让下肢、躯干和手臂的发力衔接更顺。本次记录为 61.1 km/h；阿楽教练示范为 93.9 km/h，相差 -32.8 km/h。",
    )
    html = html.replace(
        "Bat speed can improve as the lower body, trunk, and arms connect more smoothly, with the body leading before the hands accelerate.",
        "Bat speed is within the U8-U10 reference range, with room to move toward the upper end as the lower body, trunk, and arms connect more smoothly.",
    )
    return html


def main() -> None:
    global REPORT_DIR, HTML_PATH, METRICS_PATH, POSE3D_PATH, PEERS_DIR, BUILDER_PATH
    global PLAYER_SAMPLE_NAME, COACH_SAMPLE_NAME, PLAYER_SLUG, PLAYER_LABEL

    parser = argparse.ArgumentParser(
        description="Apply the final vicon_2026_julian_coach 4 schema polish to a generated metrics section."
    )
    parser.add_argument("--report-dir", type=Path, default=REPORT_DIR)
    parser.add_argument("--html", type=Path, default=None)
    parser.add_argument("--metrics", type=Path, default=None)
    parser.add_argument("--pose3d", type=Path, default=None)
    parser.add_argument("--peers", type=Path, default=PEERS_DIR)
    parser.add_argument("--builder", type=Path, default=BUILDER_PATH)
    parser.add_argument("--player-sample-name", default=PLAYER_SAMPLE_NAME)
    parser.add_argument("--coach-sample-name", default=COACH_SAMPLE_NAME)
    parser.add_argument("--player-slug", default=PLAYER_SLUG)
    parser.add_argument("--player-label", default=PLAYER_LABEL)
    args = parser.parse_args()

    REPORT_DIR = args.report_dir
    HTML_PATH = args.html or REPORT_DIR / "julian_coach_metrics_section.html"
    METRICS_PATH = args.metrics or REPORT_DIR / "batting_dashboard_metrics.csv"
    POSE3D_PATH = args.pose3d or REPORT_DIR / "vicon_2026_pose3d.csv"
    PEERS_DIR = args.peers
    BUILDER_PATH = args.builder
    PLAYER_SAMPLE_NAME = args.player_sample_name
    COACH_SAMPLE_NAME = args.coach_sample_name
    PLAYER_SLUG = args.player_slug
    PLAYER_LABEL = args.player_label

    regenerate_research_assets()
    html = HTML_PATH.read_text(encoding="utf-8")
    html = apply_css(html)
    html = update_player_batting_cards(html, coach_values())
    html = update_legend_names(html)
    html = update_peer_range_labels(html)
    html = update_coach_batting_main_player_markers(html)
    html = update_batting_units(html)
    html = update_player_batting_statuses(html)
    html = update_player_batting_peer_axis_units(html)
    html = update_player_batting_marker_positions(html)
    html = normalize_unit_stacks(html)
    html = normalize_angle_axis_units(html)
    html = update_research_section(html)
    html = update_bat_speed_copy(html)
    HTML_PATH.write_text(html, encoding="utf-8")
    print(HTML_PATH)


if __name__ == "__main__":
    main()
