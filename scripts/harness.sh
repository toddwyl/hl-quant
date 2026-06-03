#!/usr/bin/env bash
#
# scripts/harness.sh —— 验证门禁（栈无关骨架）
#
# 任何代码改动完成后、提交或声称完成之前，都必须运行本脚本且完整通过。
# 这是新项目唯一需要按技术栈填实的文件：把下面 TODO 段落替换成你项目的
# lint / typecheck / test / build 命令即可。`git diff --check` 一段保持不动。
#
# 用法（在仓库根目录执行）：
#   ./scripts/harness.sh                      # 跑全部门禁
#   HARNESS_BASELINE_CHECK=1 ./scripts/harness.sh   # 额外跑基线回归（见文末）
#
set -euo pipefail

# 脚本位于 scripts/ 下，仓库根目录为其上一级。
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

# ---- 1. 空白/冲突标记检查（栈无关，必留）-------------------------------------
# 检出残留的行尾空白、冲突标记（<<<<<<<）等。仅在 git 仓库内有意义。
if git rev-parse --git-dir >/dev/null 2>&1; then
  echo "[harness] git diff --check"
  git diff --check
else
  echo "[harness] (跳过 git diff --check：当前目录不是 git 仓库，请先 git init)"
fi

# ---- 2. Lint --------------------------------------------------------------
# TODO: 填入你项目的 lint 命令，例如：
#   echo "[harness] lint";        npm run lint
#   echo "[harness] lint";        ruff check .

# ---- 3. 类型检查 -----------------------------------------------------------
# TODO: 填入 typecheck 命令，例如：
#   echo "[harness] typecheck";   npx tsc --noEmit
#   echo "[harness] typecheck";   mypy src

# ---- 4. 单元测试 -----------------------------------------------------------
# TODO: 填入测试命令（接受透传参数 "$@"），例如：
#   echo "[harness] test";        npm test -- "$@"
#   echo "[harness] test";        pytest -q "$@"

# ---- 5. 构建（可选）--------------------------------------------------------
# TODO: 填入构建命令，例如：
#   echo "[harness] build";       npm run build

# ---- 6. 基线回归（可选）----------------------------------------------------
# 启发式探索项目可在此挂接「基线不退化」检查：把当前产物与已接受基线对比，
# 若关键指标退化则失败。设 HARNESS_BASELINE_CHECK=1 时才运行。
if [[ "${HARNESS_BASELINE_CHECK:-}" == "1" ]]; then
  echo ""
  echo "[harness] baseline regression check (HARNESS_BASELINE_CHECK=1)"
  # TODO: 填入基线回归命令，例如：
  #   <your evaluator command> --check-baseline
  echo "[harness] (未配置基线回归脚本，跳过)"
fi

echo "[harness] OK"
