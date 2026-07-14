# baseball-report-generation

Standalone report-generation scripts for baseball Vicon batting/pitching workflows and a single-video 2D report workflow.

The repository is organized by reproducible build path. Raw athlete data, videos, C3D files, generated reports, model weights, and personal machine paths are deliberately excluded.

## Contents

```text
scripts/
  report_cli.py                              unified entry point
  run_batting_report_pipeline.py             staged batting report pipeline
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
  build_pitch_template_metrics_report.py     pitching C3D metrics/assets builder
  annotate_pitch_lineart_metrics.py           computed values on pitching line art
  generate_professional_pitch_charts.py       pitching presentation charts
  sync_vicon_video.py                         2D video/Vicon event synchronization
  run_pitching_vicon_2d_alignment.py          one-command pitching 2D/Vicon alignment
  video_report/                               standalone 2D video-to-report pipeline
prompts/
  pitch_report_generation.md
  pitch_chart_redraw.md
  video_report_interpretation.md
  video_report_recommendation.md
configs/
  pitching_manifest.example.json
docs/
  ASSET_PROVENANCE.md
  DESIGN.md
  PIPELINE_ARCHITECTURE.md
  REPORT_README.md
  PITCHING_PIPELINE.md
  VIDEO_REPORT_PIPELINE.md
  VICON_VIDEO_SYNC.md
  vicon_batting_csv_to_report_metrics.md
```

## Setup

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm install
npx playwright install chromium
```

The Excel export script uses `@oai/artifact-tool`, which is available in the Codex/OpenAI document runtime. If running outside that environment, skip `--with-xlsx` or replace that script with a local Excel writer.

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
python scripts/report_cli.py build-batting-report \
  --c3d-dir ../vicon_2026 \
  --alignment-dir outputs/julian_bat_2d_vicon_alignment
```

Raw 2D video alignment path:

```bash
python scripts/report_cli.py build-batting-report \
  --c3d-dir ../vicon_2026 \
  --video ../vicon_2026/julian/Bat_2D.mp4 \
  --c3d-file "../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d" \
  --mediapipe-model models/pose_landmarker_heavy.task
```

Build the full Vicon report:

```bash
python scripts/report_cli.py full-vicon-report --input-dir ../vicon_2026
```

Run only C3D CSV/asset generation:

```bash
python scripts/report_cli.py c3d-pipeline --input-dir ../vicon_2026
```

Run C3D extraction and 3D reconstruction directly into the batting final-schema workspace:

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

Build the Julian/Coach batting metrics section and generated images:

```bash
python scripts/report_cli.py julian-coach-section
```

Optional Julian/Coach outputs:

```bash
python scripts/report_cli.py julian-coach-section --with-geometry-2d
python scripts/report_cli.py julian-coach-section --with-xlsx
python scripts/report_cli.py julian-coach-section --apply-final-schema
```

`--with-xlsx` exports the batting body metrics workbook from `batting_dashboard_metrics.csv` to `outputs/batting_metrics_excel/`.

Build the pitching metrics and assets from a C3D manifest:

```bash
python scripts/report_cli.py build-pitch-report \
  --manifest configs/pitching_manifest.json \
  --template-dir reports/vicon_2026_julian_coach \
  --out-dir reports/pitching
```

The example manifest uses placeholder relative paths. Copy it to `configs/pitching_manifest.json` and point it to local, ignored C3D inputs. See `docs/PITCHING_PIPELINE.md` for the output contract and metric limitations.

Build a standalone report from one 2D video:

```bash
python scripts/report_cli.py build-video-report \
  --input path/to/pitch.mp4 \
  --kind pitch \
  --side right \
  --athlete-name "Example Player" \
  --age-group U12
```

Synchronize raw sideline videos to Vicon:

```bash
python scripts/report_cli.py sync-vicon-video \
  --pair bat path/to/bat.mp4 path/to/bat.c3d \
  --pair pitch path/to/pitch.mp4 path/to/pitch.c3d
```

Run the complete pitching alignment path, including MediaPipe landmarks, frame mapping, and aligned skeleton MP4:

```bash
python scripts/run_pitching_vicon_2d_alignment.py \
  --video path/to/pitch.mp4 \
  --c3d path/to/pitch.c3d \
  --model path/to/pose_landmarker_heavy.task \
  --out-dir outputs/pitching_vicon_2d_alignment
```

See `docs/PITCHING_VICON_2D_ALIGNMENT.md` for slow-motion capture FPS and manual release-frame overrides.

Combine a built pitching report into the batting report:

```bash
python scripts/report_cli.py julian-coach-section \
  --pitch-report ../julian_pitch_template_report_2026-07-06/index.html
```

`--pitch-report` expects the `index.html` produced by the pitching workflow. `build_julian_coach_metrics_section.py` copies the sibling `assets/` folder into the final batting report as `pitch_assets/` and embeds its sections.

## Source Selection

Included scripts are limited to the batting, pitching, Vicon synchronization, and standalone 2D report paths documented under `docs/`.

Excluded on purpose:

- RTMPose/GVHMR pose model implementation and model folders. MediaPipe video alignment code is included; the `.task` model file is an input artifact and is not committed.
- Old 2D ablation scripts and Suzhou experiment runners.
- One-off HTML patch scripts with athlete-specific values or personal absolute paths.
- `external/`, `models/`, `src/baseball_pose/`, tests, raw data, C3D files, videos, `node_modules`.
- Generated report outputs, binary previews, zips, OBJ models, MP4/AVI files, and macOS `._*` metadata files.
