#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
test_templates.py — 基于当前模板的回归测试（跨平台，Python 驱动）

分两组：
  A. 纯逻辑用例（无需 xelatex）：复现 struct.md §8 报告的反例，
     验证 check_numbering.py / compare_versions.py / gen_config.py /
     build.py 的控制逻辑修复。
  B. 真实编译用例（PATH 中有 xelatex 与 pdftotext 才运行，否则跳过）：
     用当前 templates 构造最小工程，验证教师版单栏、版本剥离、
     自动续号与三脚本全链路通过。

用法: python scripts/test_templates.py
退出码: 0=全部通过（跳过不计失败）, 1=存在失败。
"""
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
TEMPLATES = os.path.join(SCRIPTS, "..", "templates")
PY = sys.executable

_failures = []
_skips = []


def report(name, ok, detail=""):
    print("[%s] %s%s" % ("PASS" if ok else "FAIL", name,
                         (" — " + detail) if detail and not ok else ""))
    if not ok:
        _failures.append(name)


def skip(name, why):
    print("[SKIP] %s — %s" % (name, why))
    _skips.append(name)


def load(modname, filename):
    spec = importlib.util.spec_from_file_location(
        modname, os.path.join(SCRIPTS, filename))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def run(script, *argv):
    return subprocess.run([PY, os.path.join(SCRIPTS, script)] + list(argv),
                          capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


def make_project(root, main_inputs, secs):
    """复制当前模板并写入 main.tex 与切片；生成配置。返回项目目录。"""
    for f in ("header.tex", "footer.tex", "config.yaml",
              "student.tex", "teacher.tex"):
        shutil.copy(os.path.join(TEMPLATES, f), os.path.join(root, f))
    lines = ["\\input{header.tex}", "", "\\begin{document}",
             "\\begin{center}", "  {\\Huge \\textbf{\\pdMainTitle}}",
             "\\end{center}", "\\raggedcolumns", "\\pdBeginColumns", ""]
    lines += ["\\input{%s}" % n for n in main_inputs]
    lines += ["", "\\input{footer.tex}"]
    with open(os.path.join(root, "main.tex"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    for name, body in secs.items():
        with open(os.path.join(root, name), "w", encoding="utf-8") as f:
            f.write(body)
    r = run("gen_config.py", "--project", root)
    assert r.returncode == 0, r.stdout + r.stderr
    return root


SEC_OK = r"""\section*{第一节}
\begin{probchain}
% qid: t-entry
\item \qtype{进入题} 计算 $1+1=$\fillin[$2$]{15mm}。
\ansspace{1cm}
\begin{solution}
$2$。
\end{solution}
\begin{teacherNote}
观察加法。
\end{teacherNote}
% qid: t-identify
\item \qtype{辨认题} 判断：$2+2=4$ 是否成立？\fillin[成立]{15mm}
\ansspace{1cm}
\begin{solution}
成立。
\end{solution}
\begin{teacherNote}
确认判据。
\end{teacherNote}
\end{probchain}
\begin{knowledgebox}[本节结论]
加法事实。
\end{knowledgebox}
"""


# ---------------------------------------------------------------- A. 纯逻辑

SEC_DLG = r"""\section*{第一节}
\begin{sectiondialogue}[入口]
\speaker{$\Psi$}{逆命题是否成立？难道结论并非必然？}
\speaker{$\gamma$}{先看一个反例，其中是否有矛盾？}
\speaker{$\beta$}{我枚举阶数，为何算出来不对？}
\speaker{$\Psi$}{本节任务 SECTASKMARK：究竟能否检验猜测？}
\end{sectiondialogue}
\begin{exampledialogue}[引例]
% dialogue: qid=t-entry
\speaker{$\Psi$}{判断该猜测 ENTRYQMARK，难道其中存在疑问？}
\speaker{$\alpha$}{若存在则指数为 2，这岂不是显然矛盾？}
\speaker{$\gamma$}{究竟能否逐个检验？\dlgteacher{（DLGSECRET 确认矛盾。）}}
\end{exampledialogue}
\begin{probchain}
% qid: t-entry
\item \qtype{进入题} 计算 $1+1=$\fillin[$2$]{15mm}。
\ansspace{1cm}
\begin{solution}
$2$。
\end{solution}
\begin{teacherNote}
观察加法。
\end{teacherNote}
\end{probchain}
\begin{knowledgebox}[本节结论]
加法事实。
\end{knowledgebox}
"""

COVERAGE_DLG = ("| dialogue-hook | sec1 | 逆命题冲突 | 承接 t-entry |\n"
                "| t-entry | sec1 | 进入题 | guided |\n")


def t_dialogue_checks():
    """check_dialogue.py：结构、位置、绑定、泄露、配置范围。"""
    import re as _re

    def proj(sec, cov=COVERAGE_DLG, cfg_patch=None):
        d = tempfile.mkdtemp()
        make_project(d, ["sec1.tex"], {"sec1.tex": sec})
        if cov is not None:
            with open(os.path.join(d, "coverage-map.md"), "w",
                      encoding="utf-8") as f:
                f.write(cov)
        if cfg_patch:
            p = os.path.join(d, "config.yaml")
            with open(p, encoding="utf-8") as f:
                c = f.read()
            with open(p, "w", encoding="utf-8") as f:
                f.write(cfg_patch(c))
        return d

    ok = []
    # 含两种对话块的合规工程 → 通过
    d = proj(SEC_DLG)
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 0)
    # 缺 sectiondialogue → 失败
    d = proj(_re.sub(r"(?s)\\begin\{sectiondialogue\}.*?"
                     r"\\end\{sectiondialogue\}\n?", "", SEC_DLG))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "缺少 sectiondialogue" in r.stdout)
    # 对话块混入 solution → 泄露判失败
    d = proj(SEC_DLG.replace("\\speaker{$\\beta$}{我枚举阶数，为何算出来不对？}",
                             "\\speaker{$\\beta$}{为何算出来不对？} "
                             "\\begin{solution}泄露\\end{solution}"))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "对话块内禁止" in r.stdout)
    # exampledialogue 绑定不存在的 qid → 失败
    d = proj(SEC_DLG.replace("% dialogue: qid=t-entry",
                             "% dialogue: qid=t-nope"))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "不是本切片题目 qid" in r.stdout)
    # 旧工程：dialogue_enabled: false 且无对话块 → 完全沿用旧流程
    d = proj(SEC_OK, cov=None,
             cfg_patch=lambda c: c.replace("dialogue_enabled: true",
                                           "dialogue_enabled: false"))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 0 and "未使用对话层" in r.stdout)
    # 列表形式：sec1 不在启用列表却含对话块 → 失败
    d = proj(SEC_DLG,
             cfg_patch=lambda c: c.replace("dialogue_enabled: true",
                                           "dialogue_enabled: sec2"))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "启用范围" in r.stdout)
    # 缺 coverage-map.md → 失败
    d = proj(SEC_DLG, cov=None)
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "coverage-map.md" in r.stdout)
    # unprompted 入口题配对话 → 失败
    d = proj(SEC_DLG.replace("\\item \\qtype{进入题}",
                             "\\item \\practicemode{unprompted} "
                             "\\qtype{进入题}"))
    r = run("check_dialogue.py", d)
    ok.append(r.returncode == 1 and "unprompted" in r.stdout)
    report("对话层结构/泄露/配置检查（check_dialogue）", all(ok), str(ok))

def t_fillin_parser():
    """V6：fillin 答案含花括号不得吞入宽度与尾部。"""
    cv = load("cv", "compare_versions.py")
    cases = [
        (r"\fillin[\frac{1}{2}]{20mm} TAIL", ["\\frac{1}{2}"]),
        (r"\fillin[是]{20mm}", ["是"]),
        (r"\fillin{20mm}", []),
        (r"\fillin[a\]b]{20mm}", ["a\\]b"]),
        (r"x \fillin[$e^{x}$]{25mm} y", ["$e^{x}$"]),
    ]
    bad = [(src, cv.extract_fillin_answers(src), want)
           for src, want in cases
           if cv.extract_fillin_answers(src) != want]
    report("fillin 答案解析（V6）", not bad, str(bad))


def t_config_parser():
    """V10：引号内 # 两种解析路径结果一致。"""
    gc = load("gc", "gen_config.py")
    text = 'main_title: "Title # subtitle"\ncolumns: 2\n'
    got = gc.parse_flat_yaml(text)
    ok = got.get("main_title") == "Title # subtitle"
    try:
        import yaml
        ref = {k: str(v) for k, v in yaml.safe_load(text).items()}
        ok = ok and got == ref
    except ImportError:
        pass
    errs = gc.validate({"columns": "0", "orientation": "sideways",
                        "margin_top": "1", "bogus_key": "x"})
    report("配置解析与校验（V10）", ok and len(errs) == 4,
           "got=%r errs=%r" % (got, errs))


def t_assembly_missing_and_dup():
    """V3/V4：缺失切片与重复装配必须失败。"""
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec404.tex"], {})
        r = run("check_numbering.py", d)
        ok1 = r.returncode == 1 and "不存在" in r.stdout
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex", "sec1.tex"], {"sec1.tex": SEC_OK})
        r = run("check_numbering.py", d)
        ok2 = r.returncode == 1 and "重复装配" in r.stdout
    with tempfile.TemporaryDirectory() as d:
        make_project(d, [], {})  # 真空工程允许跳过
        r = run("check_numbering.py", d)
        ok3 = r.returncode == 0
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec404.tex"], {})
        r = run("check_numbering.py", d, "--init")
        ok4 = r.returncode == 0 and "警告" in r.stdout
    report("装配缺失/重复/空工程/--init（V3,V4）",
           ok1 and ok2 and ok3 and ok4)


def t_item_level_checks():
    """逐题答案关联、禁用宏、qid 唯一性。"""
    # 缺 solution 的题必须报错
    sec_bad = SEC_OK.replace("\\begin{solution}\n成立。\n\\end{solution}\n", "")
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_bad})
        r = run("check_numbering.py", d)
        ok1 = r.returncode == 1 and "solution" in r.stdout
    # 切片改写全局计数器 / 版本开关必须报错
    sec_evil = SEC_OK.replace("\\begin{probchain}",
                              "\\setcounter{pdprob}{0}\n\\begin{probchain}")
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_evil})
        r = run("check_numbering.py", d)
        ok2 = r.returncode == 1 and "全局状态" in r.stdout
    # qid 重复必须报错；缺失只警告
    sec_dup = SEC_OK + SEC_OK
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_dup})
        r = run("check_numbering.py", d)
        ok3 = r.returncode == 1 and "qid" in r.stdout
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"],
                     {"sec1.tex": SEC_OK.replace("% qid: t-entry\n", "")})
        r = run("check_numbering.py", d)
        ok4 = r.returncode == 0 and "qid" in r.stdout
    report("逐题答案关联/禁用宏/qid（V5 源级防线）",
           ok1 and ok2 and ok3 and ok4)


def t_visibility_scan():
    """V7/V8：题干区提示判失败；题后区域记警告；单行结构不误报。"""
    # V7：unprompted 题教师内容之后的可见 microknowledge → 警告不静默
    sec_post = SEC_OK.replace(
        "\\begin{solution}\n$2$。\n\\end{solution}",
        "\\begin{solution}\n$2$。\n\\end{solution}\n"
        "\\begin{microknowledge}[补充]\n后续定义。\n\\end{microknowledge}")
    sec_post = sec_post.replace("\\item \\qtype{进入题}",
                                "\\item \\practicemode{unprompted} "
                                "\\qtype{进入题}")
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_post})
        r = run("check_numbering.py", d)
        ok1 = r.returncode == 0 and "教师内容之后" in r.stdout
    # 题干区（solution 之前）的提示标记 → 失败
    sec_stem = sec_post.replace(
        "\\item \\practicemode{unprompted} \\qtype{进入题}",
        "\\item \\practicemode{unprompted} \\qtype{进入题} "
        "\\begin{microknowledge}[提示]\n看这里。\n\\end{microknowledge}")
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_stem})
        r = run("check_numbering.py", d)
        ok2 = r.returncode == 1 and "提示标记" in r.stdout
    # V8：同一行开启题链、标记模式并闭合，不误报“题块之外”
    sec_line = ("\\section*{S}\n"
                "\\begin{probchain}\n% qid: one\n"
                "\\item \\practicemode{guided} Q\n\\ansspace{1cm}\n"
                "\\begin{solution}A\\end{solution}\n"
                "\\begin{teacherNote}N\\end{teacherNote}\n"
                "\\end{probchain}\n")
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": sec_line})
        r = run("check_numbering.py", d)
        ok3 = r.returncode == 0
    report("可见性扫描与单行结构（V7,V8）", ok1 and ok2 and ok3,
           "stem_ok=%s post_ok=%s line_ok=%s" % (ok2, ok1, ok3))


def t_second_pass_failure():
    """V2：第二遍编译失败不得继承第一遍成功状态。"""
    from unittest import mock
    b = load("build", "build.py")
    with tempfile.TemporaryDirectory() as d:
        for t in ("student.tex",):
            open(os.path.join(d, t), "w").write("x")
        calls = {"n": 0}

        def fake_run(cmd, **kw):
            calls["n"] += 1
            if calls["n"] == 1:
                open(os.path.join(d, "student.pdf"), "w").write("p")
                open(os.path.join(d, "student.log"), "w").write(
                    "[problem-driven] SUMMARY solution=1, "
                    "teacherNote=1, fillin=0\n[problem-driven] 学生版已剥离\n")
                return subprocess.CompletedProcess(cmd, 0, "ok")
            return subprocess.CompletedProcess(cmd, 1, "! boom")

        class A:
            max_retry = 0
            timeout = 60
        with mock.patch.object(b.subprocess, "run", fake_run):
            ok, _ = b.compile_target(d, "student", A())
    report("第二遍失败判失败（V2）", not ok)


def t_multicol_warning_scan():
    """V1 门禁：multicol 收到 1 栏的自动改版警告必须判失败。"""
    b = load("build2", "build.py")

    class A:
        allow_mdframed_breaks = False
        max_overfull_pt = 10.0
        max_underfull_student = None
        max_underfull_teacher = 3
        strict = False
    log = ("Package multicol Warning: Using `1' columns doesn't seem a "
           "good idea.\n I therefore use two columns instead on input "
           "line 20.\n")
    errors, _ = b.scan_log(log, "teacher", A())
    report("multicol 1 栏告警判失败（V1 门禁）", bool(errors))


def t_missing_summary_evidence():
    """V9：日志/SUMMARY 证据缺失默认返回 2，--diagnostic 明示跳过。"""
    with tempfile.TemporaryDirectory() as d:
        make_project(d, ["sec1.tex"], {"sec1.tex": SEC_OK})
        # 手工制造最小可读 PDF（无内容页），不生成日志
        for name in ("student.pdf", "teacher.pdf"):
            with open(os.path.join(d, name), "wb") as f:
                f.write(MINIMAL_PDF)
        if not shutil.which("pdftotext"):
            skip("证据缺失处理（V9）", "无 pdftotext")
            return
        r = run("compare_versions.py", d)
        ok1 = r.returncode == 2 and "证据缺失" in r.stdout
        r2 = run("compare_versions.py", d, "--diagnostic")
        ok2 = r2.returncode in (0, 1) and "已跳过" in r2.stdout
        report("证据缺失不得谎报通过（V9）", ok1 and ok2,
               "rc=%s/%s" % (r.returncode, r2.returncode))


# 最小可读 PDF（单空白页，poppler 可重构 xref）
MINIMAL_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n")


# ------------------------------------------------------- B. 真实编译用例

def t_real_build_dialogue():
    """对话层真实编译：含两种对话块的 section 与无对话的旧 section 混合装配。"""
    if not (shutil.which("xelatex") and shutil.which("pdftotext")):
        skip("真实构建对话层工程", "缺少 xelatex 或 pdftotext")
        return
    import re as _re
    with tempfile.TemporaryDirectory() as d:
        sec2_old = SEC_OK.replace("第一节", "第二节") \
            .replace("t-entry", "t2-entry").replace("t-identify", "t2-identify")
        make_project(d, ["sec1.tex", "sec2.tex"],
                     {"sec1.tex": SEC_DLG, "sec2.tex": sec2_old})
        # 分节逐步改造：只对 sec1 启用对话层
        p = os.path.join(d, "config.yaml")
        with open(p, encoding="utf-8") as f:
            c = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(c.replace("dialogue_enabled: true",
                              "dialogue_enabled: sec1"))
        r = run("gen_config.py", "--project", d)
        assert r.returncode == 0, r.stdout + r.stderr
        with open(os.path.join(d, "coverage-map.md"), "w",
                  encoding="utf-8") as f:
            f.write(COVERAGE_DLG)
        r = run("check_numbering.py", d)
        ok = r.returncode == 0
        r = run("check_dialogue.py", d)
        ok = ok and r.returncode == 0
        r = run("build.py", d)
        ok = ok and r.returncode == 0
        if not ok:
            report("真实构建对话层工程", False, (r.stdout or "")[-1500:])
            return
        r = run("compare_versions.py", d)
        ok2 = r.returncode == 0
        cv = load("cv_dlg", "compare_versions.py")
        stu = "\n".join(cv.pdf_pages_text(os.path.join(d, "student.pdf")))
        tea = "\n".join(cv.pdf_pages_text(os.path.join(d, "teacher.pdf")))
        # 本环境 poppler 对 CJK 文本抽取不可靠（既有工程同样如此），
        # 故可见性断言使用 ASCII 标记；双栏换行问题用去空白规避
        stu_c = _re.sub(r"\s+", "", stu)
        tea_c = _re.sub(r"\s+", "", tea)
        # 学生版：可见提问与任务，不见 \dlgteacher 秘句
        ok3 = "SECTASKMARK" in stu_c and "ENTRYQMARK" in stu_c
        ok4 = "DLGSECRET" not in stu_c
        ok5 = "DLGSECRET" in tea_c
        # 旧 section（无对话块）行为不变：题号连续 1..3（sec1 一题 + sec2 两题）
        nums = _re.findall(r"(?m)^\s*(\d+)\.", stu)
        ok6 = sorted(nums) == ["1", "2", "3"]
        # dialogue_student_reveal: full 时学生版应显示 \dlgteacher 内容
        with open(p, encoding="utf-8") as f:
            c = f.read()
        with open(p, "w", encoding="utf-8") as f:
            f.write(c.replace("dialogue_student_reveal: prompt_only",
                              "dialogue_student_reveal: full"))
        r = run("gen_config.py", "--project", d)
        ok7 = r.returncode == 0
        r = run("build.py", d)
        ok7 = ok7 and r.returncode == 0
        stu2 = "\n".join(cv.pdf_pages_text(os.path.join(d, "student.pdf")))
        ok7 = ok7 and "DLGSECRET" in _re.sub(r"\s+", "", stu2)
        report("真实构建对话层工程",
               ok and ok2 and ok3 and ok4 and ok5 and ok6 and ok7,
               "gates=%s compare=%s stu_dlg=%s hide=%s show=%s nums=%r full=%s"
               % (ok, ok2, ok3, ok4, ok5, nums, ok7))


def t_real_build():
    if not (shutil.which("xelatex") and shutil.which("pdftotext")):
        skip("真实构建最小工程（V1/V5 链路）", "缺少 xelatex 或 pdftotext")
        return
    with tempfile.TemporaryDirectory() as d:
        secs = {"sec1.tex": SEC_OK,
                "sec2.tex": SEC_OK.replace("第一节", "第二节")
                .replace("t-entry", "t2-entry").replace("t-identify",
                                                        "t2-identify")}
        make_project(d, ["sec1.tex", "sec2.tex"], secs)
        r = run("check_numbering.py", d)
        ok = r.returncode == 0
        r = run("build.py", d)
        ok = ok and r.returncode == 0
        if not ok:
            report("真实构建最小工程（V1/V5 链路）", False,
                   (r.stdout or "")[-1500:])
            return
        with open(os.path.join(d, "teacher.log"),
                  encoding="utf-8", errors="replace") as f:
            tlog = f.read()
        # V1：教师版必须是真正单栏，不得出现 multicol 自动改版警告
        ok1 = "doesn't seem a good idea" not in tlog
        r = run("compare_versions.py", d)
        ok2 = r.returncode == 0
        # 题号连续且无重复：学生版文本中题号 1..4 各出现一次
        cv = load("cv2", "compare_versions.py")
        pages = cv.pdf_pages_text(os.path.join(d, "student.pdf"))
        text = "\n".join(pages)
        nums = re.findall(r"(?m)^\s*(\d+)\.", text)
        ok3 = sorted(nums) == ["1", "2", "3", "4"]
        report("真实构建最小工程（V1/V5 链路）", ok1 and ok2 and ok3,
               "single_col=%s compare=%s numbering=%s nums=%r"
               % (ok1, ok2, ok3, nums))


def main():
    t_fillin_parser()
    t_config_parser()
    t_assembly_missing_and_dup()
    t_item_level_checks()
    t_visibility_scan()
    t_second_pass_failure()
    t_multicol_warning_scan()
    t_missing_summary_evidence()
    t_dialogue_checks()
    t_real_build_dialogue()
    t_real_build()
    print("=" * 60)
    if _failures:
        print("失败 %d 项: %s" % (len(_failures), ", ".join(_failures)))
        return 1
    print("全部通过（跳过 %d 项: %s）"
          % (len(_skips), ", ".join(_skips) or "无"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
