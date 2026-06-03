# 启发式探索（Heuristic Exploration）框架设计

## 背景

本框架受两条思路启发，并把它们合流为一套可在 coding agent 上落地、可持续进化的工程流程：

- **Jiayi Weng 的「启发式探索」（Heuristic Exploration）**——见其文章 *Learning Beyond Gradients*。核心洞察不是「手写规则比模型强」，而是：**当 agent 能持续吸收失败、改代码、跑实验、写测试、看回放、压缩历史时，启发式规则不再是一次性补丁，而可以被维护成一个持续进化的系统。**
- **Andrej Karpathy 的「auto-research」**——其 `autoresearch` 实验提出的「**固定评估器 + 单一可编辑程序**」研究范式：评估流程必须固定，agent 只能修改被优化的程序本身，从而让每个候选方案都在同一口径下可比，避免「改了评估器把分数刷上去」的自欺。

本框架把上述两点制度化，适用于任何**有固定评估口径、追求可度量更优解**的工程问题（性能、质量、转化、错误率等）。

> 本文件既是设计说明，也是落地模板。下文带 `<占位>` 的部分，落地项目时替换成你项目的真实目标程序、评估命令与评分指标。

## 六点核心启发

1. **被优化对象是一个「启发式系统」，而非单个函数**
   不只看某个目标函数或某份 best 配置，而要维护完整闭环：程序代码、状态表示、反馈入口、实验记录、失败样本、回归测试、历史记忆与更新机制。

2. **低分/失败本身不够，需要可解释的失败归因**
   单个 score 下降没有解释力，必须知道是哪一环（输入、阶段、规则、资源利用、样本分布、数据质量）导致。

3. **每次 trial 都应进入账本**
   统一的 `trials.jsonl` / `summary.csv` 让 agent 能跨轮次学习，而不是每次从零开始。

4. **回放与 golden case 是防遗忘机制**
   旧能力要固化成回归测试、固定 seed replay、golden trace、版本 diff，纳入 `scripts/harness.sh`，防止改新功能时悄悄退化。

5. **吸收反馈之后必须压缩历史**
   不无限叠 if-else；每轮局部修补后都要简化、删除无效规则、保留更小的可解释结构。

6. **启发式探索与参数搜索互补**
   参数搜索适合在固定空间里找数值；HL 适合发现新的状态表示、候选规则、失败类别、实验分层与回归约束。HL 位于参数搜索之上：先提出可解释假设，再用固定评估器/参数搜索/回归测试验证。

## 固定评估器 + 单一可编辑程序

这是 Karpathy「auto-research」范式在本框架中的落地，也是整个循环可比性的基础：**评估流程固定，agent 只能改被优化的程序本身。**

### 目标程序

通过编辑唯一的目标程序文件，改进当前 `<被优化目标>`（如：渲染性能 / 转化率 / 错误率 / 算法质量……）：

```text
<src/target_program.ext>
```

这个文件是被优化行为的唯一语义源。其它文件如果只是兼容 shim，会重新导出同一批实现；**不要通过修改 shim 改变行为**。

### 固定评估流程

每个候选方案都必须用同一个命令评估：

```bash
<your evaluator command>
```

评估器固定以下研究口径（按项目填实，一旦固定不得随意更改）：

- 输入/数据集：`<固定数据集或场景>`
- 环境：`<固定运行环境、依赖版本>`
- 评分公式：`score = <单一可比标量>`（单一指标便于排序与决策）
- 有效候选门槛：`<如样本量 / 运行次数下限>`

评估器会写出可复现的产物（结果 JSON + 日志），例如：

```text
data/program_results.json
data/program.log
```

从某个主题 worktree 运行时，评估器应在共享位置（如集成工作区根目录的 `data/`）读写缓存与结果，保证所有实验共享同一份基线数据。

### 禁止修改

为了「提高分数」，禁止修改以下内容（否则分数不可比）：

- 评估器脚本本身（`<your evaluator command>` 对应的脚本）
- 数据集、运行环境、评分公式、有效性门槛
- 任何用于建立基线的固定配置
- 手工编辑结果 JSON

**如果评估基础设施本身坏了，停止并报告阻塞原因，不要通过修改基准来绕过问题。**

## 核心循环（每轮迭代）

```
Probe → Diagnose → Propose → Patch → Evaluate → Replay → Decide → Compress
```

1. **Probe（探测）**：运行固定评估器（见上节），获取基线指标与归因数据。
2. **Diagnose（诊断）**：分析失败窗口、归因、分布，识别失败模式（可解释）。
3. **Propose（假设）**：提出**单一**假设（一次只动一个变量，便于归因）。
4. **Patch（修改）**：仅修改上节指定的唯一目标程序文件。
5. **Evaluate（评估）**：运行固定评估器，比较 score 及关键指标。
6. **Replay（回放）**：通过 golden case 确认既有约束/能力未被破坏。
7. **Decide（决策）**：score 严格高于基线且满足有效门槛才 accept；其余指标允许在预先约定的容忍带内波动。
8. **Compress（压缩）**：分析规则触发率，移除零触发/负贡献规则，保留更小结构。

## 关键约束

- 改动**只允许编辑**目标程序文件（见「固定评估器 + 单一可编辑程序」节）。
- 评估器、评分公式、数据源、固定配置**禁止修改**。
- **禁止使用未来信息**：任何决策只能使用决策时点已经可得的信息（时序问题尤其注意）。
- **禁止窄坑过拟合**：在连续变量上挖 1~2 点宽的离散死区是过拟合的典型标志。合理的过滤必须 (a) 有明确含义的连续区间，或 (b) 规则级别的开关，不得出现精确到个位数的碎片化过滤。
- 训练期可使用 `patience / min_delta` 容忍验证 score 的小幅噪声回落；该机制必须在 run 开始前固定并记录，且只用于训练内验证集，不得把最终 holdout 反复用于调参。
- 每轮搜索必须在 `data/hl_runs/<run_id>/` 留痕（假设、试验、候选 diff）。
- 推荐候选必须在单独 review run 中确认复现。

## 迭代规则

1. 创建独立 worktree 和分支（见 [`docs/spec/worktree-workflow.md`](../spec/worktree-workflow.md)）。
2. 想法只改 `<src/target_program.ext>`。
3. 运行 `<your evaluator command>`。
4. 只有 `score` 严格高于当前基线、且满足有效候选门槛，候选才可保留进入人工审查。
5. 任何经审查准备提交的候选，都必须先运行 `./scripts/harness.sh`。
6. 失败或未完成的实验不得合入 `main`。

每次实验都要在交接或报告中记录：候选 commit、score、关键指标、有效样本量，以及一句简短的想法说明。

## 推荐模块结构（按需实现）

落地项目可参考以下模块划分（不强制，缺则按需补）：

| 模块 | 功能 |
|------|------|
| `run_store` | Run 目录管理、hypothesis/trial JSONL 账本、自动决策记录 |
| `attribution` | 失败窗口识别、归因、CSV 输出 |
| `golden_cases` | 既有约束 replay（把真实失败固化为 fixture） |
| `compression` | 规则触发分析、贡献分析、keep/investigate/remove 分类 |
| `param_search_adapter`（可选） | 参数搜索结果批量导入为 HL trial（如 Optuna / 网格搜索等） |

## 留痕目录约定

```text
data/
├── hl_runs/<run_id>/   # 每轮搜索留痕：hypothesis / trial JSONL、artifact、候选 diff
└── hl_golden_cases/    # 约束 replay fixture
```

## 与持续学习的衔接

本框架是 `AGENTS.md`「持续学习」节的落地载体：trial 账本承载「失败留痕」，golden case 承载「防遗忘回放」，Compress 步骤承载「压缩历史」。常见的、非 HL 专属的踩坑沉淀到 [`../guide/common-pitfalls.md`](../guide/common-pitfalls.md)。

> 想把本框架变成可复用的 agent 能力？参见仓库内的 [`.claude/skills/heuristic-exploration/`](../../.claude/skills/heuristic-exploration/SKILL.md) skill。
