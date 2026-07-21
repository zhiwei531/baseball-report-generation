# Compatibility scripts

New callers should use the package entry documented in
[`../src/README.md`](../src/README.md):

```bash
PYTHONPATH=src python -m baseball_report <command> [options]
```

`report_cli.py` remains a supported compatibility target for existing callers.
The package CLI currently delegates characterized orchestration to it, so its
behavior and exit codes remain protected during migration. Everything else in
this directory is an internal builder, adapter, orchestration layer, or
isolated diagnostic utility unless explicitly documented otherwise.

## Supported executions

Run from the repository root with a player-specific final config.

| Goal | Preferred package command | Legacy compatibility command |
| --- | --- | --- |
| Build the complete pitching + batting deliverable | `PYTHONPATH=src python -m baseball_report final --config configs/<player_slug>_final_report.json` | `python scripts/report_cli.py final --config configs/<player_slug>_final_report.json` |
| Build/retry pitching | `PYTHONPATH=src python -m baseball_report pitching --config configs/<player_slug>_final_report.json` | `python scripts/report_cli.py pitching --config configs/<player_slug>_final_report.json` |
| Build/retry batting | `PYTHONPATH=src python -m baseball_report batting --config configs/<player_slug>_final_report.json` | `python scripts/report_cli.py batting --config configs/<player_slug>_final_report.json` |

`final` is the default handoff path and builds pitching first. `pitching`
produces the pitching HTML, metrics, researcher figures, and configured 2D QA.
`batting` requires the current pitching `index.html` and produces the combined
HTML, copied `pitch_assets/`, and XLSX.

Add `--dry-run` to any execution to resolve and validate its config without
creating directories or running a producer. The summary includes the final,
batting, manifest, template, C3D/video/model, and output paths plus any
compatibility or overwrite warnings.

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

## Branden execution record

The following complete command was used for Branden from the repository root:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
PYTHONPATH=src ../baseball-analysis/.venv312/bin/python -m baseball_report final \
  --config configs/generated/branden_final_report.json
```

The config records the manually reviewed 30 fps event frames: batting frame
195 and pitching frame 314. The execution order was:

```text
pitching C3D report + researcher charts
→ pitching 2D/Vicon alignment + event overlays
→ batting C3D metrics + 3D reconstructions and event assets
→ batting 2D/Vicon alignment + geometry annotations
→ combined HTML, copied pitch_assets, and batting XLSX
```

Before delivery, verify the generated files are non-empty and that the merged
HTML references local pitching assets:

```bash
test -s reports/vicon_2026_branden_coach/branden_coach_metrics_section.html
test -s reports/vicon_2026_branden_coach/batting_dashboard_metrics.csv
test -s reports/vicon_2026_branden_coach/alignment_2d/alignment_summary.json
test -s reports/pitching_branden_coach/index.html
test -s reports/pitching_branden_coach/pitch_metrics_summary.json
test -s 'outputs/branden_batting_metrics_excel/011-branden Bat 03_batting_report_metrics.xlsx'
rg 'pitch_assets/' reports/vicon_2026_branden_coach/branden_coach_metrics_section.html
```

On a macOS terminal with no OpenGL pixel format, the 2D alignment script
automatically uses the bundled RTMPose CPU fallback after the MediaPipe
`kGpuService` initialization failure. This is a detector-only substitution:
the human-reviewed event frame is retained, the C3D timeline remains the
master clock, and the displayed biomechanics values continue to come from C3D.

The report HTML generator also raises Python's CSV field-size limit before it
loads the dense reconstructed pose trajectory CSV. This prevents a valid large
trajectory field from failing at the standard 128 KiB parser limit.

## Internal scripts

`run_batting_report_pipeline.py` and the builders below it are internal
orchestration/implementation layers. Pitching builders, chart generators, and
2D alignment helpers are likewise internal. Run them only for focused
diagnosis after the public execution has established the required upstream
artifacts; always finish by rerunning the appropriate
`python -m baseball_report` execution.

`export_report_from_html.mjs` is an optional post-generation HTML-to-PDF/PPTX
exporter, not a report builder. Use `--help` for its explicit input and output
arguments.

For configuration, metrics, assets, and validation requirements, see
[`../src/README.md`](../src/README.md),
[`../skills/vicon-coach-report/SKILL.md`](../skills/vicon-coach-report/SKILL.md)
and [`../skills/vicon-coach-report/references/report-format.md`](../skills/vicon-coach-report/references/report-format.md).
