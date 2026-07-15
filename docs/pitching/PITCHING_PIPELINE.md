# Pitching Vicon Report Pipeline

Pitching is a public execution of the config-driven report CLI, not a separate
hand-off entry. It consumes a pitching manifest, a reusable template directory,
and an isolated pitching output directory from the final-report config.

## Supported commands

```bash
python scripts/report_cli.py pitching \
  --config configs/<player_slug>_final_report.json

python scripts/report_cli.py final \
  --config configs/<player_slug>_final_report.json
```

Use `pitching` to rebuild or retry pitching alone. Use `final` to produce a
complete report or when the rebuilt pitching assets must be merged into batting.
Do not invoke `build_pitch_template_metrics_report.py` or chart utilities as a
deliverable entry; the CLI invokes them in the required order and validates the
researcher outputs.

## Config contract

The final config requires:

```text
pitching.manifest       # one role: student, one key: coach; relative C3D paths resolve from this file
pitching.template_dir   # existing HTML/assets template to personalize
pitching.out_dir        # reports/pitching_<player_slug>_coach/
```

Optionally provide `pitching.alignment` only with a matching raw video, C3D,
MediaPipe model, reviewed capture FPS, and reviewed release frame. Its output
must be separate from the combined batting report directory.

## Outputs

```text
reports/pitching_<player_slug>_coach/
  index.html
  pitch_metrics_all_players.csv
  pitch_metrics_summary.json
  assets/kinetic_chain/<player_slug>_pitch_kinetic_chain_flow.png
  assets/kinetic_chain/<player_slug>_kinetic_chain_time_curves.png
  assets/analyst_charts/<player_slug>_pitch_angle_time_curve.png
  assets/analyst_charts/<player_slug>_pitch_speed_time_curve.png
```

When alignment is configured, the CLI also creates three Vicon-valued event
overlay cards under `assets/video_2d_alignment/`. Hand speed is displayed in
`km/h` as a hand-marker proxy, not ball speed. The metric flow is rear leg →
pelvis → trunk → throwing arm → hand.

See [PITCHING_VICON_2D_ALIGNMENT.md](PITCHING_VICON_2D_ALIGNMENT.md) for the
isolated alignment QA helper; use the public CLI for report builds.
