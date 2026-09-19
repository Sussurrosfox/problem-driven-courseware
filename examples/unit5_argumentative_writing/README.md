# Unit 5: 议论文写作教学示例 (B1+)

## 单元概述

这是一个完整的纸笔外语学习示例单元，展示如何将 problem-driven-courseware 改造为外语学习应用。

**主题**: 议论文写作  
**目标等级**: CEFR B1+  
**建议课时**: 6 课时  
**最终产出**: 250-300 字完整议论文

---

## 单元结构

### Section 0: 导入与学习目标
- Can-do 陈述：学完本单元你能做什么
- 真实世界应用场景说明
- 学习策略提示

### Section 1: 范文分析 (Reading Analysis)
**活动类型**: 阅读理解 + 体裁识别  
**核心任务**: 
- 阅读一篇完整议论文范文
- 标注各段落的功能（thesis statement, topic sentence, concession, conclusion）
- 理解标准四段式结构

**教学设计要点**:
- 文本长度：约 280 词
- 题目梯度：从字面理解到推断理解
- 脚手架：加粗关键句子辅助识别

### Section 2: Thesis Statement 专项训练
**活动类型**: 语法操练 + 句型练习  
**核心任务**:
- 辨认 weak vs strong thesis
- 将模糊论点改写成清晰 thesis
- 自主撰写 thesis statement

**脚手架配置**:
- Error analysis 常见错误模式
- Multiple acceptable answers
- Sample answers with explanations

### Section 3: Supporting Arguments Development
**活动类型**: 指导性写作 (Level 2 scaffolding)  
**核心任务**:
- 练习 PREP 模式（Point → Reason → Example → Point）
- 从主题句扩展成完整段落
- 例子与观点匹配练习

**语言支架**:
- Useful phrases for supporting arguments
- Structure guide for paragraph development

### Section 4: Counterargument & Rebuttal
**活动类型**: 交际模拟（书面版）  
**核心任务**:
- 学习让步信号词（admittedly, it is true that）
- 掌握反驳过渡语（however, nevertheless）
- 撰写 counterargument paragraph

**文化注释**:
- 西方学术传统中的 critical thinking 体现
- 如何礼貌地表达不同意见

### Section 5: 独立写作任务
**活动类型**: 独立写作 (Level 4 - minimal scaffolding)  
**核心任务**:
- 就"是否应该延长图书馆开放时间"写完整议论文
- 字数要求：250-300 词
- 时间限制：45 分钟

**评分标准透明化**:
- 四维度评分量表（内容 35% + 语言 35% + 组织 20% + 得体性 10%）
- 1-5 分五级描述
- 详细评分要点

### Section 6: 同伴互评与修改
**活动类型**: Peer review + Self-reflection  
**核心任务**:
- 填写同伴互评表
- 根据反馈进行 revision
- 完成最终版本

**元认知培养**:
- Self-reflection checklist
- Revision tracking

---

## 特色亮点

### 1. 渐进式脚手架设计

| 阶段 | 支持程度 | 学生角色 | 教师角色 |
|-----|---------|---------|---------|
| Sec 1 | 强 support | 识别者 | 示范者 |
| Sec 2 | 强 support | 练习者 | 指导者 |
| Sec 3 | 中 support | 仿写者 | 辅导者 |
| Sec 4 | 中 support | 模仿者 | 建模者 |
| Sec 5 | 无 support | 独立作者 | 评估者 |
| Sec 6 | 互助 support | 评论者/作者 | 协调者 |

### 2. 多模态题型配置

每单元包含：
- ✅ 1 篇阅读文本（范文分析）
- ✅ 2 个语法操练点（Thesis writing + argument extension）
- ✅ 1 个指导性写作任务（Counterargument paragraph）
- ✅ 1 个独立写作任务（Full essay）
- ✅ 1 个同伴互评活动
- ✅ 翻译练习可选（汉英对比）

### 3. 评估体系多元化

- **形成性评估**: 
  - 课堂练习完成情况
  - Peer review 参与度
  
- **总结性评估**:
  - 独立写作作品（使用 rubric）
  - Revision quality（修改痕迹）

- **自我评估**:
  - Self-reflection checklist
  - Can-do checklist 自评

### 4. 教师支持材料

教师版包含：
- 所有答案和解析
- 教学要点提醒
- 学生常见困难预测
- 拓展活动建议
- 时间安排建议
- 多元答案认可

---

## LaTeX 使用说明

### 编译前准备

1. 确保安装了中文字体（如 ctex 宏包）
2. 加载语言学习专用宏包：
```latex
\input{lang-environments.tex}  % 环境定义
\input{lang-macros.tex}        % 命令定义
```

3. 选择版本：
```latex
% 学生版（默认）
\documentclass[12pt]{ctexart}
% 不定义\TeacherVersion

% 或教师版
\def\TeacherVersion{true}  % 启用后显示答案和备注
```

### 可用环境清单

参考 `README_LANG.md` 或以下常用环境：

- `\begin{readingtask}{标题}` - 阅读理解
- `\begin{grammardrill}{主题}` - 语法操练
- `\begin{writingscaffold}[写作任务]` - 写作支架
- `\begin{genreanalysis}{体裁}` - 体裁分析
- `\begin{translationbridge}` - 翻译桥梁
- `\begin{erroranalysis}{偏误诊断}` - 偏误分析
- `\begin{writteninteraction}[交际模拟]` - 交际模拟
- `\begin{solution}` - 答案（仅教师版显示）
- `\begin{teacherNote}` - 教学备注（仅教师版显示）

### 常用命令

- `\fillin[答案]{宽度}` - 填空
- `\ansspace[宽度]` - 留白空间
- `\cefr{B1}` - CEFR 等级标记
- `\genre{argumentative_essay}` - 体裁标记
- `\wordcountrange{120}{150}` - 字数要求
- `\difficulty{B1}` - 难度标记
- `\modelanswer{译文}` - 参考答案
- `\culturetip{注释}` - 文化提示

---

## 实施建议

### 课前准备
1. 准备纸质版学案（A4 双面打印）
2. 准备范文的听力音频（可选，增加多模态）
3. 提前收集类似话题的真实范文作为拓展材料

### 课中流程
1. **第 1 课时**: Section 1-2（范文分析 + Thesis 训练）
   - 重点：术语熟悉、weak→strong 转换
   
2. **第 2 课时**: Section 3-4（论据发展 + Counterargument）
   - 重点：PREP 模式操练、让步写法
   
3. **第 3-4 课时**: Section 5（独立写作）
   - 课堂完成初稿
   - 同伴互评
   
4. **第 5-6 课时**: Section 6 + 讲评
   - 修改完善
   - 优秀作品展示
   - 反思总结

### 课后作业
- 修订后的最终版本
- 同类型话题的额外练习（家庭作业）
- Self-assessment form 填写

---

## 评估与反馈

### 成功指标

**学生层面**:
- Can-do checklist 达成率 ≥ 80%
- 独立写作平均字数达标率 ≥ 90%
- 同伴互评参与质量（有实质性反馈）

**教学层面**:
- 学生课堂参与度（提问、讨论）
- 修改过程的认真程度
- 最终作品的进步幅度

### 数据收集方法
- 学生问卷（Can-do self-rating）
- 作品前后对比分析
- Peer review 质量评估
- 教学反思日志

---

## 后续优化方向

1. **个性化适配**: 
   - 为不同水平学生提供 different difficulty levels
   - 增加选修模块（如学术论文写作、商务信函等）

2. **数字化增强**:
   - 在线同伴互评平台
   - AI 辅助语法检查
   - 电子作品集归档

3. **跨文化整合**:
   - 邀请母语者视角分享
   - 国际笔友交换项目
   - 跨文化写作比较研究

---

## 引用与资源

**范文来源**: 
基于真实语料改编，符合 B1 级 CEFR 描述

**相关理论**:
- CEFR (2020). Common European Framework of Reference for Languages
- Hyland, K. (2016). Teaching and Research Writing
- Nation, I.S.P. (2009). Teaching ESL/EFL Reading and Writing

**技术实现**:
- Problem-Driven Courseware system
- Paper-and-Pencil Language Learning adaptation
- Multi-agent collaborative authoring

---

**创建日期**: 2026 年 9 月 17 日  
**版本**: 1.0  
**许可**: 开放教育用途，请保留引用信息
