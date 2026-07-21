class BaseballReportError(Exception):
    """Base error for package-owned report-generation failures."""


class ConfigurationError(BaseballReportError):
    pass


class InputDataError(BaseballReportError):
    pass


class VideoProcessingError(InputDataError):
    pass


class C3DReadError(InputDataError):
    pass


class MarkerMappingError(InputDataError):
    pass


class CoordinateSystemError(InputDataError):
    pass


class PoseEstimationError(BaseballReportError):
    pass


class EventDetectionError(BaseballReportError):
    pass


class MetricCalculationError(BaseballReportError):
    pass


class ComparisonError(BaseballReportError):
    pass


class VisualizationError(BaseballReportError):
    pass


class ReportSchemaError(BaseballReportError):
    pass


class ReportBuildError(BaseballReportError):
    pass


class ExportError(BaseballReportError):
    pass
