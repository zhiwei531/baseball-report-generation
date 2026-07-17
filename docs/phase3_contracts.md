# Phase 3 — Core Data Contracts

> Completed: 2026-07-17
>
> Branch: `refactor/systematic-engineering`
>
> Schema status: internal `0.x.y`, not a public `1.0.0` contract

## Changes Made

- Added a minimal `src/baseball_report/` package boundary without redirecting
  the current public CLI or any producer.
- Added string enums for source type, motion type, side, handedness, role,
  coordinate profile, quality and warning severity.
- Added immutable domain objects for frame identity/windows, motion sequences,
  analysis context, events, metric definitions/results, comparisons, chart
  artifacts, report assets/sections/data, provenance/warnings and stage results.
- Added the planned exception hierarchy. Domain layers raise exceptions;
  existing CLI exit behavior is unchanged because it does not use the package.
- Added deterministic JSON conversion. It emits stable keys, converts
  unavailable numbers to `null` through typed results, and rejects NaN,
  Infinity, absolute asset paths and parent-directory traversal.
- Added read-only adapters for the current long-form batting metrics CSV and
  `pitch_metrics_summary.json`.
- Encoded existing right-handed/right-throwing and
  `legacy_vicon_z_up_mm` assumptions in adapter-created `AnalysisContext`.
- Added explicit informational warnings for the lowest-`Bat1_Z` Contact proxy
  and pitching hand-marker speed proxy.

The Vicon report skill contract influenced the provenance boundary: displayed
biomechanics remain C3D-derived, pose backends are not accepted as metric
sources, and proxy limitations are retained as machine-readable warnings.

## Files Added

- `pyproject.toml`
- `src/baseball_report/__init__.py`
- `src/baseball_report/core/`: enums, errors, validation, serialization,
  frames, motion, provenance and stage results
- `src/baseball_report/events/models.py`
- `src/baseball_report/metrics/models.py`
- `src/baseball_report/comparison/models.py`
- `src/baseball_report/visualization/models.py`
- `src/baseball_report/reporting/models.py`
- `src/baseball_report/legacy/`: batting CSV and pitching summary adapters
- `tests/test_phase3_contracts.py`
- `docs/phase3_contracts.md`

## Files Modified

- `docs/refactor_plan.md` records the Phase 3 completion gate.

No existing script, config, report template, report artifact or metric
implementation was modified by Phase 3.

## Data Flow Impact

There is no production data-flow change. The current flow remains:

```text
report_cli.py -> legacy builders -> legacy CSV/JSON/HTML/XLSX artifacts
```

The new path is read-only and disconnected:

```text
existing batting CSV / pitching summary JSON
  -> legacy adapter
  -> typed events, metrics, context and provenance
  -> tests/inspection only
```

No public command consumes `ReportData` yet.

## Numerical Impact

None. No C3D reader, frame selection, event detector, formula, aggregation,
unit, coordinate transform, handedness rule, score, rounding or report text was
changed. Adapters parse already-generated values and never recalculate them.

`FrameReference` can represent both the existing zero-based loaded-array index
and a future original source frame. Legacy artifacts that omitted the original
C3D header frame keep `source_frame_number=None`; the adapter does not invent
it.

## Compatibility

- `scripts/report_cli.py pitching|batting|final` is unchanged.
- Existing scripts are not wrappers yet and import none of the new package.
- Existing CSV, JSON, HTML, XLSX and template paths are unchanged.
- The canonical tracked template remains
  `reports/pitching_bryan_coach/index.html` and was not written.
- No TypeScript schema was added because the repository has no TypeScript
  frontend consumer.

## Validation

- 7 new contract/adapter tests passed.
- 4 existing pitching card-contract tests passed.
- Python compilation passed for every real source module.
- `pyproject.toml` parsed successfully and points package discovery at `src/`.
- Current Bryan read-only adapter comparison:
  - batting: 153 rows preserved across 9 trial bundles;
  - pitching: 9 athlete bundles;
  - pitching: all 41 current value keys preserved per athlete;
  - pitching: 18 report-facing metric definitions identified exactly.
- No trailing whitespace was found in Phase 3 files.

Direct `pytest` remains unusable in the current sibling virtual environment
because `_pytest.capture` crashes while importing the native `readline` module
(exit 139). The same 11 tests pass through standard-library `unittest`; this is
an environment/tooling issue rather than a test assertion failure.

## Known Issues

- The package is additive and not installed or used by the production CLI.
- `ReportData` is intentionally internal `0.x`; renderer integration and a
  public JSON validator are later stages.
- Legacy batting CSV has no original C3D first-frame metadata, so its adapter
  cannot restore source frame numbers.
- Pitching summary includes 18 report-facing metrics plus 23 consumed or
  diagnostic auxiliary values; Phase 4 must characterize their consumers
  before metric migration.
- Physical Vicon X/Y direction and vendor angle-channel semantic names remain
  undocumented; the package records the legacy profile without reinterpreting
  it.
- Raw athlete fixtures remain external and are not committed.

## Next Phase

Phase 4 will capture behavior before any producer changes:

1. compact non-identifying fixtures and golden manifests;
2. C3D reader/frame metadata characterization;
3. all 17 batting metrics and event windows;
4. all 18 pitching report metrics plus consumed auxiliary values;
5. pose/alignment and report DOM/asset contracts;
6. one batting and one pitching fixed-sample regression gate.
