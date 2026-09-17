#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "2.0"
r"""
pdstate.py — 运行契约与候选提交（小型运行状态机，无数据库）

管理 <project>/.pd/run.json：
  schema_version、run_id、切片顺序（以 main.tex 为准）、源文件/模板/配置
  摘要（SHA256）与任务表。任务状态机（转换受 TRANSITIONS 限制）：
    planned → ready → running → produced → checked → accepted
  另有 blocked / failed / stale。这些是运行状态，不是教学质量等级；
  章节可交付还需 deliver.py 的跨节验收与技术门禁。

F06 attempt 机制：派发前先 `start` 创建 attempt，候选写在独占目录
  .pd/candidates/<task>/attempt-NNNN/（task.json 冻结身份与输入摘要，
  inputs/ 为本次实际派发输入快照，不原地重写）；写作者提交
  <task>.tex 与 result.json（复述 run_id/task_id/attempt_id/input_digest
  并给出输出文件 SHA256）。submit 依次核对身份、状态、输入新鲜度、
  输出路径与哈希、候选结构，全部通过才原子提升为正式切片。
  旧 run（schema 1）读取时自动迁移：键规范化为不带扩展名的 task_id，
  旧在途任务降级 ready；旧候选目录不升级为当前 attempt，不可直接提交。

子命令（均在 <project> 下操作；task 参数可带 .tex 后缀，自动规范化）：
  init                      建立/重建清单（已有 run.json 时拒绝，先 invalidate）
  status                    打印任务表与各状态计数
  start <task> [--input P ...] [--prompt-file F]
                            输入包就绪（ready）后派发：创建 attempt 目录、
                            快照实际输入并冻结 task.json，状态转 running
  mark <task> <status>      主 Agent 推进状态（允许的起始状态见 TRANSITIONS；
                            running 只能由 start 设置，produced 只能由
                            submit 设置，stale 只能由 invalidate 设置）
  submit <task>             校验当前 attempt 候选后原子提升为正式切片；
                            输入已变或身份不符的迟到结果不得覆盖新版本
  invalidate                重新计算输入摘要，受影响任务标 stale（不覆写
                            旧 attempt 的冻结摘要；无变化时幂等）
  record <task> [--tokens-in N] [--tokens-out N] [--retries N] [--model M]
                            记录每任务成本（宿主提供实际 usage 时；缺失即
                            留空，不填写估算调用量）

退出码: 0=成功, 1=契约冲突（stale/状态非法/候选或证据不符）, 2=缺少输入。
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import evidence  # noqa: E402

SCHEMA_VERSION = 2
STATUS_FLOW = ("planned", "ready", "running", "produced", "checked",
               "accepted")
STATUS_EXTRA = ("blocked", "failed", "stale")
# mark 允许的状态转换（start/submit/invalidate 专用通道不在此列）
MARK_TRANSITIONS = {
    "ready": {"planned", "stale", "failed", "blocked"},
    "checked": {"produced"},
    "accepted": {"checked"},
    "blocked": {"planned", "ready", "running", "produced", "checked"},
    "failed": {"ready", "running", "produced", "checked"},
}
# invalidate：当前输入改变时，这些状态转为 stale
STALABLE = ("ready", "running", "produced", "checked", "accepted")
# 每个任务的基线输入：模板骨架、版本入口、配置与全局台账
TASK_INPUT_FILES = ("header.tex", "footer.tex", "config.tex",
                    "config-class.tex", "student.tex", "teacher.tex",
                    "config.yaml", "source-map.md", "dependency-map.md",
                    "coverage-map.md")
INPUT_RE = re.compile(r"\\input\{(sec[^/\\}.]+?)(?:\.tex)?\}")
# 候选切片中禁止出现的内容（切片纯度底线）
CANDIDATE_FORBIDDEN = ("\\documentclass", "\\begin{document}",
                       "\\end{document}")


def norm_task(task):
    """逻辑任务 ID 统一为不带扩展名（sec1.tex → sec1）。"""
    return re.sub(r"\.tex$", "", task)


def output_name(task_id):
    return task_id + ".tex"


def load_run(pdir):
    path = os.path.join(pdir, ".pd", "run.json")
    if not os.path.exists(path):
        return None, path
    with open(path, encoding="utf-8") as f:
        return json.load(f), path


def save_run(path, run):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(run, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)  # 原子替换


def migrate_run(run):
    """schema 1 → 2：键规范化为无扩展名 task_id；旧在途（running）任务
    没有 attempt，降级 ready 需重新 start；旧候选目录不升级为当前
    attempt（submit 只认 attempt-NNNN 目录，旧候选天然被拒）。"""
    tasks = {}
    for tid, t in run.get("tasks", {}).items():
        t.setdefault("attempts", [])
        t["current_attempt"] = None
        t["input_sources"] = None
        if t.get("status") == "running":
            t["status"] = "ready"
        tasks[norm_task(tid)] = t
    run["tasks"] = tasks
    run["slices"] = [norm_task(s) for s in run.get("slices", [])]
    run["schema_version"] = SCHEMA_VERSION
    run["migrated_from"] = 1
    return run


def project_slices(pdir):
    main = os.path.join(pdir, "main.tex")
    if not os.path.exists(main):
        return []
    with open(main, encoding="utf-8", errors="replace") as f:
        text = f.read()
    out = []
    for m in INPUT_RE.finditer(text):
        name = norm_task(m.group(1))
        if name not in out:
            out.append(name)
    return out


def baseline_sources(pdir, task_id):
    """任务基线输入来源（项目相对路径）：骨架 + 配置 + 台账 + 材料包。"""
    files = list(TASK_INPUT_FILES)
    files.append("material-pack-%s.md" % task_id)
    return files


def task_input_digest(pdir, task_id):
    """基线输入摘要（init/旧任务用；start 之后的任务以 input_sources 为准）。"""
    paths = [os.path.join(pdir, n) for n in baseline_sources(pdir, task_id)]
    return evidence.digest_paths(paths)[0]


def resolve_sources(pdir, sources):
    """input_sources 记录 → 绝对路径清单（可能不存在，由 digest_paths 标记）。"""
    paths = [os.path.join(pdir, n) for n in sources.get("files", [])]
    paths += list(sources.get("extra", []))
    if sources.get("prompt"):
        paths.append(sources["prompt"])
    return paths


def current_input_digest(pdir, task_id, task):
    """任务当前输入摘要：已 start 的任务按登记的 input_sources 重算。"""
    src = task.get("input_sources")
    if src:
        return evidence.digest_paths(resolve_sources(pdir, src))[0]
    return task_input_digest(pdir, task_id)


def attempt_dir(pdir, task_id, attempt_id):
    return os.path.join(pdir, ".pd", "candidates", task_id,
                        "attempt-%04d" % attempt_id)


def next_attempt_id(pdir, task_id, task):
    """attempt 编号递增、不覆盖：取记录与磁盘目录的最大值 +1。"""
    n = len(task.get("attempts", []))
    cdir = os.path.join(pdir, ".pd", "candidates", task_id)
    if os.path.isdir(cdir):
        for name in os.listdir(cdir):
            m = re.fullmatch(r"attempt-(\d+)", name)
            if m:
                n = max(n, int(m.group(1)))
    return n + 1


def cmd_init(pdir, args):
    run, path = load_run(pdir)
    if run is not None:
        print("[pdstate] run.json 已存在（run_id=%s）；如需重建请先备份删除，"
              "或用 invalidate 更新摘要。" % run["run_id"])
        return 1
    slices = project_slices(pdir)
    run = {
        "schema_version": SCHEMA_VERSION,
        "run_id": time.strftime("%Y%m%d-%H%M%S") + "-%04x" % (os.getpid() % 0xffff),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "slices": slices,
        "digests": {n: evidence.sha256_file(os.path.join(pdir, n))
                    for n in ("header.tex", "config.yaml", "config.tex")},
        "tasks": {},
    }
    for s in slices:
        run["tasks"][s] = {"task_id": s, "status": "planned", "attempts": [],
                           "current_attempt": None, "input_sources": None,
                           "input_digest": task_input_digest(pdir, s),
                           "usage": {}}
    os.makedirs(os.path.dirname(path), exist_ok=True)
    save_run(path, run)
    print("[pdstate] 已建立 run.json：run_id=%s，%d 个切片任务（planned）"
          % (run["run_id"], len(slices)))
    return 0


def cmd_status(pdir, run):
    counts = {}
    for tid, t in run["tasks"].items():
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    print("[pdstate] run_id=%s schema=%d" % (run["run_id"],
                                             run["schema_version"]))
    for tid in run["slices"]:
        t = run["tasks"].get(tid, {})
        cur = t.get("current_attempt")
        print("  %-12s %-9s attempts=%d%s" % (
            tid, t.get("status", "?"), len(t.get("attempts", [])),
            " current=attempt-%04d" % cur if cur else ""))
    print("[pdstate] 状态计数: %s" % (", ".join(
        "%s=%d" % kv for kv in sorted(counts.items())) or "无任务"))
    return 0


def cmd_start(pdir, run, path, args):
    """派发前创建 attempt：快照实际输入、冻结 task.json，ready → running。"""
    tid = norm_task(args.task)
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    task = run["tasks"][tid]
    if task["status"] != "ready":
        print("[pdstate] [冲突] %s 当前状态为 %s，只有 ready 才能 start"
              "（stale 需先修好输入并 mark ready）" % (tid, task["status"]))
        return 1

    # ---- 收集本次派发的实际输入来源 ----
    extra = [os.path.abspath(p) for p in (args.input or [])]
    prompt = os.path.abspath(args.prompt_file) if args.prompt_file else None
    sources = {"files": baseline_sources(pdir, tid), "extra": extra,
               "prompt": prompt}
    src_paths = resolve_sources(pdir, sources)

    aid = next_attempt_id(pdir, tid, task)
    adir = attempt_dir(pdir, tid, aid)
    idir = os.path.join(adir, "inputs")
    os.makedirs(idir, exist_ok=True)

    # ---- 快照输入（之后不原地重写）；缺失来源照样参与摘要（记 None） ----
    copied, missing = [], []
    for src in src_paths:
        if os.path.isfile(src):
            dest = os.path.join(idir, os.path.basename(src))
            shutil.copy2(src, dest)
            copied.append(dest)
        elif os.path.isdir(src):
            dest = os.path.join(idir, os.path.basename(os.path.normpath(src)))
            shutil.copytree(src, dest)
            copied.append(dest)
        else:
            missing.append(src)
    digest, entries = evidence.digest_paths(copied + missing)

    task_json = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run["run_id"],
        "task_id": tid,
        "attempt_id": aid,
        "input_digest": digest,
        "allowed_output": output_name(tid),
        "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "inputs": entries,
    }
    with open(os.path.join(adir, "task.json"), "w", encoding="utf-8") as f:
        json.dump(task_json, f, ensure_ascii=False, indent=2)

    task["status"] = "running"
    task["current_attempt"] = aid
    task["input_sources"] = sources
    task["input_digest"] = digest
    task["attempts"].append({"attempt_id": aid, "status": "running",
                             "started": task_json["created"],
                             "input_digest": digest})
    save_run(path, run)
    print("[pdstate] %s attempt-%04d 已创建（running）：%s" % (tid, aid, adir))
    print("[pdstate] input_digest=%s；写作者须提交 %s 与 result.json"
          "（复述 run_id/task_id/attempt_id/input_digest）"
          % (digest[:16] + "…", output_name(tid)))
    if missing:
        print("[pdstate] [警告] 以下输入来源缺失，已按 None 计入摘要: %s"
              % ", ".join(os.path.basename(m) for m in missing))
    return 0


def cmd_mark(pdir, run, path, args):
    tid, status = norm_task(args.task), args.status
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    if status in ("running", "produced", "stale"):
        print("[pdstate] %s 只能由专用命令设置（running=start, "
              "produced=submit, stale=invalidate）" % status)
        return 1
    if status not in MARK_TRANSITIONS:
        print("[pdstate] 非法状态 %s（mark 允许: %s）"
              % (status, "/".join(sorted(MARK_TRANSITIONS))))
        return 2
    cur = run["tasks"][tid]["status"]
    if cur not in MARK_TRANSITIONS[status]:
        print("[pdstate] [冲突] 不允许 %s → %s（允许的起始状态: %s）"
              % (cur, status,
                 "/".join(sorted(MARK_TRANSITIONS[status]))))
        return 1
    run["tasks"][tid]["status"] = status
    save_run(path, run)
    print("[pdstate] %s → %s" % (tid, status))
    return 0


def check_candidate(text):
    """候选切片底线结构检查；返回问题列表（空 = 通过）。"""
    problems = []
    if not text.strip():
        return ["候选文件为空"]
    for tok in CANDIDATE_FORBIDDEN:
        if tok in text:
            problems.append("候选切片不得包含 %s（切片不是完整文档）" % tok)
    return problems


def cmd_submit(pdir, run, path, args):
    tid = norm_task(args.task)
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    task = run["tasks"][tid]

    # ---- 1. run/task/attempt 与当前派发一致 ----
    aid = task.get("current_attempt")
    if not aid:
        print("[pdstate] [冲突] %s 没有当前 attempt（先用 start 派发；"
              "旧版候选目录不升级为当前 attempt）" % tid)
        return 1
    adir = attempt_dir(pdir, tid, aid)
    tj_path = os.path.join(adir, "task.json")
    if not os.path.exists(tj_path):
        print("[pdstate] [冲突] 缺少冻结的 %s（attempt 目录不完整）" % tj_path)
        return 1
    with open(tj_path, encoding="utf-8") as f:
        frozen = json.load(f)
    for key, expect in (("run_id", run["run_id"]), ("task_id", tid),
                        ("attempt_id", aid)):
        if frozen.get(key) != expect:
            print("[pdstate] [冲突] task.json 的 %s=%s 与当前派发 %s 不一致"
                  % (key, frozen.get(key), expect))
            return 1

    # ---- 2. 任务必须处于 running（stale 不能直接 submit） ----
    if task["status"] != "running":
        print("[pdstate] [冲突] %s 当前状态为 %s，不能 submit"
              "（stale 须先 mark ready 再 start 新 attempt）"
              % (tid, task["status"]))
        return 1

    # ---- 3. 冻结输入与当前任务输入仍一致 ----
    cur_digest = current_input_digest(pdir, tid, task)
    if cur_digest != frozen["input_digest"] or \
            cur_digest != task["input_digest"]:
        task["status"] = "stale"  # 当前输入改变 → stale（不动冻结摘要）
        save_run(path, run)
        print("[pdstate] [冲突] %s 的输入摘要已变化，候选结果作废（stale）；"
              "请按新输入重新派发，不得以迟到结果覆盖当前版本。" % tid)
        return 1

    # ---- 4. result 复述四身份字段，输出路径与哈希正确 ----
    rj_path = os.path.join(adir, "result.json")
    if not os.path.exists(rj_path):
        print("[pdstate] 缺少 %s（写作者须提交 result.json）" % rj_path)
        return 2
    with open(rj_path, encoding="utf-8") as f:
        result = json.load(f)
    for key in ("run_id", "task_id", "attempt_id", "input_digest"):
        if result.get(key) != frozen.get(key):
            print("[pdstate] [冲突] result.json 复述的 %s=%s 与冻结值 %s 不一致"
                  % (key, result.get(key), frozen.get(key)))
            return 1
    out = result.get("output")
    if out != frozen["allowed_output"]:
        print("[pdstate] [冲突] result.json 输出路径 %s 与允许输出 %s 不一致"
              % (out, frozen["allowed_output"]))
        return 1
    cand = os.path.join(adir, out)
    if not os.path.exists(cand):
        print("[pdstate] 候选不存在: %s" % cand)
        return 2
    with open(cand, "rb") as f:
        data = f.read()
    actual = hashlib.sha256(data).hexdigest()
    if result.get("output_sha256") != actual:
        print("[pdstate] [冲突] 候选文件哈希 %s 与 result.json 声明的 %s 不一致"
              % (actual[:16], str(result.get("output_sha256"))[:16]))
        return 1

    # ---- 5. 候选非空且结构检查通过 ----
    problems = check_candidate(data.decode("utf-8", errors="replace"))
    if problems:
        for p in problems:
            print("[pdstate] [冲突] %s" % p)
        return 1

    # ---- 全部通过：原子提升为正式切片 ----
    target = os.path.join(pdir, output_name(tid))
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, target)
    for a in task["attempts"]:
        if a["attempt_id"] == aid:
            a["status"] = "produced"
            a["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            a["output_digest"] = actual
    task["status"] = "produced"
    save_run(path, run)
    print("[pdstate] %s 已提升为正式切片（attempt-%04d），状态 produced；"
          "内容与技术检查后请 mark checked/accepted。" % (tid, aid))
    return 0


def cmd_invalidate(pdir, run, path):
    """重算输入摘要；受影响任务标 stale。不覆写旧 attempt 的冻结摘要；
    无输入变化时幂等（重复调用不改变状态）。"""
    n_stale = 0
    for tid, task in run["tasks"].items():
        cur = current_input_digest(pdir, tid, task)
        if cur != task["input_digest"]:
            if task["status"] in STALABLE:
                task["status"] = "stale"
                n_stale += 1
            task["input_digest"] = cur
    save_run(path, run)
    print("[pdstate] 摘要已刷新，%d 个任务标记为 stale（需重跑）" % n_stale)
    return 0


def cmd_record(pdir, run, path, args):
    tid = norm_task(args.task)
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    u = run["tasks"][tid].setdefault("usage", {})
    for k, v in (("tokens_in", args.tokens_in), ("tokens_out", args.tokens_out),
                 ("retries", args.retries), ("model", args.model)):
        if v is not None:
            u[k] = v  # 只记录宿主提供的实际值；缺失即缺省，不估算
    save_run(path, run)
    print("[pdstate] %s 成本记录: %s" % (tid, u))
    return 0


def main():
    ap = argparse.ArgumentParser(description="运行契约与候选提交")
    ap.add_argument("project", help="项目目录（self/）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    p = sub.add_parser("start")
    p.add_argument("task")
    p.add_argument("--input", action="append", default=[],
                   help="本次派发的实际输入文件/目录（可多个），快照入 attempt")
    p.add_argument("--prompt-file", help="实际发送的提示词文件")
    p = sub.add_parser("mark"); p.add_argument("task"); p.add_argument("status")
    p = sub.add_parser("submit"); p.add_argument("task")
    sub.add_parser("invalidate")
    p = sub.add_parser("record")
    p.add_argument("task")
    p.add_argument("--tokens-in", type=int)
    p.add_argument("--tokens-out", type=int)
    p.add_argument("--retries", type=int)
    p.add_argument("--model")
    args = ap.parse_args()
    pdir = os.path.abspath(args.project)
    if not os.path.isdir(pdir):
        print("[pdstate] 项目目录不存在: %s" % pdir)
        return 2

    if args.cmd == "init":
        return cmd_init(pdir, args)
    run, path = load_run(pdir)
    if run is None:
        print("[pdstate] 缺少 .pd/run.json，请先运行 init。")
        return 2
    if run.get("schema_version") == 1:
        run = migrate_run(run)
        save_run(path, run)
        print("[pdstate] 旧 run（schema 1）已迁移为 schema 2：任务键规范化"
              "为无扩展名 ID，旧在途任务降级 ready；旧候选不可直接提交。")
    elif run.get("schema_version") != SCHEMA_VERSION:
        print("[pdstate] schema_version 不兼容（%s != %d）"
              % (run.get("schema_version"), SCHEMA_VERSION))
        return 2
    if args.cmd == "status":
        return cmd_status(pdir, run)
    if args.cmd == "start":
        return cmd_start(pdir, run, path, args)
    if args.cmd == "mark":
        return cmd_mark(pdir, run, path, args)
    if args.cmd == "submit":
        return cmd_submit(pdir, run, path, args)
    if args.cmd == "invalidate":
        return cmd_invalidate(pdir, run, path)
    if args.cmd == "record":
        return cmd_record(pdir, run, path, args)
    return 2


if __name__ == "__main__":
    sys.exit(main())
