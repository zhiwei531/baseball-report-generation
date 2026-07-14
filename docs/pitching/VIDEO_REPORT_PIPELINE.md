# Standalone 2D Video Report Pipeline

`scripts/video_report/` contains the scripts used by the standalone single-video workflow:

```text
video
  -> MediaPipe 2D pose
  -> quality filtering, interpolation, and temporal smoothing
  -> batting or pitching proxy metrics
  -> rule-based status and limitations
  -> report JSON, Markdown, and HTML
```

## Run

```bash
python scripts/report_cli.py build-video-report \
  --input path/to/video.mp4 \
  --kind pitch \
  --side right \
  --athlete-name "Example Player" \
  --age-group U12
```

Use `--kind hit` for batting, or `--kind auto` to infer from the filename. Outputs are written under `scripts/video_report/outputs/end_to_end_reports/` unless `--out` is supplied.

## Scope

- Best for one visible athlete, a stable camera, limited occlusion, and a full-body view.
- Angles are 2D image-plane measurements and vary with camera perspective.
- Speed fields are normalized video proxies unless an external calibrated 3D source is supplied.
- The relative 3D preview is explanatory, not a replacement for calibrated motion capture.
- Raw videos and generated reports are not committed.

The prompts in `prompts/video_report_*.md` define the language and recommendation boundary if an LLM is used downstream. The deterministic pipeline itself does not require an LLM.
