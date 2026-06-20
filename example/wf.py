"""Walk-forward evaluation —— 升级版固定评估协议（anti-overfit）。

原始演示只做一次 70/30 切分（单个 OOS 样本），且接受门槛会在「负分」「3 笔」
上误报。本模块把固定评估器升级为**滚动前推（walk-forward）**协议：

- 每个 train 窗口上重新挑选最优 MA 配置（adaptive），应用到**下一段未见过的
  test 窗口**；测的是「挑参流程本身能否泛化」，而不是「某个幸运配置」。
- 用标准下行半偏差 Sortino（MAR=0，与 backtest 一致）做每 fold 的 OOS 打分。
- 同时记录买入持有（B&H）的 OOS Sortino 作基准。
- 严格部署门槛：OOS Sortino 中位数 > 0，且均值 > B&H 均值，且 >= 50% fold 跑赢
  B&H，且 OOS 总笔数 >= 阈值。

只读 strategy / backtest，不改它们的评分口径。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

import backtest

# 注意：本模块是 round-1 的「MA 窗口搜索」专用 harness，自带 MA 仿真，**不依赖**
# 当前 strategy.py 的 decide（policy 已在 round-2 切到 RSI）。这样 E1-E4 的 MA
# 结果与现行 policy 无关，始终可复现。policy-agnostic 的候选擂台见 run_candidates.py。


def _ma(close: pd.Series, n: int) -> pd.Series:
    return close.rolling(n).mean()


def _sortino(returns: pd.Series, periods: int = 252) -> float:
    """与 backtest._compute_metrics 一致的标准 Sortino（MAR=0）。"""
    r = returns.dropna()
    if len(r) < 2:
        return 0.0
    downside = r.clip(upper=0.0)
    dd = math.sqrt(float((downside ** 2).mean()))
    if dd <= 0:
        return 0.0
    return float(r.mean()) / dd * math.sqrt(periods)


def bh_metrics(prices: pd.DataFrame) -> tuple[float, float]:
    """买入持有的 (OOS Sortino, 总收益)。"""
    closes = prices["close"].reset_index(drop=True)
    ret = closes.pct_change().dropna()
    total = float(closes.iloc[-1] / closes.iloc[0] - 1.0)
    return _sortino(ret), total


def eval_window(prices: pd.DataFrame, short: int, long_: int):
    """把 (short, long) 双均线当作 standalone 窗口评估（与 round-1 口径一致：
    信号用窗口内已完成 bar，成交在次日开盘）。自带仿真，不动 strategy.py。"""
    opens = prices["open"].reset_index(drop=True)
    closes = prices["close"].reset_index(drop=True)
    target = (_ma(closes, short) > _ma(closes, long_)).to_numpy()
    cash, shares, entry = backtest.INITIAL_CASH, 0.0, 0.0
    eq, trades = [], []
    for j in range(len(closes)):
        want = bool(target[j - 1]) if j > 0 else False
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


def select_on_train(train, candidates, baseline, min_trades_train):
    """train 上挑配置：score 严格 > 基线且笔数达标的取最高分；否则退回基线。"""
    base = eval_window(train, *baseline)
    best = None
    best_score = base.score
    for s, l in candidates:
        if (s, l) == baseline:
            continue
        m = eval_window(train, s, l)
        if m.score > best_score and m.trade_count >= min_trades_train:
            best, best_score = (s, l), m.score
    return best if best is not None else baseline, base.score


@dataclass
class WFResult:
    asset: str
    n_folds: int
    oos_score_mean: float
    oos_score_median: float
    oos_ret_mean: float
    bh_score_mean: float
    bh_ret_mean: float
    frac_beat_bh: float
    frac_pos_ret: float
    total_trades: int
    deploy: bool
    folds: list


def walk_forward(
    asset: str,
    prices: pd.DataFrame,
    candidates,
    baseline=(5, 10),
    train_len: int = 504,
    test_len: int = 126,
    step: int = 126,
    min_trades_train: int = 5,
    min_total_trades: int = 20,
) -> WFResult:
    n = len(prices)
    folds = []
    start = 0
    while start + train_len + test_len <= n:
        train = prices.iloc[start:start + train_len].reset_index(drop=True)
        test = prices.iloc[start + train_len:start + train_len + test_len].reset_index(drop=True)
        pick, base_train_score = select_on_train(train, candidates, baseline, min_trades_train)
        m = eval_window(test, *pick)
        bh_s, bh_r = bh_metrics(test)
        folds.append({
            "fold": len(folds),
            "picked": f"{pick[0]}/{pick[1]}",
            "oos_score": round(m.score, 4),
            "oos_return": round(m.total_return, 4),
            "oos_trades": m.trade_count,
            "bh_score": round(bh_s, 4),
            "bh_return": round(bh_r, 4),
            "beat_bh": bool(m.score > bh_s),
        })
        start += step

    if not folds:
        return WFResult(asset, 0, 0, 0, 0, 0, 0, 0, 0, 0, False, [])

    scores = [f["oos_score"] for f in folds]
    rets = [f["oos_return"] for f in folds]
    bh_scores = [f["bh_score"] for f in folds]
    bh_rets = [f["bh_return"] for f in folds]
    total_trades = sum(f["oos_trades"] for f in folds)
    frac_beat = sum(f["beat_bh"] for f in folds) / len(folds)
    frac_pos = sum(1 for r in rets if r > 0) / len(folds)

    s_mean = sum(scores) / len(scores)
    s_med = sorted(scores)[len(scores) // 2]
    bh_mean = sum(bh_scores) / len(bh_scores)

    deploy = (
        s_med > 0
        and s_mean > bh_mean
        and frac_beat >= 0.5
        and total_trades >= min_total_trades
    )

    return WFResult(
        asset=asset,
        n_folds=len(folds),
        oos_score_mean=s_mean,
        oos_score_median=s_med,
        oos_ret_mean=sum(rets) / len(rets),
        bh_score_mean=bh_mean,
        bh_ret_mean=sum(bh_rets) / len(bh_rets),
        frac_beat_bh=frac_beat,
        frac_pos_ret=frac_pos,
        total_trades=total_trades,
        deploy=deploy,
        folds=folds,
    )
