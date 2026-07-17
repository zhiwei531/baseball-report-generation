# MediaPipe / 2D Pose Pipeline

The production path is config driven through `scripts/report_cli.py` or the
package CLI. Video, C3D, model, capture FPS, and reviewed event frame are
required for accepted alignment. `align_2d_video_vicon.py` writes landmarks
and alignment metadata; overlay renderers consume them. MediaPipe failure at
the documented macOS GPU-service boundary may use the explicit CPU RTMPose
fallback, recorded as degraded provenance.

2D pose does not calculate displayed biomechanics metrics. Landmark schema,
backend capability, missing-point behavior, and reviewed anchors are covered
by characterization tests. See `docs/repository_audit.md` for exact files and
`docs/stage4_point_mappings.md` for mappings.
