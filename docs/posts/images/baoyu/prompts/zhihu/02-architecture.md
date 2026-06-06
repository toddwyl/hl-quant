Create a professional infographic following these specifications.

## Image Specifications
- Type: Infographic (diagram, for Zhihu article inline)
- Layout: linear-progression arranged HORIZONTALLY (left→right): three node cards connected by right-pointing arrows; two hard-rule chips along the bottom
- Style: corporate-memphis (flat vector, vibrant geometric fills, NO outlines, solid fills)
- Aspect Ratio: 16:9 (landscape, wide)
- Language: Simplified Chinese
- Background: LIGHT — white / soft pastel. Wide, light banner design.

## Core Principles
- Horizontal flow reads left→right; generous whitespace; legible at article width.
- Render ALL Chinese text and code identifiers EXACTLY (strategy.py, backtest.py, Sortino), no garbled glyphs.
- Calm finance/tech palette on white: amber (node1), indigo (node2), teal (node3).

## Layout Guidelines (horizontal flow)
- Title across the top.
- THREE node cards side by side, left→right, connected by → arrows:
  - Node 1 amber "editable" (badge 改它)
  - Node 2 indigo "fixed/locked" with small lock icon (badge 钉死)
  - Node 3 teal "score" with a small trophy/flag icon. IMPORTANT: do NOT draw any number, gauge value, or decimal on node 3 — text only.
- Below the flow: two hard-rule chips, numbered 1 and 2, side by side.

## Content (preserve faithfully)

TITLE: 把量化研究压成：一个策略 + 一个打分器
KICKER (small): 固定评估器 + 单一可编辑程序

NODE 1 (amber, badge 改它): strategy.py — 唯一可编辑程序 · 提假设/改逻辑/调参数，只动这一个文件
ARROW → label: 只读它，绝不为提分而改
NODE 2 (indigo, lock, badge 钉死): backtest.py — 固定评估器 · 拉数据/模拟成交/计成本/算指标
ARROW →
NODE 3 (teal, trophy): 一个分数 ＝ Sortino — 同数据/同口径/同公式 → “有没有更好”成为可排序的客观问题

TWO HARD-RULE CHIPS:
1. 只改策略文件，评估器 / 数据 / 评分公式一律不动
2. 每轮只动一个有经济含义的变量，严格更好才留

Text labels (Simplified Chinese): 把量化研究压成：一个策略 + 一个打分器；固定评估器 + 单一可编辑程序；strategy.py；改它；唯一可编辑程序；backtest.py；钉死；固定评估器；一个分数 ＝ Sortino；可排序的客观问题；只改策略文件，评估器/数据/评分公式不动；每轮只动一个有经济含义的变量，严格更好才留
