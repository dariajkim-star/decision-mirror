# -*- coding: utf-8 -*-
"""수집 텍스트 분석: 워드클라우드 + 감정(불안/FOMO) 렉시콘 분석 + pain point 시그널 추출"""
import csv
import re
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from kiwipiepy import Kiwi
from wordcloud import WordCloud

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
FONT = r"C:\Windows\Fonts\malgun.ttf"

# ── 감정/행동 렉시콘 (No_FOMO 관점: 측정하려는 심리 상태별) ──────────────
LEXICON = {
    "FOMO·상대적박탈감": [
        "포모", "fomo", "벼락거지", "나만", "놓쳤", "놓친", "못 샀", "못샀", "지금이라도",
        "늦었", "막차", "탑승", "올라타", "추격", "불장", "안 사면", "안사면", "소외",
        "다들 벌었", "부럽", "배 아프", "배아프",
    ],
    "불안·공포": [
        "불안", "무섭", "공포", "폭락", "떨어지", "패닉", "겁나", "손 떨", "무너지",
        "걱정", "위험", "조심", "떨린", "심장", "쫄리", "살려",
    ],
    "후회·손실고통": [
        "물렸", "물타기", "손절", "존버", "후회", "괜히", "샀어야", "팔았어야", "잃었",
        "손실", "반토막", "깡통", "-%", "마이너스", "고점", "물린", "탈출", "본전",
    ],
    "분노·불신": [
        "개미", "세력", "공매도", "작전", "조작", "사기", "빡치", "화나", "짜증", "역겹",
        "쓰레기", "거품", "먹튀",
    ],
    "충동·중독시그널": [
        "빚투", "영끌", "몰빵", "풀매수", "올인", "질렀", "지르", "못 참", "못참",
        "중독", "잠 못", "잠못", "새벽", "밤새", "계속 보게", "하루종일",
    ],
}

STOPWORDS = {
    "주가", "종목", "주식", "오늘", "내일", "지금", "정도", "이제", "진짜", "그냥",
    "우리", "여기", "저기", "이거", "그거", "위해", "대한", "관련", "기자", "뉴스",
    "기사", "네이버", "삼성전자", "하이닉스", "에코프로", "카카오", "현대차", "알테오젠",
    "한미반도체", "삼전", "삼성", "얼마", "때문", "사람", "생각", "이유", "경우",
}


def load_texts() -> list[dict]:
    rows = []
    for name in ["raw_texts.csv", "raw_news.csv", "raw_details.csv", "raw_blind.csv", "raw_dcinside.csv", "raw_youtube.csv"]:
        p = DATA / name
        if p.exists():
            with open(p, encoding="utf-8-sig") as f:
                rows.extend(csv.DictReader(f))
    return rows


def emotion_tag(text: str) -> list[str]:
    t = text.lower()
    return [emo for emo, words in LEXICON.items() if any(w in t for w in words)]


def main():
    rows = load_texts()
    print(f"분석 대상: {len(rows)}건")
    BOARD_SRC = {"board", "board_body", "board_comment", "blind_body", "blind_comment",
                 "dc_title", "dc_body", "dc_comment", "yt_comment"}
    board = [r for r in rows if r["source"] in BOARD_SRC]
    news = [r for r in rows if r["source"] not in BOARD_SRC]

    # ── 1. 명사 추출 → 워드클라우드 ──
    kiwi = Kiwi()
    counter_board, counter_news = Counter(), Counter()
    for r in rows:
        text = re.sub(r"http\S+|[a-zA-Z0-9_.]+@\S+", " ", r["text"])
        nouns = [t.form for t in kiwi.tokenize(text)
                 if t.tag in ("NNG", "NNP", "SL") and len(t.form) > 1
                 and t.form not in STOPWORDS]
        tgt = counter_board if r["source"] in BOARD_SRC else counter_news
        tgt.update(nouns)

    for name, counter in [("board", counter_board), ("news", counter_news)]:
        wc = WordCloud(font_path=FONT, width=1400, height=800,
                       background_color="white", colormap="RdBu_r",
                       max_words=120).generate_from_frequencies(counter)
        wc.to_file(str(OUT / f"wordcloud_{name}.png"))
        with open(OUT / f"top_keywords_{name}.csv", "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["keyword", "count"])
            w.writerows(counter.most_common(80))
    print("워드클라우드 저장 완료")

    # ── 2. 감정 렉시콘 분석 ──
    emo_counts = Counter()
    emo_examples: dict[str, list[str]] = {k: [] for k in LEXICON}
    tagged = 0
    for r in board:  # pain point는 투자자 육성(토론방) 기준
        tags = emotion_tag(r["text"])
        if tags:
            tagged += 1
        for t in tags:
            emo_counts[t] += 1
            if len(emo_examples[t]) < 15:
                emo_examples[t].append(f"[{r['stock']}] {r['text']}")

    ratio = tagged / len(board) * 100 if board else 0
    print(f"토론방 {len(board)}건 중 감정 시그널 포함: {tagged}건 ({ratio:.1f}%)")

    # 감정 분포 차트 — 맥킨지 스타일
    #   결론형 제목 / 그레이 베이스 + 최대값만 네이비 강조 / 축·격자 제거 / 직접 레이블 / Source 표기
    NAVY, GRAY, INK, MUTED = "#051C2C", "#B7BDC3", "#051C2C", "#6E7B85"
    emos = [e for e, _ in emo_counts.most_common()]
    vals = [emo_counts[e] for e in emos]
    total_sig = sum(vals)
    top_share = vals[0] / total_sig * 100 if total_sig else 0

    fig, ax = plt.subplots(figsize=(9.5, 5))
    y = range(len(emos))[::-1]
    colors = [NAVY if i == 0 else GRAY for i in range(len(emos))]
    ax.barh(list(y), vals, color=colors, height=0.62)

    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.set_xticks([])
    ax.set_yticks(list(y))
    ax.set_yticklabels(emos, fontsize=11, color=INK)
    ax.tick_params(length=0)
    for yi, v, i in zip(y, vals, range(len(vals))):
        ax.text(v + max(vals) * 0.015, yi, f"{v}",
                va="center", fontsize=11, color=INK if i == 0 else MUTED,
                fontweight="bold" if i == 0 else "normal")

    # 평균 기준선 — 강조 대상이 평균을 얼마나 상회하는지 대비
    mean_v = sum(vals) / len(vals)
    ax.axvline(mean_v, color=MUTED, linewidth=1, linestyle=(0, (4, 3)), zorder=0)
    ax.text(mean_v, max(y) + 0.75, f"평균 {mean_v:.0f}",
            ha="center", fontsize=9, color=MUTED)

    fig.suptitle(f"개인투자자 감정 시그널의 {top_share:.0f}%는 '{emos[0]}' —\n"
                 "손실 원인을 외부에 귀인하며 자기 의사결정을 성찰하지 못한다",
                 x=0.02, y=0.97, ha="left", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.02, 0.02,
             f"Source: 네이버 종목토론방·디시인사이드·유튜브(삼프로TV/슈카월드) 등 "
             f"{len(board):,}건 중 감정 시그널 포함 {tagged:,}건(중복 태깅 {total_sig:,}회), 2026.08",
             fontsize=8, color=MUTED)
    plt.subplots_adjust(top=0.80, bottom=0.10, left=0.18, right=0.96)
    plt.savefig(OUT / "emotion_distribution.png", dpi=150)
    print("감정 분포 차트 저장 완료 (맥킨지 스타일)")

    # ── 3. 리포트 데이터 ──
    with open(OUT / "emotion_report.md", "w", encoding="utf-8") as f:
        f.write(f"# 감정 분석 리포트\n\n- 전체 수집: {len(rows)}건 (토론방 {len(board)}, 뉴스 {len(news)})\n")
        f.write(f"- 토론방 글 중 감정 시그널 포함 비율: **{ratio:.1f}%**\n\n")
        for emo, cnt in emo_counts.most_common():
            f.write(f"## {emo} — {cnt}건\n\n")
            for ex in emo_examples[emo]:
                f.write(f"- {ex}\n")
            f.write("\n")
    print(f"리포트 저장 → {OUT / 'emotion_report.md'}")


if __name__ == "__main__":
    main()
