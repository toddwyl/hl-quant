"""策略程序 —— 唯一可编辑文件（the single editable program）。

启发式学习 / 启发式探索（HL）**只允许修改本文件**；回测器 `backtest.py`
（固定评估器）保持不动。这样每个候选策略都在同一口径下可比，避免「改了评估器
把分数刷上去」的自欺。

原始想法（来自聚宽「双均线」demo）：
    五日均线在十日均线上方 → 满仓买入；下方 → 清仓卖出。

HL 循环要做的，就是在这里提出假设、改逻辑/调参数，再用 `backtest.py` 打分，
只有分数严格高于基线才保留。
"""

from __future__ import annotations

import pandas as pd

# —— 可调参数：启发式探索的搜索空间 ——
SHORT_WINDOW = 5    # 快线窗口 n1
LONG_WINDOW = 10    # 慢线窗口 n2
TREND_WINDOW = 60   # 趋势/regime 过滤窗口：只在价格站上长期均线时才做多


def decide(closes: pd.Series) -> str:
    """给出当前交易日的目标信号。

    输入：截至当前交易日（含今日收盘）的收盘价序列。
    输出：``"buy"``（目标满仓）/ ``"sell"``（目标空仓）/ ``"hold"``（维持现状）。

    纯函数：不读数据、不下单、不依赖任何外部状态——只看价格、只给信号。
    回测器负责把信号翻译成成交、成本与净值。

    规则（HL 第 1 轮：在原始双均线上叠加趋势过滤）：
    - 快线上穿慢线 **且** 收盘价站上长期均线 → 满仓做多；
    - 快线下穿慢线 **或** 收盘价跌破长期均线（趋势走坏）→ 清仓。
      趋势过滤的经济含义：下行趋势里不接飞刀，避开熊市反弹的假信号。
    """
    if len(closes) < TREND_WINDOW:
        return "hold"

    ma_short = closes.iloc[-SHORT_WINDOW:].mean()
    ma_long = closes.iloc[-LONG_WINDOW:].mean()
    ma_trend = closes.iloc[-TREND_WINDOW:].mean()
    price = closes.iloc[-1]

    regime_up = price > ma_trend

    if ma_short > ma_long and regime_up:
        return "buy"
    if ma_short < ma_long or not regime_up:
        return "sell"
    return "hold"
