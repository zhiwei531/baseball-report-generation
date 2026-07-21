from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pipeline_config
import report_cli
from pipeline_config import (
    ConfigurationError,
    PreflightResult,
    load_final_report_config,
    load_pipeline_config,
    load_pitching_manifest,
    preflight_final_report,
)


ROOT = Path(__file__).resolve().parents[1]


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ConfigFixture:
    def __init__(self, root: Path, *, with_alignment: bool = True) -> None:
        self.root = root
        self.inputs = root / "inputs"
        self.inputs.mkdir()
        self.pitch_c3d = self.inputs / "pitch.c3d"
        self.coach_c3d = self.inputs / "coach.c3d"
        self.bat_c3d = self.inputs / "bat.c3d"
        self.video = self.inputs / "bat.mp4"
        self.model = self.inputs / "pose.task"
        self.pitch_video = self.inputs / "pitch.mp4"
        for path in (
            self.pitch_c3d,
            self.coach_c3d,
            self.bat_c3d,
            self.video,
            self.model,
            self.pitch_video,
        ):
            path.write_bytes(b"fixture")
        self.template = root / "template"
        self.template.mkdir()
        (self.template / "index.html").write_text("<html></html>", encoding="utf-8")
        self.c3d_dir = root / "c3d"
        self.c3d_dir.mkdir()
        self.peers = root / "peers"
        self.peers.mkdir()
        self.pitch_out = root / "pitch-report"
        self.combined_out = root / "combined-report"
        self.xlsx_out = root / "xlsx"
        self.manifest = root / "configs" / "pitching.json"
        write_json(
            self.manifest,
            {
                "athletes": [
                    {
                        "key": "player",
                        "name": "Player",
                        "role": "student",
                        "c3d": os.path.relpath(self.pitch_c3d, self.manifest.parent),
                    },
                    {
                        "key": "coach",
                        "name": "Coach",
                        "role": "coach",
                        "c3d": os.path.relpath(self.coach_c3d, self.manifest.parent),
                    },
                ]
            },
        )
        self.batting = root / "configs" / "batting.json"
        write_json(
            self.batting,
            {
                "root_dir": str(root),
                "c3d_dir": str(self.c3d_dir),
                "report_dir": str(self.combined_out),
                "pitch_report": str(self.pitch_out / "index.html"),
                "peers": str(self.peers),
                "alignment_dir": None,
                "video": str(self.video),
                "c3d_file": str(self.bat_c3d),
                "mediapipe_model": str(self.model),
                "video_capture_fps": 30,
                "video_event_frame": 120,
                "ready_valid_start_frame": 10,
                "xlsx_out_dir": str(self.xlsx_out),
                "sample_name": "player",
                "coach_sample_name": "coach",
                "player_slug": "player",
                "player_label": "Player",
                "trial_id": "trial_1",
            },
        )
        pitching: dict[str, object] = {
            "manifest": str(self.manifest),
            "template_dir": str(self.template),
            "out_dir": str(self.pitch_out),
        }
        if with_alignment:
            pitching["alignment"] = {
                "video": str(self.pitch_video),
                "c3d": str(self.pitch_c3d),
                "model": str(self.model),
                "out_dir": str(self.pitch_out / "alignment_2d"),
                "player_slug": "player",
                "player_label": "Player",
                "video_capture_fps": 30,
                "video_event_frame": 150,
                "min_visibility": 0,
            }
        self.final = root / "configs" / "final.json"
        write_json(
            self.final,
            {
                "root_dir": str(root),
                "batting_config": str(self.batting),
                "pitching": pitching,
            },
        )


class PipelineConfigTests(unittest.TestCase):
    def test_repository_relative_config_paths_do_not_depend_on_cwd(self) -> None:
        previous = Path.cwd()
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                final = load_final_report_config("configs/generated/bryan_final_report.json")
                batting = load_pipeline_config(
                    "configs/generated/bryan_coach_batting_pipeline.json"
                )
            finally:
                os.chdir(previous)
        self.assertEqual(final.config_path, ROOT / "configs/generated/bryan_final_report.json")
        self.assertEqual(
            batting.config_path,
            ROOT / "configs/generated/bryan_coach_batting_pipeline.json",
        )

    def test_manifest_paths_are_relative_to_manifest_and_roles_are_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ConfigFixture(Path(temp_dir))
            manifest = load_pitching_manifest(fixture.manifest)
            self.assertEqual(manifest.player.key, "player")
            self.assertEqual(manifest.athletes[0].c3d, fixture.pitch_c3d.resolve())
            payload = json.loads(fixture.manifest.read_text(encoding="utf-8"))
            payload["athletes"].append(payload["athletes"][0])
            write_json(fixture.manifest, payload)
            with self.assertRaisesRegex(ConfigurationError, "keys must be unique"):
                load_pitching_manifest(fixture.manifest)

    def test_legacy_top_level_array_manifest_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ConfigFixture(Path(temp_dir))
            payload = json.loads(fixture.manifest.read_text(encoding="utf-8"))
            write_json(fixture.manifest, payload["athletes"])
            manifest = load_pitching_manifest(fixture.manifest)
            self.assertEqual(manifest.player.key, "player")

    def test_preflight_resolves_valid_inputs_without_writing_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ConfigFixture(Path(temp_dir))
            config = load_final_report_config(fixture.final)
            result = preflight_final_report(config, execution="final")
            self.assertTrue(result.ok, result.errors)
            self.assertFalse(fixture.pitch_out.exists())
            self.assertFalse(fixture.combined_out.exists())
            self.assertIn(
                ("batting_report_dir", fixture.combined_out.resolve()),
                result.resolved_paths,
            )
            self.assertEqual(config.pitching_alignment.min_visibility, 0)

    def test_preflight_rejects_output_collision_and_pitch_contract_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ConfigFixture(Path(temp_dir), with_alignment=False)
            batting = json.loads(fixture.batting.read_text(encoding="utf-8"))
            batting["report_dir"] = str(fixture.pitch_out)
            batting["pitch_report"] = str(fixture.root / "wrong" / "index.html")
            write_json(fixture.batting, batting)
            result = preflight_final_report(
                load_final_report_config(fixture.final), execution="final"
            )
            self.assertFalse(result.ok)
            self.assertTrue(any("must be distinct" in item for item in result.errors))
            self.assertTrue(any("must match" in item for item in result.errors))
            with self.assertRaises(ConfigurationError):
                result.require_valid()

    def test_batting_video_requires_reviewed_timing_and_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            fixture = ConfigFixture(Path(temp_dir), with_alignment=False)
            batting = json.loads(fixture.batting.read_text(encoding="utf-8"))
            batting["video_event_frame"] = None
            batting["c3d_file"] = None
            write_json(fixture.batting, batting)
            result = preflight_final_report(
                load_final_report_config(fixture.final), execution="final"
            )
            self.assertTrue(
                any("alignment C3D is required" in item for item in result.errors)
            )
            self.assertTrue(any("reviewed" in item for item in result.errors))

    def test_tracked_final_configs_keep_distinct_report_outputs(self) -> None:
        for slug in ("7zai", "branden", "bryan", "green", "james", "youyou"):
            with self.subTest(slug=slug):
                final = load_final_report_config(
                    ROOT / "configs/generated" / f"{slug}_final_report.json"
                )
                batting = load_pipeline_config(final.batting_config)
                self.assertNotEqual(final.pitching_out_dir, batting.report_dir)
                self.assertEqual(final.pitch_html, batting.pitch_report)


class ReportCliBoundaryTests(unittest.TestCase):
    def test_final_execution_order_remains_pitching_then_batting(self) -> None:
        calls: list[str] = []
        result = PreflightResult("final", (), (), ())
        with (
            mock.patch.object(sys, "argv", ["report_cli.py", "final", "--config", "x.json"]),
            mock.patch.object(report_cli, "load_config", return_value=object()),
            mock.patch.object(report_cli, "preflight_final_report", return_value=result),
            mock.patch.object(report_cli, "print_preflight"),
            mock.patch.object(
                report_cli, "execute_pitching", side_effect=lambda *_args, **_kwargs: calls.append("pitching")
            ),
            mock.patch.object(
                report_cli, "execute_batting", side_effect=lambda *_args, **_kwargs: calls.append("batting")
            ),
        ):
            report_cli.main()
        self.assertEqual(calls, ["pitching", "batting"])

    def test_dry_run_performs_no_execution(self) -> None:
        result = PreflightResult("final", (), (), ())
        with (
            mock.patch.object(
                sys,
                "argv",
                ["report_cli.py", "final", "--config", "x.json", "--dry-run"],
            ),
            mock.patch.object(report_cli, "load_config", return_value=object()),
            mock.patch.object(report_cli, "preflight_final_report", return_value=result),
            mock.patch.object(report_cli, "print_preflight"),
            mock.patch.object(report_cli, "execute_pitching") as pitching,
            mock.patch.object(report_cli, "execute_batting") as batting,
        ):
            report_cli.main()
        pitching.assert_not_called()
        batting.assert_not_called()

    def test_execution_environment_preserves_explicit_cache_overrides(self) -> None:
        with mock.patch.dict(
            os.environ,
            {"MPLCONFIGDIR": "/custom/mpl", "XDG_CACHE_HOME": "/custom/cache"},
            clear=True,
        ):
            env = report_cli.execution_env()
        self.assertEqual(env["MPLCONFIGDIR"], "/custom/mpl")
        self.assertEqual(env["XDG_CACHE_HOME"], "/custom/cache")


if __name__ == "__main__":
    unittest.main()
