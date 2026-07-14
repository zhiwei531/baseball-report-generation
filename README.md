# baseball-report-generation

Standalone report-generation scripts for the baseball Vicon batting report workflow.

This repository intentionally contains only the scripts used by the current batting report-generation process. Pitching sections are part of the final HTML schema, but pitching asset generation is owned by a separate teammate workflow and is represented here only as an integration interface.

## Contents

```text
scripts/
  report_cli.py                              unified entry point
  run_batting_report_pipeline.py             staged batting report pipeline
  pipeline_config.py                         shared config/path loader
  align_2d_video_vicon.py                    raw 2D video -> Vicon alignment
  render_aligned_2d_overlay.py               aligned 2D skeleton preview
  build_vicon_2026_metrics.py                C3D -> metrics/points/pose3d CSV
  render_vicon_reconstruction_images.py      Vicon 3D PNG/GIF/OBJ rendering
  run_vicon_c3d_pipeline.py                  C3D pipeline wrapper
  build_benchmark_report_html.py             full Chinese HTML report builder
  export_report_from_html.mjs                HTML -> PDF/PPTX
  build_batting_dashboard_metrics.py         Julian/Coach batting metrics
  build_julian_coach_event_gifs.py           Ready/Contact event GIFs
  build_julian_coach_annotated_speed_gifs.py frame-by-frame speed GIFs
  render_vicon_geometry_metrics_on_2d.py     Vicon values on aligned 2D skeleton
  build_julian_coach_metrics_section.py      standalone metrics HTML section
  apply_batting_coach_values.py              final batting schema polish pass
  generate_vicon_kinetic_chain_flow.py       kinetic-chain PNG utility
  annotate_frontend_metric_illustrations.py  metric illustration annotation
  build_batting_metrics_xlsx.mjs             batting metrics Excel export
docs/
  ASSET_PROVENANCE.md
  DESIGN.md
  FINAL_REPORT_IMAGE_CHECKLIST.md
  PIPELINE_ARCHITECTURE.md
  REPORT_README.md
  vicon_batting_csv_to_report_metrics.md
```

## Current Architecture

The supported report-generation path is config-driven:

```text
configs/default_report_pipeline.json
  -> scripts/report_cli.py build-batting-report
  -> scripts/run_batting_report_pipeline.py
  -> individual C3D, asset, HTML, and XLSX builders
```

Use this path for reusable batting reports. The older subcommands and individual builders remain available for debugging or partial rebuilds, but they are not the preferred production entry.

## Path Config

Reusable pipeline paths are centralized in:

```text
configs/default_report_pipeline.json
```

`root_dir` is the shared base folder. Relative paths in the config are resolved from `root_dir`; if `root_dir` itself is relative, it is resolved from this repository root.

For a new athlete/report, copy the default config and change only the paths/identity fields there:

```json
{
  "root_dir": ".",
  "c3d_dir": "../vicon_2026",
  "report_dir": "reports/vicon_2026_<player_slug>_coach",
  "video": "../vicon_2026/<player_slug>/Bat_2D.mp4",
  "c3d_file": "../vicon_2026/<player_slug>/<batting_trial>.c3d",
  "sample_name": "<player_slug>"
}
```

CLI arguments always override config values, so one-off rebuilds can still pass `--report-dir`, `--video`, or other paths directly.

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm install
npx playwright install chromium
```

The Excel export script uses `@oai/artifact-tool`, which is available in the Codex/OpenAI document runtime. If running outside that environment, pass `--skip-xlsx` to the staged pipeline or replace that script with a local Excel writer.

## Data Layout

Default paths assume this repository sits beside the data folder:

```text
final-project/
  baseball-report-generation/
  vicon_2026/
```

Generated outputs are written under this repository:

```text
reports/
output/
outputs/
```

These folders are ignored by Git except optional placeholder files.

## Unified Entry

Preferred staged batting pipeline:

```bash
python scripts/report_cli.py build-batting-report
```

Using a copied config:

```bash
python scripts/report_cli.py build-batting-report \
  --config configs/<player_slug>_report_pipeline.json
```

Raw 2D video alignment path:

```bash
python scripts/report_cli.py build-batting-report \
  --video ../vicon_2026/julian/Bat_2D.mp4 \
  --c3d-file "../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d"
```

Legacy full-report builder, kept for the older Bryan/Green benchmark report:

```bash
python scripts/report_cli.py full-vicon-report --input-dir ../vicon_2026
```

Debug-only C3D CSV/asset generation:

```bash
python scripts/report_cli.py c3d-pipeline --input-dir ../vicon_2026
```

Compatibility wrapper for C3D extraction and 3D reconstruction into the default Julian/Coach batting workspace:

```bash
python scripts/report_cli.py batting-c3d-pipeline --input-dir ../vicon_2026
```

This writes:

```text
reports/vicon_2026_julian_coach/vicon_2026_metrics.csv
reports/vicon_2026_julian_coach/vicon_2026_point_summary.csv
reports/vicon_2026_julian_coach/vicon_2026_points_all.csv
reports/vicon_2026_julian_coach/vicon_2026_pose3d.csv
reports/vicon_2026_julian_coach/vicon_2026_key_pose_models.csv
reports/vicon_2026_julian_coach/assets/vicon_reconstruction/
reports/vicon_2026_julian_coach/assets/vicon_reconstruction_models/
```

Rebuild only the HTML from existing CSV/assets:

```bash
python scripts/report_cli.py benchmark-html
```

Export existing HTML to PDF/PPTX:

```bash
python scripts/report_cli.py export-html
python scripts/report_cli.py export-html --only pdf
python scripts/report_cli.py export-html --only pptx
```

Legacy Julian/Coach section-only wrapper:

```bash
python scripts/report_cli.py julian-coach-section
```

For current builds, prefer `python scripts/report_cli.py build-batting-report`; it already runs the full staged pipeline and the XLSX stage unless `--skip-xlsx` is passed. Use `python scripts/report_cli.py julian-coach-section --help` only when debugging the legacy section-only path.

Pitching interface:

```bash
python scripts/report_cli.py build-batting-report \
  --pitch-report ../julian_pitch_template_report_2026-07-06/index.html
```

In the current staged pipeline, `pitch_report` should normally be set in the config. `--pitch-report` remains available as a CLI override. It expects an already-built pitching template HTML. `build_julian_coach_metrics_section.py` copies that template's `assets/` folder into the final batting report as `pitch_assets/` and embeds its sections. This repository does not generate `pitch_assets/*`; those builders should be added by the teammate who owns pitching.

## Source Selection

Included scripts are limited to the batting report build path documented in `docs/PIPELINE_ARCHITECTURE.md` and `docs/ASSET_PROVENANCE.md`.

Excluded on purpose:

- RTMPose/GVHMR pose model implementation and model folders. MediaPipe video alignment code is included; the `.task` model file is an input artifact and is not committed.
- Pitching-specific builders. The current repo keeps only the `--pitch-report` integration interface and expected `pitch_assets/` contract.
- Old 2D ablation scripts and Suzhou experiment runners.
- `external/`, `models/`, `src/baseball_pose/`, tests, raw data, C3D files, videos, `node_modules`.
- Generated report outputs, binary previews, zips, OBJ models, MP4/AVI files, and macOS `._*` metadata files.
