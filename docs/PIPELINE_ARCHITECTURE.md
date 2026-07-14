# Pipeline Architecture

The repo is organized around a staged batting-report pipeline. The intended long-term input contract is:

```text
Vicon C3D folder + batting 2D video
  -> C3D metrics CSV
  -> 3D reconstruction assets
  -> batting dashboard metrics
  -> 2D/Vicon alignment and 2D metric annotations
  -> static metric illustration annotations
  -> final HTML schema
  -> optional XLSX body-metrics workbook
```

Pitching is now a sibling pipeline. The batting report builder accepts its completed HTML through `--pitch-report` and copies that HTML's `assets/` into `pitch_assets/`.

## Unified Command

Preferred command:

```bash
python scripts/run_batting_report_pipeline.py \
  --c3d-dir ../vicon_2026 \
  --alignment-dir outputs/julian_bat_2d_vicon_alignment \
  --pitch-report ../julian_pitch_template_report_2026-07-06/index.html
```

When a prepared 2D alignment folder is not available, the MediaPipe alignment stage can be used directly:

```bash
python scripts/run_batting_report_pipeline.py \
  --c3d-dir ../vicon_2026 \
  --video ../vicon_2026/julian/Bat_2D.mp4 \
  --c3d-file "../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d" \
  --mediapipe-model models/pose_landmarker_heavy.task
```

The raw-video path requires the MediaPipe task model file. The `mediapipe` Python package is part of the main requirements.

## Stages

| Stage | Script | Inputs | Outputs |
|---|---|---|---|
| C3D extraction | `run_vicon_c3d_pipeline.py` -> `build_vicon_2026_metrics.py` | `--c3d-dir` | `vicon_2026_metrics.csv`, `vicon_2026_point_summary.csv`, `vicon_2026_points_all.csv`, `vicon_2026_pose3d.csv` |
| 3D reconstruction | `run_vicon_c3d_pipeline.py` -> `render_vicon_reconstruction_images.py` | C3D folder + point summary CSV | `assets/vicon_reconstruction/*`, `assets/vicon_reconstruction_models/*` |
| Batting metrics | `build_batting_dashboard_metrics.py` | `vicon_2026_points_all.csv` | `batting_dashboard_metrics.csv`, `batting_dashboard_metrics_wide.csv` |
| Batting event GIFs | `build_julian_coach_event_gifs.py` | `batting_dashboard_metrics.csv` + source C3D | `assets/vicon_reconstruction_events/*.gif` |
| Annotated speed GIFs | `build_julian_coach_annotated_speed_gifs.py` | metrics + point summary + source C3D | `assets/vicon_reconstruction_annotated/*.gif` |
| 2D alignment | `align_2d_video_vicon.py` | 2D video + single C3D + MediaPipe model | `alignment_summary.json`, `pose2d_landmarks.csv` |
| Aligned overlay | `render_aligned_2d_overlay.py` | alignment summary + 2D landmarks | `aligned_2d_skeleton_overlay.mp4` |
| 2D metric annotations | `render_vicon_geometry_metrics_on_2d.py` | alignment folder + metrics | `assets/vicon_2d_geometry_annotations/*.png` |
| Metric illustrations | `annotate_frontend_metric_illustrations.py` | static illustration sources + metrics | `assets/frontend_metric_illustrations_annotated_standalone/*.png` |
| HTML schema | `build_julian_coach_metrics_section.py` | metrics + assets + optional pitching HTML | `julian_coach_metrics_section.html` |
| Final polish | `apply_batting_coach_values.py` | HTML + metrics + peer XLSX folder | final schema HTML and refreshed researcher charts |
| XLSX | `build_batting_metrics_xlsx.mjs` | metrics CSV | `*_batting_report_metrics.xlsx` |

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

Automated when alignment/static inputs exist:

- 2D metric overlay PNGs.
- Metric illustration annotation PNGs.

Implemented as separate commands:

- Pitching C3D metrics and report assets: `build-pitch-report`.
- Standalone single-video 2D report: `build-video-report`.
- 2D video/Vicon timing alignment: `sync-vicon-video`.

Optional external inputs remain:

- Prepared pitching 2D alignment images.
- Base line-art illustrations.
- MediaPipe task model files and other model weights.

Current schema role constraint:

- The final HTML builder still treats `julian` as the primary batting role and `coach` as the reference role in several filenames and copy blocks. For a new athlete, the immediate compatible path is to generate the metrics CSV with the primary athlete mapped to `sample_name=julian`, or to refactor `build_julian_coach_metrics_section.py` to accept role aliases.
