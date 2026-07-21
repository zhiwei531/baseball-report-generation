# Stage 10 — Visualization Artifact Boundary

## Changes Made

- Added deterministic discovery of existing report images, animations, videos,
  SVG, CSV, and JSON artifacts.
- Added portable `ReportAsset` IDs, MIME types, sizes, quality, and provenance
  to ReportData and `report_view.v1`.
- Excluded sidecars and schema outputs themselves; rejected no existing
  visualization merely because its metric/event association is uncertain.
- Kept every plotting, overlay, reconstruction, filename, dimension, and codec
  implementation unchanged.
- Follow-up: extracted batting bat-speed, bat-axis-angle, and five kinetic-chain
  time series into typed visualization data functions. The legacy builder now
  supplies those series to unchanged Pillow drawing functions.
- The public batting pipeline now passes its report-local `vicon_2026_pose3d.csv`
  explicitly to the builder instead of relying on the legacy Julian default.

## Files Added

- `src/baseball_report/visualization/manifest.py`
- `src/baseball_report/visualization/batting_series.py`
- `tests/test_visualization_manifest.py`
- `tests/test_visualization_series.py`
- `docs/stage10_visualization.md`

## Files Modified

- ReportData adapter/composition/build module
- `scripts/run_batting_report_pipeline.py`
- `docs/refactor_plan.md`

## Data Flow Impact

Generated files flow through `discover_report_assets -> ReportAsset ->
ReportData/report_view`. Batting research charts additionally flow through
`pose3d rows -> typed series extraction -> legacy drawing wrapper`; filenames
and renderer behavior are unchanged.

## Numerical Impact

None. A synthetic five-frame fixture proves exact time offsets, frames, units,
smoothed values, curve order, and wrapper parity. No event frame, formula,
coordinate, rendering parameter, filename, dimension, or codec changed.

## Compatibility

The manifest is additive. Existing relative paths and consumers remain valid.
Unknown metric/event associations are empty rather than guessed.

## Validation

Tests cover MIME/kind classification, stable relative paths, sidecar exclusion,
missing roots, unique IDs, schema serialization, and exact batting series
values before drawing. The protected suite is run again at the final gate.

## Known Issues

1. Batting research time-series extraction is resolved. Some pitching,
   reconstruction, and 2D overlay scripts still combine geometry extraction
   and drawing; each needs its own series/geometry parity fixture before move.
2. Canonical report assets have explicit links. Unrecognized extra artifacts
   remain unbound where the repository provides no authoritative association.
3. CSV/JSON analysis artifacts are classified as data assets, not charts.

## Next Phase

Proceed to Stage 11 package CLI consolidation and validation commands while
retaining `scripts/report_cli.py` as a wrapper.
