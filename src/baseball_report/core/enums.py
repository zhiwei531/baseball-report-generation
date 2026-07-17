from __future__ import annotations

from enum import Enum


class StringEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class SourceType(StringEnum):
    C3D = "c3d"
    VIDEO = "video"
    MEDIAPIPE = "mediapipe"
    RTMPOSE = "rtmpose"
    LEGACY_CSV = "legacy_csv"
    LEGACY_JSON = "legacy_json"


class MotionType(StringEnum):
    BATTING = "batting"
    PITCHING = "pitching"


class Side(StringEnum):
    LEFT = "left"
    RIGHT = "right"


class Handedness(StringEnum):
    LEFT = "left"
    RIGHT = "right"


class SubjectRole(StringEnum):
    STUDENT = "student"
    COACH = "coach"
    REFERENCE = "reference"
    UNKNOWN = "unknown"


class CoordinateProfile(StringEnum):
    LEGACY_VICON_Z_UP_MM = "legacy_vicon_z_up_mm"
    MEDIAPIPE_IMAGE_NORMALIZED = "mediapipe_image_normalized"
    MEDIAPIPE_WORLD = "mediapipe_world"
    RTMPOSE_IMAGE = "rtmpose_image"
    UNKNOWN = "unknown"


class QualityStatus(StringEnum):
    VALID = "valid"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNCERTAIN = "uncertain"


class WarningSeverity(StringEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
