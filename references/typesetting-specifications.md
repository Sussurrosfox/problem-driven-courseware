# 排版规范与溢出修复指南 (Typesetting Specifications & Overflow Fixes)

本文件依据 **8-13 自学研学案** 排版溢出修复经验总结，为所有后续课文（Lesson 2--60）编写提供防溢出铁律与模板使用规范。

---

## 一、六大溢出根源与底层机理

### 1. `framed` 宏包与 `multicols` 双栏输出例程的底层冲突（致死垂直溢出 416pt）

**根因分析**：原模板采用 `\usepackage{framed}` 将大批习题整体打包入封闭框，在双栏环境下触发 `\output` 例程抢夺，导致任务块无法跨栏切分。

**修复方案**：
- 禁用 `framed`/`mdframed` 包裹整节题目
- 采用 **开放流架构**：仅标题行使用 `\colorbox{blue!7}` 浅色横幅，内部题目自由展开
- 末尾注入 `\nopagebreak` 防止孤头标题

### 2. 任务标题行缺失段落终结符 `\par`（水平跨栏穿透 256pt / 202pt）

**根因分析**：任务环境或卡片环境在可选参数为空时缺少 `\par` 换段指令，紧随其后的表格被判定为与标题处于**同一段落**，宽度相加突破单栏边界。

**修复方案**：
- 所有盒子环境末尾强制注入 `\par\nopagebreak`
- 表格环境开头添加 `\noindent` 强制新段落
- 标题与内容之间必须有段落分隔

### 3. 单源双输出版面几何失配与表格绝对定宽超标（表格右溢 21.5pt）

**根因分析**：教师版（A4 竖版 160mm）与学生版（A3 横版双栏 179mm×2）共用固定物理列宽表格，总宽超过窄边基准。

**修复方案**：
- **双版窄边对齐律**：所有表格物理总宽以教师版为红线，严格控制在 **155mm 以内**：
  $$\sum \text{ColWidth}_i + 2N\times\text{tabcolsep} + (N+1)\times 0.4\text{pt} \le 155\text{mm}$$
- 压缩内距：`\setlength{\tabcolsep}{3.5pt}`
- 学生版可适度放宽，但主代码保持窄边标准

### 4. 英文长单词与特殊音标列宽不足（单元格内溢出 1.2pt / 9.1pt）

**根因分析**：在 `\raggedright` 模式下，LaTeX 默认不执行首词断字连字符。长单词 `anthropologist` 实际宽度大于列宽，必然溢出。

**修复方案**：
- **英文长词防御律**：生词表英文列绝不低于 **2.6cm**，音标列不低于 **3.2cm**
- 允许 LaTeX 自动断字：`\hyphenation{an-thro-pol-o-gist}`
- 或使用 `\sloppy` 局部容忍（不推荐）

### 5. 教师版填空宏硬性定宽与 `\underline` 不断行（长句答案折行失败）

**根因分析**：原生 `\underline` 创建不可拆分的水平盒（`\hbox`），长句填空答案直接穿出右边距。

**修复方案**：
- **填空可折行律**：必须使用 `ulem` 宏包 `\uline` 替代 `\underline`
- 去除大括号分组，直接在 `\uline` 内用 `\bfseries` 声明加粗
- 使用自适应宽度而非固定 `\makebox`

### 6. 答题空白（`\ansspace`）过度膨胀与刚性断页（页面碎片化与孤页生成）

**根因分析**：盲目给选择题追加 2.5cm 留白、单句英译汉分配 2.0cm，且 `\ansspace` 缺少弹性伸缩胶（elastic glue），导致 TeX 频繁提前断栏。

**修复方案**：
- **空间配比律**：
  - 客观选择题后留白 ≤ **0.3cm**
  - 单句英译汉留白 **1.0～1.5cm**
  - 80-100 词翻译留白 **3.0～3.5cm**
- 底层注入弹性胶：`\vspace{...} plus 0.2 minus 0.3`
- 全局容差防御：`\setlength{\emergencystretch}{2.5em}`

---

## 二、五大铁律（写作纪律）

所有后续课文（Lesson 2--60）编写均须严格遵循以下 **5 项铁律**：

### 1. 容器开放律 (No Closed Box)
- ❌ 严禁使用 `framed`、`mdframed`、`tcolorbox` 将大批习题和作答线整体打包入框
- ✅ 只有标题/引言进条，题目必须在底层自由排版流中裸露以允许自然跨栏

### 2. 双版窄边对齐律 (Narrow-Baseline Rule)
- ❌ 禁止按学生版栏宽设计表格
- ✅ 所有表格物理总宽必须以教师版（A4 竖版 160mm）为红线：
  $$\sum \text{ColWidth}_i + 2N\times\text{tabcolsep} + (N+1)\times 0.4\text{pt} \le 155\text{mm}$$

### 3. 英文长词防御律 (Long-Word Margin)
- ❌ 禁止小于安全阈值的列宽
- ✅ 生词表英文列 ≥ **2.6cm**，音标列 ≥ **3.2cm**，防止无连字符长词戳出单元格

### 4. 填空可折行律 (Breakable Fillin)
- ❌ 严禁使用原生 `\underline` 或在大括号分组内套用 `\textbf`
- ✅ 必须使用 `\uline{\bfseries ...}`（ulem 宏包），支持长句自动折行

### 5. 空间配比律 (Proportional Space)
- ❌ 禁止刚性定宽留白
- ✅ 科学核算留白尺寸并携带弹性参数：
  ```latex
  \vspace{1.2cm} plus 0.2 minus 0.3  % 单句英译汉
  \vspace{3.5cm} plus 0.3 minus 0.5  % 段落翻译
  ```

---

## 三、模板宏定义规范

### 3.1 语言卡 `languagecard`（参考 8-13 sec1.tex L11-14）

```latex
% 独立灰色横幅，强制末尾\par\nopagebreak，表格显式添加\noindent
\newenvironment{languagecard}[1][核心词汇]{%
  \par\vspace{0.6ex}%
  \begingroup\color{gray!50!black}\small
  \noindent\textbf{【#1】}\par\vspace{0.3ex}%
  \nobreak\vspace{0.4ex}%
}{%
  \endgroup\par\nopagebreak\vspace{0.6ex}%
}
```

### 3.2 任务环境开放流重构（建议命名）

**旧版危险写法**（禁用）：
```latex
\begin{taskbox}[可选标题]
  \begin{enumerate}
    \item 第一题……
    \item 第二题……
  \end{enumerate}
\end{taskbox}
```

**新版安全写法**：
```latex
% 仅标题行浅色横幅
\noindent\colorbox{blue!7}{\parbox{\linewidth}{\bfseries 任务一：文本精读}}\par
\nobreak\vspace{0.5ex}
\begin{enumerate}
  \item 第一题……
  \item 第二题……
\end{enumerate}
\nopagebreak
```

### 3.3 生词表表格规范（参考 8-13 sec1.tex L39-50）

```latex
\footnotesize
\setlength{\tabcolsep}{3.5pt}  % 压缩内距
\begin{tabular}{|L{2.6cm}|L{3.2cm}|L{2.1cm}|L{6.3cm}|}
  \hline
  \textbf{生词短语} & \textbf{音标 / 词性} & \textbf{中文释义} & \textbf{语境搭配与学术内涵} \\
  \hline
  % 内容…
\end{tabular}
```

**列宽计算验证**（155mm 红线）：
- 2.6 + 3.2 + 2.1 + 6.3 = 14.2 cm
- 8 × tabcolsep = 8 × 3.5pt ≈ 0.95 cm
- 竖线边框 4 × 0.4pt ≈ 0.21 cm
- **总宽 ≈ 15.36 cm < 15.5 cm** ✓

---

## 四、配置宏加载清单

所有新生成的课程材料必须在导言区注入以下宏包与参数：

```latex
\usepackage{ulem}                 % 支持断行的下划线（填空答案）
\usepackage[framemethod=TikZ]{mdframed}  % 仅限小模块（知识点/对话框）

% 排版容差防御
\setlength{\emergencystretch}{2.5em}
\setlength{\tabcolsep}{3.5pt}     % 表格默认内距
```

---

## 五、检查清单（编译前自检）

1. [ ] 是否禁用了 `framed`/`mdframed` 包裹整节题目？
2. [ ] 所有盒子环境末尾是否有 `\par\nopagebreak`？
3. [ ] 表格总宽是否≤155mm？
4. [ ] 生词表英文列≥2.6cm，音标列≥3.2cm？
5. [ ] 填空宏是否使用 `\uline` 而非 `\underline`？
6. [ ] 答题留白是否携带 `plus/minus` 弹性参数？
7. [ ] 是否已设置 `\emergencystretch=2.5em`？

---

## 六、参考文献

- 详细修复案例与溢出机理推演见 **[typesetting-overflow-analysis.md](../docs/reports/typesetting-overflow-analysis.md)**
- 写作规范与题型判定见 **[references/tex-interface.md](./tex-interface.md)** 与 **[prompts/subagent_prompt.md](../prompts/subagent_prompt.md)**
- 模板实现见 **[templates/header.tex](../templates/header.tex)** 与 **[templates/sec_template.tex](../templates/sec_template.tex)**
