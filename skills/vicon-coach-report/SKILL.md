---
name: vicon-coach-report
description: Build, repair, standardize, validate, or regenerate the config-driven Vicon baseball player-vs-coach report through the packaged baseball_report CLI (batting, pitching, or combined). Use for a new athlete report, report metrics/cards/researcher charts, validated 2D/Vicon alignment, ReportData/HTML/XLSX delivery, or a clean rebuild that must not reuse another athlete's assets.
---

# Vicon Coach Report

Use `PYTHONPATH=src python -m baseball_report` as the public report-generation
entry. Treat `scripts/report_cli.py` as a compatibility implementation, not a
command for new automation. Read `references/report-format.md` before changing
a report contract, report inputs, researcher assets, or validation rules.

## Canonical workspace

Run report generation **only** from the maintained
`baseball-report-generation/` directory. Never use a dated snapshot directory
such as `baseball-report-generation-YYYYMMDD`: those folders can contain stale
configs, templates, and outputs. Before creating configs, running the CLI, or
validating a delivery, confirm the working directory ends in
`baseball-report-generation` and contains `src/baseball_report/`.

## Scope and safety

- Keep each non-reference athlete in `reports/vicon_2026_<player_slug>_coach/`; never overwrite another athlete’s report directory.
- Build pitching separately in `reports/pitching_<player_slug>_coach/`. The final batting stage copies it into the combined report as `pitch_assets/`.
- Treat the batting config’s reviewed `video_capture_fps` and `video_event_frame` as required report inputs. Do not infer them during report generation.
- Use C3D-derived values for displayed biomechanics metrics. A 2D pose may locate visual overlays but must not replace the displayed Vicon value.
- Keep hand speed in `km/h`; it is a hand-marker proxy, not ball speed. State proxy/event limitations rather than making medical claims.
- Use the latest Git-tracked `reports/pitching_bryan_coach/index.html` as the canonical pitching DOM template. Do not substitute a generated snapshot or copy assets from an earlier athlete report.
- For a clean rebuild, write to athlete-specific empty output directories and regenerate assets from configured source inputs. Existing outputs may be retained only for an intentional retry whose required upstream artifacts are known and validated.

## Configure a new athlete

1. Copy `configs/final_report.example.json` and its referenced batting config to player-specific JSON files.
2. In the batting config, set `report_dir`, player/coach sample names, batting C3D/video/model paths, reviewed video timing, and `xlsx_out_dir`.
3. Create a pitching manifest with the report subject as the first `role: student`, every available same-group peer as additional `role: student` rows, and exactly one `key: coach`; C3D paths resolve relative to that manifest. Peer rows are required when the report displays `乐风U9同组表现`: without them, group mean/range/comparison dots are not a valid team benchmark.
4. In the final config, reference the batting config and set pitching `manifest`, `template_dir`, and a separate `out_dir`. Add `pitching.alignment` only with matching raw pitch video/C3D/model plus reviewed FPS and release frame.
5. Confirm all paths resolve and that the two output directories are distinct before a full run.

For batting group comparisons, ensure every peer's batting metrics are present
in `outputs/batting_metrics_excel/all_players` before the final run.

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
PYTHONPATH=src ../baseball-analysis/.venv312/bin/python -m baseball_report final \
  --config configs/generated/<player_slug>_final_report.json
```

Run the same command with `--dry-run` first for a new or changed config. Review
resolved source, manifest, template, model, and output paths plus overwrite or
compatibility warnings before generating files.

Use `pitching` to rebuild only `reports/pitching_<player_slug>_coach/`; use
`batting` only after a current pitching `index.html` exists. Add
`--skip-pitching-alignment` only when no validated pitching 2D input is
configured. Do not invoke low-level builders as a report entry.

The final execution is ordered as:

```text
pitching HTML/assets + researcher charts
→ batting C3D tables and 3D assets
→ batting events, reviewed 2D/Vicon alignment, overlays and annotations
→ batting researcher charts + merged HTML + XLSX
```

## Targeted rebuilds

Use these only after the relevant upstream artifacts exist:

- Change a pitching metric/card/researcher chart: run `python -m baseball_report pitching`, then `python -m baseball_report batting` (or `final`) to refresh embedded `pitch_assets/`.
- Change batting HTML/card copy or legend order: run `python -m baseball_report batting` after a current pitching build; use `final` if any shared assets or inputs changed.
- Change 2D geometry or a reviewed event frame: run `python -m baseball_report final` so alignment, overlay, geometry annotations, HTML, and XLSX remain consistent.
- Do not pass internal pipeline flags such as `--skip-c3d`, `--skip-reconstruction`, `--skip-2d`, or `--skip-illustrations` to the package CLI; they are not public options. If focused diagnosis requires a low-level script, finish with the appropriate package command before handoff.

## Validate before handoff

Verify the combined HTML, pitching HTML, batting metrics CSV, alignment
summary/2D geometry outputs when configured, all researcher PNGs, and XLSX are
non-empty. Confirm relative `pitch_assets/` links resolve in the combined
report. Inspect researcher charts visually when labels, fonts, axes, or layout
change. Confirm every pitching researcher asset uses the active player slug;
never retain a prior athlete's flow, timing, angle, or speed curve.

Validate the stable analysis/report contract before handoff:

```bash
PYTHONPATH=src ../baseball-analysis/.venv312/bin/python -m baseball_report \
  validate-report --input reports/vicon_2026_<player_slug>_coach/analysis_report_data.json
```

Confirm the validator reports the expected subject, motions, metrics, sections,
and assets. Check that every relative HTML asset reference exists and that no
absolute path or prior-athlete slug remains in the generated deliverable.

For player and coach cards, require Chinese metric names, matching English metric subtitles, `乐风U9同组表现` group labels, and the shared peer legend order/colors. Search generated pitching HTML for stale labels (`m/s`, `hand_speed_mps`, `手臂槽位`, `右腿蹬地伸展线索`, `同组区间`) before delivery.

Commit only source/config changes for the task; keep generated reports and local runtime links out of commits unless explicitly requested.
