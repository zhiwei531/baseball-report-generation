# 2D Video / Vicon Synchronization

`scripts/pitching/sync_vicon_video.py` treats C3D as the master clock and aligns each sideline video to an action-specific peak:

- batting: bat-marker speed peak;
- pitching: throwing-hand marker speed peak.

Example:

```bash
python scripts/report_cli.py sync-vicon-video \
  --pair bat path/to/bat.mp4 path/to/bat.c3d \
  --pair pitch path/to/pitch.mp4 path/to/pitch.c3d \
  --output-dir outputs/vicon_video_sync
```

The output JSON records the source paths, frame rates, anchors, offset, confidence, and mapping formula:

```text
vicon_time_sec = video_time_sec + video_to_c3d_offset_sec
```

Peak alignment is a reproducible first pass. For publication-quality synchronization, manually verify the contact/release event and record any corrected offset.
