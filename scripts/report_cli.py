from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def run(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True, env=env)


def plot_env() -> dict[str, str]:
    env = os.environ.copy()
    env.setdefault("MPLCONFIGDIR", "/private/tmp/baseball_mpl_cache")
    env.setdefault("XDG_CACHE_HOME", "/private/tmp/baseball_xdg_cache")
    return env


def full_vicon_report(args: argparse.Namespace) -> None:
    pipeline = [
        PYTHON,
        "scripts/run_vicon_c3d_pipeline.py",
        "--input-dir",
        str(args.input_dir),
        "--reports-dir",
        str(args.reports_dir),
        "--assets-dir",
        str(args.assets_dir),
    ]
    if args.skip_render:
        pipeline.append("--skip-render")
    run(pipeline)
    run([PYTHON, "scripts/build_benchmark_report_html.py"])
    if not args.skip_export:
        run(["npm", "run", "export:report"])


def julian_coach_section(args: argparse.Namespace) -> None:
    metrics = args.report_dir / "batting_dashboard_metrics.csv"
    wide_metrics = args.report_dir / "batting_dashboard_metrics_wide.csv"

    run(
        [
            PYTHON,
            "scripts/build_batting_dashboard_metrics.py",
            "--points",
            str(args.points),
            "--out",
            str(metrics),
            "--wide-out",
            str(wide_metrics),
            "--ready-valid-start-frame",
            str(args.ready_valid_start_frame),
        ]
    )
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_event_gifs.py",
            "--metrics",
            str(metrics),
            "--out-dir",
            str(args.report_dir / "assets" / "vicon_reconstruction_events"),
        ],
        env=plot_env(),
    )
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_annotated_speed_gifs.py",
            "--metrics",
            str(metrics),
            "--points",
            str(args.point_summary),
            "--out-dir",
            str(args.report_dir / "assets" / "vicon_reconstruction_annotated"),
        ],
        env=plot_env(),
    )
    run(
        [
            PYTHON,
            "scripts/build_julian_coach_metrics_section.py",
            "--metrics",
            str(metrics),
            "--out",
            str(args.report_dir / "julian_coach_metrics_section.html"),
            "--pitch-report",
            str(args.pitch_report),
        ]
    )
    if args.apply_final_schema:
        run(
            [
                PYTHON,
                "scripts/apply_batting_coach_values.py",
                "--report-dir",
                str(args.report_dir),
                "--peers",
                str(args.peers),
            ]
        )
    if args.with_geometry_2d:
        run([PYTHON, "scripts/render_vicon_geometry_metrics_on_2d.py"], env=plot_env())
    if args.with_xlsx:
        env = os.environ.copy()
        env["METRICS_PATH"] = str(metrics)
        env["OUT_DIR"] = str(ROOT / "outputs" / "batting_metrics_excel")
        run(["node", "scripts/build_batting_metrics_xlsx.mjs"], env=env)


def c3d_pipeline(args: argparse.Namespace) -> None:
    cmd = [
        PYTHON,
        "scripts/run_vicon_c3d_pipeline.py",
        "--input-dir",
        str(args.input_dir),
        "--reports-dir",
        str(args.reports_dir),
        "--assets-dir",
        str(args.assets_dir),
    ]
    if args.skip_render:
        cmd.append("--skip-render")
    run(cmd)


def export_html(args: argparse.Namespace) -> None:
    cmd = ["node", "scripts/export_report_from_html.mjs"]
    if args.only:
        cmd.extend(["--only", args.only])
    if args.html:
        cmd.extend(["--html", str(args.html)])
    if args.pdf:
        cmd.extend(["--pdf", str(args.pdf)])
    if args.pptx:
        cmd.extend(["--pptx", str(args.pptx)])
    run(cmd)


def main() -> None:
    parser = argparse.ArgumentParser(description="Unified entry point for baseball report generation scripts.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("full-vicon-report", help="Build Vicon CSVs/assets, report.html, and PDF/PPTX exports.")
    p.add_argument("--input-dir", type=Path, default=ROOT.parent / "vicon_2026")
    p.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    p.add_argument("--assets-dir", type=Path, default=ROOT / "reports" / "assets")
    p.add_argument("--skip-render", action="store_true")
    p.add_argument("--skip-export", action="store_true")
    p.set_defaults(func=full_vicon_report)

    p = sub.add_parser("c3d-pipeline", help="Run C3D metrics and reconstruction asset generation.")
    p.add_argument("--input-dir", type=Path, default=ROOT.parent / "vicon_2026")
    p.add_argument("--reports-dir", type=Path, default=ROOT / "reports")
    p.add_argument("--assets-dir", type=Path, default=ROOT / "reports" / "assets")
    p.add_argument("--skip-render", action="store_true")
    p.set_defaults(func=c3d_pipeline)

    p = sub.add_parser(
        "batting-c3d-pipeline",
        help="Run C3D extraction and 3D reconstruction into the batting final-schema report folder.",
    )
    p.add_argument("--input-dir", type=Path, default=ROOT.parent / "vicon_2026")
    p.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "vicon_2026_julian_coach")
    p.add_argument("--skip-render", action="store_true")
    p.set_defaults(
        func=lambda args: c3d_pipeline(
            argparse.Namespace(
                input_dir=args.input_dir,
                reports_dir=args.report_dir,
                assets_dir=args.report_dir / "assets",
                skip_render=args.skip_render,
            )
        )
    )

    p = sub.add_parser("benchmark-html", help="Build report.html from existing report CSV/assets.")
    p.set_defaults(func=lambda _args: run([PYTHON, "scripts/build_benchmark_report_html.py"]))

    p = sub.add_parser("export-html", help="Export report.html to PDF/PPTX.")
    p.add_argument("--only", choices=["pdf", "pptx"], default=None)
    p.add_argument("--html", type=Path, default=None)
    p.add_argument("--pdf", type=Path, default=None)
    p.add_argument("--pptx", type=Path, default=None)
    p.set_defaults(func=export_html)

    p = sub.add_parser("julian-coach-section", help="Build Julian/Coach batting metrics section and key images.")
    p.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "vicon_2026_julian_coach")
    p.add_argument("--points", type=Path, default=ROOT / "reports" / "vicon_2026_julian_coach" / "vicon_2026_points_all.csv")
    p.add_argument("--point-summary", type=Path, default=ROOT / "reports" / "vicon_2026_julian_coach" / "vicon_2026_point_summary.csv")
    p.add_argument("--peers", type=Path, default=ROOT / "outputs" / "batting_metrics_excel" / "all_players")
    p.add_argument("--pitch-report", type=Path, default=ROOT.parent / "julian_pitch_template_report_2026-07-06" / "index.html")
    p.add_argument("--ready-valid-start-frame", type=int, default=770)
    p.add_argument("--with-geometry-2d", action="store_true")
    p.add_argument("--with-xlsx", action="store_true")
    p.add_argument("--apply-final-schema", action="store_true")
    p.set_defaults(func=julian_coach_section)

    p = sub.add_parser("apply-final-schema", help="Apply the final vicon_2026_julian_coach 4 HTML polish pass.")
    p.add_argument("--report-dir", type=Path, default=ROOT / "reports" / "vicon_2026_julian_coach")
    p.add_argument("--peers", type=Path, default=ROOT / "outputs" / "batting_metrics_excel" / "all_players")
    p.set_defaults(
        func=lambda args: run(
            [
                PYTHON,
                "scripts/apply_batting_coach_values.py",
                "--report-dir",
                str(args.report_dir),
                "--peers",
                str(args.peers),
            ]
        )
    )

    p = sub.add_parser("geometry-2d", help="Render Vicon-valued metric annotations on aligned 2D skeleton frames.")
    p.set_defaults(func=lambda _args: run([PYTHON, "scripts/render_vicon_geometry_metrics_on_2d.py"], env=plot_env()))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
