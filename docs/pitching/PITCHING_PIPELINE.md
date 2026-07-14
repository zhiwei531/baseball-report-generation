# Pitching Vicon Report Pipeline

This contribution fills the pitching interface previously documented in this repository. It uploads scripts only; raw C3D files, athlete videos, generated images, and report outputs remain ignored.

## Inputs

- A report template directory containing `index.html` and `assets/`.
- A JSON manifest containing one primary athlete (`key: julian`), one coach reference (`key: coach`), and optional peer athletes.
- C3D paths referenced by the manifest. Relative paths resolve from the manifest file.

The `julian` and `coach` keys are currently schema roles, not required display names. Display names come from the manifest.

## Final deliverable command

For a combined pitching + batting report, use the repository entry:

```bash
python scripts/report_cli.py --config configs/final_report.json
```

## Lower-level pitching builder

```bash
python scripts/pitching/build_pitch_template_metrics_report.py \
  --manifest configs/pitching/manifest.json \
  --template-dir reports/pitching_template \
  --out-dir reports/pitching
```

Keep `--out-dir` separate from the batting report directory. To combine pitching into batting, build pitching first, then pass `reports/pitching/index.html` to the batting pipeline through `pitch_report` or `--pitch-report`.

The builder uses the repository's existing `build_vicon_2026_metrics.py` C3D reader and `render_vicon_reconstruction_images.py` renderer. It writes:

```text
reports/pitching/index.html
reports/pitching/pitch_metrics_all_players.csv
reports/pitching/pitch_metrics_summary.json
reports/pitching/assets/frontend_metric_illustrations_pitch/
reports/pitching/assets/kinetic_chain/
reports/pitching/assets/vicon_reconstruction_events/
```

To annotate three prepared line-art images with computed values:

```bash
python scripts/pitching/annotate_pitch_lineart_metrics.py \
  --summary reports/pitching/pitch_metrics_summary.json \
  --asset-dir reports/pitching/assets/lineart_actions \
  --athlete-key julian
```

To generate publication-style presentation charts:

```bash
python scripts/pitching/generate_professional_pitch_charts.py \
  --summary reports/pitching/pitch_metrics_summary.json \
  --out-dir reports/pitching/assets/professional_pitch_charts \
  --athlete-key julian
```

The chart utility reconstructs smooth presentation curves from event anchors and summary metrics. These are not raw frame-by-frame time series and must be labeled accordingly.

To generate pitching 2D-video / Vicon-3D alignment QA assets, use the dedicated lower-level wrapper documented in `docs/pitching/PITCHING_VICON_2D_ALIGNMENT.md`. It requires reviewed slow-motion capture FPS and reviewed release frame, then writes the 2D skeleton overlay plus the side-by-side 2D-vs-3D comparison assets.

## Event and metric limitations

- Front-foot plant is approximated from foot marker height and speed.
- Release is approximated from throwing-hand marker speed after foot plant.
- Hand speed is not ball speed.
- Coach values are technical references, not universal youth targets.
- Medical or injury-risk conclusions are outside this pipeline.
