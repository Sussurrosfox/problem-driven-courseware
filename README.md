# Problem-Driven Courseware (问题驱动自学研学案制作工作流)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-green.svg)](https://www.python.org/)
[![LaTeX: XeLaTeX](https://img.shields.io/badge/TeX-XeLaTeX-orange.svg)](https://www.latex-project.org/)
[![Status: Production Ready](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)]()

`problem-driven-courseware` 是一套面向 AI Agent（如 Google Antigravity、Claude Code、Cursor 等）与教学教研人员的**专业教材与讲义问题化改造工作流**。

它能将数学与外语学科的传统教材、讲义、论文或讲稿，系统化重构为以**认知冲突为起点、核心概念渐次闭合、问题链环环相扣**的专业自学案与研学案。

---

## 🌟 核心特性

### 1. 单源双输出 (Single-source, Dual-output)
同一套 LaTeX 源码，通过条件宏编译生成两套完全对齐但视角不同的权威交付物：
- **学生版 (Student Edition)**：大 8 开（A3 横版双栏折页标准大开本）或 A4 格式，隐藏参考解答，保留严谨预留的作答书写线与填空框（`\fillin`、`\ansspace`），附带标准姓名学号栏。
- **教师版 (Teacher Edition)**：A4 竖版案头备课本，紧随题目展示彩色完整解答、教学重难点、易错分析、微知识卡片（`microknowledge`）与评分参考。

### 2. 双学科体系深度支持
- **数学学科 (Mathematics)**：
  - **题链体系**：进入题、辨认题、构造题、反例题、证明题层次分明。
  - **受控课堂对话层**：支持在章节引入（`sectiondialogue`）与例题引导（`exampledialogue`）中注入希腊字母代号角色对白，模拟师生认知冲突与设问悬置。
  - **知识闭合律**：题前必须提供前置对象与记号，严禁超前引用与隐性泄露。
- **外语学科 (Paper-and-Pencil Language Learning)**：
  - **纯纸笔学习闭环**：无多媒体依赖，专注“阅读理解 $\to$ 语法分析 $\to$ 翻译与句型转换”。
  - **CEFR 六级对标**：对标 A1–C2 标准能力模型（`lang-competency/model.yaml`）与真实书面交际场景库（`lang-competency/scenarios.yaml`）。
  - **防溢出排版五大铁律**：容器开放律、双版窄边对齐律、英文长词防御律、填空可折行律、空间配比律，彻底解决长词截断与双栏跨栏穿透问题。

### 3. 全链路自动化门禁与证据链审查
- **Attempt 状态机**：切片派发与提交严格隔离，防止并发任务冲突与旧证据污染。
- **静态技术门禁**：自动审查题号连续性（`check_numbering.py`）、对话层泄露与悬置规范（`check_dialogue.py`）、语言学案结构均衡性（`check_language_structure.py`）。
- **交付门禁汇总**：`deliver.py` 统筹配置、编译、比较与教学验收，确保只有 100% 证据完整的版本才能发布到 `release/`。

---

## 📁 目录结构

```text
problem-driven-courseware/
├── SKILL.md                 # Antigravity / Claude Agent 核心技能定义与规则路由入口
├── flow.md                  # 教师端课堂实施闭环指南（课前-课中-课后）
├── teacher-guide.md         # 教师端备课工具与提示协议说明
├── LICENSE                  # MIT 开源许可证
├── README.md                # 项目主文档
│
├── prompts/                 # 数学研学案写作者与审核 Agent 提示词
│   ├── subagent_prompt.md   # 切片写作者任务包派发模板与写作规范
│   ├── research_prompt.md   # 材料核验与两道闸门审核规范
│   └── acceptance_prompt.md # 独立教学验收审查标准与 issue 处理规范
│
├── references/              # 核心规则与权威技术规范
│   ├── production.md        # 多阶段生产流程、三张映射表协议与状态机契约
│   ├── tex-interface.md     # LaTeX 环境/宏命令规范、配置字段与 qid 纪律
│   └── typesetting-specifications.md # 防溢出五大铁律、版心尺寸与排版规范
│
├── templates/               # LaTeX 骨架模板与课堂配套文档
│   ├── main.tex             # 主编译入口骨架
│   ├── header.tex           # 导言区宏包配置与双版本控制宏
│   ├── footer.tex           # 结尾文档清理
│   ├── config.yaml          # 数学版标准配置模板
│   ├── config_lang.yaml     # 外语版标准配置模板
│   ├── sec_template.tex     # 最小标准切片示范
│   ├── student.tex          # 学生版顶层入口
│   ├── teacher.tex          # 教师版顶层入口
│   ├── classroom-plan.md    # 课堂教学计划模板
│   ├── overview-guide.md    # 章节总览与对话蓝图
│   └── error-log.md         # 课后学生错误诊断记录表
│
├── scripts/                 # 核心构建、检查、交付与测试自动化脚本
│   ├── prompt_dialog.py     # 现代化 GUI/CLI 启动配置前置向导
│   ├── prompt_dialog.bat    # Windows 快速启动脚本
│   ├── gen_config.py        # 读取 config.yaml 并生成 TeX 配置宏
│   ├── check_numbering.py   # 题目编号、qid 与全局状态静态检查器
│   ├── check_dialogue.py    # 对话层格式、泄露与悬置规范检查器
│   ├── build.py             # 双版本 XeLaTeX 编译构建调度引擎
│   ├── compare_versions.py  # 双版本抽取诊断与差异分析
│   ├── pdstate.py           # 运行时 Attempt 状态机与任务提交流程管理
│   ├── evidence.py          # 受审材料机器索引与内容摘要计算
│   ├── make_review_pack.py  # 提取生成学生审读包
│   ├── deliver.py           # 交付汇总总门禁与原子发布
│   ├── test_runtime.py      # 状态机与交付门禁单元回归测试
│   └── test_templates.py    # 模板编译与宏行为回归测试
│
├── lang-competency/         # 外语模块：能力体系与场景模型
│   ├── model.yaml           # CEFR A1-C2 等级定义与能力矩阵
│   └── scenarios.yaml       # 真实书面交际场景库与易错模式预测
│
├── lang-prompts/            # 外语模块：专职子 Agent 提示词
│   ├── reading_prompt.md    # 文本精读与分析任务设计
│   └── translation_prompt.md# 翻译与句型转换训练设计
│
├── lang-templates/          # 外语模块：专用 LaTeX 宏与环境扩展
│   ├── lang-environments.tex# readingtask/grammardrill 等环境定义
│   └── lang-macros.tex      # 词汇、填空与语言标注宏定义
│
├── lang-scripts/            # 外语模块：专属质检工具
│   └── check_language_structure.py # 外语学案结构完整性与 CEFR 一致性检查器
│
├── examples/                # 参考样例与示范切片
│   ├── eg.tex / eg_solution.tex # 基础样例源码（学生版/教师版）
│   ├── 8K.tex               # 8 开试卷大版面样例
│   ├── workflow.md          # 经典工作流记录
│   └── unit5_argumentative_writing/ # B1+ 议论文写作完整样例单元
│
└── docs/                    # 深入研究报告、设计演变与迁移指南
    ├── reports/             # 排版与系统架构深度研究报告
    │   ├── typesetting-overflow-analysis.md # LaTeX 排版溢出根治机理研究
    │   ├── typesetting-upgrade-summary.md   # 排版升级总结
    │   └── implementation-summary.md        # 外语版实施总结报告
    ├── design/              # 方案设计与演化记录
    │   └── language-enhancement-plan.md     # 外语教学系统强化方案
    └── guides/              # 详细技术集成与操作指南
        ├── language-integration-guide.md    # 外语模块集成与迁移手册
        └── language-learning-guide.md       # 纸笔外语学习系统完整指南
```

---

## 🛠️ 环境准备

运行本工具链需要安装以下工具环境：

1. **Python 3.10+**：
   ```bash
   pip install pyyaml
   ```
2. **TeX 排版环境**：
   - 安装 [TeX Live](https://www.tug.org/texlive/)、[MacTeX](https://www.tug.org/mactex/) 或 [MiKTeX](https://miktex.org/)。
   - 确保包含 `xelatex` 引擎及 `ctex`、`ulem`、`mdframed`、`multicols`、`exam-zh-choices` 等宏包。
   - 操作系统需具备常用的中文字体（如思源宋体/黑体、SimSun/SimHei）。
3. **Poppler 工具库**（用于 PDF 文本抽取与版本差异诊断）：
   - `pdftotext` 必须在系统 `PATH` 中可用。

可以使用以下命令进行环境自检：
```bash
python scripts/build.py self/ --check-env
```

---

## 🚀 快速上手工作流

### A. 制作数学自学研学案

```bash
# 1. 前置配置向导：设定自学案主标题与课堂对话体开关
python scripts/prompt_dialog.py --project self/

# 2. 状态机初始化与材料索引
python scripts/pdstate.py self/ init
python scripts/evidence.py materials-index self/ --out self/.pd/materials.json

# 3. 派发切片并启动写作者任务
python scripts/pdstate.py self/ start sec1 --input <本节切片材料> --prompt-file prompts/subagent_prompt.md

# 4. 写作者提交并标记完成
python scripts/pdstate.py self/ submit sec1
python scripts/pdstate.py self/ mark sec1 checked

# 5. 技术检查与构建
python scripts/check_numbering.py self/ --json self/.pd/reports/check_numbering.json
python scripts/check_dialogue.py  self/ --json self/.pd/reports/check_dialogue.json
python scripts/build.py           self/ --json self/.pd/reports/build.json
python scripts/compare_versions.py self/ --json self/.pd/reports/compare.json

# 6. 生成审读包并交付发布
python scripts/make_review_pack.py self/
python scripts/deliver.py self/
```

### B. 制作纸笔外语研学案

```bash
# 1. 创建项目并引用语言模板
mkdir my-unit && cd my-unit
cp ../templates/config_lang.yaml ./config.yaml
cp ../lang-templates/lang-environments.tex .
cp ../lang-templates/lang-macros.tex .

# 2. 依据 lang-prompts/ 起草阅读与翻译任务

# 3. 运行语言结构与 CEFR 一致性检查
python ../lang-scripts/check_language_structure.py .
```

---

## 🧪 自动化测试套件

本项目内置完备的自动化回归测试，确保在对模板或脚本进行任何改动后，全链路控制逻辑与 TeX 宏包行为稳健无错：

```bash
# 运行运行时证据链与状态机测试 (16 项单元测试)
python scripts/test_runtime.py

# 运行模板解析与 XeLaTeX 真实构建回归测试
python scripts/test_templates.py

# 运行外语示例单元结构检查
python lang-scripts/check_language_structure.py examples/unit5_argumentative_writing
```

---

## 📄 许可证

本项目基于 [MIT 许可证](LICENSE) 开源。欢迎自由使用、二次开发与教学推广。
