#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""test_runtime.py — F05–F08 运行时证据链回归测试（unittest + 临时目录）

覆盖 T01–T16；只使用 skills4/templates 与合成材料构造临时工程，
不依赖也不触碰真实 self/ / self-repair/。

T14（构建过程中输入变化）说明：真实 xelatex 编译太慢，这里用 monkeypatch
替换 build.compile_target 为轻量替身（写出假 PDF/日志并在“编译期间”改动
一个受审输入文件），验证的是 build.py 的 编译前后摘要比对 逻辑本身，
不验证真实编译器行为（真实编译链路归 test_templates.py）。

运行: python skills4/scripts/test_runtime.py
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import evidence  # noqa: E402
import gen_config  # noqa: E402
import deliver  # noqa: E402
import build  # noqa: E402

TEMPLATES = os.path.join(HERE, "..", "templates")
QIDS = ["sec1-entry", "sec2-entry"]

SEC1 = r"""\section*{I 第一节}
\begin{probchain}
% qid: sec1-entry
% card: CARD-01
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

SEC2 = r"""\section*{II 第二节}
\begin{probchain}
% qid: sec2-entry
\item \qtype{进入题} 判断 $2+2=4$。\fillin[成立]{15mm}
\ansspace{1cm}
\begin{solution}
成立。
\end{solution}
\begin{teacherNote}
确认判据。
\end{teacherNote}
\end{probchain}
"""

MAIN = (r"\input{header.tex}" + "\n\n\\begin{document}\n\\begin{center}\n"
        r"  {\Huge \textbf{\pdMainTitle}}" + "\n\\end{center}\n"
        r"\raggedcolumns" + "\n\\pdBeginColumns\n\n"
        r"\input{sec1.tex}" + "\n" + r"\input{sec2.tex}" + "\n\n"
        r"\input{footer.tex}" + "\n")

PACK1 = """# 第 1 节批准材料包

- **卡片 ID**: `CARD-01` | **对应需求**: `REQ-01` | **状态**: `approved`
  - **材料类型**: `SELF-CONTAINED`
  - **核验结论**: 自构例，复算过程：1+1=2，核对无误。
"""

BRIEF = ("# research-brief\n\n| 需求ID | 节点 |\n|---|---|\n"
         "| REQ-01 | SRC-01-01 |\n")
COVERAGE = ("# coverage-map\n\n| qid | 来源 |\n|---|---|\n"
            "| sec1-entry | CARD-01 |\n| sec2-entry | SRC-02 |\n")


def sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def make_project(d):
    """最小合成工程：两个有效切片、一张批准卡、fake PDF。"""
    for f in ("header.tex", "footer.tex", "config.yaml",
              "student.tex", "teacher.tex"):
        shutil.copy(os.path.join(TEMPLATES, f), os.path.join(d, f))
    # 本测试不用对话层
    cp = os.path.join(d, "config.yaml")
    with open(cp, encoding="utf-8") as f:
        c = f.read()
    open(cp, "w", encoding="utf-8", newline="").write(
        c.replace("dialogue_enabled: true", "dialogue_enabled: false"))
    open(os.path.join(d, "main.tex"), "w",
         encoding="utf-8", newline="").write(MAIN)
    open(os.path.join(d, "sec1.tex"), "w",
         encoding="utf-8", newline="").write(SEC1)
    open(os.path.join(d, "sec2.tex"), "w",
         encoding="utf-8", newline="").write(SEC2)
    open(os.path.join(d, "material-pack-sec1.md"), "w",
         encoding="utf-8").write(PACK1)
    open(os.path.join(d, "research-brief.md"), "w",
         encoding="utf-8").write(BRIEF)
    open(os.path.join(d, "coverage-map.md"), "w",
         encoding="utf-8").write(COVERAGE)
    open(os.path.join(d, "pic1.png"), "wb").write(b"\x89PNG-fake-1")
    assert gen_config.generate(d) == 0
    for f in ("student.pdf", "teacher.pdf"):
        open(os.path.join(d, f), "wb").write(b"%PDF-fake-" + f.encode())
    for sub in ("reports", "acceptance"):
        os.makedirs(os.path.join(d, ".pd", sub), exist_ok=True)
    return d


def digest_of(d):
    return evidence.content_digest(evidence.collect_inputs(d))


def run_cli(script, pdir, *argv):
    return subprocess.run(
        [sys.executable, os.path.join(HERE, script), pdir] + list(argv),
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def seed_reports(d, compare_status="pass"):
    """按当前实际状态预置四份有效报告（供 --skip-checks 验证路径）。"""
    digest = digest_of(d)
    pdf_sha = {n: sha(os.path.join(d, n + ".pdf"))
               for n in ("student", "teacher")}
    tools = {"check_numbering.json": ("check_numbering.py", "2.1"),
             "check_dialogue.json": ("check_dialogue.py", "1.1"),
             "build.json": ("build.py", "2.1"),
             "compare.json": ("compare_versions.py", "2.2")}
    cmp_issues = []
    for fn, (tool, ver) in tools.items():
        rep = {"schema_version": 2, "tool": tool, "tool_version": ver,
               "scope": {}, "input_digest": digest,
               "pdf_sha256": (pdf_sha if tool in ("build.py",
                                                  "compare_versions.py")
                              else None),
               "status": "pass", "issues": [], "evidence": {}}
        if fn == "compare.json" and compare_status == "review":
            cmp_issues = [
                {"severity": "review", "issue_id": "CMP-aaa111",
                 "kind": "fillin-answer-leak-suspect", "qid": "sec1-entry",
                 "location": {"page": 1, "context": "..."}, "message": "m1"}]
            rep["status"] = "review"
            rep["issues"] = cmp_issues
        with open(os.path.join(d, ".pd", "reports", fn), "w",
                   encoding="utf-8") as f:
            json.dump(rep, f, ensure_ascii=False)
    return digest, pdf_sha, cmp_issues


def write_acceptance(d, qids, conclusion="PASS", issues=None, digest=None):
    digest = digest or digest_of(d)
    open(os.path.join(d, ".pd", "acceptance", "chapter.md"),
         "w", encoding="utf-8").write(
        "scope: chapter\nconclusion: %s\ndigest: %s\n" % (conclusion, digest))
    rec = {"schema_version": 2, "scope": "chapter", "reviewed_qids": qids,
           "content_digest": digest,
           "student_pdf_sha256": sha(os.path.join(d, "student.pdf")),
           "conclusion": conclusion, "reviewer_role": "独立验收（测试替身）",
           "stage1_record": "s1", "stage2_record": "s2", "issues": issues or []}
    with open(os.path.join(d, ".pd", "acceptance", "chapter.json"),
             "w", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False)


def write_run(d):
    with open(os.path.join(d, ".pd", "run.json"), "w",
              encoding="utf-8") as f:
        json.dump({"schema_version": 2, "run_id": "t",
                   "slices": ["sec1", "sec2"], "digests": {}, "tasks": {},
                   "required_acceptance_scopes": {"chapter": QIDS}}, f,
                  ensure_ascii=False)


def write_materials(d):
    evidence.write_report(os.path.join(d, ".pd", "materials.json"),
                          evidence.build_materials_index(d))


def write_notes(d, cmp_issues, pdf_sha256=None):
    open(os.path.join(d, ".pd", "review-notes.md"),
         "w", encoding="utf-8").write("# 复核\nx\n")
    notes = {"schema_version": 2,
             "compare_report_sha256": sha(os.path.join(
                 d, ".pd", "reports", "compare.json")),
             "input_digest": digest_of(d),
             "pdf_sha256": pdf_sha256 or {
                 n: sha(os.path.join(d, n + ".pdf"))
                 for n in ("student", "teacher")},
             "decisions": [{"issue_id": i["issue_id"],
                            "judgment": "合法引导词",
                            "evidence": "渲染页核对"} for i in cmp_issues]}
    with open(os.path.join(d, ".pd", "review-notes.json"), "w",
             encoding="utf-8") as f:
        json.dump(notes, f, ensure_ascii=False)


def seed_all(d, compare_status="pass"):
    """完整有效证据链（可发布状态）。"""
    _dg, _ps, cmp_issues = seed_reports(d, compare_status)
    write_run(d)
    write_acceptance(d, QIDS)
    write_materials(d)
    if compare_status == "review":
        write_notes(d, cmp_issues)
    return cmp_issues


class T01_T04_Digest(unittest.TestCase):
    """F05 证据摘要语义。"""

    def test_t01_same_input_same_digest(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            self.assertEqual(digest_of(d), digest_of(d))

    def test_t02_swap_input_order_changes_digest(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            base = digest_of(d)
            mp = os.path.join(d, "main.tex")
            raw = open(mp, "rb").read()
            t = raw.decode("utf-8")
            open(mp, "w", encoding="utf-8", newline="").write(
                t.replace("\\input{sec1.tex}\n\\input{sec2.tex}",
                          "\\input{sec2.tex}\n\\input{sec1.tex}"))
            new = digest_of(d)
            self.assertNotEqual(base, new)
            # 旧验收（绑定 base 摘要）不再匹配当前内容
            rec = {"schema_version": 2, "scope": "chapter",
                   "reviewed_qids": QIDS, "content_digest": base,
                   "student_pdf_sha256": None, "conclusion": "PASS",
                   "reviewer_role": "t", "stage1_record": "s1",
                   "stage2_record": "s2", "issues": []}
            problems = evidence.validate_acceptance_json(rec,
                                                         current_digest=new)
            self.assertTrue(any("摘要" in p for p in problems))

    def test_t03_config_change_with_fake_mtime(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            base = digest_of(d)
            cp = os.path.join(d, "config.yaml")
            b0 = open(cp, "rb").read()
            mt = os.path.getmtime(cp)
            open(cp, "ab").write(b"main_title: changed\n")
            os.utime(cp, (mt, mt))  # 伪装 mtime
            new = digest_of(d)
            self.assertEqual(os.path.getmtime(cp), mt)
            self.assertNotEqual(base, new)
            # 旧检查报告（绑定旧摘要）失效
            rep = {"schema_version": 2, "tool": "check_numbering.py",
                   "tool_version": "2.1", "input_digest": base,
                   "pdf_sha256": None, "status": "pass",
                   "issues": [], "evidence": {}}
            blockers = []
            deliver.verify_report("check_numbering.py", "check_numbering.json",
                                  rep, d, new, {}, blockers)
            self.assertTrue(any("输入摘要" in b for b in blockers))
            open(cp, "wb").write(b0)

    def test_t04_referenced_image_change(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            # sec1 实际引用图片
            with open(os.path.join(d, "sec1.tex"), "a",
                      encoding="utf-8", newline="") as f:
                f.write("\\includegraphics{pic1.png}\n")
            base = digest_of(d)
            open(os.path.join(d, "pic1.png"), "wb").write(b"\x89PNG-CHANGED")
            self.assertNotEqual(base, digest_of(d))


class T05_T07_Pdstate(unittest.TestCase):
    """F06 attempt 状态机（CLI 入口实测）。"""

    def _start_with_candidate(self, d, sec, body):
        self.assertEqual(run_cli("pdstate.py", d, "mark", sec,
                                 "ready").returncode, 0)
        self.assertEqual(run_cli("pdstate.py", d, "start", sec).returncode, 0)
        run_json = json.load(open(os.path.join(d, ".pd", "run.json"),
                                  encoding="utf-8"))
        aid = run_json["tasks"][sec]["current_attempt"]
        adir = os.path.join(d, ".pd", "candidates", sec,
                            "attempt-%04d" % aid)
        tj = json.load(open(os.path.join(adir, "task.json"),
                            encoding="utf-8"))
        open(os.path.join(adir, tj["allowed_output"]), "w",
             encoding="utf-8", newline="").write(body)
        cp = os.path.join(adir, tj["allowed_output"])
        with open(os.path.join(adir, "result.json"), "w",
                  encoding="utf-8") as f:
            json.dump({"schema_version": 2, "run_id": tj["run_id"],
                       "task_id": sec, "attempt_id": aid,
                       "input_digest": tj["input_digest"],
                       "output": tj["allowed_output"],
                       "output_sha256": sha(cp)}, f, ensure_ascii=False)
        return aid

    def test_t05_stale_submit_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            self.assertEqual(run_cli("pdstate.py", d, "init").returncode, 0)
            # 第一轮正常晋升 v1
            self._start_with_candidate(d, "sec1", SEC1)
            r = run_cli("pdstate.py", d, "submit", "sec1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            official = os.path.join(d, "sec1.tex")
            hash_v1 = sha(official)
            # 第二轮：running 期间输入改变 → stale → 提交旧候选被拒
            self.assertEqual(run_cli("pdstate.py", d, "mark", "sec1",
                                     "blocked").returncode, 0)
            self._start_with_candidate(d, "sec1", SEC1 + "% v2\n")
            with open(os.path.join(d, "material-pack-sec1.md"), "a",
                      encoding="utf-8") as f:
                f.write("- 追加一张卡\n")
            r = run_cli("pdstate.py", d, "invalidate")
            self.assertEqual(r.returncode, 0)
            r = run_cli("pdstate.py", d, "submit", "sec1")
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(sha(official), hash_v1)  # 正式文件未改变

    def test_t06_late_old_attempt_cannot_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            self.assertEqual(run_cli("pdstate.py", d, "init").returncode, 0)
            # attempt-1 制作 v1 但先不提交；输入变化使其失效
            self._start_with_candidate(d, "sec1", SEC1)
            with open(os.path.join(d, "coverage-map.md"), "a",
                      encoding="utf-8") as f:
                f.write("| extra | row |\n")
            run_cli("pdstate.py", d, "invalidate")  # sec1 → stale
            self.assertNotEqual(
                run_cli("pdstate.py", d, "submit", "sec1").returncode, 0)
            # 新 attempt 提交 v2 成功
            self._start_with_candidate(d, "sec1", SEC1 + "% v2-new\n")
            r = run_cli("pdstate.py", d, "submit", "sec1")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            hash_v2 = sha(os.path.join(d, "sec1.tex"))
            # 旧 attempt 迟到：current_attempt 已是新 attempt 且任务非 running
            r = run_cli("pdstate.py", d, "submit", "sec1")
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(sha(os.path.join(d, "sec1.tex")), hash_v2)

    def test_t07_planned_mark_accepted_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            self.assertEqual(run_cli("pdstate.py", d, "init").returncode, 0)
            r = run_cli("pdstate.py", d, "mark", "sec2", "accepted")
            self.assertNotEqual(r.returncode, 0)


class T08_T12_Records(unittest.TestCase):
    """F07 注释解析 / 材料链 / 验收与复核记录。"""

    def test_t08_card_comment_parsing_both_forms(self):
        standalone = "% card: CARD-10\n"
        combined = "% qid: sec4-entry | 题型: 进入题 | card: CARD-10\n"
        e1 = evidence.scan_tex_markers(standalone)
        e2 = evidence.scan_tex_markers(combined)
        self.assertEqual(e1[0]["card"], "CARD-10")
        self.assertEqual(e2[0]["card"], "CARD-10")
        self.assertEqual(e2[0]["qid"], "sec4-entry")

    def test_t09_material_chain_rejections(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            secs = ["sec1.tex", "sec2.tex"]
            good = evidence.build_materials_index(d)
            self.assertEqual(
                evidence.validate_material_chain(d, good, secs), [])
            # unapproved 卡片被拒（不得子串误匹配）
            bad = json.loads(json.dumps(good))
            bad["cards"][0]["status"] = "unapproved"
            ps = evidence.validate_material_chain(d, bad, secs)
            self.assertTrue(any("approved" in p for p in ps))
            # 缺包：删除材料包 → 批准记录核对失败
            os.remove(os.path.join(d, "material-pack-sec1.md"))
            ps = evidence.validate_material_chain(d, good, secs)
            self.assertTrue(any("批准记录" in p for p in ps))
            # 缺 requirement：索引指向 REQ-99（research-brief 中不存在）
            open(os.path.join(d, "material-pack-sec1.md"), "w",
                 encoding="utf-8").write(PACK1)
            bad2 = json.loads(json.dumps(good))
            bad2["cards"][0]["requirement_id"] = "REQ-99"
            ps = evidence.validate_material_chain(d, bad2, secs)
            self.assertTrue(any("REQ-99" in p for p in ps))

    def test_t10_partial_qid_coverage_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            seed_all(d)
            write_acceptance(d, QIDS[:-1])  # 2 题计划只审 1 题
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 1)
            self.assertIn("未覆盖全部必需 qid", r.stdout)

    def test_t11_open_issue_with_pass_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            seed_all(d)
            write_acceptance(d, QIDS, issues=[{
                "id": "A-1", "qid": "sec1-entry", "part": "(a)",
                "code": "answer-leak", "evidence": "第 1 页",
                "status": "open", "resolution": "", "verified_digest": ""}])
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 1)
            self.assertIn("open", r.stdout)

    def test_t12_old_review_notes_rejected_after_pdf_change(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            cmp_issues = seed_all(d, compare_status="review")
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 0, r.stdout)  # 先确认可发布
            # 修改 PDF；报告重新绑定新 PDF，但 review-notes 仍绑旧 PDF
            open(os.path.join(d, "student.pdf"), "wb").write(b"%PDF-NEW")
            digest = digest_of(d)
            for fn in ("build.json", "compare.json"):
                p = os.path.join(d, ".pd", "reports", fn)
                rep = json.load(open(p, encoding="utf-8"))
                rep["pdf_sha256"] = {n: sha(os.path.join(d, n + ".pdf"))
                                     for n in ("student", "teacher")}
                rep["input_digest"] = digest
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(rep, f, ensure_ascii=False)
            # compare.json 文件内容变了 → 同时更新 notes 的报告哈希，
            # 只保留旧 PDF 哈希绑定（单独检验 PDF 绑定失效）
            np = os.path.join(d, ".pd", "review-notes.json")
            notes = json.load(open(np, encoding="utf-8"))
            notes["compare_report_sha256"] = sha(os.path.join(
                d, ".pd", "reports", "compare.json"))
            notes["input_digest"] = digest
            with open(np, "w", encoding="utf-8") as f:
                json.dump(notes, f, ensure_ascii=False)
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 1)
            self.assertIn("student.pdf", r.stdout)
            self.assertTrue(cmp_issues)  # 疑似项确实存在


class T13_T16_Release(unittest.TestCase):
    """F08 交付主流程。"""

    def test_t13_failed_check_distrusts_stale_pass_report(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            seed_all(d)  # 磁盘留有旧 pass 报告
            # 移除 student.tex / teacher.tex / PDF → build/compare 快速失败
            for f in ("student.tex", "teacher.tex",
                      "student.pdf", "teacher.pdf"):
                os.remove(os.path.join(d, f))
            r = run_cli("deliver.py", d)  # 正常模式现场重跑
            self.assertNotEqual(r.returncode, 0)
            rep = json.load(open(os.path.join(
                d, ".pd", "reports", "build.json"), encoding="utf-8"))
            self.assertNotEqual(rep.get("status"), "pass")  # 旧 pass 被取代
            self.assertFalse(os.path.exists(os.path.join(d, "release")))

    def test_t14_input_change_during_build_no_pass(self):
        # 轻量替身：monkeypatch compile_target，在“编译期间”改动一个受审
        # 输入文件，验证 build.py 的编译前后摘要比对（不跑真实 xelatex）。
        from unittest import mock

        class A:
            targets = ["student", "teacher"]
            json = None

        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            old_argv = sys.argv
            sys.argv = ["build.py", d, "--json",
                        os.path.join(d, "build.json")]

            def fake_compile(workdir, target, args, report=None):
                # 模拟编译期间输入被改动
                with open(os.path.join(workdir, "sec1.tex"), "a",
                          encoding="utf-8", newline="") as f:
                    f.write("% changed during build\n")
                for ext in (".pdf", ".log"):
                    open(os.path.join(workdir, target + ext), "w",
                         encoding="utf-8").write("fake")
                return True, {"solution": 1, "teacherNote": 1, "fillin": 0}

            try:
                with mock.patch.object(build, "compile_target",
                                       fake_compile):
                    rc = build.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc, 1)  # 不得产出有效 pass
            rep = json.load(open(os.path.join(d, "build.json"),
                                 encoding="utf-8"))
            self.assertNotEqual(rep["status"], "pass")
            self.assertTrue(any("输入" in (i.get("message") or "")
                                for i in rep["issues"]))

    def test_t15_failed_copy_preserves_old_release(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            seed_all(d)
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 0, r.stdout)
            old = {f: sha(os.path.join(d, "release", f))
                   for f in ("student.pdf", "teacher.pdf", "manifest.json")}

            def boom(*a, **k):
                raise OSError("模拟目标文件占用/权限错误")

            old_argv = sys.argv
            sys.argv = ["deliver.py", d, "--skip-checks"]
            try:
                with mock.patch.object(deliver.shutil, "copy2", boom):
                    rc = deliver.main()
            finally:
                sys.argv = old_argv
            self.assertEqual(rc, 2)
            for f, h in old.items():  # 旧版完整保留
                self.assertEqual(sha(os.path.join(d, "release", f)), h)
            self.assertFalse(os.path.exists(
                os.path.join(d, ".release-staging")))

    def test_t16_full_current_evidence_releases(self):
        with tempfile.TemporaryDirectory() as d:
            make_project(d)
            seed_all(d)
            r = run_cli("deliver.py", d, "--skip-checks")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            m = json.load(open(os.path.join(d, "release", "manifest.json"),
                               encoding="utf-8"))
            self.assertEqual(m["schema_version"], 2)
            self.assertEqual(m["sections"], ["sec1.tex", "sec2.tex"])
            self.assertEqual(m["input_digest"], digest_of(d))
            for n in ("student", "teacher"):
                self.assertEqual(m["pdf_sha256"][n],
                                 sha(os.path.join(d, "release",
                                                  n + ".pdf")))
            self.assertTrue(m["tool_versions"])
            eh = m["evidence"]["evidence_hashes"]
            self.assertEqual(eh["reports"]["build.json"],
                             sha(os.path.join(d, ".pd", "reports",
                                              "build.json")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
