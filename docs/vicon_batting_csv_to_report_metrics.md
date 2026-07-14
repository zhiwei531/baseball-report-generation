# Vicon Batting Trial: CSV 到 Report 的指标流程

本文整理当前 Vicon batting trial 从 CSV 提取、指标计算到 HTML report 展示的实际流程。内容以当前代码为准，主要对应：

- `configs/default_report_pipeline.json`
- `scripts/report_cli.py --config configs/default_report_pipeline.json`
- `scripts/run_batting_report_pipeline.py`
- `scripts/build_batting_dashboard_metrics.py`
- `scripts/build_julian_coach_metrics_section.py`
- `reports/vicon_2026_julian_coach/batting_dashboard_metrics.csv`

当前生产入口是 config-driven pipeline。单个 builder 仍有 Julian/Coach 命名假设：HTML builder 默认把 `sample_name == "julian"` 当作主体球员，把 `sample_name == "coach"` 当作教练参考。迁移到其他球员时，先复制 `configs/default_report_pipeline.json`，改 `report_dir`、`video`、`c3d_file`、`sample_name` 等字段；如需彻底去 Julian 文件名前缀，还需要继续参数化 HTML builder。

## 1. 总体数据流

```text
Vicon C3D
  -> vicon_2026_points_all.csv
  -> build_batting_dashboard_metrics.py
  -> batting_dashboard_metrics.csv            # 长表，一行一个指标
  -> batting_dashboard_metrics_wide.csv       # 宽表，一行一个 trial
  -> build_julian_coach_event_gifs.py         # Ready / Contact 事件 GIF
  -> build_julian_coach_annotated_speed_gifs.py
  -> build_julian_coach_metrics_section.py
  -> julian_coach_metrics_section.html
```

标准生成命令：

```bash
python scripts/report_cli.py --config configs/default_report_pipeline.json
```

新球员复用时：

```bash
python scripts/report_cli.py \
  --config configs/<player_slug>_report_pipeline.json
```

分阶段调试命令：

```bash
.venv312/bin/python scripts/build_batting_dashboard_metrics.py \
  --points reports/vicon_2026_<player_slug>_coach/vicon_2026_points_all.csv \
  --out reports/vicon_2026_<player_slug>_coach/batting_dashboard_metrics.csv \
  --wide-out reports/vicon_2026_<player_slug>_coach/batting_dashboard_metrics_wide.csv \
  --ready-valid-start-frame <ready_valid_start_frame>

MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
.venv312/bin/python scripts/build_julian_coach_event_gifs.py \
  --metrics reports/vicon_2026_<player_slug>_coach/batting_dashboard_metrics.csv

MPLCONFIGDIR=/private/tmp/baseball_mpl_cache \
XDG_CACHE_HOME=/private/tmp/baseball_xdg_cache \
.venv312/bin/python scripts/build_julian_coach_annotated_speed_gifs.py \
  --metrics reports/vicon_2026_<player_slug>_coach/batting_dashboard_metrics.csv \
  --points reports/vicon_2026_<player_slug>_coach/vicon_2026_point_summary.csv

.venv312/bin/python scripts/build_julian_coach_metrics_section.py \
  --metrics reports/vicon_2026_<player_slug>_coach/batting_dashboard_metrics.csv \
  --out reports/vicon_2026_<player_slug>_coach/<player_slug>_coach_metrics_section.html
```

## 2. 输入 CSV 结构

`build_batting_dashboard_metrics.py` 读取 `vicon_2026_points_all.csv`。该表是逐帧、逐 marker 的长表，关键字段包括：

| 字段 | 用途 |
| --- | --- |
| `trial_id` | 试次 ID |
| `sample_name` | 样本名，例如 `julian`、`coach` |
| `athlete` | 被试名 |
| `action_type` | 动作类型；脚本只保留 `batting` |
| `source_file` | 原始 C3D 来源 |
| `frame_index` | Vicon 帧号 |
| `timestamp_sec` | 时间戳 |
| `point` | marker 名，例如 `Bat1`、`LASI`、`RASI` |
| `x_mm/y_mm/z_mm` | marker 三维坐标，单位 mm |
| `valid` | 当前点是否有效；脚本只读取 `valid == 1` |

脚本按 `trial_id` 聚合成每个 trial 的帧序列和 marker 三维数组，再计算事件和指标。

## 3. 事件定义

当前指标不是全 trial 平均，也不是固定时间窗，而是先定位真实挥棒段，再在事件窗口上聚合。

### 3.1 挥棒段检测

1. 使用 `Bat1` 三维坐标计算逐帧速度：
   `speed_kmh = norm(diff(Bat1_xyz_mm) / 1000) * rate_hz * 3.6`。
2. 对 Bat1 速度做小窗口平滑。
3. 找到平滑后速度峰值 `swing_peak_idx`。
4. 速度阈值为 `max(8 km/h, peak_speed * 0.20)`。
5. 从速度峰值向前、向后找连续高于阈值的 active block。
6. 将该 block 前后各扩展约 `0.15 s`，得到 `swing_segment`。

### 3.2 Ready Position

Ready Position 是挥棒段之前的低速、球棒抬起窗口。默认参数：

- `--ready-event-frames 5`
- `--ready-lookback-sec 0.68`
- 可用 `--ready-valid-start-frame` 排除试次开头的走动、挥棒前干扰帧

选择规则：

1. 在挥棒开始前的 lookback 区间内找候选帧。
2. 候选帧必须有 `Bat1`、`Bat5`、头部 marker 和 Bat1 速度。
3. 低速阈值为 `max(6 km/h, peak_speed * 0.12)`。
4. 找连续 5 帧低速 block。
5. 优先选择 `Bat1_Z` 更高的 raised-bat block；速度更低作为 tie-breaker。

### 3.3 Contact Position

Contact Position 当前是接触代理点，因为没有球 marker 或真实击球事件标记。默认参数：

- `--contact-event-frames 5`

选择规则：

1. 只在 `swing_segment` 内搜索。
2. 选择 `Bat1_Z` 最低的 5 帧。
3. 如果无法找到有效帧，回退到 bat-speed peak 单帧。

注意：`contact_bat_speed_kmh` 是 Contact event 5 帧平均，不是整次挥棒最大球棒速度。

## 4. 输出 Metrics CSV

`batting_dashboard_metrics.csv` 是长表，一行一个 sample 的一个指标。核心字段：

| 字段 | 含义 |
| --- | --- |
| `trial_id` | 试次 ID |
| `sample_name` | 样本名；report 当前依赖 `julian` / `coach` |
| `module` | `Ready Position`、`Contact Position`、`Coach Flag` |
| `metric_name_zh` | 中文指标名 |
| `metric_key` | 后端稳定字段名 |
| `value` | 指标值 |
| `unit` | `deg`、`km/h`、`mm`、`height_ratio`、`0-100 risk`、`0-100 score` |
| `aggregation` | 聚合方式说明 |
| `event_name` | 指标依赖的事件 |
| `event_rule` | 事件检测规则说明 |
| `event_frame` | 事件中心帧 |
| `event_frames` | 参与聚合的帧号列表 |
| `points_used` | 使用的 Vicon marker |
| `formula` | 公式说明 |
| `components_json` | 额外组件，例如瞬时值、signed raw value、稳定性组件 |
| `notes` | 解释和限制 |

`batting_dashboard_metrics_wide.csv` 是同一批指标的宽表，用于快速检查和 Excel 导出。

## 5. 打击指标定义

当前 CSV 输出 17 个指标，其中 HTML 用户界面主要展示前 16 个；`coach_hitting_zone_stability_score` 是隐藏或研究用途指标。

### 5.1 Ready Position 指标

| metric_key | 中文名 | 聚合 | 定义 |
| --- | --- | --- | --- |
| `ready_com_height_ratio` | 重心高度 | Ready 5 帧均值 | `mean(COM_Z_ready) / height_proxy`。优先用 `CentreOfMass`，缺失时用 `0.6 * hip_mid + 0.4 * trunk_mid`；`height_proxy = head_Z - feet_Z`。 |
| `ready_rear_hip_flexion_deg` | 后髋屈曲角 | Ready 5 帧均值 | `180 - angle(shoulder_mid, rear_hip, rear_knee)`。当前假设右打：后侧为右侧。 |
| `ready_rear_knee_flexion_deg` | 后膝屈曲角 | Ready 5 帧均值 | `180 - angle(rear_hip, rear_knee, rear_ankle)`。 |
| `ready_hip_shoulder_separation_deg` | 髋肩分离角 | Ready 5 帧均值 | `abs(wrap_to_180(torso_rotation_xy - pelvis_rotation_xy))`。 |
| `ready_bat_tilt_deg` | 球棒倾角 | Ready 5 帧均值 | `atan2(abs((Bat1 - Bat5)_Z), norm((Bat1 - Bat5)_XY))`；0° 接近水平，90° 接近垂直。 |
| `ready_hand_height_ratio` | 握棒手高度 | Ready 5 帧均值 | `mean(grip_hand_center_Z_ready) / height_proxy`；握棒手中心为左右手腕中心均值。 |

### 5.2 Contact Position 指标

| metric_key | 中文名 | 聚合 | 定义 |
| --- | --- | --- | --- |
| `contact_bat_speed_kmh` | 球棒速度 | Contact 5 帧均值 | `mean(norm(diff(Bat1_xyz) / dt)) * 3.6 / 1000`。这是 contact proxy 附近速度，不是峰值速度。 |
| `contact_attack_angle_deg` | 挥棒路径角 | Contact 5 帧均值 | `atan2(Bat1_velocity_Z, norm(Bat1_velocity_XY))`；负值表示棒头速度方向偏向下。 |
| `contact_pelvis_rotation_open_deg` | 骨盆旋转角 | Contact 5 帧均值 | `abs(wrap_to_180(pelvis_rotation_xy_contact - mean(pelvis_rotation_xy_ready)))`；显示值是方向归一化后的打开幅度，signed raw value 存在 `components_json`。 |
| `contact_torso_rotation_open_deg` | 躯干旋转角 | Contact 5 帧均值 | `abs(wrap_to_180(torso_rotation_xy_contact - mean(torso_rotation_xy_ready)))`；显示值是方向归一化后的打开幅度。 |
| `contact_front_knee_flexion_deg` | 前膝屈曲角 | Contact 5 帧均值 | `180 - angle(front_hip, front_knee, front_ankle)`。当前假设右打：前侧为左侧。 |
| `ready_to_contact_head_displacement_mm` | 头部位移 | Ready 到 Contact 事件差值 | `norm(mean(head_center_contact) - mean(head_center_ready))`。 |

### 5.3 Coach Flag 指标

| metric_key | 中文名 | 聚合 | 定义 |
| --- | --- | --- | --- |
| `coach_high_com_risk_index` | 重心偏高指数 | Ready 组合风险 | `100 * mean(clip((COM_height_ratio - 0.48) / 0.14), clip((35 - rear_hip_flexion) / 35), clip((35 - rear_knee_flexion) / 35))`；越高表示重心偏高且后髋/后膝更直。 |
| `coach_rear_elbow_height_diff_mm` | 后肘高度差（掉肘） | Ready 5 帧均值 | `mean(rear_elbow_Z - rear_shoulder_Z)`；负值表示后肘低于后肩。 |
| `coach_bat_loading_angle_to_catcher_deg` | 球棒加载角（引棒不足） | Ready 5 帧均值 | `angle(project_xy(Bat5 - Bat1), catcher_direction)`；`catcher_direction = -project_xy(mean(Bat1_velocity_contact))`。 |
| `coach_rollover_forearm_roll_velocity_deg_s` | 手腕翻转角速度（翻腕） | Contact 5 帧峰值 | `max(abs(d/dt signed_angle_about_axis(wrist_marker_axis, elbow_to_wrist_axis, global_Z_reference)))`；是前臂旋前 proxy，只解释幅度。 |

### 5.4 隐藏或研究指标

| metric_key | 中文名 | 聚合 | 定义 |
| --- | --- | --- | --- |
| `coach_hitting_zone_stability_score` | 击球区稳定性 | 高速击球区组合分 | 使用 `swing_segment` 内 Bat1 速度达到该段峰值 90% 以上的帧。`100 * mean(clip(path_length_mm / 650), clip(1 - attack_angle_std_deg / 18), clip(1 - mean_curvature_1_per_mm / 0.006))`；越高表示路径更长、攻击角波动更小、曲率更低。 |

## 6. Report 如何组织指标

HTML report 不是逐项原样展示 CSV，而是把 backend 指标组织成 player-facing front metrics、coach issue cards 和 researcher evidence。

### 6.1 Front metric 组合卡

`FRONT_METRICS` 将 14 张前端卡片映射到一个或多个 backend 指标：

| 前端卡片 | 所属事件 | backend 指标与权重 |
| --- | --- | --- |
| 平衡 | Ready Position | `ready_com_height_ratio` 0.6 + `ready_to_contact_head_displacement_mm` 0.4 |
| 下肢加载 | Ready Position | `ready_rear_hip_flexion_deg` 0.5 + `ready_rear_knee_flexion_deg` 0.5 |
| 躯干蓄力 | Ready Position | `ready_hip_shoulder_separation_deg` 1.0 |
| 球棒准备 | Ready Position | `ready_bat_tilt_deg` 0.55 + `ready_hand_height_ratio` 0.45 |
| 球棒效率 | Contact Position | `contact_bat_speed_kmh` 1.0 |
| 挥棒轨迹 | Contact Position | `contact_attack_angle_deg` 1.0 |
| 下半身姿态 | Contact Position | `contact_pelvis_rotation_open_deg` 1.0 |
| 上半身姿态 | Contact Position | `contact_torso_rotation_open_deg` 1.0 |
| 支撑能力 | Contact Position | `contact_front_knee_flexion_deg` 1.0 |
| 稳定性 | Contact Position | `ready_to_contact_head_displacement_mm` 1.0 |
| 重心偏高 | 专项问题 | `coach_high_com_risk_index` 1.0 |
| 掉肘 | 专项问题 | `coach_rear_elbow_height_diff_mm` 1.0 |
| 引棒不足 | 专项问题 | `coach_bat_loading_angle_to_catcher_deg` 1.0 |
| 翻腕 | 专项问题 | `coach_rollover_forearm_roll_velocity_deg_s` 1.0 |

每张前端卡片显示：

- 中文卡片名
- 英文解释
- `优秀 / 良好 / 待提高` badge
- 0-100 分数
- 其他球员或教练对照区间
- 训练解释文案
- 对应动作示意图

### 6.2 Backend metric 卡

HTML 还会对 backend metrics 生成 metric card。Ready 和 Contact 指标按模块展示；Coach Flag 指标进入“专项问题”。每张 backend card 显示该球员数值、教练参考值、差值、同队/同龄对比区间和解释。

### 6.3 Researcher evidence

研究者视角主要使用：

- `event_frame` / `event_frames`
- `components_json`
- Vicon 3D GIF
- 速度和角度时间曲线
- kinetic-chain 图

这些图用于说明事件定位、速度曲线、动作链条和数据来源，不改变前端分档规则。

## 7. “优 - 良 - 待提高”区间

当前 report 实际使用的是三档：

```text
优秀 / 良好 / 待提高
```

如果对外交付需要写成“优 - 良 - 待提高”，可以把 `优秀` 视为 `优`。代码里的 CSS class 是：

| 中文状态 | CSS class | 含义 |
| --- | --- | --- |
| 优秀 | `good` | 接近或优于教练参考 |
| 良好 | `review` | 可用，但和参考有一定差距，建议观察或训练 |
| 待提高 | `risk` | 明显偏离参考，应作为优先改进项 |

### 7.1 前端组合卡分档

组合卡先把每个 backend 指标转换成 0-100 分，再按权重平均。分档规则：

| 分数区间 | 状态 |
| --- | --- |
| `score >= 85` | 优秀 / 优 |
| `65 <= score < 85` | 良好 |
| `score < 65` | 待提高 |

### 7.2 单个 backend 指标的组件分数

对每个 backend 指标，先和教练参考值 `standard` 比较。一般指标用绝对相对差：

```text
diff_ratio = abs(player_value - coach_value) / max(abs(coach_value), 1.0)
```

下列越低越好的指标使用方向性差值，只惩罚球员高于教练参考的部分：

```text
coach_high_com_risk_index
coach_rollover_forearm_roll_velocity_deg_s
ready_to_contact_head_displacement_mm
```

```text
diff_ratio = max(0, (player_value - coach_value) / max(abs(coach_value), 1.0))
```

组件分数映射：

| diff_ratio 区间 | 分数计算 | 大致解释 |
| --- | --- | --- |
| `<= 0.12` | `100 - diff_ratio / 0.12 * 8` | 92-100 分，接近教练参考 |
| `0.12 - 0.30` | `92 - (diff_ratio - 0.12) / 0.18 * 22` | 70-92 分，中等差距 |
| `0.30 - 0.60` | `70 - (diff_ratio - 0.30) / 0.30 * 30` | 40-70 分，明显差距 |
| `> 0.60` | `max(20, 40 - (diff_ratio - 0.60) / 0.40 * 20)` | 20-40 分，较大差距 |

组合卡就是这些组件分数的加权平均。

### 7.3 Backend metric card 分档

backend metric card 不显示 0-100 组合分，而是直接按和 coach 的差距分状态。

一般指标：

| 相对差距 | 状态 |
| --- | --- |
| `ratio <= 0.12` | 优秀 / 优 |
| `0.12 < ratio <= 0.30` | 良好 |
| `ratio > 0.30` | 待提高 |

其中：

```text
ratio = abs(player_value - coach_value) / max(abs(coach_value), 1.0)
```

方向性指标：

| metric_key | 判定 |
| --- | --- |
| `coach_high_com_risk_index` | 球员值 `<=` 教练值为优秀，否则待提高 |
| `coach_rollover_forearm_roll_velocity_deg_s` | 球员值 `<=` 教练值为优秀，否则待提高 |
| `ready_to_contact_head_displacement_mm` | 球员值 `<=` 教练值为优秀，否则待提高 |
| `coach_hitting_zone_stability_score` | 球员值 `>=` 教练值为优秀，否则待提高 |

如果球员值或教练值缺失，当前 report 默认显示 `良好` / `review`，但这更像是前端兜底，不应作为真实训练判断。正式报告建议改成“需复核”或“数据不足”。

## 8. 当前实现限制

1. 当前 batting handedness 固定为右打：后侧为右侧，前侧为左侧。左打球员需要参数化 `choose_batting_side()`。
2. Contact Position 是 `Bat1_Z` 最低点代理，不是真实球棒击球点；没有球 marker 时不能声称是真实 contact。
3. `build_julian_coach_metrics_section.py` 仍硬编码 `julian` 和部分 `julian_*.gif` 资源名。
4. `coach_hitting_zone_stability_score` 已在 CSV 中计算，但当前 Julian metrics section 主要隐藏或研究使用。
5. 分档区间主要是“相对教练参考”的工程规则，不是医学或生物力学诊断阈值。
6. 缺失值当前 fallback 为 `良好`，正式复用时建议改成独立的 `数据不足 / 需复核` 状态。

## 9. 建议后续标准化

当前已经把主入口路径、球员输出目录、2D 视频、C3D、MediaPipe model、XLSX 输出目录等集中到 `configs/default_report_pipeline.json`。

HTML final-schema builder 目前只保留 `scripts/build_julian_coach_metrics_section.py`。它必须以
`baseball-analysis/reports/vicon_2026_julian_coach 4/julian_coach_metrics_section.html`
为标准模板对齐后再复用；不要保留或推荐未通过该模板校验的泛化 builder，否则容易造成颜色 schema、卡片内部结构和资源位置漂移。

后续如果要支持任意球员，应在现有标准 builder 内做参数化，并继续校验以下内容：

- player / coach sample name
- batting handedness
- Ready valid start frame
- 资源文件名前缀
- `优秀 / 良好 / 待提高` 阈值
- 缺失值状态
