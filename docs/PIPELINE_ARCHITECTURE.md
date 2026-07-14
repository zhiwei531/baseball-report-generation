# Pipeline Architecture

The repo is organized around separate staged batting and pitching pipelines. They do not write into the same output directory unless explicitly configured to do so.

The batting input contract is:

```text
Vicon C3D folder + batting 2D video
  -> C3D metrics CSV
  -> 3D reconstruction assets
  -> batting dashboard metrics
  -> 2D/Vicon alignment and 2D metric annotations
  -> static metric illustration annotations
  -> final HTML schema
  -> XLSX body-metrics workbook unless skipped
```

The pitching input contract is:

```text
Pitching C3D manifest + pitching template directory
  -> pitching metrics CSV/JSON
  -> pitching 3D reconstruction events
  -> pitching line-art metric annotations
  -> pitching kinetic-chain assets
  -> reports/pitching/index.html
```

The batting report builder accepts the independently built pitching HTML through `--pitch-report` and copies that HTML's `assets/` into `pitch_assets/`.

## Unified Command

The single final-deliverable entry builds pitching and then batting:

```bash
python scripts/report_cli.py --config configs/final_report.json
```

Start from `configs/final_report.example.json`. It references a batting pipeline
config and specifies the pitching manifest/template/output inputs:

```text
configs/default_report_pipeline.json
```

Path rules:

- `root_dir` is the shared base folder for the pipeline.
- Relative path fields are resolved from `root_dir`.
- A relative `root_dir` is resolved from the repository root.
- CLI arguments override config values.

For a new player, copy both the final config and batting config, then update the
batting C3D/video identity fields and pitching inputs:

```bash
python scripts/report_cli.py \
  --config configs/<player_slug>_final_report.json
```

The raw-video path is mandatory. The config must provide `mediapipe_model`, plus manually reviewed `video_capture_fps` and `video_event_frame`; automatic event inference and a prepared alignment folder are not supported report inputs.

For the validated Julian batting alignment, the Vicon event is `bat_speed_peak` at C3D frame `854`. The 2D event frame is manually reviewed as encoded video frame `184`. The source video metadata reports playback FPS `29.48022763100522`; with `240` capture FPS this produces slow-motion factor `8.141049757281554`.

`report_cli.py` passes the freshly built `pitching.out_dir/index.html` to the
batting builder, so the final report cannot accidentally embed a separately
hard-coded pitching output.

## Stages

### Batting

| Stage | Script | Inputs | Outputs |
|---|---|---|---|
| C3D extraction | `run_vicon_c3d_pipeline.py` -> `build_vicon_2026_metrics.py` | `--c3d-dir` | `vicon_2026_metrics.csv`, `vicon_2026_point_summary.csv`, `vicon_2026_points_all.csv`, `vicon_2026_pose3d.csv` |
| 3D reconstruction | `run_vicon_c3d_pipeline.py` -> `render_vicon_reconstruction_images.py` | C3D folder + point summary CSV | `assets/vicon_reconstruction/*`, `assets/vicon_reconstruction_models/*` |
| Batting metrics | `build_batting_dashboard_metrics.py` | `vicon_2026_points_all.csv` | `batting_dashboard_metrics.csv`, `batting_dashboard_metrics_wide.csv` |
| Batting event GIFs | `build_julian_coach_event_gifs.py` | `batting_dashboard_metrics.csv` + source C3D | `assets/vicon_reconstruction_events/*.gif` |
| Annotated speed GIFs | `build_julian_coach_annotated_speed_gifs.py` | metrics + point summary + source C3D | `assets/vicon_reconstruction_annotated/*.gif` |
| 2D alignment | `align_2d_video_vicon.py` | 2D video + single C3D + MediaPipe model | `alignment_summary.json`, `pose2d_landmarks.csv` |
| Aligned overlay | `render_aligned_2d_overlay.py` | alignment summary + 2D landmarks | `aligned_2d_skeleton_overlay.mp4`, `aligned_2d_overlay_preview.jpg` |
| 2D-vs-3D QA comparison | `render_vicon_3d_2d_alignment_comparison.py` | alignment summary + C3D | `assets/vicon_2d_vicon_3d_comparison/*` |
| 2D metric annotations | `render_vicon_geometry_metrics_on_2d.py` | alignment folder + metrics | `assets/vicon_2d_geometry_annotations/*.png` |
| Metric illustrations | `annotate_frontend_metric_illustrations.py` | static illustration sources + metrics | `assets/frontend_metric_illustrations_annotated_standalone/*.png` |
| HTML schema | `build_julian_coach_metrics_section.py` | metrics + assets + optional pitching HTML | `julian_coach_metrics_section.html` |
| Final polish | `apply_batting_coach_values.py` | HTML + metrics + peer XLSX folder | final schema HTML and refreshed researcher charts |
| XLSX | `build_batting_metrics_xlsx.mjs` | metrics CSV | `*_batting_report_metrics.xlsx` |

### Pitching

| Stage | Script | Inputs | Outputs |
|---|---|---|---|
| Pitching metrics/assets | `pitching/build_pitch_template_metrics_report.py` | manifest + template dir | `reports/pitching/index.html`, metrics CSV/JSON, pitching assets |
| Pitching line-art annotation | `pitching/annotate_pitch_lineart_metrics.py` | pitch summary + line-art source dir | `assets/lineart_actions/*_metrics.png` |
| Pitching chart utility | `pitching/generate_professional_pitch_charts.py` | pitch summary JSON | `assets/professional_pitch_charts/*.png` |
| Vicon/video sync | `pitching/sync_vicon_video.py` | video/C3D pairs | `outputs/vicon_video_sync/*.json` |
Individual builders are implementation details, not report entries. The report-generation contract is the config-driven `report_cli.py --config ...` command.

## Skip Flags

The pipeline exposes skip flags for partial rebuilds:

```bash
--skip-c3d
--skip-reconstruction
--skip-2d
--skip-illustrations
--skip-final-schema
--skip-xlsx
```

Use `--require-2d` or `--require-static-assets` when the build must fail instead of skipping missing optional inputs.

## Current Boundary

Fully automated from Vicon C3D:

- C3D-derived CSVs.
- 3D reconstruction images/GIFs/models.
- Batting dashboard metrics.
- Batting event GIFs.
- Batting annotated speed GIFs.
- Researcher batting kinetic-chain and graphs.
- XLSX body metrics.

Automated when raw 2D inputs or prepared alignment inputs exist:

- MediaPipe 2D/Vicon alignment.
- 2D skeleton overlay preview video.
- 2D metric overlay PNGs.

Automated when static illustration sources exist:

- Metric illustration annotation PNGs.

Built separately:

- Pitching image generation and pitching report generation. Default output is `reports/pitching`; batting integration copies it into batting as `pitch_assets/`.

Current schema role constraint:

- The final HTML builder still treats `julian` as the primary batting role and `coach` as the reference role in several filenames and copy blocks. For a new athlete, the immediate compatible path is to generate the metrics CSV with the primary athlete mapped to `sample_name=julian`.
- If this is later refactored to accept role aliases, keep the implementation inside the standard final-schema builder and validate the output against `baseball-analysis/reports/vicon_2026_julian_coach 4/julian_coach_metrics_section.html`. Do not keep alternate HTML builders in the repo until they match that standard template.
