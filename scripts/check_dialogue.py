#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "1.2"
r"""
check_dialogue.py — 对话层（sectiondialogue / exampledialogue）结构与泄露检查

只验证结构与泄露，不以台词字面相似度判定质量；数学正确性归独立教学验收。
现有 check_numbering.py / build.py / compare_versions.py 仍是硬门槛，
本脚本与之并列执行、互不替代。

检查内容（sec*.tex 以 main.tex 的 \input 顺序为准）：

  配置与启用范围：
  1. config.yaml 的 dialogue_enabled 取 false 时，任何对话块都判失败
     （配置矛盾）；取 true 时全部小节启用；取 sec0,sec1 列表时只有列表内
     小节启用（用于分节逐步改造），列表外小节出现对话块判失败。
  2. 启用小节可用注释 `% dialogue: off-section <理由>` /
     `% dialogue: off-example <理由>` 单项关闭（理由必填）。

  sectiondialogue（section 开头对话）：
  3. 每个启用小节（含 probchain 的小节）有且仅有一个 sectiondialogue
     （dialogue_section_opening: false 时不得出现）；
  4. sectiondialogue 必须位于 \section* 之后、首个实质题/定义
     （probchain / microknowledge / knowledgebox）之前；
  5. 台词用 \speaker，句数严格控制（sectiondialogue 4-6 句，exampledialogue 3-4 句）。

  exampledialogue（入口引例对话）：
  6. 首个入口题（每个含 probchain 的小节的一级首 \item）之前必须有以
     `% dialogue: qid=<入口题qid>` 绑定的 exampledialogue
     （dialogue_example_opening: false 时不得出现）；
  7. exampledialogue 声明的 qid 必须存在于本切片题目中、全章不重复，
     且对话块必须位于被绑定题目之前；
  8. 台词句数：sectiondialogue 默认 4-6 句（上限 dialogue_max_section_turns，默认 8）；
     exampledialogue 默认 3-4 句（上限 dialogue_max_example_turns，默认 6）；
  9. 任何标 \practicemode{unprompted} 的题目不得配置 exampledialogue
     （对白构成实质提示时题目必须为 guided）。

  泄露与覆盖：
 10. 对话块内禁止 solution / teacherNote / \fillin / \ansspace
     （答案性内容只能放入 \dlgteacher{...}，学生版默认隐藏）；
 11. dialogue_require_coverage_hook: true 时，coverage-map.md 必须存在，
     且每个含 sectiondialogue 的小节有 dialogue-hook 记录行（含小节名），
     每个 exampledialogue 的 qid 在 coverage-map.md 中出现。

  语义反剧透门禁（v1.2 新增）：
 12. check_fillin_leak：扫描 exampledialogue 台词中是否出现紧随题目的
     \fillin 答案 token（基于归一化字符串相似度 >0.8 判定）；
 13. check_suspension_ending：对话块末句必须以 ？/!/？/! 结尾，且含悬置
     指示词；末句含断言标志词则判失败；
 14. check_conflict_density：对话块中必须至少含 2 处认知冲突触发词。

  未使用对话层的旧工程（无任何对话块）一律通过，行为完全不变。

退出码: 0=通过, 1=发现问题, 2=缺少依赖或输入。
用法: python check_dialogue.py [工作目录] [--json PATH]
"""
import argparse
import os
import re
import sys


for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_numbering import strip_comment, sec_inputs  # noqa: E402
from gen_config import load_config  # noqa: E402
import evidence  # noqa: E402

DIALOGUE_ENVS = ("sectiondialogue", "exampledialogue")
# 对话块内禁止出现的答案性内容（\dlgteacher 是唯一合法的教师专属通道）
FORBIDDEN_IN_DLG = re.compile(
    r"\\begin\{(?:solution|teacherNote)\}|\\fillin\b|\\ansspace\b")
SPEAKER = re.compile(r"\\speaker\{")
# 注释标记：绑定 qid / 单节关闭
DLG_QID = re.compile(r"^\s*%\s*dialogue:\s*qid=([^\s%]+)")
DLG_OFF = re.compile(r"^\s*%\s*dialogue:\s*(off-section|off-example)\s*(.*)$")
QID = re.compile(r"^\s*%\s*qid:\s*([^\s%]+)")
TOKEN = re.compile(
    r"\\(begin|end)\{([a-zA-Z*]+)\}"      # 1=kind 2=env
    r"|\\item\b"
    r"|\\practicemode\{([^{}]*)\}"         # 3=模式取值
    r"|\\section\*")
LIST_ENVS = ("enumerate", "itemize", "description", "choices", "tasks",
             "probchain")
# “首个实质题/定义”环境：sectiondialogue 必须结束于它们之前
SUBSTANTIVE_ENVS = ("probchain", "microknowledge", "knowledgebox")


class Cfg:
    """对话配置（缺省值与 references/tex-interface.md 配置字段表一致）。"""
    section_opening = True
    example_opening = True
    max_section_turns = 8
    max_example_turns = 6
    require_coverage_hook = True


def dialogue_config(workdir, problems):
    """读取 config.yaml 的对话配置；返回 (enabled, cfg)。

    enabled: None=未启用；'all'=全部小节；或启用小节名集合（如 {'sec0'}）。
    """
    path = os.path.join(workdir, "config.yaml")
    cfg = Cfg()
    raw = {}
    if os.path.exists(path):
        try:
            raw = load_config(path)
        except (OSError, ValueError) as e:
            problems.append("config.yaml 解析失败: %s" % e)
            raw = {}
    # 兼容 skill4 建议的嵌套写法（dialogue: 下方缩进子键）
    nested = raw.get("dialogue")
    if isinstance(nested, dict):
        for k, v in nested.items():
            raw.setdefault("dialogue_" + str(k),
                           str(v).lower() if isinstance(v, bool) else str(v))

    def boo(key, default):
        v = raw.get(key)
        return default if v is None else str(v).strip().lower() == "true"

    def num(key, default):
        try:
            return int(str(raw.get(key)).strip())
        except (TypeError, ValueError):
            return default

    cfg.section_opening = boo("dialogue_section_opening", Cfg.section_opening)
    cfg.example_opening = boo("dialogue_example_opening", Cfg.example_opening)
    cfg.max_section_turns = num("dialogue_max_section_turns",
                                Cfg.max_section_turns)
    cfg.max_example_turns = num("dialogue_max_example_turns",
                                Cfg.max_example_turns)
    cfg.require_coverage_hook = boo("dialogue_require_coverage_hook",
                                    Cfg.require_coverage_hook)

    en = str(raw.get("dialogue_enabled", "")).strip().lower()
    if en in ("", "false"):
        enabled = None
    elif en == "true":
        enabled = "all"
    else:
        enabled = {s.strip() for s in en.split(",") if s.strip()}
    return enabled, cfg


def scan_file(workdir, name):
    r"""单趟扫描切片。

    返回 dict：
      section_line  首个 \section* 行号（无则 None）
      first_sub     首个实质题/定义（probchain/microknowledge/knowledgebox）行号
      blocks        对话块 [{env,start,end,speakers,qid,forbidden:[(行,token)]}]
      items         probchain 一级题目 [{line,qid,mode}]（按出现顺序）
      offs          {off-section/off-example: (行号, 理由)}
      qids          本文件全部题目 qid -> 题目起始行号
    """
    path = os.path.join(workdir, name)
    with open(path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    section_line = None
    first_sub = None
    blocks = []
    items = []
    offs = {}
    qids = {}
    stack = []          # [env, start_line]
    cur_dlg = None
    pending_qid = None
    cur_item = None

    def close_dialogue(end_line):
        nonlocal cur_dlg
        if cur_dlg is not None:
            cur_dlg["end"] = end_line
            blocks.append(cur_dlg)
            cur_dlg = None

    def finish_item():
        nonlocal cur_item
        if cur_item is not None:
            items.append(cur_item)
            cur_item = None

    for lineno, raw in enumerate(lines, 1):
        mq = QID.match(raw)
        if mq:
            pending_qid = mq.group(1)
        md = DLG_QID.match(raw)
        if md and cur_dlg is not None:
            cur_dlg["qid"] = md.group(1)
        mo = DLG_OFF.match(raw)
        if mo:
            offs[mo.group(1)] = (lineno, mo.group(2).strip())

        line = strip_comment(raw)
        for m in TOKEN.finditer(line):
            tok = m.group(0)
            if tok.startswith("\\item"):
                top_list = None
                for frame in reversed(stack):
                    if frame[0] in LIST_ENVS:
                        top_list = frame
                        break
                if top_list is not None and top_list[0] == "probchain":
                    finish_item()
                    cur_item = {"line": lineno, "qid": pending_qid,
                                "mode": "guided"}
                    if pending_qid:
                        qids.setdefault(pending_qid, lineno)
                    pending_qid = None
                continue
            if tok.startswith("\\practicemode"):
                if cur_item is not None:
                    cur_item["mode"] = m.group(3).strip()
                continue
            if tok.startswith("\\section"):
                if section_line is None:
                    section_line = lineno
                continue
            kind, env = m.group(1), m.group(2)
            if kind == "begin":
                if env in SUBSTANTIVE_ENVS and first_sub is None:
                    first_sub = lineno
                if env in DIALOGUE_ENVS:
                    close_dialogue(lineno)  # 防御：上一块未闭合先结算
                    # 记录精确范围（begin token 之后起算），内容计数延后统一处理
                    cur_dlg = {"env": env, "start": lineno, "end": None,
                               "start_col": m.end(), "end_col": None,
                               "speakers": 0, "qid": None, "forbidden": []}
                stack.append([env, lineno])
            else:  # end
                if stack and stack[-1][0] == env:
                    stack.pop()
                else:
                    # 配对错误由 check_numbering.py 报告，此处尽力恢复
                    for k in range(len(stack) - 1, -1, -1):
                        if stack[k][0] == env:
                            del stack[k:]
                            break
                if env in DIALOGUE_ENVS and cur_dlg is not None:
                    cur_dlg["end_col"] = m.start()  # end token 之前为止
                    close_dialogue(lineno)
    finish_item()
    if cur_dlg is not None:
        cur_dlg["end"] = len(lines)
        cur_dlg["end_col"] = len(strip_comment(lines[-1])) if lines else 0
        blocks.append(cur_dlg)

    # 按精确行列范围提取块内文本（去注释），统一统计台词与违禁 token
    for b in blocks:
        seg = []
        for ln in range(b["start"], b["end"] + 1):
            text = strip_comment(lines[ln - 1])
            if ln == b["start"]:
                text = text[b["start_col"]:]
            if ln == b["end"] and b["end_col"] is not None:
                text = text[:b["end_col"]]
            seg.append((ln, text))
        for ln, text in seg:
            b["speakers"] += len(SPEAKER.findall(text))
            for fm in FORBIDDEN_IN_DLG.finditer(text):
                b["forbidden"].append((ln, fm.group(0)))
    return {"section_line": section_line, "first_sub": first_sub,
            "blocks": blocks, "items": items, "offs": offs, "qids": qids}


# ---------------------------------------------------------------------------
# v1.2 新增：语义反剧透门禁三函数
# ---------------------------------------------------------------------------

# 规则 A：\fillin 答案泄露检测
_FILLIN_ANSWER = re.compile(r"\\fillin\s*\[([^\]]*)\]")
# \speaker{角色}{台词} — 台词部分允许含 \bm{u} 等嵌套大括号，末尾以 } 加可选空白结尾
# 使用 \}\s*$ 而非 }$ 以匹配 strip_comment 后行末可能残留的空白/换行
_SPEAKER_LINE = re.compile(r"\\speaker\{[^}]*\}\{(.*)\}\s*$")


def _normalize_math(s):
    """归一化数学字符串用于相似度比较：去空白、转小写、去反斜杠。"""
    return re.sub(r"[\s\\{}]", "", s).lower()


def _token_similarity(a, b):
    """简单归一化编辑距离相似度（0~1）。"""
    a, b = _normalize_math(a), _normalize_math(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    # Jaccard on character trigrams
    def trigrams(s):
        return set(s[i:i+3] for i in range(len(s) - 2)) if len(s) >= 3 else {s}
    ta, tb = trigrams(a), trigrams(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def check_fillin_leak(name, s, scanned_lines, problems):
    r"""规则 A：检测 exampledialogue 台词是否泄露紧随题目的 \fillin 答案。

    对每个 exampledialogue：
    1. 找到绑定 qid 对应题目的起始行；
    2. 扫描该题目块（到下一个 \item 或文件末）中所有 \fillin[answer]{...} 的 answer；
    3. 归一化后与对话台词中的数学子串逐一比较，相似度 > 0.8 则报错。
    """
    blocks = s["blocks"]
    qids = s["qids"]
    lines = scanned_lines

    for b in blocks:
        if b["env"] != "exampledialogue" or b["qid"] is None:
            continue
        if b["qid"] not in qids:
            continue  # 已由其他规则报缺失

        item_line = qids[b["qid"]]
        # 提取该题目块（从 item_line 到下一个一级 \item 或文件末）中 \fillin answers
        fillin_answers = []
        in_block = False
        for lineno, raw in enumerate(lines, 1):
            if lineno == item_line:
                in_block = True
            if in_block and lineno > item_line:
                stripped = strip_comment(raw)
                # 下一个同级 \item（在 probchain 内）终止扫描范围
                if re.search(r"\\item\b", stripped):
                    break
            if in_block:
                for m in _FILLIN_ANSWER.finditer(strip_comment(raw)):
                    ans = m.group(1).strip()
                    if ans:
                        fillin_answers.append(ans)

        if not fillin_answers:
            continue

        # 提取对话块台词文本（非 \dlgteacher 部分）
        dlg_text_lines = []
        for ln in range(b["start"], b["end"] + 1):
            raw_line = lines[ln - 1]
            # 跳过 \dlgteacher 行（教师专属）
            if r"\dlgteacher" in raw_line:
                continue
            text = strip_comment(raw_line)
            if ln == b["start"]:
                text = text[b["start_col"]:]
            if ln == b["end"] and b["end_col"] is not None:
                text = text[:b["end_col"]]
            dlg_text_lines.append((ln, text))

        # 对每个 fillin answer token 扫描台词
        # 修复 B2：用 found_leak 标志确保每个 answer 只报一次（break 只跳出最内层）
        for ans in fillin_answers:
            found_leak = False
            for ln, text in dlg_text_lines:
                if found_leak:
                    break
                # 从台词中提取数学片段（$...$ 或连续非空格 token）
                math_frags = re.findall(r"\$[^$]+\$|[A-Za-z\\][^\s,;！？!?。，]{2,}", text)
                for frag in math_frags:
                    sim = _token_similarity(ans, frag)
                    if sim > 0.8:
                        problems.append(
                            "%s:%d: [ERROR] dialogue-answer-leak: 台词提前泄露了"
                            "题目 qid=%s 的 \\fillin 答案 '%s'（匹配片段 '%s'，相似度 %.2f）"
                            % (name, ln, b["qid"], ans, frag, sim))
                        found_leak = True
                        break  # 跳出 frag 循环；外层 ln 循环由 found_leak 控制


# 规则 B：末句悬置检测
_SUSPENSION_INDICATORS = re.compile(
    r"验算|计算|证明|检验|究竟|能否|谁对|动笔|算一算|写出|代入|核验|检查|验证")
_PREMATURE_RESOLUTION = re.compile(
    r"由此可见|必然成立|所以答案是|显然等于|因此等于|可以得到|由上可知|结论是")


def _extract_last_speaker_text(b, lines):
    """提取对话块最后一个 \\speaker{}{} 的台词文本。"""
    last_text = None
    last_ln = None
    for ln in range(b["start"], b["end"] + 1):
        raw = lines[ln - 1]
        text = strip_comment(raw)
        m = _SPEAKER_LINE.search(text)
        if m:
            last_text = m.group(1).strip()
            last_ln = ln
    return last_text, last_ln


def check_suspension_ending(name, b, lines, problems):
    r"""规则 B：对话块末句必须是悬置句（设问或指向计算检验的行动句）。

    检测逻辑：
    1. 末句必须以 ？/?/！/! 结尾；
    2. 末句必须含悬置指示词（验算/计算/证明/检验/究竟/能否/谁对）之一；
    3. 末句若含断言标志词（由此可见/必然成立/所以答案是/显然等于），判定失败。
    """
    last_text, last_ln = _extract_last_speaker_text(b, lines)
    if last_text is None:
        return  # 无台词，已由其他规则处理

    ends_with_question = bool(re.search(r"[？?！!]\s*$", last_text))
    has_suspension = bool(_SUSPENSION_INDICATORS.search(last_text))
    has_resolution = bool(_PREMATURE_RESOLUTION.search(last_text))

    if has_resolution:
        problems.append(
            "%s:%d: [ERROR] dialogue-premature-resolution: 对话末句违背悬置原则，"
            "过早给出了确定性结论（含断言标志词：%s）"
            % (name, last_ln,
               _PREMATURE_RESOLUTION.search(last_text).group(0)))
    elif not ends_with_question or not has_suspension:
        problems.append(
            "%s:%d: [ERROR] dialogue-suspension-missing: 对话末句不符合悬置原则——"
            "须以 ？/！/？/! 结尾且含【验算/计算/证明/检验/究竟/能否/谁对】等悬置指示词"
            "（当前末句：%s）"
            % (name, last_ln, last_text[:80]))


# 规则 C：认知冲突密度检测
_CONFLICT_WORDS = re.compile(
    r"凭什么|难道|为何|矛盾|不对|偏偏|并非|未必|破绽|疑问")
_MIN_CONFLICT_COUNT = 2


def check_conflict_density(name, b, lines, problems):
    r"""规则 C：对话块中必须至少含 2 处认知冲突触发词。

    触发词表：凭什么、难道、为何、矛盾、不对、偏偏、并非、未必、破绽、疑问。
    缺乏冲突词说明对话沦为平铺直叙，直接报警。
    """
    full_text = []
    for ln in range(b["start"], b["end"] + 1):
        raw = lines[ln - 1]
        if r"\dlgteacher" in raw:
            continue  # 仅检查学生可见台词
        text = strip_comment(raw)
        if ln == b["start"]:
            text = text[b["start_col"]:]
        if ln == b["end"] and b["end_col"] is not None:
            text = text[:b["end_col"]]
        full_text.append(text)

    combined = "\n".join(full_text)
    matches = _CONFLICT_WORDS.findall(combined)
    if len(matches) < _MIN_CONFLICT_COUNT:
        found = "、".join(matches) if matches else "（无）"
        problems.append(
            "%s:%d: [ERROR] dialogue-conflict-density: %s 对话块认知冲突触发词不足 %d 处"
            "（仅找到：%s）——对话沦为平铺直叙，缺乏有效认知冲突"
            % (name, b["start"], b["env"], _MIN_CONFLICT_COUNT, found))


def check(workdir):

    problems = []
    warnings = []
    enabled, cfg = dialogue_config(workdir, problems)

    inputs = sec_inputs(workdir)
    if inputs is None:
        inputs = sorted(f for f in os.listdir(workdir)
                        if re.fullmatch(r"sec.*\.tex", f))
    files = [f for f in inputs
             if os.path.exists(os.path.join(workdir, f))]

    scanned = {name: scan_file(workdir, name) for name in files}
    all_blocks = [(n, b) for n, s in scanned.items() for b in s["blocks"]]
    evidence = {
        "dialogue_blocks": len(all_blocks),
        "sectiondialogue": sum(1 for _n, b in all_blocks
                               if b["env"] == "sectiondialogue"),
        "exampledialogue": sum(1 for _n, b in all_blocks
                               if b["env"] == "exampledialogue")}

    # ---- 未使用对话层的旧工程：完全沿用旧流程 ----
    if not all_blocks:
        for name, s in scanned.items():
            for key, off in s["offs"].items():
                if not off[1]:
                    problems.append("%s:%d: `%% dialogue: %s` 必须填写理由"
                                    % (name, off[0], key))
        has_off = any(s["offs"] for s in scanned.values())
        if enabled and not has_off:
            problems.append(
                "config.yaml 声明 dialogue_enabled=%s，但全部小节均无对话块；"
                "未准备好启用对话层时请改回 false，或只列出已改造小节"
                % ("true" if enabled == "all"
                   else ",".join(sorted(enabled))))
        return problems, warnings, evidence

    if enabled is None:
        problems.append("存在对话块，但 config.yaml 未启用对话层"
                        "（dialogue_enabled 缺省或为 false）：配置矛盾")

    # ---- 覆盖承接（coverage-map.md）----
    coverage = ""
    if cfg.require_coverage_hook:
        cov_path = os.path.join(workdir, "coverage-map.md")
        if not os.path.exists(cov_path):
            problems.append("使用对话层但缺少 coverage-map.md，无法登记对话承接"
                            "（dialogue_require_coverage_hook: true）")
        else:
            with open(cov_path, encoding="utf-8", errors="replace") as f:
                coverage = f.read()

    dlg_qid_seen = {}   # 对话绑定 qid -> 首次位置（全章唯一）
    for name, s in scanned.items():
        stem = re.sub(r"\.tex$", "", name)
        blocks = s["blocks"]
        sec_dlgs = [b for b in blocks if b["env"] == "sectiondialogue"]
        exa_dlgs = [b for b in blocks if b["env"] == "exampledialogue"]
        is_active = (enabled == "all" or
                     (isinstance(enabled, set) and stem in enabled))
        off_sec = s["offs"].get("off-section")
        off_exa = s["offs"].get("off-example")
        for key, off in (("off-section", off_sec), ("off-example", off_exa)):
            if off and not off[1]:
                problems.append("%s:%d: `%% dialogue: %s` 必须填写理由"
                                % (name, off[0], key))

        if enabled is not None and not is_active:
            for b in blocks:
                problems.append(
                    "%s:%d: 小节不在 dialogue_enabled 启用范围内，不得出现 %s"
                    "（先在 config.yaml 登记再改造）" % (name, b["start"], b["env"]))
            continue
        if enabled is None:
            continue  # 配置矛盾已报错，不再逐项展开

        # ---- 关闭标记与对话块互斥 ----
        if off_sec and sec_dlgs:
            problems.append("%s: 已声明 `%% dialogue: off-section`，"
                            "但仍存在 sectiondialogue" % name)
        if off_exa and exa_dlgs:
            problems.append("%s: 已声明 `%% dialogue: off-example`，"
                            "但仍存在 exampledialogue" % name)

        # ---- sectiondialogue：数量、位置、回合、覆盖承接 ----
        if cfg.section_opening and not off_sec and s["items"]:
            if not sec_dlgs:
                problems.append(
                    "%s: 启用小节缺少 sectiondialogue（应在 \\section* 之后、"
                    "首个实质题/定义之前；不适用时加 `%% dialogue: off-section"
                    " <理由>` 并在 overview-guide/coverage-map 说明）" % name)
            elif len(sec_dlgs) > 1:
                problems.append("%s: sectiondialogue 出现 %d 个，每节至多一个"
                                % (name, len(sec_dlgs)))
        if not cfg.section_opening and sec_dlgs:
            problems.append("%s: dialogue_section_opening: false，"
                            "但存在 sectiondialogue（配置矛盾）" % name)
        for b in sec_dlgs:
            if s["section_line"] and b["start"] < s["section_line"]:
                problems.append("%s:%d: sectiondialogue 位于 \\section* 之前"
                                % (name, b["start"]))
            if s["first_sub"] and b["end"] and b["end"] > s["first_sub"]:
                problems.append(
                    "%s:%d: sectiondialogue 必须结束于首个实质题/定义"
                    "（第 %d 行）之前" % (name, b["start"], s["first_sub"]))
            if b["speakers"] == 0:
                problems.append("%s:%d: sectiondialogue 内没有 \\speaker 台词"
                                % (name, b["start"]))
            if b["speakers"] > cfg.max_section_turns:
                problems.append(
                    "%s:%d: sectiondialogue 台词 %d 句超过上限 %d"
                    "（dialogue_max_section_turns）"
                    % (name, b["start"], b["speakers"], cfg.max_section_turns))
            if coverage and not any(
                    "dialogue-hook" in l and stem in l
                    for l in coverage.splitlines()):
                problems.append(
                    "%s: coverage-map.md 缺少本小节的 dialogue-hook 承接记录"
                    "（记录行须含 dialogue-hook 与小节名 %s）" % (name, stem))

        # ---- exampledialogue：全局开关、绑定、位置、回合 ----
        if not cfg.example_opening and exa_dlgs:
            problems.append("%s: dialogue_example_opening: false，"
                            "但存在 exampledialogue（配置矛盾）" % name)
        for b in exa_dlgs:
            if b["qid"] is None:
                problems.append("%s:%d: exampledialogue 缺少 "
                                "`%% dialogue: qid=<题ID>` 绑定注释"
                                % (name, b["start"]))
            else:
                if b["qid"] not in s["qids"]:
                    problems.append("%s:%d: exampledialogue 绑定的 qid “%s” "
                                    "不是本切片题目 qid"
                                    % (name, b["start"], b["qid"]))
                elif b["end"] and b["end"] > s["qids"][b["qid"]]:
                    problems.append(
                        "%s:%d: exampledialogue 必须位于被绑定题目"
                        "（qid=%s，第 %d 行）之前"
                        % (name, b["start"], b["qid"], s["qids"][b["qid"]]))
                if b["qid"] in dlg_qid_seen:
                    problems.append("%s:%d: exampledialogue 绑定的 qid “%s” "
                                    "与 %s 重复（对话绑定必须全章唯一）"
                                    % (name, b["start"], b["qid"],
                                       dlg_qid_seen[b["qid"]]))
                else:
                    dlg_qid_seen[b["qid"]] = "%s:%d" % (name, b["start"])
                if coverage and b["qid"] not in coverage:
                    problems.append("%s:%d: exampledialogue 绑定的 qid “%s” "
                                    "未在 coverage-map.md 登记"
                                    % (name, b["start"], b["qid"]))
            if b["speakers"] == 0:
                problems.append("%s:%d: exampledialogue 内没有 \\speaker 台词"
                                % (name, b["start"]))
            if b["speakers"] > cfg.max_example_turns:
                problems.append(
                    "%s:%d: exampledialogue 台词 %d 句超过上限 %d"
                    "（dialogue_max_example_turns）"
                    % (name, b["start"], b["speakers"], cfg.max_example_turns))

        # ---- 首个入口题必须有绑定的 exampledialogue ----
        if cfg.example_opening and not off_exa and s["items"]:
            entry = s["items"][0]
            bound = [b for b in exa_dlgs
                     if b["qid"] is not None and b["qid"] == entry["qid"]]
            if entry["qid"] is None:
                problems.append("%s:%d: 首个入口题缺少 `%% qid:` 注释，"
                                "无法绑定 exampledialogue"
                                % (name, entry["line"]))
            elif not bound:
                problems.append(
                    "%s:%d: 首个入口题（qid=%s）之前缺少以 "
                    "`%% dialogue: qid=%s` 绑定的 exampledialogue"
                    % (name, entry["line"], entry["qid"], entry["qid"]))

        # ---- 任何 unprompted 题都不得配置 exampledialogue（对白即实质提示）----
        mode_by_qid = {it["qid"]: it for it in s["items"] if it["qid"]}
        for b in exa_dlgs:
            it = mode_by_qid.get(b["qid"]) if b["qid"] else None
            if it and it["mode"] == "unprompted":
                problems.append(
                    "%s:%d: unprompted 题（qid=%s）不得配置 exampledialogue；"
                    "对白提供实质提示时题目必须标为 guided"
                    % (name, b["start"], b["qid"]))

        # ---- 对话块内泄露 ----
        for b in blocks:
            for ln, tok in b["forbidden"]:
                problems.append(
                    "%s:%d: 对话块内禁止 %s（答案性内容只能放入 "
                    "\\dlgteacher{...}，教师版专属）" % (name, ln, tok))

        # ---- v1.2 语义反剧透门禁（规则 A/B/C）----
        _file_path = os.path.join(workdir, name)
        try:
            with open(_file_path, encoding="utf-8", errors="replace") as _f:
                _lines = _f.readlines()
        except OSError:
            _lines = []
        if _lines:
            # 规则 A：fillin 答案泄露
            check_fillin_leak(name, s, _lines, problems)
            # 规则 B/C：对每个对话块检测末句悬置与冲突密度
            for b in blocks:
                check_suspension_ending(name, b, _lines, problems)
                check_conflict_density(name, b, _lines, problems)

    return problems, warnings, evidence


def main():
    ap = argparse.ArgumentParser(description="对话层结构与泄露检查")
    ap.add_argument("workdir", nargs="?", default=".")
    ap.add_argument("--json", metavar="PATH", help="写入结构化检查结果")
    args = ap.parse_args()
    workdir = os.path.abspath(args.workdir)
    if not os.path.isdir(workdir):
        print("[check_dialogue] 工作目录不存在: %s" % workdir)
        if args.json:
            evidence.write_report(args.json, {
                "schema_version": evidence.SCHEMA_VERSION,
                "tool": "check_dialogue.py", "tool_version": TOOL_VERSION,
                "scope": {"workdir": workdir},
                "input_digest": None, "pdf_sha256": None,
                "status": "error",
                "issues": [{"severity": "error",
                            "message": "工作目录不存在: %s" % workdir}],
                "evidence": {}})
            print("[check_dialogue] 结构化报告已写入 %s" % args.json)
        return 2
    problems, warnings, ev = check(workdir)

    # ---- F05：输入证据摘要（本检查不读 PDF，pdf_sha256 恒为 null） ----
    manifest = evidence.collect_inputs(workdir)
    digest = evidence.content_digest(manifest)
    if manifest["missing"] or manifest["unresolved"]:
        ev = dict(ev)
        ev["missing_inputs"] = manifest["missing"]
        ev["unresolved_inputs"] = manifest["unresolved"]

    if args.json:
        report = {"schema_version": evidence.SCHEMA_VERSION,
                  "tool": "check_dialogue.py", "tool_version": TOOL_VERSION,
                  "scope": {"workdir": workdir},
                  "input_digest": digest, "pdf_sha256": None,
                  "status": "fail" if problems else "pass",
                  "issues": ([{"severity": "error", "message": p}
                              for p in problems]
                             + [{"severity": "warning", "message": w}
                                for w in warnings]),
                  "evidence": ev}
        evidence.write_report(args.json, report)
        print("[check_dialogue] 结构化报告已写入 %s" % args.json)

    for w in warnings:
        print("[check_dialogue] [警告] " + w)
    if problems:
        print("[check_dialogue] 发现 %d 个问题:" % len(problems))
        for p in problems:
            print("  - " + p)
        return 1
    if ev["dialogue_blocks"]:
        print("[check_dialogue] 通过：对话块 %d 个（sectiondialogue=%d, "
              "exampledialogue=%d）。"
              % (ev["dialogue_blocks"], ev["sectiondialogue"],
                 ev["exampledialogue"]))
    else:
        print("[check_dialogue] 通过：未使用对话层，沿用旧流程。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
