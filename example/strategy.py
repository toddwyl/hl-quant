"""策略程序 —— 唯一可编辑文件（the single editable program）。

启发式学习 / 启发式探索（HL）**只允许修改本文件**；回测器 `backtest.py`
（固定评估器）保持不动。这样每个候选策略都在同一口径下可比，避免「改了评估器
把分数刷上去」的自欺。

原始想法（来自聚宽「双均线」demo）：
    短期均线在长期均线上方 → 满仓买入；下方 → 清仓卖出。

HL 循环要做的，就是在这里提出假设、改逻辑/调参数，再用 `backtest.py` 打分，
只有分数严格高于基线才保留。

本文件当前状态 = HL 第 1 轮接受的候选：
    把窗口从基线的 (5, 10) 放慢到 (10, 20)。
    经济含义：5/10 太灵敏，在震荡里频繁翻转、过早离场、空耗手续费；放慢均线
    可以滤掉日间噪声、把趋势拿得更久。在上证指数上六项指标全面变好（见 README）。
"""

from __future__ import annotations

import pandas as pd

# —— 可调参数：启发式探索的搜索空间 ——
SHORT_WINDOW = 10   # 快线窗口 n1（基线 5）
LONG_WINDOW = 20    # 慢线窗口 n2（基线 10）


def decide(closes: pd.Series) -> str:
    """给出当前交易日的目标信号。

    输入：截至当前交易日（含今日收盘）的收盘价序列。
    输出：``"buy"``（目标满仓）/ ``"sell"``（目标空仓）/ ``"hold"``（维持现状）。

    纯函数：不读数据、不下单、不依赖任何外部状态——只看价格、只给信号。
    回测器负责把信号翻译成成交、成本与净值。
    """
    if len(closes) < LONG_WINDOW:
        return "hold"

    ma_short = closes.iloc[-SHORT_WINDOW:].mean()
    ma_long = closes.iloc[-LONG_WINDOW:].mean()

    if ma_short > ma_long:
        return "buy"
    if ma_short < ma_long:
        return "sell"
    return "hold"
