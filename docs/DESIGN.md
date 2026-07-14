---
version: alpha
name: youth-baseball-pitch-report-design-guide
description: 青少年棒球动作体检 HTML 报告的设计指南。该系统服务于国内棒球俱乐部、家长、儿童运动员、教练和研究者，目标不是单一科研论文或单一 PDF，而是把 3D 动作捕捉、教练对照、球员对比、原始数据和训练建议整理成三个相互独立的中文 HTML 模块：球员模块、教练模块、研究者模块；每个模块分别支持 pitching 和 batting 分析。PDF 和 PPTX 只作为同一 HTML 视觉系统下的导出或展示版本。

colors:
  primary: "#2563eb"
  on-primary: "#ffffff"
  ink: "#101828"
  ink-hover: "#111827"
  body: "#344054"
  body-mid: "#667085"
  mute: "#98a2b3"
  hairline: "#d0d5dd"
  canvas: "#f5f7fb"
  canvas-soft: "#eef6ff"
  canvas-card: "#ffffff"
  canvas-mid: "#e4e7ec"
  accent-sunset: "#f97316"
  accent-sunset-soft: "#ffedd5"
  accent-dusk: "#101828"
  accent-twilight: "#dbeafe"
  accent-breeze: "#60a5fa"
  accent-ai-blue: "#4f5eea"
  accent-violet: "#7c4dff"
  accent-midnight: "#0f172a"
  semantic-good: "#16a34a"
  semantic-good-soft: "#dcfce7"
  semantic-warn: "#f97316"
  semantic-warn-soft: "#fff7ed"
  semantic-risk: "#ef4444"
  semantic-risk-soft: "#fef2f2"
  semantic-review: "#e89918"
  semantic-unavailable: "#697586"
  semantic-unavailable-soft: "#eef2f7"

typography:
  display-xl:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 56px
    fontWeight: 500
    lineHeight: 66px
    letterSpacing: 0px
  display-lg:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 45px
    fontWeight: 500
    lineHeight: 56px
    letterSpacing: 0px
  display-md:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 34px
    fontWeight: 500
    lineHeight: 44px
    letterSpacing: 0px
  display-sm:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 27px
    fontWeight: 500
    lineHeight: 36px
    letterSpacing: 0px
  display-xs:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 24px
    fontWeight: 500
    lineHeight: 32px
  body-lg:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 24px
    fontWeight: 400
    lineHeight: 34px
  body-md:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 20px
    fontWeight: 400
    lineHeight: 30px
  body-sm:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 18px
    fontWeight: 400
    lineHeight: 26px
  caption-mono:
    fontFamily: SFMono-Regular, Menlo, Monaco, ui-monospace, monospace
    fontSize: 18px
    fontWeight: 400
    lineHeight: 24px
    letterSpacing: 0px
  caption-mono-sm:
    fontFamily: SFMono-Regular, Menlo, Monaco, ui-monospace, monospace
    fontSize: 16px
    fontWeight: 400
    lineHeight: 22px
    letterSpacing: 0px
  button-md:
    fontFamily: STHeiti, PingFang SC, Microsoft YaHei, system-ui, sans-serif
    fontSize: 20px
    fontWeight: 500
    lineHeight: 28px

rounded:
  none: 0px
  sm: 12px
  pill: 9999px
  full: 9999px
  card: 24px
  hero: 26px

spacing:
  xxs: 4px
  xs: 8px
  sm: 12px
  md: 18px
  lg: 24px
  xl: 32px
  2xl: 48px
  3xl: 64px
  4xl: 78px

components:
  nav-bar:
    backgroundColor: "{colors.canvas-card}"
    textColor: "{colors.primary}"
    typography: "{typography.body-lg}"
    padding: "{spacing.lg} {spacing.4xl}"
  nav-link:
    textColor: "{colors.body-mid}"
    typography: "{typography.body-md}"
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.on-primary}"
    borderColor: "{colors.primary}"
    typography: "{typography.button-md}"
    rounded: "{rounded.pill}"
    padding: "{spacing.xs} {spacing.lg}"
  button-outline-on-dark:
    backgroundColor: "{colors.accent-dusk}"
    textColor: "{colors.accent-twilight}"
    borderColor: "{colors.accent-dusk}"
    typography: "{typography.button-md}"
    rounded: "{rounded.pill}"
    padding: "{spacing.xs} {spacing.lg}"
  button-outline-sm:
    backgroundColor: "{colors.canvas-soft}"
    textColor: "{colors.primary}"
    borderColor: "#bfdbfe"
    typography: "{typography.body-sm}"
    rounded: "{rounded.pill}"
    padding: "{spacing.xs} {spacing.md}"
  text-input:
    backgroundColor: "{colors.accent-dusk}"
    textColor: "#e5e7eb"
    borderColor: "{colors.accent-dusk}"
    typography: "{typography.body-sm}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md} {spacing.lg}"
  card-content:
    backgroundColor: "{colors.canvas-card}"
    textColor: "{colors.ink}"
    borderColor: "{colors.canvas-mid}"
    typography: "{typography.body-md}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  card-feature-product:
    backgroundColor: "{colors.canvas-card}"
    textColor: "{colors.ink}"
    borderColor: "{colors.canvas-mid}"
    typography: "{typography.body-md}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  hero-band:
    backgroundColor: "{colors.accent-dusk}"
    textColor: "{colors.on-primary}"
    typography: "{typography.display-xl}"
    padding: "{spacing.2xl} {spacing.2xl}"
  content-band:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.ink}"
    typography: "{typography.display-md}"
    padding: "{spacing.2xl} {spacing.4xl}"
  eyebrow-mono:
    textColor: "{colors.primary}"
    typography: "{typography.caption-mono}"
  divider-hairline:
    borderColor: "{colors.hairline}"
  footer:
    backgroundColor: "{colors.canvas}"
    textColor: "{colors.mute}"
    typography: "{typography.body-sm}"
    padding: "{spacing.lg} {spacing.4xl}"

  # ─── Examples (illustrative) — report-native sections and chart blocks ───
  ex-pricing-tier:
    description: "基础版报告交付卡。用于说明家长版 HTML 包含红黄绿诊断、关键截图和训练建议。"
    backgroundColor: "{colors.canvas-card}"
    textColor: "{colors.ink}"
    borderColor: "{colors.canvas-mid}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  ex-pricing-tier-featured:
    description: "专业版报告交付卡。用于强调 3D 骨架、教练对照、同龄对比、CSV 数据、动态图和可导出演示版本。"
    backgroundColor: "{colors.accent-dusk}"
    textColor: "{colors.on-primary}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  ex-product-selector:
    description: "报告模块选择器。按首页仪表盘、动作对照、动力链、训练建议、复测档案组织内容。"
    backgroundColor: "{colors.canvas-soft}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  ex-cart-drawer:
    description: "交付物清单。列出 HTML 报告、可导出 PDF、可展示 PPTX、3D 模型视频、数据表和年度成长档案。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
    item-divider: "{colors.hairline}"
  ex-app-shell-row:
    description: "报告目录行。当前 section 用蓝色竖条标记，辅助课程汇报或后续 dashboard 迁移。"
    backgroundColor: "{colors.canvas}"
    activeIndicator: "{colors.primary}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md} {spacing.lg}"
  ex-data-table-cell:
    description: "指标表格单元格。表头简短，正文只保留数值、单位、教练参考和一句解释。"
    headerBackground: "{colors.canvas-soft}"
    headerTypography: "{typography.body-sm}"
    bodyTypography: "{typography.body-sm}"
    cellPadding: "{spacing.md} {spacing.lg}"
    rowBorder: "{colors.hairline}"
  ex-auth-form-card:
    description: "提示词留档卡。深色背景展示完整输入内容，仅用于课程任务或内部审查。"
    backgroundColor: "{colors.accent-dusk}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  ex-modal-card:
    description: "数据说明卡。用于解释 3D 速度、身体中心位移、球速估算等可靠性边界。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.card}"
    padding: "{spacing.xl}"
  ex-empty-state-card:
    description: "暂缺数据占位。用于 Vicon、雷达枪或真实教练数据缺失时，说明当前模块的计算限制。"
    backgroundColor: "{colors.canvas-soft}"
    rounded: "{rounded.card}"
    padding: "{spacing.2xl}"
    captionTypography: "{typography.body-md}"
  ex-toast:
    description: "重要提示条。浅蓝底、蓝色标题，用于测量说明、读图顺序、风险提示和复测建议。"
    backgroundColor: "{colors.canvas-soft}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md} {spacing.lg}"
    typography: "{typography.body-sm}"
  ex-priority-list:
    description: "本次先看什么。按训练优先级列出 3-5 个问题，每行包含排序、短标题、家长解释和状态标签。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.sm}"
    padding: "{spacing.md}"
    item-divider: "{colors.hairline}"
  ex-score-radar:
    description: "五维或六维评分图。用于球员模块首屏，必须配分数图例和最弱项说明。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.sm}"
    padding: "{spacing.lg}"
  ex-training-calendar:
    description: "7 天家庭训练与复测计划。把训练建议转成日程、检查点和复测动作。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.sm}"
    padding: "{spacing.lg}"
  ex-source-table:
    description: "研究者模块原始数据表。用于 CV/Vicon 字段追溯，必须可滚动、可下载、保留 sample-field-value 结构。"
    backgroundColor: "{colors.canvas-card}"
    rounded: "{rounded.sm}"
    padding: "{spacing.lg}"

---


## Overview

这份设计系统用于青少年棒球动作体检 HTML 报告。报告不再是单一投球 PDF，而是一个按读者角色拆分的 HTML report：球员模块、教练模块、研究者模块。三个模块互相独立，可以单独打开、单独导出、单独分享；每个模块内部都分别包含 pitching 和 batting 两类动作分析。

报告主体应直接生成 HTML，而不是先生成整页图片再嵌入 PDF。HTML 采用浅灰画布 `{colors.canvas}`、白色圆角卡片 `{colors.canvas-card}`、蓝色章节标识 `{colors.primary}` 和绿/橙/红语义编码。整体风格是中文运动体检报告，而不是学术图谱或工程日志。首页用深色英雄区承载报告标题和视频截图，后续模块使用稳定的顶部栏、内容卡片和白卡布局；如需 PDF，应由同一份 HTML 通过打印样式导出，保证格式统一。

内容倾向按读者区分。球员模块要求易读、直白、照片和骨架可视化优先，重点回答主体球员“我哪里做得好、哪里要改、练什么”；教练模块更关注参数、对比图、球员之间差异和改进方案，允许更专业的术语和多指标图表；研究者模块展示 raw data、速度/角度时间序列、事件检测、数据质量和方法说明，风格接近论文 research work。

**Module Architecture:**
- **球员模块**：面向球员和家长。Pitching 与 batting 独立展示，每类动作包含关键截图、骨架叠加、关节角度标注、六维 overall 评分、key metrics、3-5 条训练建议和复测目标。
- **教练模块**：面向教练和体能训练人员。Pitching 与 batting 独立展示，每类动作包含主体球员 vs 教练参考、主体球员 vs 其他球员、短板排序、动作偏差图、训练优先级和队内对比。
- **研究者模块**：面向科研和工程复盘。Pitching 与 batting 独立展示，每类动作包含 raw CV/Vicon/3D pose 数据、事件点、速度-时间曲线、角度-时间曲线、置信度/缺失率/平滑说明和可复现实验参数。

**Key Characteristics:**
- 全中文输出。标题、解释、结论、图表标题、图例、caption、表头和训练建议均使用中文；英文只作为必要技术缩写，例如 `3D`、`Vicon`、`CV`。面向用户的速度和距离单位必须使用中文常用单位。
- HTML 为主交付。PDF 从 HTML 打印导出，PPTX 从同一组件和图表资产派生，避免三套格式各自排版。
- 三模块独立。球员、教练、研究者不能混在同一叙事流里；同一个指标在三个模块里可以用不同解释深度。
- Pitching 与 batting 独立。两个动作类型不能共用一套章节标题和指标解释；每类动作都有自己的核心指标、阶段事件和训练建议。
- 家长友好但不牺牲专业性。球员模块直白，教练模块更专业，研究者模块保留 raw data 和方法细节。
- 可量化。所有核心结论尽量落到角度、速度、距离、百分比、相位时间、队内百分位或与参考值差距。
- 可对照。主分析对象、教练参考、同龄样本和队内其他球员必须使用同一指标口径；跨模块对比要标明数据来源。
- 可训练。每个主要短板必须连接到具体练习、训练频率、复测指标和风险提示。
- 谨慎表达可靠性。3D 关节角适合看相对差距；3D 速度、身体中心位移和球速估算必须注明边界。
- 真实数据优先。只要当前 CSV 或三维姿态序列能计算出图表，就必须生成真实图；只有真实数据不足时才保留 placeholder，并明确写缺什么数据。
- 图表紧凑可读。图表宽度必须服务卡片阅读，不为了横向展开而拉长 x 轴；桌面双栏卡片内图表应按卡片宽度自适应，不强制横向滚动。

## Colors

### Brand & Accent
- **实验室蓝** (`{colors.primary}` — `#2563eb`): 主品牌色。用于页眉品牌、章节竖条、重点标签、提示框标题和图表主色。
- **深色英雄区** (`{colors.accent-dusk}` — `#101828`): 首页英雄卡和提示词页输入卡的背景，制造专业感和视觉锚点。
- **浅蓝说明底** (`{colors.canvas-soft}` — `#eef6ff`): 用于测量说明、读图顺序、复测提醒等解释性提示框。
- **暖橙强调** (`{colors.accent-sunset}` — `#f97316`): 用于需要优先改进但不是高风险的指标、差距数值和训练重点。
- **浅橙底** (`{colors.accent-sunset-soft}` — `#ffedd5`): 用于“训练建议”等温和提醒标签。
- **模型对照蓝** (`{colors.accent-breeze}` — `#60a5fa`): 标准姿态纠正图里代表孩子原始姿态的浅蓝虚线。
- **评分蓝紫** (`{colors.accent-ai-blue}` — `#4f5eea`): 五维/六维评分雷达、主评分面积、关键对比强调线。
- **动态紫** (`{colors.accent-violet}` — `#7c4dff`): 可用于动态图、模型视角切换或研究者模块中的 secondary series。
- **深夜色** (`{colors.accent-midnight}` — `#0f172a`): 图表或特殊说明中的深色文字和深色区块备用色。

### Surface
- **Canvas** (`{colors.canvas}` — `#f5f7fb`): 默认页面背景。浅灰能让白色卡片清晰分层，同时比纯白更像正式体检报告。
- **Canvas Soft** (`{colors.canvas-soft}` — `#eef6ff`): 说明卡、读图提示、测量边界和低强调信息块。
- **Canvas Card** (`{colors.canvas-card}` — `#ffffff`): 主要内容卡片、图表容器、指标卡、表格容器。
- **Canvas Mid** (`{colors.canvas-mid}` — `#e4e7ec`): 卡片边框、表格分割、弱背景块。
- **Hairline** (`{colors.hairline}` — `#d0d5dd`): 页脚线、图表边框、表格线和轻量分隔。

### Text
- **Ink** (`{colors.ink}` — `#101828`): 标题、关键结论、指标名称。
- **Ink Hover** (`{colors.ink-hover}` — `#111827`): 深色正文备用，适合图表标题或黑色参考线标签。
- **Body** (`{colors.body}` — `#344054`): 正文解释、训练建议、指标说明。
- **Body Mid / Mute** (`{colors.body-mid}` — `#667085`): 副标题、卡片小标题、单位说明、方法说明。
- **Mute** (`{colors.mute}` — `#98a2b3`): 页脚、打印页码、低优先级来源提示。

### Semantic
语义色必须和动作诊断含义绑定，不能只为装饰使用。

- **绿色** (`{colors.semantic-good}` — `#16a34a`): 接近目标、可保持、标准姿态或训练优势。
- **浅绿底** (`{colors.semantic-good-soft}` — `#dcfce7`): 达标指标卡背景，例如髋肩分离处于可训练范围。
- **橙色** (`{colors.semantic-warn}` — `#f97316`): 需要优先改善，但不直接标记风险。
- **浅橙底** (`{colors.semantic-warn-soft}` — `#fff7ed`): 中等偏差指标卡和训练重点卡。
- **红色** (`{colors.semantic-risk}` — `#ef4444`): 明显偏差、姿态纠正图中的问题骨段、热力图高偏差区域。
- **浅红底** (`{colors.semantic-risk-soft}` — `#fef2f2`): 高优先级短板指标卡。
- **复核黄** (`{colors.semantic-review}` — `#e89918`): 数值可用但受机位、识别或 proxy 影响，需要复测确认。
- **不可用灰** (`{colors.semantic-unavailable}` — `#697586`): 缺少必要数据，不能生成确定判断。
- **不可用浅灰** (`{colors.semantic-unavailable-soft}` — `#eef2f7`): N/A、缺失数据、限制说明卡背景。

## Typography

### Font Family
两类字体承担整个系统：
1. **STHeiti / PingFang SC / Microsoft YaHei** — 中文标题、正文、表格、指标卡和训练建议。HTML 首选系统中文字体栈；导出 PDF 时沿用同一字体栈，避免图片化文字导致缩放模糊。
2. **SFMono / Menlo / Monaco** — 仅用于必要的技术单位、数据文件名、缩写或课程留档中的代码式文本。最终家长页不应把 mono 字体作为主要风格。

### Hierarchy

| Token | Size | Weight | Line Height | Letter Spacing | Use |
|---|---|---|---|---|---|
| `{typography.display-xl}` | 56px | 500 | 66px | 0 | 首页英雄标题，例如“3D 动作体检报告”。 |
| `{typography.display-lg}` | 45px | 500 | 56px | 0 | 每个 section 的主标题，例如“核心运动学仪表盘”。 |
| `{typography.display-md}` | 34px | 500 | 44px | 0 | 页面内章节标题，配蓝色竖条。 |
| `{typography.display-sm}` | 27px | 500 | 36px | 0 | 卡片标题、训练阶段标题、截图标签。 |
| `{typography.display-xs}` | 24px | 500 | 32px | 0 | 表格标题、图表注释标题。 |
| `{typography.body-lg}` | 24px | 400 | 34px | 0 | 首页副标题、重要说明。 |
| `{typography.body-md}` | 20px | 400 | 30px | 0 | 默认正文、指标解释、训练内容。 |
| `{typography.body-sm}` | 18px | 400 | 26px | 0 | 页脚、方法说明、卡片辅助文字。 |
| `{typography.caption-mono}` | 18px | 400 | 24px | 0 | 技术标签、单位或代码式短文本。 |
| `{typography.caption-mono-sm}` | 16px | 400 | 22px | 0 | 表格小单位、数据来源。 |
| `{typography.button-md}` | 20px | 500 | 28px | 0 | 胶囊标签，例如“中文报告”“可量化诊断”。 |

### Principles
- **中文可读性优先。** 不使用过小字号；HTML 正文建议不小于 16 px，PPTX 中正文不得小于 14 号，打印导出时图表文字必须能在 A4 缩放后阅读。
- **标题短、解释直。** 每个 section 标题只表达当前任务，例如“儿童 vs 儿童对比”，不要加入营销式长句。
- **数值比形容词更重要。** 说“比教练低 28.5 cm”优先于“明显不足”。
- **不要重复同一段解释。** 同类限制说明合并到“测量说明”或“哪些数据要谨慎看”。
- **不要使用负字距。** 中文报告保持 `letterSpacing: 0px`，避免压缩导致可读性下降。
- **指标卡字体要紧凑。** 投球和打击 key metrics 卡片用于快速扫描，不使用英雄级字号；数值、单位和说明要分层，说明文字保持 1-2 句，避免把数据来源、算法细节和训练建议都塞进卡片。

### Note on Font Substitutes
如果在非 macOS 环境生成报告，可替换为：
- **中文正文和标题** — *Noto Sans CJK SC*、*Source Han Sans SC*、*Microsoft YaHei*。
- **英文和单位** — *Inter* 或系统 sans-serif。
- **技术留档** — *SF Mono*、*Menlo*、*JetBrains Mono*。

## Layout

### Spacing System
- **页面基准**: HTML 以响应式页面为主，桌面端内容最大宽度建议 1180-1240 px，居中显示。
- **页面边距**: 桌面端左右 64-78 px，平板 32 px，手机 16-20 px。页眉、标题、卡片和页脚都对齐同一内容容器。
- **顶部栏**: 白底固定视觉区域，桌面端高度约 88-118 px。左侧“棒球动作实验室”，右侧“青少年棒球动作报告”。
- **主标题区**: 每个 section 使用清晰标题、副标题和一组卡片；不再依赖固定 y 坐标。
- **卡片内边距**: 24-32 px；图表容器边距更大，避免图例、标题和曲线贴边。
- **页脚**: HTML 底部固定说明“3D视频动作分析报告，仅用于训练参考”。导出 PDF 时才生成页码。

### Grid & Container
- 内容宽度使用 `.report-container` 统一控制，推荐 `max-width: 1180px`，移动端使用 `width: calc(100% - 32px)`。
- 顶层导航必须有三个一级入口：`球员`、`教练`、`研究者`。每个入口下再用二级 tab 切换 `投球` 和 `打击`。
- 三个一级模块互相独立，不能让球员模块的简化解释、教练模块的队内对比、研究者模块的 raw curve 混排在同一个 section。
- 球员模块首页关键结论使用 4 列指标卡，报告问题使用 3 列卡；核心仪表盘使用 2 行 4 列指标网格。
- 教练模块使用对比导向布局：主体球员卡 + 队内/同龄对比卡 + 教练参考卡 + 改进优先级卡。
- 研究者模块使用数据导向布局：事件点表格 + 原始曲线 + 数据质量卡 + 参数说明卡。
- 高层次图表 section 使用 2 个上方半宽卡片 + 1 个下方全宽热力图卡片。
- 球员对比、标准纠正图、时间轴和动力链使用全宽卡片，保证非专业读者能看清关系。
- 全指标诊断使用 2 列指标卡，每张卡包含中文名、数值、教练值、方法和简短说明。
- 移动端可降为单列，但核心仪表盘和对比图要保持横向滚动或重新排版，不能压到无法读数。

### Responsive Strategy

#### Breakpoints

| Name | Width | Key Changes |
|---|---|---|
| Mobile HTML | < 768px | 单列卡片；核心图表可横向滚动；训练建议和指标解释优先完整显示。 |
| Desktop HTML | ≥ 768px | 使用 2-4 列网格；图表和视频截图保持稳定比例。 |
| Print / PDF Export | A4 | 从同一 HTML 打印导出；通过 `@media print` 控制分页、页眉页脚和断页，禁止整页截图式生成。 |
| PPTX 宽屏 | 16:9 | 从同一图表资产和内容 schema 派生；字体不得小于 14 号；动画和 GIF 只放 PPTX。 |

#### Touch Targets
HTML 报告可以有折叠详情、视频播放、模型动态展示和导出按钮。所有可点击区域应不小于 44 x 44 px；胶囊标签如果不可点击，不要做成按钮样式。

#### Image Behavior
- **视频截图**使用 cover crop，保证人物和投球动作占据卡片中心。
- **图表**必须使用 contain，不允许裁切标题、图例、坐标轴或曲线。
- **3D 标准姿态图**必须保留孩子原始姿态连线：浅蓝虚线代表孩子原始模型，绿色代表按孩子身材缩放后的教练标准姿态，红色代表偏差较大的孩子原始骨段。
- **骨架截图不是主证据。** 只用于说明数据来源和姿态对照，核心判断仍由指标、时间轴、动力链和热力图承载。

#### Graph Layout Rules
- 图表默认按父卡片宽度自适应，禁止为普通卡片图表设置过大的 `min-width` 导致横向拖拽。只有原始数据表、极宽 raw table 或确实无法压缩的矩阵才允许内部横向滚动。
- 研究者模块的角度/速度曲线建议使用紧凑坐标系：整体 SVG 约 720 px 宽，绘图区 x 轴不要超过约 560 px；数据质量条形图也建议约 720 px 宽。对比点位图建议约 720 px 宽，轴线长度约 320 px；在卡片中显示时必须水平居中。
- 图表必须把标题、事件标签、坐标轴刻度、单位、图例和曲线分区放置。文字不能覆盖曲线、数据点、条带、骨架或彼此。
- 事件标签不能直接压在曲线绘图区内。事件文字应放在图顶部独立标签带或绘图区外侧，用细指示线连接事件竖线；标签可加浅色背景以保证可读性。
- y 轴单位与 y 轴刻度必须分离。长单位如“公里/小时”不能与刻度数值重叠；必要时增大左边距、把单位放到刻度上方，并给刻度文字加白底隔离。
- 图例应放在绘图区外，通常在图底部或右侧留白，不得占用曲线区域。图例文字过长时优先缩短中文名，而不是扩大图表宽度。
- 数据质量条形图的条带终点必须限制在图框内，右侧百分比数值必须预留固定空间；条带、数值和边框不得相互重叠或越界。
- 时间轴和动力链要给实际数据文本留位置。每个阶段/节点必须能显示时间、帧号、数值或“需逐帧检测”等状态，不允许只放圆点和箭头。
- 移动端图表仍应按卡片宽度缩放；如果缩放后文字不可读，应改为上下分组或缩短标签，不要恢复超长横向图。
- 图表文字字号要与图表尺寸匹配。卡片内 SVG 标签建议 11-14 px；标题和 caption 放在卡片 HTML 文本层，不要把大量说明塞进 SVG 内。

## Elevation & Depth

| Level | Treatment | Use |
|---|---|---|
| Level 0 — Page | 浅灰背景，无阴影。 | 页面画布。 |
| Level 1 — Card | 白色填充、2 px 浅灰边框、24 px 圆角。 | 指标卡、图表容器、训练建议。 |
| Level 2 — Hero | 深色填充、无描边、26 px 圆角。 | 首页英雄区、提示词输入区。 |
| Level 3 — Semantic Fill | 浅绿/浅橙/浅红背景、浅灰边框。 | 达标、警示、明显偏差指标。 |

报告不依赖重阴影。层级主要由背景色、边框、圆角、字号和留白建立。

## Shapes

### Border Radius Scale

| Token | Value | Use |
|---|---|---|
| `{rounded.none}` | 0px | 页面背景、顶部栏和全宽区域。 |
| `{rounded.sm}` | 12px | 图表图片、表格内部、小提示条。 |
| `{rounded.card}` | 24px | 默认内容卡片和指标卡。 |
| `{rounded.hero}` | 26px | 首页深色英雄区和大截图。 |
| `{rounded.pill}` | 9999px | 状态标签、方法标签、报告能力标签。 |
| `{rounded.full}` | 9999px | 序号圆点、图例圆点。 |

## Components

### Buttons

**`button-primary`** — 蓝底白字胶囊。
- 主要用于 HTML 报告中的导出、跳转或查看详情。若只是状态标签，不要使用真实按钮样式。

**`button-outline-on-dark`** — 深色英雄区内的浅色胶囊标签。
- 当前首页用“中文报告”“可量化诊断”“训练建议”三个标签说明报告价值。

**`button-outline-sm`** — 浅蓝底小胶囊。
- 用于方法标签，例如“3D计算”“3D速度估算”“3D proxy”。标签必须帮助读者理解数据来源，而不是堆技术词。

### Cards & Containers

**`card-content`** — 默认白色内容卡。
- 用于图表、表格、指标卡、训练建议和儿童对比。背景白色，边框 `#e4e7ec`，圆角 24 px。

**`card-feature-product`** — 重点模块卡。
- 用于首页关键结论、三问回答、三项优先改进。卡内必须有一个清晰标题、一个主数值或主结论、一句解释。

**`status-badge`** — 指标状态标签。
- 状态固定为五类：`良好`、`偏离`、`关注`、`需复核`、`不可用`。
- `良好` 表示指标进入建议区间，作为保持项；`偏离` 表示指标可用但偏离目标，需要技术修正；`关注` 表示差距明显，应进入本周训练重点；`需复核` 表示数值可能受机位或识别影响，先复测再下结论；`不可用` 表示缺少必要数据，不生成确定判断。
- 状态不能只靠颜色表达，必须有中文标签；研究者模块要能追溯状态规则。

**`priority-list`** — “本次先看什么”优先级列表。
- 用于球员模块首屏，列出 3-5 个最重要问题。每行包含排序圆点、短标题、1 句家长解释和状态标签。
- 内容示例：挥棒路径、髋肩分离、攻击角、蓄力质量、启动效率。
- 排序依据应综合差距大小、训练可改性、表现影响和风险提示，而不是只按单个数值排序。

**`progress-bar-comparison`** — 横向进度对比条。
- 用于教练模块展示主体球员、同龄样本、教练/Vicon 参考的同指标对比。
- 每行必须包含对象名称、条形、数值和单位。颜色建议：主体球员橙色，同龄/队内样本蓝色，教练/Vicon 参考绿色。
- 适合髋肩分离、前腿膝角、头部稳定、攻击角、棒速、挥棒时间等横向对比。

**`scoring-rule-summary`** — 评分规则摘要。
- 用于研究者模块或报告说明页，解释 `良好`、`偏离`、`关注`、`需复核`、`不可用` 的判定逻辑。
- 不放在球员模块首屏，但球员模块中的每个状态都应能追溯到这个规则。

### Inputs & Forms

**`text-input`** — 深色提示词留档卡。
- 当前报告的留档 section 展示“输入内容”和“生成结果”。该 section 用于课程任务或内部可复现性；家长正式交付可隐藏或折叠。

**`data-scroll-table`** — 原始数据滚动表。
- 仅用于研究者模块，承载 CV 原始数据、Vicon 原始数据和计算后指标表。
- 推荐 `sample / field / value` 三列基础结构，也可以扩展 `source / unit / method / confidence`。
- 表格必须可滚动、可下载 CSV，并保留 N/A、None、proxy 字段，不要为了美观删掉缺失值。

### Navigation

**`nav-bar`** — 固定页眉。
- 白色背景。左侧为“棒球动作实验室”，右侧为“青少年棒球动作报告”。不放冗余 logo 或英文 slogan。

**`nav-link`** — 页眉右侧报告类型文本。
- 使用灰色，不抢主标题层级。

**`footer`** — 固定页脚。
- HTML 底部写“3D视频动作分析报告，仅用于训练参考”。打印导出 PDF 时可在右侧生成页码。

### Signature Components

**`hero-band`** — 首页深色报告摘要区。
- 深色背景，白色大标题，浅蓝副标题，右侧放带骨架叠加的视频截图。它要在首屏直接建立“这是动作体检报告”的视觉印象。

**`content-band`** — 标准页面内容区。
- 浅灰背景上承载白卡。每个 section 只解决一个主要问题，避免把所有图表堆到同一屏。

**`eyebrow-mono`** — 蓝色章节竖条。
- 当前系统不用英文 eyebrow，而是用 12 x 40 px 蓝色圆角竖条配中文章节标题。它是页面内层级的主要识别符。

**`divider-hairline`** — 页脚和表格分割线。
- 使用浅灰线，保持体检报告感，不做重色块分割。

**`hero-motion-evidence`** — 首屏动作证据图。
- 来自当前 HTML 的 `motion-canvas` 模式：深色面板内放骨架、挥棒/投球路径、关键角度文字和 2-3 个底部评分。
- 它不是纯装饰图，必须承载至少 2 个指标证据，例如“髋肩分离 4.2°”“攻击角 43.5°”“稳定 97分”。
- 如果有真实视频截图，优先用截图叠加骨架；没有截图时可用简化 SVG 骨架作为占位，但必须标注“示意”。

**`training-calendar`** — 7 天家庭训练与复测计划。
- 用于球员模块训练 section，把 3-5 条建议落成一周执行日程。
- 每天卡片包含：日期、训练阶段标签、2-3 个 checklist、是否需要拍摄视频、疼痛/疲劳记录。
- 第 7 天固定为同机位复测日，至少复测 2 个短板指标和 1 个保持项。

**`limitation-card-grid`** — 本次限制卡片组。
- 用于研究者模块，也可在教练模块折叠展示。明确列出不可用或需复核项目。
- 必须覆盖真实球速/转速、真实接触时间、coach 参考未统一到 Vicon、proxy 事件等限制；每项要说明为什么不能直接下结论。

### Required Graphs

以下图表是 HTML 报告必须输出的核心可视化。每张图都要有中文标题、1 句读图说明、数据来源标签和可靠性备注。图表优先使用 HTML/SVG/canvas 或清晰 PNG 资产渲染，打印导出时必须保持图例、标题、坐标轴和曲线不裁切。

**球员模块：Pitching**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `athlete-pitch-overall-radar` | 投球六维评分图 | 这个球员投球整体强弱在哪里？ | 归一化 0-100：下肢支撑、身体前移、髋肩分离、躯干控制、手臂加速、稳定性。 | 首屏后优先展示；旁边列出“最强 2 项”和“最需要改 2 项”；不要只给面积大小。 |
| `athlete-pitch-photo-angles` | 投球关键截图角度标注 | 球员能不能直观看到自己哪里不标准？ | 出手、落脚、随挥等关键帧；3D 或 2D 投影关节角。 | 用真实照片/视频截图叠加骨架和角度弧线；文字短，适合家长和孩子直接理解。 |
| `athlete-pitch-key-metrics` | 投球关键指标卡 | 本次最重要的指标是多少，和目标差多少？ | 前膝角、髋肩分离、跨步长度、投球臂槽、躯干倾斜、手臂/手部速度估算。 | 6-8 张卡片；红/橙/绿状态；每项必须给数值、单位、简短中文解释。 |
| `athlete-pitch-standard-overlay` | 投球标准姿态纠正图 | 原始姿态和标准姿态差在哪里？ | 主体球员 3D 姿态 + 教练 3D 姿态按球员肢体长度缩放。 | 必须使用真实三维骨架而不是固定示意 placeholder；浅蓝虚线表示球员出手附近原始姿态，绿色实线表示教练参考姿态，红色表示偏差较大的球员骨段；图例必须放在骨架外侧，不覆盖身体线。 |
| `athlete-pitch-training-targets` | 投球训练目标卡 | 接下来练什么，怎么复测？ | 来自关键短板和复测指标。 | 3-5 条训练建议，每条包含动作、频率、组数、对应指标和下次复测目标。 |
| `athlete-pitch-priority-list` | 投球优先级列表 | 本次最先看哪 3-5 个问题？ | 差距大小、训练可改性、表现影响和风险综合排序。 | 放在球员模块首屏；每行包含排序、问题、直白解释和状态标签。 |
| `athlete-pitch-7day-plan` | 投球 7 天训练计划 | 训练建议如何变成每天能做的安排？ | 来自训练目标卡和复测指标。 | 每天 2-3 个 checklist；第 7 天同机位复测；记录疼痛、疲劳和完成率。 |

**球员模块：Batting**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `athlete-bat-overall-radar` | 打击六维评分图 | 这个球员打击动作整体强弱在哪里？ | 归一化 0-100：站姿稳定、跨步控制、髋肩分离、躯干旋转、挥棒平面、击球后平衡。 | 与投球雷达图风格一致，但维度必须是 batting 专属，不要复用投球维度。 |
| `athlete-bat-photo-angles` | 打击关键截图角度标注 | 球员在准备、启动、击球、随挥时哪里需要改？ | 准备姿势、前脚落地、球棒进入击球区、击球点、随挥关键帧。 | 在照片上标注前膝、髋肩、躯干倾斜、球棒角度和头部稳定；尽量用少量大字。 |
| `athlete-bat-vicon-2d-geometry-overlay` | 打击 Vicon 几何值 2D 视频标注 | Vicon 算出的几何角度在真实视频画面中对应哪里？ | Vicon C3D/Excel 几何值 + 已对齐 2D skeleton overlay 截图；2D 只作为视觉辅助，不作为数值来源。 | Ready/Contact 各一张图，放在对应 section title 下方，宽度接近左侧三张 metrics card；右侧 media 卡仍只放事件 GIF。关节角用细肢段线、夹角虚线延长线、细 leader line 和小号数值，不用角度 arc；骨盆/躯干旋转用横向压扁的标准单弧箭头，尾部裁掉约 20%，避免覆盖人体。 |
| `athlete-bat-key-metrics` | 打击关键指标卡 | 打击动作最重要的指标是否达标？ | 跨步长度、前脚方向、髋肩分离、躯干旋转速度、球棒平面角、手部速度、头部稳定。 | 6-8 张卡片；重点解释“这会影响击球稳定性/挥棒速度/击球角度”。 |
| `athlete-bat-swing-path` | 挥棒轨迹示意图 | 球棒是否稳定进入击球区？ | 球棒端点、手部轨迹或可用 proxy；若无球棒点则用手腕/手部 proxy。 | 用清晰轨迹线叠加击球区；必须标注 proxy 限制，不要把手腕轨迹说成真实球棒轨迹。 |
| `athlete-bat-training-targets` | 打击训练目标卡 | 接下来练什么，怎么复测？ | 来自关键短板和复测指标。 | 3-5 条训练建议，包含 tee drill、分解挥棒、下肢稳定、节奏控制等可执行练习。 |
| `athlete-bat-priority-list` | 打击优先级列表 | 家长和球员应该先看哪几个问题？ | 差距大小、训练可改性、表现影响和风险综合排序。 | 内容可包含挥棒路径、髋肩分离、攻击角、蓄力质量、启动效率；每项必须直白解释。 |
| `athlete-bat-7day-plan` | 打击 7 天训练计划 | 每天练什么，怎么检查？ | 来自训练目标卡和复测指标。 | 可包含墙边髋肩分离、Tee 平扫路线、跨步停顿挥棒、看球冻结；第 7 天复测髋肩分离和攻击角。 |

**教练模块：Pitching**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `coach-pitch-player-comparison` | 投球队员对比图 | 主体球员在队内/同龄样本中处于什么位置？ | 主体球员、其他球员、教练参考同一 3D 口径。 | 优先使用同一指标一条横轴、不同颜色点展示球员所处位置；参考值用黑色竖线。x 轴保持紧凑，不为少数点拉成过长图；必须标注“不是医学评价，不做单一排名”。 |
| `coach-pitch-gap-dashboard` | 投球差距仪表盘 | 主体球员和教练参考具体差多少？ | 关键投球指标差值：角度、速度、距离、百分比。 | 按差距绝对值排序；显示本次数值、参考值、差值、优先级。 |
| `coach-pitch-reference-bars` | 投球参考对比条 | 主体球员、同龄样本、教练/Vicon 参考谁高谁低？ | 同一指标下的主体球员、同龄/队内样本、教练/Vicon 参考。 | 横向条形对比；颜色固定为主体球员橙、同龄/队内蓝、教练/Vicon 绿。 |
| `coach-pitch-phase-timeline` | 投球阶段时间轴 | 问题发生在哪个投球阶段？ | FC、MER proxy、BR、FT 等事件点与阶段指标。 | 横向 0-100% 时间轴；可叠加主体球员和教练事件相位差。 |
| `coach-pitch-kinetic-chain` | 投球动力链传递图 | 发力顺序是否从下肢到手部顺畅传递？ | 骨盆、躯干、肩/肘/手部峰值速度和峰值时间。 | 用箭头和时间顺序展示；若速度为估算必须标注“同流程参考趋势”。 |
| `coach-pitch-intervention-map` | 投球改进优先级图 | 教练应该先改哪 2-3 个问题？ | 差距大小、风险提示、训练可改性综合排序。 | 矩阵图：横轴影响表现，纵轴训练优先级；每个点链接到训练方案。 |

**教练模块：Batting**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `coach-bat-player-comparison` | 打击队员对比图 | 主体球员的挥棒速度、稳定性和节奏在队内如何？ | 主体球员、其他球员、教练参考同一 3D/球棒 proxy 口径。 | 优先使用同一指标一条横轴、不同颜色点展示样本位置；光学或建议参考用黑色竖线。x 轴不要过长，标签放在轴线右侧独立列，避免压到点。 |
| `coach-bat-gap-dashboard` | 打击差距仪表盘 | 主体球员和参考动作差多少？ | 髋肩分离、躯干旋转速度、手部速度、球棒平面、前脚方向、头部稳定。 | 按表现影响排序；每项显示数值、参考、差距和训练方向。 |
| `coach-bat-reference-bars` | 打击参考对比条 | 主体球员和对照/参考差多少？ | 髋肩分离、前腿膝角、头部稳定、棒角/攻击角、棒速、挥棒时间。 | 采用横向进度条；当前 report 使用 bryan 与 green 的同源 Vicon 指标，coach 参考若使用必须标注临时性。 |
| `coach-bat-swing-sequence` | 打击阶段时间轴 | 准备、启动、落脚、击球、随挥的节奏是否合理？ | 打击事件点和阶段持续时间。 | 时间轴必须独立于投球事件；不要使用 FC/MER/BR 投球标签。 |
| `coach-bat-swing-plane` | 挥棒平面与击球区图 | 球棒进入击球区是否稳定？ | 球棒轨迹、手部轨迹 proxy、击球点 proxy。 | 展示主体球员 vs 参考轨迹；如果缺球棒 marker，明确写“手部 proxy”。 |
| `coach-bat-intervention-map` | 打击改进优先级图 | 教练应该先改稳定性、节奏还是旋转速度？ | 差距大小、动作阶段、训练可改性综合排序。 | 输出 3 个训练优先级，每个优先级连接到 drills 和复测指标。 |

**研究者模块：Pitching**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `research-pitch-angle-time` | 投球角度-时间曲线 | 关键关节角如何随时间变化？ | 膝角、肘角、躯干倾斜、髋肩分离等 3D 曲线。 | 必须由逐帧 3D 姿态 CSV 计算；坐标轴、单位、事件竖线完整。事件文字放在绘图区外的顶部标签带；y 轴单位与刻度分离；x 轴紧凑，不强制横向长图。 |
| `research-pitch-speed-time` | 投球速度-时间曲线 | 骨盆、躯干、手部峰值速度何时出现？ | 3D segment velocity 或 proxy velocity。 | 必须由逐帧 3D 坐标差分生成，并转成常用速度单位展示；标出峰值和事件点。曲线、图例、事件标签不得互相覆盖。 |
| `research-pitch-event-table` | 投球事件点表 | FC、MER、BR、FT 是否检测可靠？ | 帧号、时间戳、事件规则、关键指标。 | 表格可专业，但必须可下载 CSV；缺失事件要明示。 |
| `research-pitch-data-quality` | 投球数据质量图 | 这条数据能不能用于分析？ | pose 缺失率、插值 gap、平滑参数、置信度、可用帧比例。 | 用折线/条形/热力图展示；条带和右侧百分比数值必须留在图框内，不得越界；不要隐藏异常帧。 |
| `research-pitch-source-table` | 投球 Vicon 原始数据表 | 每个投球指标来自哪个 C3D 字段或派生字段？ | `sample / field / value`，可扩展 source、unit、method。 | 当前 report 主体只追溯 Vicon C3D 和派生指标；旧 CV/GVHMR benchmark 字段不得混入主体来源表。 |
| `research-pitch-limitations` | 投球限制卡片组 | 哪些指标不能直接下结论？ | 雷达/球追踪缺失、coach 参考未统一到 Vicon、proxy 指标。 | 用状态卡展示 `需复核` 和 `不可用`，不隐藏限制。 |

**研究者模块：Batting**

| Graph | 中文名称 | 必须回答的问题 | 数据口径 | 展示规则 |
|---|---|---|---|---|
| `research-bat-angle-time` | 打击角度-时间曲线 | 打击关键关节角如何随时间变化？ | 前膝、髋肩分离、躯干倾斜、肘角、球棒平面 proxy。 | 必须由逐帧 3D 姿态 CSV 计算；事件竖线标准备、启动、落脚、击球、随挥。事件文字放在绘图区外，不能压到曲线。 |
| `research-bat-speed-time` | 打击速度-时间曲线 | 躯干、手部、球棒速度峰值何时出现？ | Vicon 3D segment velocity、手部速度、`Bat1-Bat5` 球棒 marker 速度。 | 标出峰值顺序；如果未来数据缺少球棒 marker 才标注 proxy。速度必须使用公里/小时等常用单位，不展示无意义原始单位。 |
| `research-bat-swing-trajectory-raw` | 打击原始轨迹图 | 手部/球棒/身体中心轨迹是否稳定？ | 2D/3D 坐标轨迹、滤波前后轨迹。 | 允许显示 X/Y/Z 或平面投影；这是研究者模块，不能放到球员首屏。 |
| `research-bat-data-quality` | 打击数据质量图 | 这条打击数据能不能用于分析？ | pose 缺失率、球棒/手部 proxy 可用率、插值 gap、平滑参数。 | 明确哪些指标可算、哪些指标不可算；输出 raw data 下载入口。 |
| `research-bat-source-table` | 打击 Vicon 原始数据表 | 每个打击指标来自哪个 C3D 字段或派生字段？ | `sample / field / value`，包含 Vicon marker、事件 proxy 和派生指标。 | 保留 hip_shoulder_separation_deg、attack_angle_deg、bat1/bat5 speed、swing_time_sec 等字段；旧 CV/GVHMR benchmark 字段不得混入主体来源表。 |
| `research-bat-vicon-source` | 打击 Vicon 说明图 | Vicon 在报告里承担什么角色？ | Vicon 3D marker、bat speed、bat angle、swing time、wrist/finger marker speed。 | 当前 report 中 Vicon 是主体 raw data source，不是 CV 校准附属；可用横向条展示 bryan 与 green 的同源对照。 |
| `research-bat-limitations` | 打击限制卡片组 | 哪些指标不可用或需复核？ | 真实球速/转速、真实接触事件、coach 参考未统一到 Vicon。 | 每项都要写“为什么不能判断”和“下次需要什么数据”。 |

**Scoring System**
- 球员模块可以使用五维或六维评分。五维适合当前 HTML 快速摘要：`蓄力`、`路径`、`稳定`、`节奏`、`速度可信`；六维适合完整体检：再拆分下肢支撑、身体前移、髋肩分离、躯干控制、末端加速、稳定性。
- 评分必须是 0-100 分，并且能追溯到原始指标或规则。示例：蓄力可来自髋肩分离，路径可来自攻击角/挥棒平面，稳定可来自头部稳定和前腿支撑，速度可信可来自数据来源和机位稳定性。
- 首屏可以展示 2-3 个最大分数差异，例如“17分 蓄力”“43分 路径”“97分 稳定”，但后文必须解释这些分数怎么来的。

**Graph Priority**
- 球员模块第一优先级：照片/截图角度标注、六维评分图、关键指标卡、标准姿态纠正图、训练目标卡。
- 教练模块第一优先级：主体球员 vs 教练参考、主体球员 vs 其他球员、差距仪表盘、阶段时间轴、改进优先级图。
- 研究者模块第一优先级：速度-时间曲线、角度-时间曲线、事件点表、数据质量图、Vicon C3D 来源表、限制卡和 raw data 下载入口。
- 原始角度/速度曲线不进入球员模块首屏；它们属于研究者模块，或在教练模块中作为折叠详情。

**Graph Copy Rules**
- 每张图标题使用中文，例如“投球动力链传递图”，不要只写 `Kinetic Chain`。
- 每张图下方必须有一句“怎么看”：球员模块用直白语言，教练模块用训练语言，研究者模块用数据/方法语言。
- 每张图必须标注方法：`3D计算`、`3D速度估算`、`2D视频估算`、`Vicon`、`雷达枪` 或 `手部 proxy`。
- Pitching 与 batting 的阶段标签必须分开。投球使用抬腿、落脚、最大外旋、出手、随挥；打击使用准备、启动、前脚落地、进入击球区、击球点、随挥。
- 如果某项指标只是 proxy，图上必须写“估算”或“参考趋势”，不要写成真实测量。
- 当图像把 Vicon 值叠加到 2D 视频截图上时，必须明确区分“数值来源”和“视觉辅助”：角度值来自 Vicon C3D/Excel，2D 骨架线只是帮助读者定位身体部位。不要把 2D 关键点计算值展示成 Vicon 几何值。
- 图例不得覆盖标题、曲线、坐标轴或数据点；移动端允许横向滚动，不允许把文字压缩到不可读。
- 报告交付版不得出现大段英文标题、英文 caption 或英文状态；英文 metric name 只能出现在研究者原始字段追溯表中，且旁边必须有中文指标名。
- 图表 caption/title 要短，不要把方法说明塞进图内；方法说明放在图下“怎么看”或 module note。

**Current HTML Implementation Requirements**
- 当前可复用的 batting final-schema report 由 `python scripts/report_cli.py build-batting-report` 生成；路径和主体配置集中在 `configs/default_report_pipeline.json`，核心编排在 `scripts/run_batting_report_pipeline.py`。该入口会从 Vicon C3D 生成中间 CSV、3D reconstruction 资产、batting metrics、MediaPipe 2D alignment、2D metric annotations、HTML schema、researcher charts 和 XLSX。`scripts/build_benchmark_report_html.py` 仍保留为早期 Bryan/Green benchmark report 的 legacy builder，不是新球员 batting report 的推荐入口。
- 当前主体 raw data source 必须统一为 Vicon C3D 及其派生表；旧 benchmark 视频 CV/GVHMR 身体数据不得混入当前主体指标、曲线或 C3D 来源表。默认 Julian/Coach config 使用 `../vicon_2026` 和 `reports/vicon_2026_julian_coach/`；新球员必须复制 config 并写入 `reports/vicon_2026_<player_slug>_coach/`，不要覆盖 Julian 参考目录。
- Julian/Coach batting metrics section 是当前独立打击 dashboard 的设计样例：前端卡片只展示聚合后的前端指标和评分，后台 Vicon 几何/速度字段用于加权计算和 Excel 追溯。Ready/Contact 的 2D 几何标注图应直接放在 section title 下方，不放进右侧 GIF 卡；右侧保留 Julian 事件 GIF。Ready 标注后髋、后膝和髋肩分离，右打假设下后腿为右腿；Contact 标注骨盆旋转、躯干旋转和前膝，右打假设下前腿为左腿。角度标注必须贴合实际夹角和补角语义：如果报告值是 `180 - angle(...)` 的屈曲角，视觉上要保留夹角处虚线延长线，并用 leader line 指向该屈曲角数值，避免在明显大于 90 度的身体夹角上画一个 40-50 度的错误 arc。
- 姿态纠正图不得再使用固定 SVG placeholder。当前实现口径：球员投球样本出手附近帧作为浅蓝虚线，教练三维序列出手侧手部速度峰值附近帧作为绿色参考，偏差最大的球员骨段用红色强调。
- C3D 点重建图不得使用全局 trial points 或全局平均点。必须先提取关键动作位置，再从该关键帧附近小窗口重建点位：投球使用出手侧/主导手速度峰值，打击使用球棒速度峰值。重建资产必须先单独渲染为 PNG/GIF/MP4/AVI，再嵌入 report；不得在 HTML 中临时用内联 SVG 拼接 C3D 重建图。报告中 C3D 重建区块应展示关键动作窗口 GIF/视频，而不是完整 trial GIF 或只放单张关键帧图片；打击窗口默认关键帧前约 0.6 秒、后约 0.4 秒，投球窗口默认关键帧前约 1.4 秒、后约 0.4 秒以包含前腿抬起阶段，PNG 仅作为关键帧截图或动图缺失时的 fallback。动图/视频必须使用关键动作窗口内的固定坐标范围和固定相机视角，不能每帧 autoscale 导致背景网格缩放；点位可做短窗口可视化平滑以降低 marker 抖动，但不能改变用于指标计算的原始数据。报告中必须能追溯 `sample_name`、`key_event`、`key_frame_index` 和 `key_time_sec`，其中 `sample_name` 必须直接来自 `vicon_2026` 下的子文件夹名。Vicon 报告区块不得硬编码某一个样本名或只展示某一个 trial；必须按 `sample_name` 和动作类型动态遍历当前 CSV 中的所有 C3D trial。C3D 动图骨架只使用真实身体 marker 的人体连接关系，不画 Plug-in Gait/model 局部轴段或其他辅助 segments；可显示真实 marker 散点、`CentreOfMass` 和打击时的 `Bat1-Bat5`，但不得显示 `CentreOfMassFloor` 这类地面/辅助点导致画面误读。三维人体不得塞满画布，渲染时必须放大坐标边界并给骨架四周留出明显空白；Y 轴显示中心应让脚部 marker 位于视觉中心附近，不要为了脚部位置改 Z 轴范围。三维重建图使用专业报告风格：白底、浅灰网格、红色人体连接、蓝色 marker 点、绿色球棒、灰色虚线棒头轨迹；不要在人体或球棒 marker 点上标注点名，图例只保留球棒和棒头轨迹。头部 `LFHD/RFHD/LBHD/RBHD` 四点必须连接为闭合立体面，并全部连接到 `C7`；躯干 `C7/CLAV/STRN/T10/RBAK`、骨盆 `LASI/RASI/LPSI/RPSI`、左右脚踝/跟/趾和 `Bat1-Bat5` 必须分别连接为刚体结构。打击时 `Bat1-Bat5` 既按顺序连接，也要增加外轮廓/互相连接来勾勒球棒形状；灰色虚线轨迹表示棒头 `Bat1`。
- 研究者模块不得在已有逐帧 3D 姿态 CSV 时保留“缺少逐帧数据”占位。至少要生成投球角度曲线、投球速度曲线、打击角度曲线、打击速度曲线和三维姿态数据质量图。
- 角度时间曲线至少包含前腿膝角、肘角、躯干倾斜、髋肩分离。速度时间曲线至少包含髋部中心、躯干中心和手部末端速度；球棒未直接检测时必须写 proxy 或限制说明。
- 点位对比图采用一行一个指标、一条横轴、多色点位的形式：主体样本蓝色，对照样本橙色，教练/Vicon/建议参考黑色竖线。它比多组条形更适合展示“球员处于同一指标什么位置”。点位图 SVG 在卡片内显示为约 80% 宽并居中，避免左贴边。
- 图表宽度必须紧凑。当前实现目标：研究者曲线和数据质量图约 720 px 内部坐标宽度；队员对比点位图约 720 px 内部坐标宽度，x 轴约 320 px，但页面显示尺寸约为卡片宽度的 80%，避免字体、点和轴线显得过大；不使用 860 px 以上的强制宽图。
- 普通图表的 CSS 不应设置大 `min-width`。桌面双栏中图表应缩放到约 500 px 卡片宽度；移动端图表应缩放到单卡宽度。表格可滚动，图表默认不靠横向滚动解决布局。
- 速度单位必须转换为常用单位。`px/s` 要结合源视频分辨率、帧率和画面人体高度估算为公里/小时；无法物理标定的 `3d_unit/s` 不展示为用户单位，改为“需标定”、相对百分比或方法限制说明。
- 页面中不得出现“像素/秒”“三维单位/秒”“归一化单位/秒”等无现实意义单位。研究者表可保留 raw field name，但用户可见数值栏应转换或标为需标定。
- 数据质量图条带必须在 SVG 框内，右侧百分比数值要预留空间；质量指标同时说明可用帧、关节完整率和输入质量分，不能只给一个颜色。
- 时间轴和动力链必须显示实际数值文本位置。事件点可显示秒和帧号；未知事件写“需逐帧检测”或“需球棒轨迹”，不要空白。

### Examples (illustrative)

> 以下示例是当前 HTML 报告的 section 级模块，可作为 PDF 导出、PPTX 或 dashboard 复用的结构。

**`ex-pricing-tier`** — 基础版报告。
- 内容：红黄绿动作诊断、关键截图、至少 3 条家庭训练建议、复测重点。

**`ex-pricing-tier-featured`** — 专业版报告。
- 内容：3D 指标、正常速度教练对照、儿童 vs 儿童、标准姿态纠正图、完整指标 CSV、动态图展示。

**`ex-product-selector`** — 报告模块目录。
- 当前推荐顺序：总览入口、球员模块、教练模块、研究者模块。每个模块内部再分投球和打击，不把两类动作混成一套指标。

**`ex-cart-drawer`** — 交付物清单。
- HTML 用于家长阅读和统一排版；PDF 由 HTML 打印导出；PPTX 用于课程展示和动态模型；CSV/PNG/GIF 用于教练或后续分析。

**`ex-app-shell-row`** — 章节目录行。
- HTML 报告可直接使用左侧或顶部目录导航；导出 PDF 时目录保持为普通 section 顺序。
- 一级目录固定为球员、教练、研究者；二级目录固定为投球、打击；三级目录才是图表和训练建议。

**`ex-data-table-cell`** — 指标表格。
- 表头必须短：指标、本次结果、教练参考、差距、说明。不要把完整计算公式塞进家长页。
- 研究者模块可以使用更完整的 raw table，但必须和球员模块的简化指标卡分开。

**`ex-auth-form-card`** — 提示词与生成结果留档。
- 只用于课程要求或内部可复现性，不作为家长报告的核心页面。

**`ex-modal-card`** — 数据可靠性说明。
- 解释“3D速度受单目深度抖动影响”“身体中心位移不是力板重心”“球速需要雷达枪”等边界。

**`ex-empty-state-card`** — 暂缺数据。
- 例如暂无真实 Vicon、暂无雷达球速、暂无真实教练同机位时，用该组件明确说明，不用虚假数值填充。

**`ex-toast`** — 蓝色提示条。
- 每个 section 最多 1 个，承担读图顺序、测量说明、用途说明或风险提示。


## Do's and Don'ts

## Export Layout Rules

### PDF
- PDF 是 `report.html` 的版式冻结版本，不是重新设计的一套报告。导出时必须保留 HTML 的自然视觉关系，包括 hero、section 顺序、两列卡片、训练计划网格、研究者表格和模型图所在的原始上下文。
- 当前 PDF pipeline 使用 Chromium 渲染 HTML，然后按纵向分段截图装入 A4 页面。分页点优先取完整视觉行、section、card 和 grid 边界；不要在两列布局中只按左列或右列单个 card 的底部断页。
- 不要把 PDF card 重新打包成独立 rows/columns。这样会破坏 HTML 中 vertical/horizontal card 的上下文关系，也容易造成图过大、表过小、模型图丢失或页内空洞。
- PDF 可以为导出会话临时压缩字号、卡片 padding、图表 SVG 尺寸和滚动容器，但这些调整必须服务于 HTML 原布局，而不是创建新的页面布局系统。
- PDF 中单页空白应尽量控制在 20% 以内；图与图之间的垂直空隙不应超过页面高度约 10%。如果做不到，优先从 HTML section 顺序、卡片高度、表格拆分和分段点调整。
- 长表格可以在导出 DOM 中拆成 1/2、2/2 等连续表，每段必须保留标题和表头；不要使用无表头的截图硬切。
- 对包含滚动条的图表或表格，导出前必须展开为完整可见内容，避免只截取当前 scroll viewport。
- 3D 骨架和质量图属于解释性/来源性视觉，不应抢占高密度曲线、表格和训练建议的面积；但也不能缩到无法判断结构。

### PPTX
- PPTX 是展示版，不要求保持 HTML 长页切片。它可以使用卡片级截图，但必须保留同一视觉系统、中文标题、颜色体系和卡片样式。
- PPTX 中相近的窄卡片可以两列合并；高密度曲线、表格、模型图和长说明需要单独成页或自动切片，避免文字过小或内容截断。
- PPTX 导出后必须检查预览或 QA 日志，确认没有明显 overlap、标题换行失控、图表裁切或无法阅读的小字。

### Do
- 把 HTML report 分成球员、教练、研究者三个一级模块，并允许每个模块独立导出。
- 每个一级模块都分别提供 pitching 和 batting 两套分析，不复用不适配的阶段标签或指标解释。
- 用中文直接给结论，并根据球员、教练、研究者三类受众调整解释深度。
- 球员模块先回答三件事：我哪里做得好、哪里要改、练什么。
- 教练模块重点回答：主体球员和教练/其他球员差在哪里、差多少、优先改哪几个动作。
- 研究者模块重点回答：原始数据是否可靠、事件点是否合理、速度/角度曲线如何变化。
- 球员模块优先使用照片截图、骨架、关节角标注、六维评分图和关键指标卡。
- 教练模块优先使用参数仪表盘、球员对比图、差距排序、阶段时间轴和改进优先级矩阵。
- 研究者模块优先使用 Vicon C3D raw data、Vicon 来源表、速度-时间曲线、角度-时间曲线、事件点表、评分规则摘要和数据质量图。
- 当前数据足以生成的研究者曲线、姿态纠正图和数据质量图必须真实生成，不要用 placeholder 顶替。
- 图表 x 轴要紧凑，优先按卡片宽度自适应；不要靠强制超宽 SVG 或横向滚动解决普通图表布局。
- 图表文字要有独立空间：事件标签放在曲线区外，y 轴单位和刻度分离，图例不覆盖数据。
- 速度和距离单位要转换成常用中文单位；无法标定的速度不要显示为真实速度。
- 使用五档状态体系：良好、偏离、关注、需复核、不可用；每个状态必须能追溯到规则或证据。
- 球员模块首屏可以使用五维评分摘要：蓄力、路径、稳定、节奏、速度可信；完整报告可扩展为六维评分。
- 训练建议要进一步落成 7 天家庭训练与复测计划，第 7 天必须安排同机位复测。
- 当前 report 以 Vicon C3D 作为主体 raw data source，并通过 config-driven pipeline 统一路径；不要把 standard Vicon 动捕身体数据和 optical CV/GVHMR 身体数据混成同一个未解释的数值。
- N/A、None、proxy 和不可用项必须展示清楚，研究者模块保留原始字段和限制说明。
- 每张可视化都配一句明确解释，说明家长应该先看什么。
- 早期 benchmark report 的对象口径固定为 bryan 主分析、green 教练模块对照、coach 临时参考；当前 batting final-schema 以 config 中的 `sample_name` / report directory 为主体口径。图表中必须明确对象颜色和临时参考边界。
- PDF 导出优先沿用 HTML 自然版式做分段截图，分页只微调断点，不重新组合 card。
- 标准姿态纠正图必须显示孩子原始姿态浅蓝虚线、缩放教练标准姿态绿色线、偏差较大骨段红线。
- 对速度、身体中心位移、球速估算写清可靠性边界，并建议正式复测补充雷达枪、Vicon 或力板。
- 训练建议必须包含动作名称、训练频率、组数或次数、对应改善的数据短板。
- PPTX 与 HTML 保持同一视觉系统，增加 3D 模型动态展示，字体不小于 14 号。
- 把课程要求的提示词和生成结果放入留档 section；正式家长交付时可隐藏该 section。

### Don't
- 不要把球员、教练、研究者三个模块混成一条长报告；三类受众的图表深度和措辞必须分开。
- 不要把 pitching 指标直接套到 batting，也不要把 batting 阶段标签套到 pitching。
- 不要把报告写成科研论文，不要让角度时间序列成为首屏或核心卖点。
- 不要把研究者模块的 raw coordinate 曲线放进球员模块首屏。
- 不要反复解释同一个限制；同类说明合并到测量说明或复测注意事项。
- 不要在家长页使用产品比较或模型调用过程等过程词；最终交付只说数据、结论和建议。
- 不要隐藏 `N/A`、`None`、`proxy` 或缺失字段；可信报告必须暴露哪些不能判断。
- 不要把 `px/s` 速度当成真实球速或真实棒速；它只适合同机位前后对比。
- 不要在用户可见报告中显示“像素/秒”“三维单位/秒”“归一化单位/秒”等没有现实意义的单位；必须换算、标为相对值或写“需标定”。
- 不要把 optical CV/GVHMR 身体数据混入当前 Vicon 主体报告；若临时引用 coach 数据，必须在正文说明它没有统一到同一 Vicon C3D 采集链路。
- 不要把 3D 骨架截图当作核心证据；它只能辅助说明姿态和数据来源。
- 不要裁切图表标题、图例、坐标轴或曲线；图表必须 contain 放入卡片。
- 不要把研究者曲线、点位图、时间轴或动力链做成横向过长的图；普通图表应适配卡片宽度。
- 不要在 PDF 导出中把 HTML card 拆散后重新配对、重新排序或按信息密度重排；这会让版式和原 HTML 脱节。
- 不要让图表文字和曲线、数据点、条带、骨架或其他文字重叠；发现重叠时优先重排文字，而不是单纯缩小字号。
- 不要在有逐帧三维姿态数据时继续保留“缺少逐帧数据”的占位图。
- 不要用成人教练骨架直接覆盖孩子身体；标准姿态必须按孩子肢体长度缩放。
- 不要把儿童 vs 儿童写成排名；它只用于理解同龄样本中的动作特点。
- 不要把身体中心位移称为真实重心；当前计算是髋部和脊柱中心的近似估算。
- 不要把视频估算球速写成正式球速；正式训练应使用雷达枪或球轨迹设备。
- 不要在 HTML 或导出 PDF 中使用过小字体、过密表格或缺少解释的英文指标。
