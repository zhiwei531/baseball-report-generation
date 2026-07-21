# Final Refactor Verification

> Branch: `refactor/systematic-engineering`
>
> Date: 2026-07-17

## Changes Made

- Completed the audited, incremental migration through configuration, typed
  motion/IO/kinematics/mapping/event/metric/pipeline/report/comparison/asset/CLI
  boundaries.
- Kept characterized legacy computations and builders as compatibility
  wrappers/adapters where deletion gates are not satisfied.
- Removed production and test `sys.path` mutation; package/script roots are
  supplied by the controlled CLI pipeline environment.
- Added the complete architecture, schema, data flow, metric, development,
  migration, and troubleshooting documentation set.

## Files Added

See intent-based commits and `docs/migration_guide.md`. The stable code lives
under `src/baseball_report/`; stage evidence is in `docs/stage1_*` through
`docs/stage11_cli.md`.

## Files Modified

Legacy scripts were changed only through validated wrappers, registry calls,
explicit pipeline stages, schema gates, and path/environment cleanup. No old
entry, notebook, sample, canonical template, or report copy was deleted.

## Data Flow Impact

The public flow now has explicit stages and additive typed outputs:

```text
configured raw inputs -> characterized legacy computation -> typed adapters
-> ReportData 1.0.1 -> report_view.v1 -> schema-gated static builder
-> HTML/XLSX/assets + pipeline/asset manifests
```

Legacy CSV/JSON remain dual-written compatibility artifacts.

## Numerical Impact

None. Fixed samples preserved frame counts, point/marker counts, source-frame
metadata, event frames/windows, all 17 batting values, all 41 pitching values
(18 report + 23 auxiliary), units, sides, score thresholds, report registry
hash, report artifact counts, HTML contract, and XLSX sheets. Existing
tolerance remains `1e-9`; exact identity is used for indices, strings and
rounded report values.

## Compatibility

- Preferred: `PYTHONPATH=src python -m baseball_report ...`.
- Retained: `python scripts/report_cli.py ...`.
- Retained: legacy CSV/JSON, HTML builder, final polish, XLSX and Node export
  commands.
- Canonical template remains the latest Git-tracked Bryan pitching
  `index.html`; it was read from Git and never overwritten by refactor work.
- No main merge occurred.

## Validation

- `95` unit/characterization/integration tests: `OK` (`7` protected/local
  artifact cases skipped when their opt-in paths are absent).
- Protected Bryan batting and pitching C3D golden baselines: exact.
- Protected report HTML/artifact/XLSX baseline: exact, with the two previously
  characterized optional missing 2D images unchanged.
- Git-tracked Python compilation: pass.
- Package import graph: 38 modules, zero detected cycles.
- Node `.mjs` syntax: pass.
- Package CLI `final --dry-run` on tracked Branden config: ready.
- Metric IDs: 17 batting and 18 pitching report IDs unique.
- `sys.path.append/insert`: none in production or tests.
- No TypeScript schema comparison is applicable because there is no TypeScript
  frontend; no frontend biomechanics recalculation was found. The Node XLSX
  builder displays existing metric rows.

## Known Issues

1. Current supported biomechanics profile remains right batting/right
   throwing; no unverified left-side generalization was introduced.
2. Physical Vicon global X/Y meaning and vendor angle-channel semantics remain
   uncertain; the explicit legacy coordinate profile is preserved.
3. HTML and final-polish value binding now use ReportData 1.0.1. The final
   batting polish itself remains a compatibility pass; removal requires two
   subjects to pass DOM, screenshot, PDF/PPTX and copy parity.
4. Several visualization scripts still combine series calculation and drawing;
   ReportAsset ownership is stable, but series extraction requires additional
   chart-data golden fixtures.
5. Canonical report assets now have explicit metric/event links; genuinely
   unclassified extra assets remain intentionally unbound instead of guessed.
6. macOS `._*` AppleDouble sidecars still break naked recursive `compileall`;
   `tools/validate_sources.py` now validates only Git-tracked sources and is
   sidecar-safe.
7. The working tree contains user-owned report/builder/config changes and
   untracked `node_modules`; none were committed by this refactor.

## Next Phase

No automatic code-deletion or merge phase follows. After a compatibility
release and two-subject visual/export parity, review the Stage 13 removal
conditions, then open separate deletion commits and merge only with developer
approval.
