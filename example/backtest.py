"""固定评估器（fixed evaluator）—— 跑一次回测，得到一个分数。

职责：
1. 拉取（并缓存）日线 OHLC 数据；支持两个数据源：
   - 聚宽 JQData（默认，需要 JOINQUANT_ACCOUNT / JOINQUANT_PASSWORD）；
   - yfinance（设 HLQ_SOURCE=yfinance 或标的以 ``^`` 开头时自动启用），用于
     标普 500 等海外标的演示，无需账号。
2. 逐日调用 ``strategy.decide(...)``，模拟满仓/空仓切换、扣减手续费；
3. 计算 Sharpe / Sortino / 年化 / 最大回撤等指标，汇成**单一分数**。

评分口径：

    score = Sortino   （标准下行半方差口径，MAR=0）

⚠️ 本文件是固定评估口径，HL 循环**不允许修改**它。要提分只能改 strategy.py。
若评估器本身坏了（如认证失败、数据缺口），停下来报告，不要靠改基准绕过。

成交时点（无未来函数）：
    信号只用「截至昨日收盘」已完成的 bar 计算，成交发生在**今日开盘**。
    这样决策时点可得的信息与成交时点严格分离，避免「用今日收盘决策又按
    今日收盘成交」的同 bar 前视偏差。

运行：
    # A股（聚宽，默认）
    export JOINQUANT_ACCOUNT=...  JOINQUANT_PASSWORD=...
    python backtest.py

    # 标普500（yfinance，无需账号）
    HLQ_SOURCE=yfinance HLQ_SECURITY=^GSPC \
        HLQ_START=2022-01-01 HLQ_END=2026-02-28 python backtest.py
"""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from pathlib import Path

import pandas as pd

import strategy

# ============================================================
# 固定研究口径（FIXED —— 不要为了提分而修改）
# ============================================================
SECURITY = os.environ.get("HLQ_SECURITY", "000001.XSHG")  # 默认：上证指数
START_DATE = os.environ.get("HLQ_START", "2025-03-01")
END_DATE = os.environ.get("HLQ_END", "2026-02-28")
INITIAL_CASH = 1_000_000.0        # 初始资金
TRADING_DAYS_PER_YEAR = 252

# 数据源：auto / joinquant / yfinance。auto 时标的以 ^ 开头走 yfinance。
DATA_SOURCE = os.environ.get("HLQ_SOURCE", "auto").lower()

# 手续费口径：买卖佣金万分之三，卖出印花税千分之一，单边佣金最低 5 元
COMMISSION_RATE = 0.0003
STAMP_TAX_RATE = 0.001
MIN_COMMISSION = 5.0

CACHE_DIR = Path(__file__).parent / ".cache"


@dataclass
class Metrics:
    score: float
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown: float
    win_rate: float
    trade_count: int


# ------------------------------------------------------------
# 数据：认证 + 拉取 + 本地缓存（统一为含 open / close 两列）
# ------------------------------------------------------------
def _use_yfinance() -> bool:
    if DATA_SOURCE == "yfinance":
        return True
    if DATA_SOURCE == "joinquant":
        return False
    return SECURITY.startswith("^")  # auto


def load_prices() -> pd.DataFrame:
    """拉取日线，返回含 ``open`` / ``close`` 两列的 DataFrame；优先读本地缓存。"""
    CACHE_DIR.mkdir(exist_ok=True)
    src = "yf" if _use_yfinance() else "jq"
    cache_file = CACHE_DIR / f"{SECURITY}_{START_DATE}_{END_DATE}_{src}.pkl"
    if cache_file.exists():
        return pd.read_pickle(cache_file)

    df = _load_yfinance() if _use_yfinance() else _load_joinquant()
    if df is None or df.empty:
        raise SystemExit(f"未取到 {SECURITY} 在 {START_DATE}~{END_DATE} 的数据。")
    df = df[["open", "close"]].reset_index(drop=True)
    df.to_pickle(cache_file)
    return df


def _load_joinquant() -> pd.DataFrame:
    account = os.environ.get("JOINQUANT_ACCOUNT")
    password = os.environ.get("JOINQUANT_PASSWORD")
    if not account or not password:
        raise SystemExit(
            "缺少聚宽凭证。请先设置环境变量：\n"
            "  export JOINQUANT_ACCOUNT=<你的聚宽账号>\n"
            "  export JOINQUANT_PASSWORD=<你的聚宽密码>\n"
            "或改用免账号的 yfinance 源：HLQ_SOURCE=yfinance HLQ_SECURITY=^GSPC"
        )
    import jqdatasdk as jq

    jq.auth(account, password)
    return jq.get_price(
        SECURITY, start_date=START_DATE, end_date=END_DATE, frequency="daily"
    )


def _load_yfinance() -> pd.DataFrame:
    import yfinance as yf

    raw = yf.download(
        SECURITY,
        start=START_DATE,
        end=END_DATE,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if raw is None or raw.empty:
        return raw
    # yfinance 多标的时返回 MultiIndex 列，单标的时拍平
    if isinstance(raw.columns, pd.MultiIndex):
        raw.columns = raw.columns.get_level_values(0)
    return raw.rename(columns={"Open": "open", "Close": "close"})


# ------------------------------------------------------------
# 回测：逐日模拟满仓 / 空仓切换（信号用已完成 bar，成交在次日开盘）
# ------------------------------------------------------------
def run_backtest(prices: pd.DataFrame) -> Metrics:
    opens = prices["open"].reset_index(drop=True)
    closes = prices["close"].reset_index(drop=True)

    cash = INITIAL_CASH
    shares = 0.0
    entry_cost = 0.0          # 当前持仓的买入总成本（含手续费），用于胜率统计
    equity_curve: list[float] = []
    closed_trades: list[float] = []   # 每笔已平仓交易的盈亏

    for i in range(len(closes)):
        # 信号只用「截至昨日收盘」已完成的 bar；成交在今日开盘。
        # i == 0 时没有任何已完成 bar，保持空仓。
        signal = strategy.decide(closes.iloc[:i]) if i > 0 else "hold"
        exec_price = float(opens.iloc[i])

        if signal == "buy" and shares == 0.0:
            commission = max(cash * COMMISSION_RATE, MIN_COMMISSION)
            invest = cash - commission
            shares = invest / exec_price
            entry_cost = cash            # 全部现金投入
            cash = 0.0
        elif signal == "sell" and shares > 0.0:
            proceeds = shares * exec_price
            commission = max(proceeds * COMMISSION_RATE, MIN_COMMISSION)
            tax = proceeds * STAMP_TAX_RATE
            cash = proceeds - commission - tax
            closed_trades.append(cash - entry_cost)
            shares = 0.0
            entry_cost = 0.0

        # 净值按今日收盘标记
        equity_curve.append(cash + shares * float(closes.iloc[i]))

    return _compute_metrics(equity_curve, closed_trades)


def _compute_metrics(equity_curve: list[float], closed_trades: list[float]) -> Metrics:
    equity = pd.Series(equity_curve)
    n_days = len(equity)

    total_return = equity.iloc[-1] / INITIAL_CASH - 1.0
    annualized_return = (
        (1.0 + total_return) ** (TRADING_DAYS_PER_YEAR / n_days) - 1.0
        if n_days > 0
        else 0.0
    )

    daily_returns = equity.pct_change().dropna()
    mean_r = float(daily_returns.mean())
    std = float(daily_returns.std())
    sharpe = (
        mean_r / std * math.sqrt(TRADING_DAYS_PER_YEAR) if std > 0 else 0.0
    )

    # 标准 Sortino：目标下行半偏差（MAR=0），在**全部**周期上取 min(r,0)^2 的均方根，
    # 而不是「只取负收益子集再算样本标准差」。
    downside = daily_returns.clip(upper=0.0)
    downside_dev = math.sqrt(float((downside ** 2).mean())) if n_days > 1 else 0.0
    sortino = (
        mean_r / downside_dev * math.sqrt(TRADING_DAYS_PER_YEAR)
        if downside_dev > 0
        else 0.0
    )

    running_max = equity.cummax()
    drawdown = (equity - running_max) / running_max
    max_drawdown = float(-drawdown.min())   # 取正值

    wins = sum(1 for pnl in closed_trades if pnl > 0)
    win_rate = wins / len(closed_trades) if closed_trades else 0.0

    score = sortino

    return Metrics(
        score=score,
        total_return=total_return,
        annualized_return=annualized_return,
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        max_drawdown=max_drawdown,
        win_rate=win_rate,
        trade_count=len(closed_trades),
    )


def main() -> None:
    prices = load_prices()
    m = run_backtest(prices)
    print(f"标的 {SECURITY}  区间 {START_DATE} ~ {END_DATE}  "
          f"({len(prices)} 个交易日, 源={'yfinance' if _use_yfinance() else 'joinquant'})")
    print(f"参数  {getattr(strategy, 'PARAMS', '')}")
    print("-" * 48)
    print(f"  总收益     : {m.total_return:+.2%}")
    print(f"  年化收益   : {m.annualized_return:+.2%}")
    print(f"  Sharpe     : {m.sharpe_ratio:.3f}")
    print(f"  Sortino    : {m.sortino_ratio:.3f}")
    print(f"  最大回撤   : {m.max_drawdown:.2%}")
    print(f"  胜率       : {m.win_rate:.2%}  ({m.trade_count} 笔)")
    print("-" * 48)
    print(f"  >>> SCORE  : {m.score:.4f}")

    results_file = CACHE_DIR / "results.json"
    CACHE_DIR.mkdir(exist_ok=True)
    import json
    results_file.write_text(json.dumps(asdict(m), indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
