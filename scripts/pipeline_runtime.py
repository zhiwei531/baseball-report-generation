from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping, Sequence


LOGGER = logging.getLogger("baseball_report.pipeline")
RUNTIME_SCHEMA_VERSION = "pipeline_run.v1"


@dataclass(frozen=True)
class StageExecutionResult:
    stage_name: str
    success: bool
    command: tuple[str, ...]
    input_summary: Mapping[str, object] = field(default_factory=dict)
    output_summary: Mapping[str, object] = field(default_factory=dict)
    artifacts: tuple[Path, ...] = ()
    warnings: tuple[str, ...] = ()
    duration_seconds: float = 0.0

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["command"] = list(self.command)
        payload["artifacts"] = [str(path) for path in self.artifacts]
        payload["warnings"] = list(self.warnings)
        return payload


class PipelineStageError(RuntimeError):
    def __init__(self, stage_name: str, message: str) -> None:
        super().__init__(f"{stage_name}: {message}")
        self.stage_name = stage_name


def configure_logging(level: str = "INFO") -> None:
    numeric_level = getattr(logging, level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"unknown log level: {level}")
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def require_artifacts(stage_name: str, artifacts: Sequence[Path]) -> tuple[Path, ...]:
    resolved = tuple(Path(path).resolve() for path in artifacts)
    missing = [str(path) for path in resolved if not path.exists()]
    if missing:
        raise PipelineStageError(stage_name, "missing required artifacts: " + ", ".join(missing))
    return resolved


def run_command_stage(
    stage_name: str,
    command: Sequence[str | Path],
    *,
    cwd: Path,
    env: Mapping[str, str] | None = None,
    input_summary: Mapping[str, object] | None = None,
    required_artifacts: Sequence[Path] = (),
) -> StageExecutionResult:
    normalized = tuple(str(part) for part in command)
    started = time.perf_counter()
    LOGGER.info("stage=%s status=started command=%s", stage_name, " ".join(normalized))
    try:
        subprocess.run(normalized, cwd=cwd, check=True, env=None if env is None else dict(env))
    except subprocess.CalledProcessError as exc:
        duration = time.perf_counter() - started
        LOGGER.error(
            "stage=%s status=failed exit_code=%s duration_seconds=%.3f",
            stage_name,
            exc.returncode,
            duration,
        )
        raise PipelineStageError(stage_name, f"command exited with code {exc.returncode}") from exc
    artifacts = require_artifacts(stage_name, required_artifacts)
    duration = time.perf_counter() - started
    result = StageExecutionResult(
        stage_name=stage_name,
        success=True,
        command=normalized,
        input_summary=dict(input_summary or {}),
        output_summary={"artifact_count": len(artifacts)},
        artifacts=artifacts,
        duration_seconds=duration,
    )
    LOGGER.info(
        "stage=%s status=success artifacts=%d duration_seconds=%.3f",
        stage_name,
        len(artifacts),
        duration,
    )
    return result


def write_pipeline_manifest(
    path: Path,
    *,
    pipeline_name: str,
    stages: Sequence[StageExecutionResult],
    metadata: Mapping[str, object] | None = None,
) -> Path:
    output = path.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": RUNTIME_SCHEMA_VERSION,
        "pipeline_name": pipeline_name,
        "success": all(stage.success for stage in stages),
        "stage_count": len(stages),
        "duration_seconds": sum(stage.duration_seconds for stage in stages),
        "metadata": dict(metadata or {}),
        "stages": [stage.to_dict() for stage in stages],
    }
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)
    LOGGER.info("pipeline=%s status=success manifest=%s", pipeline_name, output)
    return output
