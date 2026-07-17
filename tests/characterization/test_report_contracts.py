from __future__ import annotations

import os
import re
import unittest
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PITCH_TEMPLATE = ROOT / "reports" / "pitching_bryan_coach" / "index.html"
XLSX_BUILDER = ROOT / "scripts" / "build_batting_metrics_xlsx.mjs"


class ReportContractCharacterizationTests(unittest.TestCase):
    def test_canonical_pitching_template_dom_and_relative_asset_contract(self) -> None:
        html = PITCH_TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r'<article class="metric-card\b', html)), 16)
        self.assertEqual(len(re.findall(r"<section\b", html)), 7)
        self.assertEqual(len(re.findall(r'class="peer-range\b', html)), 28)
        self.assertIn("教练视角：专项问题", html)
        self.assertIn("研究者视角：动力链与时间曲线", html)
        self.assertIn("乐风U9同组表现", html)
        refs = re.findall(r'(?:src|href)=["\']([^"\']+)', html)
        local_refs = [
            ref.split("?", 1)[0].split("#", 1)[0]
            for ref in refs
            if not ref.startswith(("data:", "#", "http:", "https:", "mailto:", "javascript:"))
        ]
        self.assertTrue(local_refs)
        self.assertTrue(all(not Path(ref).is_absolute() and ".." not in Path(ref).parts for ref in local_refs))

    def test_xlsx_builder_metric_and_sheet_contract(self) -> None:
        source = XLSX_BUILDER.read_text(encoding="utf-8")
        order_block = re.search(r"const ORDER = \[(.*?)\];", source, re.DOTALL)
        self.assertIsNotNone(order_block)
        metric_ids = re.findall(r'"([a-z0-9_]+)"', order_block.group(1))
        self.assertEqual(len(metric_ids), 16)
        self.assertEqual(metric_ids[0], "ready_com_height_ratio")
        self.assertEqual(metric_ids[-1], "coach_rollover_forearm_roll_velocity_deg_s")
        self.assertNotIn("coach_hitting_zone_stability_score", metric_ids)
        self.assertEqual(
            re.findall(r'workbook\.worksheets\.add\("([^"]+)"\)', source),
            ["报告指标", "事件定位", "说明"],
        )
        self.assertIn("本报告按右打假设生成", source)
        self.assertIn("Bat1_Z 最低", source)

    @unittest.skipUnless(
        os.environ.get("BASEBALL_REPORT_LOCAL_COMBINED_HTML"),
        "set BASEBALL_REPORT_LOCAL_COMBINED_HTML for local generated-artifact validation",
    )
    def test_local_combined_report_references_existing_assets(self) -> None:
        report = Path(os.environ["BASEBALL_REPORT_LOCAL_COMBINED_HTML"])
        html = report.read_text(encoding="utf-8")
        refs = re.findall(r'(?:src|href)=["\']([^"\']+)', html)
        missing = []
        for ref in refs:
            clean = ref.split("?", 1)[0].split("#", 1)[0]
            if not clean or clean.startswith(("data:", "http:", "https:", "mailto:", "javascript:")):
                continue
            if not (report.parent / clean).exists():
                missing.append(clean)
        expected_missing = sorted(
            item
            for item in os.environ.get(
                "BASEBALL_REPORT_EXPECTED_MISSING_ASSETS", ""
            ).split(",")
            if item
        )
        self.assertEqual(sorted(missing), expected_missing)
        self.assertIn("pitch_assets/", html)

    @unittest.skipUnless(
        os.environ.get("BASEBALL_REPORT_LOCAL_XLSX"),
        "set BASEBALL_REPORT_LOCAL_XLSX for local workbook validation",
    )
    def test_local_xlsx_contains_expected_sheets(self) -> None:
        workbook = Path(os.environ["BASEBALL_REPORT_LOCAL_XLSX"])
        with zipfile.ZipFile(workbook) as archive:
            xml = ET.fromstring(archive.read("xl/workbook.xml"))
        namespace = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
        names = [sheet.attrib["name"] for sheet in xml.findall("x:sheets/x:sheet", namespace)]
        self.assertEqual(names, ["报告指标", "事件定位", "说明"])


if __name__ == "__main__":
    unittest.main()
