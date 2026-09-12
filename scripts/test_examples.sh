#!/usr/bin/env bash
# =============================================================================
# test_examples.sh — 回归测试：编译 examples/ 中的参考样例
# 在干净构建目录中对 eg.tex（学生版）与 eg_solution.tex（教师版）各编译两遍，
# 验证 Skill 模板与示例在经历改动后依然可正常出片。
# 示例引用的图片若不存在（如 images/fig-*.png 未随 Skill 分发），
# 自动生成 1x1 占位 PNG 以保证结构回归测试可运行。
# 用法: bash test_examples.sh        （可在任意目录运行）
# =============================================================================
set -u
SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_DIR="$(mktemp -d)"
trap 'rm -rf "$BUILD_DIR"' EXIT

# 1x1 白色 PNG 占位图
PLACEHOLDER_B64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

make_placeholders() {
  # 从 $1(tex 文件) 提取 \includegraphics 路径，缺失则写占位图
  grep -oE '\\includegraphics(\[[^]]*\])?\{[^}]+\}' "$1" 2>/dev/null \
    | sed -E 's/.*\{([^}]+)\}.*/\1/' \
    | while IFS= read -r img; do
        if [ ! -f "$BUILD_DIR/$img" ]; then
          mkdir -p "$BUILD_DIR/$(dirname "$img")"
          printf '%s' "$PLACEHOLDER_B64" | base64 -d > "$BUILD_DIR/$img" 2>/dev/null \
            && echo "[test_examples] 生成占位图: $img"
        fi
      done
}

fail=0
for target in eg eg_solution; do
  src="$SKILL_DIR/examples/$target.tex"
  if [ ! -f "$src" ]; then
    echo "[test_examples] 缺少 $src，跳过。"
    fail=1
    continue
  fi
  cp "$src" "$BUILD_DIR/"
  # 复制示例引用的同目录资源（图片等，含子目录）
  (cd "$SKILL_DIR/examples" && find . -mindepth 1 ! -name '*.tex' ! -name '*.md' \
       -exec cp --parents {} "$BUILD_DIR/" \; 2>/dev/null)
  make_placeholders "$src"

  ok=1
  for pass in 1 2; do
    if ! (cd "$BUILD_DIR" && xelatex -interaction=nonstopmode "$target.tex" >"$target.pass$pass.log" 2>&1); then
      echo "[test_examples] FAIL: $target.tex 第 $pass 遍编译失败，日志片段："
      grep -E '^!' "$BUILD_DIR/$target.pass$pass.log" | head -5
      ok=0
      break
    fi
  done
  if [ "$ok" -eq 1 ] && [ -f "$BUILD_DIR/$target.pdf" ]; then
    echo "[test_examples] OK: $target.tex -> $target.pdf 编译通过。"
  else
    fail=1
  fi
done

if [ "$fail" -eq 0 ]; then
  echo "[test_examples] 全部回归测试通过。"
else
  echo "[test_examples] 存在失败项，请检查上方日志。"
fi
exit "$fail"
