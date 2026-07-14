import fs from "node:fs/promises";
import fsSync from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DEFAULT_HTML = path.join(ROOT, "report.html");
const DEFAULT_PDF = path.join(ROOT, "output/pdf/report_from_html.pdf");
const DEFAULT_PPTX = path.join(ROOT, "output/pptx/report_from_html.pptx");
const DEFAULT_WORK_DIR = path.join("/private/tmp", "baseball-report-html-export");

const C = {
  bg: "#f5f7fb",
  ink: "#101828",
  body: "#344054",
  muted: "#667085",
  blue: "#2563eb",
  border: "#d0d5dd",
  white: "#ffffff",
};

function parseArgs(argv) {
  const args = {
    html: DEFAULT_HTML,
    pdf: DEFAULT_PDF,
    pptx: DEFAULT_PPTX,
    workDir: DEFAULT_WORK_DIR,
    viewportWidth: 1280,
    viewportHeight: 900,
    pdfMediaScale: 0.82,
    pptxMediaScale: 0.9,
    only: "all",
  };
  for (let i = 0; i < argv.length; i++) {
    const key = argv[i];
    const value = argv[i + 1];
    if (key === "--html") args.html = path.resolve(value), i++;
    else if (key === "--pdf") args.pdf = path.resolve(value), i++;
    else if (key === "--pptx") args.pptx = path.resolve(value), i++;
    else if (key === "--work-dir") args.workDir = path.resolve(value), i++;
    else if (key === "--viewport-width") args.viewportWidth = Number(value), i++;
    else if (key === "--viewport-height") args.viewportHeight = Number(value), i++;
    else if (key === "--pdf-media-scale") args.pdfMediaScale = Number(value), i++;
    else if (key === "--pptx-media-scale") args.pptxMediaScale = Number(value), i++;
    else if (key === "--only") args.only = value, i++;
    else if (key === "--help" || key === "-h") {
      console.log(`Usage:
  node scripts/export_report_from_html.mjs [options]

Options:
  --html PATH              Source HTML report. Default: report.html
  --pdf PATH               Output PDF. Default: output/pdf/report_from_html.pdf
  --pptx PATH              Output PPTX. Default: output/pptx/report_from_html.pptx
  --work-dir PATH          Screenshot/QA workspace. Default: /private/tmp/baseball-report-html-export
  --only all|pdf|pptx      Export subset. Default: all
  --viewport-width N       Browser viewport width. Default: 1280
  --viewport-height N      Browser viewport height. Default: 900
  --pdf-media-scale N      Scale report images/SVGs in PDF export. Default: 0.82
  --pptx-media-scale N     Scale captured report blocks in PPTX export. Default: 0.9
`);
      process.exit(0);
    }
  }
  if (!["all", "pdf", "pptx"].includes(args.only)) {
    throw new Error("--only must be one of: all, pdf, pptx");
  }
  if (!Number.isFinite(args.pdfMediaScale) || args.pdfMediaScale <= 0 || args.pdfMediaScale > 1) {
    throw new Error("--pdf-media-scale must be a number greater than 0 and at most 1");
  }
  if (!Number.isFinite(args.pptxMediaScale) || args.pptxMediaScale <= 0 || args.pptxMediaScale > 1) {
    throw new Error("--pptx-media-scale must be a number greater than 0 and at most 1");
  }
  return args;
}

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (err) {
    throw new Error(
      [
        "Missing dependency: playwright.",
        "Install it in baseball-analysis with:",
        "  npm install --save-dev playwright",
        "  npx playwright install chromium",
        "",
        `Original error: ${err.message}`,
      ].join("\n"),
    );
  }
}

async function loadArtifactTool() {
  const packageDirs = [
    path.join(ROOT, "node_modules", "@oai", "artifact-tool"),
    path.join(
      process.env.HOME || "",
      ".cache",
      "codex-runtimes",
      "codex-primary-runtime",
      "dependencies",
      "node",
      "node_modules",
      "@oai",
      "artifact-tool",
    ),
  ];
  const entryCandidates = packageDirs.flatMap((dir) => [
    path.join(dir, "dist", "node", "artifact_tool.mjs"),
    path.join(dir, "dist", "artifact_tool.mjs"),
  ]);
  const entry = entryCandidates.find((candidate) => fsSync.existsSync(candidate));
  if (!entry) {
    throw new Error(
      [
        "Missing dependency: @oai/artifact-tool.",
        "This package is provided by the Codex presentations runtime.",
        "Run inside Codex, or place @oai/artifact-tool in node_modules before exporting PPTX.",
      ].join("\n"),
    );
  }
  return await import(pathToFileURL(entry).href);
}

async function ensureDir(fileOrDir, isDir = false) {
  await fs.mkdir(isDir ? fileOrDir : path.dirname(fileOrDir), { recursive: true });
}

async function waitForImages(page) {
  await page.evaluate(async () => {
    document.querySelectorAll("img").forEach((img) => {
      img.loading = "eager";
      img.decoding = "sync";
    });
    const images = Array.from(document.images);
    const timeout = new Promise((resolve) => setTimeout(resolve, 8000));
    const imageReady = Promise.all(
      images.map(
        (img) =>
          new Promise((resolve) => {
            if (img.complete) return resolve();
            img.addEventListener("load", resolve, { once: true });
            img.addEventListener("error", resolve, { once: true });
          }),
      ),
    );
    await Promise.race([imageReady, timeout]);
  });
}

async function forceLoadLazyMedia(page) {
  await page.evaluate(async () => {
    document.querySelectorAll("img").forEach((img) => {
      img.loading = "eager";
      img.decoding = "sync";
    });
    const step = Math.max(360, Math.floor(window.innerHeight * 0.65));
    for (let y = 0; y < document.body.scrollHeight; y += step) {
      window.scrollTo(0, y);
      await new Promise((resolve) => setTimeout(resolve, 90));
    }
    window.scrollTo(0, 0);
  });
  await waitForImages(page);
  await page.waitForTimeout(800);
}

async function preparePage(page, htmlPath, viewportWidth, viewportHeight, pdfMediaScale) {
  const pdfMediaPct = `${Math.round(pdfMediaScale * 100)}%`;
  await page.setViewportSize({ width: viewportWidth, height: viewportHeight });
  await page.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await page.addStyleTag({
    content: `
      @page { size: A4; margin: 9mm; }
      html.export-mode { background: ${C.bg}; }
      html.export-mode body { background: ${C.bg}; }
      html.export-mode .topbar { position: static; }
      html.export-mode main { max-width: 1180px; }
      html.export-mode .table-scroll,
      html.export-mode .line-chart-scroll,
      html.export-mode .mini-chart-scroll,
      html.export-mode .dot-plot-scroll {
        overflow: visible !important;
        max-height: none !important;
        padding-bottom: 0 !important;
      });
      html.export-mode table {
        min-width: 0 !important;
        width: 100% !important;
        table-layout: fixed;
      });
      html.export-mode th,
      html.export-mode td {
        overflow-wrap: anywhere;
        word-break: break-word;
      }
      html.export-mode .training {
        overflow: visible !important;
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
      }
      html.export-mode .line-chart-svg,
      html.export-mode .dot-compare-svg,
      html.export-mode .wide-svg {
        width: 100% !important;
        max-width: 100% !important;
      }
      html.export-mode .section,
      html.export-mode .visual-card,
      html.export-mode .metric-card,
      html.export-mode .card {
        break-inside: avoid;
        page-break-inside: avoid;
      }
      html.export-mode.export-ppt .visual-card {
        box-shadow: none;
      }
      html.export-mode.export-pdf .hero-evidence,
      html.export-mode.export-pdf .visual-card figure,
      html.export-mode.export-pdf .visual-card .line-chart-scroll,
      html.export-mode.export-pdf .visual-card .mini-chart-scroll,
      html.export-mode.export-pdf .visual-card .dot-plot-scroll,
      html.export-mode.export-pdf .visual-card > svg,
      html.export-mode.export-pdf .visual-card .radar,
      html.export-mode.export-pdf .visual-card .pose-svg,
      html.export-mode.export-pdf .visual-card .wide-svg {
        max-width: ${pdfMediaPct} !important;
        margin-left: auto !important;
        margin-right: auto !important;
      }
      html.export-mode.export-pdf .visual-card img,
      html.export-mode.export-pdf .visual-card svg {
        max-width: ${pdfMediaPct} !important;
        height: auto !important;
        margin-left: auto !important;
        margin-right: auto !important;
      }
      html.export-mode.export-pdf .hero-evidence img {
        max-width: 100% !important;
      }
      html.export-mode.export-pdf main {
        max-width: 1160px !important;
        padding-top: 16px !important;
        padding-bottom: 0 !important;
      }
      html.export-mode.export-pdf .section {
        margin-top: 20px !important;
        break-inside: auto !important;
        page-break-inside: auto !important;
      }
      html.export-mode.export-pdf footer {
        display: none !important;
      }
      html.export-mode.export-pdf .section-title {
        margin-bottom: 10px !important;
      }
      html.export-mode.export-pdf .module-note {
        padding: 8px 10px !important;
        margin-bottom: 8px !important;
      }
      html.export-mode.export-pdf .module-note p {
        font-size: 12px !important;
        line-height: 17px !important;
      }
      html.export-mode.export-pdf h2 {
        font-size: 23px !important;
        line-height: 29px !important;
      }
      html.export-mode.export-pdf h3 {
        font-size: 19px !important;
        line-height: 25px !important;
      }
      html.export-mode.export-pdf h4,
      html.export-mode.export-pdf .visual-card h4 {
        font-size: 14px !important;
        line-height: 19px !important;
      }
      html.export-mode.export-pdf p,
      html.export-mode.export-pdf .visual-card p,
      html.export-mode.export-pdf .metric-card p,
      html.export-mode.export-pdf .card p {
        font-size: 12px !important;
        line-height: 17px !important;
        margin-top: 5px !important;
      }
      html.export-mode.export-pdf .grid-2 {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 10px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .grid-3 {
        grid-template-columns: repeat(3, minmax(0, 1fr)) !important;
        gap: 10px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .grid {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        gap: 10px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .card,
      html.export-mode.export-pdf .metric-card,
      html.export-mode.export-pdf .visual-card {
        padding: 11px !important;
        border-radius: 14px !important;
        border-width: 1px !important;
        -webkit-box-decoration-break: clone;
        box-decoration-break: clone;
        break-inside: auto !important;
        page-break-inside: auto !important;
      }
      html.export-mode.export-pdf .compact-metrics .metric-card {
        padding: 10px !important;
      }
      html.export-mode.export-pdf .metric-value {
        font-size: 19px !important;
        line-height: 23px !important;
        margin: 5px 0 3px !important;
      }
      html.export-mode.export-pdf .badge {
        font-size: 10px !important;
        padding: 2px 6px !important;
      }
      html.export-mode.export-pdf .priority-list {
        gap: 8px !important;
      }
      html.export-mode.export-pdf .priority-item {
        gap: 10px !important;
        padding: 8px !important;
        border-radius: 14px !important;
        break-inside: avoid-page !important;
        page-break-inside: avoid !important;
      }
      html.export-mode.export-pdf .rank {
        width: 32px !important;
        height: 32px !important;
        font-size: 15px !important;
      }
      html.export-mode.export-pdf .training {
        grid-template-columns: repeat(4, minmax(0, 1fr)) !important;
        gap: 8px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .day {
        padding: 8px !important;
        border-radius: 14px !important;
        break-inside: avoid-page !important;
        page-break-inside: avoid !important;
      }
      html.export-mode.export-pdf .day li {
        font-size: 11.5px !important;
        line-height: 17px !important;
      }
      html.export-mode.export-pdf .reconstruction-card,
      html.export-mode.export-pdf .reconstruction-card .reconstruction-figure {
        break-inside: avoid-page !important;
        page-break-inside: avoid !important;
      }
      html.export-mode.export-pdf .reconstruction-grid {
        display: block !important;
        columns: 2;
        column-gap: 10px;
      }
      html.export-mode.export-pdf .reconstruction-grid > .visual-card {
        display: inline-block !important;
        width: 100% !important;
        margin: 0 0 10px !important;
      }
      html.export-mode.export-pdf .reconstruction-card .reconstruction-img {
        max-width: 100% !important;
        aspect-ratio: 16 / 8.8 !important;
        object-fit: contain !important;
      }
      html.export-mode.export-pdf .reconstruction-card figcaption {
        padding: 8px 10px !important;
        gap: 2px !important;
      }
      html.export-mode.export-pdf .reconstruction-card figcaption b {
        font-size: 12.5px !important;
        line-height: 16px !important;
      }
      html.export-mode.export-pdf .reconstruction-card figcaption span {
        font-size: 10.5px !important;
        line-height: 14px !important;
      }
      html.export-mode.export-pdf table {
        font-size: 7.6px !important;
        table-layout: fixed !important;
      }
      html.export-mode.export-pdf th,
      html.export-mode.export-pdf td {
        font-size: 7.6px !important;
        padding: 1px 3px !important;
        line-height: 9px !important;
        vertical-align: top !important;
      }
      html.export-mode.export-pdf th:last-child,
      html.export-mode.export-pdf td:last-child {
        font-size: 6.8px !important;
        line-height: 8px !important;
      }
      html.export-mode.export-pdf .source-table-card table {
        font-size: 11px !important;
      }
      html.export-mode.export-pdf .source-table-card th,
      html.export-mode.export-pdf .source-table-card td {
        font-size: 11px !important;
        line-height: 34px !important;
        padding: 6px 5px !important;
      }
      html.export-mode.export-pdf .source-table-card th:last-child,
      html.export-mode.export-pdf .source-table-card td:last-child {
        font-size: 9px !important;
        line-height: 26px !important;
      }
      html.export-mode.export-pdf .reconstruction-figure,
      html.export-mode.export-pdf .evidence-figure,
      html.export-mode.export-pdf .radar,
      html.export-mode.export-pdf .line-chart-scroll,
      html.export-mode.export-pdf .mini-chart-scroll,
      html.export-mode.export-pdf .dot-plot-scroll,
      html.export-mode.export-pdf figure,
      html.export-mode.export-pdf img,
      html.export-mode.export-pdf svg {
        break-inside: avoid !important;
        page-break-inside: avoid !important;
      }
      html.export-mode.export-pdf .hero {
        grid-template-columns: 1.04fr .96fr !important;
        gap: 18px !important;
        padding: 28px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .hero h1 {
        font-size: 38px !important;
        line-height: 46px !important;
      }
      html.export-mode.export-pdf .hero p {
        font-size: 16.5px !important;
        line-height: 25px !important;
      }
      html.export-mode.export-pdf .hero .pill {
        font-size: 13px !important;
        padding: 5px 10px !important;
      }
      html.export-mode.export-pdf .hero-evidence {
        max-width: 100% !important;
        padding: 10px !important;
        gap: 8px !important;
      }
      html.export-mode.export-pdf .hero-stat b {
        font-size: 18px !important;
      }
      html.export-mode.export-pdf .hero-stat span {
        font-size: 11px !important;
      }
      html.export-mode.export-pdf .visual-card {
        padding-top: 12px !important;
        padding-bottom: 12px !important;
      }
      html.export-mode.export-pdf .visual-card h4 {
        break-after: avoid-page;
        page-break-after: avoid;
      }
      html.export-mode.export-pdf .research-curves-card {
        padding: 10px !important;
      }
      html.export-mode.export-pdf .research-curve-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 8px !important;
        align-items: start !important;
      }
      html.export-mode.export-pdf .research-curve-grid figure {
        padding: 6px !important;
        border-radius: 8px !important;
      }
      html.export-mode.export-pdf .research-curve-grid img {
        width: 100% !important;
        max-width: 100% !important;
        max-height: 280px !important;
        object-fit: contain !important;
      }
      html.export-mode.export-pdf .research-curve-grid figcaption {
        margin-top: 4px !important;
        font-size: 10.5px !important;
        line-height: 13px !important;
      }
      html.export-mode.export-pdf .peak-angle-card img,
      html.export-mode.export-pdf .clean-evidence-media img,
      html.export-mode.export-pdf .evidence-media img {
        max-height: 360px !important;
        object-fit: contain !important;
      }
      html.export-mode.julian-coach-export .event-gifs {
        position: static !important;
        top: auto !important;
      }
      html.export-mode.julian-coach-export.export-pdf main {
        max-width: 1180px !important;
        padding: 24px 24px 48px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .section {
        margin-top: 28px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .grid-2 {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 18px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .metrics-with-media {
        grid-template-columns: minmax(0, 2fr) minmax(300px, 1fr) !important;
        gap: 18px !important;
        align-items: start !important;
      }
      html.export-mode.julian-coach-export.export-pdf .compact-metrics,
      html.export-mode.julian-coach-export.export-pdf .metrics-with-media .grid {
        grid-template-columns: 1fr !important;
        gap: 18px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .issue-metrics {
        grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
        gap: 18px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .metric-card {
        grid-template-columns: minmax(110px, 145px) minmax(130px, 165px) minmax(0, 1fr) !important;
        gap: 16px !important;
        min-height: 226px !important;
        padding: 20px 22px !important;
        border-radius: 22px !important;
        overflow: hidden !important;
      }
      html.export-mode.julian-coach-export.export-pdf .issue-metrics .metric-card {
        grid-template-columns: minmax(88px, 115px) minmax(104px, 135px) minmax(0, 1fr) !important;
        gap: 12px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .metric-illustration {
        max-width: 160px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .metric-detail-cn {
        font-size: 13px !important;
        line-height: 19px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .metric-detail-en {
        font-size: 10.5px !important;
        line-height: 15px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .peer-range {
        grid-template-columns: max-content 24px minmax(88px, 1fr) 24px !important;
      }
      html.export-mode.julian-coach-export.export-pdf .section-annotation {
        width: calc((100% - 18px) / 1.46) !important;
      }
      html.export-mode.julian-coach-export.export-pdf .kinetic-chain-figure,
      html.export-mode.julian-coach-export.export-pdf .reconstruction-annotated,
      html.export-mode.julian-coach-export.export-pdf .event-gif-figure {
        max-width: 100% !important;
      }
      html.export-mode.julian-coach-export.export-ppt main {
        padding-top: 24px !important;
        padding-bottom: 48px !important;
      }
      @media print {
        body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
        .section { break-before: auto; }
      }
    `,
  });
  await page.evaluate(() => {
    document.documentElement.classList.add("export-mode");
    if (document.querySelector("#julian-coach-batting-metrics")) {
      document.documentElement.classList.add("julian-coach-export");
    }
    document.querySelectorAll(".reconstruction-img").forEach((img) => {
      const card = img.closest(".visual-card");
      card?.classList.add("reconstruction-card");
      card?.parentElement?.classList.add("reconstruction-grid");
    });
    document.querySelectorAll("article.visual-card").forEach((card) => {
      const title = card.querySelector("h4")?.textContent?.trim() || "";
      if (title === "指标来源表") {
        card.classList.add("source-table-card");
        if (card.dataset.sourceSplitDone === "1") return;
        const tbody = card.querySelector("tbody");
        const rows = tbody ? Array.from(tbody.querySelectorAll("tr")) : [];
        if (tbody && rows.length > 14) {
          const splitAt = 7;
          const clone = card.cloneNode(true);
          clone.classList.add("source-table-card");
          clone.dataset.sourceSplitDone = "1";
          card.dataset.sourceSplitDone = "1";
          const titleNode = card.querySelector("h4");
          const cloneTitle = clone.querySelector("h4");
          if (titleNode) titleNode.textContent = "指标来源表 1/2";
          if (cloneTitle) cloneTitle.textContent = "指标来源表 2/2";
          rows.forEach((row, idx) => {
            if (idx >= splitAt) row.remove();
          });
          clone.querySelectorAll("tbody tr").forEach((row, idx) => {
            if (idx < splitAt) row.remove();
          });
          card.after(clone);
        }
      }
    });
  });
  await forceLoadLazyMedia(page);
  await page.emulateMedia({ media: "print" });
}

async function exportPdf(page, outPdf) {
  await ensureDir(outPdf);
  await page.evaluate(() => {
    document.documentElement.classList.add("export-pdf");
    document.documentElement.classList.remove("export-ppt");
    document.querySelectorAll(".visual-card").forEach((card) => {
      card.classList.remove("pdf-keep-card", "pdf-flow-card");
    });
  });
  await page.pdf({
    path: outPdf,
    format: "A4",
    printBackground: true,
    preferCSSPageSize: true,
    margin: { top: "9mm", right: "9mm", bottom: "9mm", left: "9mm" },
  });
}

async function collectPackedPdfBlocks(page) {
  await page.evaluate(() => {
    document.documentElement.classList.add("export-pdf");
    document.documentElement.classList.remove("export-ppt");
  });
  return await page.evaluate(() => {
    const candidates = [
      document.querySelector(".hero"),
      ...document.querySelectorAll(
        [
          ".section-title",
          ".module-note",
          "article.visual-card",
          ".grid > article.metric-card",
          ".grid > article.card",
          ".grid-2 > article.card",
          ".grid-3 > article.card",
        ].join(","),
      ),
    ].filter(Boolean);
    const nodes = [...new Set(candidates)]
      .filter((node) => {
        const parentVisualCard = node.closest("article.visual-card");
        return !parentVisualCard || parentVisualCard === node;
      })
      .sort((a, b) => {
        if (a === b) return 0;
        return a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
      });
    nodes.forEach((node, idx) => node.setAttribute("data-pdf-pack-block", String(idx)));
    return nodes.map((node, idx) => {
      const title =
        node.querySelector("h1, h2, h3, h4")?.textContent?.trim() ||
        node.textContent?.trim()?.slice(0, 32) ||
        `报告块 ${idx + 1}`;
      return {
        index: idx,
        title,
        className: node.className || "",
        tagName: node.tagName,
        isHero: node.classList.contains("hero"),
        isHeading: node.classList.contains("section-title"),
        isNote: node.classList.contains("module-note"),
        isMetric: node.classList.contains("metric-card"),
        isReconstruction: node.classList.contains("reconstruction-card"),
        isSourceTable: node.classList.contains("source-table-card"),
      };
    });
  });
}

async function screenshotPackedPdfBlocks(page, blocks, imageDir) {
  await ensureDir(imageDir, true);
  const records = [];
  for (const block of blocks) {
    const locator = page.locator(`[data-pdf-pack-block="${block.index}"]`);
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return {
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY,
        width: rect.width,
        height: rect.height,
      };
    });
    if (!box || box.width < 20 || box.height < 16) continue;
    const file = path.join(imageDir, `pdf-block-${String(block.index + 1).padStart(2, "0")}.png`);
    await page.screenshot({
      path: file,
      animations: "disabled",
      fullPage: true,
      clip: {
        x: Math.max(0, box.x),
        y: Math.max(0, box.y),
        width: box.width,
        height: box.height,
      },
    });
    const record = {
      ...block,
      file,
      width: box.width,
      height: box.height,
      fullWidth: box.width,
      fullHeight: box.height,
      ratio: box.height / box.width,
    };
    records.push(record);
  }
  return records;
}

function pdfPackKind(record) {
  if (record.isHero || record.isHeading || record.isNote) return "full";
  if (record.isSourceChunk) return "full";
  if (pdfHighDensityFull(record)) return "full";
  if (record.width > 900) return "full";
  if (record.height > 760) return "full";
  if (record.isMetric || (record.width < 360 && record.height < 290)) return "quarter";
  return "half";
}

function pdfHighDensityFull(record) {
  return /时间曲线|事件点表|C3D逐帧来源表/.test(record.title);
}

function pdfVisualWeight(record) {
  if (record.isHero || record.isHeading || record.isNote) return 1;
  if (/数据质量图/.test(record.title)) return 0.92;
  if (record.isReconstruction || /C3D骨架动图/.test(record.title)) return 0.84;
  if (/六维评分图|关键帧证据图|姿态纠正图|挥棒轨迹证据图/.test(record.title)) return 0.82;
  if (/阶段时间轴|动力链传递图|改进优先级矩阵/.test(record.title)) return 0.78;
  if (/投球七天训练计划|优先级列表|差距仪表盘/.test(record.title)) return 0.92;
  if (/光学动作捕捉对照说明|限制卡片组/.test(record.title)) return 1.08;
  if (record.isSourceChunk) return 1;
  if (/时间曲线|事件点表|C3D逐帧来源表|Vicon 2026 C3D来源表/.test(record.title)) return 1.12;
  return 1;
}

function pdfRowSignature(record) {
  if (record.isReconstruction) return "model";
  if (pdfVisualWeight(record) < 0.9) return "compact";
  if (pdfHighDensityFull(record)) return "dense";
  if (record.ratio > 1.06) return "vertical";
  if (record.ratio < 0.72) return "horizontal";
  return "balanced";
}

function buildPackedPdfPages(records) {
  const page = { width: 794, height: 1123, pad: 34, gap: 10 };
  const contentW = page.width - page.pad * 2;
  const contentH = page.height - page.pad * 2;
  const pages = [];
  let current = [];
  let y = 0;

  const pushPage = () => {
    if (current.length) pages.push(current);
    current = [];
    y = 0;
  };
  const addRow = (items) => {
    if (!items.length) return;
    const rowGap = page.gap;
    const cols = items.length;
    const rowW = cols === 1 ? contentW : (contentW - rowGap * (cols - 1)) / cols;
    let laidOut = items.map((record) => {
      const visualWeight = pdfVisualWeight(record);
      const fitScale = rowW / record.width;
      const scale = Math.min(fitScale * visualWeight, fitScale, 1.3);
      return {
        record,
        width: record.width * scale,
        height: record.height * scale,
      };
    });
    let rowH = Math.max(...laidOut.map((item) => item.height));
    const scaleRow = (scale) => {
      laidOut = laidOut.map((item) => ({
        ...item,
        width: item.width * scale,
        height: item.height * scale,
      }));
      rowH *= scale;
    };
    if (rowH > contentH) {
      scaleRow(contentH / rowH);
    }
    if (y > 0 && y + rowH > contentH) {
      const remaining = contentH - y;
      const fitScale = remaining / rowH;
      if (remaining / contentH >= 0.2 && fitScale >= 0.55) {
        scaleRow(fitScale);
      } else {
        pushPage();
      }
    }
    current.push({ items: laidOut, height: rowH });
    y += rowH + page.gap;
  };

  let queue = [];
  let queueKind = "";
  let queueSig = "";
  const flush = () => {
    while (queue.length) {
      const max = queueKind === "quarter" ? 4 : queueKind === "half" ? 2 : 1;
      const row = queue.splice(0, max);
      addRow(row);
    }
    queueKind = "";
    queueSig = "";
  };

  for (const record of records) {
    const kind = pdfPackKind(record);
    const sig = kind === "half" ? pdfRowSignature(record) : kind;
    if (kind === "full") {
      flush();
      addRow([record]);
      continue;
    }
    if (queue.length && (kind !== queueKind || sig !== queueSig)) flush();
    queueKind = kind;
    queueSig = sig;
    queue.push(record);
    if (queue.length >= (kind === "quarter" ? 4 : 2)) flush();
  }
  flush();
  pushPage();
  return { pages, page };
}

function packedPdfHtml(pages, page) {
  const pageCss = `
    @page { size: A4; margin: 0; }
    * { box-sizing: border-box; }
    body { margin: 0; background: ${C.bg}; font-family: Arial, sans-serif; }
    .pdf-page {
      width: ${page.width}px;
      height: ${page.height}px;
      padding: ${page.pad}px;
      background: ${C.bg};
      break-after: page;
      overflow: hidden;
    }
    .row {
      display: flex;
      gap: ${page.gap}px;
      align-items: flex-start;
      justify-content: center;
      margin-bottom: ${page.gap}px;
    }
    .row:last-child { margin-bottom: 0; }
    .cell {
      display: flex;
      justify-content: center;
      align-items: flex-start;
      min-width: 0;
    }
    img {
      display: block;
      object-fit: contain;
      border: 0;
    }
  `;
  const body = pages
    .map((rows) => {
      const rowsHtml = rows
        .map((row) => {
          const cells = row.items
            .map((item) => {
              const href = pathToFileURL(item.record.file).href;
              if (item.record.isSourceChunk) {
                const scale = item.width / item.record.fullWidth;
                const fullHeight = item.record.fullHeight * scale;
                const clipY = (item.record.clipY || 0) * scale;
                return `<div class="cell" style="width:${item.width}px;height:${item.height}px;overflow:hidden"><img src="${href}" style="width:${item.width}px;height:${fullHeight}px;transform:translateY(-${clipY}px);transform-origin:top left" alt=""></div>`;
              }
              return `<div class="cell" style="width:${item.width}px;height:${item.height}px"><img src="${href}" style="width:${item.width}px;height:${item.height}px" alt=""></div>`;
            })
            .join("");
          return `<div class="row" style="height:${row.height}px">${cells}</div>`;
        })
        .join("");
      return `<section class="pdf-page">${rowsHtml}</section>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>${pageCss}</style></head><body>${body}</body></html>`;
}

async function exportPackedPdf(page, browser, outPdf, workDir) {
  await ensureDir(outPdf);
  const imageDir = path.join(workDir, "pdf-packed-blocks");
  const packedHtml = path.join(workDir, "packed-report.html");
  const blocks = await collectPackedPdfBlocks(page);
  const records = await screenshotPackedPdfBlocks(page, blocks, imageDir);
  const packed = buildPackedPdfPages(records);
  await fs.writeFile(packedHtml, packedPdfHtml(packed.pages, packed.page));
  const packedPage = await browser.newPage({ viewport: { width: packed.page.width, height: packed.page.height } });
  try {
    await packedPage.goto(pathToFileURL(packedHtml).href, { waitUntil: "networkidle" });
    await packedPage.pdf({
      path: outPdf,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });
  } finally {
    await packedPage.close();
  }
}

async function collectSlicedPdfPages(page) {
  await page.evaluate(() => {
    document.documentElement.classList.add("export-pdf");
    document.documentElement.classList.remove("export-ppt");
  });
  return await page.evaluate(() => {
    const page = { width: 794, height: 1123, pad: 24, gap: 0 };
    const viewportW = Math.ceil(Math.max(document.documentElement.clientWidth, window.innerWidth));
    const scrollH = Math.ceil(Math.max(document.documentElement.scrollHeight, document.body.scrollHeight));
    const contentW = page.width - page.pad * 2;
    const contentH = page.height - page.pad * 2;
    const maxSliceH = Math.floor((contentH / contentW) * viewportW);
    const minSliceH = Math.floor(maxSliceH * 0.68);
    const candidateSelectors = [
      ".hero",
      ".section-title",
      ".module-note",
      "article.visual-card",
      "article.evidence-card",
      ".clean-evidence-card",
      ".issue-card",
      ".grid2",
      ".grid",
      ".grid-2",
      ".grid-3",
      ".metric-grid",
      ".chart-row",
      ".radar-area",
      ".map",
      ".plan",
      ".compact-metrics",
      ".training",
      ".training-grid",
      ".table-wrap",
      ".lim-list",
    ].join(",");
    const avoidSelectors = [
      ".hero",
      ".module-note",
      "article.visual-card",
      "article.evidence-card",
      "article.metric-card",
      "article.card",
      ".card",
      ".metric",
      ".chart",
      ".clean-evidence-card",
      ".issue-card",
      ".map-item",
      ".day",
      ".lim",
    ].join(",");
    const rects = [...document.querySelectorAll(candidateSelectors)]
      .map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          top: Math.round(rect.top + window.scrollY),
          bottom: Math.round(rect.bottom + window.scrollY),
        };
      })
      .filter((rect) => rect.bottom > 80 && rect.bottom < scrollH - 20)
      .sort((a, b) => a.top - b.top || a.bottom - b.bottom);
    const rowBottoms = [];
    for (const rect of rects) {
      const last = rowBottoms[rowBottoms.length - 1];
      if (last && Math.abs(last.top - rect.top) <= 24) {
        last.bottom = Math.max(last.bottom, rect.bottom);
      } else {
        rowBottoms.push({ ...rect });
      }
    }
    const uniqueBottoms = [...new Set(rowBottoms.map((rect) => rect.bottom))].sort((a, b) => a - b);
    const avoidRects = [...document.querySelectorAll(avoidSelectors)]
      .map((node) => {
        const rect = node.getBoundingClientRect();
        return {
          top: Math.round(rect.top + window.scrollY),
          bottom: Math.round(rect.bottom + window.scrollY),
        };
      })
      .filter((rect) => rect.bottom - rect.top > 24);
    const uncross = (start, proposedEnd, target) => {
      const crossing = avoidRects.filter((rect) => rect.top < proposedEnd - 8 && rect.bottom > proposedEnd + 8);
      if (!crossing.length) return proposedEnd;
      const rowTop = Math.min(...crossing.map((rect) => rect.top));
      const rowBottom = Math.max(...crossing.map((rect) => rect.bottom));
      if (rowBottom <= start + maxSliceH * 1.08) return rowBottom;
      if (rowTop >= start + minSliceH) return rowTop;
      return target;
    };
    const slices = [];
    let y = 0;
    while (y < scrollH - 4) {
      const remaining = scrollH - y;
      if (remaining <= maxSliceH * 1.08) {
        slices.push({ y, height: remaining, width: viewportW });
        break;
      }
      const target = y + maxSliceH;
      const lower = y + minSliceH;
      const candidates = uniqueBottoms.filter((bottom) => bottom >= lower && bottom <= target);
      let end = candidates.length ? candidates[candidates.length - 1] : target;
      end = uncross(y, end, target);
      if (end - y < 260) end = Math.min(y + maxSliceH, scrollH);
      slices.push({ y, height: end - y, width: viewportW });
      y = end;
    }
    return { page, viewportW, scrollH, maxSliceH, slices };
  });
}

async function screenshotSlicedPdfPages(page, slices, imageDir) {
  await ensureDir(imageDir, true);
  const records = [];
  for (let idx = 0; idx < slices.length; idx++) {
    const slice = slices[idx];
    const file = path.join(imageDir, `html-slice-${String(idx + 1).padStart(2, "0")}.png`);
    await page.screenshot({
      path: file,
      animations: "disabled",
      fullPage: true,
      clip: {
        x: 0,
        y: Math.max(0, slice.y),
        width: slice.width,
        height: slice.height,
      },
    });
    records.push({ ...slice, file });
  }
  return records;
}

function slicedPdfHtml(records, page) {
  const contentW = page.width - page.pad * 2;
  const contentH = page.height - page.pad * 2;
  const pageCss = `
    @page { size: A4; margin: 0; }
    * { box-sizing: border-box; }
    body { margin: 0; background: ${C.bg}; font-family: Arial, sans-serif; }
    .pdf-page {
      width: ${page.width}px;
      height: ${page.height}px;
      padding: ${page.pad}px;
      background: ${C.bg};
      break-after: page;
      overflow: hidden;
      display: flex;
      align-items: flex-start;
      justify-content: center;
    }
    img {
      display: block;
      border: 0;
      object-fit: contain;
    }
  `;
  const body = records
    .map((record) => {
      const scale = Math.min(contentW / record.width, contentH / record.height);
      const w = record.width * scale;
      const h = record.height * scale;
      const href = pathToFileURL(record.file).href;
      return `<section class="pdf-page"><img src="${href}" style="width:${w}px;height:${h}px" alt=""></section>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>${pageCss}</style></head><body>${body}</body></html>`;
}

async function exportSlicedPdf(page, browser, outPdf, workDir) {
  await ensureDir(outPdf);
  const imageDir = path.join(workDir, "pdf-html-slices");
  const slicedHtml = path.join(workDir, "sliced-report.html");
  const plan = await collectSlicedPdfPages(page);
  const records = await screenshotSlicedPdfPages(page, plan.slices, imageDir);
  await fs.writeFile(slicedHtml, slicedPdfHtml(records, plan.page));
  const pdfPage = await browser.newPage({ viewport: { width: plan.page.width, height: plan.page.height } });
  try {
    await pdfPage.goto(pathToFileURL(slicedHtml).href, { waitUntil: "networkidle" });
    await pdfPage.pdf({
      path: outPdf,
      format: "A4",
      printBackground: true,
      preferCSSPageSize: true,
      margin: { top: "0", right: "0", bottom: "0", left: "0" },
    });
  } finally {
    await pdfPage.close();
  }
}

async function isJulianCoachReport(page) {
  return await page.evaluate(() => Boolean(document.querySelector("#julian-coach-batting-metrics")));
}

async function collectJulianCoachSlideSlices(page) {
  await page.evaluate(() => {
    document.documentElement.classList.add("export-ppt", "julian-coach-export");
    document.documentElement.classList.remove("export-pdf");
  });
  return await page.evaluate(() => {
    const viewportW = Math.ceil(Math.max(document.documentElement.clientWidth, window.innerWidth));
    const fallbackTitle = document.querySelector("h1")?.textContent?.trim() || document.title || "报告";
    const rectOf = (node) => {
      const r = node.getBoundingClientRect();
      return {
        x: 0,
        y: Math.round(r.top + window.scrollY),
        width: viewportW,
        height: Math.round(r.height),
        top: Math.round(r.top + window.scrollY),
        bottom: Math.round(r.bottom + window.scrollY),
      };
    };
    const unionRect = (nodes, fullWidth = true) => {
      const rects = nodes.map((node) => node.getBoundingClientRect());
      const left = Math.min(...rects.map((r) => r.left + window.scrollX));
      const right = Math.max(...rects.map((r) => r.right + window.scrollX));
      const top = Math.min(...rects.map((r) => r.top + window.scrollY));
      const bottom = Math.max(...rects.map((r) => r.bottom + window.scrollY));
      return {
        x: fullWidth ? 0 : Math.round(left),
        y: Math.round(top),
        width: fullWidth ? viewportW : Math.round(right - left),
        height: Math.round(bottom - top),
        top: Math.round(top),
        bottom: Math.round(bottom),
      };
    };
    const mediaForRect = (sliceRect) =>
      [...document.querySelectorAll("img, video")]
        .map((mediaNode) => {
          const rect = mediaNode.getBoundingClientRect();
          const src =
            mediaNode.currentSrc ||
            mediaNode.getAttribute("src") ||
            mediaNode.querySelector?.("source")?.getAttribute("src") ||
            "";
          if (!src || rect.width < 8 || rect.height < 8) return null;
          const abs = {
            left: rect.left + window.scrollX,
            top: rect.top + window.scrollY,
            right: rect.right + window.scrollX,
            bottom: rect.bottom + window.scrollY,
            width: rect.width,
            height: rect.height,
          };
          const top = Math.max(abs.top, sliceRect.y);
          const bottom = Math.min(abs.bottom, sliceRect.y + sliceRect.height);
          const left = Math.max(abs.left, sliceRect.x);
          const right = Math.min(abs.right, sliceRect.x + sliceRect.width);
          if (bottom <= top || right <= left) return null;
          return {
            tagName: mediaNode.tagName,
            src: new URL(src, document.baseURI).href,
            x: left - sliceRect.x,
            y: top - sliceRect.y,
            width: right - left,
            height: bottom - top,
            cropTop: (top - abs.top) / abs.height,
            cropBottom: (abs.bottom - bottom) / abs.height,
          };
        })
        .filter(Boolean);
    const sections = [...document.querySelectorAll("main > section")].filter((section) => {
      const rect = section.getBoundingClientRect();
      return rect.width > 100 && rect.height > 30;
    });
    const records = [];
    const addRecord = (section, title, rect) => {
      const record = {
        index: records.length,
        section,
        title,
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
        top: rect.top,
      };
      record.media = mediaForRect(record);
      records.push(record);
    };
    for (const section of sections) {
      const rect = section.getBoundingClientRect();
      const sectionTitle =
        section.querySelector(".section-title h1, .section-title h2, .section-title h3")?.textContent?.trim() ||
        fallbackTitle;
      const metrics = [...section.querySelectorAll(".compact-metrics > .metric-card")];
      if (!metrics.length) {
        addRecord(sectionTitle, sectionTitle, rectOf(section));
        continue;
      }

      const annotation = section.querySelector(".section-annotation");
      if (annotation) {
        addRecord(sectionTitle, `${sectionTitle} 动作参考`, unionRect([section.querySelector(".section-title"), annotation]));
      }

      const isIssueSection = section.classList.contains("section") && sectionTitle === "专项问题";
      const chunkSize = isIssueSection ? 2 : 2;
      const metricGroups = [];
      for (let i = 0; i < metrics.length; i += chunkSize) {
        metricGroups.push(metrics.slice(i, i + chunkSize));
      }
      metricGroups.forEach((group, idx) => {
        addRecord(
          sectionTitle,
          metricGroups.length > 1 ? `${sectionTitle} 指标 ${idx + 1}/${metricGroups.length}` : `${sectionTitle} 指标`,
          unionRect(group, !isIssueSection && idx === 0),
        );
      });
    }
    return records;
  });
}

async function screenshotJulianCoachSlideSlices(page, slices, imageDir) {
  await ensureDir(imageDir, true);
  const records = [];
  for (const slice of slices) {
    const file = path.join(imageDir, `section-slice-${String(slice.index + 1).padStart(2, "0")}.png`);
    await page.screenshot({
      path: file,
      animations: "disabled",
      fullPage: true,
      clip: {
        x: Math.max(0, slice.x),
        y: Math.max(0, slice.y),
        width: slice.width,
        height: slice.height,
      },
    });
    records.push({ ...slice, file });
  }
  return records;
}

async function collectBlocks(page) {
  await page.evaluate(() => {
    document.documentElement.classList.add("export-ppt");
  });
  return await page.evaluate(() => {
    const sectionLabel = (node) => {
      const section = node.closest("section");
      if (!section) return "";
      const heading = section.querySelector(".section-title h2, .section-title h3, :scope > h2, :scope > h3");
      return heading?.textContent?.trim() || "";
    };
    const blockSelectors = [
      ".hero",
      "article.visual-card",
      "article.evidence-card",
      ".clean-evidence-card",
      ".issue-card",
      "article.metric-card",
      ".grid2 > .card",
      ".card",
      ".compact-metrics > .metric-card",
      ".metric-grid > .metric",
      ".chart-row > .chart",
      ".map",
      ".radar-area",
      ".plan",
      ".training-grid > .training",
      ".table-wrap",
      ".lim-list",
    ];
    const fallbackSection =
      document.querySelector(".eyebrow")?.textContent?.trim() ||
      document.querySelector("h1")?.textContent?.trim() ||
      document.title ||
      "";
    const nodes = [];
    for (const node of document.querySelectorAll(blockSelectors.join(","))) {
      if (nodes.some((existing) => existing === node || existing.contains(node))) continue;
      nodes.push(node);
    }
    return nodes.map((node, idx) => {
      const rect = node.getBoundingClientRect();
      const title =
        node.querySelector("h1, h2, h3, h4, .metric-name, .metric-title")?.textContent?.trim() ||
        node.getAttribute("id") ||
        `报告页面 ${idx + 1}`;
      node.setAttribute("data-export-block", String(idx));
      return {
        index: idx,
        title,
        section: sectionLabel(node) || fallbackSection,
        top: Math.round(rect.top + window.scrollY),
      };
    });
  });
}

async function screenshotBlocks(page, blocks, imageDir) {
  await ensureDir(imageDir, true);
  const records = [];
  const maxSliceHeight = 1100;
  for (const block of blocks) {
    const locator = page.locator(`[data-export-block="${block.index}"]`);
    await locator.scrollIntoViewIfNeeded();
    const box = await locator.evaluate((node) => {
      const rect = node.getBoundingClientRect();
      return {
        x: rect.left + window.scrollX,
        y: rect.top + window.scrollY,
        width: rect.width,
        height: rect.height,
      };
    });
    if (!box || box.width < 20 || box.height < 20) continue;
    const media = await locator.evaluate((node) => {
      const blockRect = node.getBoundingClientRect();
      return [...node.querySelectorAll("img, video")]
        .map((mediaNode) => {
          const rect = mediaNode.getBoundingClientRect();
          const src =
            mediaNode.currentSrc ||
            mediaNode.getAttribute("src") ||
            mediaNode.querySelector?.("source")?.getAttribute("src") ||
            "";
          if (!src || rect.width < 8 || rect.height < 8) return null;
          return {
            tagName: mediaNode.tagName,
            src: new URL(src, document.baseURI).href,
            x: rect.left - blockRect.left,
            y: rect.top - blockRect.top,
            width: rect.width,
            height: rect.height,
          };
        })
        .filter(Boolean);
    });
    const slices = box.height <= maxSliceHeight + 180 ? 1 : Math.max(1, Math.ceil(box.height / maxSliceHeight));
    const balancedSliceHeight = Math.ceil(box.height / slices);
    for (let slice = 0; slice < slices; slice++) {
      const sliceTop = slice * balancedSliceHeight;
      const sliceHeight = Math.min(balancedSliceHeight, box.height - sliceTop);
      const sliceMedia = media
        .map((item) => {
          const top = Math.max(item.y, sliceTop);
          const bottom = Math.min(item.y + item.height, sliceTop + sliceHeight);
          if (bottom <= top) return null;
          return {
            ...item,
            y: top - sliceTop,
            height: bottom - top,
            cropTop: (top - item.y) / item.height,
            cropBottom: (item.y + item.height - bottom) / item.height,
          };
        })
        .filter(Boolean);
      const file = path.join(
        imageDir,
        `block-${String(block.index + 1).padStart(2, "0")}-${String(slice + 1).padStart(2, "0")}.png`,
      );
      await page.screenshot({
        path: file,
        animations: "disabled",
        fullPage: true,
        clip: {
          x: Math.max(0, box.x),
          y: Math.max(0, box.y + sliceTop),
          width: box.width,
          height: sliceHeight,
        },
      });
      records.push({
        ...block,
        title: slices > 1 ? `${block.title}（${slice + 1}/${slices}）` : block.title,
        file,
        width: box.width,
        height: sliceHeight,
        media: sliceMedia,
      });
    }
  }
  return records;
}

async function bytes(file) {
  return new Uint8Array(await fs.readFile(file));
}

function addText(slide, text, x, y, w, h, size = 18, opts = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position: { left: x, top: y, width: w, height: h },
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = {
    fontSize: size,
    bold: !!opts.bold,
    color: opts.color || C.body,
    fontFace: "Microsoft YaHei",
  };
  return shape;
}

async function addPng(slide, file, x, y, w, h) {
  return await slide.images.add({
    blob: await bytes(file),
    contentType: "image/png",
    alt: path.basename(file),
    fit: "contain",
    position: { left: x, top: y, width: w, height: h },
  });
}

function mediaFilePath(src) {
  try {
    const url = new URL(src);
    if (url.protocol !== "file:") return null;
    return fileURLToPath(url);
  } catch {
    return null;
  }
}

async function addAnimatedMediaOverlays(slide, record, frame) {
  const scaleX = frame.width / record.width;
  const scaleY = frame.height / record.height;
  for (const media of record.media || []) {
    const file = mediaFilePath(media.src);
    if (!file || !/\.gif$/i.test(file) || !fsSync.existsSync(file)) continue;
    await slide.images.add({
      blob: await bytes(file),
      contentType: "image/gif",
      alt: path.basename(file),
      fit: "cover",
      crop: {
        left: 0,
        top: media.cropTop || 0,
        right: 0,
        bottom: media.cropBottom || 0,
      },
      position: {
        left: frame.left + media.x * scaleX,
        top: frame.top + media.y * scaleY,
        width: media.width * scaleX,
        height: media.height * scaleY,
      },
    });
  }
}

function buildSlideGroups(records) {
  const groups = [];
  for (let i = 0; i < records.length; i++) {
    const current = records[i];
    const next = records[i + 1];
    const canPair =
      next &&
      current.width <= 680 &&
      next.width <= 680 &&
      current.height <= 720 &&
      next.height <= 720;
    if (canPair) {
      groups.push([current, next]);
      i++;
    } else {
      groups.push([current]);
    }
  }
  return groups;
}

function groupTitle(group) {
  if (group.length === 1) return group[0].title;
  return group.map((record) => record.title.replace(/（\d+\/\d+）$/, "")).join(" / ");
}

async function exportPptx(records, outPptx, qaPath, previewDir, mediaScale) {
  const { Presentation, PresentationFile } = await loadArtifactTool();
  await ensureDir(outPptx);
  await ensureDir(previewDir, true);
  const deck = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  let pageNo = 1;
  const groups = buildSlideGroups(records);
  for (const group of groups) {
    const slide = deck.slides.add();
    slide.background.fill = C.bg;
    const section = group[0].section || group[0].title;
    const title = groupTitle(group);
    addText(slide, section, 54, 24, 420, 24, 14, { bold: true, color: C.blue });
    addText(slide, title, 54, 52, 990, 40, title.length > 24 ? 25 : 31, {
      bold: true,
      color: C.ink,
    });
    addText(slide, String(pageNo).padStart(2, "0"), 1188, 28, 48, 20, 13, { color: C.muted });

    if (group.length === 1) {
      const [record] = group;
      const maxW = 1172 * mediaScale;
      const maxH = 580 * mediaScale;
      const scale = Math.min(maxW / record.width, maxH / record.height);
      const w = record.width * scale;
      const h = record.height * scale;
      const frameW = 1172;
      const frameH = 580;
      const x = 54 + (frameW - w) / 2;
      const y = 108 + (frameH - h) / 2;
      await addPng(slide, record.file, x, y, w, h);
      await addAnimatedMediaOverlays(slide, record, { left: x, top: y, width: w, height: h });
    } else {
      const frameY = 118;
      const frameH = 552;
      const gap = 28;
      const colW = (1172 - gap) / 2;
      for (let idx = 0; idx < group.length; idx++) {
        const record = group[idx];
        const scale = Math.min(colW / record.width, frameH / record.height);
        const w = record.width * scale;
        const h = record.height * scale;
        const colX = 54 + idx * (colW + gap);
        const x = colX + (colW - w) / 2;
        const y = frameY + (frameH - h) / 2;
        await addPng(slide, record.file, x, y, w, h);
        await addAnimatedMediaOverlays(slide, record, { left: x, top: y, width: w, height: h });
      }
    }
    pageNo++;
  }
  for (const [idx, slide] of deck.slides.items.entries()) {
    const stem = `slide-${String(idx + 1).padStart(2, "0")}`;
    const png = await deck.export({ slide, format: "png", scale: 1 });
    await fs.writeFile(path.join(previewDir, `${stem}.png`), new Uint8Array(await png.arrayBuffer()));
  }
  const montage = await deck.export({ format: "webp", montage: true, scale: 1 });
  await fs.writeFile(path.join(previewDir, "deck-montage.webp"), new Uint8Array(await montage.arrayBuffer()));

  const pptx = await PresentationFile.exportPptx(deck);
  await pptx.save(outPptx);
  await fs.writeFile(
    qaPath,
    JSON.stringify(
      {
        slides: records.length,
        outputSlides: groups.length,
        outPptx,
        previewDir,
        mediaScale,
        groups: groups.map((group) => group.map((record) => record.title)),
        records: records.map((r) => ({
          title: r.title,
          section: r.section,
          top: r.top,
          width: Math.round(r.width),
          height: Math.round(r.height),
          file: r.file,
          animatedMedia: (r.media || []).filter((m) => /\.gif($|\?)/i.test(m.src)).map((m) => m.src),
        })),
      },
      null,
      2,
    ),
  );
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  const { chromium } = loadPlaywright();
  await ensureDir(args.workDir, true);
  await ensureDir(path.join(args.workDir, "screenshots"), true);

  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ deviceScaleFactor: 2 });
  try {
    await preparePage(page, args.html, args.viewportWidth, args.viewportHeight, args.pdfMediaScale);
    const julianCoachReport = await isJulianCoachReport(page);
    if (args.only === "all" || args.only === "pdf") {
      await exportSlicedPdf(page, browser, args.pdf, args.workDir);
    }
    if (args.only === "all" || args.only === "pptx") {
      await page.emulateMedia({ media: "screen" });
      await page.evaluate(() => {
        document.documentElement.classList.add("export-ppt");
        document.documentElement.classList.remove("export-pdf");
      });
      const records = julianCoachReport
        ? await screenshotJulianCoachSlideSlices(
            page,
            await collectJulianCoachSlideSlices(page),
            path.join(args.workDir, "screenshots"),
          )
        : await screenshotBlocks(page, await collectBlocks(page), path.join(args.workDir, "screenshots"));
      await exportPptx(
        records,
        args.pptx,
        path.join(args.workDir, "pptx-qa.json"),
        path.join(args.workDir, "pptx-preview"),
        julianCoachReport ? 1 : args.pptxMediaScale,
      );
    }
  } finally {
    await browser.close();
  }
  console.log(JSON.stringify({ pdf: args.pdf, pptx: args.pptx, workDir: args.workDir }, null, 2));
}

main().catch((err) => {
  console.error(err.stack || err.message);
  process.exitCode = 1;
});
