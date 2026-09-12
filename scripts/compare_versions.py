#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
compare_versions.py — 学生版/教师版 PDF 对比检查

检查项:
  1. 泄露扫描（硬失败）：学生版 PDF 文本中不得出现教师版专属标记。
     默认模式含中文标记（【解】、【证明】、参考解答、教学要点、易错分析、
     评分、教师用书等）与英文单词（Solution / Answer / Proof，词边界匹配），
     并自动收集源文件中 solution/teacherNote 的自定义标题。
     可用 --forbid 追加、--allow 豁免默认模式。命中时给出页码与上下文。
  2. 疑似数学答案泄露（仅警告，供人工复核）：从 sec*.tex 源中提取
     \fillin[答案]{宽度} 的答案文本（学生版只渲染下划线，答案文本出现即
     可疑），命中时给出页码与上下文。注意答案表达式可能本就出现在题干中，
     属启发式检查，默认不判失败；--strict-answers 下判失败。
     --answer-min-len 控制参与检查的最短答案长度，--no-answer-check 关闭。
  3. 源级计数联合检查（硬失败）：统计源文件 \begin{solution} /
     \begin{teacherNote} 数量，与 student.log / teacher.log 中
     [problem-driven] SUMMARY 计数交叉核对，不一致说明剥离计数异常。
  4. 页数 / 文本量对比（仅诊断）：两者页数关系不定，教师版文本量通常
     更大，仅打印供参考，不作为正确性判据。

pdftotext 抽取失败会立即报错退出（退出码 2），绝不按空文本继续比较。
依赖: poppler 的 pdftotext（PATH 中可用）。
用法: python compare_versions.py [工作目录] [选项]
退出码: 0=通过, 1=发现问题, 2=缺少依赖、输入文件或文本抽取失败。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

# 默认禁用词：教师版专属的中文标记与英文单词（英文用词边界正则）
DEFAULT_FORBID_CN = [
    "【解】", "【证明】", "【答】", "参考解答", "参考答案",
    "教学要点", "易错分析", "评分", "教师用书",
]
DEFAULT_FORBID_EN = re.compile(r"\b(Solution|Answer|Proof)\b")

RE_SUMMARY = re.compile(
    r"\[problem-driven\] SUMMARY solution=(\d+),\s*"
    r"teacherNote=(\d+),\s*fillin=(\d+)")
RE_ENV_TITLE = re.compile(
    r"\\begin\{(?:solution|teacherNote)\}\[([^\]]+)\]")


def strip_comments(text):
    """TeX 感知的注释剥离：\\% 是转义字符，不作为注释起点。"""
    out = []
    for line in text.splitlines():
        i = 0
        while True:
            j = line.find("%", i)
            if j < 0:
                out.append(line)
                break
            # 统计 % 前连续反斜杠个数，奇数个则为 \% 转义
            k = j - 1
            while k >= 0 and line[k] == "\\":
                k -= 1
            if (j - 1 - k) % 2 == 1:
                i = j + 1  # 转义的 \%，继续向后找
            else:
                out.append(line[:j])
                break
    return "\n".join(out)


def pdf_pages_text(pdf):
    """按页抽取文本，返回页文本列表；失败返回 None。"""
    r = subprocess.run(["pdftotext", pdf, "-"], capture_output=True)
    if r.returncode != 0:
        return None
    text = r.stdout.decode("utf-8", errors="replace")
    return text.split("\x0c")  # pdftotext 以换页符分页


def find_hits(pages, needle):
    """在分页文本中查找子串，返回 [(页码, 上下文), ...]（最多 5 条）。"""
    hits = []
    for pno, page in enumerate(pages, 1):
        start = 0
        while True:
            i = page.find(needle, start)
            if i < 0:
                break
            ctx = page[max(0, i - 15):i + len(needle) + 15]
            ctx = re.sub(r"\s+", " ", ctx).strip()
            hits.append((pno, ctx))
            start = i + len(needle)
            if len(hits) >= 5:
                return hits
    return hits


def find_hits_re(pages, pattern):
    """正则版 find_hits。"""
    hits = []
    for pno, page in enumerate(pages, 1):
        for m in pattern.finditer(page):
            ctx = page[max(0, m.start() - 15):m.end() + 15]
            ctx = re.sub(r"\s+", " ", ctx).strip()
            hits.append((pno, ctx))
            if len(hits) >= 5:
                return hits
    return hits


def sec_sources(workdir):
    """工作目录中的切片源文件（优先按 main.tex 装配顺序）。"""
    main = os.path.join(workdir, "main.tex")
    names = []
    if os.path.exists(main):
        with open(main, encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r"\\input\{(sec[^}]*)\}",
                                 strip_comments(f.read())):
                name = m.group(1)
                names.append(name if name.endswith(".tex") else name + ".tex")
    if not names:
        names = sorted(f for f in os.listdir(workdir)
                       if re.fullmatch(r"sec.*\.tex", f))
    return [n for n in names
            if os.path.exists(os.path.join(workdir, n))]


def extract_fillin_answers(text):
    """提取 \\fillin[答案]{宽度} 中的答案（支持嵌套花括号）。"""
    answers = []
    for m in re.finditer(r"\\fillin\[", text):
        i = m.end()
        depth, buf = 1, []
        while i < len(text) and depth > 0:
            c = text[i]
            if c == "{":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    break
            elif c == "}":
                depth += 1
            if depth > 0:
                buf.append(c)
            i += 1
        answers.append("".join(buf))
    return answers


def normalize_answer(ans):
    """把 LaTeX 答案规整为可与 pdftotext 文本比较的骨架。"""
    s = re.sub(r"\\[a-zA-Z]+", " ", ans)      # 去控制序列
    s = re.sub(r"[$_{}^{}()\\]", " ", s)       # 去数学定界
    s = re.sub(r"\s+", "", s)
    return s


def load_summary(workdir, target):
    log = os.path.join(workdir, target + ".log")
    if not os.path.exists(log):
        return None
    with open(log, encoding="utf-8", errors="replace") as f:
        m = RE_SUMMARY.search(f.read())
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    ap = argparse.ArgumentParser(description="学生版/教师版 PDF 对比检查")
    ap.add_argument("workdir", nargs="?", default=".")
    ap.add_argument("--forbid", nargs="*", default=[],
                    help="追加禁用模式（纯文本子串）")
    ap.add_argument("--allow", nargs="*", default=[],
                    help="从默认禁用模式中豁免（纯文本子串）")
    ap.add_argument("--answer-min-len", type=int, default=4,
                    help="参与泄露检查的最短 \\fillin 答案骨架长度（默认 4）")
    ap.add_argument("--no-answer-check", action="store_true",
                    help="关闭 \\fillin 答案泄露检查")
    ap.add_argument("--strict-answers", action="store_true",
                    help="疑似答案泄露也判为失败")
    args = ap.parse_args()
    workdir = os.path.abspath(args.workdir)

    if not shutil.which("pdftotext"):
        print("[compare] 未找到 pdftotext（poppler），无法对比。")
        return 2
    stu = os.path.join(workdir, "student.pdf")
    tea = os.path.join(workdir, "teacher.pdf")
    if not (os.path.exists(stu) and os.path.exists(tea)):
        print("[compare] 缺少 student.pdf 或 teacher.pdf，请先运行 build.py。")
        return 2

    # 文本抽取失败必须报错，禁止按空文本继续比较
    stu_pages = pdf_pages_text(stu)
    tea_pages = pdf_pages_text(tea)
    if stu_pages is None or tea_pages is None:
        bad = "student.pdf" if stu_pages is None else "teacher.pdf"
        print("[compare] pdftotext 抽取 %s 失败，无法执行泄露检查。" % bad)
        return 2

    problems = []
    suspicions = []  # 疑似答案泄露：启发式命中，供人工复核

    # ---- 1. 标记泄露扫描（默认模式 + 自定义标题 + 用户追加）----
    forbid = [w for w in DEFAULT_FORBID_CN + args.forbid
              if w not in args.allow]
    src_texts = {}
    for name in sec_sources(workdir):
        with open(os.path.join(workdir, name),
                  encoding="utf-8", errors="replace") as f:
            src_texts[name] = strip_comments(f.read())
    for text in src_texts.values():
        for title in RE_ENV_TITLE.findall(text):
            # 教师版环境标题在渲染时均带有【...】
            bracketed = title if title.startswith("【") else f"【{title}】"
            if bracketed not in forbid and bracketed not in args.allow:
                forbid.append(bracketed)  # solution/teacherNote 自定义标题（加框）

    for w in forbid:
        hits = find_hits(stu_pages, w)
        for pno, ctx in hits:
            problems.append("学生版第 %d 页出现禁用标记 “%s”: …%s…"
                            % (pno, w, ctx))
    if "EN" not in args.allow:
        for pno, ctx in find_hits_re(stu_pages, DEFAULT_FORBID_EN):
            problems.append("学生版第 %d 页出现英文教师标记: …%s…"
                            % (pno, ctx))

    # ---- 2. 疑似 \\fillin 答案泄露（供人工复核）----
    if not args.no_answer_check:
        seen, answers = set(), []
        for text in src_texts.values():
            for raw in extract_fillin_answers(text):
                norm = normalize_answer(raw)
                if len(norm) >= args.answer_min_len and norm not in seen:
                    seen.add(norm)
                    answers.append((raw.strip(), norm))
        n_hit = 0
        for raw, norm in answers:
            hits = find_hits([re.sub(r"\s+", "", p) for p in stu_pages], norm)
            for pno, ctx in hits:
                n_hit += 1
                suspicions.append(
                    "学生版第 %d 页疑似泄露 \\fillin 答案 “%s”"
                    "（需人工复核）: …%s…" % (pno, raw[:30], ctx[:40]))
                break  # 每个答案只报第一处
        print("[compare] \\fillin 答案源级检查：%d 个候选答案，%d 个疑似命中"
              % (len(answers), n_hit))

    # ---- 3. 源级 comment 计数与日志 SUMMARY 交叉核对 ----
    n_sol_src = sum(len(re.findall(r"\\begin\{solution\}", t))
                    for t in src_texts.values())
    n_note_src = sum(len(re.findall(r"\\begin\{teacherNote\}", t))
                     for t in src_texts.values())
    for target in ("student", "teacher"):
        sm = load_summary(workdir, target)
        if sm is None:
            continue
        if (n_sol_src, n_note_src) != sm:
            problems.append(
                "%s.log SUMMARY (solution=%d, teacherNote=%d) 与源文件计数 "
                "(solution=%d, teacherNote=%d) 不一致，剥离/统计异常"
                % (target, sm[0], sm[1], n_sol_src, n_note_src))
    print("[compare] 源文件计数：solution=%d, teacherNote=%d"
          % (n_sol_src, n_note_src))

    # ---- 4. 页数与文本量（仅诊断）----
    stu_text = "\n".join(stu_pages)
    tea_text = "\n".join(tea_pages)
    print("[compare] 页数: 学生版 %d 页 / 教师版 %d 页"
          % (len(stu_pages) - 1, len(tea_pages) - 1))
    ns = len(re.sub(r"\s", "", stu_text))
    nt = len(re.sub(r"\s", "", tea_text))
    print("[compare] 正文字符量: 学生版 %d / 教师版 %d（仅诊断）" % (ns, nt))

    if suspicions:
        print("[compare] %d 条疑似答案泄露（启发式，请人工复核）:"
              % len(suspicions))
        for s in suspicions[:20]:
            print("  ? " + s)
        if len(suspicions) > 20:
            print("  … 其余 %d 条省略" % (len(suspicions) - 20))
        if args.strict_answers:
            problems.extend(suspicions)

    if problems:
        print("[compare] 发现 %d 个问题:" % len(problems))
        for p in problems[:30]:
            print("  - " + p)
        if len(problems) > 30:
            print("  … 其余 %d 条省略" % (len(problems) - 30))
        return 1
    print("[compare] 通过：无泄露、源级计数一致。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
