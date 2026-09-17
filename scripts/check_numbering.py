#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "2.1"
r"""
check_numbering.py — 切片装配与题链结构检查

扫描工作目录（以 main.tex 的 \input 顺序为准），检查：

  装配完整性（P0）：
  1. 磁盘上所有 sec*.tex 必须被 main.tex 引入（发现“文件存在但未装配”）；
  2. main.tex 引入的切片文件必须存在（--init 初始化模式下降级为警告，
     允许“骨架先行、暂无正文”的初始化检查）；
  3. 引入顺序必须与切片编号顺序一致（sec1, sec2, ... 单调递增）；
     重复引入同一切片、或不同文件名解析出相同编号，均判失败；
  4. main.tex 引入了切片但全部缺失时，按已发现问题判失败，
     不再以“未发现任何 sec*.tex”放行。

  题链结构（栈式校验，带行号）：
  5. TeX 感知的注释处理：\% 为转义字符，不会被误认为注释起点；
  6. \begin / \end 栈式配对：发现嵌套顺序错误、交叉闭合、未闭合环境；
  7. probchain 内必须至少有一个可见题目（其一级 enumerate 至少一个 \item），
     任何 enumerate/itemize 不得为空，\item 不得出现在列表环境之外，
     probchain 不得嵌套；
  8. [旧写法] series=probchain 必须恰好一次且位于首个含题链的文件，其余
     文件只能用 resume；series/resume 不得与 probchain 环境混用。

  逐题身份与答案关联（切片级硬约束）：
  9. 切片不得改写全局状态：\setcounter{pdprob}、\def\TeacherVersion、
     \ifdefined\TeacherVersion 出现在 sec*.tex 中即失败
     （题号由装配顺序渲染，双版差异只能由模板宏产生）；
 10. probchain 每个一级 \item 题块（至下一个一级 \item 或 \end{probchain}）
     必须恰好含一个 solution 和一个 teacherNote 环境；
 11. 每个一级 \item 之前应有 `% qid: <稳定题ID>` 注释：qid 全章唯一
     （重复判失败；缺失记警告，兼容旧工程）。显示题号是渲染结果，
     qid 才是跨节关联与验收记录使用的稳定身份。

  题目状态 practice_mode（轻量检查；旧文档不含 \practicemode 时不受影响）：
 12. \practicemode 取值只能是 guided / unprompted（缺省视为 guided），
     且必须出现在 probchain 题目块内、每块至多一次；
 13. 标为 unprompted 的题目块，其学生版可见区域不得含 \hintline、
     microknowledge 或 hint 环境等学生版可见提示标记。可见性由环境栈
     决定（solution/teacherNote 结束后恢复），全部 token 按字符位置
     单趟扫描。提示标记出现在题干区（\item 至首个教师环境）判失败；
     出现在本题教师内容结束之后（题间区域）记警告，需人工确认其服务
     后续题目而非本题提示。

  说明：双版 SUMMARY 计数一致性由 build.py 负责；数学正确性归教学验收；
  对话层（sectiondialogue/exampledialogue）结构与泄露由 check_dialogue.py 负责。

退出码: 0=通过, 1=发现问题。
用法: python check_numbering.py [工作目录] [--init] [--json PATH]
"""
import argparse
import os
import re
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence  # noqa: E402

SERIES = re.compile(r"\\begin\{enumerate\}\[[^\]]*series=probchain")
RESUME = re.compile(r"\\begin\{enumerate\}\[[^\]]*resume=probchain")
INPUT = re.compile(r"\\input\{([^{}]+)\}")
# 单趟合并扫描：按字符位置依次处理 begin/end、\item、\practicemode、提示标记
TOKEN = re.compile(
    r"\\(begin|end)\{([a-zA-Z*]+)\}"      # 1=kind 2=env
    r"|\\item\b"                           # 题目/列表项
    r"|\\practicemode\{([^{}]*)\}"         # 3=模式取值
    r"|\\hintline\b")                      # 提示行
PMODE_OK = ("guided", "unprompted")
# unprompted 题目块内禁止出现的学生版可见提示环境（begin 分支另行识别）；
# 对话块（sectiondialogue/exampledialogue）同理：unprompted 题干区出现对话
# 即构成隐性提示（入口题场景另由 check_dialogue.py 硬检查）。
HINT_ENVS = ("microknowledge", "hint", "sectiondialogue", "exampledialogue")
# 教师专属环境：环境栈内存在这些环境时，内容学生版不可见
TEACHER_ENVS = ("solution", "teacherNote")
# 切片禁止改写的全局状态（题号计数器与版本开关）
FORBIDDEN = re.compile(
    r"\\setcounter\{pdprob\}|\\def\\TeacherVersion\b"
    r"|\\ifdefined\\TeacherVersion\b")
QID = re.compile(r"^\s*%\s*qid:\s*([^\s%]+)")
# 可使用 \item 的列表环境（probchain 内部自带一级 enumerate，
# 其直接 \item 就是题目；choices/tasks 为选择题宏包环境）
LIST_ENVS = ("enumerate", "itemize", "description", "choices", "tasks",
             "probchain")


def strip_comment(line):
    r"""去掉行内注释；\% 是转义字符，不作为注释起点。"""
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
    r"""按 main.tex 的 \input 顺序返回切片文件名；无 main.tex 返回 None。"""
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


def check_file(workdir, name, problems, warnings, qid_seen):
    """栈式校验单个切片文件；返回 (含probchain, series数, resume数, enum数)。"""
    path = os.path.join(workdir, name)
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    text = "\n".join(strip_comment(l) for l in lines)
    n_series = len(SERIES.findall(text))
    n_resume = len(RESUME.findall(text))
    has_probchain = "\\begin{probchain}" in text

    for m in FORBIDDEN.finditer(text):
        problems.append(
            "%s: 切片不得改写全局状态（%s）；题号由装配顺序渲染，"
            "双版差异只能由模板宏产生" % (name, m.group(0)))

    # 栈式 begin/end 校验：帧 = [环境名, 起始行, 一级 \item 数]
    stack = []          # 环境帧
    prob_visible = {}   # probchain 帧起始行 -> 一级题目数
    # 当前题目块（probchain 一级 \item）状态，用于逐题与 practice_mode 检查
    cur_item = None
    pending_qid = None  # 最近看到的 % qid: 注释（归属于下一个一级题目）

    def visible():
        """学生版可见性由环境栈决定，solution/teacherNote 结束后自动恢复。"""
        return not any(fr[0] in TEACHER_ENVS for fr in stack)

    def finish_item(end_line):
        """结算当前题目块：逐题答案关联 + unprompted 提示标记 + qid。"""
        nonlocal cur_item
        if not cur_item:
            return
        for env in TEACHER_ENVS:
            n = cur_item["envs"].get(env, 0)
            if n != 1:
                problems.append(
                    "%s:%d: 题目块应恰好含一个 %s 环境（实际 %d 个）"
                    % (name, cur_item["line"], env, n))
        if cur_item["mode"] == "unprompted":
            if cur_item["hints"]:
                problems.append(
                    "%s:%d: unprompted 题目块内出现学生版可见提示标记"
                    "（第 %s 行），无提示练习只能保留题干、必要已知条件和 \\ansspace"
                    % (name, cur_item["line"],
                       ", ".join(str(n) for n in cur_item["hints"][:5])))
            if cur_item["post_hints"]:
                warnings.append(
                    "%s:%d: unprompted 题的教师内容之后出现学生版可见提示标记"
                    "（第 %s 行），请确认其服务后续题目而非本题提示"
                    % (name, cur_item["line"],
                       ", ".join(str(n) for n in cur_item["post_hints"][:5])))
        qid = cur_item["qid"]
        if qid is None:
            warnings.append(
                "%s:%d: 题目块缺少 `%% qid: <稳定题ID>` 注释"
                "（跨节关联与验收记录需要稳定身份）" % (name, cur_item["line"]))
        elif qid in qid_seen:
            problems.append(
                "%s:%d: qid “%s” 与 %s 重复，稳定题身份必须全章唯一"
                % (name, cur_item["line"], qid, qid_seen[qid]))
        else:
            qid_seen[qid] = "%s:%d" % (name, cur_item["line"])
        cur_item = None

    for lineno, raw in enumerate(lines, 1):
        mq = QID.match(raw)
        if mq:
            pending_qid = mq.group(1)
        line = strip_comment(raw)
        # 全部 token 按字符位置单趟处理（同一行内 \item 与 \practicemode
        # 的先后关系由位置决定，不受换行影响）
        for m in TOKEN.finditer(line):
            tok = m.group(0)
            if tok.startswith("\\item"):
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
                        finish_item(lineno)
                        cur_item = {"line": lineno, "mode": "guided",
                                    "mode_set": False, "hints": [],
                                    "post_hints": [], "teacher_closed": False,
                                    "envs": {}, "qid": pending_qid}
                        pending_qid = None
                continue
            if tok.startswith("\\hintline"):
                if cur_item and visible():
                    (cur_item["post_hints"] if cur_item["teacher_closed"]
                     else cur_item["hints"]).append(lineno)
                continue
            if tok.startswith("\\practicemode"):
                value = m.group(3).strip()
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
                continue
            kind, env = m.group(1), m.group(2)
            if kind == "begin":
                if env == "probchain":
                    for frame in stack:
                        if frame[0] == "probchain":
                            problems.append(
                                "%s:%d: probchain 嵌套于第 %d 行的 probchain 内"
                                % (name, lineno, frame[1]))
                if cur_item is not None and env in TEACHER_ENVS:
                    cur_item["envs"][env] = cur_item["envs"].get(env, 0) + 1
                if cur_item and visible() and env in HINT_ENVS:
                    (cur_item["post_hints"] if cur_item["teacher_closed"]
                     else cur_item["hints"]).append(lineno)
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
                if frame[0] in TEACHER_ENVS and cur_item is not None:
                    cur_item["teacher_closed"] = True  # 之后为题间区域
                if frame[0] in LIST_ENVS and frame[0] != "probchain" \
                        and frame[2] == 0:
                    problems.append("%s:%d: %s 环境内没有任何 \\item"
                                    % (name, frame[1], frame[0]))
                if frame[0] == "probchain":
                    finish_item(lineno)
                    prob_visible[frame[1]] = frame[2]
    finish_item(lines and len(lines) or 0)
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
    ap = argparse.ArgumentParser(description="切片装配与题链结构检查")
    ap.add_argument("workdir", nargs="?", default=".")
    ap.add_argument("--init", action="store_true",
                    help="初始化检查：允许引入的切片暂不存在（降级为警告）")
    ap.add_argument("--json", metavar="PATH", help="写入结构化检查结果")
    args = ap.parse_args()
    workdir = os.path.abspath(args.workdir)
    problems = []
    warnings = []

    # ---- F05：输入证据摘要（本检查不读 PDF，pdf_sha256 恒为 null） ----
    manifest = evidence.collect_inputs(workdir)
    digest = evidence.content_digest(manifest)
    report = {"schema_version": evidence.SCHEMA_VERSION,
              "tool": "check_numbering.py", "tool_version": TOOL_VERSION,
              "scope": {"workdir": workdir, "files": []},
              "input_digest": digest, "pdf_sha256": None,
              "status": "pass", "issues": [], "evidence": {}}
    if manifest["missing"] or manifest["unresolved"]:
        report["evidence"]["missing_inputs"] = manifest["missing"]
        report["evidence"]["unresolved_inputs"] = manifest["unresolved"]

    def emit_report():
        report["issues"] = ([{"severity": "error", "message": p}
                             for p in problems]
                            + [{"severity": "warning", "message": w}
                               for w in warnings])
        if args.json:
            evidence.write_report(args.json, report)
            print("[check_numbering] 结构化报告已写入 %s" % args.json)

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
            msg = "main.tex 引入的切片 %s 不存在" % f
            (warnings if args.init else problems).append(
                msg + ("（--init 模式，仅警告）" if args.init else ""))
        # 重复装配：同一路径出现多次，或不同文件名解析出相同编号
        seen_names = set()
        for f in inputs:
            if f in seen_names:
                problems.append("main.tex 重复装配同一切片 %s" % f)
            seen_names.add(f)
        keys = [sec_key(f)[0] for f in inputs]
        seen_keys = {}
        for f, k in zip(inputs, keys):
            if k in seen_keys:
                problems.append("切片编号 %d 被 %s 与 %s 同时占用"
                                % (k, seen_keys[k], f))
            seen_keys.setdefault(k, f)
        if keys != sorted(keys):
            problems.append("main.tex 的切片引入顺序与编号顺序不一致: %s"
                            % ", ".join(inputs))

    files = [f for f in inputs
             if os.path.exists(os.path.join(workdir, f))]
    report["scope"]["files"] = files
    if not files:
        # 先处理已发现的问题；只有真正空的工程才允许“跳过”
        for w in warnings:
            print("[check_numbering] [警告] " + w)
        if problems:
            print("[check_numbering] 发现 %d 个问题:" % len(problems))
            for p in problems:
                print("  - " + p)
            report["status"] = "fail"
            emit_report()
            return 1
        print("[check_numbering] 未发现任何 sec*.tex，跳过。")
        report["status"] = "pass"
        emit_report()
        return 0

    series_seen = 0
    used_probchain_env = False
    used_legacy = False

    legacy_mode = False  # 已有文件使用 series/resume 旧写法
    qid_seen = {}        # qid -> 首次出现位置（全章唯一）

    for idx, name in enumerate(files):
        has_pc, n_series, n_resume, n_enum = check_file(
            workdir, name, problems, warnings, qid_seen)
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

    report["status"] = "fail" if problems else "pass"
    report["evidence"]["qid_count"] = len(qid_seen)
    emit_report()

    for w in warnings:
        print("[check_numbering] [警告] " + w)
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
