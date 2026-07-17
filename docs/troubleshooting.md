# Troubleshooting

- `No module named baseball_report`: install editable (`pip install -e .`) or
  use `PYTHONPATH=src`.
- configuration/preflight failure: run the same command with `--dry-run` and
  fix the resolved missing/overlapping paths; never make template/output equal.
- missing 2D output: verify video, C3D, model, reviewed capture FPS and reviewed
  event frame. Do not infer them.
- schema rejects NaN/Infinity: route legacy input through the adapters; nested
  non-finite metadata becomes `null` plus a warning.
- missing HTML asset: inspect `analysis_report_data.json`, relative reference,
  and generated report root. Absolute or `..` paths are invalid.
- unexpected metric: compare event frame, side profile, coordinate profile,
  unit, and metric registry before changing formula or golden data.
- MediaPipe macOS GPU initialization: only the documented `kGpuService`
  failure permits the recorded CPU fallback.
- Git push DNS failure: retry; commits remain local and main is not modified.
