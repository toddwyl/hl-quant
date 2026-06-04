---
name: hl-quant
description: Use when optimizing a trading strategy through heuristic learning — diagnosing strategy weakness, proposing economically-grounded hypotheses, patching the strategy file, evaluating with a fixed backtest scorer, and deciding whether to accept based on strict multi-metric gates. Triggers on "启发式探索", "启发式学习", "HL循环", "策略调参", "回测改进", "优化策略分数", "heuristic exploration", "heuristic learning".
---

# Heuristic Exploration for Quantitative Strategy Optimization

Iteratively improve a trading strategy by running a fixed backtest scorer, diagnosing failures, proposing one economically-grounded hypothesis at a time, and accepting only candidates that are strictly better across all key metrics.

**Reference:** The full framework design is in [`docs/design/heuristic-exploration-framework.md`](../../docs/design/heuristic-exploration-framework.md).

## When to Use

- Strategy underperforms (low Sharpe, high drawdown, low win rate)
- Want to improve strategy score / return / risk-adjusted metrics
- Need to diagnose *why* a strategy fails (not just that it fails)
- Evaluating whether a parameter change is genuine improvement or overfitting

## When NOT to Use

- Pure numerical parameter search within a fixed space → use Optuna / grid search instead
- Strategy logic is already frozen and only needs deployment
- No fixed evaluator exists yet → build one first

## Core Loop

```
Probe → Diagnose → Propose → Patch → Evaluate → Replay → Decide → Compress
```

1. **Probe**: Run the fixed evaluator, get baseline score + all metrics + attribution artifacts.
2. **Diagnose**: Analyze *why* it's weak — not just "score is low". Identify failure mode: bad entries? premature exits? wrong regime? concentration risk? whipsaw in noise?
3. **Propose**: One hypothesis with **economic/market logic** (not data mining). Example: "slow MAs filter noise better in trending markets" — not "MA=17 gives highest score".
4. **Patch**: Edit **ONLY** the strategy file. Never touch the evaluator, data source, or scoring formula.
5. **Evaluate**: Run the same fixed evaluator. Compare score + all key metrics vs baseline.
6. **Replay**: Check golden cases / live constraints aren't broken by the change.
7. **Decide**: Pass the strict multi-metric gate → accept. Otherwise → reject and return to Diagnose.
8. **Compress**: Remove zero-trigger / negative-contribution rules. Keep the strategy small and interpretable. Never infinitely stack if-else patches.

## Fixed Evaluator + Single Editable Program

This is the foundation of comparability. Every candidate runs through the **same** pipeline:

```
same data → same backtest engine → same cost model → same scoring formula → one score
```

**Only the strategy file is editable.** If you change the evaluator to "make the score go up", scores become incomparable and the entire loop is self-deception.

If the evaluator infrastructure breaks (auth fails, data gap, engine crash) → **stop and report the blocker**. Never work around it by modifying the baseline.

## Acceptance Gate (Strict)

A candidate MUST pass ALL of the following — no partial acceptance:

| Metric | Requirement |
|--------|-------------|
| **score** (primary) | strictly higher than baseline |
| total return | not degraded |
| annualized return | not degraded |
| Sharpe ratio | not degraded |
| max drawdown | not worse |
| win rate | not significantly worse |
| trade count | sufficient for statistical validity |

**Score up but a key metric collapsed → REJECT.** A higher score from one lucky trade is not improvement.

## Anti-Overfitting Rules (Mandatory)

### 1. Every Change Must Have Economic / Market Logic

Strategy modifications must be explainable in terms of market behavior, not just "this number gave a higher score":

| Change | Economic logic | Verdict |
|--------|---------------|---------|
| Slow MA from 5/10 to 10/20 | Filters intraday noise, holds trends longer | ✅ |
| Add trend filter (price > 60-day MA) | Avoids buying in downtrend regime | ✅ |
| MFI dead zone 72-73 | Why 72-73 specifically? No market explanation | ❌ |
| Tighten stop-loss from 10% to 8.2% | Why 8.2% exactly? Sounds like curve-fitting | ❌ |

### 2. No Narrow-Pit Filtering on Continuous Variables

**FORBIDDEN**: 1-2 point wide dead zones on MFI, RSI, volume ratio, etc.

```python
# ❌ OVERFITTING: Why 57-58 but not 56-57? No economic explanation.
ENTRY_MFI_DEAD_ZONE_MIN = 57.0
ENTRY_MFI_DEAD_ZONE_MAX = 58.0

# ✅ ACCEPTABLE: Continuous interval with clear economic meaning
ENTRY_MFI_DEAD_ZONE_MIN = 60.0  # "MFI 60-66 = capital flow hesitation zone"
ENTRY_MFI_DEAD_ZONE_MAX = 66.0
```

Filters must be (a) continuous intervals with economic meaning, or (b) rule-level switches.

### 3. No Future Information

- Entry signals use only completed bar data
- Orders execute at next bar's open (or a deterministic fill rule)
- Never use same-day incomplete high/low/amplitude to filter entries

### 4. Sufficient Sample Size

High score with 1-2 trades is likely luck, not a robust edge. Require enough trades for statistical validity. A strategy that trades once and wins 100% is **not** better than one that trades 50 times with 60% win rate.

### 5. Train / Validation Discipline

When a stock pool or time split is available:

- **Training split**: Used freely during search
- **Validation split**: Evaluated every trial but **NEVER used to guide search direction** — observing validation degradation to reject overfitting is allowed; tuning parameters to maximize validation score is data leakage
- **Final holdout**: Run once only after candidate is frozen. If holdout loses to baseline → do not deploy

Monitor generalization health:

| Indicator | Healthy | Warning | Reject |
|-----------|---------|---------|--------|
| train score − validation score | < 0.5 | 0.5 ~ 1.0 | > 1.0 |
| train return / validation return | 0.7 ~ 1.3 | 0.5 ~ 0.7 or 1.3 ~ 2.0 | < 0.5 or > 2.0 |

A candidate in "Reject" zone fails even if it passes the hard gates — train/validation divergence indicates overfitting.

## How to Improve Generalization

1. **Prefer structural changes over parameter tweaks**: Adding a regime filter (trend vs. range) generalizes better than tuning a threshold from 7.2% to 7.8%.
2. **One variable per iteration**: Change one thing, evaluate, attribute. Multiple simultaneous changes make failure unattributable and success unrepeatable.
3. **Compress after accepting**: Remove rules that don't trigger, merge overlapping conditions, keep the strategy small and interpretable. A 50-rule strategy that could be 10 rules is overfitting in structural form.
4. **Replay golden cases**: Freeze real failure scenarios as fixtures. New candidates must pass them — no regressions in live constraints (T+1, position limits, price validity, etc.).
5. **Don't chase the highest score**: Stop at the candidate where all metrics improve and trade count is healthy, not at the one with the absolute highest score but 1-2 trades.

## Workflow Example

```
# 1. Probe baseline
python backtest.py
# → score 0.39, return +5.5%, Sharpe 0.70, drawdown 7.1%, 12 trades

# 2. Diagnose
#    "MA 5/10 too sensitive — whipsawed in and out, only captured 5.5% of 25.5% index gain"

# 3. Propose hypothesis
#    "Slow MAs to 10/20: filters noise, holds trends longer. Continuous sensitivity adjustment, not a narrow dead zone."

# 4. Patch strategy.py: SHORT_WINDOW=10, LONG_WINDOW=20

# 5. Evaluate
python backtest.py
# → score 1.22, return +17.3%, Sharpe 1.84, drawdown 6.7%, 7 trades

# 6. Decide: ALL metrics improved → ACCEPT

# 7. Compress: No redundant rules to remove. Strategy stays minimal.
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Modifying evaluator to boost score | Only edit the strategy file |
| Adding narrow dead zones on continuous vars | Use continuous intervals with economic meaning |
| Accepting based on score alone | Must pass ALL key metrics |
| Tuning parameters to maximize validation score | Validation is for checking, not optimizing — that's data leakage |
| High score with 1-2 trades | Require sufficient sample size |
| Using future information for entry signals | Only use completed bar data |
| Stacking patches without compression | After accepting, remove zero-trigger rules, keep strategy small |
| Multiple changes per iteration | One hypothesis per cycle for clean attribution |
| Ignoring train/validation divergence | Score gap > 1.0 = overfitting, reject even if gates pass |

## Overfitting Failure Case Study (from Production)

A production search branch added 4 narrow MFI dead zones (57-58, 68-69, 72-73, 74-76) and achieved score 3.18 / win rate 69% / drawdown 6.7%. **Rejected** because:

1. No economic explanation for why those specific 1-point ranges are bad
2. 1-point bandwidth means any market microstructure change invalidates them
3. Fragmented filtering destroyed interpretability of the original MFI 60-66 "hesitation zone"
4. Score jump (2.73→3.18) came from excluding tiny noise — unstable out-of-sample
5. **Generalization failure**: Such narrow filtering would almost certainly fail on a validation split — the excluded points are noise artifacts of the training stock pool

The alternative approach achieved score 2.94 with only 2 minimal, well-justified changes and ALL 6 metrics strictly improved. **Less is more when each change has clear economic logic.**
