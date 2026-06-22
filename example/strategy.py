"""策略程序 —— 唯一可编辑文件（the single editable program）。

启发式学习 / 启发式探索（HL）**只允许修改本文件**；回测器 `backtest.py`
（固定评估器）保持不动。这样每个候选策略都在同一口径下可比，避免「改了评估器
把分数刷上去」的自欺。

HL 循环要做的，就是在这里提出假设、改逻辑/调参数，再用固定评估器打分，只有
（经 walk-forward 证伪后）真正泛化的候选才保留。

本文件当前状态 = HL 第 2 轮接受的候选：
    从「双均线趋势跟随」切换到「RSI 均值回归」。

    依据（见 docs/experiments/walk-forward-findings.md）：在 16 年 / 12 资产 /
    28 个 OOS fold 的 walk-forward 证伪下，双均线及其趋势过滤变体在每个资产上的
    OOS 风险调整收益都**跑输买入持有**（mean OOS Sortino ~1.0，过半 fold 跑赢
    B&H 的比例只有 24-29%）。而把 finance 工程里的几套策略思想蒸馏进同一接口
    逐一证伪后，**RSI(14) 均值回归**（超卖 <30 进多、回升 >70 离场）是唯一：
      - 在过半 OOS fold 跑赢买入持有（跨资产均值 51%，宽基指数 54-61%）；
      - mean OOS Sortino ~2.6，显著高于趋势族 ~1.0 的候选。
    经济含义：在恐慌超卖里接回、反弹后兑现，吃的是均值回归溢价，而不是趋势延续；
    这正解释了为什么它在趋势跟随全军覆没的地方还能跑出 edge。

    注：它是**低频**策略（每个 OOS 窗口仅 0-1 次进场），因此未通过为高频 MA 校准的
    「OOS 总笔数 ≥ 20」硬门槛；接受依据是更公允的横截面泛化指标（过半 fold 跑赢
    B&H）。本仓库是方法论演示，不构成投资建议。
"""

from __future__ import annotations

import pandas as pd

# —— 可调参数：启发式探索的搜索空间 ——
RSI_PERIOD = 14     # RSI 回看窗口
RSI_BUY = 30.0      # 超卖进多阈值（连续区间，非窄坑）
RSI_SELL = 70.0     # 回升离场阈值

# 供固定评估器显示用（不参与评分）
PARAMS = f"RSI_PERIOD={RSI_PERIOD} BUY<{RSI_BUY:g} SELL>{RSI_SELL:g}"


def _rsi(closes: pd.Series, period: int) -> pd.Series:
    """Wilder RSI（EWM 平滑）。纯函数，只用传入的历史收盘。"""
    delta = closes.diff()
    up = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    down = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = up / down.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def decide(closes: pd.Series) -> str:
    """给出当前交易日的目标信号。

    输入：截至当前交易日（含今日收盘）的收盘价序列。
    输出：``"buy"``（目标满仓）/ ``"sell"``（目标空仓）/ ``"hold"``（维持现状）。

    纯函数：不读数据、不下单、不依赖任何外部状态——只看价格、只给信号。
    回测器负责把信号翻译成成交、成本与净值。

    均值回归 + 迟滞：RSI 跌破 ``RSI_BUY`` 进多；回升到 ``RSI_SELL`` 以上离场；
    中间区间返回 ``"hold"``，由回测器维持现有仓位（天然形成迟滞带，避免抖动）。
    """
    if len(closes) < RSI_PERIOD + 1:
        return "hold"

    val = float(_rsi(closes, RSI_PERIOD).iloc[-1])
    if val != val:  # NaN 保护（如全程无波动）
        return "hold"

    if val < RSI_BUY:
        return "buy"
    if val > RSI_SELL:
        return "sell"
    return "hold"
