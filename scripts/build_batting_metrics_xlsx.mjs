import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const metricsPath = process.env.METRICS_PATH || `${root}/reports/vicon_2026_julian_coach/batting_dashboard_metrics.csv`;
const outDir = process.env.OUT_DIR || `${root}/outputs/batting_metrics_excel`;
const targetSample = process.env.SAMPLE_NAME || "julian";
const targetTrial = process.env.TRIAL_ID || "";
const c3dFrames = process.env.C3D_FRAMES || "";
const c3dRateHz = process.env.C3D_RATE_HZ || "100.0";

const ORDER = [
  "ready_com_height_ratio",
  "ready_rear_hip_flexion_deg",
  "ready_rear_knee_flexion_deg",
  "ready_hip_shoulder_separation_deg",
  "ready_bat_tilt_deg",
  "ready_hand_height_ratio",
  "contact_bat_speed_kmh",
  "contact_attack_angle_deg",
  "contact_pelvis_rotation_open_deg",
  "contact_torso_rotation_open_deg",
  "contact_front_knee_flexion_deg",
  "ready_to_contact_head_displacement_mm",
  "coach_high_com_risk_index",
  "coach_rear_elbow_height_diff_mm",
  "coach_bat_loading_angle_to_catcher_deg",
  "coach_rollover_forearm_roll_velocity_deg_s",
];

const FRONT_GROUP = {
  ready_com_height_ratio: "平衡",
  ready_rear_hip_flexion_deg: "下肢加载",
  ready_rear_knee_flexion_deg: "下肢加载",
  ready_hip_shoulder_separation_deg: "躯干蓄力",
  ready_bat_tilt_deg: "球棒准备",
  ready_hand_height_ratio: "球棒准备",
  contact_bat_speed_kmh: "球棒效率",
  contact_attack_angle_deg: "挥棒轨迹",
  contact_pelvis_rotation_open_deg: "下半身姿态",
  contact_torso_rotation_open_deg: "上半身姿态",
  contact_front_knee_flexion_deg: "支撑能力",
  ready_to_contact_head_displacement_mm: "稳定性",
  coach_high_com_risk_index: "重心偏高",
  coach_rear_elbow_height_diff_mm: "掉肘",
  coach_bat_loading_angle_to_catcher_deg: "引棒不足",
  coach_rollover_forearm_roll_velocity_deg_s: "翻腕",
};

const EXPLAIN = {
  ready_com_height_ratio: "准备姿态的身体高度 proxy；数值越高通常代表站姿更直，需要结合髋膝屈曲解释。",
  ready_rear_hip_flexion_deg: "后侧髋部加载程度；更大的屈曲通常表示后腿更进入蓄力姿态。",
  ready_rear_knee_flexion_deg: "后膝进入运动姿态的程度；过小会偏直立，启动可能慢。",
  ready_hip_shoulder_separation_deg: "准备阶段肩线与骨盆线的预分离，需结合稳定性解释。",
  ready_bat_tilt_deg: "准备时球棒相对地面的倾角，用于判断球棒是否处在可加载位置。",
  ready_hand_height_ratio: "握棒手相对身高的高度；过低可能限制后肘和球棒加载空间。",
  contact_bat_speed_kmh: "Contact event 内 Bat1 棒头线速度；Contact 定义为真实挥棒段内 Bat1_Z 最低的几帧。",
  contact_attack_angle_deg: "Bat1 速度向量相对水平面的角度；负值表示棒头运动方向偏向下。",
  contact_pelvis_rotation_open_deg: "从 Ready 到 Contact 的骨盆打开幅度；已取绝对值以消除 Vicon 朝向正负号影响。",
  contact_torso_rotation_open_deg: "从 Ready 到 Contact 的躯干打开幅度；已取绝对值，需和骨盆打开一起解释。",
  contact_front_knee_flexion_deg: "Contact 时前腿屈曲角，用于观察支撑和制动能力。",
  ready_to_contact_head_displacement_mm: "Ready 头部中心到 Contact 头部中心的位移；越大通常代表头部越不稳定。",
  coach_high_com_risk_index: "综合 COM 高度、后髋屈曲和后膝屈曲的 0-100 风险分；越高越偏直立。",
  coach_rear_elbow_height_diff_mm: "后肘相对后肩高度；负值代表后肘低于肩。",
  coach_bat_loading_angle_to_catcher_deg: "球棒根部方向和推断捕手方向的夹角；越大越可能说明引棒方向不足。",
  coach_rollover_forearm_roll_velocity_deg_s: "Contact event 内前臂 roll 角速度峰值；高值提示提前翻腕风险。",
};

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = "";
  let quoted = false;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    const next = text[i + 1];
    if (quoted) {
      if (ch === '"' && next === '"') {
        cell += '"';
        i += 1;
      } else if (ch === '"') {
        quoted = false;
      } else {
        cell += ch;
      }
    } else if (ch === '"') {
      quoted = true;
    } else if (ch === ",") {
      row.push(cell);
      cell = "";
    } else if (ch === "\n") {
      row.push(cell.replace(/\r$/, ""));
      rows.push(row);
      row = [];
      cell = "";
    } else {
      cell += ch;
    }
  }
  if (cell.length || row.length) {
    row.push(cell.replace(/\r$/, ""));
    rows.push(row);
  }
  const headers = rows.shift();
  return rows.filter((r) => r.some((v) => v !== "")).map((r) => Object.fromEntries(headers.map((h, i) => [h, r[i] ?? ""])));
}

function unitLabel(unit) {
  if (unit === "height_ratio") return "%身高";
  if (unit === "0-100 risk") return "风险分";
  if (unit === "0-100 score") return "分";
  return unit;
}

function valueFor(row) {
  const value = Number(row.value);
  if (!Number.isFinite(value)) return row.value;
  if (row.unit === "height_ratio") return Number((value * 100).toFixed(2));
  if (row.unit === "0-100 risk" || row.unit === "0-100 score") return Number(value.toFixed(2));
  if (Math.abs(value) >= 100) return Number(value.toFixed(2));
  return Number(value.toFixed(2));
}

function eventLabel(row) {
  if (row.module === "Ready Position" || row.event_name === "Ready Position") return "事件一：准备姿态 Ready Position";
  if (row.metric_key === "ready_to_contact_head_displacement_mm") return "事件二：击球姿态 Contact Position";
  if (row.module === "Contact Position" || row.event_name === "Contact Position") return "事件二：击球姿态 Contact Position";
  if (row.module === "Coach Flag") return "教练专项问题检测 Coach Flags";
  return row.event_name || row.module;
}

function timeSec(frame) {
  const n = Number(frame);
  return Number.isFinite(n) ? Number((n / 100).toFixed(2)) : "";
}

function parseSwingSegment(rule) {
  const m = String(rule || "").match(/(?:expanded frames|segment) (\d+)-(\d+)/);
  return m ? [Number(m[1]), Number(m[2])] : [null, null];
}

function setBaseSheetStyle(sheet) {
  sheet.showGridLines = false;
}

function styleMainSheet(sheet, lastRow) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:G1").merge();
  sheet.getRange("A2:G2").merge();
  sheet.getRange("A1:G1").format = {
    fill: "#0F766E",
    font: { bold: true, color: "#FFFFFF", size: 16 },
    horizontalAlignment: "center",
  };
  sheet.getRange("A2:G2").format = {
    fill: "#ECFDF5",
    font: { color: "#065F46", size: 10 },
    wrapText: true,
  };
  sheet.getRange("A4:G4").format = {
    fill: "#115E59",
    font: { bold: true, color: "#FFFFFF", size: 11 },
    horizontalAlignment: "center",
  };
  sheet.getRange(`A5:G${lastRow}`).format = {
    wrapText: true,
    font: { size: 11 },
    borders: {
      insideHorizontal: { style: "thin", color: "#38BDF8" },
      insideVertical: { style: "thin", color: "#BAE6FD" },
    },
  };
  for (let r = 5; r <= lastRow; r += 1) {
    if (r % 2 === 1) sheet.getRange(`A${r}:G${r}`).format.fill = "#BAE6FD";
  }
  sheet.getRange(`D5:D${lastRow}`).format.numberFormat = "0.00";
  sheet.getRange(`D5:D${lastRow}`).format.horizontalAlignment = "right";
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:B").format.columnWidth = 17;
  sheet.getRange("C:C").format.columnWidth = 26;
  sheet.getRange("D:D").format.columnWidth = 12;
  sheet.getRange("E:E").format.columnWidth = 12;
  sheet.getRange("F:F").format.columnWidth = 36;
  sheet.getRange("G:G").format.columnWidth = 64;
  sheet.getRange("A1:G1").format.rowHeight = 28;
  sheet.getRange("A2:G2").format.rowHeight = 42;
  sheet.freezePanes.freezeRows(4);
}

function styleEventSheet(sheet, lastRow) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:F1").merge();
  sheet.getRange("A1:F1").format = {
    fill: "#1D4ED8",
    font: { bold: true, color: "#FFFFFF", size: 15 },
    horizontalAlignment: "center",
  };
  sheet.getRange("A3:F3").format = {
    fill: "#1E40AF",
    font: { bold: true, color: "#FFFFFF", size: 11 },
    horizontalAlignment: "center",
  };
  sheet.getRange(`A4:F${lastRow}`).format = {
    wrapText: true,
    font: { size: 11 },
    borders: {
      insideHorizontal: { style: "thin", color: "#DBEAFE" },
      insideVertical: { style: "thin", color: "#DBEAFE" },
    },
  };
  sheet.getRange("A:A").format.columnWidth = 30;
  sheet.getRange("B:C").format.columnWidth = 12;
  sheet.getRange("D:D").format.columnWidth = 12;
  sheet.getRange("E:E").format.columnWidth = 58;
  sheet.getRange("F:F").format.columnWidth = 14;
  sheet.freezePanes.freezeRows(3);
}

function styleInfoSheet(sheet, lastRow) {
  setBaseSheetStyle(sheet);
  sheet.getRange("A1:B1").format = {
    fill: "#7C2D12",
    font: { bold: true, color: "#FFFFFF", size: 11 },
    wrapText: true,
  };
  sheet.getRange("A12:C12").format = {
    fill: "#7C2D12",
    font: { bold: true, color: "#FFFFFF", size: 11 },
    wrapText: true,
  };
  sheet.getRange(`A2:C${lastRow}`).format = {
    wrapText: true,
    font: { size: 11 },
    borders: { insideHorizontal: { style: "thin", color: "#FED7AA" } },
  };
  sheet.getRange("A:A").format.columnWidth = 24;
  sheet.getRange("B:B").format.columnWidth = 68;
  sheet.getRange("C:C").format.columnWidth = 58;
}

const csvText = await fs.readFile(metricsPath, "utf8");
const rows = parseCsv(csvText);
const selectedRows = rows.filter((r) => (targetTrial ? r.trial_id === targetTrial : r.sample_name === targetSample));
if (!selectedRows.length) {
  throw new Error(`No batting metrics rows found for ${targetTrial || targetSample} in ${metricsPath}`);
}
const targetRows = new Map(selectedRows.map((r) => [r.metric_key, r]));
const source = targetRows.get("contact_bat_speed_kmh").source_file;
const sourceFileName = source.split("/").pop();
const sourceBaseName = sourceFileName.replace(/\.c3d$/i, "");
const outPath = `${outDir}/${sourceBaseName}_batting_report_metrics.xlsx`;
const ready = targetRows.get("ready_com_height_ratio");
const contact = targetRows.get("contact_bat_speed_kmh");
const highCom = targetRows.get("coach_high_com_risk_index");
const [swingStart, swingEnd] = parseSwingSegment(contact.event_rule);
let swingPeak = "";
try {
  const components = JSON.parse(highCom.components_json || "{}");
  swingPeak = components.swing_peak_frame ?? "";
} catch {
  swingPeak = "";
}
const gifStart = Number.isFinite(Number(swingPeak)) ? Number(swingPeak) - 60 : "";
const gifEnd = Number.isFinite(Number(swingPeak)) ? Number(swingPeak) + 40 : "";

const workbook = Workbook.create();
const report = workbook.worksheets.add("报告指标");
const events = workbook.worksheets.add("事件定位");
const info = workbook.worksheets.add("说明");
await fs.mkdir(outDir, { recursive: true });

const reportRows = [
  ["Vicon 打击两事件报告指标", null, null, null, null, null, null],
  ["说明：本报告按右打假设生成，左腿=前腿、右腿=后腿；该 C3D 无球 marker，Contact Position 用真实挥棒段内 Bat1_Z 最低的几帧近似。", null, null, null, null, null, null],
  [null, null, null, null, null, null, null],
  ["事件", "前端大指标", "后台字段", "数值", "单位", "Vicon数据来源", "说明"],
];

for (const key of ORDER) {
  const row = targetRows.get(key);
  reportRows.push([
    eventLabel(row),
    FRONT_GROUP[key] ?? row.module,
    row.metric_name_zh,
    valueFor(row),
    unitLabel(row.unit),
    row.points_used,
    EXPLAIN[key] ?? row.notes ?? row.formula,
  ]);
}
report.getRange(`A1:G${reportRows.length}`).values = reportRows;
styleMainSheet(report, reportRows.length);
report.tables.add(`A4:G${reportRows.length}`, true, "BattingMetrics");

const eventRows = [
  ["事件定位与算法说明", null, null, null, null, null],
  [null, null, null, null, null, null],
  ["事件", "数组索引", "C3D帧号", "时间(s)", "定位方法", "本文件可行性"],
  ["准备姿态 Ready Position", Number(ready.event_frame), Number(ready.event_frame) + 1, timeSec(ready.event_frame), ready.event_rule, "高"],
  ["击球姿态 Contact Position", Number(contact.event_frame), Number(contact.event_frame) + 1, timeSec(contact.event_frame), contact.event_rule, "中高"],
  ["真实挥棒段 Detected Swing Segment", `${swingStart}-${swingEnd}`, `${swingStart + 1}-${swingEnd + 1}`, `${timeSec(swingStart)}-${timeSec(swingEnd)}`, "基于平滑 Bat1 速度峰值和连续高速段检测，并向前后扩展 0.15s。", "中高"],
  ["3D Reconstruction 动作窗口", `${gifStart}-${gifEnd}`, `${gifStart + 1}-${gifEnd + 1}`, `${timeSec(gifStart)}-${timeSec(gifEnd)}`, "围绕球棒峰值速度帧渲染：前 0.60s、后 0.40s；用于逐帧瞬时速度标注。", "高"],
];
events.getRange(`A1:F${eventRows.length}`).values = eventRows;
styleEventSheet(events, eventRows.length);
events.tables.add(`A3:F${eventRows.length}`, true, "BattingEvents");

const infoRows = [
  ["基础信息", "值", null],
  ["文件", sourceFileName, null],
  ["采样频率", `${c3dRateHz} Hz`, null],
  ["总帧数", c3dFrames ? Number(c3dFrames) : "", null],
  ["前腿/支撑腿假设", "左腿 L", null],
  ["后腿/加载腿假设", "右腿 R", null],
  ["打者站位假设", "右打", null],
  ["球棒 marker", "Bat1-Bat5", null],
  ["数据来源", source, null],
  ["限制", "本 C3D 没有真实球/击球点 marker，因此 Contact 用真实挥棒段内 Bat1_Z 最低帧近似；速度类图像标注为整段 3D window 逐帧瞬时值。", null],
  [null, null, null],
  ["字段", "计算逻辑", "备注"],
  ["Ready Position", "挥棒段前低速且球棒举起的 5 帧", "用于准备姿态、后肘、引棒、重心偏高等指标。"],
  ["Contact Position", "真实挥棒段内 Bat1_Z 最低的 5 帧", "用于球棒速度、Attack Angle、骨盆/躯干旋转、前膝和头部位移。"],
  ["真实挥棒段", "平滑 Bat1 速度峰值附近的连续高速段，再扩展 0.15s", "先排除 trial 前期走动/挥手和打完后棒子滑落，再定位 batting 动作。"],
  ["球棒速度", "norm(diff(Bat1_xyz)/dt) * 3.6 / 1000", "主表为 Contact event 平均值；3D 动图标注为每帧瞬时值。"],
  ["Attack Angle", "atan2(Bat1_velocity_Z, norm(Bat1_velocity_XY))", "负值表示棒头速度方向偏向下。"],
  ["髋肩分离/旋转", "肩线与骨盆线在水平面的角度差或 Ready-to-Contact 变化；对外展示取绝对 opening magnitude", "signed raw value 可能受实验室 Vicon XY 朝向影响，保留在 metrics CSV 的 components_json 中。"],
  ["翻腕风险", "前臂 roll 角速度峰值，使用 RELB/RWRA/RWRB 构建前臂旋转 proxy", "为 marker proxy，不等同真实腕关节内部旋前角。"],
  ["Coach Flags", "将教练语言映射到可计算 proxy 指标", "用于报告解释，不应直接作为医学或伤病判断。"],
];
info.getRange(`A1:C${infoRows.length}`).values = infoRows;
styleInfoSheet(info, infoRows.length);
info.tables.add(`A12:C${infoRows.length}`, true, "BattingNotes");

const errorScan = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(errorScan.ndjson);

for (const sheetName of ["报告指标", "事件定位", "说明"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(`${outDir}/${sourceBaseName}_batting_${sheetName}.png`, new Uint8Array(await preview.arrayBuffer()));
}

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(outPath);
console.log(outPath);
