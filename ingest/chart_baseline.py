# -*- coding: utf-8 -*-
"""주간 수면 시간 차트 — 맥킨지 스타일 (결론형 제목, 평균 기준선, 강조 최소)"""
import csv
import io
import statistics
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).parent
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NAVY, GRAY, INK, MUTED = "#051C2C", "#C2C8CD", "#051C2C", "#6E7B85"
RED = "#C0392B"  # 위험 주 강조 (의미 있는 색 1개 추가: 5.5h 미만)

rows = list(csv.DictReader(open(BASE / "data" / "garmin_weekly.csv", encoding="utf-8-sig")))
rows = [r for r in rows if r["sleep_min"]][::-1]  # 과거→최근
hours = [float(r["sleep_min"]) / 60 for r in rows]
mean_h = statistics.mean(hours)
short = [i for i, h in enumerate(hours) if h < 5.5]

fig, ax = plt.subplots(figsize=(10.5, 4.6))
ax.plot(range(len(hours)), hours, color=NAVY, lw=2, zorder=3)
ax.scatter(short, [hours[i] for i in short], color=RED, s=42, zorder=4)
ax.axhline(mean_h, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=1)
ax.text(len(hours) - 0.5, mean_h + 0.12, f"1년 평균 {mean_h:.1f}h",
        ha="right", fontsize=9, color=MUTED)

for s in ax.spines.values():
    s.set_visible(False)
ax.set_xticks([])
ax.tick_params(length=0)
ax.set_yticks([4, 6, 8, 10])
ax.set_yticklabels([f"{v}h" for v in [4, 6, 8, 10]], fontsize=10, color=MUTED)

# 위험 주 직접 라벨 (최저 2개만 — 모든 점에 숫자 금지)
lows = sorted(short, key=lambda i: hours[i])[:2]
for i in lows:
    ax.annotate(f"{hours[i]:.1f}h", (i, hours[i]), textcoords="offset points",
                xytext=(0, -14), ha="center", fontsize=9, color=RED, fontweight="bold")

fig.suptitle(f"1년간 주평균 수면이 5.5시간을 밑돈 주가 {len(short)}번 — 최저 4.0h",
             x=0.02, y=0.96, ha="left", fontsize=13.5, fontweight="bold", color=INK)
fig.text(0.02, 0.865, "수면 변동성이 큰 프로파일 — '어젯밤 수면' L1 문구의 정보 가치가 높다",
         ha="left", fontsize=10, color=MUTED)
fig.text(0.02, 0.03, "Source: Garmin Connect 주간 수면 집계, 2025.08~2026.08 (n=51주), ● = 주평균 5.5h 미만",
         fontsize=8, color=MUTED)
plt.subplots_adjust(top=0.78, bottom=0.10, left=0.05, right=0.98)
out = BASE / "output" / "chart_sleep_weekly.png"
plt.savefig(out, dpi=150)
print(f"→ {out}")
