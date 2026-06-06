Create a professional infographic following these specifications.

## Image Specifications
- Type: Infographic (mechanism breakdown, for Zhihu article inline)
- Layout: four numbered gate-cards arranged as a HORIZONTAL ROW (4 columns) across the top, then one full-width counter-example callout strip below, then a slim bottom takeaway strip
- Style: corporate-memphis (flat vector, vibrant geometric fills, NO outlines, solid fills)
- Aspect Ratio: 16:9 (landscape, wide)
- Language: Simplified Chinese
- Background: LIGHT — white / soft pastel. Wide, light, clean business-deck look.

## Core Principles
- Wide composition: 4 equal columns on top, callout band below; generous whitespace; legible.
- Render ALL Chinese text and the set notation {2, 5} EXACTLY, no garbled glyphs.
- Calm palette on white: indigo / teal / amber / purple for the 4 gates; counter-example callout in soft red/coral with ❌; correct alternative with green ✓.
- Keep each gate to a short line.

## Layout Guidelines
- Title at top-left, kicker beside/under it.
- FOUR numbered gate-cards in a single horizontal row (1→4), each a small icon + heading + one short line.
- Below: one full-width counter-example callout band (coral) with a ❌ wrong rule and a ✓ correct rule.
- Bottom: slim takeaway strip.

## Content (preserve faithfully)

TITLE: 怎么真正防住过拟合：四道闸
KICKER (small): 量化真正的敌人，是把噪声当成规律

GATE 1 (indigo): 独立验证集 — 随机抽 1/3 做验证集（固定种子）；只用来否决，不指导搜索
GATE 2 (teal): 双重确认 — 训练集 + 验证集都不退化才算合格改进；分化过大 → 拒绝
GATE 3 (amber): 市场规律闸 — 改动要符合市场规律、讲得清逻辑；讲不清，分数再高也拒
GATE 4 (purple): 样本量门槛 — 有效交易太少（1~2 笔）判无效，那是运气不是 edge

COUNTER-EXAMPLE CALLOUT (full-width coral band):
反面例子（真实踩坑）
❌ 跳过「连涨 2 天」、放行「连涨 3/4 天」、又跳过「连涨 5 天」 —— 跳过天数 = {2, 5}：碎片化、非单调，没有市场解释 = 过拟合
✓ 正确：单调连续，如「连涨超过 N 天后统一回避」

BOTTOM TAKEAWAY: 优化的不是回测分数，而是「不被回测骗到」

Text labels (Simplified Chinese): 怎么真正防住过拟合：四道闸；量化真正的敌人，是把噪声当成规律；独立验证集；随机抽 1/3 做验证集；只用来否决，不指导搜索；双重确认；训练集 + 验证集都不退化才算合格改进；市场规律闸；改动要符合市场规律、讲得清逻辑；样本量门槛；有效交易太少判无效；反面例子；跳过天数 = {2, 5}；碎片化、非单调，没有市场解释 = 过拟合；单调连续：连涨超过 N 天统一回避；优化的不是回测分数，而是不被回测骗到
