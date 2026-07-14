# Pitching 2D Video / Vicon Alignment

This folder contains the complete pitching alignment path used to synchronize a raw sideline video with its matching Vicon C3D trial.

## One-command entry

```bash
python scripts/run_pitching_vicon_2d_alignment.py \
  --video path/to/pitch.mp4 \
  --c3d path/to/pitch.c3d \
  --model path/to/pose_landmarker_heavy.task \
  --out-dir outputs/pitching_vicon_2d_alignment
```

For a slow-motion recording, add the true capture rate:

```bash
--video-capture-fps 240
```

If release detection needs manual correction, add the reviewed video frame:

```bash
--video-event-frame 293
```

## Included scripts

- `run_pitching_vicon_2d_alignment.py`: pitching-specific one-command wrapper.
- `sync_vicon_video.py`: aligns the video motion peak with the Vicon throwing-hand speed peak.
- `align_2d_video_vicon.py`: extracts MediaPipe 2D landmarks and maps Vicon frames onto video frames.
- `render_aligned_2d_overlay.py`: renders the aligned 2D skeleton MP4.
- `build_vicon_2026_metrics.py`: C3D reader and point/event utilities required by the alignment script.

## Outputs

```text
pitching_alignment_manifest.json
sync/vicon_video_sync.json
alignment/alignment_summary.json
alignment/pose2d_landmarks.csv
alignment/vicon_points_aligned_to_video.csv
alignment/aligned_2d_skeleton_overlay.mp4
```

The mapping uses C3D as the master clock. Automatic release alignment is a reproducible first pass; manually verify the release frame before publication.
