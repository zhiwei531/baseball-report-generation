from __future__ import annotations

import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

from baseball_report.cli import main
from baseball_report.core.enums import SubjectRole
from baseball_report.core.provenance import Provenance
from baseball_report.reporting.models import ReportData, SubjectMetadata


class PackageCliTests(unittest.TestCase):
    def test_validate_report_prints_machine_readable_summary(self) -> None:
        report = ReportData(
            schema_version="1.0.0",
            report_id="cli-test",
            created_at="2026-07-17T12:00:00+08:00",
            subject=SubjectMetadata("player", "Player", SubjectRole.STUDENT),
            motions=(),
            events=(),
            metrics=(),
            comparisons=(),
            charts=(),
            assets=(),
            sections=(),
            warnings=(),
            provenance=Provenance("test", "cli", "test"),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "report.json"
            path.write_text(report.to_json(), encoding="utf-8")
            with mock.patch("builtins.print") as output:
                self.assertEqual(main(["validate-report", "--input", str(path)]), 0)
        summary = json.loads(output.call_args.args[0])
        self.assertEqual(summary["schema_version"], "1.0.0")
        self.assertTrue(summary["valid"])

    def test_pipeline_commands_preserve_implemented_flags_and_exit_code(self) -> None:
        with mock.patch(
            "baseball_report.cli.subprocess.run", return_value=SimpleNamespace(returncode=7)
        ) as run:
            code = main(
                [
                    "final",
                    "--config",
                    "configs/final.json",
                    "--dry-run",
                    "--log-level",
                    "DEBUG",
                    "--run-manifest",
                    "run.json",
                    "--skip-pitching-alignment",
                ]
            )
        self.assertEqual(code, 7)
        command = run.call_args.args[0]
        self.assertIn("scripts/report_cli.py", command[1])
        self.assertEqual(command[2], "final")
        self.assertIn("--dry-run", command)
        self.assertIn("--skip-pitching-alignment", command)
        self.assertEqual(run.call_args.kwargs["cwd"], Path(command[1]).parents[1])


if __name__ == "__main__":
    unittest.main()
