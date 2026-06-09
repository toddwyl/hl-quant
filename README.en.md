<div align="center">

<img src="docs/images/banner.svg" alt="hl-quant" width="760">

### Compress quant research into "one editable strategy + one fixed scorer"<br>then use Heuristic Learning to keep pushing the metrics up.

[中文](README.md) · English

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Stars](https://img.shields.io/github/stars/toddwyl/hl-quant?style=flat)](https://github.com/toddwyl/hl-quant/stargazers)
[![Agent Skill](https://img.shields.io/badge/Agent%20Skill-npx%20skills-black)](skills/hl-quant/SKILL.md)
[![Demo Data: JoinQuant](https://img.shields.io/badge/demo%20data-JoinQuant%20JQData-orange)](https://www.joinquant.com/help/api/doc?name=JQDatadoc)
[![Linux.do community](https://img.shields.io/badge/Linux.do-community-0ea5e9)](https://linux.do/)

[What is this](#what-is-this) · [Quick Start](#quick-start) · [How it works](#how-it-works) · [Install the Skill](#install-the-skill) · [WeChat Group](#wechat-group) · [Star History](#star-history)

</div>

---

## What is this

`hl-quant` brings Jiayi Weng's [Heuristic Learning](https://trinkle23897.github.io/learning-beyond-gradients/) framework and Andrej Karpathy's [auto-research](https://github.com/karpathy/autoresearch) paradigm down to one concrete thing: **optimizing a quantitative trading strategy**.

It is a **minimal** example: distill the strategy research loop into just two organs — **one editable strategy + one fixed backtest scorer** — and then use Heuristic Learning (HL) to push the score higher, one round at a time.

What's kept here is a **generic, minimal demo**: a simple strategy and a fixed backtester, showing how HL organizes the "propose a hypothesis → modify the strategy → evaluate against a fixed scorer → accept/reject" loop. The actual strategy, stock pool, data source, trading constraints, and scoring gates all need to be redesigned for your own research goals. This repository is **not** investment advice.

## Core Paradigm: Fixed Evaluator + Single Editable Program

```
        ┌─────────────────┐   edit it   ┌──────────────────┐
  HL →  │   strategy.py   │ ──────────▶ │   backtest.py    │ ──▶  one score
        │  only editable  │   read-only │  fixed evaluator  │      (score)
        └─────────────────┘            └──────────────────┘
```

- **`strategy.py`** — the single source of strategy semantics. HL is **only allowed to edit this one file**: propose hypotheses, change logic, tune parameters.
- **`backtest.py`** — the fixed evaluation pipeline. Pull data, simulate fills, compute metrics, output **one score**. Once fixed it **must not change** — otherwise you "tweak the evaluator to inflate the score" and candidates are no longer comparable.

Every candidate is scored with the same command, the same data, and the same scoring formula, so "is this version actually better?" becomes an objective, rankable question.

The score uses the **Sortino ratio**, compressing a strategy's downside-risk-adjusted return into a single scalar:

```
score = Sortino
```

> [!NOTE]
> The full design behind the paradigm is in [`docs/design/heuristic-exploration-framework.md`](docs/design/heuristic-exploration-framework.md).

## Quick Start

<details>
<summary>🔑 Configure data credentials</summary>

The example backtest defaults to pulling daily bars from [JoinQuant JQData](https://www.joinquant.com/help/api/doc?name=JQDatadoc), purely to demonstrate the data interface and the fixed evaluation pipeline; real projects can swap in their own data source. Do not hardcode account/password into code or commit them into the repo — pass them via environment variables:

```bash
export JOINQUANT_ACCOUNT=<your JoinQuant account>
export JOINQUANT_PASSWORD=<your JoinQuant password>
```

</details>

<details>
<summary>📦 Install dependencies</summary>

Install dependencies from `requirements.txt`:

```bash
pip install -r requirements.txt
```

</details>

<details>
<summary>▶️ Run a backtest</summary>

```bash
cd example
python backtest.py
```

</details>

## How it works

<details>
<summary>🧭 The HL loop</summary>

Heuristic Learning is a structured reasoning loop — each round proposes one **economically meaningful** hypothesis, edits only the strategy file, scores it with the fixed evaluator, and **keeps it only if strictly better**:

```
Probe (run baseline) → Diagnose (find the weakness) → Propose (one economically grounded hypothesis)
   → Patch (edit only strategy.py) → Evaluate (fixed evaluator scores it) → Decide (keep only if strictly better)
```

Two hard rules:

1. **Only edit `strategy.py`** — the evaluator / data source / scoring formula stay untouched.
2. **Only strictly better counts** — a candidate whose score is not strictly above baseline is not kept; narrow dead-zone overfitting (digging 1–2-point-wide pits on continuous variables) is rejected.

</details>

<details>
<summary>📈 Demo: HL trial ledger</summary>

Run it under the discipline of [`skills/hl-quant/SKILL.md`](skills/hl-quant/SKILL.md): the fixed evaluator stays put, only `strategy.py` changes, and every round leaves evidence, a judgment, and a decision.

Fixed command:

```bash
cd example
python backtest.py
```

This round backtests the Shanghai Composite Index (`000001.XSHG`), over `2025-03-01 ~ 2026-02-28`; buy-and-hold over the same window returns about **+25.50%**.

| HL step | Evidence | Judgment | Action |
| --- | --- | --- | --- |
| **Probe** | Baseline 5/10: score 0.7545, total return +5.46%, win rate 41.67%, 12 trades | Captured only a sliver of the index's gain; many trades, low quality | Keep the evaluator fixed, move to Diagnose |
| **Diagnose** | 12 trades, low win rate, return far below buy-and-hold | 5/10 MAs too sensitive — whipsawed in choppy ranges, exited too early | Focus on the "MA sensitivity" variable |
| **Propose** | In trending markets, slower MAs usually filter intraday noise | Slowing 5/10 to 10/20 has economic meaning, not a narrow-pit dig | Propose only this one parameter change |
| **Patch** | `strategy.py` is the only editable program | Evaluator, data source, scoring formula untouched | `SHORT_WINDOW: 5 → 10`, `LONG_WINDOW: 10 → 20` |
| **Evaluate** | 10/20: score 2.0615, total return +17.33%, win rate 57.14%, 7 trades | Score strictly higher; return, Sharpe, drawdown, win rate all improve together | Candidate enters acceptance check |
| **Replay** | 10/30, 20/60 score even higher, but only 2 / 1 trade left | Sample size too small — looks like landing on this particular regime | Reject chasing the highest score |
| **Decide** | 10/20 scores higher and trade count is still acceptable | Improvement is more credible than 10/30, 20/60 | **Accept 10/20** |

The actual patch is just two parameters:

```python
SHORT_WINDOW = 10   # baseline 5
LONG_WINDOW = 20    # baseline 10
```

Rerunning the fixed evaluator outputs:

```
params  SHORT_WINDOW=10  LONG_WINDOW=20
------------------------------------------------
  Total return : +17.33%
  Annualized   : +18.19%
  Sharpe       : 1.839
  Sortino      : 2.062
  Max drawdown : 6.71%
  Win rate     : 57.14%  (7 trades)
------------------------------------------------
  >>> SCORE    : 2.0615
```

Candidate evidence table:

| Candidate | Score / Sortino | Total return | Sharpe | Max drawdown | Win rate | Trades | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| 5/10 baseline | 0.7545 | +5.46% | 0.698 | 7.10% | 41.67% | 12 | baseline |
| 10/20 | 2.0615 | +17.33% | 1.839 | 6.71% | 57.14% | 7 | accept |
| 10/30 | 2.2579 | +19.24% | 2.017 | 4.94% | 100.00% | 2 | reject: too few samples |
| 20/60 | 2.0898 | +17.93% | 1.915 | 5.01% | 100.00% | 1 | reject: too few samples |

</details>

## Install the Skill

The loop above is packaged as a reusable [Agent Skill](skills/hl-quant/SKILL.md). Install it into your own agent (Claude Code / Cursor, etc.) in one command with [`npx skills`](https://github.com/vercel-labs/skills):

```bash
npx skills add toddwyl/hl-quant
```

Once installed, tell the agent "optimize this strategy with heuristic exploration" to trigger it. It will iterate under the discipline of `Probe → Diagnose → Propose → Patch → Evaluate → Decide` — editing only the strategy file, with strict gates and anti-overfitting guards.

## Repository Layout

```
hl-quant/
├── README.md
├── requirements.txt    # pip dependencies (the repo ships no virtual env)
├── example/
│   ├── strategy.py     # the only editable program (HL edits here)
│   └── backtest.py     # fixed evaluator (pull demo data → simulate → score)
├── skills/
│   └── hl-quant/SKILL.md            # npx-installable heuristic-exploration skill
└── docs/
    └── design/heuristic-exploration-framework.md   # the full design behind the paradigm
```

## WeChat Group

A WeChat group for Chinese-speaking users. Scan to join and discuss heuristic learning, quant strategies, and agent workflows:

<div align="center">
<img src="docs/images/wechat-group.png" alt="WeChat group QR code" width="240">
</div>

> [!NOTE]
> The group QR code is refreshed periodically; if it has expired, please leave a note in Issues.

## Star History

<a href="https://star-history.com/#toddwyl/hl-quant&Date">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=toddwyl/hl-quant&type=Date&theme=dark" />
    <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=toddwyl/hl-quant&type=Date" />
    <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=toddwyl/hl-quant&type=Date" width="600" />
  </picture>
</a>

## References

Weng, J. (2026). *Learning Beyond Gradients*. https://trinkle23897.github.io/learning-beyond-gradients/

Karpathy, A. (2025). *auto-research*. https://github.com/karpathy/autoresearch
