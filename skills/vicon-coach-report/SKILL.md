---
name: vicon-coach-report
description: Build, repair, standardize, or regenerate the config-driven Vicon baseball player-vs-coach report (batting, pitching, or combined). Use for a new athlete’s report, a change to report metrics/cards/researcher charts, validated 2D/Vicon alignment, or refreshing a combined HTML/XLSX deliverable without overwriting a reference athlete’s report.
---

# Vicon Coach Report

Use the repository’s public report entry, not individual HTML builders, for a complete deliverable. Read `references/report-format.md` before changing a report contract, report inputs, researcher assets, or validation rules.

## Scope and safety

- Keep each non-reference athlete in `reports/vicon_2026_<player_slug>_coach/`; never overwrite another athlete’s report directory.
- Build pitching separately in `reports/pitching_<player_slug>_coach/`. The final batting stage copies it into the combined report as `pitch_assets/`.
- Treat the batting config’s reviewed `video_capture_fps` and `video_event_frame` as required report inputs. Do not infer them during report generation.
- Use C3D-derived values for displayed biomechanics metrics. A 2D pose may locate visual overlays but must not replace the displayed Vicon value.
- Keep hand speed in `km/h`; it is a hand-marker proxy, not ball speed. State proxy/event limitations rather than making medical claims.

## Configure a new athlete

1. Copy `configs/final_report.example.json` and `configs/default_report_pipeline.json` to player-specific JSON files.
2. In the batting config, set `report_dir`, `pitch_report`, player/coach sample names, the batting C3D/video/model paths, reviewed video timing, and `xlsx_out_dir`.
3. Create a pitching manifest containing one `role: student` and one `key: coach`; C3D paths are resolved relative to that manifest.
4. In the final config, reference the batting config and set pitching `manifest`, `template_dir`, and a separate `out_dir`. Add `pitching.alignment` only when its raw pitch video and reviewed event frame are available.
5. Confirm all paths resolve before a full run.

The Bryan trio is a working example:

```text
configs/generated/bryan_final_report.json
configs/generated/bryan_coach_batting_pipeline.json
configs/generated/bryan_coach_pitching_manifest.json
```

## Public executions

Run from `baseball-report-generation/` with the project virtual environment:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py final \
  --config configs/<player_slug>_final_report.json
```

Use `pitching` to rebuild only `reports/pitching_<player_slug>_coach/`; use `batting` only after a current pitching `index.html` exists. Add `--skip-pitching-alignment` only when no validated pitching 2D input is configured. Do not use low-level builders as a substitute for a complete report run.

The final execution is ordered as:

```text
pitching HTML/assets + researcher charts
→ batting C3D tables and 3D assets
→ batting events, reviewed 2D/Vicon alignment, overlays and annotations
→ batting researcher charts + merged HTML + XLSX
```

## Targeted rebuilds

Use these only after the relevant upstream artifacts exist:

- Change a pitching metric/card/researcher chart: run `report_cli.py pitching`, then `report_cli.py batting` (or the final entry) to refresh the embedded `pitch_assets/`.
- Change batting HTML/card copy or legend order: run `scripts/run_batting_report_pipeline.py --config <batting-config> --pitch-report <pitch-index>`; retain the normal HTML-polish and XLSX stages.
- Change 2D geometry or a reviewed event frame: run the final entry so alignment, overlay, geometry annotations, HTML, and XLSX remain consistent.
- Use `--skip-c3d`, `--skip-reconstruction`, `--skip-2d`, or `--skip-illustrations` only for a deliberate partial rebuild with known-good retained inputs. Never use partial flags to conceal a missing required artifact.

## Validate before handoff

Verify the combined HTML, pitching HTML, batting metrics CSV, alignment summary/2D geometry outputs when configured, all researcher PNGs, and the XLSX are non-empty. Confirm relative `pitch_assets/` links resolve in the combined report. Inspect researcher charts visually when labels, fonts, axes, or layout change.

For player and coach cards, require Chinese metric names, matching English metric subtitles, `乐风U9同组表现` group labels, and the shared peer legend order/colors. Search generated pitching HTML for stale labels (`m/s`, `hand_speed_mps`, `手臂槽位`, `右腿蹬地伸展线索`, `同组区间`) before delivery.

Commit only source/config changes for the task; keep generated reports and local runtime links out of commits unless explicitly requested.
