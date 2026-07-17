from __future__ import annotations

import copy
import math
import unittest

from baseball_report.core.enums import SubjectRole
from baseball_report.core.errors import ReportSchemaError
from baseball_report.core.provenance import Provenance
from baseball_report.reporting.models import ReportData, SubjectMetadata
from baseball_report.reporting.validation import validate_report_payload


def minimal_payload() -> dict[str, object]:
    report = ReportData(
        schema_version="1.0.0",
        report_id="schema-test",
        created_at="2026-07-17T12:00:00+08:00",
        subject=SubjectMetadata("subject", "Subject", SubjectRole.STUDENT),
        motions=(),
        events=(),
        metrics=(),
        comparisons=(),
        charts=(),
        assets=(),
        sections=(),
        warnings=(),
        provenance=Provenance("test", "schema-test", "test"),
    )
    return report.to_dict()


class ReportSchemaValidationTests(unittest.TestCase):
    def test_valid_stable_payload_round_trips(self) -> None:
        payload = minimal_payload()
        self.assertIs(validate_report_payload(payload), payload)

    def test_builder_boundary_rejects_internal_schema_missing_fields_and_non_finite(self) -> None:
        payload = minimal_payload()
        payload["schema_version"] = "0.9.0"
        with self.assertRaisesRegex(ReportSchemaError, "1.0"):
            validate_report_payload(payload)
        payload = minimal_payload()
        del payload["sections"]
        with self.assertRaisesRegex(ReportSchemaError, "missing fields"):
            validate_report_payload(payload)
        payload = minimal_payload()
        payload["subject"]["metadata"] = {"bad": math.nan}  # type: ignore[index]
        with self.assertRaisesRegex(ReportSchemaError, "NaN"):
            validate_report_payload(payload)

    def test_unknown_section_and_metric_references_are_rejected(self) -> None:
        payload = minimal_payload()
        payload["sections"] = [
            {
                "section_id": "bad",
                "order": 0,
                "title_zh": "bad",
                "title_en": None,
                "status": "available",
                "metric_ids": ["missing"],
                "event_ids": [],
                "chart_ids": [],
                "asset_ids": [],
                "metadata": {},
            }
        ]
        with self.assertRaisesRegex(ReportSchemaError, "unknown metric_ids"):
            validate_report_payload(payload)
        bad = copy.deepcopy(minimal_payload())
        bad["assets"] = [
            {
                "asset_id": "a",
                "kind": "image",
                "file_ref": "/absolute.png",
                "mime_type": "image/png",
                "sequence_ids": [],
                "metric_ids": [],
                "event_ids": [],
                "quality": "valid",
                "provenance": None,
                "metadata": {},
            }
        ]
        with self.assertRaises(ReportSchemaError):
            validate_report_payload(bad)

    def test_subject_order_and_artifact_references_are_validated(self) -> None:
        payload = minimal_payload()
        payload["subject"]["subject_id"] = ""  # type: ignore[index]
        with self.assertRaisesRegex(ReportSchemaError, "subject_id"):
            validate_report_payload(payload)

        payload = minimal_payload()
        payload["sections"] = [
            {
                "section_id": "bad-order",
                "order": "0",
                "title_zh": "bad",
                "title_en": None,
                "status": "available",
                "metric_ids": [],
                "event_ids": [],
                "chart_ids": [],
                "asset_ids": [],
                "metadata": {},
            }
        ]
        with self.assertRaisesRegex(ReportSchemaError, "non-negative integer"):
            validate_report_payload(payload)

        payload = minimal_payload()
        payload["charts"] = [
            {
                "artifact_id": "chart",
                "sequence_ids": ["missing-motion"],
                "kind": "line",
                "title_zh": "chart",
                "title_en": None,
                "data_ref": "assets/chart.json",
                "file_ref": None,
                "mime_type": "application/json",
                "event_ids": [],
                "metric_ids": [],
                "provenance": {"source_type": "test", "source_id": "x", "algorithm_id": "x"},
            }
        ]
        with self.assertRaisesRegex(ReportSchemaError, "unknown sequence_ids"):
            validate_report_payload(payload)


if __name__ == "__main__":
    unittest.main()
