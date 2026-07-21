# Data Flow

```mermaid
flowchart TD
  C3D --> Reader --> Motion["MotionSequence / legacy arrays"]
  Video --> Pose["MediaPipe or explicit RTMPose fallback"]
  Motion --> Event["batting / pitching event detectors"]
  Event --> Metric["17 batting / 18 pitching report metrics"]
  Motion --> Visual["reconstruction / overlay / charts"]
  Pose --> Align["reviewed video-event alignment"]
  Align --> Visual
  Metric --> Legacy["CSV + pitch summary JSON"]
  Legacy --> Schema["ReportData 1.0 + report_view.v1"]
  Visual --> Schema
  Schema --> HTML
  Legacy --> HTML
  HTML --> Export["optional PDF/PPTX exporters"]
```

Frame identities remain distinct: loaded zero-based sequence index, original
C3D header frame, reviewed source-video frame, timestamp, and display frame.
No layer infers conversion between them without explicit metadata.
