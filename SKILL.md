---
name: problem-driven-courseware
description: 将数学教材、论文、讲义或课件改造成以问题为入口、保留必要解释并强调引例与反例的研学案和自学文稿。采用单源双输出生成学生版与教师版，依据概念依赖和章节主线组织题链，可选用受控课堂对话层（sectiondialogue/exampledialogue）改造 section 开头与入口引例。当用户提到问题驱动课件、自学案、研学案、8K作业纸、学生版与教师版双输出、数学教材问题化改造或课堂讨论体/对话式引例时使用此 skill。
---

# 问题驱动数学自学案制作工作流 (problem-driven-courseware)

本 Skill 将材料改造成“问题驱动的叙事教材”：问题负责产生认知需要，简短解释负责保持动机、术语和数学精度，完整证明负责建立可迁移的方法。不得为了形式上的提问而删除原文中承担这些功能的解释段。

文稿采用“单源双输出（Single-source, Dual-output）”原则：通过条件宏在同一套源文件中无缝生成**学生版**（隐藏解答、留足书写白、附姓名学号栏）与**教师版**（紧跟题目呈现彩色参考解答、教学要点、易错分析与评分标准）。

> **规则路由制**：本文件只负责用途、摘要与路由；各规则只在下表链接的指定文件维护一份。提示词和模板不得另造冲突规则，口径冲突时以路由目标文件为准。文末“更新约定”仅记录变更历史，不构成第二套生效规则。

---

## 一、 触发条件与适用场景

- **触发关键词**：纯问题驱动、问题链、问题驱动课件、自学案、研学案、8K 作业纸、学生版与教师版双输出、数学教材问题化改造、课堂讨论体、对话式引例（后两者对应可选对话层）。
- **输入材料**：数学教材某章、讲义 Markdown、TeX 源码、定理列表等。
- **输出**：`self/` 独立目录（脚手架 + sec*.tex 切片 + `.pd/` 运行与交付证据 + `release/` 发布产物）；没有 `self` 则新建，重名冲突严禁静默覆盖、须询问用户。
- **适用场景**：专业数学课程的自主探究导学案开发；大开本（大8开横版双栏）试卷/练习册/课堂研学案制作；多子 Agent 并发切片生产完整章节内容（严格实行“一节一写作者”派发机制）。

## 二、 核心约束摘要（权威文本见路由目标）

- **数学正确性**：原文核心论证链必须保留；每个例子/反例由主 Agent 独立重算（定义域、量词、边界、对象类型、前置闭合）。→ `references/production.md` §一/§六
- **依赖闭合**：题目前必须提供其所需对象、运算、记号、维数条件和前置结论；依赖一律按**学生实际可见内容**检查，仅在教师版出现的结论不构成闭合。→ `references/production.md` §二、`prompts/subagent_prompt.md` 第 8 条
- **揭示边界**：按小问及其学习目标判断；此前内容已完成该小问唯一数学动作的，删除/改写该小问，不得以同一大题后续动作豁免。→ `prompts/subagent_prompt.md` 第 8b 条、`prompts/acceptance_prompt.md`
- **单源双输出纪律**：禁止分别手工改写学生版和教师版；差异只能由模板宏产生（`\qtype`/`\practicemode`/`solution`/`teacherNote`/`\fillin`/`\ansspace`/`\dlgteacher`）。→ `references/tex-interface.md` §三
- **qid 纪律**：每题一级 `\item` 前有全章唯一 `% qid:` 注释；切片严禁重置计数器或版本开关宏；跨题引用用 `\label{q:...}`/`\ref` 不手填题号。→ `references/tex-interface.md` §四
- **材料批准链**：正文材料必须可沿“正文 → 卡片 ID → research-brief 需求 → coverage-map 登记 → 来源摘录”回溯；只有主 Agent 两道闸门后的 `approved` 卡片可进入正文。→ `prompts/research_prompt.md`、`references/production.md` §四步骤 2
- **证据与失效**：任何受审输入变化使旧教学 PASS、旧检查报告与旧候选失效；只有当前完整证据能生成新的 release。→ `references/production.md` §四步骤 3.5/5.5
- **文风**：简明严谨、概念克制，禁机械中括号标签，陈列用 enumerate。→ `prompts/subagent_prompt.md` 第 10–12 条

## 三、 文件路由表（每项规则的权威维护位置）

| 文件 | 职责（何时读取） |
|---|---|
| `SKILL.md` | 本文件：用途、触发、摘要、路由、最短入口（启动 skill 时） |
| `references/production.md` | 多阶段运行流程、三张映射表协议、题型判定、practice_mode 判定、材料批准、对话层协议、pdstate attempt 状态机、独立验收调度、构建与 deliver 门禁、恢复方式、质量验收清单（主 Agent 规划/派发/汇总/交付时；对话协议节仅启用对话层时加载） |
| `references/tex-interface.md` | 合法环境/宏、config.yaml 全部字段、qid/card/dialogue/label 注释规范、双版可见性、入口文件与分层架构（写 TeX 或修改模板/配置/检查脚本时） |
| `prompts/subagent_prompt.md` | 切片写作者任务包清单、派发模板、小问判定规则（揭示边界/证明支架/microknowledge/文风）；开篇、对话改造为可选段落（派发切片子 Agent 时） |
| `prompts/research_prompt.md` | 材料需求字段、来源类型与最小证据字段、候选与批准的权限分工、长度预算（派发研究核验 Agent 与两道闸门时） |
| `prompts/acceptance_prompt.md` | 两阶段输入边界、统一判例、逐项处置、acceptance JSON/review-notes 证据格式、保守失效方案（独立教学验收时） |
| `templates/sec_template.tex` | 可编译最小示范切片；注释只解释示例特殊点（起草切片时参照） |
| `flow.md` / `teacher-guide.md` | 课堂实施闭环与教师端工具（**只在课堂实施任务中读取**，生成讲义时不必加载） |
| `templates/` 其余 | main/header/footer/config.yaml/student/teacher 骨架、overview-guide、classroom-plan、error-log（脚手架与课堂模板） |
| `scripts/` | 构建、检查、证据、运行契约、交付脚本（见 §四命令序列；各脚本 docstring 为接口说明） |
| `examples/` | 旧示例与方法论参考（不作回归证据） |

## 四、 最短操作入口

```bash
# 0. 前置配置（标题与对话层开关；用户已提供则直接复用不弹窗）
python scripts/prompt_dialog.py --project self/
# 1. 脚手架与三张映射表（source-map / dependency-map / coverage-map），协议见 references/production.md §二
# 2. 材料需求与核验（可选跳过），生成材料包与机器索引
python scripts/evidence.py materials-index self/ --out self/.pd/materials.json
# 3. 运行契约：init → 逐节 start → 写作者提交 → submit → mark checked
python scripts/pdstate.py self/ init
python scripts/pdstate.py self/ start sec1 --input <本节材料> --prompt-file <提示词>
python scripts/pdstate.py self/ submit sec1 && python scripts/pdstate.py self/ mark sec1 checked
# 4. 装配后的技术检查与构建（均支持 --json）
python scripts/check_numbering.py self/ --json self/.pd/reports/check_numbering.json
python scripts/check_dialogue.py  self/ --json self/.pd/reports/check_dialogue.json
python scripts/build.py           self/ --json self/.pd/reports/build.json
python scripts/compare_versions.py self/ --json self/.pd/reports/compare.json
# 5. 学生审读包 → 独立教学验收（prompts/acceptance_prompt.md）→ 交付门禁
python scripts/make_review_pack.py self/
python scripts/deliver.py self/            # 或证据齐备后 --skip-checks
# 6. 回归：模板或脚本改动后
python scripts/test_templates.py && python scripts/test_runtime.py
```

运行环境预检：`python scripts/build.py self/ --check-env`（Python 3.10+、XeLaTeX、中文字体、`exam-zh-choices`、poppler `pdftotext`）。

## 五、 教师端课堂实施（仅课堂任务读取）

生成讲义后，教师端使用 `teacher-guide.md` 了解工具职责与提示协议，使用 `flow.md` 执行课前—课中—课后闭环。备课时复制 `templates/classroom-plan.md`，课后用 `templates/error-log.md` 记录错误与卡点。`templates/overview-guide.md` 作为章节总览与高观点讲解文档；启用对话层时在其中冻结「对话蓝图」。**这两个文件只在课堂实施任务中读取，讲义生成流程不加载。**

## 更新约定（变更历史，不构成第二套生效规则）

- 2026-09：引入 knowledgebox 节末结论框（每节必须）、证明题前 proofstrategy 策略段（必须）、probchain 统一编号、开篇—首节入口约定、揭示顺序表、研究核验两道闸门与独立教学验收。
- 2026-09：新增标题与小节命名规范——`main_title` 默认「学案」，具体标题须询问用户确认；`\section*` 标题统一以大写罗马数字（I、II、III……）开头。
- 2026-09（工程修整，依据工程架构研究报告）：修复教师版单栏声明未实现、第二遍编译返回码、装配缺失/重复误判、逐题答案关联、fillin 解析器、可见性扫描与证据缺失谎报；引入 qid 稳定题身份、`.pd/` 运行契约（pdstate.py）、学生审读包（make_review_pack.py）与交付汇总门禁（deliver.py）；回归测试改为 test_templates.py；配置生成统一显式 `--project`。
- 2026-09（对话层改造，依据 skill4 方案）：新增可选对话层——`sectiondialogue`/`exampledialogue` 环境与 `\speaker`、`\dlgteacher` 宏（单源双输出，学生版默认隐藏教师专属台词）；`config.yaml` 增加 `dialogue_*` 开关（含 `sec0,sec1` 列表形式的分节逐步启用）；`source-map.md` 新增 `dialogue-hook` 内容类型；新增 `scripts/check_dialogue.py` 结构与泄露硬检查并纳入 deliver 门禁；`templates/overview-guide.md` 增加对话蓝图、`classroom-plan.md` 增加对话回合表、`error-log.md` 增加 dialogue-answer-leak / orphan / dependency-gap / redundancy 错误类型；`prompts/subagent_prompt.md` 增加 dialogue-enhancement 固定字段与四阶段产物要求，`acceptance_prompt.md` 增加隐性提示/孤立对白/依赖缺口验收项；回归测试覆盖“无对话旧 section”与“含两种对话块 section”混合装配。
- 2026-09（启动前置向导）：新增 `scripts/prompt_dialog.py` 与 `prompt_dialog.bat`，在启动 skill 前以现代化 UI 对话框询问并确认自学案主标题与课堂对话体开关，自动更新 `config.yaml` 并重新编译 LaTeX 参数宏，支持无缝 CLI 降级。
- 2026-09（对话层印刷友好与角色名规范化）：`sectiondialogue`/`exampledialogue` 配色由蓝/橙改为黑白灰（实线框/虚线框区分），教师版 `\speaker` 角色名与 `\dlgteacher` 不再使用蓝/绿色；对话角色名统一为希腊字母——教师固定 `$\Psi$`，学生固定 `$\alpha$`、`$\beta$`、`$\gamma$` 等，严禁 Teacher/Alpha 等英文名；`prompt_dialog.bat` 收入 `scripts/` 并改为按自身位置定位脚本的可复用启动器，删除工程根目录的章节特异转发 wrapper。
- 2026-09（证据与运行契约强化 F05/F06）：`scripts/evidence.py` 统一受审输入清单与内容摘要（装配顺序参与摘要、mtime 不参与、动态路径显式记 missing/unresolved），六个检查/交付脚本报告统一 schema_version 2 并绑定 input_digest 与 pdf_sha256，任何受审输入变化均使旧教学 PASS 失效（保守方案）；`pdstate.py` 引入 attempt 机制——派发前 `start` 创建独占 `.pd/candidates/<task>/attempt-NNNN/`（冻结 task.json 与输入快照），写作者提交 secN.tex + result.json（复述 run_id/task_id/attempt_id/input_digest 与输出哈希），submit 五道核对通过才原子提升，旧候选与迟到结果不得晋升。
- 2026-09（交付证据结构化 F07）：新增 `.pd/materials.json` 批准卡片机器索引（`evidence.py materials-index` 由材料包生成，状态精确相等判断），卡片注释解析兼容独立 `% card:` 与旧版合并行；验收记录必须附同名 JSON（reviewed_qids/content_digest/issues 状态机：open 禁止 PASS、fixed 须复验摘要、withdrawn 须误报依据），`run.json` 声明 `required_acceptance_scopes`；compare 疑似项携带稳定 `issue_id`，复核须写 `.pd/review-notes.json` 绑定报告/PDF 哈希，Markdown 非空不再足以放行。
- 2026-09（当前证据门禁与原子发布 F08）：`deliver.py` 只接受 schema_version 2 门禁证据，正常模式按 配置→编号→对话→构建→双版诊断 顺序现场重跑且只信本次新报告；`--skip-checks` 跳过执行但不跳过验证（版本/摘要/PDF/日志/文本证据哈希逐项核对，弃用 mtime 依据）；教学验收不齐返回“待验收”并保留审读草稿；发布改临时目录+原子切换，失败保留上一版完整 release，manifest 记录证据哈希与实际工具版本；self-repair 旧 `.pd` 归档为 `.pd-history-v1` 并按 attempt 流程重建（任务推进至 checked，PASS 待 F09 验收）；`prompt_dialog.py` 明确口径为“配置已保存/发布待重建”，用户已提供的标题与开关直接复用不再弹窗。
- 2026-09（运行时回归 F09）：新增 `scripts/test_runtime.py`——unittest + 临时目录的 16 项证据链回归（摘要语义、attempt 状态机、材料链、验收/复核记录、失败不信任旧报告、原子发布），不触碰真实工程；模板回归与运行时回归并列。
- 2026-09（路由制文档重构 F10）：SKILL.md 由“唯一生效位置”改为路由制——规则归属唯一权威文件：运行流程/状态机/交付归 `references/production.md`，TeX 接口与配置字段归 `references/tex-interface.md`，写作者口径归 `prompts/subagent_prompt.md`（新增任务包清单），研究/验收口径分别归 `prompts/research_prompt.md` / `prompts/acceptance_prompt.md`；`templates/sec_template.tex` 注释精简为示例特殊点；`flow.md`/`teacher-guide.md` 明确只在课堂实施任务中读取；模型指定改为“低成本档位、实际模型名由宿主已配置映射提供”，不再硬编码具体型号。
