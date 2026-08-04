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
import random
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

    # 종목 중심 커뮤니티를 위에, 일반 경제채널을 아래에 배치해 대비
    # 주의: '보유 여부'는 측정되지 않았다 — 이건 채널 유형 구분이지 투자자 속성 구분이 아니다
    STOCK_CENTERED = ["네이버 종목토론방", "디시 주식갤", "유튜브 삼프로TV"]
    channels = [c for c in STOCK_CENTERED if c in channels] + \
               [c for c in channels if c not in STOCK_CENTERED]

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
    # y축 라벨에 채널별 감정 게시글 n을 병기 — 20건 채널과 300건 채널이 같은 무게로 안 보이도록
    ax.set_yticks(list(range(len(channels)))[::-1])
    ax.set_yticklabels([f"{c} (n={totals[c]})" for c in channels], fontsize=10.5, color=INK)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.55, len(channels) + 0.1)

    def top_emo(ch):
        d = per_ch[ch]
        k = max(d, key=d.get)
        return k, d[k] / (sum(d.values()) or 1) * 100

    holders = [c for c in channels if c in STOCK_CENTERED]
    others = [c for c in channels if c not in STOCK_CENTERED]
    lo_ch = others[0] if others else channels[-1]
    lo_emo, lo_pct = top_emo(lo_ch)
    hi_range = [top_emo(c)[1] for c in holders]
    title_block(fig,
                "종목 중심 커뮤니티에서는 분노·불신이, 일반 경제채널에서는 불안·공포가 두드러진다",
                f"종목 중심 채널 3곳은 '{FOCUS}' 비중이 가장 높았다({min(hi_range):.0f}~{max(hi_range):.0f}%). "
                f"일반 경제채널({lo_ch.replace('유튜브 ', '')})은 '{lo_emo}'이 1위({lo_pct:.0f}%)\n"
                "→ 투자 포지션과 밀접한 커뮤니티일수록 분노·불신 표현이 많이 나타날 가능성. "
                "실제 보유·손실 여부는 미측정, 후속 조사 필요")
    source_block(fig, f"감정 시그널 보유 글 {sum(totals.values()):,}건 기준, 중복 태깅 포함")
    plt.subplots_adjust(top=0.68, bottom=0.12, left=0.22, right=0.98)
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
    # 비율 옆에 분자/분모를 함께 표기 — 종목별 표본 크기 차이를 숨기지 않는다
    for yy, s, v in zip(y, order, vals):
        lx = max(v + max(vals) * 0.015, mean_v + max(vals) * 0.02)  # 평균선과 겹침 방지
        ax.text(lx, yy, f"{v:.1f}%", va="center", fontsize=10,
                color=INK if v >= mean_v else MUTED,
                fontweight="bold" if v >= mean_v else "normal")
        ax.text(lx + max(vals) * 0.075, yy, f"({sig[s]}/{tot[s]})", va="center",
                fontsize=8.5, color=MUTED)
    ax.axvline(mean_v, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=0)
    ax.text(mean_v, len(order) - 0.4, f"전체 평균 {mean_v:.1f}%", ha="center",
            fontsize=9, color=MUTED)
    ax.set_xlim(0, max(vals) * 1.30)

    title_block(fig,
                f"감정 표현 비율은 10개 종목 모두 {min(vals):.0f}~{max(vals):.0f}% 범위에 분포했다",
                "분석 대상 안에서는 특정 한두 종목에만 감정 표현이 집중되지 않았다.\n"
                "→ 종목 특성뿐 아니라 투자자와 커뮤니티의 상태를 함께 볼 필요가 있다")
    source_block(fig, f"네이버 종목토론방 {sum(tot[s] for s in stocks):,}건, "
                      "괄호는 (감정 태깅 글/전체 글)")
    plt.subplots_adjust(top=0.74, bottom=0.10, left=0.16, right=0.97)
    plt.savefig(OUT / "chart2_stock_density.png", dpi=150)
    plt.close()
    print("chart2 저장")


# ─────────────────────────────────────────────────────────────
def _bootstrap_ci(emo: list[int], non: list[int], iters=2000, seed=42):
    """평균비의 부트스트랩 95% 신뢰구간. 공감수는 극단값에 민감해 CI가 필수."""
    rng = random.Random(seed)
    ratios = []
    for _ in range(iters):
        e = [emo[rng.randrange(len(emo))] for _ in range(len(emo))]
        n = [non[rng.randrange(len(non))] for _ in range(len(non))]
        me, mn = sum(e) / len(e), sum(n) / len(n)
        if mn > 0:
            ratios.append(me / mn)
    ratios.sort()
    return ratios[int(len(ratios) * 0.025)], ratios[int(len(ratios) * 0.975)]


def _median(xs: list[int]) -> float:
    s = sorted(xs)
    m = len(s) // 2
    return float(s[m]) if len(s) % 2 else (s[m - 1] + s[m]) / 2


def chart3_amplification(rows):
    """질문: 감정글이 더 많은 반응을 받는가? → 채널 내 평균비 + 부트스트랩 CI

    주의 1: 채널마다 공감수 절대 규모가 달라(슈카월드 평균 25 vs 토론방 2),
            채널을 섞으면 왜곡된다. 반드시 채널 '내부'에서 비교한다.
    주의 2: 공감수는 0이 많고 일부 인기글에 몰려 평균이 극단값에 흔들린다.
            → 중앙값·상위5개 제외·부트스트랩 CI를 함께 산출해 강건성을 확인한다.
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
        emo, non = d["emo"], d["non"]
        if len(emo) < 30 or len(non) < 30:
            continue
        ae, an = sum(emo) / len(emo), sum(non) / len(non)
        # 상위 5개 제외 후에도 방향이 유지되는지 (인기글 1~2개가 끈 결과인지 확인)
        e_trim, n_trim = sorted(emo)[:-5], sorted(non)[:-5]
        trim_ratio = ((sum(e_trim) / len(e_trim)) / (sum(n_trim) / len(n_trim))
                      if sum(n_trim) else float("nan"))
        lo, hi = _bootstrap_ci(emo, non)
        data.append({
            "ch": ch, "ratio": ae / an, "ae": ae, "an": an,
            "ne": len(emo), "nn": len(non),
            "me": _median(emo), "mn": _median(non),
            "trim": trim_ratio, "lo": lo, "hi": hi,
        })
    data.sort(key=lambda x: -x["ratio"])

    fig, ax = plt.subplots(figsize=(10, 4.8))
    y = list(range(len(data)))[::-1]
    # CI가 1.0을 넘지 않는(=유의한) 경우만 강조
    colors = [NAVY if d["lo"] > 1 else GRAYS[2] for d in data]
    ax.barh(y, [d["ratio"] for d in data], color=colors, height=0.5)
    # 부트스트랩 95% CI 오차막대
    for yy, d in zip(y, data):
        ax.plot([d["lo"], d["hi"]], [yy, yy], color=INK if d["lo"] > 1 else MUTED,
                lw=1.2, solid_capstyle="butt", zorder=3)
        for x in (d["lo"], d["hi"]):
            ax.plot([x, x], [yy - 0.09, yy + 0.09],
                    color=INK if d["lo"] > 1 else MUTED, lw=1.2, zorder=3)

    strip_axes(ax)
    ax.set_yticks(y)
    ax.set_yticklabels([d["ch"] for d in data], fontsize=10.5, color=INK)
    xmax = max(d["hi"] for d in data)
    for yy, d in zip(y, data):
        lx = max(d["hi"] + xmax * 0.03, 1.06)
        sig = d["lo"] > 1
        ax.text(lx, yy + 0.16, f"{d['ratio']:.2f}배  [{d['lo']:.2f}–{d['hi']:.2f}]",
                va="center", fontsize=10, color=INK if sig else MUTED,
                fontweight="bold" if sig else "normal")
        ax.text(lx, yy - 0.09,
                f"중앙값 {d['me']:.0f} vs {d['mn']:.0f} · 상위5 제외 {d['trim']:.2f}배",
                va="center", fontsize=7.5, color=MUTED)
        ax.text(lx, yy - 0.28, f"평균 {d['ae']:.1f} vs {d['an']:.1f} · n={d['ne']}/{d['nn']}",
                va="center", fontsize=7.5, color=MUTED)
    ax.axvline(1.0, color=MUTED, lw=1, ls=(0, (4, 3)), zorder=0)
    ax.text(1.0, len(data) - 0.3, "1.0배 = 차이 없음", ha="center", fontsize=9, color=MUTED)
    ax.set_xlim(0, xmax * 1.42)
    ax.set_ylim(-0.6, len(data) - 0.2)

    top = data[0]
    title_block(fig,
                f"{top['ch']}에서는 감정글의 평균 공감수가 비감정글보다 {top['ratio']:.2f}배 높았다",
                "종목토론방에서는 감정 표현이 더 많은 반응을 얻었지만, 일반 경제채널에서는 "
                "같은 패턴이 나타나지 않았다\n"
                "→ 가로선은 부트스트랩 95% 신뢰구간. 중앙값·상위5개 제외 결과를 함께 표기해 "
                "인기글 쏠림 여부를 확인할 수 있다")
    source_block(fig, "채널 내부 비교(채널 간 공감수 규모 차이 보정), 공감수 집계 가능 글 기준")
    plt.subplots_adjust(top=0.70, bottom=0.12, left=0.18, right=0.97)
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

    # 상위어가 종목·채널 구성 때문에 올라온 건 아닌지 확인 (제거 전후 비교, 콘솔 출력)
    DOMAIN_NOISE = {"삼성", "전자", "하이닉스", "에코", "프로", "카카오", "네이버", "현대",
                    "테슬라", "엔비디아", "구독", "영상", "채널", "댓글", "링크"}
    cnt_clean = Counter({k: v for k, v in cnt.items() if k not in DOMAIN_NOISE})
    before = [k for k, _ in cnt.most_common(15)]
    after = [k for k, _ in cnt_clean.most_common(15)]
    print(f"  [chart4] 종목·채널어 제거 전후 상위15 일치: "
          f"{len(set(before) & set(after))}/15 | 제거된 항목: {set(before) - set(after) or '없음'}")

    top = cnt_clean.most_common(15)
    labels = [k for k, _ in top][::-1]
    vals = [v for _, v in top][::-1]
    RATIONAL = {k for k, _ in top[:3]}  # 상위 3개 = 표면의 정보·투자 언어

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
                f"빈도 상위 키워드는 {top3}였다 — 감정은 표면 어휘만으로 드러나지 않는다",
                "명시적 감정 표현은 전체 게시글의 일부(13.4%)였고, 빈도 상위어는 정보·투자 관련 단어가 차지했다\n"
                "→ 단순 키워드 분석만으로 주문 직전의 충동 상태를 포착하기 어렵고, "
                "행동·생체신호를 결합할 필요성이 제기된다")
    source_block(fig, "커뮤니티·댓글 텍스트 명사 기준, 종목명·채널 고유어 제외")
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
