# Report commands

`report_cli.py` is the only public report-generation entry. Everything else in
this directory is called by that entry or is an isolated diagnostic utility.

## Supported executions

Run from the repository root with a player-specific final config.

| Goal | Command | Contract |
| --- | --- | --- |
| Build the complete pitching + batting deliverable | `python scripts/report_cli.py final --config configs/<player_slug>_final_report.json` | Default and required handoff path. Builds pitching first, then embeds its current HTML/assets in batting. |
| Build/retry pitching | `python scripts/report_cli.py pitching --config configs/<player_slug>_final_report.json` | Produces `reports/pitching_<player_slug>_coach/index.html`, researcher figures, and configured pitching 2D QA. |
| Build/retry batting | `python scripts/report_cli.py batting --config configs/<player_slug>_final_report.json` | Requires the current pitching `index.html`; creates the combined HTML, copied `pitch_assets/`, and XLSX. |

Use `final` after any change to timings, shared report copy, template assets, or
both disciplines. Use `pitching` then `batting` only to retry a known isolated
stage. `--skip-pitching-alignment` is valid only when no validated pitching 2D
input is configured.

## Public pipeline

```text
pitching HTML + metrics + researcher figures (+ configured pitching 2D QA)
  → batting C3D metrics + 3D assets
  → reviewed batting 2D/Vicon alignment + overlays
  → batting researcher figures + merged HTML + XLSX
```

The final config owns the dependency boundary. Keep pitching output in
`reports/pitching_<player_slug>_coach/` and combined output in
`reports/vicon_2026_<player_slug>_coach/`; batting copies the current pitching
assets into `pitch_assets/` while merging.

## Internal scripts

`run_batting_report_pipeline.py` and the builders below it are internal
orchestration/implementation layers. Pitching builders, chart generators, and
2D alignment helpers are likewise internal. Run them only for focused
diagnosis after the public execution has established the required upstream
artifacts; always finish by rerunning the appropriate `report_cli.py`
execution.

`export_report_from_html.mjs` is an optional post-generation HTML-to-PDF/PPTX
exporter, not a report builder. Use `--help` for its explicit input and output
arguments.

For configuration, metrics, assets, and validation requirements, see
[`../skills/vicon-coach-report/SKILL.md`](../skills/vicon-coach-report/SKILL.md)
and [`../skills/vicon-coach-report/references/report-format.md`](../skills/vicon-coach-report/references/report-format.md).
