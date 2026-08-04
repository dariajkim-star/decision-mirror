# -*- coding: utf-8 -*-
"""수집 텍스트에서 페르소나 원형(archetype)을 채굴한다.

목적: PRD의 User Journey 주인공을 상상으로 만들지 않고, 실제 수집된 5,022건에서
      반복 관찰되는 행동·감정 패턴으로 도출한다.

방법:
1. 감정 태그 '조합'의 동시출현 패턴 → 어떤 감정들이 함께 다니는가
2. 시퀀스 마커(방금/아까/오늘/샀는데/물렸다...)를 가진 글 → 이미 존재하는 미니 저니
3. 1인칭 자기서술 vs 3인칭 논평 분리 → 페르소나는 1인칭에서만 나온다
4. 채널 × 감정조합 교차 → 원형별 서식지

출력: output/persona_evidence.md
"""
import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

from analyze import LEXICON, emotion_tag, load_texts

OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

BOARD_SRC = {"board", "board_body", "board_comment", "dc_title", "dc_body",
             "dc_comment", "yt_comment"}

# 1인칭 자기서술 마커 — 남 얘기가 아니라 본인 경험을 쓴 글
FIRST_PERSON = ["나는", "내가", "난 ", "제가", "저는", "내 ", "제 ", "우리", "나도", "저도",
                "샀는데", "샀다", "팔았", "물렸", "들고", "보유", "익절", "손절했", "매수했",
                "매도했", "탔다", "탔는데", "넣었"]

# 시퀀스 마커 — 시간 순서가 있는 서술 = 미니 저니
SEQUENCE = ["방금", "아까", "오늘", "어제", "그때", "장 시작", "장초반", "장마감", "개장",
            "새벽", "아침", "점심", "저녁", "밤에", "출근", "퇴근", "자다", "잠",
            "하다가", "했는데", "보고", "보다가", "듣고", "봤는데", "그러다"]

# 행동 마커 — 관측 가능한 행동이 언급된 글
BEHAVIOR = ["계속 보", "계속보", "몇 번", "몇번", "자꾸", "반복", "새로고침", "들어가",
            "확인", "쳐다", "눈이 가", "손이", "눌렀", "클릭", "검색"]


# 광고·홍보 노이즈 (특히 유튜브 고정댓글)
SPAM = ["http", "bit.ly", "구독", "핫딜", "링크", "무료체험", "이벤트 참여", "쿠폰",
        "카톡방", "오픈채팅", "리딩방", "텔레그램", "▶", "👉"]

# 상태 맹시 증거: 감정어 없이 '행동'만 드러나는 글 (반복확인·고빈도 모니터링)
# 상태 맹시의 정의상 타겟 사용자는 감정을 언어화하지 않는다 → 감정 태그로만 캐면 편향됨
BLINDNESS = ["계속 보", "계속보", "하루종일", "몇 번씩", "몇번씩", "자꾸 보", "자꾸보",
             "새로고침", "들락", "눈이 가", "눈을 못", "손이 가", "못 참", "못참",
             "밤새", "잠이 안", "잠 못", "새벽", "출근길", "화장실", "회사에서",
             "일이 손에", "집중이 안", "신경 쓰여", "신경쓰여", "불안해서", "궁금해서"]


def has(text: str, markers: list[str]) -> bool:
    return any(m in text for m in markers)


def is_spam(text: str) -> bool:
    return sum(1 for m in SPAM if m in text) >= 2 or text.count("http") >= 1


def main():
    rows = [r for r in load_texts()
            if r["source"] in BOARD_SRC and not is_spam(r["text"])]
    print(f"커뮤니티 텍스트 {len(rows):,}건 (광고 제외)")

    # ── 1. 감정 조합 동시출현 ──
    combos = Counter()
    tagged_rows = []
    for r in rows:
        tags = tuple(sorted(emotion_tag(r["text"])))
        if tags:
            combos[tags] += 1
            tagged_rows.append((tags, r))
    print(f"감정 태깅 {len(tagged_rows):,}건")

    # ── 2. 1인칭 × 시퀀스 = 미니 저니 후보 ──
    journeys = []
    for tags, r in tagged_rows:
        t = r["text"]
        score = (has(t, FIRST_PERSON) * 2 + has(t, SEQUENCE) * 2
                 + has(t, BEHAVIOR) * 3 + (len(t) > 40))
        if score >= 4:
            journeys.append((score, tags, r))
    journeys.sort(key=lambda x: -x[0])
    print(f"미니 저니 후보 {len(journeys):,}건")

    # ── 3. 채널 × 감정 교차 ──
    def channel(r):
        s = r["source"]
        if s.startswith("board"):
            return "네이버 종목토론방"
        if s.startswith("dc_"):
            return "디시 주식갤"
        return f"유튜브 {r['stock']}"

    ch_emo = defaultdict(Counter)
    for tags, r in tagged_rows:
        for t in tags:
            ch_emo[channel(r)][t] += 1

    # ── 4. 리포트 ──
    with open(OUT / "persona_evidence.md", "w", encoding="utf-8") as f:
        f.write("# 페르소나 근거 자료 — 수집 데이터에서 채굴\n\n")
        f.write(f"대상: 커뮤니티 텍스트 {len(rows):,}건 중 감정 태깅 {len(tagged_rows):,}건\n\n")

        f.write("## 1. 감정 조합 동시출현 — 어떤 감정이 함께 다니는가\n\n")
        f.write("| 감정 조합 | 건수 | 해석 힌트 |\n|---|---|---|\n")
        for tags, n in combos.most_common(15):
            label = " + ".join(tags)
            f.write(f"| {label} | {n} | |\n")
        f.write("\n")

        f.write("## 2. 채널별 감정 분포 (원형의 서식지)\n\n")
        for ch, c in sorted(ch_emo.items(), key=lambda x: -sum(x[1].values())):
            tot = sum(c.values())
            if tot < 20:
                continue
            dist = ", ".join(f"{k} {v/tot*100:.0f}%" for k, v in c.most_common())
            f.write(f"- **{ch}** (n={tot}): {dist}\n")
        f.write("\n")

        # ── 상태 맹시 증거: 감정어 없이 행동만 드러난 글 ──
        blind = []
        for r in rows:
            t = r["text"]
            if has(t, BLINDNESS) and len(t) > 25:
                blind.append((bool(emotion_tag(t)), r))
        no_emo = [r for tagged, r in blind if not tagged]
        f.write("## 3. 상태 맹시 증거 — 행동은 드러나는데 감정어는 없는 글\n\n")
        f.write(f"반복확인·고빈도 모니터링 언급 {len(blind)}건 중 "
                f"**감정 렉시콘에 전혀 걸리지 않는 글 {len(no_emo)}건 "
                f"({len(no_emo)/max(len(blind),1)*100:.0f}%)**. ")
        f.write("이들은 행동으로는 위험 신호를 보이지만 스스로 감정을 언어화하지 않는다 — "
                "텍스트 감성분석이 놓치는 집단이자, 이 제품의 실제 타겟.\n\n")
        for r in no_emo[:20]:
            txt = re.sub(r"\s+", " ", r["text"])[:200]
            f.write(f"- `[{channel(r)}/{r['stock']}]` {txt}\n")
        f.write("\n")

        f.write("## 4. 미니 저니 후보 — 1인칭 + 시간순서 + 행동 언급\n\n")
        f.write("페르소나는 여기서 나와야 한다. 상상이 아니라 실제 문장.\n\n")
        by_combo = defaultdict(list)
        for score, tags, r in journeys:
            by_combo[" + ".join(tags)].append((score, r))
        for combo, items in sorted(by_combo.items(), key=lambda x: -len(x[1]))[:8]:
            f.write(f"### {combo} ({len(items)}건)\n\n")
            for score, r in items[:12]:
                txt = re.sub(r"\s+", " ", r["text"])[:220]
                f.write(f"- `[{channel(r)}/{r['stock']}]` {txt}\n")
            f.write("\n")

    print(f"→ {OUT / 'persona_evidence.md'}")


if __name__ == "__main__":
    main()
