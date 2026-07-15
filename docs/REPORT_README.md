# Vicon Benchmark Report README

这份文档保留早期 Bryan/Green benchmark report 的背景、设计规则和历史构建流程。当前可复用的 batting final-schema report 主入口已经迁移到：

```bash
python scripts/report_cli.py final --config configs/final_report.json
```

该入口读取 `configs/default_report_pipeline.json`，并由 `scripts/run_batting_report_pipeline.py` 串联 C3D CSV、3D reconstruction、2D alignment/annotation、HTML schema、researcher charts 和 XLSX stages。新球员报告应复制 config 并输出到 `reports/vicon_2026_<player_slug>_coach/`，不要直接复用 Julian 输出目录。

以下 “benchmark report” 章节仍可用于理解历史 `report.html`、PDF/PPTX 导出和 Vicon 可视化规范，但不是当前 batting final-schema 的推荐操作手册。

## 当前数据原则

当前报告统一 raw data source：身体运动学、逐帧曲线、指标来源表和 C3D 动图都来自
`../vicon_2026` 文件夹下的 Vicon C3D。

- 主分析人：`bryan`
- 教练模块对照：`green`
- 被试名来源：`../vicon_2026/{subfolder}`，子文件夹名就是被试名。
- 临时 coach 参考：投球教练参考暂时沿用既有 `data_full/coach_pose3d/gvhmr/pitch_horizontal_coach.csv` 和相关 coach 指标表，只作为黑色参考线或评分参考，不作为 raw source。

报告不再把 benchmark 视频 CV/GVHMR 身体数据和 Vicon 身体数据混在一起。旧的
`reports/slymask_benchmark_metrics.csv`、RTMPose/GVHMR benchmark pose CSV 和截图缩略图不再作为当前报告主体数据来源。

## 一键构建顺序

在 `baseball-analysis/` 目录运行：

```bash
.venv312/bin/python scripts/run_vicon_c3d_pipeline.py --input-dir ../vicon_2026
.venv312/bin/python scripts/build_benchmark_report_html.py
npm run export:report
```

三步分别完成：

1. `run_vicon_c3d_pipeline.py` 从 `../vicon_2026/*/*.c3d` 读取 C3D，生成 trial 指标、key-pose summary、全帧 marker CSV、pose3d CSV、PNG/GIF/MP4/AVI 和 OBJ key-pose model。
2. `build_benchmark_report_html.py` 读取 Vicon 派生表和原始 C3D，生成 `report.html`。
3. `export_report_from_html.mjs` 读取同一份 HTML，生成 PDF 和 PPTX 导出版本。

注意：第三步需要 `numpy`，请使用 `.venv312/bin/python`，不要用系统 `python3`。

若本地尚未安装浏览器导出依赖，先运行：

```bash
npm install
npx playwright install chromium
```

## HTML 到 PDF/PPTX 导出

导出入口：

```bash
npm run export:report
```

默认产物：

```text
output/pdf/report_from_html.pdf
output/pptx/report_from_html.pptx
```

也可以单独导出：

```bash
npm run export:report:pdf
npm run export:report:pptx
```

设计策略：

- PDF 使用 Chromium 渲染 `report.html` 后按 HTML 自然版式做纵向分段截图，再把每个分段放入 A4 页面。它不会把卡片重新组合成新的 PDF 网格，因此视觉顺序、两列关系、section 间距和 HTML 保持一致。
- PDF 分页点优先选择 `.hero`、`.section-title`、`.module-note`、`article.visual-card`、`.grid`、`.grid-2`、`.grid-3`、`.compact-metrics` 和 `.training` 的自然边界。两列布局会按同一视觉行的最大底部断页，避免出现左列结束但右列卡片被切半的情况。
- PDF 当前不是文本型 print PDF；它是 HTML 分段截图组成的版式 PDF。优先目标是分享时版面稳定、卡片不乱序、不截断、不因浏览器打印分页破坏布局。
- PPTX 使用 HTML 渲染后的卡片级截图，每个 `.visual-card` 生成一页或与相近窄卡片合并为一页幻灯片。这样比固定高度整页截图更不容易在图表、表格和长说明中间切断。
- 导出前脚本会给页面临时注入 `html.export-mode`，把 `.line-chart-scroll`、`.dot-plot-scroll`、`.mini-chart-scroll`、`.table-scroll` 和 `.training` 从横向/纵向滚动容器改成导出友好的展开布局。因此带左右拖动条的 SVG、表格和训练计划不会只截当前可见区域。
- 导出脚本不会改写 `report.html` 源文件；排版调整只在浏览器导出会话中生效。

可选参数示例：

```bash
node scripts/export_report_from_html.mjs \
  --html report.html \
  --pdf output/pdf/vicon_report.pdf \
  --pptx output/pptx/vicon_report.pptx \
  --pdf-media-scale 0.82 \
  --pptx-media-scale 0.9 \
  --work-dir /private/tmp/baseball-report-html-export
```

`--pdf-media-scale` 只影响 PDF 导出会话中 HTML 内图片和 SVG 图表的渲染尺寸，默认 `0.82`；最终 PDF 仍按 HTML 自然版式纵向切片。`--pptx-media-scale` 只影响 PPTX 中单张卡片截图在幻灯片上的显示大小，默认 `0.9`。PPTX 会把较窄的卡片自动两列合并到同一页，提高信息密度；长卡片仍会自动切片，避免表格和图表被截断。

导出中间文件会写入 `--work-dir`：

```text
pdf-html-slices/      PDF 使用的 HTML 纵向分段截图
sliced-report.html    把分段截图重新装入 A4 页面的临时 HTML
screenshots/          PPTX 使用的卡片截图
pptx-preview/         PPTX 预览图与 montage
pptx-qa.json          PPTX 分组与导出清单
```

如果 PDF 排版需要继续微调，优先调整 HTML/CSS 和分段边界，不要回到按 card 重新打包的 PDF 逻辑；重打包会破坏 HTML 里的自然两列关系。

## 分享包

HTML 分享包位于：

```text
output/share/report_html_share/
output/share/report_html_share.zip
```

分享包内保留 `report.html`、本地 GIF 资源和可选导出版本：

```text
report.html
reports/assets/vicon_reconstruction/*.gif
output/pdf/report_from_html.pdf
output/pptx/report_from_html.pptx
README.txt
```

`report.html` 依赖同级 `reports/` 文件夹中的本地资源。压缩包可以直接发给别人；解压后不要只单独移动 HTML 文件。

## 当前纳入的 C3D

| 被试 | 动作 | C3D | 报告用途 |
|---|---|---|---|
| `bryan` | pitching | `vicon_2026/bryan/001 Cal 04 Pitch 05.c3d` | 主体投球分析 |
| `bryan` | batting | `vicon_2026/bryan/001 Cal 04 Bat 05.c3d` | 主体打击分析 |
| `green` | pitching | `vicon_2026/green/006 Pitch 09.c3d` | 教练模块投球对照 |
| `green` | batting | `vicon_2026/green/006 Bat 04.c3d` | 教练模块打击对照 |

## Julian/Coach Batting Metrics Section

`reports/vicon_2026_julian_coach/` 是当前 Julian 与 Coach 打击专项
metrics 的独立工作区。它不生成完整报告，只生成 metrics section、事件 GIF、
速度标注 GIF、2D 几何标注截图和 Excel 指标表。

输入数据：

```text
reports/vicon_2026_julian_coach/vicon_2026_points_all.csv
reports/vicon_2026_julian_coach/vicon_2026_point_summary.csv
../vicon_2026/julian/007-julian Cal 04 Bat 05.c3d
../vicon_2026/coach/008-coach Cal 03 Bat 02.c3d
```

当前推荐构建入口：

```bash
python scripts/report_cli.py final --config configs/final_report.json
```

新球员复用：

```bash
python scripts/report_cli.py \
  --config configs/<player_slug>_report_pipeline.json
```

底层构建顺序由 `scripts/run_batting_report_pipeline.py` 管理：C3D extraction -> batting metrics -> 3D event GIFs -> MediaPipe 2D alignment/overlay -> 2D metric annotations -> static illustration annotations -> HTML schema -> final polish -> XLSX export。单个 builder 命令只建议用于调试 partial rebuild。

主要产物：

```text
reports/vicon_2026_julian_coach/batting_dashboard_metrics.csv
reports/vicon_2026_julian_coach/batting_dashboard_metrics_wide.csv
reports/vicon_2026_julian_coach/julian_coach_metrics_section.html
reports/vicon_2026_julian_coach/assets/vicon_reconstruction_events/julian_ready.gif
reports/vicon_2026_julian_coach/assets/vicon_reconstruction_events/julian_contact.gif
reports/vicon_2026_julian_coach/assets/vicon_reconstruction_annotated/julian_speed_annotated.gif
reports/vicon_2026_julian_coach/assets/vicon_reconstruction_annotated/coach_speed_annotated.gif
reports/vicon_2026_julian_coach/assets/vicon_2d_geometry_annotations/ready_position_vicon_geometry_on_2d.png
reports/vicon_2026_julian_coach/assets/vicon_2d_geometry_annotations/contact_position_vicon_geometry_on_2d.png
reports/vicon_2026_julian_coach/alignment_2d/aligned_2d_skeleton_overlay.mp4
outputs/batting_metrics_excel/007-julian Cal 04 Bat 05_batting_report_metrics.xlsx
```

其中 `vicon_2026_points_all.csv`、`vicon_2026_pose3d.csv`、zip 包和各类
`output/` 导出目录属于本地生成物，不随 Git 提交；仓库保留汇总指标表、HTML
section 和关键 PNG/GIF 可视化资产。需要完整重建时从 C3D 输入重新生成。

当前 HTML section 以 Julian 为主、Coach 为对照。Ready Position 和
Contact Position 的 2D 几何标注图放在各自 section title 正下方，不放在右侧
media 卡片里；图宽接近左侧三个 metrics card 的总宽度。右侧只放 Julian 的事件
GIF；Coach 不在这两块重复放 GIF。3D Reconstruction 速度标注使用 Julian/Coach
两张整段动作窗口 GIF，左侧卡片烘进 GIF，且只显示逐帧瞬时值，不显示
Ready/Contact event 固定汇总值。当前页面展示移除了“击球区稳定性”这一项；
CSV 计算脚本仍保留该项原始计算，方便后续恢复或研究使用。

2D 几何标注图只用于“把 Vicon 3D 计算结果放回视频画面中解释”。数值必须来自
Vicon metrics CSV/Excel，不允许用 2D 关键点重新计算后展示。当前对齐采用：
`video_frame = event_frame + (vicon_time - event_time) * 240`，其中 Vicon 球棒速度
峰值 frame 854 对齐到视频 frame 184；验证点为 844 -> 160、854 -> 184、
870 -> 222。Ready 的 Vicon event center 是 frame 772，但严格映射不在当前 2D
overlay 可视窗口内，所以使用视频开头骨架较稳定的一帧做视觉底图，仍标注 Vicon
frame 772 的几何值。Contact 使用 Vicon frame 853 / video frame 182，因为该帧
2D 骨架比 nominal center 更贴合人体。

最终视觉规则：

- Ready 只标注后侧加载相关几何：后髋角、后膝角、髋肩分离；右打假设下后腿是右腿。
- Contact 只标注接触瞬间几何：骨盆旋转、躯干旋转、前膝角；右打假设下前腿是左腿。
- 关节角不再用角度 arc 表示，改用细实线肢段、夹角处细虚线延长线、从夹角中心引出的细 leader line 和小号角度值。
- 旋转角使用标准单弧箭头；箭头要横向更扁、整体不覆盖太多人体、头部贴近身体轮廓、尾部裁掉约 20%，保留从头到尾约 80% 的弧线。
- 页面文字尽量少；除 metric 名称和值以外，几何关系优先由线、虚线、箭头和颜色表达。

Excel 导出仿照投球 `*_pitch_report_metrics.xlsx` 的三 sheet 结构：

- `报告指标`：7 列指标表，列为事件、前端大指标、后台字段、数值、单位、Vicon 数据来源、说明。
- `事件定位`：Ready、Contact、真实挥棒段和 3D Reconstruction 动作窗口的帧号、时间和定位方法。
- `说明`：基础信息、右打假设、无球 marker 限制和主要计算逻辑。

## 输入与输出

HTML 报告当前直接读取：

```text
reports/vicon_2026_metrics.csv
reports/vicon_2026_point_summary.csv
reports/vicon_2026_points_all.csv
reports/vicon_2026_pose3d.csv
reports/vicon_2026_key_pose_models.csv
reports/assets/vicon_reconstruction/*.png
reports/assets/vicon_reconstruction/*.gif
reports/assets/vicon_reconstruction/*.mp4
reports/assets/vicon_reconstruction/*.avi
reports/assets/vicon_reconstruction_models/*.obj
../vicon_2026/bryan/*.c3d
../vicon_2026/green/*.c3d
output/data/benchmark_pitch_vertical_09_motion_metrics_full.csv
output/data/benchmark_pitch_vertical_09_vs_pitch_horizontal_coach_metrics.csv
data_full/coach_pose3d/gvhmr/pitch_horizontal_coach.csv
```

其中最后三项只用于临时 coach 参考，报告正文会明确标注。主体 raw data source 仍是 Vicon C3D。

构建产物：

```text
report.html
reports/vicon_2026_metrics.csv
reports/vicon_2026_point_summary.csv
reports/vicon_2026_points_all.csv
reports/vicon_2026_pose3d.csv
reports/vicon_2026_key_pose_models.csv
reports/assets/vicon_reconstruction/*.png
reports/assets/vicon_reconstruction/*.gif
reports/assets/vicon_reconstruction/*.mp4
reports/assets/vicon_reconstruction/*.avi
reports/assets/vicon_reconstruction_models/*.obj
```

## 指标计算

`build_vicon_2026_metrics.py` 解析 C3D 后输出 trial 级指标：

- 髋肩分离：髋部轴与肩部轴的 planar yaw 差。
- 前腿膝角：髋、膝、踝 marker 的三点夹角。
- 躯干倾斜：髋部中心到颈/躯干 marker 的向量相对竖直方向的倾角。
- 手部速度：手腕 marker 三维坐标逐帧差分后的峰值速度。
- 髋部/躯干速度：对应 marker 中心的三维速度峰值。
- 球棒速度：Bat1/Bat5 相关 marker 三维速度峰值。
- 挥棒窗口：球棒速度超过该 trial 峰值一定比例的连续高速度窗口。
- 数据质量：C3D 有效点比例。

`build_benchmark_report_html.py` 会继续复用已有评分函数：

- `score_close`：用主体值与参考值的接近程度给分。
- `score_ratio`：用主体值与对照/参考值的比例给分。

但这些分数的主体输入已换成 bryan 的 Vicon 指标。green 只作为教练模块对照。coach 参考只用于投球部分的临时参考线和部分评分目标。

## 逐帧曲线

HTML 构建脚本会直接读取 bryan/green 的原始 C3D，把 Vicon marker 映射到报告内部关节名，然后生成逐帧曲线：

- 投球角度时间曲线：前腿膝角、肘角、躯干倾斜、髋肩分离。
- 投球速度时间曲线：髋部中心、躯干中心、手部末端速度。
- 打击角度时间曲线：前腿膝角、肘角、躯干倾斜、髋肩分离。
- 打击速度时间曲线：髋部中心、躯干中心、手部末端速度。
- 数据质量图：bryan/green 投球与打击的帧数、关节完整率和有效情况。

## C3D 动图

Vicon 动图和模型由 `scripts/run_vicon_c3d_pipeline.py` 预渲染到：

```text
reports/assets/vicon_reconstruction/{trial_id}.png
reports/assets/vicon_reconstruction/{trial_id}.gif
reports/assets/vicon_reconstruction/{trial_id}.mp4
reports/assets/vicon_reconstruction/{trial_id}.avi
reports/assets/vicon_reconstruction_models/{trial_id}_key_pose.obj
```

关键动作帧由 `build_vicon_2026_metrics.py` 自动选择：

- batting：球棒速度峰值帧，规则名 `bat_speed_peak`。
- pitching：主导手/出手侧手部速度峰值帧，规则名 `right_hand_speed_peak` 或 `left_hand_speed_peak`。
- 若速度不可用，退回 `mid_frame_fallback`。

渲染规范：

- PNG 和视频使用同一画布、DPI、相机角度和固定坐标范围；视频每帧不得 autoscale。
- 打击窗口默认关键帧前 `0.6 s`、后 `0.4 s`；投球窗口默认关键帧前 `1.4 s`、后 `0.4 s`，用于包含投球前的前腿抬起阶段。
- 视觉风格为白底浅灰网格、红色人体连接、蓝色 marker、绿色球棒、灰色虚线棒头轨迹。
- 人体和球棒 marker 点上都不标点名；图例只保留球棒和棒头轨迹。
- Y 轴显示中心按脚部 marker 居中；不要为了脚部视觉位置修改 Z 轴范围。
- MP4 用于兼容播放，OpenCV MP4 可能让白底轻微偏黄；MJPG AVI 是颜色更准确的检查/交付视频。

GIF 默认展示关键帧前约 `0.6 s`、后约 `0.4 s` 的窗口，最多 `72` 帧。渲染时使用固定相机视角和固定坐标范围，只画真实身体 marker、`CentreOfMass` 和打击时的 `Bat1-Bat5`。头部 `LFHD/RFHD/LBHD/RBHD` 四点连接为闭合立体面，并全部连接到 `C7`；躯干 `C7/CLAV/STRN/T10/RBAK`、骨盆 `LASI/RASI/LPSI/RPSI`、左右脚踝/跟/趾和 `Bat1-Bat5` 分别连接为刚体结构。

## 报告模块

- 球员模块：只展示 bryan 的投球和打击诊断、评分、关键指标卡、C3D 动图和训练建议。
- 教练模块：展示 bryan vs green 的同源 Vicon 对比；投球保留临时 coach 参考线。
- 研究者模块：展示 C3D 逐帧曲线、C3D 来源表、事件点、数据质量和指标来源表。

## 报告呈现要求

- 投球和打击 metrics 卡片都使用紧凑字号；指标说明保持简短，重点解释 biomechanics 含义，不在卡片里重复 raw data source。
- 每个 motion metric 和 graph 都应有一句中文“怎么看”，解释它和棒球动力链、支撑、分离、挥棒平面或末端速度的关系。
- 队员对比点位图采用一行一个指标、一条横轴、多色点位的形式；图宽约为卡片宽度的 80%，并在卡片内居中。
- C3D 动图 caption 必须说明关键事件、帧号和时间，并描述当前刚体连接方式。
- 研究者曲线和数据质量图保持紧凑，不使用过宽 SVG；图例、坐标轴、单位和事件标签不能互相覆盖。

## 已知限制

- 当前 coach 参考还没有统一到 Vicon C3D，报告已标为临时参考。
- Vicon 打击的 `swing_time_sec` 是高速挥棒窗口，不是 bat-ball contact time。
- `valid_point_pct` 只表示 C3D 点有效率，不等同真实头部稳定评分。
- 攻击角目前是球棒轴相对水平面的角度，严格 attack angle 仍需要真实击球点/接触帧。
- 训练建议用于训练参考，不是医学诊断。
