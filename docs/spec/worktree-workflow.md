# Worktree 工作流

本仓库使用 Git worktree 作为并行开发的默认方式，所有 worktree 统一创建在 `.worktrees/` 目录下。

## 目标

- 保持 `main` 分支足够稳定，随时可集成和验证
- 每个代理或开发者拥有独立的检出目录
- 减少无关改动之间的互相干扰
- 让合并和回退边界清晰可见

## 角色划分

### 1. 集成工作区（Integration）

- **路径**：项目根目录
- **分支**：`main`
- **用途**：fetch、集成、验证、push

规则：

- 存在并行工作时，不在此目录直接开发新功能。
- 仅用于查看整体状态、运行最终集成检查、解决冲突、推送 `main`。

### 2. 主题工作区（Topic）

- **路径模式**：`.worktrees/<topic>`
- **分支模式**：`feat/<topic>`、`fix/<topic>`、`docs/<topic>`、`investigate/<topic>`
- **用途**：为单个切片提供隔离的开发环境

规则：

- 一个 worktree 对应一个分支，一个分支对应一个 worktree。
- 一个分支只做一件完整的事。
- 多个代理并行时，必须使用不同的 worktree 和不同的分支。
- 如果两个切片会大量修改相同文件，不要并行，除非其中一方明确拥有这些文件。

## 标准生命周期

### 创建主题工作区

在集成工作区（项目根目录）执行：

```bash
git fetch origin
git worktree add .worktrees/<topic> -b <branch-name> origin/main
```

示例：

```bash
git fetch origin
git worktree add .worktrees/login-page -b feat/login-page origin/main
```

### 在主题工作区内开发

进入主题工作区后：

```bash
cd .worktrees/<topic>
git status -sb
```

然后按常规工作流循环：

1. 读取相关文件
2. 做一个完整的改动
3. 验证改动（`./scripts/harness.sh`）
4. 提交后再停止

开发过程中如需同步 `main` 的最新改动：

```bash
git fetch origin
git rebase origin/main
```

如果 rebase 风险较高，可改用显式合并：

```bash
git fetch origin
git merge origin/main
```

### 集成回 `main`

确保主题工作区已提交并通过验证。推荐的干净历史路径：

1. 先将主题分支 rebase 到最新 `origin/main`
2. 再用 fast-forward 合并到本地 `main`

```bash
# 在主题工作区中 rebase
cd .worktrees/<topic>
git fetch origin
git rebase origin/main

# 回到集成工作区合并
cd <project-root>
git switch main
git merge --ff-only <branch-name>
```

如果主题分支只有部分内容已就绪，在集成工作区使用 `git cherry-pick` 而不是整体合并。

### 推送策略

- 主题分支需要备份、审查或协作时可随时推送。
- `main` 仅在集成工作区吸收了目标分支并通过验证后才推送。

### 清理

主题分支合并完成后：

```bash
git worktree remove .worktrees/<topic>
git branch -d <branch-name>
```

如果分支已推送到远端：

```bash
git push origin --delete <branch-name>
```

## 命名约定

- 主题名称简短具体：`login-page`、`api-error-handling`、`dashboard-perf`。
- 所有 worktree 统一放在 `.worktrees/` 下，方便发现和管理。
- 不要让长期未合并的 worktree 远离 `origin/main`。
- 如果某个 worktree 变成了探索性质而非可交付，将分支重命名为 `investigate/<topic>` 或直接关闭。
- 多代理并行时，按文件归属或子系统拆分，而不是按模糊目标拆分。

## 并行拆分示例

好的拆分：

- `feat/login-page`：`src/pages/Login/*`
- `fix/api-error-handling`：`src/api/*`
- `docs/api-design`：`docs/` 下的设计文档

坏的拆分：

- 两个代理同时修改 `src/app.tsx`
- 一个分支混合了后端修复、前端页面改版和文档更新
- 在集成工作区直接开发新功能，同时另一个主题分支还在集成中
