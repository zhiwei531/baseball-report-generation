# Report Schema

`ReportData 1.0.x` is the stable analysis-to-builder contract. Required roots:
schema/report identity, subject, motions, events, metrics, comparisons, charts,
assets, sections, warnings, and provenance. IDs and references are validated;
non-finite numbers and absolute/parent-traversal asset paths are rejected.

`report_view.v1` resolves ordered section references for renderers. Python
`0.x` remains readable only for compatibility; builders require `1.0.x`.
There is no TypeScript contract because this repository has no TypeScript
consumer.

`1.0.1` adds `reference_result` and `peer_results` snapshots to each
comparison. These carry the comparison subject, sequence, value, unit, event
frame, and calculation components needed by the static batting builder. The
builder therefore binds metric cards and peer markers from ReportData instead
of reopening legacy metric CSV/XLSX files. The old `--metrics` and `--peers`
arguments remain accepted during the compatibility period but no longer supply
card data.

Validate with:

```bash
PYTHONPATH=src python -m baseball_report validate-report --input analysis_report_data.json
```

See `docs/stage8_report_schema.md` and `docs/stage9_reporting.md`.
