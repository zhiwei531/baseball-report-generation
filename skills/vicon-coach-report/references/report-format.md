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
python scripts/report_cli.py final --config configs/<player_slug>_final_report.json
```

`final` rebuilds pitching first, generates its researcher charts, then runs batting and embeds the pitching report/assets. `pitching` and `batting` are retry scopes; individual builders are debugging tools, not complete report entries.

The final config references a batting pipeline config plus a pitching manifest/template/output. The batting config must supply reviewed 2D video timing (`video_capture_fps`, `video_event_frame`) when 2D alignment is enabled. Keep the pitching output separate from the combined report output.

## Metric Card Contract

Each card requires a Chinese label, English label, status badge, main value/unit, comparison range, Chinese/English interpretation, and metric illustration.

For pitching player and coach cards, use `乐风U9同组表现` as the peer-range caption. Use the shared eight-player legend order/colors: Bryan blue, 席启源 green, 姚槿宏 orange, 杜子墨 purple, Julian red, 费怡然 teal, 桑禹诚 yellow, 缪炜昱 pink.

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
