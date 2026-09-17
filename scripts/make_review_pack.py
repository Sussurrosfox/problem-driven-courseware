#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "1.2"
r"""
make_review_pack.py — 生成学生审读包（独立教学验收阶段一的受控输入）

验收者不得直接读含答案的 TeX 源。本脚本在构建出草稿学生版后，生成
<project>/.pd/review/：
  student-pages.txt   按页分隔的学生版可见文本（页首标注页码）
  manifest.json       审读包清单：内容摘要 content_digest（sec*.tex +
                      模板 + 配置 + 版本开关文件）、student.pdf 摘要、
                      引用图片清单及摘要、生成时间

content_digest 是验收记录（.pd/acceptance/<scope>.md）与 deliver.py
判定“旧 PASS 是否仍有效”的共同依据：修改受审内容后摘要改变，旧验收
结论自动失效。

注意：pdftotext 的抽取顺序对双栏/图文混排可能不可靠；顺序存疑时验收者
应直接审读渲染页（student.pdf），本包只提供受控、可追溯的文本视图。

用法: python make_review_pack.py <project>
退出码: 0=成功, 2=缺少依赖或输入。
"""
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence  # noqa: E402

IMG_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")


def main():
    pdir = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
    if not shutil.which("pdftotext"):
        print("[review-pack] 未找到 pdftotext（poppler）。")
        return 2
    pdf = os.path.join(pdir, "student.pdf")
    if not os.path.exists(pdf):
        print("[review-pack] 缺少 student.pdf，请先用 build.py 构建草稿学生版。")
        return 2
    r = subprocess.run(["pdftotext", pdf, "-"], capture_output=True)
    if r.returncode != 0:
        print("[review-pack] pdftotext 抽取 student.pdf 失败。")
        return 2
    text = r.stdout.decode("utf-8", errors="replace")
    pages = text.split("\x0c")

    # ---- F05：共享证据模块统一收集输入清单与摘要（含装配顺序与图片资产） ----
    in_manifest = evidence.collect_inputs(pdir)
    digest = evidence.content_digest(in_manifest)
    secs = [f for f in in_manifest["assembly_order"]
            if re.match(r"sec", os.path.basename(f))]
    if not secs:
        secs = sorted(f for f in os.listdir(pdir)
                      if re.fullmatch(r"sec.*\.tex", f))
    images = {}
    for name in secs:
        path = os.path.join(pdir, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for img in IMG_RE.findall(f.read()):
                ip = os.path.join(pdir, img)
                images[img] = evidence.sha256_file(ip) or "MISSING"

    outdir = os.path.join(pdir, ".pd", "review")
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "student-pages.txt"), "w",
              encoding="utf-8") as f:
        for i, page in enumerate(pages, 1):
            if not page.strip():
                continue
            f.write("===== 第 %d 页 =====\n%s\n" % (i, page.strip()))

    manifest = {
        "schema_version": evidence.SCHEMA_VERSION,
        "tool": "make_review_pack.py", "tool_version": TOOL_VERSION,
        "scope": {"sections": secs},
        "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "input_digest": digest,
        "content_digest": digest,  # 兼容字段：验收记录 digest 行引用此值
        "pdf_sha256": {"student": evidence.sha256_file(pdf)},
        "student_pdf_sha256": evidence.sha256_file(pdf),
        "sections": secs,
        "images": images,
        "status": "pass",
        "issues": [],
        "evidence": {"missing_inputs": in_manifest["missing"],
                     "unresolved_inputs": in_manifest["unresolved"],
                     "card_refs": evidence.card_usages(pdir, secs)},
        "note": "文本视图仅供受控审读；阅读顺序存疑时审读渲染页。",
    }
    with open(os.path.join(outdir, "manifest.json"), "w",
              encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print("[review-pack] 审读包已生成: %s" % outdir)
    print("[review-pack] content_digest=%s（验收记录须引用此摘要）" % digest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
