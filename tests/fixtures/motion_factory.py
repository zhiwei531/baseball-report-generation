from __future__ import annotations

from pathlib import Path

import numpy as np

from build_batting_dashboard_metrics import TrialSeries
from build_vicon_2026_metrics import C3DTrial, clean_label


def make_batting_trial() -> TrialSeries:
    frame_count = 80
    rate_hz = 100.0
    points: dict[str, np.ndarray] = {}

    def add(name: str, xyz: tuple[float, float, float]) -> None:
        points[name] = np.tile(np.array(xyz, dtype=float), (frame_count, 1))

    for name, xyz in {
        "LASI": (-100, 0, 900),
        "LPSI": (-100, -20, 900),
        "RASI": (100, 0, 900),
        "RPSI": (100, -20, 900),
        "LSHO": (-150, 0, 1400),
        "RSHO": (150, 0, 1400),
        "LKNE": (-100, 0, 500),
        "RKNE": (100, 0, 500),
        "LANK": (-100, 0, 0),
        "RANK": (100, 0, 0),
        "LHEE": (-100, -50, 0),
        "RHEE": (100, -50, 0),
        "LTOE": (-100, 100, 0),
        "RTOE": (100, 100, 0),
        "LELB": (-250, 0, 1200),
        "RELB": (250, 0, 1200),
        "LWRA": (-300, 0, 1100),
        "LWRB": (-305, 10, 1100),
        "RWRA": (300, 0, 1100),
        "RWRB": (305, 10, 1100),
        "LFHD": (-50, 0, 1700),
        "RFHD": (50, 0, 1700),
        "LBHD": (-50, -30, 1700),
        "RBHD": (50, -30, 1700),
        "C7": (0, 0, 1450),
        "T10": (0, 0, 1100),
        "CLAV": (0, 20, 1400),
        "STRN": (0, 30, 1300),
        "RBAK": (0, -20, 1250),
        "CentreOfMass": (0, 0, 900),
    }.items():
        add(name, xyz)

    x = np.zeros(frame_count)
    x[30:51] = np.linspace(0, 1000, 21)
    x[51:] = 1000
    z = np.full(frame_count, 1200.0)
    z[30:51] = 1200 - 300 * np.sin(np.linspace(0, np.pi, 21))
    points["Bat1"] = np.column_stack((x, np.zeros(frame_count), z))
    points["Bat5"] = points["Bat1"] + np.array([-500, 0, -100])
    return TrialSeries(
        trial_id="synthetic_batting_a",
        sample_name="case_a",
        athlete="case_a",
        action_type="batting",
        source_file="synthetic/non_identifying.c3d",
        frames=np.arange(frame_count),
        timestamps=np.arange(frame_count) / rate_hz,
        points=points,
    )


def make_pitching_trial() -> tuple[C3DTrial, list[str]]:
    frame_count = 120
    rate_hz = 100.0
    labels: list[str] = []
    series: list[np.ndarray] = []

    def add(name: str, xyz: tuple[float, float, float]) -> np.ndarray:
        value = np.tile(np.array(xyz, dtype=float), (frame_count, 1))
        labels.append(name)
        series.append(value)
        return value

    add("LASI", (-100, 0, 900))
    add("LPSI", (-100, -20, 900))
    add("RASI", (100, 0, 900))
    add("RPSI", (100, -20, 900))
    add("LSHO", (-150, 0, 1400))
    add("RSHO", (150, 0, 1400))
    left_knee = add("LKNE", (-100, 0, 700))
    left_knee[:, 2] = 700 + 500 * np.exp(-0.5 * ((np.arange(frame_count) - 20) / 4) ** 2)
    for name, xyz in (("LHEE", (-100, -30, 300)), ("LTOE", (-100, 80, 300))):
        foot = add(name, xyz)
        foot[:, 2] = np.where(np.arange(frame_count) < 45, 300, 20)
    add("RHEE", (100, -30, 20))
    add("RTOE", (100, 80, 20))
    add("LANK", (-100, 0, 20))
    add("RANK", (100, 0, 20))
    for name, xyz in (
        ("LFHD", (-50, 0, 1700)),
        ("RFHD", (50, 0, 1700)),
        ("LBHD", (-50, -30, 1700)),
        ("RBHD", (50, -30, 1700)),
    ):
        add(name, xyz)
    add("RELB", (250, 0, 1250))
    right_wrist_a = add("RWRA", (300, 0, 1200))
    right_wrist_b = add("RWRB", (310, 10, 1200))
    right_finger = add("RFIN", (320, 5, 1220))
    hand_x = 1000 / (1 + np.exp(-(np.arange(frame_count) - 80) / 2))
    for value in (right_wrist_a, right_wrist_b, right_finger):
        value[:, 0] += hand_x
    for name, base in (
        ("LKneeAngles", 30),
        ("LHipAngles", 40),
        ("RKneeAngles", 50),
        ("RAnkleAngles", 60),
        ("RShoulderAngles", 70),
        ("RElbowAngles", 80),
        ("RWristAngles", 90),
    ):
        angles = add(name, (0, 0, 0))
        angles[:, 0] = base + np.arange(frame_count) * 0.1
        angles[:, 1] = base + 100 + np.arange(frame_count) * 0.2
        angles[:, 2] = base + 200 + np.arange(frame_count) * 0.3
    xyz = np.stack(series, axis=1)
    points = np.concatenate((xyz, np.zeros((*xyz.shape[:2], 1))), axis=2)
    trial = C3DTrial(Path("synthetic_pitching.c3d"), labels, points, rate_hz, "mm")
    return trial, [clean_label(label) for label in labels]
