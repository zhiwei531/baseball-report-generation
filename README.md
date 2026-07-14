# baseball-report-generation

Standalone report-generation scripts for baseball Vicon batting and pitching report workflows.

This repository intentionally keeps batting and pitching build paths separate. Batting reports use the config-driven batting pipeline; pitching reports build their own template and assets under a separate output directory, then can be passed into the batting report through `--pitch-report`.

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
  pitching/                                  pitching C3D report builders
configs/
  default_report_pipeline.json               batting pipeline path config
  pitching/manifest.example.json             pitching C3D manifest template
docs/
  ASSET_PROVENANCE.md
  DESIGN.md
  FINAL_REPORT_IMAGE_CHECKLIST.md
  PIPELINE_ARCHITECTURE.md
  pitching/
  REPORT_README.md
  vicon_batting_csv_to_report_metrics.md
prompts/
  pitch_report_generation.md
  pitch_chart_redraw.md
```

## Current Architecture

The supported batting report-generation path is config-driven:

```text
configs/default_report_pipeline.json
  -> scripts/report_cli.py build-batting-report
  -> scripts/run_batting_report_pipeline.py
  -> individual C3D, asset, HTML, and XLSX builders
```

Use this path for reusable batting reports. Pitching is built separately with `build-pitching-report` and should write to `reports/pitching` or another explicit pitching output directory. The older subcommands and individual builders remain available for debugging or partial rebuilds, but they are not the preferred production entry.

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

Raw 2D/Vicon alignment is part of the same batting entry. The default Julian config uses:

```text
video: ../vicon_2026/julian/Bat_2D.mp4
c3d_file: ../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d
mediapipe_model: ../baseball-analysis/models/pose_landmarker_heavy.task
video_capture_fps: 240
video_event_frame: 184
```

Run it through the staged report command:

```bash
python scripts/report_cli.py build-batting-report \
  --video ../vicon_2026/julian/Bat_2D.mp4 \
  --c3d-file "../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d" \
  --mediapipe-model ../baseball-analysis/models/pose_landmarker_heavy.task \
  --video-capture-fps 240 \
  --video-event-frame 184
```

This runs `align_2d_video_vicon.py` and `render_aligned_2d_overlay.py`, producing:

```text
reports/vicon_2026_julian_coach/alignment_2d/alignment_summary.json
reports/vicon_2026_julian_coach/alignment_2d/pose2d_landmarks.csv
reports/vicon_2026_julian_coach/alignment_2d/vicon_points_aligned_to_video.csv
reports/vicon_2026_julian_coach/alignment_2d/aligned_2d_skeleton_overlay.mp4
reports/vicon_2026_julian_coach/alignment_2d/aligned_2d_overlay_preview.jpg
```

The Vicon event is read from `build_vicon_2026_metrics.py` via `key_action_frame()`; for the Julian batting trial it resolves to `bat_speed_peak`, frame `854`. The encoded playback FPS is read from the video metadata; for the validated Julian file it was `29.48022763100522`, giving a slow factor of `8.141049757281554` when paired with `240` capture FPS.

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

Build pitching first:

```bash
python scripts/report_cli.py build-pitching-report \
  --manifest configs/pitching/manifest.json \
  --template-dir reports/pitching_template \
  --out-dir reports/pitching
```

Then combine that built pitching HTML into the batting report:

```bash
python scripts/report_cli.py build-batting-report \
  --pitch-report reports/pitching/index.html
```

`build-pitching-report` does not write into the batting report directory. In the batting staged pipeline, `pitch_report` should normally be set in the batting config. `--pitch-report` remains available as a CLI override. It expects an already-built pitching `index.html`; `build_julian_coach_metrics_section.py` copies that HTML's sibling `assets/` folder into the final batting report as `pitch_assets/` and embeds its sections.

Vicon/video synchronization:

```bash
python scripts/report_cli.py sync-vicon-video \
  --pair pitch path/to/pitch.mp4 path/to/pitch.c3d \
  --output-dir outputs/vicon_video_sync
```

## Source Selection

Included scripts are limited to the batting, pitching, and Vicon/video synchronization paths documented in `docs/PIPELINE_ARCHITECTURE.md`, `docs/ASSET_PROVENANCE.md`, and `docs/pitching/`.

Excluded on purpose:

- RTMPose/GVHMR pose model implementation and model folders. MediaPipe video alignment code is included; the `.task` model file is an input artifact and is not committed.
- Standalone single-video report package scripts. Those scripts do not align a 2D video to a C3D trial and are not part of the current final report pipeline.
- Old 2D ablation scripts and Suzhou experiment runners.
- `external/`, `models/`, `src/baseball_pose/`, tests, raw data, C3D files, videos, `node_modules`.
- Generated report outputs, binary previews, zips, OBJ models, MP4/AVI files, and macOS `._*` metadata files.
