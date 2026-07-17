from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from baseball_report.legacy.batting_csv import adapt_batting_metrics_csv
from baseball_report.legacy.pitching_summary import adapt_pitching_summary_json

from .adapters import build_report_data_from_legacy, write_report_data
from .composition import compose_report_view
from .validation import load_report_payload
from baseball_report.core.serialization import dumps_deterministic


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build stable ReportData 1.0 JSON from current legacy report artifacts."
    )
    parser.add_argument("--batting", type=Path)
    parser.add_argument("--pitching", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--view-output", type=Path)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--subject-id", required=True)
    parser.add_argument("--subject-label", required=True)
    parser.add_argument("--subject-key", action="append", default=[])
    args = parser.parse_args()
    if args.batting is None and args.pitching is None:
        parser.error("at least one of --batting or --pitching is required")

    adapted = []
    if args.batting is not None:
        adapted.append(adapt_batting_metrics_csv(args.batting))
    if args.pitching is not None:
        adapted.append(adapt_pitching_summary_json(args.pitching))
    report = build_report_data_from_legacy(
        adapted,
        report_id=args.report_id,
        created_at=datetime.now(timezone.utc).isoformat(),
        subject_id=args.subject_id,
        subject_display_name=args.subject_label,
        subject_keys=args.subject_key or (args.subject_id,),
    )
    output = write_report_data(args.output, report)
    load_report_payload(output)
    if args.view_output is not None:
        view_output = args.view_output.resolve()
        view_output.parent.mkdir(parents=True, exist_ok=True)
        temporary = view_output.with_suffix(view_output.suffix + ".tmp")
        temporary.write_text(dumps_deterministic(compose_report_view(report)), encoding="utf-8")
        temporary.replace(view_output)
    print(output)


if __name__ == "__main__":
    main()
