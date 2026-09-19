# 纸笔外语学习 Skills 系统文档

## 概述

本模块将 problem-driven-courseware 从数学学科改造为**纸笔外语学习**（Paper-and-Pencil Language Learning）形式，专注于通过**阅读理解→语法分析→翻译训练**的纸笔学习路径。

---

## 核心特性

### 能力模型
- **CEFR 六级对标**：A1-C2 完整分级体系
- **四项核心技能**：阅读分析、翻译技能、语法掌握、句型转换
  ✗ **已移除**：写作系统——改为翻译与转换训练以保持自学材料聚焦性
- **体裁多样化**：记叙文/说明文/议论文/书信体全覆盖

### 纸笔教学优势
- ✅ 无多媒体依赖（无需音频/视频设备）
- ✅ 深度加工（允许精细分析语言结构）
- ✅ 成本效益（印刷分发成本低）
- ✅ 考试导向（适合 TOEFL/IELTS/SAT 备考）

---

## 目录结构

```
problem-driven-courseware/
├── lang-competency/                    # 语言能力核心模块
│   ├── model.yaml                      # CEFR 能力等级模型
│   └── scenarios.yaml                  # 书面交际场景库
│
├── lang-scripts/                       # Python 检查脚本
│   └── check_language_structure.py     # 语言学案结构检查器
│
├── lang-templates/                     # LaTeX 模板扩展
│   ├── lang-environments.tex           # 语言专用 LaTeX 环境定义
│   └── lang-macros.tex                 # 语言宏包定义
│
├── lang-prompts/                       # 子 Agent 提示词
│   ├── reading_prompt.md               # 阅读理解任务设计
│   └── translation_prompt.md           # 翻译与转换训练（原名 writing_prompt.md，v2.0 已废弃）
│
├── templates/
│   └── config_lang.yaml                # 外语学习配置（新增）
│
├── examples/                           # 示例单元（待创建）
│   └── unit5_chinese_english_translation/    # B1 汉英翻译单元
│       ├── main.tex
│       ├── sec0.tex (开篇)
│       ├── sec1.tex (单句翻译练习)
│       ├── sec2.tex (段落翻译)
│       └── ...
│
└── report.md                           # 改造方案报告
```

---

## 快速开始

### 1. 创建项目

```bash
# 在目标位置创建新目录
mkdir my-language-unit
cd my-language-unit

# 复制脚手架文件
cp ../problem-driven-courseware/templates/config_lang.yaml .
cp ../problem-driven-courseware/lang-templates/lang-environments.tex .
cp ../problem-driven-courseware/lang-templates/lang-macros.tex .
```

### 2. 配置项目

编辑 `config_lang.yaml`：

```yaml
target_language: "English"
proficiency_target: "B1"
skill_emphasis: ["reading", "translation"]  # v2.0 已将 writing 改为 translation
main_title: 英语议论文写作学案
```

### 3. 运行检查

```bash
python ../../lang-scripts/check_language_structure.py . --json
```

---

## 主要组件说明

### LaTeX 环境

#### 阅读理解任务
```latex
\begin{readingtask}{Section 1.1}
  \begin{readingtext}
    [约 250 词的阅读文本]
  \end{readingtext}
  
  \begin{questions}
    \question[2]{主旨理解题}
    \ansspace{4cm}
    
    \question[3]{细节题}
    \fillin[答案]{5cm}
  \end{questions}
  
  \begin{solution}
    完整答案和解析
  \end{solution}
\end{readingtask}
```

#### 语法操练
```latex
\begin{grammardrill}{Present Perfect vs Past Simple}
  \rule{have/has + Vpp — 强调与现在的联系}
  \contrast{Past Simple: V-ed (过去的动作)}
  
  \begin{exercises}
    \question{I \fillin[have lost]{3cm} my keys.}
    \question{Shakespeare \fillin[wrote]{3cm} many plays.}
  \end{exercises}
\end{grammardrill}
```

#### 翻译任务
```latex
\begin{translationtask}{Section 1.1 - Chinese-English Translation}
  \textbf{Translate the following Chinese text into English.}
  
  % 中文原文
  \chinesetext{
    随着全球化进程加速，跨文化交流变得越来越重要。
    然而，语言障碍仍然是国际合作的主要挑战之一。
  }
  
  % 关键词汇对照
  \keywords{
    \item globalization: 全球化
    \item cross-cultural communication: 跨文化交流
    \item language barrier: 语言障碍
  }
  
  % 语法焦点
  \syntaxfocus{本段重点考察：现在进行时、被动语态、名词复数}
  
  % 字数要求
  \wordlimit{80-100 words}
  
  % 学生作答区
  \begin{answerspace}
    [留足书写空间]
  \end{answerspace}
  
  % 参考答案（仅教师版显示）
  \begin{solution}
    As the process of globalization accelerates, 
    cross-cultural communication is becoming increasingly important. 
    However, language barriers remain one of the main challenges 
    in international cooperation.
    
    \begin{teacherNote}
    【评分要点】
    - "随着..."译为"As...accelerates"或"With the acceleration of..."均可
    - 注意第三人称单数：communication is
    【常见错误】
    - 误用一般现在时：becomes important（应为进行时表趋势）
    - 中式英语：language block（正确：barrier）
    \end{teacherNote}
  \end{solution}
\end{translationtask}
```

*注：v2.0 版本已移除 `writingscaffold` 环境，原有自由写作功能调整为翻译与转换训练。*

### Python 脚本

`check_language_structure.py` 执行以下检查：
- ✅ 读写任务比例均衡性
- ✅ CEFR 等级一致性验证
- ✅ 语法脚手架充分性
- ✅ 评分标准清晰度
- ✅ 答案完整性
- ✅ 体裁多样性

用法：
```bash
python check_language_structure.py <project_path> --json
```

---

## 子 Agent 工作流

### 阅读理解任务设计师
职责：
- 设计 150-400 词适切难度文本
- 构建梯度题目（literal → inferential → critical）
- 提供完整答案和教学建议

### 翻译与转换训练师
职责：
- 设计精准汉英翻译任务（单句→段落→短文）
- 提供关键词汇对照和语法焦点提示
- 制定四维度评分标准（内容忠实度/语法准确性/词汇地道性/衔接连贯性）

*注：v2.0 已移除"写作任务架构师"角色，原 free writing 功能调整为 translation & transformation training。*

---

## 最佳实践

### 难度控制
- A1-A2: 生词密度 ≤ 8%, 句长≤15 词
- B1-B2: 生词密度 ≤ 5%, 句长≤20 词
- C1+: 生词密度 ≤ 3%, 复杂句式增多

### 题型搭配建议
每单元包含：
- 1-2 篇阅读理解（不同体裁）
- 2-3 个语法操练点
- 1 个单句翻译练习（Level 1）
- 1 个段落翻译任务（Level 2）
*注：v2.0 已移除自由写作任务*

### 脚手架撤出
| 层级 | 支持程度 | 示例 |
|-----|---------|------|
| Level 1 | 完全机械 | 单句精准翻译 |
| Level 2 | 强支持 | 关键词汇对照 + 结构提示 |
| Level 3 | 中等支持 | 观点转换 + 指定句式 |

*注：v2.0 已删除 Level 4（独立写作），聚焦受控翻译训练。*

---

## 与原版对比

| 维度 | 数学原版 | 纸笔语言版 |
|-----|---------|-----------|
| 核心目标 | 逻辑证明能力 | 交际表达能力 |
| 输入渠道 | 文本阅读 | 文本阅读 |
| 输出渠道 | 书写证明 | 书写表达 |
| 评估标准 | 唯一正确答案 | 多维度评分量表 |
| 题型体系 | 进入/辨认/构造/反例/证明 | 阅读/语法/写作/翻译 |
| 脚手架 | 微型知识点卡 | 范文/短语/结构指南 |
| 对话层 | 思维误区暴露（可选） | 弱化使用 |

---

## 常见问题

**Q: 能否同时训练听力和口语？**  
A: 本版本专注纸笔学习，不包含音视频。如需多模态支持，请参考完整版。

**Q: 是否适用于非英语语言？**  
A: 是！只需修改 `target_language` 配置即可支持法、德、日等语言。

**Q: 如何确保语料真实性？**  
A: 启用 `corpus_integration: true`，脚本会自动验证文本是否出自真实语料或符合地道表达。

**Q: 范文会不会导致抄袭？**  
A: v2.0 版本已移除范文仿写功能，改为**译文对照**。译文仅作为评分参考（教师版可见），目的在于展示语法结构运用，而非供学生模仿抄袭。

**Q: 翻译答案是否唯一？**  
A: Level 1 单句翻译答案相对明确；Level 2-3 段落翻译允许多种表达方式，只要在可接受变体范围内且语法正确均可得分。详见 `translation_prompt.md` 中的评分标准。

---

## 下一步行动

1. **创建首个单元**：参考 `examples/unit5_chinese_english_translation/`
2. **开展教学试验**：小范围试用并收集反馈
3. **迭代优化**：根据学生表现调整翻译难度梯度
4. **扩展资源**：建立个人译例库和语法焦点库

---

## 参考资料

- **CEFR 官方框架**: Common European Framework of Reference for Languages (2020)
- **翻译教学法**: Bell, R. (1991). The Theory and Practice of Translation Teaching
- **阅读教学法**: Nation, I.S.P. (2009). Teaching ESL/EFL Reading and Writing
- **语料库资源**: COCA (Corpus of Contemporary American English)

---

**版本**: 2.0 (翻译与转换训练版)  
**更新日期**: 2026 年 9 月 17 日  
**重要变更**: 移除自由写作功能，聚焦汉英翻译训练
