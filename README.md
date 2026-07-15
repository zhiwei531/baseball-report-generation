# baseball-report-generation

This repository produces a combined pitching + batting final deliverable. The
single supported entry builds pitching first, then passes its generated HTML and
assets into the batting report build.

## Standard entry

```bash
python scripts/report_cli.py final --config configs/final_report.json
```

Start from `configs/final_report.example.json`, copy it to
`configs/final_report.json`, and update both the batting config reference and
the pitching manifest/template/alignment inputs. The optional
`pitching.alignment` block generates the pitching 2D-video/Vicon-3D QA assets
from manually reviewed capture FPS and release frame.

The referenced batting config must provide reviewed `video_capture_fps` and
`video_event_frame`. Automatic event inference and prebuilt alignment folders
are intentionally rejected: they are not part of the validated report path.

## Client executions

Clients may run the two report disciplines independently, then retry only the
failed stage:

```bash
python scripts/report_cli.py pitching --config configs/final_report.json
python scripts/report_cli.py batting --config configs/final_report.json
```

`batting` requires the `pitching` execution's `out_dir/index.html`. `final`
is the convenience execution that runs those two stages in that order.

The pitching execution fails closed unless the two researcher curves, kinetic-chain curve, and (when alignment is configured) three report-ready 2D/Vicon event overlays are all generated.

## Required 2D/Vicon sequence

```text
C3D -> metrics -> MediaPipe landmarks -> reviewed event alignment
    -> clean MediaPipe skeleton overlay -> 2D-vs-Vicon-3D QA comparison
    -> Vicon-valued Ready/Contact geometry annotations -> HTML -> XLSX
```

The standard overlay is an actual MediaPipe skeleton rendered on the source
video. It contains no title, timestamp, caption, alignment label, or event
border, so event-frame exports are exactly matched pairs: one raw 2D frame and
one clean 2D+skeleton-overlay frame. QA metadata is opt-in with
`render_aligned_2d_overlay.py --show-alignment-metadata`.

Before rebuilding 2D assets, the pipeline removes its prior generated alignment, geometry-annotation, and QA-comparison folders. A failed rebuild cannot leave the report pointing at a prior player's screenshots.

For the Julian reference trial, Vicon `bat_speed_peak` frame 854 is manually mapped to video frame 184. The video is 240 fps at capture and approximately 29.48 fps at playback.

The report entry owns cross-discipline orchestration. Individual batting and
pitching scripts remain implementation details, preventing a stale hard-coded
pitching report from being embedded in a newly generated batting deliverable.

## Final report validation

Run the delivery gate after generation:

```bash
python scripts/validate_final_report.py \
  reports/vicon_2026_bryan_coach/bryan_coach_metrics_section.html \
  --athlete Bryan \
  --forbidden-subject Julian \
  --gold-html path/to/approved/bryan_coach_metrics_section.html
```

The validator checks every local `src`/`href`/`poster`, the required role and discipline labels, required pitching researcher assets, U9 copy, subject leakage, and gold-template tag/class structure. Data-driven status classes are ignored during structure comparison.

Create a compact self-contained delivery (HTML, every referenced asset, and small provenance/metric files; no multi-hundred-megabyte raw coordinate CSVs):

```bash
python scripts/package_final_report.py \
  reports/vicon_2026_bryan_coach/bryan_coach_metrics_section.html \
  --out outputs/bryan_final_report_delivery.zip
```
