# Pitching 2D Video / Vicon 3D Alignment

This is the standard QA path for synchronizing a raw sideline pitching video with its matching Vicon C3D trial. The combined final-report entry invokes it when the optional `pitching.alignment` block is present in its config; the command below remains useful for isolated QA.

## Command

```bash
python scripts/pitching/run_vicon_2d_alignment.py \
  --video path/to/pitch.mp4 \
  --c3d path/to/pitch.c3d \
  --model path/to/pose_landmarker_heavy.task \
  --out-dir outputs/pitching_vicon_2d_alignment \
  --player-slug bryan \
  --player-label Bryan \
  --video-capture-fps 30 \
  --video-event-frame 293
```

`--video-capture-fps` and `--video-event-frame` are required. Do not publish report assets from automatic release-frame detection without manual review.

## Inputs

- Raw sideline pitching video.
- Matching pitching C3D trial.
- MediaPipe Pose Landmarker `.task` model.
- Reviewed true capture FPS for slow-motion video.
- Reviewed 2D release frame.

## Outputs

```text
pitching_alignment_manifest.json
sync/vicon_video_sync.json
sync/pitch_sync_signals.csv
alignment/alignment_summary.json
alignment/pose2d_landmarks.csv
alignment/vicon_points_aligned_to_video.csv
alignment/aligned_2d_skeleton_overlay.mp4
comparison/<player_slug>_2d_video_vs_vicon_3d_reconstruction.mp4
comparison/<player_slug>_2d_video_vs_vicon_3d_reconstruction_preview.jpg
```

When invoked through `scripts/report_cli.py`, the report output also contains:

```text
assets/video_2d_alignment/<player_slug>_pitch_peak_knee_2d_overlay.png
assets/video_2d_alignment/<player_slug>_pitch_foot_plant_2d_overlay.png
assets/video_2d_alignment/<player_slug>_pitch_release_2d_overlay.png
assets/video_2d_alignment/pitch_event_overlay_provenance.json
```

The wrapper cleans only these standard output children inside `--out-dir` before regenerating them, so stale alignment videos and previews do not survive a rerun.

## Companion Scripts

- `scripts/pitching/sync_vicon_video.py`: writes the pitching sync JSON and signal CSV.
- `scripts/align_2d_video_vicon.py`: extracts 2D landmarks and maps Vicon frames to video frames.
- `scripts/render_aligned_2d_overlay.py`: renders the aligned 2D skeleton overlay MP4.
- `scripts/render_vicon_3d_2d_alignment_comparison.py`: renders the side-by-side 2D video and Vicon 3D comparison MP4/preview.
- `scripts/pitching/render_pitch_event_overlays.py`: renders the three report screenshots with MediaPipe geometry and Vicon event values.

The mapping uses C3D as the master clock. The release frame and capture FPS are explicit reviewed inputs because these values materially change every downstream screenshot and video alignment asset.
