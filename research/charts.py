# -*- coding: utf-8 -*-
"""No_FOMO 리서치 차트 — 맥킨지 차팅 문법

원칙: 결론형 제목 / 질문에 맞는 차트 / 강조색은 핵심에만·나머지 회색 /
      장식 제로 / 직접 라벨링 / 출처 하단 / 평균 기준선·방향 화살표

생성물 (output/):
  chart1_channel_mix.png    채널별 감정 구성 (100% 누적 막대)
  chart2_stock_density.png  종목별 감정 밀도 (정렬 가로막대 + 평균선)
  chart3_amplification.png  감정별 공감 증폭도 (정렬 가로막대 + 평균선)
  chart4_keywords.png       상위 키워드 (정렬 가로막대)
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from kiwipiepy import Kiwi

from analyze import LEXICON, STOPWORDS, emotion_tag, load_texts

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# 팔레트: 강조 1색(딥블루) + 무채색 계조
NAVY = "#051C2C"
GRAYS = ["#8C959D", "#A8AFB6", "#C2C8CD", "#DBDFE2"]  # 진→연
INK, MUTED, RULE = "#051C2C", "#6E7B85", "#C2C8CD"

SOURCE_NOTE = "Source: 네이버 종목토론방·디시인사이드 주식갤·유튜브(삼프로TV·슈카월드), 2026.08.03~04 수집"

FOCUS = "분노·불신"  # 강조 대상 (전체 1위 감정)


def strip_axes(ax, keep_left=True):
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks([])
    ax.tick_params(length=0)
    if not keep_left:
        ax.set_yticks([])


def title_block(fig, headline, sub=None):
    fig.text(0.02, 0.955, headline, ha="left", va="top",
             fontsize=13.5, fontweight="bold", color=INK)
    if sub:
        fig.text(0.02, 0.875, sub, ha="left", va="top", fontsize=10, color=MUTED)


def source_block(fig, extra=""):
    fig.text(0.02, 0.025, SOURCE_NOTE + (f" | {extra}" if extra else ""),
             fontsize=8, color=MUTED)


def channel_of(r: dict) -> str | None:
    """행 → 채널 라벨."""
    s = r["source"]
    if s in ("board", "board_body", "board_comment"):
        return "네이버 종목토론방"
    if s.startswith("dc_"):
        return "디시 주식갤"
    if s == "yt_comment":
        return f"유튜브 {r['stock']}"
    return None


# ─────────────────────────────────────────────────────────────
def chart1_channel_mix(rows):
    """질문: 채널마다 감정 구성이 다른가? → 100% 누적 막대 (구성 비교)"""
    per_ch = defaultdict(Counter)
    totals = Counter()
    for r in rows:
        ch = channel_of(r)
        if not ch:
            continue
        tags = emotion_tag(r["text"])
        if tags:
            totals[ch] += 1
            for t in tags:
                per_ch[ch][t] += 1

    channels = [c for c, _ in totals.most_common() if totals[c] >= 20]
    emos = [e for e, _ in Counter(
        {k: sum(per_ch[c][k] for c in channels) for k in LEXICON}).most_common()]

    # 종목 보유 커뮤니티를 위에, 일반 경제채널을 아래에 배치해 대비
    HOLDER = ["네이버 종목토론방", "디시 주식갤", "유튜브 삼프로TV"]
    channels = [c for c in HOLDER if c in channels] + [c for c in channels if c not in HOLDER]

    fig, ax = plt.subplots(figsize=(10.5, 4.8))
    left = defaultdict(float)
    label_x = {}
    for i, emo in enumerate(emos):
        color = NAVY if emo == FOCUS else GRAYS[min(i if emos.index(FOCUS) > i else i - 1, 3)]
        vals, ys = [], []
        for j, ch in enumerate(channels):
            tot = sum(per_ch[ch].values()) or 1
            vals.append(per_ch[ch][emo] / tot * 100)
            ys.append(len(channels) - 1 - j)
        ax.barh(ys, vals, left=[left[c] for c in channels], color=color, height=0.58)
        for ch, v, yy in zip(channels, vals, ys):
            if v >= 12:  # 넓은 세그먼트에만 직접 라벨 (모든 값에 숫자 금지)
                ax.text(left[ch] + v / 2, yy, f"{v:.0f}%", ha="center", va="center",
                        fontsize=9.5, color="white" if emo == FOCUS else INK,
                        fontweight="bold" if emo == FOCUS else "normal")
            left[ch] += v
        label_x[emo] = left[channels[0]] - vals[0] / 2  # 최상단 행 기준 라벨 위치

    # 범례 대신 상단 직접 라벨 — 좁은 구간은 위층으로 올려 충돌 회피
    placed: list[float] = []
    for emo in emos:
        x = label_x[emo]
        row = 1 if any(abs(x - p) < 13 for p in placed) else 0
        placed.append(x)
        ax.text(min(x, 97), len(channels) - 0.62 + row * 0.30, emo,
                ha="center" if x < 90 else "right", va="bottom", fontsize=9,
                color=NAVY if emo == FOCUS else MUTED,
                fontweight="bold" if emo == FOCUS else "normal")

    strip_axes(ax)
    ax.set_yticks(list(range(len(channels)))[::-1])
    ax.set_yticklabels(channels, fontsize=10.5, color=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, len(channels) + 0.1)

    def top_emo(ch):
        d = per_ch[ch]
        k = max(d, key=d.get)
        return k, d[k] / (sum(d.values()) or 1) * 100

    holders = [c for c in channels if c in HOLDER]
    others = [c for c in channels if c not in HOLDER]
    lo_ch = others[0] if others else channels[-1]
    lo_emo, lo_pct = top_emo(lo_ch)
    hi_range = [top_emo(c)[1] for c in holders]
    title_block(fig,
                f"물린 사람은 분노하고, 지켜보는 사람은 불안해한다 — 같은 시장, 다른 감정",
                f"종목 보유 커뮤니티 3곳은 모두 '{FOCUS}'이 1위({min(hi_range):.0f}~{max(hi_range):.0f}%), "
                f"일반 경제채널({lo_ch.replace('유튜브 ', '')})은 '{lo_emo}'이 1위({lo_pct:.0f}%)")
    source_block(fig, f"감정 시그널 보유 글 {sum(totals.values()):,}건 기준, 중복 태깅 포함")
    plt.subplots_adjust(top=0.68, bottom=0.12, left=0.17, right=0.98)
    plt.savefig(OUT / "chart1_channel_mix.png", dpi=150)
    plt.close()
    print("chart1 저장")


# ─────────────────────────────────────────────────────────────
def chart2_stock_density(rows):
    """질문: 어느 종목이 가장 감정적인가? → 정렬 가로막대 + 평균선"""
    tot, sig = Counter(), Counter()
    for r in rows:
        if r["source"] not in ("board", "board_body", "board_comment"):
            continue
        st = r["stock"]
        tot[st] += 1
        if emotion_tag(r["text"]):
            sig[st] += 1
    stocks = [s for s in tot if tot[s] >= 50]
    dens = {s: sig[s] / tot[s] * 100 for s in stocks}
    order = sorted(dens, key=dens.get, reverse=True)
    vals = [dens[s] for s in order]
    mean_v = sum(sig[s] for s in stocks) / sum(tot[s] for s in stocks) * 100

    fig, ax = plt.subplots(figsize=(9.5, 5.2))
    y = list(range(len(order)))[::-1]
    colors = [NAVY if v >= mean_v else GRAYS[2] for v in vals]
    ax.barh(y, vals, color=colors, height=0.62)
    strip_axes(ax)
    ax.set_yticks(y)
    ax.set_yticklabels(order, fontsize=10.5, color=INK)
    for yy, v in zip(y, vals):
        lx = max(v + max(vals) * 0.015, mean_v + max(vals) * 0.02)  # 평균선과 겹침 방지
        ax.text(lx, yy, f"{v:.0f}%", va="center", fontsize=10,
                color=INK if v >= mean_v else MUTED,
                fontweight="bold" if v >= mean_v else "normal")
    ax.axvline(mean_v, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=0)
    ax.text(mean_v, len(order) - 0.4, f"전체 평균 {mean_v:.0f}%", ha="center",
            fontsize=9, color=MUTED)
    ax.set_xlim(0, max(vals) * 1.12)

    title_block(fig,
                f"감정 과열은 특정 종목의 문제가 아니다 — 10개 종목 전부 "
                f"{min(vals):.0f}~{max(vals):.0f}% 좁은 구간",
                "종목을 바꿔도 감정 밀도는 그대로 → 개입 대상은 '종목'이 아니라 '투자자의 상태'여야 한다")
    source_block(fig, f"네이버 종목토론방 {sum(tot[s] for s in stocks):,}건")
    plt.subplots_adjust(top=0.76, bottom=0.10, left=0.16, right=0.97)
    plt.savefig(OUT / "chart2_stock_density.png", dpi=150)
    plt.close()
    print("chart2 저장")


# ─────────────────────────────────────────────────────────────
def chart3_amplification(rows):
    """질문: 감정글이 더 확산되는가? → 채널 내 배수 비교 (1.0배 기준선)

    주의: 채널마다 공감수 절대 규모가 달라(슈카월드 평균 25 vs 토론방 2),
    채널을 섞으면 결과가 왜곡된다. 반드시 채널 '내부'에서 비교한다.
    """
    stat = defaultdict(lambda: {"emo": [], "non": []})
    for r in rows:
        ch = channel_of(r)
        v = (r.get("likes") or "").strip()
        if not ch or not v.isdigit():
            continue
        stat[ch]["emo" if emotion_tag(r["text"]) else "non"].append(int(v))

    data = []
    for ch, d in stat.items():
        if len(d["emo"]) < 30 or len(d["non"]) < 30:
            continue
        ae, an = sum(d["emo"]) / len(d["emo"]), sum(d["non"]) / len(d["non"])
        data.append((ch, ae / an, ae, an, len(d["emo"])))
    data.sort(key=lambda x: -x[1])
    labels = [d[0] for d in data]
    ratios = [d[1] for d in data]

    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    y = list(range(len(labels)))[::-1]
    colors = [NAVY if r > 1 else GRAYS[2] for r in ratios]
    ax.barh(y, ratios, color=colors, height=0.55)
    strip_axes(ax)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=INK)
    for yy, (ch, ratio, ae, an, n) in zip(y, data):
        lx = max(ratio + 0.04, 1.07)  # 1.0배 기준선과 라벨이 겹치지 않도록
        ax.text(lx, yy, f"{ratio:.2f}배", va="center", fontsize=10.5,
                color=INK if ratio > 1 else MUTED,
                fontweight="bold" if ratio > 1 else "normal")
        ax.text(lx, yy - 0.32, f"감정글 {ae:.1f} vs 그 외 {an:.1f} (n={n})",
                va="center", fontsize=8, color=MUTED)
    ax.axvline(1.0, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=0)
    ax.text(1.0, len(labels) - 0.35, "1.0배 = 차이 없음", ha="center", fontsize=9, color=MUTED)
    ax.set_xlim(0, max(ratios) * 1.25)

    top_ch, top_r = data[0][0], data[0][1]
    title_block(fig,
                f"감정 되먹임은 '물린 사람들의 방'에서만 작동한다 — {top_ch} {top_r:.2f}배",
                "종목토론방에서는 감정글이 더 많은 공감을 받지만, 일반 경제채널에서는 오히려 덜 받는다")
    source_block(fig, "채널 내부 비교(채널 간 공감수 규모 차이 보정), 공감수 집계 가능 글 기준")
    plt.subplots_adjust(top=0.72, bottom=0.13, left=0.20, right=0.97)
    plt.savefig(OUT / "chart3_amplification.png", dpi=150)
    plt.close()
    print("chart3 저장")


# ─────────────────────────────────────────────────────────────
def chart4_keywords(rows):
    """질문: 무엇을 말하는가? → 상위 키워드 정렬 가로막대 (워드클라우드 보완, 순위 비교용)"""
    kiwi = Kiwi()
    cnt = Counter()
    BOARD = {"board", "board_body", "board_comment", "dc_title", "dc_body", "dc_comment", "yt_comment"}
    for r in rows:
        if r["source"] not in BOARD:
            continue
        text = re.sub(r"http\S+", " ", r["text"])
        cnt.update(t.form for t in kiwi.tokenize(text)
                   if t.tag in ("NNG", "NNP") and len(t.form) > 1 and t.form not in STOPWORDS)

    top = cnt.most_common(15)
    labels = [k for k, _ in top][::-1]
    vals = [v for _, v in top][::-1]
    RATIONAL = {k for k, _ in top[:3]}  # 상위 3개 = 표면의 이성적 언어

    fig, ax = plt.subplots(figsize=(9.5, 6))
    y = list(range(len(labels)))
    colors = [NAVY if k in RATIONAL else GRAYS[2] for k in labels]
    ax.barh(y, vals, color=colors, height=0.66)
    strip_axes(ax)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10.5, color=INK)
    for yy, v, k in zip(y, vals, labels):
        ax.text(v + max(vals) * 0.012, yy, str(v), va="center", fontsize=9.5,
                color=INK if k in RATIONAL else MUTED,
                fontweight="bold" if k in RATIONAL else "normal")
    ax.set_xlim(0, max(vals) * 1.1)

    top3 = "·".join(k for k, _ in top[:3])
    title_block(fig,
                f"커뮤니티의 표면 언어는 이성적이다 — 상위 3개가 '{top3}'",
                "충동은 글에 드러나지 않는다(명시적 감정 표현 13%) → 텍스트만으로는 감지 불가, "
                "생체신호가 필요한 이유")
    source_block(fig, "커뮤니티·댓글 텍스트 명사 기준")
    plt.subplots_adjust(top=0.79, bottom=0.09, left=0.14, right=0.97)
    plt.savefig(OUT / "chart4_keywords.png", dpi=150)
    plt.close()
    print("chart4 저장")


def main():
    rows = load_texts()
    print(f"입력 {len(rows):,}건")
    chart1_channel_mix(rows)
    chart2_stock_density(rows)
    chart3_amplification(rows)
    chart4_keywords(rows)
    print(f"\n→ {OUT}")


if __name__ == "__main__":
    main()
