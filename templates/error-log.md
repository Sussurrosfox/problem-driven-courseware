# 课后错误记录（模板）

## 基本信息

- 课程/章节：
- 日期与班级：
- 材料版本：学生版 `________`；教师版 `________`

## 核心题表现记录

| 题号 | qid | delivery_role | 卡点分类 | 表现与证据 | 涉及知识点 | 处置建议 |
|---|---|---|---|---|---|---|
|  | `core` | guided/unprompted | 题干不清/前置知识缺失/推理断裂/表达不规范 |  |  |  |
|  | `core` | guided/unprompted |  |  |  |  |

**说明**: 只记录 core 任务中的卡点，self-study 题目不在此记录。

## 无提示题（unprompted）复核

- 无提示题是否出现普遍入口卡点（题号与表现）：
- 是否需要恢复为 guided（题号与理由）：

## 对话层复核（启用对话层时填写）

| 位置（section/qid） | 错误类型 | 表现与证据 | 处置建议 |
|---|---|---|---|
|  | dialogue-answer-leak / dialogue-orphan / dialogue-dependency-gap / dialogue-redundancy |  |  |

- `dialogue-answer-leak`：学生版可见对白提前出现后续结论、完整计算或唯一证明路线（只重写对白；实质提示无法移除时该题改为 guided 并更新覆盖表）。
- `dialogue-orphan`：对白结束留下的问题没有任何后续题目承接（删除对白或把末句改接真实存在的 qid，不得添加装饰性题目）。
- `dialogue-dependency-gap`：对白使用未定义符号、运算或定理（先补最小 microknowledge 或恢复 exposition）。
- `dialogue-redundancy`：对白仅重复 exposition 而未改变学生判断（删重复句，保留一条能承接入口题的句子）。

## 下次修订

- 下次修订只调整以下之一（圈选）：题目状态（guided/unprompted） / 题序 / 题干
- 具体调整内容：
