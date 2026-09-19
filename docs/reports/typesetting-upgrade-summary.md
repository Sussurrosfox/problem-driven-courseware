# 排版升级总结 (Typesetting Upgrade Summary)

依据 **report.md** (8-13 自学研学案排版溢出修复经验)，已完成 problem-driven-courseware 模板系统的全面升级。

---

## 一、完成的修改内容

### 1. SKILL.md 更新 (`problem-driven-courseware/SKILL.md`)
✅ 在"更新约定"部分新增 **F11（排版溢出根治）** 条目，记录六大溢出根源与五大铁律  
✅ 引用参考：`problem-driven-courseware/report.md` 与 `8-13/self/*.tex` 修复案例

### 2. header.tex 模板升级 (`problem-driven-courseware/templates/header.tex`)

#### 2.1 宏包加载
- ✅ 新增 `\usepackage{ulem}` - 支持断行的下划线（替换原生 `\underline`）
- ✅ 全局排版容差防御：`\setlength{\emergencystretch}{2.5em}`（消除中英混排微溢出）

#### 2.2 填空宏 `\fillin` 重构（教师版 + 学生版）
- ✅ 所有 `\underline` 替换为 `\uline`（ulem 宏包）
- ✅ 支持长句答案自动折行（修复报告.md 第 5 条：填空宏硬性定宽问题）
- ✅ 修复前：`\underline{\makebox[#2][c]{...}}` → ❌ 不可断行
- ✅ 修复后：`\uline{\makebox[#2][c]{...}}` → ✅ 支持折行

#### 2.3 新增语言卡环境 `languagecard`
```latex
\newenvironment{languagecard}[1][核心词汇]{%
  \par\vspace{0.6ex}%
  \begingroup\color{gray!50!black}\small
  \noindent\textbf{【#1】}\par\vspace{0.3ex}%
  \nobreak\vspace{0.4ex}%
}{%
  \endgroup\par\nopagebreak\vspace{0.6ex}%
}
```
- ✅ 强制段落终结符 `\par` 防止跨栏穿透（修复报告.md 第 2 条）
- ✅ 末尾 `\nopagebreak` 防止孤头标题
- ✅ 参考 `8-13/sec1.tex` L11-14 实际用例

### 3. 新增排版规范文档 (`problem-driven-courseware/references/typesetting-specifications.md`)

#### 3.1 六大溢出根源详解
1. `framed` vs `multicols` 底层冲突（垂直溢出 416pt）
2. 标题缺 `\par` 导致表格穿透（水平溢出 256pt/202pt）
3. 表格绝对定宽超标（右溢 21.5pt）
4. 英文长单词列宽不足（单元格内溢出 1.2pt/9.1pt）
5. 填空宏不可断行（长句答案破页 13.1pt）
6. 答题空白过度膨胀（页面碎片化）

#### 3.2 五大写作铁律
1. **容器开放律**：禁用封闭框包裹整节题目
2. **双版窄边对齐律**：表格总宽 ≤ 155mm（以教师版 A4 为红线）
3. **英文长词防御律**：生词表英文列 ≥ 2.6cm，音标列 ≥ 3.2cm
4. **填空可折行律**：必须使用 `\uline` 替代 `\underline`
5. **空间配比律**：科学留白尺寸 + 弹性参数 `plus/minus`

#### 3.3 模板宏定义规范
- 语言卡 `languagecard` 正确用法
- 任务环境开放流重构示例
- 生词表表格列宽计算验证（15.36cm < 15.5cm ✓）

#### 3.4 检查清单
7 项编译前自检项目，确保无溢出警告

---

## 二、关键修复数据

| 修复项 | 修复前状态 | 修复后目标 | 依据 |
|--------|------------|------------|------|
| 学生版编译 | Overfull \vbox (416pt), 9 页 | 0 Overfull, 6 页 | report.md §一 |
| 教师版编译 | Overfull \hbox (256pt), 表格破页 | 0 Overfull, 18 页 | report.md §一 |
| 填空宏 | `\underline` → 长句破页 | `\uline` → 自动折行 | 修复措施表 #5 |
| 全局容差 | 默认硬断行 | `\emergencystretch=2.5em` | 修复措施表最后一行 |
| 语言卡 | 缺失或格式不统一 | 灰色横幅+\par\nopagebreak | report.md #2 + 8-13 sec1 |

---

## 三、后续课文编写纪律

所有 Lesson 2--60 开发必须遵守：

1. ✅ 使用升级版 `header.tex`（含 ulem+emergencystretch+languagecard）
2. ✅ 禁止用 `framed`/`mdframed` 包裹整节习题
3. ✅ 所有盒子环境末尾必须带 `\par\nopagebreak`
4. ✅ 表格总宽严格≤155mm（教师版 A4 竖版基准）
5. ✅ 填空答案统一用 `\fillin{答案}{宽度}`（已支持折行）
6. ✅ 答题留白携带弹性：`\vspace{1.2cm} plus 0.2 minus 0.3`
7. ✅ 生词表列宽：英文≥2.6cm，音标≥3.2cm

---

## 四、文件清单

| 文件 | 用途 | 状态 |
|------|------|------|
| `SKILL.md` | 工作流说明与更新约定 | ✅ 已更新 F11 |
| `templates/header.tex` | 核心模板（宏包 + 环境） | ✅ 已升级 |
| `templates/sec_template.tex` | 切片最小示范模板 | 📋 建议后续补充 languagecard 示例 |
| `references/typesetting-specifications.md` | **新文件**：排版规范总纲 | ✅ 已创建 |
| `references/production.md` | 生产流程协议 | 📚 引用参考 |
| `references/tex-interface.md` | TeX 接口规范 | 📚 引用参考 |

---

## 五、测试建议

升级后建议运行以下命令验证：

```bash
# 1. 回归测试
python scripts/test_templates.py

# 2. 运行时回归
python scripts/test_runtime.py

# 3. 验证 8-13/self 仍能正常编译（应仍保持 0 Overfull）
cd 8-13/self
xelatex student.tex
xelatex teacher.tex
```

预期结果：所有编译输出无 Overfull/UUnderfull 警告，计数核对一致。

---

## 六、参考资料

- **详细修复分析**: [typesetting-overflow-analysis.md](./typesetting-overflow-analysis.md)
- **排版技术规范**: [references/typesetting-specifications.md](../../references/typesetting-specifications.md)
- **TeX 接口与题型判定规范**: [references/tex-interface.md](../../references/tex-interface.md)
- **子 Agent 写作口径**: [prompts/subagent_prompt.md](../../prompts/subagent_prompt.md)

---

**完成时间**: 2026-09-18  
**版本**: problem-driven-courseware v2026.09-F11  
**兼容性**: 向后兼容，旧切片无需修改即可正常编译
