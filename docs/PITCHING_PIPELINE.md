# Pitching Vicon Report Pipeline

This contribution fills the pitching interface previously documented in this repository. It uploads scripts only; raw C3D files, athlete videos, generated images, and report outputs remain ignored.

## Inputs

- A report template directory containing `index.html` and `assets/`.
- A JSON manifest containing one primary athlete (`key: julian`), one coach reference (`key: coach`), and optional peer athletes.
- C3D paths referenced by the manifest. Relative paths resolve from the manifest file.

The `julian` and `coach` keys are currently schema roles, not required display names. Display names come from the manifest.

## Main command

```bash
python scripts/report_cli.py build-pitch-report \
  --manifest configs/pitching_manifest.json \
  --template-dir reports/vicon_2026_julian_coach \
  --out-dir reports/pitching
```

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
python scripts/annotate_pitch_lineart_metrics.py \
  --summary reports/pitching/pitch_metrics_summary.json \
  --asset-dir reports/pitching/assets/lineart_actions \
  --athlete-key julian
```

To generate publication-style presentation charts:

```bash
python scripts/generate_professional_pitch_charts.py \
  --summary reports/pitching/pitch_metrics_summary.json \
  --out-dir reports/pitching/assets/professional_pitch_charts \
  --athlete-key julian
```

The chart utility reconstructs smooth presentation curves from event anchors and summary metrics. These are not raw frame-by-frame time series and must be labeled accordingly.

## Event and metric limitations

- Front-foot plant is approximated from foot marker height and speed.
- Release is approximated from throwing-hand marker speed after foot plant.
- Hand speed is not ball speed.
- Coach values are technical references, not universal youth targets.
- Medical or injury-risk conclusions are outside this pipeline.
