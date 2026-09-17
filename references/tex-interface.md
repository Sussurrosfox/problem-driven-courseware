# TeX 接口规范（tex-interface）

本文件是合法环境/宏、注释规范、双版可见性与 `config.yaml` 配置字段的权威维护位置（由 SKILL.md 路由至此）。切片写作者只需要本文件的「写作者速查」部分；检查脚本（check_numbering/check_dialogue/build/compare）按本文件口径实现。`templates/sec_template.tex` 是可编译的最小示范，其注释只解释示例特殊点。

---

## 一、 工程化分层架构与入口文件

```
work_dir/
└── self/               # [核心输出目录] 总是将新创作的文件置于单独的 self 文件夹中（没有则新建，重名则询问）
    ├── student.tex     # [层1] 学生版编译入口 (\input{main.tex})
    ├── teacher.tex     # [层1] 教师版编译入口 (\def\TeacherVersion{}\input{main.tex})
    ├── main.tex        # [层2] 主骨架：\input header.tex，\begin{document}，双栏开始，\input sec*/footer
    ├── header.tex      # [层2] 纯导言区：版面参数、宏包、双版本环境、microknowledge/knowledgebox
    │                   #        与对话层（sectiondialogue/exampledialogue/\speaker/\dlgteacher）宏定义
    │                   #        （教师版版面在此覆盖为 A4 竖版单栏；学生版沿用 config.yaml 大8开横版双栏）
    ├── footer.tex      # [层2] 收尾：双栏结束、LastPage 锚点、\end{document}
    ├── config.yaml     # [层2] 参数文件：纸张/边距/标题/页眉文案（改课程只改此文件）
    ├── config-class.tex# [自动生成] 文档类选项（scripts/gen_config.py 生成）
    ├── config.tex      # [自动生成] geometry 与文本参数宏（同上生成，勿手改）
    ├── sec0.tex        # [层3] 开篇引例切片（经开篇职责判定后撰写，叙述为主、少用问题；可省略）
    ├── sec1.tex        # [层3] 第 1 小节纯切片内容 (仅包含 \section*{} 与题目环境)
    ├── .pd/            # [内部] 运行契约与交付证据：run.json、candidates/、review/、acceptance/
    └── ...
```

**入口文件规范**：

- `student.tex`：
  ```latex
  % -*- coding: utf-8 -*-
  \input{main.tex}
  ```
- `teacher.tex`：
  ```latex
  % -*- coding: utf-8 -*-
  \def\TeacherVersion{}
  \input{main.tex}
  ```

**参数化配置**：换课程/学期只需复制并修改 `config.yaml`，然后运行 `python scripts/gen_config.py --project <项目目录>` 重新生成 `config-class.tex` 与 `config.tex`（生成器做内容比较，内容相同不重写；build.py/deliver.py 在计算摘要前也会确定性重生成）。模板本体零改动；Skill 自带默认生成结果，未运行脚本也可直接编译。

## 二、 config.yaml 配置字段（gen_config.py 校验，未知键/非法取值报错）

| 键 | 取值 | 含义 |
|---|---|---|
| `font_size` | `10pt`/`11pt`/`12pt` | 文档类字号 |
| `paperwidth` / `paperheight` | 带单位尺寸（mm/cm/in/pt/em/ex/bp/pc） | 页面尺寸 |
| `orientation` | `landscape`/`portrait` | 页面方向 |
| `margin_top` / `margin_bottom` / `margin_left` / `margin_right` | 带单位尺寸 | 页边距 |
| `headheight` | 带单位尺寸 | 页眉高度 |
| `columns` | 正整数（默认 2） | 学生版栏数（1 时不进入 multicols） |
| `main_title` | 文本 | 学案主标题（须用户确认，不得杜撰） |
| `teacher_head_left` | 文本 | 教师版页眉左侧文案 |
| `dialogue_enabled` | `true`/`false`/`sec0,sec1` 列表 | 对话层启用范围；列表形式用于分节逐步改造 |
| `dialogue_section_opening` | true/false | 是否要求 section 开头对话 |
| `dialogue_example_opening` | true/false | 是否要求入口题引例对话 |
| `dialogue_max_section_turns` | 正整数（默认 8） | sectiondialogue 台词句数上限 |
| `dialogue_max_example_turns` | 正整数（默认 6） | exampledialogue 台词句数上限 |
| `dialogue_student_reveal` | `prompt_only`（默认）/ `full` | 学生版是否隐藏 `\dlgteacher` 内容 |
| `dialogue_require_coverage_hook` | true/false | 对话块是否必须在 coverage-map.md 登记承接 |

**标题与对话层配置（启动前置 UI 询问）**：每次启动该 skill 制作自学案前，须运行 `python scripts/prompt_dialog.py --project <项目目录>`（Windows 下亦可执行 `scripts/prompt_dialog.bat`）确认「自学案主标题 (main_title)」与「是否启用受控课堂对话体 (dialogue_enabled)」；用户已明确提供的标题和开关直接复用，不再次弹窗；配置成功应用后提示“配置已保存”，若已有 release 且输入已变则追加“发布待重建”（向导本身不触发发布）。严禁在未经用户确认前自行杜撰标题。

**小节标题（`\section*`）**：统一以大写罗马数字加空格开头（`I `、`II `、`III `……），形如 `\section*{I 小节标题}`；编号按装配顺序连续递增（含开篇切片 sec0，若存在则从 `I` 起编），严禁使用中文数字（一、二、三）、顿号或其他编号样式。

## 三、 写作者速查：合法环境与宏

切片文件**绝对不要**包含 `\documentclass`、导言区或 `\begin{document}` / `\end{document}`，直接以 `\section*{...}` 开头。

- **`\qtype{题型}`**：题干开头的题型标签（如 `\qtype{进入题}`）。教师版显示【xx题】字样便于把握设计意图；学生版自动隐藏，不向学生明示题型。
- **`\practicemode{guided|unprompted}`**：题目状态标签，紧跟 `\item` 书写；台账中必须逐题记录。源文件省略该命令时按 guided 处理。`\practicemode{unprompted}` 表示无提示纯习题，教师版显示【无提示练习】字样，学生版隐藏；取值非法时发出 `Package problem-driven Warning`。unprompted 题的学生版必须同时隐藏 `\qtype`、提示行、microknowledge 引导及任何“先做某步/观察某式”的引导，只保留题干、必要已知条件和 `\ansspace`；教师版仍保留完整解答、唯一推荐讲法、易错点与评分点。多小问负担不同而共用一个题级标签时，按其中需要支架的小问标 guided；不得用 unprompted 描述实际含有方法提示的题目。（判定规则权威文本见 `references/production.md`「题目状态 practice_mode」。）
- **`\begin{probchain} ... \end{probchain}`**：题链编号环境，跨小节自动连续编号（内置计数器，无需 series/resume 手工对位；旧写法 `[series=probchain]` / `[resume=probchain]` 仍兼容但需手工对位）。多问小题（含所有证明题）在其内使用嵌套 `enumerate` 排布各小问，**每一问各自紧跟 `\ansspace{...}` 留出相应书写空间**。
- **`\fillin[参考答案]{预留宽度}`**：学生版渲染为下划线留白；教师版自动在下划线上方居中填入醒目的蓝色加粗参考答案。缺少宽度或答案时发出 `Package problem-driven Warning`。
- **`\ansspace{高度}`**：学生版产生垂直书写空白；教师版自动压缩至约 0.4ex，消除页面冗余空行。
- **`\begin{solution}[前缀] ... \end{solution}`**：学生版由 `comment` 宏包彻底剥离（剥离数量计入编译日志 SUMMARY）；教师版渲染为带蓝色标题与缩进的完整解答。
- **`\begin{teacherNote}[批注标题] ... \end{teacherNote}`**：教师版专属的教学策略、常见错误预警与评分重点。
- **`\begin{microknowledge}[标题] ... \end{microknowledge}`**：带框线的小型定义卡片（实线框，前置定义），两版均显示。
- **`\begin{knowledgebox}[标题] ... \end{knowledgebox}`**：带灰色虚线框的章节末结论框，两版均显示，仅用于梳理本节由问题链自主探究推出的核心结论（前置知识与定义须用实线 `microknowledge` 卡片）。
- **对话层环境（可选）**：`\begin{sectiondialogue}[标题]...\end{sectiondialogue}`（黑色实线框，section 开头冲突片段）、`\begin{exampledialogue}[标题]...\end{exampledialogue}`（黑色虚线框，首个入口题引例对话），黑白印刷友好。台词一律 `\speaker{角色}{台词}`；教师专属台词放入 `\dlgteacher{...}`（学生版默认隐藏，`dialogue_student_reveal: full` 时全显）；对话块内禁止 `solution`/`teacherNote`/`\fillin`/`\ansspace`。

  **对话层功能定位（v1.2 升级版）**：
  - `sectiondialogue` 定位：**全节宏观认知的"避坑雷达"**——专门演绎初学者对本节核心概念最容易产生的典型误解、片面直觉与经验陷阱，引发强烈认知冲突，把推翻直觉、代数证明与严谨闭环的裁判权 100% 留白给真实学生；严格 4-6 句。
  - `exampledialogue` 定位：**首道题目的"解题动机点火器"**——针对即将动笔计算的数学对象抛出直觉陷阱，让学生带着反驳欲投入后续题目；严格 3-4 句。
  - 角色分工遵循认知原型矩阵：$\Psi/\tau$（启发导师，引导冲突但严禁总结结论）、$\alpha$（几何经验派，踩"经验主义"陷阱）、$\beta$（形式主义派，暴露"机械套用"思维）、$\gamma$（直觉质疑派，指出极端特例"扎针"）。
  - 对话结构采用"冲突—暴露—对立—悬置"四步法，末句必须以悬置设问或指向计算检验的行动句结束，绝对禁止在末句公布正确答案。
  - **绝对零泄露原则**：对话台词严禁出现紧随题目 `\fillin[...]` 内的答案表达式、分配律恒等式展开，或后续 microknowledge 定理的正式名称与维度数值。
  - 凡是概念平易直白、无需设置认知障碍的题目，必须显式标注 `% dialogue: off-example 概念直白无需预设认知冲突`（理由必填），并在 `overview-guide.md` 与 `coverage-map.md` 中说明。绝不允许"为了写对话而写对话"。

- **编译摘要**：文档结束时自动输出 `[problem-driven] SUMMARY solution=N, teacherNote=N, fillin=N` 到日志，供 build.py 核对两版环境数量是否一致。

**内容类型与合法 TeX 写法对应表**（除表列环境外，其余均为普通段落，**没有同名 LaTeX 环境**，不得自造）：

| 内容类型 | 合法 TeX 写法 |
|---|---|
| discussion / exposition | 普通叙述段落 |
| proofstrategy | 证明题前的加粗引导段 `\textbf{证明策略：}……`，不泄露结论 |
| microknowledge | `\begin{microknowledge}[标题]...\end{microknowledge}`（实线框，前置定义） |
| knowledgebox | `\begin{knowledgebox}[本节结论]...\end{knowledgebox}`（虚线框，节末结论） |
| sectiondialogue（可选对话层） | `\begin{sectiondialogue}[标题]...\end{sectiondialogue}`（黑色实线框） |
| exampledialogue（可选对话层） | `\begin{exampledialogue}[标题]...\end{exampledialogue}`（黑色虚线框） |

## 四、 注释规范（qid / card / dialogue / label-ref）

- **稳定题身份 `% qid: <id>`**：每个 probchain 一级 `\item` 前必须有 `% qid: <稳定题ID>` 注释，全章唯一；显示题号是渲染结果，跨节关联、台账与验收记录一律使用 qid。每道题恰好配备一个 `solution` 与一个 `teacherNote`。切片严禁 `\setcounter{pdprob}` 与 `\def/\ifdefined\TeacherVersion`：题号由装配顺序渲染，双版差异只能由本模板宏产生（check_numbering.py 硬检查）。可同行附带题型/难度元信息（如 `% qid: sec4-entry | 题型: 进入题 | 难度: ★☆☆`）。
- **材料卡片引用**：用**独立行** `% card: CARD-xx`（置于对应 qid 注释之后、题块之前）；旧版合并行 `% qid: ... | card: CARD-xx` 仍被解析器识别，新写作不再输出。切片中出现的卡片 ID 必须已在批准材料包与 `.pd/materials.json` 索引中（deliver 材料链核对）。正文不得出现卡片 ID 以外的来源核验标签或研究过程说明。
- **跨题引用**：需要引用其他题目时，在该题 `\item` 后写 `\label{q:<qid>}`，引用处写 `第~\ref{q:<qid>}~题`；渲染结果为实际全局题号，不得手填数字。
- **对话注释**：exampledialogue 用 `% dialogue: qid=<入口题qid>` 绑定题目；单节关闭写 `% dialogue: off-section <理由>` 或 `% dialogue: off-example <理由>`（理由必填，并在 `overview-guide.md` 与 `coverage-map.md` 说明）。
