# Architecture

This repository is one config-driven monolith, not a service mesh. The package
owns stable contracts and reusable rules; compatibility scripts still own
characterized legacy computations and rendering.

```mermaid
flowchart LR
  Config --> CLI["baseball_report CLI"]
  CLI --> Pipeline["explicit stage orchestration"]
  Pipeline --> IO["video / C3D / CSV / JSON IO"]
  IO --> Events
  Events --> Metrics
  Metrics --> Comparison
  Comparison --> ReportData["ReportData 1.0"]
  ReportData --> View["report_view.v1"]
  View --> Builder["static HTML compatibility builder"]
  Pipeline --> Assets["charts / overlays / GIF / MP4 / XLSX"]
  Assets --> ReportData
```

Ownership details are in `docs/target_architecture.md`; completed migration
evidence is in `docs/stage1_configuration.md` through
`docs/stage11_cli.md`.

Key invariants: Vicon is authoritative for displayed biomechanics; pose is
alignment/visual only; current side profile is right batting/right throwing;
coordinates remain `legacy_vicon_z_up_mm`; hand speed is not ball speed; the
Git-tracked Bryan pitching `index.html` is the canonical template.
