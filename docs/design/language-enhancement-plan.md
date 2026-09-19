# Skills 系统改造方案 (Enhancement Plan)

**创建日期**: 2026-09-17  
**改造目标**: 聚焦纸笔自学材料制作，精简写作功能，保留翻译能力，消除冗余设计

---

## 一、改造背景与原因

### 当前问题分析

经过对现有 Skills 系统的全面审查，发现以下需要改进的地方：

#### 1. **写作功能过于宽泛（核心问题）**
当前 `writing_prompt.md` 包含自由写作训练，这与"纸笔自学材料"的核心定位存在矛盾：

- ❌ **Level 4 独立写作**：仅给题目和要求，完全自主组织 → 需要学生具备较高的语言生成能力，超出自学材料辅助范畴
- ❌ **范文仿写依赖**：大量 model paragraph 提供会导致学生照搬而非真正学习
- ❌ **过程导向过重**：planning → drafting → revising 全流程支持更适合课堂教学而非自学
- ❌ **评估复杂化**：四维度评分标准对学生自评要求过高

#### 2. **缺少真正的"输出训练"核心**
纸笔学习环境下，最有效的输出训练应当是：
- ✅ **翻译转换**：汉英对等转换，检验语言精度
- ✅ **句型改写**：基于给定结构的精准操练
- ❌ **自由创作**：超出当前自学材料的 scaffolding 能力

#### 3. **与其他模块重复**
- `readingtask` 已包含 comprehension questions
- `grammardrill` 已覆盖结构操练
- 新增独立的 `writingscaffold` 导致功能重叠

---

## 二、改造方案概述

### 核心原则

**保留大前提**：继续制作纸笔自学材料（Paper-and-Pencil Self-Learning Materials）

**改造方向**：将写作部分从"自由写作训练"改为"受控翻译与转换训练"

### 具体改动清单

| 项目 | 原设计 | 新设计 | 理由 |
|-----|-------|-------|-----|
| **功能定位** | 写作任务设计师（Writing Task Designer） | 翻译与转换训练师（Translation & Transformation Trainer） | 聚焦语言精度检验 |
| **Level 1** | 机械性练习（句型转换/填空） | ✓ 保留 | 属于精准操练 |
| **Level 2** | 指导性写作（强 scaffolding） | ✗ 删除 | 改为"段落翻译" |
| **Level 3** | 半独立写作 | ✗ 删除 | 改为"句子翻译 + 结构重组" |
| **Level 4** | 独立写作 | ✗ 删除 | 完全不符合自学场景 |
| **脚手架** | outline/model phrase/model paragraph | ✓ 保留但用途改变 | 作为翻译对照参考 |
| **评分标准** | 四维度 rubric | ✓ 改为翻译准确性标准 | 更客观可自评 |
| **输出形式** | 自由写作区 | ✓ 改为翻译作答区 | 明确学习目标 |

---

## 三、详细改造步骤

### 第一步：修改 `writing_prompt.md`

#### 3.1 核心职责变更

**原标题**：写作任务设计子 Agent 提示词 (Writing Task Designer)  
**新标题**：翻译与转换训练子 Agent 提示词 (Translation & Transformation Trainer)

**核心原则变更**：
```yaml
原核心原则:
  1. 渐进式脚手架：from guided → independent
  2. 体裁意识培养
  3. 过程导向：planning → drafting → revising
  4. 评估透明化

新核心原则:
  1. 精准对等转换：检验词汇/语法/语域掌握度
  2. 中英对比分析：突出语序/搭配/文化差异
  3. 受控难度递增：sentence → paragraph → short text
  4. 自测可行性：答案唯一或有限变体
```

#### 3.2 任务层级重设

```yaml
新的任务层级设计:
  Level 1: 单句精准翻译（语法操练式）
    - 核心词汇造句翻译
    - 时态/语态结构翻译
    - 从句引导词选择翻译
  
  Level 2: 段落要点翻译（强 scaffolding）
    - 提供关键短语英文对照
    - 给出段落结构框架
    - 限制字数范围（80-120 词）
  
  Level 3: 观点转换表达（中等 scaffolding）
    - 中文观点 → 英文表达
    - 使用指定连接词/句式
    - 长度约束（120-150 词）
  
  ✗ 删除 Level 4：独立写作不再适用自学场景
```

#### 3.3 设计要求调整

**删除内容**：
```latex
% 删除以下元素:
\genre{argumentative_essay}          # 体裁分类不再强调
\structureguidestart                 # 改为翻译结构提示
\endsstructureguide
\modelparagraphstart                 # 范文改为译文对照
\endmodelparagraph
\writingtime{20 minutes}              # 改为翻译时间建议
```

**新增内容**：
```latex
% 新增翻译训练元素:
\chinesetext{中文原文}
\keywords{关键短语中英文对照}
\structurehint{段落结构提示（非完整提纲）}
\wordlimit{100-120 words}
\syntaxfocus{本翻译重点考察的语法结构}
```

#### 3.4 答案与评分标准

**评分标准简化为**：
```yaml
翻译准确性评分:
  - 内容忠实度 (Content Fidelity): 40%
    * 是否遗漏/歪曲原意
    * 关键信息点完整性
    
  - 语法准确性 (Grammar Accuracy): 30%
    * 时态/语态/一致性问题
    * 句子结构完整性
    
  - 词汇地道性 (Lexical Appropriateness): 20%
    * 搭配是否正确
    * 避免中式英语
    
  - 衔接连贯性 (Cohesion): 10%
    * 连接词使用得当
    * 逻辑推进清晰
```

**输出格式示例**：
```latex
\begin{translationtask}{Section {{SECTION_ID}} - Translation Task {{TASK_TITLE}}}
  \chinesetext{
    随着全球化进程加速，跨文化交流变得越来越重要。
    然而，语言障碍仍然是国际合作的主要挑战之一。
    我们需要通过教育和合作来克服这些问题。
  }
  
  \keywords{
    \item globalization: 全球化
    \item cross-cultural communication: 跨文化交流
    \item language barrier: 语言障碍
    \item international cooperation: 国际合作
  }
  
  \syntaxfocus{本段落重点考察：现在完成时、让步状语从句、被动语态}
  
  % 学生作答区
  \begin{answerspace}
    [留足书写空间]
  \end{answerspace}
  
  % 参考答案（仅教师版）
  \begin{solution}
    As the process of globalization accelerates, 
    cross-cultural communication is becoming increasingly important. 
    However, language barriers remain one of the main challenges 
    in international cooperation. We need to overcome these problems 
    through education and collaboration.
    
    \begin{teacherNote}
    【评分要点】
    - "随着..."译为"As...accelerates"或"With the acceleration of..."均可
    - "越来越重要"可用 increasingly important / growing importance
    - "仍然"应译为 remain / continue to be
    - 注意第三人称单数：communication is
    【常见错误】
    - 误用一般现在时：becomes important（应为进行时表趋势）
    - 中式英语：language block（正确：barrier）
    \end{teacherNote}
  \end{solution}
\end{translationtask}
```

### 第二步：更新 `README_LANG.md`

#### 5.1 核心特性章节更新

```markdown
## 核心特性

### 能力模型
- **CEFR 六级对标**：A1-C2 完整分级体系
- **四项核心技能**：阅读分析、翻译技能、语法掌握、句型转换
  ✗ 删除"写作系统"——改为翻译与转换训练

### 纸笔教学优势
- ✅ 无多媒体依赖
- ✅ 深度加工（允许精细分析语言结构）
- ✅ 成本效益
- ✅ 考试导向（适合 TOEFL/IELTS/SAT 备考）
- ✅ **翻译训练提升语言精度**（新增亮点）
```

#### 5.2 目录结构更新

```
├── lang-prompts/                       # 子 Agent 提示词
│   ├── reading_prompt.md               # 阅读理解任务设计
│   └── translation_prompt.md           # 翻译与转换训练（原名 writing_prompt.md）
```

#### 5.3 快速开始更新

配置文件中：
```yaml
skill_emphasis: ["reading", "translation"]  # 改为 translation 而非 writing
```

### 第三步：更新能力模型 (`lang-competency/model.yaml`)

#### 6.1 写作目标调整为翻译目标

```yaml
# 每个 CEFR 等级的写作_targets 改为 translation_targets

B1:
  translation_targets:
    - "翻译常见的日常话题句子"
    - "将简单段落翻译成英文（100-150 词）"
    - "表达个人意见和理由"
    # 删除原有的 write letter/article 等自由写作目标
```

#### 6.2 新增翻译技能专项

```yaml
paper_specific_competencies:
  # ... existing ...
  
  translation_skills:
    chinese_to_english:
      - "lexical_equivalence": 词汇对等转换
      - "avoiding_chinglish": 避免中式英语
      - "syntax_adaptation": 句法结构调整
      - "idiomatic_expression": 地道表达替换
      
    english_to_chinese:
      - "reading_for_translation": 阅读理解的翻译转化
      - "cultural_adaptation": 文化语境适配
      
    transformation_skills:
      - "paraphrasing": 同义改写
      - "sentence_combining": 句于合并
      - "voice_conversion": 语态转换
```

### 第四步：更新 LaTeX 模板定义

#### 7.1 新增翻译环境 (`lang-environments.tex`)

```latex
% 翻译任务环境
\newenvironment{translationtask}[1]{
  \begin{taskblock}{#1}
  \noindent\textbf{Translate the following Chinese text into English.}
}{
  \end{taskblock}
}

% 中文原文框
\newenvironment{chinesetext}{
  \begin{quote}
  \small
}{
  \end{quote}
}

% 关键词对照
\newcommand{\keywordsstart}{\begin{itemize}\itemsep2pt}
\newcommand{\endkeywords}{\end{itemize}}

% 语法焦点提示
\newcommand{\syntaxfocus}[1]{\teacheronly{\textcolor{gray}{[Focus: #1]}}}
```

#### 7.2 宏包定义 (`lang-macros.tex`)

```latex
% 翻译相关宏命令
\newcommand{\chineseinput}[1]{\begin{chinesetext}#1\end{chinesetext}}
\newcommand{\transfocus}[1]{\syntaxfocus{#1}}
\newcommand{\wordlimit}[1]{\teacheronly{\textit{(Target: #1)}}}
```

### 第五步：更新脚本检查器

#### 8.1 `check_language_structure.py` 调整

**删除检查项**：
```python
# 删除以下检查:
- verify_writing_scaffolding()       # 不再验证写作脚手架
- check_genre_diversity()            # 不再检查体裁多样性
- validate_independent_task()        # 不再验证独立写作
```

**新增检查项**：
```python
# 新增翻译训练检查:
def check_translation_fidelity():
    """验证翻译任务的中文原文质量"""
    pass

def check_lexical_equivalence():
    """检查关键短语对照是否充分"""
    pass

def check_grammar_focus():
    """验证语法焦点是否明确且适切"""
    pass

def validate_self_assessment_feasibility():
    """验证翻译答案的可自评性（答案需相对明确）"""
    pass
```

### 第六步：更新 Subagent Prompt

在 `prompts/subagent_prompt.md` 中：

#### 9.1 任务包更新

```markdown
## 切片写作者任务清单

### 原有写作改造任务：✗ 删除
- Level 2/3/4 写作任务派发指令
- 范文仿写指导
- 自由创作提示

### 新增翻译训练任务：✓ 新增
- **单句翻译任务**：每节至少 3 个不同语法点的句子翻译
- **段落翻译任务**：1 个 80-150 词的中文段落，提供关键词汇对照
- **句型转换任务**：基于同一内容，使用不同句式/时态/语态重写
```

#### 9.2 小问判定规则调整

```markdown
### 揭示边界判断（翻译任务）:
- 若前文已给出该句型的英文范例，删除同类翻译题
- 若刚讲解过某个语法点，立即配套相应翻译练习

### 文风要求:
- 中文原文简明清晰，避免歧义
- 关键词汇提前给出中英文对照
- 语法焦点明确标注
```

---

## 四、预期效果与优势

### 4.1 教学效果

✅ **目标更聚焦**：学生明确知道这是翻译训练而非自由创作  
✅ **难度可控**：基于给定内容的转换，不会出现无从下笔的情况  
✅ **自测可行**：答案相对明确，便于学生对照检查  
✅ **评分客观**：减少主观评判，提高评分一致性  

### 4.2 系统效率

✅ **Prompt 精简**：从复杂的写作指导简化为翻译规则  
✅ **Scaffolding 减负**：无需生成大量范文，减少 Token 消耗  
✅ **质量稳定**：翻译任务更容易保证语言准确性  
✅ **回归测试简化**：测试用例从 4 级写作降为 3 级翻译  

---

## 五、迁移计划与时间安排

### Phase 1: 设计与开发 (Week 1-2)
- [ ] 完成 `translation_prompt.md` 编写
- [ ] 更新 LaTeX 模板定义
- [ ] 修改 `check_language_structure.py`
- [ ] 编写回归测试用例

### Phase 2: 内部测试 (Week 3)
- [ ] 在小范围试点单元试用
- [ ] 收集学生反馈（可读性/可操作性）
- [ ] 调整翻译难度梯度
- [ ] 优化关键词汇对照格式

### Phase 3: 文档更新 (Week 4)
- [ ] 更新 README_LANG.md
- [ ] 修改示例单元
- [ ] 完善常见问题解答
- [ ] 发布升级说明

### Phase 4: 正式上线 (Week 5)
- [ ] 正式发布 v2.0 版本
- [ ] 标记旧版 writing_prompt.md 为 deprecated
- [ ] 提供迁移指南

---

## 六、风险评估与应对

### 风险 1：用户习惯难以改变
**问题**：部分教师可能仍希望保留自由写作训练  
**应对**：
- 在官方版本逐步淘汰，但允许 fork 自定义
- 提供"写作友好模式"配置开关供特殊需求

### 风险 2：翻译任务单一化
**问题**：长期只做翻译可能导致枯燥  
**应对**：
- 多样化翻译类型（句/段/观点/文体）
- 增加创意翻译任务（广告语/诗歌片段）
- 结合阅读文本进行"读后翻译"

### 风险 3：难度把控困难
**问题**：翻译难度不易量化  
**应对**：
- 严格遵循 CEFR 描述制定难度标准
- 建立译例库作为难度参照
- 增加 peer review 机制

---

## 七、替代方案思考

### 若不完全移除写作功能，可采用折衷方案：

#### 折衷方案 A：限制性写作
- 保留写作任务，但必须基于给定大纲/关键词
- 禁止 Level 3/4 级别
- 只提供 skeleton outline 而非 full model

#### 折衷方案 B：读写分离
- 写作放在课后拓展部分
- 标注"建议课堂使用"
- 自学材料以翻译为主

**推荐选择**：**完全移除自由写作**（本方案），理由：
1. 自学材料定位清晰
2. 翻译更符合纸笔学习特性
3. 系统维护成本更低
4. 学习效果更易评估

---

## 八、结论与建议

### 总结

本次改造的核心是从 **"写作训练"** 转向 **"翻译与转换训练"**，目的是：

1. ✅ 聚焦自学材料的核心价值
2. ✅ 降低系统复杂度
3. ✅ 提高评估客观性
4. ✅ 符合纸笔学习环境特点

### 最终建议

**强烈建议采用此改造方案**，原因如下：

- 🎯 **定位清晰**：明确区分"自学材料"与"课堂教材"
- 📈 **效果可验证**：翻译答案相对明确，便于学生 self-check
- 🔧 **维护简便**：减少 prompt 复杂度，提升稳定性
- 🌟 **特色突出**：强化翻译训练成为产品差异化亮点

---

## 附录：当前 Skills 其他问题清单

*此部分列出当前 Skills 系统除写作功能外的其他需要注意的问题*

### 问题 1: Reading Task 的难度控制不够严格

**现象**：
- 阅读文本长度与 CEFR 等级不完全对应
- 生词密度有时超标（尤其是 B1+ 等级）

**影响**：
- 学生可能因难度不适配而丧失信心
- 无法准确反映 CEFR 分级效果

**建议**：
- 在 `check_language_structure.py` 中增加自动统计
- 提供 CEFR 对照的文本长度/生词密度查询表
- 强制要求在 config.yaml 中标注预估难度

### 问题 2: Grammar Drill 的覆盖面不足

**现象**：
- 某些单元只关注 1-2 个语法点
- 缺乏系统性复习循环

**影响**：
- 知识点碎片化
- 遗忘率高

**建议**：
- 建立 grammar topics 矩阵
- 每单元末尾添加"回顾旧知识点"环节
- 增加 spaced repetition 标记

### 问题 3: Translation 与 Grammar 的内容重复

**现象**：
- 翻译练习与语法操练内容高度重合
- 学生感到重复训练

**影响**：
- 学习动力下降
- 时间效率低

**建议**：
- 明确分工：Grammar Drill 侧重结构识别，Translation 侧重综合应用
- 错开出现顺序：先讲语法 → 再做翻译 → 最后复习
- 翻译任务使用全新素材

### 问题 4: 教师版答案解释不够详尽

**现象**：
- solution 环境中仅提供正确答案
- 缺少常见错误预测

**影响**：
- 教师难以针对性辅导
- 学生自学时遇到障碍无人解答

**建议**：
- 统一 solution 结构：答案 + 解析 + 常见错误 + 教学建议
- 增加 `\commonmistakes` 环境
- 鼓励 AI 生成典型错误案例

### 问题 5: 缺少跨单元的知识关联

**现象**：
- 各 section 相对独立
- 看不到知识体系的构建过程

**影响**：
- 学习者难以建立整体认知
- 遗忘后不知如何查找复习

**建议**：
- 在 overview-guide 中建立知识图谱
- 每个单元开头标注 prerequisite
- 增加 "see also" 引用标记

### 问题 6: 体裁多样性实际执行不足

**现象**：
- 多数单元仍以议论文为主
- 记叙文/书信体占比偏低

**影响**：
- 语言能力发展不均衡
- 与实际应用场景脱节

**建议**：
- 在 curriculum design 阶段强制规划体裁配比
- 设置体裁覆盖率 KPI（如：每个 CEFR 等级至少涵盖 3 种体裁）
- 在 assessment 中体现体裁多样性权重

### 问题 7: Config 字段过多，初学者困惑

**现象**：
- config.yaml 包含数十个字段
- 新手不知道哪些必填、哪些选填

**影响**：
- 启动成本高
- 容易配置错误

**建议**：
- 精简默认配置（只保留 core 字段）
- 提供 starter-config 模板
- 在 prompt_dialog 中分步引导填写

### 问题 8: 缺少多语言支持测试

**现象**：
- 目前主要测试英语
- 法语/德语/日语等其他语言支持不完整

**影响**：
- 国际化程度受限
- 通用性受影响

**建议**：
- 建立多语言测试套件
- 提取语言无关的通用逻辑
- 抽象出 language-specific plugins

### 问题 9: 证据链过长，调试困难

**现象**：
- `.pd/` 目录结构复杂（attempt/candidates/reports/materials 等）
- 故障定位需要追踪多个文件

**影响**：
- 开发调试效率低
- 用户遇到错误不知如何处理

**建议**：
- 简化证据结构（合并部分子目录）
- 提供更友好的错误诊断工具
- 在 key 节点增加 human-readable summary

### 问题 10: 回归测试覆盖率仍有提升空间

**现象**：
- `test_runtime.py` 仅覆盖 16 项
- 边缘 case 测试不足

**影响**：
- 潜在 bug 可能漏测
- 升级风险高

**建议**：
- 增加到 25+ 项测试
- 增加模糊测试（fuzzing）
- 建立 CI/CD 自动化测试流程

---

## 文档修订历史

| 日期 | 修订人 | 修订内容 |
|-----|-------|---------|
| 2026-09-17 | System | 初始版本创建 |

---

**文档结束**
