# -*- coding: utf-8 -*-
"""매매 근거 분류 차트 — 맥킨지 스타일 (pain point 검증 결과)"""
import io
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NAVY, GRAY, INK, MUTED = "#051C2C", "#C2C8CD", "#051C2C", "#6E7B85"

# 합의 수치 (score_trade_basis.py)
cats = ["심리주도", "혼합", "데이터주도"]
vals = [21, 1, 1]
loss = [11, 0, 0]  # 양측 합의 손실

fig, ax = plt.subplots(figsize=(9.5, 4.0))
y = [2, 1, 0]
# 전체 막대 (심리주도만 네이비, 손실 부분은 진하게 표시)
ax.barh(y, vals, color=[GRAY, GRAY, GRAY], height=0.55)
ax.barh(y[0], loss[0], color=NAVY, height=0.55)  # 심리주도 중 손실
ax.barh(y[0], vals[0], color="none", edgecolor=NAVY, lw=1.4, height=0.55)

for s in ax.spines.values():
    s.set_visible(False)
ax.set_xticks([])
ax.set_yticks(y)
ax.set_yticklabels(cats, fontsize=11, color=INK)
ax.tick_params(length=0)

ax.text(vals[0] + 0.3, y[0], f"{vals[0]}건", va="center", fontsize=11,
        color=INK, fontweight="bold")
ax.text(loss[0] / 2, y[0], f"손실·물림 {loss[0]}", va="center", ha="center",
        fontsize=9.5, color="white", fontweight="bold")
for i in (1, 2):
    ax.text(vals[i] + 0.3, y[i], f"{vals[i]}건", va="center", fontsize=10, color=MUTED)
ax.set_xlim(0, 24)

fig.suptitle("매매 근거를 밝힌 글 23건 중 21건이 심리 주도 — 그중 절반은 물렸다",
             x=0.02, y=0.95, ha="left", fontsize=13.5, fontweight="bold", color=INK)
fig.text(0.02, 0.855, "데이터를 근거로 든 매매는 단 1건. 복수매매(물타기·복구)는 4건 전원 손실",
         ha="left", fontsize=10, color=MUTED)
fig.text(0.02, 0.04, "Source: 4개 채널 매매 언급 글 268건 중 표본 220건, 독립 판정 2명 합의(kappa 0.79) 기준, 2026.08 | "
         "손실 = 양측 판정 일치분만", fontsize=8, color=MUTED)
plt.subplots_adjust(top=0.74, bottom=0.13, left=0.13, right=0.97)
out = Path(__file__).parent / "output" / "chart5_trade_basis.png"
plt.savefig(out, dpi=150)
print(f"→ {out}")
