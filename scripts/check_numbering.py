#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_numbering.py — 切片装配与题链结构检查

扫描工作目录（以 main.tex 的 \\input 顺序为准），检查：

  装配完整性（P0）：
  1. 磁盘上所有 sec*.tex 必须被 main.tex 引入（发现“文件存在但未装配”）；
  2. main.tex 引入的切片文件必须存在；
  3. 引入顺序必须与切片编号顺序一致（sec1, sec2, ... 单调递增）；

  题链结构（栈式校验，带行号）：
  4. TeX 感知的注释处理：\\% 为转义字符，不会被误认为注释起点；
  5. \\begin / \\end 栈式配对：发现嵌套顺序错误、交叉闭合、未闭合环境；
  6. probchain 内必须至少有一个可见题目（其一级 enumerate 至少一个 \\item），
     任何 enumerate/itemize 不得为空，\\item 不得出现在列表环境之外，
     probchain 不得嵌套；
  7. [旧写法] series=probchain 必须恰好一次且位于首个含题链的文件，其余
     文件只能用 resume；series/resume 不得与 probchain 环境混用。

  题目状态 practice_mode（轻量检查；旧文档不含 \\practicemode 时不受影响）：
  8. \\practicemode 取值只能是 guided / unprompted（缺省视为 guided），
     且必须出现在 probchain 题目块内、每块至多一次；
  9. 标为 unprompted 的题目块，其学生版可见区域（\\item 至首个
     solution/teacherNote 之间）不得含 \\hintline、microknowledge 或
     hint 环境等学生版可见提示标记。

  说明：题号/题干的双版一致性与教师版解答存在性由 build.py 的双版
  SUMMARY 核对与 compare_versions.py 的源级计数负责，本脚本不重复检查。

退出码: 0=通过, 1=发现问题。
用法: python check_numbering.py [工作目录]
"""
import os
import re
import sys

SERIES = re.compile(r"\\begin\{enumerate\}\[[^\]]*series=probchain")
RESUME = re.compile(r"\\begin\{enumerate\}\[[^\]]*resume=probchain")
INPUT = re.compile(r"\\input\{([^{}]+)\}")
TOKEN = re.compile(r"\\(begin|end)\{([a-zA-Z*]+)\}|\\item\b")
# 题目状态字段（可选，缺省 guided）
PMODE = re.compile(r"\\practicemode\{([^{}]*)\}")
PMODE_OK = ("guided", "unprompted")
# unprompted 题目块内禁止出现的学生版可见提示标记
HINT_MARK = re.compile(
    r"\\hintline\b|\\begin\{microknowledge\}|\\begin\{hint")
# 可使用 \item 的列表环境（probchain 内部自带一级 enumerate，
# 其直接 \item 就是题目；choices/tasks 为选择题宏包环境）
LIST_ENVS = ("enumerate", "itemize", "description", "choices", "tasks",
             "probchain")


def strip_comment(line):
    """去掉行内注释；\\% 是转义字符，不作为注释起点。"""
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k = j - 1
        while k >= 0 and line[k] == "\\":
            k -= 1
        if (j - 1 - k) % 2 == 1:  # 奇数个反斜杠 → \% 转义
            i = j + 1
        else:
            return line[:j]


def sec_inputs(workdir):
    """按 main.tex 的 \\input 顺序返回切片文件名；无 main.tex 返回 None。"""
    main = os.path.join(workdir, "main.tex")
    if not os.path.exists(main):
        return None
    files = []
    with open(main, encoding="utf-8", errors="replace") as f:
        for line in f:
            for m in INPUT.finditer(strip_comment(line)):
                name = m.group(1)
                if re.match(r"sec[^/\\]*(\.tex)?$", name):
                    files.append(name if name.endswith(".tex")
                                 else name + ".tex")
    return files


def sec_key(name):
    m = re.search(r"(\d+)", name)
    return (int(m.group(1)) if m else 0, name)


def check_file(workdir, name, idx, problems):
    """栈式校验单个切片文件；返回 (含probchain, series数, resume数)。"""
    path = os.path.join(workdir, name)
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    text = "\n".join(strip_comment(l) for l in lines)
    n_series = len(SERIES.findall(text))
    n_resume = len(RESUME.findall(text))
    has_probchain = "\\begin{probchain}" in text

    # 栈式 begin/end 校验：帧 = [环境名, 起始行, 一级 \\item 数]
    stack = []          # 环境帧
    prob_visible = {}   # probchain 帧起始行 -> 一级题目数
    # 当前题目块（probchain 一级 \item）状态，用于 practice_mode 轻量检查：
    # stem = 学生版可见区域（\item 至首个 solution/teacherNote 之间）未结束
    cur_item = None

    def finish_item():
        """结算当前题目块：unprompted 块内不得有学生版可见提示标记。"""
        nonlocal cur_item
        if cur_item and cur_item["mode"] == "unprompted" \
                and cur_item["hints"]:
            problems.append(
                "%s:%d: unprompted 题目块内出现学生版可见提示标记"
                "（第 %s 行），无提示练习只能保留题干、必要已知条件和 \\ansspace"
                % (name, cur_item["line"],
                   ", ".join(str(n) for n in cur_item["hints"][:5])))
        cur_item = None

    for lineno, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        for m in TOKEN.finditer(line):
            if m.group(0).startswith("\\item"):
                # \item 必须位于列表环境内；计入最内层列表的一级计数
                top_list = None
                for frame in reversed(stack):
                    if frame[0] in LIST_ENVS:
                        top_list = frame
                        break
                if top_list is None:
                    problems.append("%s:%d: \\item 出现在列表环境之外"
                                    % (name, lineno))
                else:
                    top_list[2] += 1
                    if top_list[0] == "probchain":
                        finish_item()
                        cur_item = {"line": lineno, "mode": "guided",
                                    "mode_set": False, "stem": True,
                                    "hints": []}
                continue
            kind, env = m.group(1), m.group(2)
            if kind == "begin":
                if env == "probchain":
                    for frame in stack:
                        if frame[0] == "probchain":
                            problems.append(
                                "%s:%d: probchain 嵌套于第 %d 行的 probchain 内"
                                % (name, lineno, frame[1]))
                if env in ("solution", "teacherNote") and cur_item:
                    cur_item["stem"] = False  # 之后内容仅教师版可见
                stack.append([env, lineno, 0])
            else:  # end
                if not stack:
                    problems.append("%s:%d: \\end{%s} 没有配对的 \\begin"
                                    % (name, lineno, env))
                    continue
                if stack[-1][0] != env:
                    open_desc = ", ".join("%s(第%d行)" % (fr[0], fr[1])
                                          for fr in stack)
                    problems.append(
                        "%s:%d: \\end{%s} 与当前未闭合环境交叉闭合（栈: %s）"
                        % (name, lineno, env, open_desc))
                    # 尝试恢复：弹出到匹配位置
                    for k in range(len(stack) - 1, -1, -1):
                        if stack[k][0] == env:
                            del stack[k:]
                            break
                    continue
                frame = stack.pop()
                if frame[0] in LIST_ENVS and frame[0] != "probchain" \
                        and frame[2] == 0:
                    problems.append("%s:%d: %s 环境内没有任何 \\item"
                                    % (name, frame[1], frame[0]))
                if frame[0] == "probchain":
                    finish_item()
                    prob_visible[frame[1]] = frame[2]
        # ---- practice_mode 轻量检查（在本行环境/token 更新之后扫描） ----
        for m in PMODE.finditer(line):
            value = m.group(1).strip()
            if value not in PMODE_OK:
                problems.append(
                    "%s:%d: \\practicemode 取值非法（“%s”），只能是 guided 或 unprompted"
                    % (name, lineno, value))
            if cur_item is None:
                problems.append(
                    "%s:%d: \\practicemode 出现在 probchain 题目块之外"
                    % (name, lineno))
            elif cur_item["mode_set"]:
                problems.append(
                    "%s:%d: 同一题目块内 \\practicemode 重复出现（首次在第 %d 行）"
                    % (name, lineno, cur_item["line"]))
            else:
                cur_item["mode"] = value
                cur_item["mode_set"] = True
        if cur_item and cur_item["stem"]:
            for _m in HINT_MARK.finditer(line):
                cur_item["hints"].append(lineno)
    for frame in stack:
        problems.append("%s: 环境 %s（第 %d 行 \\begin）到文件末尾未闭合"
                        % (name, frame[0], frame[1]))
    for start_line, n_items in prob_visible.items():
        if n_items == 0:
            problems.append("%s:%d: probchain 内没有可见题目"
                            "（一级 enumerate 缺少 \\item）"
                            % (name, start_line))
    n_enum = len(re.findall(r"\\begin\{enumerate\}", text))
    return has_probchain, n_series, n_resume, n_enum


def main():
    workdir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    problems = []

    inputs = sec_inputs(workdir)
    if inputs is None:
        print("[check_numbering] 未发现 main.tex，退化为文件名排序（"
              "无法检查装配完整性）。")
        inputs = sorted((f for f in os.listdir(workdir)
                         if re.fullmatch(r"sec.*\.tex", f)), key=sec_key)
    else:
        # ---- 装配完整性检查 ----
        on_disk = {f for f in os.listdir(workdir)
                   if re.fullmatch(r"sec.*\.tex", f)
                   and f != "sec_template.tex"}
        not_assembled = sorted(on_disk - set(inputs), key=sec_key)
        for f in not_assembled:
            problems.append("切片 %s 存在但未在 main.tex 中装配（漏 \\input）"
                            % f)
        missing = [f for f in inputs
                   if not os.path.exists(os.path.join(workdir, f))]
        for f in missing:
            problems.append("main.tex 引入的切片 %s 不存在" % f)
        keys = [sec_key(f)[0] for f in inputs]
        if keys != sorted(keys):
            problems.append("main.tex 的切片引入顺序与编号顺序不一致: %s"
                            % ", ".join(inputs))

    files = [f for f in inputs
             if os.path.exists(os.path.join(workdir, f))]
    if not files:
        print("[check_numbering] 未发现任何 sec*.tex，跳过。")
        return 0

    series_seen = 0
    used_probchain_env = False
    used_legacy = False

    legacy_mode = False  # 已有文件使用 series/resume 旧写法

    for idx, name in enumerate(files):
        has_pc, n_series, n_resume, n_enum = check_file(
            workdir, name, idx, problems)
        if has_pc:
            used_probchain_env = True
        if legacy_mode and idx > 0 and n_enum and not has_pc \
                and n_series == 0 and n_resume == 0:
            problems.append("%s: 旧写法题链缺少 resume=probchain，"
                            "编号将重新从 1 开始" % name)
        if n_series or n_resume:
            used_legacy = True
            legacy_mode = True
            series_seen += n_series
            if n_series and idx != 0:
                problems.append("%s: series=probchain 出现在非首个切片文件中"
                                % name)
            if n_series > 1:
                problems.append("%s: series=probchain 出现 %d 次（应至多 1 次）"
                                % (name, n_series))

    if used_legacy and not used_probchain_env and series_seen == 0:
        problems.append("旧写法题链缺少 series=probchain 起点（首个切片未声明 series）")
    if used_legacy and used_probchain_env:
        problems.append("probchain 环境与 series/resume 旧写法混用，题号将错位，请统一为 probchain")

    if problems:
        print("[check_numbering] 发现 %d 个问题:" % len(problems))
        for p in problems:
            print("  - " + p)
        return 1
    print("[check_numbering] 通过：%d 个切片文件装配完整、题链结构一致。"
          % len(files))
    return 0


if __name__ == "__main__":
    sys.exit(main())
