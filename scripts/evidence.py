#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""evidence.py — 受审输入清单与内容摘要（F05 共享模块）

六个脚本（build / check_numbering / check_dialogue / compare_versions /
deliver / make_review_pack）统一通过本模块计算输入证据，避免旧证据冒充
当前结果。本模块只做字面量解析（\input / \includegraphics 的静态参数），
不是完整 TeX 解释器：解析不了的动态路径显式记入 manifest 的
missing / unresolved 字段，绝不静默遗漏。

摘要语义（保守失效方案）：
  - 文件索引按项目相对路径排序，内容为文件 SHA256，修改时间不参与；
  - assembly_order 保留 main.tex 中 \input 的实际顺序，不排序；
    仅交换两个 \input 的顺序也会改变 content_digest；
  - 总摘要 = 对 {"files", "assembly_order", "missing", "unresolved"}
    做确定格式 JSON 序列化（排序键、无多余空白）后的 SHA256。

函数均为纯函数，不读写全局状态，便于用 unittest 固定行为：
  sha256_file(path)            -> str | None
  collect_inputs(project)      -> manifest dict
  content_digest(manifest)     -> str (64 hex)
  digest_paths(paths)          -> (str, entries list)
  write_report(path, report)   -> None

F07 追加（材料/验收/疑似项证据，均为纯函数）：
  scan_tex_markers(text)       注释标记解析（兼容独立 % card: 与旧版
                               % qid: ... | card: 合并行）
  card_usages(project, secs)   切片卡片引用 → {card_id: {files, qids}}
  build_materials_index(project)  由材料包整理 materials.json 机器索引
  validate_material_chain(...) 材料链五核对（机械一致性，不证明真实性）
  validate_acceptance_json(...)  验收 JSON 记录一致性核对
  validate_review_notes(...)   疑似项复核记录与当前报告/PDF 绑定核对
"""
import hashlib
import json
import os
import re
import sys
import time

SCHEMA_VERSION = 2

INPUT_RE = re.compile(r"\\input\{([^{}]+)\}")
GRAPHICS_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^{}]+)\}")
# \includegraphics 缺省扩展名时的探测顺序（与 pdftex/xetex 常用顺序一致）
GRAPHICS_EXTS = (".pdf", ".png", ".jpg", ".jpeg", ".eps")
# 配置与版本入口：始终作为受审输入（存在与否都会反映在 manifest 中）
ENTRY_FILES = ("student.tex", "teacher.tex", "main.tex",
               "config.yaml", "config.tex", "config-class.tex")


def sha256_file(path):
    """文件内容 SHA256（十六进制）；文件不存在返回 None。纯函数。"""
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _strip_comments(text):
    r"""TeX 感知的注释剥离：\% 是转义字符，不作为注释起点。"""
    out = []
    for line in text.splitlines():
        i = 0
        while True:
            j = line.find("%", i)
            if j < 0:
                out.append(line)
                break
            k = j - 1
            while k >= 0 and line[k] == "\\":
                k -= 1
            if (j - 1 - k) % 2 == 1:  # 奇数个反斜杠 → 转义
                i = j + 1
            else:
                out.append(line[:j])
                break
    return "\n".join(out)


def _norm_rel(project, base_rel, target):
    """把 TeX 引用路径规整为项目相对路径（posix 分隔符）。

    返回 (rel 或 None, 是否越界/非法)。target 含反斜杠（动态宏路径）
    时返回 (None, True) 由调用方记入 unresolved。
    """
    if "\\" in target or "{" in target or "}" in target:
        return None, True
    base_dir = os.path.dirname(os.path.join(project, base_rel))
    ap = os.path.abspath(os.path.join(base_dir, target))
    root = os.path.abspath(project)
    if ap != root and not ap.startswith(root + os.sep):
        return None, True  # 越出项目根，无法纳入摘要
    return ap[len(root) + 1:].replace(os.sep, "/"), False


def collect_inputs(project):
    r"""收集受审输入清单。返回 manifest dict（见模块 docstring）。

    manifest 字段：
      project        项目绝对路径（不参与摘要）
      files          [{"path": 相对路径, "sha256": ...}]，按路径排序
      assembly_order main.tex 中全部字面量 \input 目标的实际顺序（不排序）；
                     无 main.tex 时退化为磁盘上 sec*.tex 的排序清单
      missing        被引用但不存在的相对路径（排序）
      unresolved     [{"source","target","kind"}]，动态/越界路径（排序）
    """
    project = os.path.abspath(project)
    files = {}
    missing = set()
    unresolved = []
    assembly_order = []
    visited = set()

    def add_existing(rel):
        if rel not in files:
            files[rel] = sha256_file(os.path.join(project, rel))

    def parse_tex(rel):
        if rel in visited:
            return
        visited.add(rel)
        path = os.path.join(project, rel)
        if not os.path.exists(path):
            missing.add(rel)
            return
        add_existing(rel)
        with open(path, encoding="utf-8", errors="replace") as f:
            text = _strip_comments(f.read())
        for m in INPUT_RE.finditer(text):
            target = m.group(1).strip()
            if not target:
                continue
            if not os.path.splitext(target)[1]:
                target += ".tex"
            trel, bad = _norm_rel(project, rel, target)
            if bad:
                unresolved.append({"source": rel, "target": m.group(1),
                                   "kind": "input"})
                continue
            if rel == "main.tex":
                assembly_order.append(trel)
            if trel.endswith(".tex"):
                parse_tex(trel)
            else:
                if os.path.exists(os.path.join(project, trel)):
                    add_existing(trel)
                else:
                    missing.add(trel)
        for m in GRAPHICS_RE.finditer(text):
            raw = m.group(1).strip()
            if not raw:
                continue
            grel, bad = _norm_rel(project, rel, raw)
            if bad:
                unresolved.append({"source": rel, "target": raw,
                                   "kind": "graphics"})
                continue
            if os.path.splitext(raw)[1]:
                if os.path.exists(os.path.join(project, grel)):
                    add_existing(grel)
                else:
                    missing.add(grel)
                continue
            found = False
            for ext in GRAPHICS_EXTS:
                cand = grel + ext
                if os.path.exists(os.path.join(project, cand)):
                    add_existing(cand)
                    found = True
                    break
            if not found:
                missing.add(grel)

    for name in ENTRY_FILES:
        rel = name.replace(os.sep, "/")
        if name.endswith(".tex"):
            parse_tex(rel)
        elif os.path.exists(os.path.join(project, rel)):
            add_existing(rel)
        else:
            missing.add(rel)

    if not os.path.exists(os.path.join(project, "main.tex")):
        # 无 main.tex：退化为磁盘切片扫描（保持与旧行为兼容的输入范围）
        for f in sorted(os.listdir(project)) if os.path.isdir(project) else []:
            if re.fullmatch(r"sec.*\.tex", f):
                assembly_order.append(f)
                parse_tex(f)

    return {
        "project": project,
        "files": [{"path": p, "sha256": files[p]} for p in sorted(files)],
        "assembly_order": assembly_order,
        "missing": sorted(missing),
        "unresolved": sorted(unresolved,
                             key=lambda u: (u["source"], u["kind"],
                                            u["target"])),
    }


def content_digest(manifest):
    """受审内容总摘要：确定格式 JSON（排序键、无空白）的 SHA256。

    只覆盖 files / assembly_order / missing / unresolved；项目绝对路径
    与文件修改时间不参与，保证同内容同摘要。
    """
    payload = {k: manifest.get(k) for k in
               ("files", "assembly_order", "missing", "unresolved")}
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def digest_paths(paths):
    """对若干文件/目录的内容求确定性摘要（纯函数，不看 mtime）。

    paths 中文件以其 basename 为键，目录递归展开为 "<dirname>/<相对路径>"
    键；键排序后连同内容 SHA256 做确定格式 JSON 序列化再求总摘要。
    不存在的路径记 sha256=None（反映在摘要中，不静默遗漏）。
    返回 (hexdigest, entries)，entries 为 [{"path", "sha256"}] 排序清单。
    """
    entries = {}
    for p in paths:
        if os.path.isfile(p):
            entries[os.path.basename(p)] = sha256_file(p)
        elif os.path.isdir(p):
            base = os.path.basename(os.path.normpath(p))
            for root, _dirs, names in os.walk(p):
                for n in names:
                    ap = os.path.join(root, n)
                    rel = os.path.relpath(ap, p).replace(os.sep, "/")
                    entries["%s/%s" % (base, rel)] = sha256_file(ap)
        else:
            entries[os.path.basename(os.path.normpath(p))] = None
    ordered = [{"path": k, "sha256": entries[k]} for k in sorted(entries)]
    blob = json.dumps(ordered, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest(), ordered


def write_report(path, report):
    """把结构化报告写入 PATH（统一交付证据格式）；path 为空时不写。"""
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)


# ======================= F07：材料/验收/疑似项证据 =======================
# 注释标记解析：同时兼容独立行 `% card: CARD-10` 与旧版合并行
# `% qid: sec4-entry | 题型: ... | card: CARD-10`；新写作只输出独立行。
_QID_PART = re.compile(r"\bqid:\s*([^\s%|]+)")
_CARD_PART = re.compile(r"\bcard:\s*([A-Za-z]+-\d+)")
_CARD_HEADER = re.compile(
    r"\*\*卡片 ID\*\*:\s*`([A-Za-z]+-\d+)`\s*\|\s*"
    r"\*\*对应需求\*\*:\s*`([A-Za-z]+-\d+)`\s*\|\s*"
    r"\*\*状态\*\*:\s*`([A-Za-z-]+)`")
_ANCHOR = re.compile(r"([\w./\\-]+\.tex)`?\s*(L[\d-]+)")


def scan_tex_markers(text):
    """逐行扫描 TeX 注释标记（qid / card），兼容独立行与旧版合并行。

    返回 [{"line", "qid", "card"}]（qid/card 可为 None），按行号有序。
    供 deliver/make_review_pack 与后续检查脚本复用，不要另写解析器。
    """
    events = []
    for lineno, line in enumerate(text.splitlines(), 1):
        s = line.strip()
        if not s.startswith("%"):
            continue
        mq = _QID_PART.search(s)
        mc = _CARD_PART.search(s)
        if mq or mc:
            events.append({"line": lineno,
                           "qid": mq.group(1) if mq else None,
                           "card": mc.group(1) if mc else None})
    return events


def card_usages(project, sec_files):
    """切片中的卡片引用 → {card_id: {"files": [...], "qids": [...]}}。

    卡片归属于其前面最近的 qid 注释（合并行则取同行的 qid）。
    """
    usage = {}
    for name in sec_files:
        path = os.path.join(project, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            events = scan_tex_markers(f.read())
        cur_qid = None
        for ev in events:
            if ev["qid"]:
                cur_qid = ev["qid"]
            if ev["card"]:
                u = usage.setdefault(ev["card"], {"files": [], "qids": []})
                if name not in u["files"]:
                    u["files"].append(name)
                qid = ev["qid"] or cur_qid
                if qid and qid not in u["qids"]:
                    u["qids"].append(qid)
    return usage


def _parse_pack_cards(text):
    """解析材料包中的卡片块，返回 [{card_id, requirement_id, status,
    source_type, verification_text}]（status 为精确字符串，不子串匹配）。"""
    cards = []
    heads = list(_CARD_HEADER.finditer(text))
    for i, m in enumerate(heads):
        block = text[m.end():heads[i + 1].start() if i + 1 < len(heads)
                       else len(text)]
        mtype = re.search(r"\*\*材料类型\*\*:\s*`?([A-Z-]+)`?", block)
        mver = re.search(r"\*\*核验结论\*\*:\s*(.+)", block)
        cards.append({
            "card_id": m.group(1),
            "requirement_id": m.group(2),
            "status": m.group(3),
            "source_type": mtype.group(1) if mtype else "",
            "verification_text": mver.group(1).strip() if mver else "",
        })
    return cards


def build_materials_index(project, sec_files=None):
    """由 material-pack-*.md 的已有证据整理 .pd/materials.json 机器索引
    （不替代原来源摘录）。返回 index dict；供独立小入口或 F08 迁移调用。"""
    project = os.path.abspath(project)
    if sec_files is None:
        manifest = collect_inputs(project)
        sec_files = [f for f in manifest["assembly_order"]
                     if re.match(r"sec", os.path.basename(f))]
    usage = card_usages(project, sec_files)
    cards = []
    packs = sorted(f for f in os.listdir(project)
                   if re.fullmatch(r"material-pack-.*\.md", f))
    for pk in packs:
        with open(os.path.join(project, pk), encoding="utf-8",
                  errors="replace") as f:
            for c in _parse_pack_cards(f.read()):
                anchor = _ANCHOR.search(c["verification_text"])
                if c["source_type"] == "SELF-CONTAINED":
                    locator = "SELF-CONTAINED: 数据与复算过程见核验结论"
                else:
                    locator = ("%s %s" % (anchor.group(1), anchor.group(2))
                               if anchor else "")
                cards.append({
                    "card_id": c["card_id"],
                    "requirement_id": c["requirement_id"],
                    "status": c["status"],
                    "source_type": c["source_type"],
                    "source_locator": locator,
                    "verification_locator": "%s#%s" % (pk, c["card_id"]),
                    "used_by_qids": usage.get(c["card_id"], {}).get(
                        "qids", []),
                })
    cards.sort(key=lambda c: c["card_id"])
    return {"schema_version": SCHEMA_VERSION,
            "tool": "evidence.py build_materials_index",
            "generated": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "cards": cards}


def validate_material_chain(project, index, sec_files):
    """材料链五核对（机械一致性；来源与计算的真实性归审读，不在此证明）。

    返回问题列表（空 = 通过）：
      1. 正文引用的卡片在索引中存在且 status 精确等于 approved；
      2. 卡片的 requirement_id 在 research-brief.md 中存在；
      3. 材料包中有该卡片的 approved 批准记录（精确状态匹配）；
      4. 原文/复算证据定位（source_locator/verification_locator）非空；
      5. 引用卡片的实际 qid 在 coverage-map.md 中存在。
    """
    problems = []
    usage = card_usages(project, sec_files)
    cards = {c.get("card_id"): c for c in (index or {}).get("cards", [])}
    if usage and not cards:
        problems.append("正文引用卡片 %s，但 materials.json 无卡片记录"
                        % ", ".join(sorted(usage)))
        return problems

    def _read(name):
        path = os.path.join(project, name)
        if not os.path.exists(path):
            return None
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()

    brief = _read("research-brief.md")
    coverage = _read("coverage-map.md")
    packs = {}
    for f in os.listdir(project):
        if re.fullmatch(r"material-pack-.*\.md", f):
            packs[f] = _read(f)

    for cid, u in sorted(usage.items()):
        where = "/".join(u["files"])
        c = cards.get(cid)
        if c is None:
            problems.append("切片 %s 引用卡片 %s，但 materials.json 无索引"
                            % (where, cid))
            continue
        # 1. 状态精确相等：unapproved 不得误匹配
        if c.get("status") != "approved":
            problems.append("卡片 %s 状态为 %r，只有 approved 可进入正文"
                            % (cid, c.get("status")))
        # 2. requirement 在 research-brief 中存在
        req = c.get("requirement_id") or ""
        if brief is None:
            problems.append("缺少 research-brief.md，无法核对卡片 %s 的需求 %s"
                            % (cid, req))
        elif not re.search(r"\b%s\b" % re.escape(req), brief):
            problems.append("卡片 %s 对应需求 %s 不在 research-brief.md 中"
                            % (cid, req))
        # 3. 材料包有批准记录（精确状态）
        approved_in_pack = any(
            pc["card_id"] == cid and pc["status"] == "approved"
            for text in packs.values() for pc in _parse_pack_cards(text))
        if not approved_in_pack:
            problems.append("卡片 %s 在任何 material-pack-*.md 中都无 "
                            "approved 批准记录" % cid)
        # 4. 原文/复算证据定位存在
        if not c.get("source_locator"):
            problems.append("卡片 %s 缺少原文锚点/复算证据定位 "
                            "（source_locator 为空）" % cid)
        if not c.get("verification_locator"):
            problems.append("卡片 %s 缺少核验记录定位 "
                            "（verification_locator 为空）" % cid)
        # 5. 实际 qid 在 coverage 中存在
        for qid in u["qids"]:
            if coverage is None:
                problems.append("缺少 coverage-map.md，无法登记卡片 %s 的 "
                                "实际 qid %s" % (cid, qid))
            elif qid not in coverage:
                problems.append("卡片 %s 引用于 qid %s，但 coverage-map.md "
                                "中不存在该 qid" % (cid, qid))
    return problems


_ACCEPTANCE_REQUIRED = ("schema_version", "scope", "reviewed_qids",
                        "content_digest", "student_pdf_sha256",
                        "conclusion", "reviewer_role", "stage1_record",
                        "stage2_record", "issues")
_ISSUE_REQUIRED = ("id", "qid", "part", "code", "evidence", "status",
                   "resolution", "verified_digest")


def validate_acceptance_json(rec, current_digest=None, student_pdf_sha=None):
    """校验 .pd/acceptance/<scope>.json 的记录一致性（不代替实际审读）。

    返回问题列表（空 = 通过）。规则：
      - 必需字段齐全；conclusion ∈ PASS/REVISE/NEEDS_EVIDENCE；
      - conclusion=PASS 时不得有 status=open 的 issue，且绑定当前
        content_digest 与 student.pdf 哈希（调用方提供时）；
      - status=fixed 的 issue 必须有改后位置（resolution）与复验摘要
        （verified_digest）；status=withdrawn 必须给出误报依据
        （resolution 非空且不得只填“综合考虑”）。
    """
    problems = []
    scope = (rec or {}).get("scope", "?")
    for k in _ACCEPTANCE_REQUIRED:
        if k not in rec:
            problems.append("验收记录 %s.json 缺少字段 %s" % (scope, k))
    if problems:
        return problems
    if rec["conclusion"] not in ("PASS", "REVISE", "NEEDS_EVIDENCE"):
        problems.append("验收记录 %s 结论非法: %r" % (scope, rec["conclusion"]))
    if not isinstance(rec["reviewed_qids"], list):
        problems.append("验收记录 %s 的 reviewed_qids 必须是数组" % scope)
    open_issues = []
    for it in rec["issues"]:
        for k in _ISSUE_REQUIRED:
            if k not in it:
                problems.append("验收记录 %s 的 issue 缺少字段 %s: %r"
                                % (scope, k, it.get("id")))
                break
        else:
            if it["status"] == "open":
                open_issues.append(it["id"])
            elif it["status"] == "fixed":
                if not it["resolution"] or not it["verified_digest"]:
                    problems.append("issue %s 标记 fixed 但缺少改后位置或复验摘要"
                                    % it["id"])
            elif it["status"] == "withdrawn":
                res = (it["resolution"] or "").strip()
                if not res or res in ("综合考虑", "已处理"):
                    problems.append("issue %s 标记 withdrawn 但未说明误报依据"
                                    % it["id"])
            else:
                problems.append("issue %s 状态非法: %r（允许 open/fixed/"
                                "withdrawn）" % (it["id"], it["status"]))
    if rec["conclusion"] == "PASS":
        if open_issues:
            problems.append("验收记录 %s 结论为 PASS，但存在未处理的 open "
                            "issue: %s" % (scope, ", ".join(open_issues)))
        if current_digest is not None \
                and rec["content_digest"] != current_digest:
            problems.append("验收记录 %s 绑定的内容摘要与当前摘要不一致"
                            "（旧 PASS 不能冒充当前结果）" % scope)
        if student_pdf_sha is not None \
                and rec["student_pdf_sha256"] != student_pdf_sha:
            problems.append("验收记录 %s 绑定的 student.pdf 哈希与当前构建"
                            "不一致" % scope)
    return problems


def validate_review_notes(notes, compare_report, compare_report_sha,
                          input_digest, pdf_sha256):
    """校验 .pd/review-notes.json 与当前 compare 报告/PDF 的绑定关系。

    返回问题列表（空 = 通过）：报告文件哈希、输入摘要、双版 PDF 哈希必须
    与当前一致（上次同名文件不能替代本次审查）；compare 报告中的每条
    疑似项（severity=review 的 issue_id）都必须有带判断与证据的复核记录。
    """
    problems = []
    for k in ("schema_version", "compare_report_sha256", "input_digest",
              "pdf_sha256", "decisions"):
        if k not in notes:
            problems.append("review-notes.json 缺少字段 %s" % k)
    if problems:
        return problems
    if notes["compare_report_sha256"] != compare_report_sha:
        problems.append("review-notes.json 绑定的 compare 报告哈希与当前报告"
                        "不一致（旧复核记录不覆盖新报告）")
    if notes["input_digest"] != input_digest:
        problems.append("review-notes.json 绑定的输入摘要与当前不一致")
    for k in ("student", "teacher"):
        if (notes["pdf_sha256"] or {}).get(k) != (pdf_sha256 or {}).get(k):
            problems.append("review-notes.json 绑定的 %s.pdf 哈希与当前构建"
                            "不一致（旧复核不覆盖新 PDF）" % k)
    issue_ids = {i["issue_id"] for i in compare_report.get("issues", [])
                 if i.get("severity") == "review" and i.get("issue_id")}
    decided = set()
    for d in notes["decisions"]:
        if not isinstance(d, dict) or not d.get("issue_id"):
            problems.append("review-notes.json 存在缺少 issue_id 的复核记录")
            continue
        if d.get("judgment") and d.get("evidence"):
            decided.add(d["issue_id"])
        else:
            problems.append("疑似项 %s 的复核记录缺少判断或证据"
                            % d["issue_id"])
    for missing in sorted(issue_ids - decided):
        problems.append("compare 疑似项 %s 未有复核判断（漏审）" % missing)
    for extra in sorted(decided - issue_ids):
        problems.append("复核记录包含本次报告中不存在的疑似项 %s（过期记录）"
                        % extra)
    return problems


def _main():
    """独立小入口：python evidence.py materials-index <project> [--out PATH]

    由材料包已有证据整理生成 materials.json（默认写到 --out；不加 --out
    时打印到 stdout，绝不自动写入项目 .pd/）。
    """
    import argparse
    ap = argparse.ArgumentParser(description="evidence 共用证据工具")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("materials-index",
                       help="由 material-pack-*.md 生成 materials.json")
    p.add_argument("project")
    p.add_argument("--out", help="输出路径（缺省打印到 stdout）")
    args = ap.parse_args()
    if args.cmd == "materials-index":
        if not os.path.isdir(args.project):
            print("[evidence] 项目目录不存在: %s" % args.project)
            return 2
        index = build_materials_index(args.project)
        if args.out:
            write_report(args.out, index)
            print("[evidence] materials.json 已写入 %s（%d 张卡片）"
                  % (args.out, len(index["cards"])))
        else:
            print(json.dumps(index, ensure_ascii=False, indent=2))
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(_main())
