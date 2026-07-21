# `baseball_report` package

`src/baseball_report/` is the stable Python package boundary for report
generation. New commands and reusable code should import from this package or
run its module CLI instead of importing executable files from `scripts/`.

The repository is still a config-driven monolith. The package does not add a
database, service layer, queue, or alternate biomechanics implementation.
Characterized legacy builders remain under `scripts/` and are invoked through
compatibility adapters until their behavior has an equivalent package-owned
implementation and regression coverage.

## Run from a source checkout

From the repository root:

```bash
PYTHONPATH=src python -m baseball_report --help

PYTHONPATH=src python -m baseball_report final \
  --config configs/generated/<player_slug>_final_report.json

PYTHONPATH=src python -m baseball_report validate-report \
  --input reports/<report>/analysis_report_data.json
```

The project currently supports `pitching`, `batting`, `final`, and
`validate-report`. Use each subcommand's `--help` output as the authoritative
flag list. The report commands accept the final config rather than separate
ad-hoc paths, keeping the pitching manifest, batting config, templates, and
output directories traceable through one validated configuration boundary.

When using the repository's existing analysis environment, replace `python`
with `../baseball-analysis/.venv312/bin/python`; this does not change the
package entry or configuration contract.

## Module ownership

| Module | Responsibility | Must not own |
| --- | --- | --- |
| `cli.py` | Parse supported commands, invoke the pipeline boundary, report exit status, validate ReportData | Metric formulas, event detection, HTML layout |
| `core/` | Shared enums, frame identity, motion sequences, provenance, validation, errors, deterministic serialization | File-format-specific parsing or report styling |
| `io/` | Adapt C3D and pose CSV inputs into explicit motion data | Baseball scoring or narrative generation |
| `events/` | Typed motion-event results and collections | File reading or chart rendering |
| `metrics/` | Typed metric definitions and results | Template manipulation or artifact copying |
| `comparison/` | Player/reference comparison models and protected legacy comparison rules | Raw C3D/video loading |
| `visualization/` | Chart-ready series and report asset manifests | Recalculation of biomechanics metrics |
| `reporting/` | ReportData models, legacy adapters, schema validation, composition, asset boundaries | MediaPipe inference or C3D reconstruction |
| `legacy/` | Explicit adapters for characterized CSV/JSON formats | New domain behavior |

The current numerical invariants remain unchanged: Vicon data is authoritative
for displayed biomechanics, pose data is used for alignment and visual
overlays, coordinate and unit declarations remain explicit, and legacy event
frames and metric formulas are protected by characterization tests.

## Package and `scripts/` boundary

Use the package for:

- report-generation CLI calls;
- stable `MotionSequence`, event, metric, comparison, and ReportData models;
- C3D/pose adapters and schema validation;
- reusable reporting and visualization contracts.

Treat `scripts/` as a compatibility and implementation directory. Do not
import a lower-level builder into new application code when a package-owned
model, adapter, or CLI boundary exists. `scripts/report_cli.py` remains
available so existing automation keeps working; the package CLI currently
delegates report orchestration to that wrapper while preserving the package
environment and exit code.

Do not bypass the public CLI by calling individual builders to create a final
deliverable. Focused diagnostic runs may use an internal script, but the
appropriate package command must be rerun before report handoff.

## Adding or migrating code

1. Preserve the current event frames, formulas, units, coordinate systems,
   side rules, and report values with characterization tests.
2. Put pure domain calculations in the relevant package module and keep file
   IO, visualization, and reporting separate.
3. Add an adapter before changing a legacy dictionary or CSV contract.
4. Keep the old script entry as a compatibility wrapper until callers and
   documentation have migrated and parity is verified.
5. Update the module and old/new-entry mapping in
   [`../docs/migration_guide.md`](../docs/migration_guide.md).

Architecture and data-contract details are documented in
[`../docs/architecture.md`](../docs/architecture.md),
[`../docs/report_schema.md`](../docs/report_schema.md), and
[`../docs/development.md`](../docs/development.md).
