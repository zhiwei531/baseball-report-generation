# Report Schema

`ReportData 1.0.x` is the stable analysis-to-builder contract. Required roots:
schema/report identity, subject, motions, events, metrics, comparisons, charts,
assets, sections, warnings, and provenance. IDs and references are validated;
non-finite numbers and absolute/parent-traversal asset paths are rejected.

`report_view.v1` resolves ordered section references for renderers. Python
`0.x` remains readable only for compatibility; builders require `1.0.x`.
There is no TypeScript contract because this repository has no TypeScript
consumer.

Validate with:

```bash
PYTHONPATH=src python -m baseball_report validate-report --input analysis_report_data.json
```

See `docs/stage8_report_schema.md` and `docs/stage9_reporting.md`.
