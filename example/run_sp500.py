"""标普 500 演示：用修正后的固定评估器 + 训练/留出（holdout）纪律跑一轮 HL。

相对原始 README 演示，这里补上三处纪律，直接对应已修复的问题：

1. 固定评估器已修正同 bar 前视（信号用已完成 bar、成交在次日开盘）。
2. Sortino 改为标准下行半偏差口径（MAR=0）。
3. **训练/留出切分**：候选只在 train 上搜索与接受，冻结后在 holdout 上**只跑一次**。
   不再「在同一段数据上挑参数又汇报同一段数据的分数」。

数据用 yfinance 拉标普 500（^GSPC），无需任何账号。

运行：
    python run_sp500.py
"""

from __future__ import annotations

import os

# 必须在 import backtest 之前设好评估口径（backtest 在 import 时读取这些 env）。
os.environ.setdefault("HLQ_SOURCE", "yfinance")
os.environ.setdefault("HLQ_SECURITY", "^GSPC")
os.environ.setdefault("HLQ_START", "2022-01-01")
os.environ.setdefault("HLQ_END", "2026-02-28")

import backtest  # noqa: E402
import strategy  # noqa: E402

# 候选搜索空间（短窗, 长窗）。基线 = 5/10（聚宽双均线 demo 的原始参数）。
BASELINE = (5, 10)
CANDIDATES = [(5, 10), (10, 20), (10, 30), (20, 60), (15, 40)]

# 训练集占比（按时间切分，前段训练、后段留出）。
TRAIN_FRAC = 0.70

# 训练集上有效候选的最小交易笔数。单标的 ~3 年 train，双均线天然笔数不多，
# 按规模把 SKILL 默认 50 下调到 10，并在 run 开始前固定，避免临场心证。
MIN_TRADES_TRAIN = 10


def evaluate(prices, short, long_):
    """在给定窗口下跑固定评估器，返回 Metrics。"""
    strategy.SHORT_WINDOW = short
    strategy.LONG_WINDOW = long_
    return backtest.run_backtest(prices)


def buy_and_hold_return(prices) -> float:
    closes = prices["close"].reset_index(drop=True)
    return float(closes.iloc[-1] / closes.iloc[0] - 1.0)


def fmt_row(tag, m):
    return (f"| {tag:<10} | {m.score:>7.4f} | {m.total_return:>+7.2%} "
            f"| {m.sharpe_ratio:>6.3f} | {m.max_drawdown:>6.2%} "
            f"| {m.win_rate:>6.2%} | {m.trade_count:>3d} |")


def main() -> None:
    prices = backtest.load_prices()
    n = len(prices)
    split = int(n * TRAIN_FRAC)
    train = prices.iloc[:split].reset_index(drop=True)
    test = prices.iloc[split:].reset_index(drop=True)

    print(f"标的 {backtest.SECURITY}  区间 {backtest.START_DATE} ~ {backtest.END_DATE}")
    print(f"共 {n} 个交易日 → 训练 {len(train)} / 留出 {len(test)}  "
          f"(切分 {TRAIN_FRAC:.0%})")
    print(f"训练期买入持有 {buy_and_hold_return(train):+.2%}   "
          f"留出期买入持有 {buy_and_hold_return(test):+.2%}")

    base_train = evaluate(train, *BASELINE)

    # ---- 1) 训练集上搜索 ----
    print("\n=== 训练集（仅在此搜索/接受）===")
    print("| 候选       |   Score |   总收益 | Sharpe |  回撤 |   胜率 | 笔数 |")
    print("| ---------- | ------: | ------: | -----: | ----: | -----: | ---: |")
    results = {}
    for s, l in CANDIDATES:
        m = evaluate(train, s, l)
        results[(s, l)] = m
        tag = f"{s}/{l}" + ("*" if (s, l) == BASELINE else "")
        print(fmt_row(tag, m))

    # ---- 2) 接受门槛：score 严格 > 基线 且 笔数 >= 下限 ----
    passing = [
        (w, m) for w, m in results.items()
        if w != BASELINE
        and m.score > base_train.score
        and m.trade_count >= MIN_TRADES_TRAIN
    ]
    print(f"\n接受门槛：score > 基线({base_train.score:.4f}) 且 训练笔数 >= "
          f"{MIN_TRADES_TRAIN}")
    if not passing:
        print(">>> 没有候选通过训练集门槛 → 保留基线，不部署。")
        return

    best_w, best_m = max(passing, key=lambda x: x[1].score)
    print(f">>> 训练集选中候选 {best_w[0]}/{best_w[1]}  "
          f"(score {best_m.score:.4f} vs 基线 {base_train.score:.4f})")
    for w, m in passing:
        if w != best_w:
            print(f"    其余通过项 {w[0]}/{w[1]} score {m.score:.4f} "
                  f"({m.trade_count} 笔) —— 未选")

    # ---- 3) 留出集：冻结候选后只跑一次 ----
    print("\n=== 留出集（holdout，冻结后只跑一次）===")
    base_test = evaluate(test, *BASELINE)
    cand_test = evaluate(test, *best_w)
    print("| 配置       |   Score |   总收益 | Sharpe |  回撤 |   胜率 | 笔数 |")
    print("| ---------- | ------: | ------: | -----: | ----: | -----: | ---: |")
    print(fmt_row(f"{BASELINE[0]}/{BASELINE[1]} 基线", base_test))
    print(fmt_row(f"{best_w[0]}/{best_w[1]} 候选", cand_test))

    print()
    if cand_test.score > base_test.score:
        print(f">>> 留出集上候选 score {cand_test.score:.4f} > 基线 "
              f"{base_test.score:.4f} → 泛化成立，可部署。")
    else:
        print(f">>> 留出集上候选 score {cand_test.score:.4f} <= 基线 "
              f"{base_test.score:.4f} → 训练集优势未泛化，**不部署**（疑似过拟合）。")


if __name__ == "__main__":
    main()
