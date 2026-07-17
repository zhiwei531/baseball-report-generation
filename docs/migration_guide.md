# Migration Guide

| Old entry/module | New owner | Compatibility | Status | Removal condition |
|---|---|---|---|---|
| `scripts/report_cli.py` | `python -m baseball_report` | retained | wrapper target | package pipeline direct + compatibility period |
| path/config globals | `pipeline_config.py` | retained adapters | migrated | all configs versioned |
| C3D dictionaries | `MotionSequence` adapter | retained | migrated boundary | all consumers typed |
| event functions in builders | `event_detection.py` | wrappers | migrated | no dynamic references |
| metric tables | `metric_registry.py` | legacy dict view | migrated | every consumer typed |
| score/peer functions | `comparison/legacy_rules.py` | wrappers | migrated | view renderer parity |
| legacy CSV/JSON | `ReportData 1.0` adapters | dual output | active | historical data migrated |
| HTML value binding | `report_view.v1` | legacy binding retained | partial | two-subject DOM/screenshot/export parity |
| direct asset copy | `reporting/assets.py` | wrapper | migrated | all builders switched |
| visualization files | `ReportAsset` manifest | additive | active | typed series parity |

No legacy code is deleted in this refactor. See Stage 13 conditions in
`docs/refactor_plan.md`.
