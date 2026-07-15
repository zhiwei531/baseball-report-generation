# baseball-report-generation

Generate one Vicon baseball deliverable containing pitching and batting. The
only supported report entry is `scripts/report_cli.py`; it always builds
pitching before embedding its assets in the batting report.

## Run a report

From this repository, use the project virtual environment and a player-specific
final config:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py final \
  --config configs/<player_slug>_final_report.json
```

Copy `configs/final_report.example.json` and its referenced batting config to
player-specific files. Set distinct output directories:

```text
reports/pitching_<player_slug>_coach/
reports/vicon_2026_<player_slug>_coach/
```

The checked-in Bryan trio is a working config example:

```text
configs/generated/bryan_final_report.json
configs/generated/bryan_coach_batting_pipeline.json
configs/generated/bryan_coach_pitching_manifest.json
```

The batting config requires reviewed `video_capture_fps` and
`video_event_frame`. Configure `pitching.alignment` in the final config when
matching pitching video, C3D, model, and reviewed release frame are available.
Do not infer these timing inputs during report generation.

## Retry scopes

Use only the public CLI executions below. `batting` requires the current
`pitching.out_dir/index.html`; use `final` whenever a change affects both
disciplines, timing, assets, or the merged deliverable.

```bash
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py pitching \
  --config configs/<player_slug>_final_report.json

../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py batting \
  --config configs/<player_slug>_final_report.json
```

The lower-level builders in `scripts/` are implementation details for focused
debugging only; they are not report-generation entries and must not be used to
hand off a combined report.

## Report guarantees

- Displayed biomechanics metrics come from Vicon C3D-derived data; 2D pose is
  used for alignment and visual overlays only.
- Pitching hand speed is a hand-marker proxy reported in `km/h`, not ball
  speed.
- Pitching flow and researcher assets are generated per player and rebound to
  the active player when an existing template is reused.
- Validate the generated combined HTML, pitching HTML, researcher PNGs,
  alignment assets (when configured), and XLSX before handoff.

See [scripts/README.md](scripts/README.md) for the public command contract and
the packaged `skills/vicon-coach-report/` for the operational workflow.
