# Event Detection

Event ownership is centralized in `scripts/event_detection.py`; old builder
functions are wrappers. Batting preserves Ready Position and Contact Position
(lowest-`Bat1_Z` proxy) windows. Pitching preserves peak knee, foot contact,
foot plant, and release. Alignment preserves the reviewed source-video anchor.

Each typed event carries sequence ID, primary zero-based index, window,
detector/rule/source, confidence/quality, and warnings. Exact algorithms,
thresholds, frame offsets, and parity evidence are in
`docs/stage5_event_detection.md`. Event wording or frame definitions were not
changed by the refactor.
