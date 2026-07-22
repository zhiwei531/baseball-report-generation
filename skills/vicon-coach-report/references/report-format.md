# Vicon Coach Metrics Report Format

## Page Structure

```text
球员综合表现报告
  球员视角
    打击
    投球
  教练视角
    打击
    投球
  研究者视角
    打击：动力链与时间曲线
    投球：动力链与时间曲线
```

Keep Chinese as the primary language. Use English subtitles where the template provides them. Use the same Vicon-derived data for player explanation, coach comparison, and researcher evidence.

## Current Entry Contract

Use the config-driven public CLI:

```bash
PYTHONPATH=src python -m baseball_report final \
  --config configs/generated/<player_slug>_final_report.json
```

`final` rebuilds pitching first, generates its researcher charts, then runs batting and embeds the pitching report/assets. `pitching` and `batting` are retry scopes; individual builders are debugging tools, not complete report entries.

Run `final --dry-run` before a new or changed configuration. The legacy
`scripts/report_cli.py` entry remains a compatibility implementation but must
not be used in new automation. The package CLI's `--help` output is the
authoritative option list; low-level partial-build flags are not public CLI
options.

The final config references a batting pipeline config plus a pitching manifest/template/output. The batting config must supply reviewed 2D video timing (`video_capture_fps`, `video_event_frame`) when 2D alignment is enabled. Keep the pitching output separate from the combined report output.

Use the latest Git-tracked `reports/pitching_bryan_coach/index.html` as the
canonical pitching DOM template. Never use a dated snapshot or another
athlete's generated assets as the template source. For a clean build, generate
all athlete assets into distinct empty output directories.

## Metric Card Contract

Each card requires a Chinese label, English label, status badge, main value/unit, comparison range, Chinese/English interpretation, and metric illustration.

For pitching player and coach cards, use `乐风U9同组表现` as the peer-range caption. Fix the shared eight-player legend order and colors: Bryan blue (`#2563eb`), 席启源 green (`#16a34a`), 姚槿宏 orange (`#f97316`), 杜子墨 purple (`#a855f7`), Julian red (`#ef4444`), 费怡然 teal (`#0891b2`), 桑禹诚 yellow (`#ca8a04`), 缪炜昱 gray-black (`#344054`). Do not reorder these entries from input-row order; treat `Brandon` as 缪炜昱's alias, not a ninth player.

When a metric card contains the three white comparison pills, label them
`乐风U9均值`, `阿楽教练参考`, and `球员<实际球员名>` (for example,
`球员Bryan`). Never leave a generic `球员` or a hard-coded Julian name.

Pitching values normalized by body height must retain that context in every
player/coach card, comparison pill, range endpoint, issue summary, and event
overlay: render `79.4%身高比`, never a bare `79.4%`. The four 3D
reconstruction captions must likewise identify `球员<实际球员名>` or `阿楽教练`;
do not show generic labels or template-editing instructions.
For progress-range endpoints, put the numeric percentage on the first line
and `身高比` on the second line, so the labels never overlap the slider.

Researcher chart captions and nearby explanatory copy must use coaching
language. Do not expose `C3D`, `marker`, or other implementation provenance in
Chinese or English report text; describe the observed action, timing, and
movement sequence instead. In Chinese copy, call the comparison role `教练`,
not `Coach`; English copy may use lowercase `coach` where needed.

## Required Batting Inputs

The long-form metrics CSV must include target-player and coach rows, plus:

```text
trial_id, sample_name, athlete, action_type, source_file, module,
metric_name_zh, metric_key, value, unit, aggregation, event_name,
event_rule, event_frame, event_frames, points_used, formula,
components_json, notes
```

## Output Contract

```text
reports/vicon_2026_<player_slug>_coach/
  batting_dashboard_metrics.csv
  batting_dashboard_metrics_wide.csv
  <player_slug>_coach_metrics_section.html
  alignment_2d/                         # when batting 2D inputs are configured
  assets/
    analyst_charts/
    kinetic_chain/
    vicon_2d_geometry_annotations/
    vicon_reconstruction_annotated/
    vicon_reconstruction_events/
  pitch_assets/                         # copied from pitching report on merge

reports/pitching_<player_slug>_coach/
  index.html
  pitch_metrics_summary.json
  assets/kinetic_chain/<player_slug>_pitch_kinetic_chain_flow.png
  assets/kinetic_chain/<player_slug>_kinetic_chain_time_curves.png
  assets/analyst_charts/<player_slug>_pitch_angle_time_curve.png
  assets/analyst_charts/<player_slug>_pitch_speed_time_curve.png
```

The pitching flow is rear leg → pelvis → trunk → throwing arm → hand. Hand speed is reported in `km/h` and is a hand-marker proxy, not ball speed.
