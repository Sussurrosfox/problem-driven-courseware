#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
build.py — XeLaTeX 双版编译 + 日志验收

编译只是手段，验收才是目的：返回码为 0 不代表可交付。本脚本对每个目标
（默认 student / teacher）执行：

  1. 编译：xelatex -halt-on-error -interaction=nonstopmode，成功后自动第二遍
     （稳定 \pageref{LastPage} 等交叉引用）；失败可按 --max-retry 重试；
  2. 产物校验：PDF 必须生成，且 PDF / LOG 的修改时间不早于本次编译启动时间
     （防止旧产物造成“假成功”）；
  3. 日志告警扫描（按严重度分级，超过可配置阈值即判失败）：
     - undefined reference / citation      → 严重，任何一处即失败；
     - Package problem-driven Warning      → 严重（\fillin 缺参数等内容缺陷）；
     - mdframed "bad break"                → 严重，任何一处即失败
       （可用 --allow-mdframed-breaks 降级为警告）；
     - Overfull \hbox                      → 超出 --max-overfull-pt（默认 10pt）
       的溢出判失败，其余按警告报告；
     - Underfull \hbox/\vbox               → 计数报告；超过 --max-underfull
       判失败。学生版默认不限制（答题留白产生 underfull 属正常），
       教师版默认 --max-underfull-teacher=3；
     - Font Warning                        → 警告；--strict 下判失败；
  4. 双版一致性核对（P0）：解析日志中的
     [problem-driven] SUMMARY solution=N, teacherNote=N, fillin=N，
     要求学生/教师两版的 solution、teacherNote、fillin 计数完全一致；
     教师版 solution 必须 > 0；学生版日志必须包含“已剥离”标记行。
     页数与文本量仅作诊断（见 compare_versions.py），不作为正确性判据。

用法:
  python build.py [工作目录] [选项]
退出码: 0=通过, 1=编译或验收失败, 2=缺少依赖或输入。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

RE_UNDEF_REF = re.compile(
    r"LaTeX Warning: (?:Reference|Citation) `[^']*' .*undefined|"
    r"There were undefined (?:references|citations)")
RE_PD_WARNING = re.compile(r"Package problem-driven Warning")
RE_MDFRAMED = re.compile(r"Package mdframed Warning: You got a bad break")
RE_OVERFULL = re.compile(r"Overfull \\hbox \(([\d.]+)pt too wide\)")
RE_UNDERFULL = re.compile(r"Underfull \\[hv]box")
RE_FONT_WARN = re.compile(r"(?:LaTeX )?Font Warning|Missing character:")
RE_SUMMARY = re.compile(
    r"\[problem-driven\] SUMMARY solution=(\d+),\s*"
    r"teacherNote=(\d+),\s*fillin=(\d+)")
RE_STRIPPED = re.compile(r"\[problem-driven\] 学生版已剥离")


def scan_log(log_text, target, args):
    """扫描单个日志，返回 (errors, warnings) 两个消息列表。"""
    errors, warnings = [], []

    n_undef = len(RE_UNDEF_REF.findall(log_text))
    if n_undef:
        errors.append("未定义引用/文献 %d 处（交叉引用未闭合或编译遍数不足）" % n_undef)

    n_pd = len(RE_PD_WARNING.findall(log_text))
    if n_pd:
        errors.append("Package problem-driven 警告 %d 处"
                      "（\\fillin 缺少宽度或参考答案，详见日志）" % n_pd)

    n_md = len(RE_MDFRAMED.findall(log_text))
    if n_md:
        msg = "mdframed bad break %d 处（knowledgebox 跨页断裂，需拆框或允许分页）" % n_md
        if args.allow_mdframed_breaks:
            warnings.append(msg)
        else:
            errors.append(msg)

    overs = [float(x) for x in RE_OVERFULL.findall(log_text)]
    serious = [x for x in overs if x > args.max_overfull_pt]
    if serious:
        errors.append("严重 Overfull \\hbox %d 处（最大 %.1fpt > 阈值 %.1fpt）"
                      % (len(serious), max(serious), args.max_overfull_pt))
    minor = len(overs) - len(serious)
    if minor:
        warnings.append("轻微 Overfull \\hbox %d 处（均 ≤ %.1fpt）"
                        % (minor, args.max_overfull_pt))

    n_under = len(RE_UNDERFULL.findall(log_text))
    limit = (args.max_underfull_student if target == "student"
             else args.max_underfull_teacher)
    if n_under:
        if limit is not None and n_under > limit:
            errors.append("Underfull \\hbox/\\vbox %d 处，超过阈值 %d"
                          % (n_under, limit))
        else:
            note = "（学生版留白属正常，仅诊断）" if target == "student" else ""
            warnings.append("Underfull \\hbox/\\vbox %d 处%s" % (n_under, note))

    n_font = len(RE_FONT_WARN.findall(log_text))
    if n_font:
        msg = "字体警告/缺字 %d 处（字体回退可能导致字形替换）" % n_font
        (errors if args.strict else warnings).append(msg)

    return errors, warnings


def parse_summary(log_text):
    m = RE_SUMMARY.search(log_text)
    if not m:
        return None
    return {"solution": int(m.group(1)),
            "teacherNote": int(m.group(2)),
            "fillin": int(m.group(3))}


def compile_target(workdir, target, args):
    """编译单个目标并验收日志。返回 (ok, summary_or_None)。"""
    tex = os.path.join(workdir, target + ".tex")
    pdf = os.path.join(workdir, target + ".pdf")
    log = os.path.join(workdir, target + ".log")
    if not os.path.exists(tex):
        print("[%s] 缺少 %s.tex" % (target, target))
        return False, None

    cmd = ["xelatex", "-halt-on-error", "-interaction=nonstopmode",
           target + ".tex"]
    good = False
    passes = 0
    for attempt in range(args.max_retry + 1):
        t0 = time.time()
        r = subprocess.run(cmd, cwd=workdir, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, encoding="utf-8",
                           errors="replace")
        passes += 1
        if r.returncode == 0:
            # 第二遍稳定交叉引用 / LastPage
            subprocess.run(cmd, cwd=workdir, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, encoding="utf-8",
                           errors="replace")
            passes += 1
            good = True
            break
        print("[%s] 第 %d 次编译失败（-halt-on-error 中止于首个错误）："
              % (target, attempt + 1))
        for line in r.stdout.splitlines():
            if line.startswith("!"):
                print("    " + line)
                break

    print("[%s] 编译%s（%d 遍）" % (target, "成功" if good else "失败", passes))
    if not good:
        return False, None

    # ---- 产物时效校验：防止旧 PDF / 旧日志造成假成功 ----
    stale = []
    for path, what in ((pdf, "PDF"), (log, "日志")):
        if not os.path.exists(path):
            stale.append("%s 未生成（%s）" % (what, os.path.basename(path)))
        elif os.path.getmtime(path) < t0 - 1:
            stale.append("%s 不是本次编译产物（%s 修改时间早于编译启动）"
                         % (what, os.path.basename(path)))
    for msg in stale:
        print("[%s] [错误] %s" % (target, msg))
    if stale:
        return False, None

    with open(log, encoding="utf-8", errors="replace") as f:
        log_text = f.read()

    errors, warnings = scan_log(log_text, target, args)
    for msg in warnings:
        print("[%s] [警告] %s" % (target, msg))
    for msg in errors:
        print("[%s] [错误] %s" % (target, msg))

    summary = parse_summary(log_text)
    if summary is None:
        print("[%s] [错误] 日志缺少 [problem-driven] SUMMARY 行"
              "（header.tex 被改动或编译提前中止？）" % target)
        errors.append("缺少 SUMMARY")
    else:
        print("[%s] SUMMARY solution=%d, teacherNote=%d, fillin=%d"
              % (target, summary["solution"], summary["teacherNote"],
                 summary["fillin"]))
        if target == "teacher" and summary["solution"] == 0:
            print("[%s] [错误] 教师版 solution=0，参考解答缺失" % target)
            errors.append("教师版无 solution")
        if target == "student" and not RE_STRIPPED.search(log_text):
            print("[%s] [错误] 学生版日志缺少“已剥离”标记，"
                  "solution/teacherNote 可能未被剥离" % target)
            errors.append("学生版剥离标记缺失")

    return not errors, summary


def main():
    ap = argparse.ArgumentParser(description="XeLaTeX 双版编译 + 日志验收")
    ap.add_argument("workdir", nargs="?", default=".")
    ap.add_argument("--targets", nargs="+", default=["student", "teacher"])
    ap.add_argument("--max-retry", type=int, default=1)
    ap.add_argument("--max-overfull-pt", type=float, default=10.0,
                    help="单处 Overfull \\hbox 允许的最大溢出点数（默认 10pt）")
    ap.add_argument("--max-underfull-teacher", type=int, default=3,
                    help="教师版允许的 Underfull 数量（默认 3）")
    ap.add_argument("--max-underfull-student", type=int, default=None,
                    help="学生版允许的 Underfull 数量（默认不限制：留白属正常）")
    ap.add_argument("--allow-mdframed-breaks", action="store_true",
                    help="将 mdframed bad break 从失败降级为警告")
    ap.add_argument("--strict", action="store_true",
                    help="字体警告也判为失败")
    args = ap.parse_args()
    workdir = os.path.abspath(args.workdir)

    if not shutil.which("xelatex"):
        print("error: 未找到 xelatex")
        return 2

    ok = True
    summaries = {}
    for t in args.targets:
        t_ok, t_summary = compile_target(workdir, t, args)
        ok &= t_ok
        if t_summary:
            summaries[t] = t_summary

    # ---- 双版 SUMMARY 一致性核对 ----
    if "student" in summaries and "teacher" in summaries:
        s, t = summaries["student"], summaries["teacher"]
        for key in ("solution", "teacherNote", "fillin"):
            if s[key] != t[key]:
                print("[一致性] [错误] 学生版 %s=%d 与教师版 %s=%d 不一致"
                      "（题链在两版中出现次数不同，双版本条件宏可能被破坏）"
                      % (key, s[key], key, t[key]))
                ok = False
                break
        else:
            print("[一致性] 双版 SUMMARY 计数一致：solution=%d, "
                  "teacherNote=%d, fillin=%d"
                  % (s["solution"], s["teacherNote"], s["fillin"]))

    print("[build] 总体结果：%s" % ("通过" if ok else "未通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
