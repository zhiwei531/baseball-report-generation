from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from baseball_report.core.errors import BaseballReportError
from baseball_report.reporting.validation import load_report_payload


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_REPORT_CLI = REPO_ROOT / "scripts" / "report_cli.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m baseball_report")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("pitching", "batting", "final"):
        child = subparsers.add_parser(name, help=f"Run the implemented {name} report pipeline.")
        child.add_argument("--config", type=Path, required=True)
        child.add_argument("--dry-run", action="store_true")
        child.add_argument("--log-level", default="INFO")
        child.add_argument("--run-manifest", type=Path)
        if name in {"pitching", "final"}:
            child.add_argument("--skip-pitching-alignment", action="store_true")
    validate = subparsers.add_parser("validate-report", help="Validate ReportData 1.0 JSON.")
    validate.add_argument("--input", type=Path, required=True)
    return parser


def _package_environment() -> dict[str, str]:
    env = os.environ.copy()
    required_paths = (str(REPO_ROOT / "src"), str(REPO_ROOT / "scripts"))
    existing = tuple(part for part in env.get("PYTHONPATH", "").split(os.pathsep) if part)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys((*required_paths, *existing)))
    return env


def _legacy_command(args: argparse.Namespace) -> list[str]:
    command = [
        sys.executable,
        str(LEGACY_REPORT_CLI),
        args.command,
        "--config",
        str(args.config),
        "--log-level",
        args.log_level,
    ]
    if args.run_manifest is not None:
        command.extend(["--run-manifest", str(args.run_manifest)])
    if args.dry_run:
        command.append("--dry-run")
    if getattr(args, "skip_pitching_alignment", False):
        command.append("--skip-pitching-alignment")
    return command


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-report":
            payload = load_report_payload(args.input)
            print(
                json.dumps(
                    {
                        "valid": True,
                        "schema_version": payload["schema_version"],
                        "report_id": payload["report_id"],
                        "motions": len(payload["motions"]),
                        "metrics": len(payload["metrics"]),
                        "sections": len(payload["sections"]),
                        "assets": len(payload["assets"]),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                )
            )
            return 0
        completed = subprocess.run(_legacy_command(args), cwd=REPO_ROOT, env=_package_environment())
        return completed.returncode
    except BaseballReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
