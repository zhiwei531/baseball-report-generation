from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from baseball_report.visualization.manifest import discover_report_assets


class VisualizationManifestTests(unittest.TestCase):
    def test_discovers_portable_existing_assets_without_guessing_metric_links(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "assets" / "charts").mkdir(parents=True)
            (root / "assets" / "charts" / "speed.png").write_bytes(b"png")
            (root / "assets" / "movement.gif").write_bytes(b"gif")
            (root / "assets" / "video.mp4").write_bytes(b"mp4")
            (root / "assets" / "._sidecar.png").write_bytes(b"sidecar")
            (root / "analysis_report_data.json").write_text("{}", encoding="utf-8")
            assets = discover_report_assets(root)
        self.assertEqual(
            [asset.file_ref for asset in assets],
            ["assets/charts/speed.png", "assets/movement.gif", "assets/video.mp4"],
        )
        self.assertEqual([asset.kind for asset in assets], ["image", "animation", "video"])
        self.assertEqual([asset.mime_type for asset in assets], ["image/png", "image/gif", "video/mp4"])
        self.assertTrue(all(not asset.metric_ids and not asset.event_ids for asset in assets))
        self.assertTrue(all(not Path(asset.file_ref).is_absolute() for asset in assets))

    def test_missing_root_is_an_empty_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            self.assertEqual(discover_report_assets(Path(temp_dir) / "missing"), ())


if __name__ == "__main__":
    unittest.main()
