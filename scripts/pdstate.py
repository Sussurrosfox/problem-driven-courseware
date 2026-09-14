#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "1.0"
r"""
pdstate.py — 运行契约与候选提交（小型运行状态机，无数据库）

管理 <project>/.pd/run.json：
  schema_version、run_id、切片顺序（以 main.tex 为准）、源文件/模板/配置
  摘要（SHA256）与任务表。任务状态机：
    planned → ready → running → produced → checked → accepted
  另有 blocked / failed / stale。这些是运行状态，不是教学质量等级；
  章节可交付还需 deliver.py 的跨节验收与技术门禁。

子命令（均在 <project> 下操作）：
  init                      建立/重建清单（已有 run.json 时拒绝，先 invalidate）
  status                    打印任务表与各状态计数
  mark <task> <status>      主 Agent 推进状态（planned/ready/running/checked/
                            accepted/blocked/failed；produced 只能由 submit 设置）
  submit <task>             校验 input_digest 未变后，将 .pd/candidates/<task>/
                            中的候选原子提升为正式切片；迟到结果不得覆盖新版本
  invalidate                重新计算输入摘要，受影响任务标 stale
  record <task> [--tokens-in N] [--tokens-out N] [--retries N] [--model M]
                            记录每任务成本（宿主提供 usage 时）

退出码: 0=成功, 1=契约冲突（stale/状态非法/候选缺失）, 2=缺少输入。
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")

SCHEMA_VERSION = 1
STATUS_FLOW = ("planned", "ready", "running", "produced", "checked",
               "accepted")
STATUS_EXTRA = ("blocked", "failed", "stale")
# 每个任务的输入摘要覆盖：模板骨架、配置、全局台账与该节材料包
TASK_INPUT_FILES = ("header.tex", "footer.tex", "config.tex",
                    "config-class.tex", "student.tex", "teacher.tex",
                    "source-map.md", "dependency-map.md", "coverage-map.md")
INPUT_RE = re.compile(r"\\input\{(sec[^/\\}.]+?)(?:\.tex)?\}")


def sha256(path):
    if not os.path.exists(path):
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


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


def project_slices(pdir):
    main = os.path.join(pdir, "main.tex")
    if not os.path.exists(main):
        return []
    with open(main, encoding="utf-8", errors="replace") as f:
        text = f.read()
    out = []
    for m in INPUT_RE.finditer(text):
        name = m.group(1) + ".tex"
        if name not in out:
            out.append(name)
    return out


def task_input_digest(pdir, task_id):
    """任务输入摘要：骨架 + 配置 + 台账 + 该节材料包。"""
    h = hashlib.sha256()
    files = list(TASK_INPUT_FILES)
    files.append("material-pack-%s.md" % task_id.replace(".tex", ""))
    for name in files:
        d = sha256(os.path.join(pdir, name))
        h.update(name.encode())
        h.update((d or "MISSING").encode())
    return h.hexdigest()


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
        "digests": {n: sha256(os.path.join(pdir, n))
                    for n in ("header.tex", "config.yaml", "config.tex")},
        "tasks": {},
    }
    for s in slices:
        run["tasks"][s] = {"status": "planned", "attempts": [],
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
        print("  %-12s %-9s attempts=%d" % (tid, t.get("status", "?"),
                                            len(t.get("attempts", []))))
    print("[pdstate] 状态计数: %s" % (", ".join(
        "%s=%d" % kv for kv in sorted(counts.items())) or "无任务"))
    return 0


def cmd_mark(pdir, run, path, args):
    tid, status = args.task, args.status
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    if status == "produced":
        print("[pdstate] produced 只能由 submit 设置")
        return 1
    if status not in STATUS_FLOW + STATUS_EXTRA:
        print("[pdstate] 非法状态 %s（允许: %s）"
              % (status, "/".join(STATUS_FLOW + STATUS_EXTRA)))
        return 2
    run["tasks"][tid]["status"] = status
    save_run(path, run)
    print("[pdstate] %s → %s" % (tid, status))
    return 0


def cmd_submit(pdir, run, path, args):
    tid = args.task
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    task = run["tasks"][tid]
    cand = os.path.join(pdir, ".pd", "candidates", tid.replace(".tex", ""), tid)
    if not os.path.exists(cand):
        print("[pdstate] 候选不存在: %s" % cand)
        return 2
    cur_digest = task_input_digest(pdir, tid)
    if cur_digest != task["input_digest"]:
        # 输入已变化：迟到的结果不得覆盖当前版本
        task["status"] = "stale"
        save_run(path, run)
        print("[pdstate] [冲突] %s 的输入摘要已变化，候选结果作废（stale）；"
              "请按新输入重新派发，不得以迟到结果覆盖当前版本。" % tid)
        return 1
    target = os.path.join(pdir, tid)
    with open(cand, "rb") as f:
        data = f.read()
    tmp = target + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, target)  # 原子提升为正式切片
    task["attempts"].append({
        "attempt_id": len(task["attempts"]) + 1,
        "time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "output_digest": hashlib.sha256(data).hexdigest(),
    })
    task["status"] = "produced"
    save_run(path, run)
    print("[pdstate] %s 已提升为正式切片（attempt #%d），状态 produced；"
          "内容与技术检查后请 mark checked/accepted。"
          % (tid, len(task["attempts"])))
    return 0


def cmd_invalidate(pdir, run, path):
    n_stale = 0
    for tid, task in run["tasks"].items():
        if task_input_digest(pdir, tid) != task["input_digest"]:
            if task["status"] not in ("planned", "stale"):
                task["status"] = "stale"
                n_stale += 1
            task["input_digest"] = task_input_digest(pdir, tid)
    save_run(path, run)
    print("[pdstate] 摘要已刷新，%d 个任务标记为 stale（需重跑）" % n_stale)
    return 0


def cmd_record(pdir, run, path, args):
    tid = args.task
    if tid not in run["tasks"]:
        print("[pdstate] 未知任务 %s" % tid)
        return 2
    u = run["tasks"][tid].setdefault("usage", {})
    for k, v in (("tokens_in", args.tokens_in), ("tokens_out", args.tokens_out),
                 ("retries", args.retries), ("model", args.model)):
        if v is not None:
            u[k] = v
    save_run(path, run)
    print("[pdstate] %s 成本记录: %s" % (tid, u))
    return 0


def main():
    ap = argparse.ArgumentParser(description="运行契约与候选提交")
    ap.add_argument("project", help="项目目录（self/）")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
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
    if run.get("schema_version") != SCHEMA_VERSION:
        print("[pdstate] schema_version 不兼容（%s != %d）"
              % (run.get("schema_version"), SCHEMA_VERSION))
        return 2
    if args.cmd == "status":
        return cmd_status(pdir, run)
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
