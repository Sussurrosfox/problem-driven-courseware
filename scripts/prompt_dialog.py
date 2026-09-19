#!/usr/bin/env python3
# -*- coding: utf-8 -*-
TOOL_VERSION = "2.3"
r"""
prompt_dialog.py — 自学案前置配置 UI 对话框

功能说明：
  在启动 problem-shrink-courseware skill 制作自学案前弹出简明图形对话框，
  交互式询问用户两项核心前置参数：
    1. 自学案主标题 (main_title): 例如「学案」、「高等代数学案」、「子空间与基学案」
    2. 是否启用受控课堂对话体 (dialogue_enabled): true / false
  
  确认后处理：
    - 若指定 --project 目录（或自动探测到工程），自动更新或创建 config.yaml，
      并调用 gen_config.py 重新编译 config.tex 与 config-class.tex；
    - 向标准输出（stdout）输出 JSON 供自动化流程或宿主 Agent 读取；
    - 交互提示（Banner/Prompt）走标准错误输出（stderr），确保管道重定向时 stdout 只有纯净 JSON；
    - 支持 --cli 参数或无显示器环境时自动回退为终端交互，具备跨平台鲁棒性。

命令行用法：
  python prompt_dialog.py
  python prompt_dialog.py --project <项目目录>
  python prompt_dialog.py --project ./self --title "高等代数学案" --dialogue true
  python prompt_dialog.py --cli
"""

import argparse
import json
import os
import re
import subprocess
import sys

# 编码保护
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, "reconfigure"):
        stream.reconfigure(encoding="utf-8", errors="replace")


def get_default_paths():
    """获取脚本所在目录及相关模板路径。"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    skill_root = os.path.dirname(script_dir)
    template_config = os.path.join(skill_root, "templates", "config.yaml")
    gen_config_script = os.path.join(script_dir, "gen_config.py")
    return script_dir, skill_root, template_config, gen_config_script


def detect_suggested_titles(search_dirs):
    """从附近的 .tex 源文件或目录结构中挖掘建议的标题。"""
    candidates = []
    seen = set()
    title_re = re.compile(r"\\title\s*\{([^}]+)\}")

    for sdir in search_dirs:
        if not sdir or not os.path.exists(sdir):
            continue
        try:
            for fname in os.listdir(sdir):
                if fname.endswith(".tex"):
                    fpath = os.path.join(sdir, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            text = f.read(3000)
                        m = title_re.search(text)
                        if m:
                            raw = m.group(1).strip()
                            # 过滤 LaTeX 宏与章节编号标记（注意：字符集内不能用 \S，以免匹配所有非空白符）
                            cleaned = re.sub(r"\\[a-zA-Z]+", "", raw)
                            cleaned = re.sub(r"[0-9\.\s§]+", "", cleaned).strip()
                            cleaned = re.sub(r"[\-_]+", "", cleaned)
                            if cleaned and len(cleaned) >= 2:
                                val = cleaned if cleaned.endswith("学案") else cleaned + "学案"
                                if val not in seen:
                                    seen.add(val)
                                    candidates.append(val)
                    except Exception:
                        pass
        except Exception:
            pass
    return candidates


def read_config_yaml(yaml_path):
    """简易安全读取 config.yaml 中的已知键值。"""
    data = {}
    if not os.path.exists(yaml_path):
        return data
    try:
        with open(yaml_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#") or ":" not in s:
                    continue
                k, _, v = s.partition(":")
                k = k.strip()
                v = v.strip()
                if v.startswith(('"', "'")) and len(v) >= 2:
                    v = v[1:-1]
                else:
                    v = v.split(" #", 1)[0].strip()
                data[k] = v
    except Exception as e:
        print(f"[prompt_dialog] 读取 {yaml_path} 警告: {e}", file=sys.stderr)
    return data


def update_config_yaml(yaml_path, main_title, dialogue_enabled, template_path=None):
    """更新或创建 config.yaml 文件，完整保留现有注释与排版布局。"""
    dlg_str = "true" if dialogue_enabled else "false"

    if not os.path.exists(yaml_path):
        if template_path and os.path.exists(template_path):
            with open(template_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = (
                "# 纯问题驱动自学案 —— 全局参数配置\n"
                "font_size: 12pt\n"
                "paperwidth: 285mm\n"
                "paperheight: 420mm\n"
                "orientation: landscape\n"
                "margin_top: 1in\n"
                "margin_bottom: 1in\n"
                "margin_left: 1in\n"
                "margin_right: 1in\n"
                "headheight: 25pt\n"
                "columns: 2\n"
                "main_title: 学案\n"
                "teacher_head_left: 【教师用书·参考解答与教学要点】\n"
                "dialogue_enabled: true\n"
                "dialogue_section_opening: true\n"
                "dialogue_example_opening: true\n"
                "dialogue_max_section_turns: 8\n"
                "dialogue_max_example_turns: 6\n"
                "dialogue_student_reveal: prompt_only\n"
                "dialogue_require_coverage_hook: true\n"
            )
    else:
        with open(yaml_path, "r", encoding="utf-8") as f:
            content = f.read()

    # 正则更新 main_title
    if re.search(r"^main_title\s*:", content, flags=re.MULTILINE):
        content = re.sub(
            r"^(main_title\s*:\s*).*$",
            r"\g<1>" + main_title,
            content,
            flags=re.MULTILINE,
        )
    else:
        content += f"\nmain_title: {main_title}\n"

    # 正则更新 dialogue_enabled
    if re.search(r"^dialogue_enabled\s*:", content, flags=re.MULTILINE):
        content = re.sub(
            r"^(dialogue_enabled\s*:\s*).*$",
            r"\g<1>" + dlg_str,
            content,
            flags=re.MULTILINE,
        )
    else:
        content += f"\ndialogue_enabled: {dlg_str}\n"

    os.makedirs(os.path.dirname(os.path.abspath(yaml_path)), exist_ok=True)
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(content)


def run_gen_config(project_dir, gen_config_script):
    """调用 gen_config.py 重新生成 config.tex 与 config-class.tex。"""
    if not os.path.exists(gen_config_script):
        return False
    try:
        cmd = [sys.executable, gen_config_script, "--project", project_dir]
        res = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        if res.returncode == 0:
            return True
        print(f"[prompt_dialog] gen_config 警告: {res.stderr or res.stdout}", file=sys.stderr)
    except Exception as e:
        print(f"[prompt_dialog] 调用 gen_config 失败: {e}", file=sys.stderr)
    return False


def report_config_saved(project_dir):
    """配置应用成功后的口径提示（F08）：只说“配置已保存”，不宣称已发布；
    已存在发布且输入已变时追加“发布待重建”。"""
    print("[prompt_dialog] 配置已保存（config.yaml 已更新，config*.tex 已重新生成）。",
          file=sys.stderr)
    manifest_path = os.path.join(project_dir, "release", "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, encoding="utf-8") as f:
            old = json.load(f)
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import evidence
        cur = evidence.content_digest(evidence.collect_inputs(project_dir))
        if old.get("input_digest") != cur:
            print("[prompt_dialog] 检测到已有 release 且受审输入已变化："
                  "发布待重建（请重新构建并通过 deliver.py 门禁）。",
                  file=sys.stderr)
    except Exception:
        # 无法判定时不臆测发布状态
        print("[prompt_dialog] 已有 release 的清单无法解析，发布状态未知；"
              "如需交付请重新运行 deliver.py。", file=sys.stderr)


def run_cli_dialog(init_title="学案", init_dialogue=True, project_dir=None):
    """无图形界面或指定 --cli 时的命令行终端交互。交互走 stderr。"""
    print("=" * 60, file=sys.stderr)
    print("  [自学案配置向导] 纯问题驱动自学案前置配置 (CLI 模式)", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    if project_dir:
        print(f"目标项目: {os.path.abspath(project_dir)}", file=sys.stderr)
    print(file=sys.stderr)

    # 1. 标题
    title_prompt = f"1. 请输入自学案主标题 (main_title) [默认: {init_title}]: "
    try:
        sys.stderr.write(title_prompt)
        sys.stderr.flush()
        user_title = sys.stdin.readline()
        if not user_title and user_title != "":
            user_title = ""
        user_title = user_title.strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[prompt_dialog] 已取消操作。", file=sys.stderr)
        return None
    final_title = user_title if user_title else init_title

    # 2. 对话体
    def_dlg_str = "y" if init_dialogue else "n"
    dlg_prompt = (
        f"2. 是否启用受控课堂对话体? (y: 开启 / n: 关闭) [默认: {def_dlg_str}]: "
    )
    try:
        sys.stderr.write(dlg_prompt)
        sys.stderr.flush()
        user_dlg = sys.stdin.readline().strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[prompt_dialog] 已取消操作。", file=sys.stderr)
        return None

    if user_dlg in ("y", "yes", "true", "1"):
        final_dialogue = True
    elif user_dlg in ("n", "no", "false", "0"):
        final_dialogue = False
    else:
        final_dialogue = init_dialogue

    return {
        "status": "success",
        "main_title": final_title,
        "dialogue_enabled": final_dialogue,
        "project_dir": os.path.abspath(project_dir) if project_dir else None,
    }


def run_gui_dialog(init_title="学案", init_dialogue=True, project_dir=None, extra_presets=None):
    """启动基于 Tkinter 的现代化简明图形对话框。"""
    if sys.platform == "win32":
        try:
            import ctypes
            try:
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception:
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(1)
                except Exception:
                    ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

    import tkinter as tk
    from tkinter import ttk, messagebox

    result = {"status": "cancelled"}

    root = tk.Tk()
    root.title("自学案配置初始化向导")

    # 窗口尺寸与屏幕居中
    win_w, win_h = 560, 500
    root.update_idletasks()
    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    rx = max(0, (sw - win_w) // 2)
    ry = max(0, (sh - win_h) // 2 - 30)
    root.geometry(f"{win_w}x{win_h}+{rx}+{ry}")
    root.minsize(520, 460)

    # 统一视觉风格
    style = ttk.Style(root)
    available_themes = style.theme_names()
    if "vista" in available_themes:
        style.theme_use("vista")
    elif "clam" in available_themes:
        style.theme_use("clam")

    font_header = ("Microsoft YaHei UI", 12, "bold")
    font_sub = ("Microsoft YaHei UI", 9)
    font_label = ("Microsoft YaHei UI", 10, "bold")
    font_text = ("Microsoft YaHei UI", 10)
    font_tip = ("Microsoft YaHei UI", 9)

    # 顶部横幅
    banner_frame = tk.Frame(root, bg="#1a5276", padx=20, pady=14)
    banner_frame.pack(fill=tk.X)

    title_banner = tk.Label(
        banner_frame,
        text="📘 纯问题驱动自学案 · 前置参数配置",
        font=font_header,
        fg="white",
        bg="#1a5276",
    )
    title_banner.pack(anchor="w")

    sub_banner = tk.Label(
        banner_frame,
        text="每次启动自学案制作前，请确认课程主标题与课堂对话体开关。",
        font=font_sub,
        fg="#d4e6f1",
        bg="#1a5276",
    )
    sub_banner.pack(anchor="w", pady=(4, 0))

    # 主表单区域
    main_frame = ttk.Frame(root, padding=(24, 16, 24, 10))
    main_frame.pack(fill=tk.BOTH, expand=True)

    # ---- 1. 标题设置 ----
    lbl_title_group = ttk.Label(main_frame, text="1. 自学案主标题 (main_title):", font=font_label)
    lbl_title_group.pack(anchor="w", pady=(0, 4))

    title_var = tk.StringVar(value=init_title)
    entry_title = ttk.Entry(main_frame, textvariable=title_var, font=font_text)
    entry_title.pack(fill=tk.X, pady=(0, 6))
    entry_title.focus_set()
    entry_title.select_range(0, tk.END)

    # 预设推荐候选标签 / 按钮
    preset_frame = ttk.Frame(main_frame)
    preset_frame.pack(fill=tk.X, pady=(0, 14))

    ttk.Label(preset_frame, text="快捷选项:", font=font_tip, foreground="#666666").pack(side=tk.LEFT, padx=(0, 6))

    # 组合预设
    preset_list = []
    if extra_presets:
        for p in extra_presets:
            if p not in preset_list:
                preset_list.append(p)
    default_presets = ["高等代数学案", "线性代数学案", "微积分学案", "数学分析学案", "学案"]
    for p in default_presets:
        if p not in preset_list:
            preset_list.append(p)

    for p in preset_list[:5]:
        btn = ttk.Button(
            preset_frame,
            text=p,
            command=lambda val=p: title_var.set(val),
        )
        btn.pack(side=tk.LEFT, padx=2)

    # 分割线
    sep1 = ttk.Separator(main_frame, orient="horizontal")
    sep1.pack(fill=tk.X, pady=(4, 12))

    # ---- 2. 对话体开关 ----
    lbl_dlg_group = ttk.Label(main_frame, text="2. 课堂受控对话体 (dialogue_enabled):", font=font_label)
    lbl_dlg_group.pack(anchor="w", pady=(0, 6))

    dlg_var = tk.BooleanVar(value=init_dialogue)

    # 选项 A: 开启
    rb_on = ttk.Radiobutton(
        main_frame,
        text="开启受控课堂对话体（推荐）",
        variable=dlg_var,
        value=True,
    )
    rb_on.pack(anchor="w", padx=8, pady=(2, 0))

    tip_on = ttk.Label(
        main_frame,
        text="   • 在每小节开头生成认知冲突片段 (sectiondialogue)\n"
             "   • 在首个入口题前生成生动引例对话 (exampledialogue)\n"
             "   • 角色名固定：教师 $\\Psi$，学生 $\\alpha/\\beta/\\gamma$ 等，按回合探究推进\n"
             "   • 会泄露答案的教师台词须放入 \\dlgteacher{...}，学生版受控隐藏",
        font=font_tip,
        foreground="#333333",
        justify=tk.LEFT,
    )
    tip_on.pack(anchor="w", padx=26, pady=(1, 8))

    # 选项 B: 关闭
    rb_off = ttk.Radiobutton(
        main_frame,
        text="关闭对话体（传统紧凑题链排版）",
        variable=dlg_var,
        value=False,
    )
    rb_off.pack(anchor="w", padx=8, pady=(4, 0))

    tip_off = ttk.Label(
        main_frame,
        text="   • 不生成人物对白，版面更紧凑，适合纯刷题或单元快速复习",
        font=font_tip,
        foreground="#666666",
        justify=tk.LEFT,
    )
    tip_off.pack(anchor="w", padx=26, pady=(1, 10))

    # ---- 3. 项目路径与提示 ----
    if project_dir:
        sep2 = ttk.Separator(main_frame, orient="horizontal")
        sep2.pack(fill=tk.X, pady=(4, 8))

        proj_box = ttk.Frame(main_frame)
        proj_box.pack(fill=tk.X)
        ttk.Label(
            proj_box,
            text=f"📁 目标工程: {os.path.basename(os.path.abspath(project_dir))}",
            font=font_tip,
            foreground="#1a5276",
        ).pack(anchor="w")
        ttk.Label(
            proj_box,
            text=f"   路径: {os.path.abspath(project_dir)}",
            font=("Consolas", 8),
            foreground="#777777",
        ).pack(anchor="w")

    # ---- 4. 底部操作按钮 ----
    btn_frame = ttk.Frame(root, padding=(20, 10, 20, 16))
    btn_frame.pack(fill=tk.X, side=tk.BOTTOM)

    def on_confirm(event=None):
        t = title_var.get().strip()
        if not t:
            messagebox.showwarning("提示", "自学案标题不能为空，请输入标题或选择预设项。")
            entry_title.focus_set()
            return
        result["status"] = "success"
        result["main_title"] = t
        result["dialogue_enabled"] = bool(dlg_var.get())
        result["project_dir"] = os.path.abspath(project_dir) if project_dir else None
        root.destroy()

    def on_cancel(event=None):
        result["status"] = "cancelled"
        root.destroy()

    btn_cancel = ttk.Button(btn_frame, text="取消 (Esc)", command=on_cancel, width=12)
    btn_cancel.pack(side=tk.RIGHT, padx=(8, 0))

    btn_ok = ttk.Button(btn_frame, text="确定并应用 (Enter)", command=on_confirm, width=16)
    btn_ok.pack(side=tk.RIGHT)

    # 快捷键绑定
    root.bind("<Return>", on_confirm)
    root.bind("<KP_Enter>", on_confirm)
    root.bind("<Escape>", on_cancel)

    # 窗口提升到前端
    root.lift()
    root.attributes("-topmost", True)
    root.after_idle(root.attributes, "-topmost", False)

    root.mainloop()

    if result.get("status") == "success":
        return result
    return None


def ask_courseware_config(project_dir=None, default_title=None, default_dialogue=None, use_cli=False):
    """供 Python 脚本或 Agent 调用的统一接口函数。"""
    script_dir, skill_root, template_config, gen_config_script = get_default_paths()

    # 寻找已有配置
    yaml_path = None
    existing_cfg = {}
    search_dirs = [os.getcwd()]

    if project_dir:
        project_dir = os.path.abspath(project_dir)
        search_dirs.insert(0, project_dir)
        search_dirs.insert(1, os.path.dirname(project_dir))
        if os.path.exists(os.path.join(project_dir, "config.yaml")):
            yaml_path = os.path.join(project_dir, "config.yaml")
        elif os.path.exists(os.path.join(project_dir, "self", "config.yaml")):
            project_dir = os.path.join(project_dir, "self")
            yaml_path = os.path.join(project_dir, "config.yaml")
        else:
            yaml_path = os.path.join(project_dir, "config.yaml")

        if os.path.exists(yaml_path):
            existing_cfg = read_config_yaml(yaml_path)

    # 智能挖掘标题
    detected_titles = detect_suggested_titles(search_dirs)

    # 确定初值
    init_title = default_title or existing_cfg.get("main_title")
    if not init_title:
        init_title = detected_titles[0] if detected_titles else "学案"

    if default_dialogue is not None:
        init_dialogue = default_dialogue
    elif "dialogue_enabled" in existing_cfg:
        init_dialogue = existing_cfg.get("dialogue_enabled", "true").lower() == "true"
    else:
        init_dialogue = True

    # 用户已明确提供的标题和开关直接复用，不再次弹窗
    if default_title is not None and default_dialogue is not None:
        res = {
            "status": "success",
            "main_title": default_title,
            "dialogue_enabled": default_dialogue,
            "project_dir": os.path.abspath(project_dir) if project_dir else None,
        }
        print(f"[prompt_dialog] 复用已明确提供的标题与开关（不再弹窗）: "
              f"{default_title} / dialogue={default_dialogue}", file=sys.stderr)
    # 触发界面
    elif use_cli:
        res = run_cli_dialog(init_title, init_dialogue, project_dir)
    else:
        try:
            res = run_gui_dialog(init_title, init_dialogue, project_dir, extra_presets=detected_titles)
        except Exception as e:
            print(f"[prompt_dialog] GUI 启动异常 ({e})，回退到终端交互...", file=sys.stderr)
            res = run_cli_dialog(init_title, init_dialogue, project_dir)

    if not res or res.get("status") != "success":
        return None

    # 同步更新工程
    if project_dir and yaml_path:
        update_config_yaml(yaml_path, res["main_title"], res["dialogue_enabled"], template_config)
        res["config_yaml"] = yaml_path
        if run_gen_config(project_dir, gen_config_script):
            report_config_saved(project_dir)

    return res


def main():
    ap = argparse.ArgumentParser(
        description="自学案前置配置 UI 对话框：每次启动 skills 前询问标题与是否启用对话体"
    )
    ap.add_argument(
        "--project",
        "-p",
        default=None,
        help="目标项目目录（若指定，将更新/创建其下的 config.yaml 并重新生成 TeX 配置）",
    )
    ap.add_argument(
        "--title",
        "-t",
        default=None,
        help="预填自学案主标题",
    )
    ap.add_argument(
        "--dialogue",
        "-d",
        choices=["true", "false"],
        default=None,
        help="预填是否启用对话体 (true/false)",
    )
    ap.add_argument(
        "--cli",
        action="store_true",
        help="强制使用命令行终端交互，不启动 GUI 对话框",
    )
    ap.add_argument(
        "--output-json",
        "-o",
        default=None,
        help="将用户确认的配置以 JSON 保存到指定文件",
    )
    args = ap.parse_args()

    project_dir = args.project
    if not project_dir:
        # 若当前目录下存在 self 或 config.yaml，自动绑定
        if os.path.exists("self/config.yaml"):
            project_dir = "self"
        elif os.path.exists("config.yaml"):
            project_dir = "."

    default_dlg = None
    if args.dialogue is not None:
        default_dlg = args.dialogue.lower() == "true"

    res = ask_courseware_config(
        project_dir=project_dir,
        default_title=args.title,
        default_dialogue=default_dlg,
        use_cli=args.cli,
    )

    if not res or res.get("status") != "success":
        print(json.dumps({"status": "cancelled"}, ensure_ascii=False))
        return 1

    if args.output_json:
        try:
            with open(args.output_json, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[prompt_dialog] 写入 {args.output_json} 失败: {e}", file=sys.stderr)

    # 标准输出纯净 JSON
    print(json.dumps(res, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
