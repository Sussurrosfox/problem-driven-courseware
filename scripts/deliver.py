#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "2.0"
r"""
deliver.py — 交付汇总门禁（F08：只有当前完整证据能生成新的 release）

技术检查与教学验收互不替代。只接受 schema_version=2 的门禁证据；旧
Markdown 与旧 JSON 可保留为历史，但缺少字段时提示重建/复验，不自动补
摘要、不把历史 PASS 转成当前 PASS。

正常模式按顺序执行（任何子进程异常或非零退出都停止放行；报告只信本次
调用产出的新文件，调用前删除旧报告，失败即不信任旧报告）：
  1. gen_config.generate  确定性生成配置（内容相同不重写）；
  2. check_numbering.py → 3. check_dialogue.py → 4. build.py
  → 5. compare_versions.py，各自 --json 落盘 .pd/reports/；
  6. 核对教学验收（acceptance/<scope>.json + run.json 的
     required_acceptance_scopes）、材料链（materials.json）与疑似项处置
     （review-notes.json）；未完成教学验收时返回“待验收”，保留已生成的
     审读草稿（.pd/review/），不触碰 release。

--skip-checks 复用已完成的检查，但仍逐项验证：schema/工具版本、报告
input_digest 与当前输入摘要一致、报告绑定的 PDF 哈希与实际产物一致、
报告记录的日志/PDF 文本证据哈希与实际文件一致。跳过执行不等于跳过验证，
不再使用 mtime 作为通过依据。

放行门槛：编号/对话/构建必须 pass；compare 可以是 pass，或是所有疑似项
都有当前有效处置记录的 review（经 review-notes.json 哈希绑定核对）。
required scopes、qid 覆盖、教学问题处置、材料引用全部满足才发布；发布前
重新核对输入与 PDF 哈希。发布先写临时目录，全部成功后原子切换 release；
失败时保留上一版完整 release。

用法: python deliver.py <project> [--skip-checks]
退出码: 0=可交付（已原子切换 release）, 1=门禁未通过或待验收,
       2=缺少依赖或输入。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPTS)
import evidence  # noqa: E402
import gen_config  # noqa: E402

EXPECTED_SCHEMA = 2
CHECKS = [("check_numbering.py", "check_numbering.json"),
          ("check_dialogue.py", "check_dialogue.json"),
          ("build.py", "build.json"),
          ("compare_versions.py", "compare.json")]
PDF_READERS = ("build.py", "compare_versions.py")


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def run_check(script, pdir, report_path):
    """执行一个检查脚本；只信本次调用产出的新报告（先删除旧报告）。"""
    if os.path.exists(report_path):
        os.remove(report_path)  # 调用失败时不得回读遗留的旧 pass 文件
    try:
        return subprocess.run([sys.executable,
                               os.path.join(SCRIPTS, script),
                               pdir, "--json", report_path],
                              capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        return subprocess.CompletedProcess(script, 2, "", str(e))


def pdf_text_sha(pdf):
    """与 compare_versions.py 相同口径的 PDF 抽取文本哈希。"""
    r = subprocess.run(["pdftotext", pdf, "-"], capture_output=True)
    if r.returncode != 0:
        return None
    text = r.stdout.decode("utf-8", errors="replace")
    return hashlib.sha256("\n".join(text.split("\x0c"))
                          .encode("utf-8")).hexdigest()


def verify_report(script, fname, rep, pdir, digest, pdf_sha, blockers):
    """验证单份报告确为当前输入/当前构建的证据（skip 与正常模式同口径）。"""
    if rep is None:
        blockers.append("缺少或无法解析报告 %s（先运行对应检查）" % fname)
        return
    if rep.get("schema_version") != EXPECTED_SCHEMA:
        blockers.append("报告 %s 的 schema_version=%s，只接受 %d；旧证据属"
                        "历史，请重建（重跑 %s）"
                        % (fname, rep.get("schema_version"), EXPECTED_SCHEMA,
                           script))
        return  # schema 不符时其余字段不可信
    if rep.get("tool") != script:
        blockers.append("报告 %s 的 tool 字段为 %r，应为 %s（张冠李戴）"
                        % (fname, rep.get("tool"), script))
    if not rep.get("tool_version"):
        blockers.append("报告 %s 缺少 tool_version 字段" % fname)
    if rep.get("input_digest") != digest:
        blockers.append("报告 %s 绑定的输入摘要与当前摘要不一致，证据对应"
                        "旧输入；请重跑 %s" % (fname, script))
    bound = rep.get("pdf_sha256")
    if script in PDF_READERS:
        if not isinstance(bound, dict):
            blockers.append("报告 %s 未绑定 PDF 哈希（pdf_sha256）" % fname)
        else:
            for n in ("student", "teacher"):
                if bound.get(n) != pdf_sha.get(n):
                    blockers.append("报告 %s 绑定的 %s.pdf 哈希与当前产物不"
                                    "一致，证据对应旧构建" % (fname, n))
    elif bound is not None:
        blockers.append("报告 %s 不应读取 PDF，但 pdf_sha256 非 null" % fname)
    # 日志证据哈希核对新鲜度
    for t, h in ((rep.get("evidence") or {}).get("log_sha256") or {}).items():
        if h is not None and h != evidence.sha256_file(
                os.path.join(pdir, t + ".log")):
            blockers.append("报告 %s 记录的 %s.log 哈希与实际日志不一致"
                            "（日志已被替换或重编译）" % (fname, t))
    # PDF 文本证据哈希核对（compare 读取过抽取文本）
    texts = (rep.get("evidence") or {}).get("pdf_text_sha256") or {}
    for t, h in texts.items():
        pdf = os.path.join(pdir, t + ".pdf")
        if not os.path.exists(pdf) or not shutil.which("pdftotext"):
            blockers.append("无法验证报告 %s 记录的 %s PDF 文本证据哈希"
                            "（缺 PDF 或 pdftotext）" % (fname, t))
        elif h != pdf_text_sha(pdf):
            blockers.append("报告 %s 记录的 %s.pdf 文本证据哈希与当前抽取"
                            "不一致" % (fname, t))


def atomic_release(pdir, manifest):
    """先写临时目录，全部成功后原子切换 release；失败保留上一版完整
    release（不出现新旧 PDF 混合发布）。"""
    rel = os.path.join(pdir, "release")
    staging = os.path.join(pdir, ".release-staging")
    backup = os.path.join(pdir, ".release-prev")
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)
    try:
        for name in ("student.pdf", "teacher.pdf"):
            shutil.copy2(os.path.join(pdir, name),
                         os.path.join(staging, name))
        with open(os.path.join(staging, "manifest.json"), "w",
                  encoding="utf-8") as f:
            json.dump(manifest, f, ensure_ascii=False, indent=2)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise  # 尚未触碰旧 release
    if os.path.isdir(rel):
        if os.path.exists(backup):
            shutil.rmtree(backup)
        os.rename(rel, backup)
    try:
        os.rename(staging, rel)
    except Exception:
        if os.path.isdir(backup):
            os.rename(backup, rel)  # 回滚：恢复上一版完整 release
        raise
    if os.path.isdir(backup):
        shutil.rmtree(backup)
    return rel


def main():
    ap = argparse.ArgumentParser(description="交付汇总门禁")
    ap.add_argument("project")
    ap.add_argument("--skip-checks", action="store_true",
                    help="复用 .pd/reports/ 已有报告（仍逐项验证版本/摘要/"
                         "PDF/日志/文本证据哈希；跳过执行不等于跳过验证）")
    args = ap.parse_args()
    pdir = os.path.abspath(args.project)
    if not os.path.isdir(pdir):
        print("[deliver] 项目目录不存在: %s" % pdir)
        return 2

    # ---- 1: 确定性生成配置（内容相同不重写；失败立即返回） ----
    if gen_config.generate(pdir) != 0:
        print("[deliver] 配置生成失败，停止放行。")
        return 2

    # 切片清单取自共享证据模块的装配顺序（保留 main.tex 实际 \input 顺序）
    secs = [f for f in evidence.collect_inputs(pdir)["assembly_order"]
            if re.match(r"sec", os.path.basename(f))]
    if not secs:
        secs = sorted(f for f in os.listdir(pdir)
                      if re.fullmatch(r"sec.*\.tex", f))
    rdir = os.path.join(pdir, ".pd", "reports")
    os.makedirs(rdir, exist_ok=True)
    blockers = []          # 技术/证据类阻断
    accept_blockers = []   # 教学验收类阻断（报“待验收”）

    # ---- 2~5: 技术检查（正常模式现场重跑，只信本次产出的新报告） ----
    reports = {}
    for script, fname in CHECKS:
        rpath = os.path.join(rdir, fname)
        if not args.skip_checks:
            r = run_check(script, pdir, rpath)
            tail = (r.stdout or "").strip().splitlines()
            for line in tail[-3:]:
                print("  [%s] %s" % (script, line))
            if r.returncode != 0 and not os.path.exists(rpath):
                blockers.append("%s 执行失败（退出码 %s：%s），未产出新报告；"
                                "旧报告已不信任" % (script, r.returncode,
                                                    (r.stderr or "").strip()
                                                    [:120]))
                continue
            if r.returncode not in (0, 1):
                blockers.append("%s 子进程异常（退出码 %s），停止放行"
                                % (script, r.returncode))
                continue
        reports[fname] = load_json(rpath)

    # ---- 当前输入摘要与产物哈希（配置已生成后的实际状态） ----
    digest = evidence.content_digest(evidence.collect_inputs(pdir))
    pdf_sha = {n: evidence.sha256_file(os.path.join(pdir, n + ".pdf"))
               for n in ("student", "teacher")}

    # ---- 报告逐项验证（两种模式同口径；跳过执行不等于跳过验证） ----
    for script, fname in CHECKS:
        verify_report(script, fname, reports.get(fname), pdir, digest,
                      pdf_sha, blockers)

    # ---- 放行门槛：编号/对话/构建必须 pass；compare 可为 pass 或有处置
    #      记录的 review（禁止把所有脚本的 review 一概视为通过） ----
    for script, fname in CHECKS[:3]:
        rep = reports.get(fname) or {}
        if rep.get("status") != "pass":
            blockers.append("%s 未通过（status=%s，问题 %d 条）"
                            % (script, rep.get("status"),
                               len(rep.get("issues", []))))
    cmp_rep = reports.get("compare.json") or {}
    cmp_status = cmp_rep.get("status")
    if cmp_status not in ("pass", "review"):
        blockers.append("compare_versions.py 未通过（status=%s）"
                        % cmp_status)

    # ---- 5b: 疑似答案项处置（review-notes.json 哈希绑定核对） ----
    if cmp_status == "review":
        notes = os.path.join(pdir, ".pd", "review-notes.md")
        if not (os.path.exists(notes) and os.path.getsize(notes) > 0):
            blockers.append("compare_versions.py 有疑似答案项待复核，但缺少 "
                            ".pd/review-notes.md 人工复核记录")
        notes_json = load_json(os.path.join(pdir, ".pd",
                                            "review-notes.json"))
        if notes_json is None:
            blockers.append("缺少 .pd/review-notes.json 机器复核记录"
                            "（只有 Markdown 非空不足以放行）")
        elif notes_json.get("schema_version") != EXPECTED_SCHEMA:
            blockers.append("review-notes.json 的 schema_version=%s，只接受 "
                            "%d；请按当前报告重建复核记录"
                            % (notes_json.get("schema_version"),
                               EXPECTED_SCHEMA))
        else:
            cmp_sha = evidence.sha256_file(os.path.join(rdir, "compare.json"))
            for p in evidence.validate_review_notes(
                    notes_json, cmp_rep, cmp_sha, digest, pdf_sha):
                blockers.append(p)

    # ---- 6: 材料批准链（materials.json 机器索引 + 五核对） ----
    used_cards = evidence.card_usages(pdir, secs)
    if used_cards:
        index = load_json(os.path.join(pdir, ".pd", "materials.json"))
        if index is None:
            blockers.append(
                "正文引用卡片 %s，但缺少 .pd/materials.json 机器索引"
                "（可用 python scripts/evidence.py materials-index <project>"
                " --out ... 由材料包生成）" % ", ".join(sorted(used_cards)))
        elif index.get("schema_version") != EXPECTED_SCHEMA:
            blockers.append("materials.json 的 schema_version=%s，只接受 %d；"
                            "请用 materials-index 重新生成"
                            % (index.get("schema_version"), EXPECTED_SCHEMA))
        else:
            for p in evidence.validate_material_chain(pdir, index, secs):
                blockers.append(p)
    # 无卡片引用且计划明确无补充材料时允许空索引（不强制 materials.json）

    # ---- 3+4: 教学验收（acceptance JSON + required scopes；未完成=待验收） ----
    adir = os.path.join(pdir, ".pd", "acceptance")
    run_json = load_json(os.path.join(pdir, ".pd", "run.json")) or {}
    required = run_json.get("required_acceptance_scopes") or {}
    ajsons = {}
    md_only = []
    if os.path.isdir(adir):
        for fn in sorted(os.listdir(adir)):
            if fn.endswith(".json"):
                rec = load_json(os.path.join(adir, fn))
                if rec is None:
                    accept_blockers.append("验收 JSON %s 无法解析" % fn)
                    continue
                ajsons[fn[:-5]] = rec
                for p in evidence.validate_acceptance_json(rec):
                    accept_blockers.append(p)
            elif fn.endswith(".md") and not fn.upper().startswith("README"):
                base = fn[:-3]
                if not os.path.exists(os.path.join(adir, base + ".json")):
                    md_only.append(fn)
    if not required:
        accept_blockers.append(
            "run.json 缺少 required_acceptance_scopes 声明，无法判定必需"
            "验收范围（旧 run 属历史；请用 pdstate.py 重建任务并登记必需"
            " scope 与 qid 清单）")
    for fn in md_only:
        accept_blockers.append("验收记录 %s 属旧版 Markdown 历史证据，缺少同名"
                               " JSON 门禁输入；请复验后补写同名 .json" % fn)
    if required:
        stu_sha = pdf_sha.get("student")
        for scope, qids in required.items():
            rec = ajsons.get(scope)
            if rec is None:
                if scope not in [f[:-3] for f in md_only]:
                    accept_blockers.append(
                        "缺少必需验收范围 %s 的 JSON 记录"
                        "（.pd/acceptance/%s.json；缺证据时不得临时删除必需"
                        " scope）" % (scope, scope))
                continue
            for p in evidence.validate_acceptance_json(
                    rec, current_digest=digest, student_pdf_sha=stu_sha):
                accept_blockers.append(p)
            if rec.get("conclusion") != "PASS":
                accept_blockers.append("必需验收范围 %s 的结论为 %s，非 PASS"
                                       % (scope, rec.get("conclusion")))
            missing_qids = sorted(set(qids) - set(rec.get("reviewed_qids",
                                                          [])))
            if missing_qids:
                accept_blockers.append("必需验收范围 %s 的 PASS 未覆盖全部必需"
                                       " qid（缺 %d 个: %s…）"
                                       % (scope, len(missing_qids),
                                          ", ".join(missing_qids[:5])))

    if blockers:
        print("[deliver] 门禁未通过，%d 个阻断项:" % len(blockers))
        for b in blockers:
            print("  - " + b)
        if accept_blockers:
            print("[deliver] 另有 %d 项教学验收待完成:" % len(accept_blockers))
            for b in accept_blockers:
                print("  - " + b)
        return 1
    if accept_blockers:
        # 技术证据齐备但教学验收未完成：待验收，保留审读草稿，不触碰 release
        print("[deliver] 待验收：技术检查已通过，但教学验收未完成"
              "（%d 项）：" % len(accept_blockers))
        for b in accept_blockers:
            print("  - " + b)
        print("[deliver] 已生成的审读草稿（.pd/review/）保留；可运行 "
              "make_review_pack.py 刷新草稿，验收完成后重跑 deliver。")
        return 1

    # ---- 发布前再核对一次输入与 PDF 哈希（防审查完成后文件又被修改） ----
    final_digest = evidence.content_digest(evidence.collect_inputs(pdir))
    final_pdf = {n: evidence.sha256_file(os.path.join(pdir, n + ".pdf"))
                 for n in ("student", "teacher")}
    if final_digest != digest or final_pdf != pdf_sha:
        print("[deliver] 发布前复核发现受审输入或 PDF 已变化，拒绝交付"
              "（摘要 %s → %s）" % (digest[:12], final_digest[:12]))
        return 1
    for name in ("student.pdf", "teacher.pdf"):
        if not os.path.exists(os.path.join(pdir, name)):
            print("[deliver] 缺少 %s，请先完成构建。" % name)
            return 2

    # ---- 通过：临时目录齐备后原子切换 release ----
    evidence_hashes = {
        "reports": {fn: evidence.sha256_file(os.path.join(rdir, fn))
                    for _s, fn in CHECKS},
        "acceptance": {fn: evidence.sha256_file(os.path.join(adir, fn))
                       for fn in (sorted(os.listdir(adir))
                                  if os.path.isdir(adir) else [])
                       if fn.endswith(".json")},
        "materials.json": evidence.sha256_file(
            os.path.join(pdir, ".pd", "materials.json")),
        "review-notes.json": evidence.sha256_file(
            os.path.join(pdir, ".pd", "review-notes.json")),
    }
    manifest = {
        "schema_version": evidence.SCHEMA_VERSION,
        "tool": "deliver.py", "tool_version": TOOL_VERSION,
        "released": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_digest": digest,
        "content_digest": digest,  # 兼容字段
        "sections": secs,
        "pdf_sha256": pdf_sha,
        "pdfs": pdf_sha,  # 兼容字段
        "status": "pass",
        "issues": [],
        "reports": {fn: (reports.get(fn) or {}).get("status")
                    for _s, fn in CHECKS},
        "tool_versions": {(reports.get(fn) or {}).get("tool", s):
                          (reports.get(fn) or {}).get("tool_version")
                          for s, fn in CHECKS},
        "evidence": {"evidence_hashes": evidence_hashes},
    }
    try:
        rel = atomic_release(pdir, manifest)
    except (OSError, shutil.Error) as e:
        print("[deliver] 发布失败（%s）；上一版 release 保持完整。" % e)
        return 2
    print("[deliver] 全部门禁通过，发布目录: %s" % rel)
    print("[deliver] 注意：本结论意为“已完成的检查范围内未发现问题”，"
          "不代表整章教学效果已被证明。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
