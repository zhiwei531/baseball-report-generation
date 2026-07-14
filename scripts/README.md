# Scripts map

这个目录同时包含「正式报告入口」、被入口调用的构建器，以及用于局部调试的低层工具。不要把所有脚本当成独立的完整流程来运行。

## 先选入口

| 目标 | 推荐命令 | 说明 |
| --- | --- | --- |
| 生成完整 batting / Vicon 报告 | `python scripts/report_cli.py --config configs/default_report_pipeline.json` | **当前正式入口**；按配置串联全部验证过的 batting stages。 |
| 重新跑 batting 流程（调试编排） | `python scripts/run_batting_report_pipeline.py --config <config.json>` | 正式入口实际调用的编排脚本。通常应使用 `report_cli.py`。 |
| 仅从 Vicon C3D 重建中间表和 3D 资产 | `python scripts/run_vicon_c3d_pipeline.py --input-dir ../vicon_2026` | 不会生成完整 HTML 报告。 |
| 生成 pitching 模板报告 | `python scripts/pitching/build_pitch_template_metrics_report.py ...` | 与 batting pipeline 独立；参数与数据契约见 [`../docs/pitching/PITCHING_PIPELINE.md`](../docs/pitching/PITCHING_PIPELINE.md)。 |

新球员报告应先复制并修改 `configs/default_report_pipeline.json`，使输出指向新的 `reports/vicon_2026_<player>_coach/` 目录。不要直接覆盖 Julian 的报告目录。

## Batting / Vicon 正式流程

`report_cli.py` → `run_batting_report_pipeline.py` 的主要顺序是：

```text
C3D → Vicon CSV / 3D assets → batting event metrics → 3D event GIFs
    → 2D-Vicon alignment → 2D skeleton overlay / 2D-vs-3D QA
    → Vicon-valued 2D metric annotations → HTML / charts → XLSX
```

| 脚本 | 作用 | 主要输出 / 何时单独运行 |
| --- | --- | --- |
| `report_cli.py` | 完整 batting 报告的唯一支持入口；验证配置后启动 pipeline。 | 完整 report build。 |
| `run_batting_report_pipeline.py` | 按依赖顺序调用下列 builder，并传递 config 中的路径与样本名。 | 用于查看、调试或扩展完整流程。 |
| `pipeline_config.py` | 读取、校验、标准化 pipeline JSON config 的共享库。 | **库文件，不直接运行**。 |
| `run_vicon_c3d_pipeline.py` | C3D 子流程编排：抽取 Vicon 表并渲染 3D reconstruction assets。 | CSV、3D PNG/GIF；适合只重建 C3D 产物。 |
| `build_vicon_2026_metrics.py` | 从 Vicon C3D 抽取 trials、marker/point summary 与基础指标表。 | `vicon_2026_metrics.csv`、point summary、all-points CSV。 |
| `render_vicon_reconstruction_images.py` | 将 C3D 运动学重建成 3D 截图和动图。 | `assets/vicon_reconstruction/`。 |
| `build_batting_dashboard_metrics.py` | 从 all-points CSV 识别 Ready / Contact 等事件并计算 batting metrics。 | `batting_dashboard_metrics.csv` 及 wide CSV。 |
| `build_julian_coach_event_gifs.py` | 用事件帧附近的 C3D 重建制作 Ready / Contact GIF。 | `assets/vicon_reconstruction_events/`。 |
| `build_julian_coach_annotated_speed_gifs.py` | 渲染带速度/挥棒方向标注的 3D GIF。 | `assets/vicon_reconstruction_annotated/`。 |
| `align_2d_video_vicon.py` | 对视频运行 MediaPipe 2D pose，并把视频帧映射到 Vicon 时间轴。 | alignment summary、`pose2d_landmarks.csv`。 |
| `render_aligned_2d_overlay.py` | 在对齐后的真实 2D 视频上绘制骨架 overlay。 | `aligned_2d_skeleton_overlay.mp4`。 |
| `render_vicon_3d_2d_alignment_comparison.py` | 生成 2D 视频与 Vicon 3D 的并排 QA 对照。 | comparison MP4 / preview。 |
| `render_vicon_geometry_metrics_on_2d.py` | 将 **Vicon CSV 数值** 以骨架、几何辅助线、leader line、彩色指标卡叠加在 Ready / Contact 2D 视频帧上。2D skeleton 仅定位，不计算显示值。 | `assets/vicon_2d_geometry_annotations/*_vicon_geometry_on_2d.png` 及 event preview MP4。 |
| `annotate_frontend_metric_illustrations.py` | 给前端/报告中的静态教学示意图叠加对应指标说明。 | `assets/frontend_metric_illustrations_annotated_standalone/`。 |
| `build_julian_coach_metrics_section.py` | 生成最终 batting HTML section、指标卡、研究者图与必要的报告资产引用。 | `julian_coach_metrics_section.html`、charts。 |
| `apply_batting_coach_values.py` | 最终 polish：将教练/peer 数据与最终 chart copy 回填到 HTML 并刷新相关资产。 | 完整流程的后段；不要在缺少对应 peer inputs 时单独运行。 |
| `build_batting_metrics_xlsx.mjs` | 从 metrics CSV 导出 Excel workbook。 | `outputs/batting_metrics_excel/`。 |

## Pitching 工具

Pitching 目前不经 `report_cli.py` 自动执行；它是一条独立的模板报告和 2D 对齐路径。

| 脚本 | 作用 |
| --- | --- |
| `pitching/build_pitch_template_metrics_report.py` | 读取 pitching manifest / metrics，生成 pitching HTML、指标表和图表资产。 |
| `pitching/generate_professional_pitch_charts.py` | 单独生成 pitching 的专业化图表。 |
| `pitching/annotate_pitch_lineart_metrics.py` | 在 pitching 的线稿动作图上标注指标。 |
| `pitching/sync_vicon_video.py` | 用动作峰值将 sideline video 与 Vicon C3D 时钟同步，输出 sync JSON / signal CSV。 |
| `pitching/run_vicon_2d_alignment.py` | pitching 2D 对齐的低层编排：sync → MediaPipe alignment → overlay → QA comparison。 |

## 兼容 / 单独导出工具

| 脚本 | 状态与用途 |
| --- | --- |
| `build_benchmark_report_html.py` | 旧版 benchmark HTML builder（Bryan / Green）。不属于当前 final-schema batting 入口；维护旧 benchmark 时才使用。 |
| `generate_vicon_kinetic_chain_flow.py` | 从 Vicon point data 生成单独的 kinetic-chain flow PNG；适合局部重绘或研究图调试。 |
| `export_report_from_html.mjs` | 把 HTML 报告导出为 PDF / PPTX；输入 HTML 路径与导出参数见 `--help` 和 [`../docs/REPORT_README.md`](../docs/REPORT_README.md)。 |

## 常见局部重建

只改 2D 几何标注时，在已完成 alignment 与 metrics 的前提下运行：

```bash
python scripts/render_vicon_geometry_metrics_on_2d.py \
  --alignment-dir outputs/<alignment_name> \
  --metrics reports/vicon_2026_<player>_coach/batting_dashboard_metrics.csv \
  --sample-name <player>
```

只改 HTML / 指标卡时，优先重跑 `build_julian_coach_metrics_section.py`；如果改动会影响事件、数值或对齐，改用完整入口重新生成。详细的输入输出溯源见 [`../docs/ASSET_PROVENANCE.md`](../docs/ASSET_PROVENANCE.md)，全流程说明见 [`../docs/REPORT_README.md`](../docs/REPORT_README.md)。
