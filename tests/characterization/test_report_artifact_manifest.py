from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.capture_report_artifact_baseline import capture_report_artifacts


class ReportArtifactManifestTests(unittest.TestCase):
    def test_manifest_records_schema_dom_assets_charts_and_workbook(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            pitching = root / "pitching"
            combined = root / "combined"
            (pitching / "assets" / "analyst_charts").mkdir(parents=True)
            combined.mkdir()
            (pitching / "assets" / "analyst_charts" / "curve.png").write_bytes(b"png")
            (pitching / "index.html").write_text(
                '<section><article class="metric-card"><div class="peer-range"></div>'
                '<img src="assets/analyst_charts/curve.png"></article></section>',
                encoding="utf-8",
            )
            combined_html = combined / "report.html"
            combined_html.write_text('<section><img src="missing.png"></section>', encoding="utf-8")
            (combined / "batting_dashboard_metrics.csv").write_text(
                "trial_id,metric_key\nt1,m1\n", encoding="utf-8"
            )
            (pitching / "pitch_metrics_summary.json").write_text(
                '{"assumptions":{},"athletes":[{"events":{"release":1},"values":{"m2":2}}]}',
                encoding="utf-8",
            )
            xlsx = root / "report.xlsx"
            workbook_xml = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                '<sheets><sheet name="报告指标" sheetId="1"/></sheets></workbook>'
            )
            with zipfile.ZipFile(xlsx, "w") as archive:
                archive.writestr("xl/workbook.xml", workbook_xml)
            manifest = capture_report_artifacts(
                pitching_dir=pitching,
                combined_dir=combined,
                combined_html=combined_html,
                xlsx=xlsx,
            )
        self.assertEqual(manifest["pitching_html"]["metric_card_count"], 1)
        self.assertEqual(manifest["pitching_html"]["missing_local_references"], [])
        self.assertEqual(manifest["combined_html"]["missing_local_references"], ["missing.png"])
        self.assertEqual(manifest["pitching_directory"]["chart_artifact_count"], 1)
        self.assertEqual(manifest["batting_schema"]["metric_ids"], ["m1"])
        self.assertEqual(manifest["pitching_schema"]["event_ids"], ["release"])
        self.assertEqual(manifest["xlsx"]["sheet_names"], ["报告指标"])


if __name__ == "__main__":
    unittest.main()
