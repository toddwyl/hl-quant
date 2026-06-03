# 执行计划与交接文档

本目录管理所有需要跨会话完成的任务：开发计划和长时间运行任务的交接。

任务收尾时把计划文档从 `active/` 移到 `completed/` 即可。若使用 session-handoff 等工具在别处生成了草稿，请把实质结论合并进本目录下的对应 `.md`。

## 目录结构

```
docs/plans/
├── README.md              ← 本文件：目录规范说明
├── _TEMPLATE.md           ← 计划/交接文档模板（复制它来新建）
├── active/                ← 当前进行中的任务（文件在即任务在）
│   └── YYYY-MM-DD-<topic>.md
└── completed/             ← 已完成的任务归档
    └── YYYY-MM-DD-<topic>.md
```

「计划」与「交接」共用同一套骨架与 `active/` → `completed/` 生命周期：计划偏重「要做什么 + 怎么验证」，交接偏重「现在到哪了 + 接手者下一步怎么继续」。何时该写交接文档、强制行为见 [`AGENTS.md`](../../AGENTS.md)「会话交接（Handoff）」节。

## 规范

### 创建

复制 [`_TEMPLATE.md`](_TEMPLATE.md) 到 `active/`，重命名为 `YYYY-MM-DD-<topic>.md`，按骨架填写：状态、背景、当前进度、关键信息、下一步、注意事项。

### 完成

1. 确认任务已验证通过（`./scripts/harness.sh`）。
2. 将文档从 `active/` 移到 `completed/`。

### 会话开始

代理启动时扫描 `active/` 目录，读取所有 `.md` 文件，向用户汇报当前状态。
