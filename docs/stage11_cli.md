# Stage 11 — Unified Package CLI

## Changes Made

- Added `python -m baseball_report pitching|batting|final` with only flags
  already implemented by the public orchestration.
- Added `validate-report --input` for ReportData 1.0.
- Preserved child exit codes and the existing `scripts/report_cli.py` execution
  order as a compatibility adapter.

## Numerical Impact

None. The package command delegates to the same pipeline and configuration.

## Compatibility

The legacy command remains supported. No PDF/PPTX, unimplemented motion, or
handedness option was invented.

## Validation

Tests cover argument forwarding, exit-code propagation, schema validation, and
all command help output.

## Known Issues

The source checkout currently requires `PYTHONPATH=src` unless installed with
`pip install -e .`; Stage 12 documents both modes.

## Next Phase

Documentation, package/dependency reproducibility, then final verification.
