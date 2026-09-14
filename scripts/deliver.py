#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "1.0"
r"""
deliver.py — 交付汇总门禁

技术检查与教学验收互不替代。本入口汇总全部证据，**全部满足**才交付：

  1. 装配无缺失与重复          —— check_numbering.py 通过；
  2. 双版构建与技术检查完成     —— build.py / compare_versions.py 通过
     （默认现场重跑并以 --json 落盘到 .pd/reports/；--skip-checks 时读取
     已有报告，但报告生成时间早于当前切片源文件时判为过期证据，拒绝交付）；
  3. 独立教学验收 PASS 且绑定当前内容摘要 —— .pd/acceptance/*.md 至少
     一份含 `conclusion: PASS` 与匹配当前 content_digest 的
     `digest: <sha256>` 行；摘要不一致即旧 PASS 失效，拒绝交付；
  4. 阻断问题有处理记录        —— 验收记录中不得有未处理的 REVISE /
     NEEDS_EVIDENCE 结论（每条须随后续 PASS 记录或有依据的撤销说明）；
  5. 疑似答案项已人工复核       —— compare 报告 status=review 时，
     .pd/review-notes.md 必须存在且非空；
  6. 材料批准链完整            —— 若存在 material-pack-*.md，切片中出现的
     卡片 ID 不得在材料包中缺失（机械核对；事实与数学核验归主 Agent）。

通过后生成 <project>/release/（student.pdf、teacher.pdf、manifest.json），
仅为本地交付产物，不含向外部平台上传。

用法: python deliver.py <project> [--skip-checks]
退出码: 0=可交付, 1=门禁未通过, 2=缺少依赖或输入。
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
CONTENT_FILES = ("header.tex", "footer.tex", "config.tex",
                 "config-class.tex", "student.tex", "teacher.tex",
                 "config.yaml")


def sha256_file(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def sec_names(pdir):
    main = os.path.join(pdir, "main.tex")
    names = []
    if os.path.exists(main):
        with open(main, encoding="utf-8", errors="replace") as f:
            for m in re.finditer(r"\\input\{(sec[^/\\}.]+?)(?:\.tex)?\}",
                                 f.read()):
                names.append(m.group(1) + ".tex")
    return names


def content_digest(pdir, secs):
    h = hashlib.sha256()
    for name in sorted(secs) + list(CONTENT_FILES):
        d = sha256_file(os.path.join(pdir, name))
        h.update(name.encode())
        h.update((d or "MISSING").encode())
    return h.hexdigest()


def run_check(script, pdir, report_path):
    r = subprocess.run([sys.executable, os.path.join(SCRIPTS, script),
                        pdir, "--json", report_path],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    return r


def load_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def main():
    ap = argparse.ArgumentParser(description="交付汇总门禁")
    ap.add_argument("project")
    ap.add_argument("--skip-checks", action="store_true",
                    help="不重跑三脚本，读取 .pd/reports/ 已有报告")
    args = ap.parse_args()
    pdir = os.path.abspath(args.project)
    if not os.path.isdir(pdir):
        print("[deliver] 项目目录不存在: %s" % pdir)
        return 2

    secs = sec_names(pdir)
    digest = content_digest(pdir, secs)
    rdir = os.path.join(pdir, ".pd", "reports")
    os.makedirs(rdir, exist_ok=True)
    blockers = []

    # ---- 1+2: 技术检查 ----
    checks = [("check_numbering.py", "check_numbering.json"),
              ("build.py", "build.json"),
              ("compare_versions.py", "compare.json")]
    reports = {}
    for script, fname in checks:
        rpath = os.path.join(rdir, fname)
        if not args.skip_checks:
            r = run_check(script, pdir, rpath)
            tail = (r.stdout or "").strip().splitlines()
            for line in tail[-3:]:
                print("  [%s] %s" % (script, line))
            if not os.path.exists(rpath):
                blockers.append("%s 未产出结构化报告（退出码 %s）"
                                % (script, r.returncode))
                continue
        rep = load_json(rpath)
        if rep is None:
            blockers.append("缺少或无法解析报告 %s（先运行对应检查）" % fname)
            continue
        if args.skip_checks:
            newest_src = max(
                (os.path.getmtime(os.path.join(pdir, s)) for s in secs
                 if os.path.exists(os.path.join(pdir, s))), default=None)
            if newest_src is not None and os.path.getmtime(rpath) < newest_src:
                blockers.append("报告 %s 早于当前切片源文件，属过期证据；"
                                "请去掉 --skip-checks 重跑检查" % fname)
                continue
        reports[fname] = rep
        if rep.get("status") not in ("pass", "review"):
            blockers.append("%s 未通过（status=%s，问题 %d 条）"
                            % (script, rep.get("status"),
                               len(rep.get("issues", []))))

    # ---- 3+4: 教学验收记录绑定当前内容摘要 ----
    adir = os.path.join(pdir, ".pd", "acceptance")
    records = []
    if os.path.isdir(adir):
        for fn in sorted(os.listdir(adir)):
            if fn.endswith(".md"):
                with open(os.path.join(adir, fn), encoding="utf-8",
                          errors="replace") as f:
                    records.append((fn, f.read()))
    if not records:
        blockers.append("缺少独立教学验收记录（.pd/acceptance/<scope>.md）")
    else:
        # 每个文件的有效结论 = 最后一个 conclusion/digest 字段（允许同文件
        # 追加复验记录）；REVISE/NEEDS_EVIDENCE 必须由后续同 scope 的
        # PASS（绑定当前摘要）或 withdrawn 记录处理。
        effective = []  # 与 records 逐项对齐: (conclusion, digest, 末结论位置)
        for fn, text in records:
            concls = list(re.finditer(r"(?mi)^\s*conclusion:\s*(\S+)", text))
            digests = re.findall(r"(?mi)^\s*digest:\s*([0-9a-f]{64})", text)
            if not concls:
                blockers.append("验收记录 %s 缺少 conclusion 字段" % fn)
            effective.append((concls[-1].group(1) if concls else None,
                              digests[-1] if digests else None,
                              concls[-1].end() if concls else 0))
        digest_ok = False
        for idx, (fn, text) in enumerate(records):
            concl, dg, cpos = effective[idx]
            if concl in ("REVISE", "NEEDS_EVIDENCE"):
                resolved = (
                    # 同文件在该结论之后追加 withdrawn 依据
                    re.search(r"(?m)^\s*withdrawn:\s*\S", text[cpos:])
                    is not None
                    # 或后续同 scope 记录的 PASS（绑定当前摘要）/ withdrawn
                    or any(
                        (effective[j][0] == "PASS" and effective[j][1] == digest)
                        or re.search(r"(?m)^\s*withdrawn:\s*\S",
                                     records[j][1][effective[j][2]:])
                        for j in range(idx + 1, len(records))
                        if records[j][0] == fn))
                if not resolved:
                    blockers.append("验收记录 %s 的结论 %s 未有后续处理记录"
                                    % (fn, concl))
            if concl == "PASS" and dg == digest:
                digest_ok = True
        if not digest_ok:
            blockers.append("没有绑定当前内容摘要的 PASS 验收记录"
                            "（当前 content_digest=%s；修改受审内容后旧 "
                            "PASS 自动失效，需重新验收）" % digest[:12] + "…")

    # ---- 5: 疑似答案项人工复核 ----
    cmp_rep = reports.get("compare.json")
    if cmp_rep and cmp_rep.get("status") == "review":
        notes = os.path.join(pdir, ".pd", "review-notes.md")
        if not (os.path.exists(notes) and os.path.getsize(notes) > 0):
            blockers.append("compare_versions.py 有疑似答案项待复核，但缺少 "
                            ".pd/review-notes.md 人工复核记录")

    # ---- 6: 材料批准链（机械核对） ----
    packs = [f for f in os.listdir(pdir)
             if re.fullmatch(r"material-pack-.*\.md", f)]
    if packs:
        approved_ids = set()
        for pk in packs:
            with open(os.path.join(pdir, pk), encoding="utf-8",
                      errors="replace") as f:
                for line in f:
                    if "approved" in line:
                        m = re.search(r"\b([A-Za-z]+-\d+)\b", line)
                        if m:
                            approved_ids.add(m.group(1))
        used = set()
        for s in secs:
            sp = os.path.join(pdir, s)
            if os.path.exists(sp):
                with open(sp, encoding="utf-8", errors="replace") as f:
                    used |= set(re.findall(r"%\s*card:\s*([A-Za-z]+-\d+)",
                                           f.read()))
        missing = used - approved_ids
        if missing:
            blockers.append("切片引用了未在批准材料包中的卡片: %s"
                            % ", ".join(sorted(missing)))

    if blockers:
        print("[deliver] 门禁未通过，%d 个阻断项:" % len(blockers))
        for b in blockers:
            print("  - " + b)
        return 1

    # ---- 通过：生成本地发布目录 ----
    rel = os.path.join(pdir, "release")
    os.makedirs(rel, exist_ok=True)
    for name in ("student.pdf", "teacher.pdf"):
        src = os.path.join(pdir, name)
        if not os.path.exists(src):
            print("[deliver] 缺少 %s，请先完成构建。" % name)
            return 2
        shutil.copy2(src, os.path.join(rel, name))
    manifest = {
        "tool": "deliver.py", "tool_version": TOOL_VERSION,
        "released": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "content_digest": digest,
        "sections": secs,
        "pdfs": {n: sha256_file(os.path.join(rel, n))
                 for n in ("student.pdf", "teacher.pdf")},
        "reports": {fn: reports.get(fn, {}).get("status")
                    for _s, fn in checks},
    }
    with open(os.path.join(rel, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("[deliver] 全部门禁通过，发布目录: %s" % rel)
    print("[deliver] 注意：本结论意为“已完成的检查范围内未发现问题”，"
          "不代表整章教学效果已被证明。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
