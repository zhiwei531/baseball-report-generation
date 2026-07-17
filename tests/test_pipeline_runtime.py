from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pipeline_runtime as runtime


class PipelineRuntimeTests(unittest.TestCase):
    def test_successful_stage_records_command_artifacts_and_duration(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "already-created.json"
            artifact.write_text("{}", encoding="utf-8")
            result = runtime.run_command_stage(
                "smoke",
                [sys.executable, "-c", "pass"],
                cwd=root,
                input_summary={"trial_id": "synthetic"},
                required_artifacts=(artifact,),
            )
        self.assertTrue(result.success)
        self.assertEqual(result.stage_name, "smoke")
        self.assertEqual(result.output_summary["artifact_count"], 1)
        self.assertGreaterEqual(result.duration_seconds, 0.0)

    def test_failed_command_and_missing_artifact_raise_stage_scoped_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch.object(
                runtime.subprocess,
                "run",
                side_effect=subprocess.CalledProcessError(7, ["bad"]),
            ):
                with self.assertRaisesRegex(runtime.PipelineStageError, "failed_stage.*code 7"):
                    runtime.run_command_stage("failed_stage", ["bad"], cwd=root)
            with self.assertRaisesRegex(runtime.PipelineStageError, "missing required artifacts"):
                runtime.run_command_stage(
                    "artifact_check",
                    [sys.executable, "-c", "pass"],
                    cwd=root,
                    required_artifacts=(root / "missing",),
                )

    def test_manifest_is_machine_readable_and_stage_ordered(self) -> None:
        stage = runtime.StageExecutionResult(
            stage_name="load",
            success=True,
            command=("python", "load.py"),
            artifacts=(Path("artifact.csv"),),
            duration_seconds=0.25,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            output = runtime.write_pipeline_manifest(
                Path(temp_dir) / "run.json",
                pipeline_name="test_pipeline",
                stages=(stage,),
                metadata={"source": "synthetic"},
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], "pipeline_run.v1")
        self.assertEqual(payload["pipeline_name"], "test_pipeline")
        self.assertEqual(payload["stage_count"], 1)
        self.assertEqual(payload["stages"][0]["stage_name"], "load")


if __name__ == "__main__":
    unittest.main()
