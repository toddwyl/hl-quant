"""HL 候选擂台：把 finance 工程里的几套策略思想（SMA 交叉 / RSI 均值回归 /
MACD 动量 / 突破 Donchian / 趋势过滤）蒸馏进 decide 接口，用同一套 walk-forward
严格门槛逐一证伪，挑出能更新 heuristic policy 的赢家。

每个候选 = 一个「目标多空」布尔序列函数（只用截至当根收盘的信息，成交在次日开盘，
无未来函数）。指标在全序列上一次性向量化算好，仿真按段切片，避免 O(n^2)。

运行：python run_candidates.py
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

import backtest  # noqa: E402
import wf  # noqa: E402
from run_experiments import BASKET, load  # noqa: E402

TRAIN_LEN, TEST_LEN, STEP = 504, 126, 126
MIN_TOTAL_TRADES = 20


# ----------------------------------------------------------------------
# 候选：close 序列 → 目标持有布尔数组（True=想做多）。只用过去/当前已完成 bar。
# ----------------------------------------------------------------------
def _ma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n).mean()


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / down.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _macd(close: pd.Series, fast=12, slow=26, signal=9):
    ema_f = close.ewm(span=fast, adjust=False).mean()
    ema_s = close.ewm(span=slow, adjust=False).mean()
    line = ema_f - ema_s
    sig = line.ewm(span=signal, adjust=False).mean()
    return line, sig


def _hysteresis(enter: pd.Series, exit_: pd.Series) -> np.ndarray:
    """状态机：enter 触发进多，exit 触发离场，否则维持。"""
    e = enter.to_numpy(); x = exit_.to_numpy()
    out = np.zeros(len(e), dtype=bool)
    state = False
    for i in range(len(e)):
        if e[i]:
            state = True
        elif x[i]:
            state = False
        out[i] = state
    return out


def cand_ma(close, short=10, long_=20):
    return (_ma(close, short) > _ma(close, long_)).to_numpy()


def cand_ma_trend(close, short=10, long_=20, trend=200):
    base = _ma(close, short) > _ma(close, long_)
    up = close > _ma(close, trend)
    return (base & up).to_numpy()


def cand_rsi(close, period=14, lo=30, hi=70):
    r = _rsi(close, period)
    return _hysteresis(r < lo, r > hi)


def cand_macd(close, **kw):
    line, sig = _macd(close)
    return (line > sig).to_numpy()


def cand_donchian(close, n=50):
    hi = close.rolling(n).max()
    lo = close.rolling(n).min()
    return _hysteresis(close >= hi, close <= lo)


CANDIDATES = {
    "ma_10_20 (baseline)": cand_ma,
    "ma_trend_200": cand_ma_trend,
    "rsi_mr_14": cand_rsi,
    "macd_mom": cand_macd,
    "donchian_50": cand_donchian,
}


# ----------------------------------------------------------------------
# 仿真：在 [a,b) 段上按 target 持有，成交在次日开盘，复用 backtest 成本与指标。
# ----------------------------------------------------------------------
def sim_segment(opens, closes, target, a, b):
    cash = backtest.INITIAL_CASH
    shares = 0.0
    entry = 0.0
    eq = []
    trades = []
    for j in range(a, b):
        want = bool(target[j - 1]) if j > 0 else False  # 用昨日已完成信号
        px = float(opens.iloc[j])
        if want and shares == 0.0:
            comm = max(cash * backtest.COMMISSION_RATE, backtest.MIN_COMMISSION)
            shares = (cash - comm) / px
            entry = cash
            cash = 0.0
        elif not want and shares > 0.0:
            proceeds = shares * px
            comm = max(proceeds * backtest.COMMISSION_RATE, backtest.MIN_COMMISSION)
            tax = proceeds * backtest.STAMP_TAX_RATE
            cash = proceeds - comm - tax
            trades.append(cash - entry)
            shares = 0.0
        eq.append(cash + shares * float(closes.iloc[j]))
    return backtest._compute_metrics(eq, trades)


def walk_forward_candidate(prices, target):
    opens = prices["open"].reset_index(drop=True)
    closes = prices["close"].reset_index(drop=True)
    n = len(prices)
    folds = []
    start = 0
    while start + TRAIN_LEN + TEST_LEN <= n:
        ts, te = start + TRAIN_LEN, start + TRAIN_LEN + TEST_LEN
        m = sim_segment(opens, closes, target, ts, te)
        seg = prices.iloc[ts:te].reset_index(drop=True)
        bh_s, _ = wf.bh_metrics(seg)
        folds.append((m.score, m.total_return, m.trade_count, bh_s))
        start += STEP
    return folds


def aggregate(folds):
    if not folds:
        return None
    scores = [f[0] for f in folds]
    rets = [f[1] for f in folds]
    trades = sum(f[2] for f in folds)
    beat = sum(1 for f in folds if f[0] > f[3]) / len(folds)
    bh_mean = sum(f[3] for f in folds) / len(folds)
    s_mean = sum(scores) / len(scores)
    s_med = sorted(scores)[len(scores) // 2]
    deploy = (s_med > 0 and s_mean > bh_mean and beat >= 0.5 and trades >= MIN_TOTAL_TRADES)
    return dict(n=len(folds), s_mean=s_mean, s_med=s_med, r_mean=sum(rets) / len(rets),
                bh_mean=bh_mean, beat=beat, trades=trades, deploy=deploy)


def main():
    # 预拉所有资产
    assets = []
    for ticker, start in BASKET:
        try:
            assets.append((ticker, load(ticker, start)))
        except SystemExit:
            pass

    print(f"候选擂台：{len(assets)} 资产 × walk-forward "
          f"(train {TRAIN_LEN}d / test {TEST_LEN}d / step {STEP}d)")
    print("严格门槛：OOS Sortino 中位>0 且 均值>B&H 且 ≥50% fold 跑赢 B&H 且 OOS笔数≥20\n")

    summary = {}
    for name, fn in CANDIDATES.items():
        passes = 0
        agg_scores = []
        agg_beat = []
        for ticker, prices in assets:
            target = fn(prices["close"].reset_index(drop=True))
            agg = aggregate(walk_forward_candidate(prices, target))
            if agg is None:
                continue
            passes += agg["deploy"]
            agg_scores.append(agg["s_mean"])
            agg_beat.append(agg["beat"])
        summary[name] = dict(
            pass_n=passes,
            mean_oos_sortino=sum(agg_scores) / len(agg_scores),
            mean_beat_bh=sum(agg_beat) / len(agg_beat),
        )

    print(f"{'candidate':<22}{'assets pass gate':<18}{'mean OOS Sortino':<18}{'mean %beat B&H'}")
    print("-" * 76)
    ranked = sorted(summary.items(), key=lambda kv: (kv[1]["pass_n"], kv[1]["mean_beat_bh"]), reverse=True)
    for name, s in ranked:
        print(f"{name:<22}{str(s['pass_n'])+'/'+str(len(assets)):<18}"
              f"{s['mean_oos_sortino']:<+18.3f}{s['mean_beat_bh']:.0%}")

    win = ranked[0]
    print(f"\n>>> 赢家：{win[0]}  "
          f"(过门槛 {win[1]['pass_n']}/{len(assets)}，"
          f"mean %beat B&H {win[1]['mean_beat_bh']:.0%})")
    return ranked


if __name__ == "__main__":
    main()
