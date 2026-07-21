# Development

Use Python 3.10+; the verified local environment is Python 3.12.2 with Node
22.15.0 and npm 11.12.1. Install the
package in editable mode or prefix commands with `PYTHONPATH=src`. Runtime
package dependency is NumPy; legacy report scripts additionally require the
libraries already imported by those scripts (NumPy, pandas, matplotlib,
Pillow, OpenCV, MediaPipe and the configured RTMPose runtime). Node is required
only for XLSX/PDF/PPTX exporters; `package.json` pins Playwright as the direct
Node development dependency. Models and personal Vicon/video data remain
external configuration and are never package dependencies.

Run tests from the repository root:

```bash
PYTHONPATH=src:scripts:. python -m unittest discover -s tests
```

Validate tracked Python/Node sources without touching ignored macOS
AppleDouble `._*` files or writing bytecode beside source files:

```bash
python tools/validate_sources.py
```

Protected C3D/report baselines are opt-in through the environment variables in
`tests/integration/test_real_characterization_baselines.py`. Never commit raw
athlete media. Commit by intent on a refactor branch; do not merge automatically.
