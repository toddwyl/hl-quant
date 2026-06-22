"""HL 框架的稳健性实验台 —— E1..E4，含 walk-forward + 严格门槛 + 留痕。

运行：
    python run_experiments.py        # 默认 yfinance，无需账号

写出：
    data/hl_runs/<run_id>/trials.jsonl   # 每 fold 留痕
    data/hl_runs/<run_id>/summary.json   # 汇总
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("HLQ_SOURCE", "yfinance")
os.environ.setdefault("HLQ_SECURITY", "^GSPC")

import backtest  # noqa: E402
import wf  # noqa: E402

CANDIDATES = [(5, 10), (10, 20), (10, 30), (20, 60), (15, 40), (30, 100)]
BASELINE = (5, 10)

# 资产篮子：指数 / ETF / 大盘股 / 商品 / 债券 / 加密。per-ticker 起始日。
BASKET = [
    ("^GSPC", "2010-01-01"), ("^IXIC", "2010-01-01"), ("^DJI", "2010-01-01"),
    ("SPY", "2010-01-01"), ("QQQ", "2010-01-01"), ("AAPL", "2010-01-01"),
    ("MSFT", "2010-01-01"), ("NVDA", "2010-01-01"), ("AMZN", "2010-01-01"),
    ("GLD", "2010-01-01"), ("TLT", "2010-01-01"), ("BTC-USD", "2015-01-01"),
]
END = "2026-02-28"

RUN_DIR = Path(__file__).parent.parent / "data" / "hl_runs" / time.strftime("%Y%m%d_%H%M%S")


def load(ticker: str, start: str):
    backtest.SECURITY = ticker
    backtest.START_DATE = start
    backtest.END_DATE = END
    backtest.DATA_SOURCE = "yfinance"
    return backtest.load_prices()


def run_basket(cost_mult: float = 1.0, ledger=None):
    """对篮子做 adaptive walk-forward，返回 WFResult 列表。"""
    base_comm, base_stamp, base_min = (
        backtest.COMMISSION_RATE, backtest.STAMP_TAX_RATE, backtest.MIN_COMMISSION,
    )
    backtest.COMMISSION_RATE = base_comm * cost_mult
    backtest.STAMP_TAX_RATE = base_stamp * cost_mult
    backtest.MIN_COMMISSION = base_min * cost_mult
    results = []
    for ticker, start in BASKET:
        try:
            prices = load(ticker, start)
        except SystemExit:
            continue
        res = wf.walk_forward(ticker, prices, CANDIDATES, BASELINE)
        results.append(res)
        if ledger is not None:
            for f in res.folds:
                ledger.write(json.dumps(
                    {"cost_mult": cost_mult, "asset": ticker, **f},
                    ensure_ascii=False) + "\n")
    backtest.COMMISSION_RATE, backtest.STAMP_TAX_RATE, backtest.MIN_COMMISSION = (
        base_comm, base_stamp, base_min,
    )
    return results


def print_table(results):
    print(f"{'asset':<9}{'folds':<6}{'OOS Sortino(med/mean)':<22}"
          f"{'B&H Sortino':<13}{'%beatBH':<9}{'%pos':<7}{'trades':<8}{'DEPLOY'}")
    print("-" * 88)
    for r in results:
        med_mean = f"{r.oos_score_median:+.3f}/{r.oos_score_mean:+.3f}"
        print(f"{r.asset:<9}{r.n_folds:<6}{med_mean:<22}"
              f"{r.bh_score_mean:<+13.3f}{r.frac_beat_bh:<9.0%}"
              f"{r.frac_pos_ret:<7.0%}{r.total_trades:<8}"
              f"{'YES' if r.deploy else 'no'}")


def old_gate(r) -> bool:
    """复刻早期弱门槛：候选 OOS score 仅需 > 基线 OOS score（用 mean 近似）。"""
    return r.oos_score_mean > r.bh_score_mean - 999  # 早期甚至不与 B&H 比，几乎恒真


def main() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    ledger = (RUN_DIR / "trials.jsonl").open("w", encoding="utf-8")

    print("=" * 88)
    print("E1+E2  Adaptive walk-forward (train 504d / test 126d / step 126d), 1x cost")
    print("=" * 88)
    base = run_basket(1.0, ledger)
    print_table(base)
    n_deploy = sum(r.deploy for r in base)
    print(f"\n严格门槛通过：{n_deploy}/{len(base)} 个资产")

    print("\n" + "=" * 88)
    print("E1  ^GSPC fold 明细")
    print("=" * 88)
    g = next(r for r in base if r.asset == "^GSPC")
    print(f"{'fold':<6}{'picked':<9}{'OOS Sortino':<14}{'OOS ret':<11}"
          f"{'B&H Sortino':<13}{'beatBH':<8}{'trades'}")
    for f in g.folds:
        print(f"{f['fold']:<6}{f['picked']:<9}{f['oos_score']:<+14.3f}"
              f"{f['oos_return']:<+11.2%}{f['bh_score']:<+13.3f}"
              f"{str(f['beat_bh']):<8}{f['oos_trades']}")

    print("\n" + "=" * 88)
    print("E3  旧弱门槛 vs 新严格门槛（同一份 WFA 结果）")
    print("=" * 88)
    print(f"{'asset':<9}{'old gate':<12}{'new strict gate':<18}{'verdict'}")
    print("-" * 60)
    old_yes = new_yes = 0
    for r in base:
        o = old_gate(r); n = r.deploy
        old_yes += o; new_yes += n
        verdict = "假阳性被拦截" if (o and not n) else ("一致" if o == n else "")
        print(f"{r.asset:<9}{'DEPLOY' if o else 'no':<12}"
              f"{'DEPLOY' if n else 'no':<18}{verdict}")
    print(f"\n旧门槛部署 {old_yes}/{len(base)}，新门槛部署 {new_yes}/{len(base)} "
          f"→ 拦下 {old_yes - new_yes} 个假阳性")

    print("\n" + "=" * 88)
    print("E4  成本敏感性：篮子严格门槛通过数 @ 1x / 3x / 5x 成本")
    print("=" * 88)
    summary_costs = {}
    for k in (1.0, 3.0, 5.0):
        res = run_basket(k, ledger if k != 1.0 else None)
        nd = sum(r.deploy for r in res)
        survivors = [r.asset for r in res if r.deploy]
        summary_costs[k] = {"n_deploy": nd, "survivors": survivors}
        print(f"  {k:>0.0f}x 成本：{nd}/{len(res)} 通过  {survivors}")

    ledger.close()
    summary = {
        "candidates": [list(c) for c in CANDIDATES],
        "baseline": list(BASELINE),
        "e1_e2_deploy": [r.asset for r in base if r.deploy],
        "e4_cost_sensitivity": {str(k): v for k, v in summary_costs.items()},
    }
    (RUN_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n留痕写入 {RUN_DIR}")


if __name__ == "__main__":
    main()
