# hl-quant — 用启发式学习做量化策略优化

一个**最小化**的范例：把量化策略的研究流程，提炼成「**一个可编辑的策略 + 一个固定的回测打分器**」两件东西，再用启发式学习（Heuristic Learning / 启发式探索）持续把分数推高。

思路源自一套真实的小微盘量化系统（`quant_trader`），这里只抽出它最核心的两个器官，去掉所有工程脚手架，让范式本身一眼可见。

## 核心范式：固定评估器 + 单一可编辑程序

```
        ┌─────────────────┐   改它      ┌──────────────────┐
  HL →  │   strategy.py   │ ──────────▶ │   backtest.py    │ ──▶  一个分数
        │  唯一可编辑程序  │   只读它     │   固定评估器      │      (score)
        └─────────────────┘            └──────────────────┘
```

- **`strategy.py`** —— 策略的唯一语义源。启发式学习**只允许改这一个文件**：提假设、改逻辑、调参数。
- **`backtest.py`** —— 固定的评估口径。拉数据、模拟成交、算指标、输出**单一分数**。一旦固定就**不许动**——否则「改了评估器把分数刷上去」，候选之间不再可比。

每个候选策略都用同一条命令、同一段数据、同一个评分公式打分，于是「这版到底有没有更好」变成一个可排序的客观问题。详见 [`docs/design/heuristic-exploration-framework.md`](docs/design/heuristic-exploration-framework.md)。

## 评分公式

沿用 `quant_trader` 的生产口径，把一条策略的表现压成一个标量：

```
score = Sharpe * 0.5 + 年化收益 * 2.0 - 最大回撤 * 1.0
```

## 快速开始

### 1. 配置聚宽（JoinQuant）数据凭证

回测数据来自[聚宽 JQData](https://www.joinquant.com/help/api/doc?name=JQDatadoc)。**不要把账号密码写进代码或提交进仓库**，用环境变量传入：

```bash
export JOINQUANT_ACCOUNT=<你的聚宽账号>
export JOINQUANT_PASSWORD=<你的聚宽密码>
```

### 2. 安装依赖

建议用虚拟环境（仓库**不附带**任何环境，按 `requirements.txt` 自行安装）：

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 跑一次回测

```bash
cd example
python backtest.py
```

首次联网拉取日线后会缓存到 `example/.cache/`，之后重复运行直接读缓存。

## 演示：一轮启发式学习

初始策略就是聚宽经典的**双均线**例子（短期线上穿长期线买入、下穿卖出），原封不动放在 `strategy.py` 里。回测标的上证指数（`000001.XSHG`），区间约一年（同期买入持有约 **+25.5%**）。

**第 0 轮（基线，窗口 5/10）**——纯双均线只吃到了大盘涨幅的一小角，还被反复甩进甩出：

```
总收益 +5.46%   Sharpe 0.698   最大回撤 7.10%   胜率 41.67% (12 笔)   SCORE 0.3922
```

**诊断**：5/10 的均线太灵敏，在震荡里频繁翻转、过早离场、空耗手续费——12 笔交易只换来 +5.46%，而同期大盘涨了 25.5%，趋势大半没拿住。

**假设（一次只动一个变量，且有经济含义）**：把均线**放慢**到 10/20，滤掉日间噪声、把趋势拿得更久。这是对「灵敏度」这一连续维度的整体调整，不是在某个数值上挖窄坑。

**第 1 轮（窗口 10/20）**——只改 `strategy.py` 的两个窗口，评估器一字未动：

```
总收益 +17.33%   Sharpe 1.839   最大回撤 6.71%   胜率 57.14% (7 笔)   SCORE 1.2163
```

| 指标 | 基线 5/10 | 放慢到 10/20 | |
|---|---|---|---|
| **SCORE** | 0.3922 | **1.2163** | ✅ +0.824 |
| 总收益 | +5.46% | +17.33% | ✅ |
| Sharpe | 0.698 | 1.839 | ✅ |
| 最大回撤 | 7.10% | 6.71% | ✅ 更低 |
| 胜率 | 41.67% | 57.14% | ✅ |
| 交易笔数 | 12 | 7 | 更少空耗 |

六项指标全面变好，分数严格抬升 → **接受**。

> **顺带一条反过拟合的纪律**：继续放慢到 10/30、20/60，分数还会更高（1.36、1.28），但交易只剩 1~2 笔——样本太少，更像是撞上了这段行情，而非稳健规律。所以我们停在 10/20 这个「分数全面更好 + 交易笔数健康」的候选上，而不是一味追最高分。这正是 HL 要靠**严格多指标门槛 + 有效样本量**来挡住的陷阱。

## 启发式学习循环

```
Probe（跑基线）→ Diagnose（看弱点）→ Propose（提一个有经济含义的假设）
   → Patch（只改 strategy.py）→ Evaluate（固定评估器打分）→ Decide（严格更好才留）
```

两条硬规矩：

1. **只改 `strategy.py`**，评估器/数据源/评分公式一律不动。
2. **严格更好才算数**——分数没有严格高于基线的候选，不予保留；窄区间死区式的过拟合（在连续变量上挖 1~2 点宽的坑）一律拒绝。

## 把这套循环装成 Agent Skill

上面这套循环已经打包成一个可复用的 [Agent Skill](skills/heuristic-exploration/SKILL.md)，用 [`npx skills`](https://github.com/vercel-labs/skills) 一键安装到你自己的 agent（Claude Code / Cursor 等）：

```bash
npx skills add toddwyl/hl-quant
```

装好后，跟 agent 说「用启发式探索优化这个策略」就会触发它，按 `Probe → Diagnose → Propose → Patch → Evaluate → Decide` 的纪律帮你迭代——只改策略文件、严格门槛、反过拟合。

## 仓库结构

```
hl-quant/
├── README.md
├── requirements.txt    # pip 依赖（仓库不附带任何虚拟环境）
├── example/
│   ├── strategy.py     # 唯一可编辑程序（HL 改这里）
│   └── backtest.py     # 固定评估器（拉聚宽数据 → 模拟 → 打分）
├── skills/
│   └── heuristic-exploration/SKILL.md   # 可 npx 安装的启发式探索 skill
└── docs/
    └── design/heuristic-exploration-framework.md   # 范式背后的完整设计
```

## 致谢与延伸

- 范式取自 Andrej Karpathy 的 **auto-research**（固定评估器 + 单一可编辑程序）与 Jiayi Weng 的 **启发式探索**（持续吸收失败、改代码、跑实验、压缩历史）。
- 数据由[聚宽 JQData](https://www.joinquant.com/help/api/doc?name=JQDatadoc) 提供。
