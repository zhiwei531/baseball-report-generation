# baseball-report-generation

Generate one Vicon baseball deliverable containing pitching and batting. The
only supported report entry is `scripts/report_cli.py`; it always builds
pitching before embedding its assets in the batting report.

> **Canonical workspace:** Run every report-generation command from this
> `baseball-report-generation/` directory. Do **not** run from dated snapshot
> folders such as `baseball-report-generation-YYYYMMDD`; they are not the
> maintained report-generation workspace and may contain stale configs,
> templates, or outputs.

## Run a report

From this repository, use the project virtual environment and the
player-specific final config in `configs/generated/`:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py final \
  --config configs/generated/<player_slug>_final_report.json
```

For example, the current 7zai deliverable is generated with:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py final \
  --config configs/generated/7zai_final_report.json
```

Validate all configured inputs and resolved output paths without generating or
modifying report artifacts:

```bash
../baseball-analysis/.venv312/bin/python scripts/report_cli.py final \
  --config configs/generated/<player_slug>_final_report.json \
  --dry-run
```

The dry run is safe to call from outside the repository: final and batting
config paths remain repository-root relative, while pitching C3D paths remain
relative to their manifest file. Review every warning before a full build,
especially template/output overlap and existing output directories.

For a new player, create the three player-specific files under
`configs/generated/`: final config, batting config, and pitching manifest.
Start with `configs/final_report.example.json` and its referenced batting
config. Set distinct output directories:

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

### Branden reproducible run

Branden's reviewed inputs are checked in as:

```text
configs/generated/branden_final_report.json
configs/generated/branden_coach_batting_pipeline.json
configs/generated/branden_coach_pitching_manifest.json
```

The reviewed 30 fps anchors are frame **195** for batting (bat-speed/contact
window) and frame **314** for pitching (release/throwing-hand-speed window).
Rebuild the complete deliverable with:

```bash
MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py final \
  --config configs/generated/branden_final_report.json
```

This produces:

```text
reports/pitching_branden_coach/index.html
reports/vicon_2026_branden_coach/branden_coach_metrics_section.html
outputs/branden_batting_metrics_excel/011-branden Bat 03_batting_report_metrics.xlsx
```

#### Headless macOS pose fallback

The configured MediaPipe task is the default 2D detector. In a terminal
without a macOS OpenGL pixel format, MediaPipe can fail while creating its GPU
service even when its CPU delegate is requested. `align_2d_video_vicon.py`
automatically falls back to the bundled CPU-only
`../baseball-analysis/models/rtmpose-m-wholebody.onnx` model only for that
specific `kGpuService` initialization failure. It writes the same landmark CSV
schema and records `"pose_backend": "rtmpose_cpu_fallback"` in the alignment
summary. The reviewed event frame, C3D clock, displayed metrics, and report
output contract remain unchanged.

The batting config requires reviewed `video_capture_fps` and
`video_event_frame`. Configure `pitching.alignment` in the final config when
matching pitching video, C3D, model, and reviewed release frame are available.
Do not infer these timing inputs during report generation.

### Required peer configuration for team comparisons

The pitching manifest must include every available same-group player when the
report displays `乐风U9同组表现` (group mean, range, or comparison dots). Put
the report subject first with `role: "student"`, then add each peer as another
`role: "student"` row, and include exactly one `role: "coach"` row. Each row
must point to that person's matching pitching C3D. With only the report
subject and coach configured, a report can run, but its group-comparison
results are not a valid team benchmark.

The batting peer comparison has the same requirement: make sure all players'
batting metrics are present in `outputs/batting_metrics_excel/all_players`.

## Retry scopes

Use only the public CLI executions below. `batting` requires the current
`pitching.out_dir/index.html`; use `final` whenever a change affects both
disciplines, timing, assets, or the merged deliverable.

```bash
../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py pitching \
  --config configs/generated/<player_slug>_final_report.json

../baseball-analysis/.venv312/bin/python -u scripts/report_cli.py batting \
  --config configs/generated/<player_slug>_final_report.json
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
