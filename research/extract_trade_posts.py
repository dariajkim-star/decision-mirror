# -*- coding: utf-8 -*-
"""매매 언급 글 추출 — pain point 검증용 재분석 1단계

daria의 문제의식(2026-08-05 재정의):
  "데이터가 아니라 심리에 의해 매매를 하고 물리는 상황을 없애고 싶다.
   이 painpoint가 실제 마켓에 있는지 보고 싶다."

따라서 분석 단위를 바꾼다: 글 = 감정 표현 (기존) → 글 = 매매 결정의 기록.
매매(했다/한다/하려 한다)를 언급한 글을 추출해 근거 분류의 모집단을 만든다.

출력: output/trade_posts.csv (판정 대상), 콘솔 요약
"""
import csv
import io
import random
import re
import sys
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NEWS = {"gnews", "news", "news_desc", "naver_main_news", "naver_main_desc", "fin_news"}

# 매매 행위 언급 (자신 또는 구체적 결정) — 완료·진행·임박
TRADE = re.compile(
    r"(?:매수|매도|샀|산다|사려|사야|살까|팔았|판다|팔려|팔까|팔아야|"
    r"들어갔|들어간다|들어갈까|진입|탔다|탈까|타야|익절|손절했|손절할까|"
    r"물타|추매|풀매수|몰빵|정리했|비중\s?(?:늘|줄))"
)
# 광고 배제 (lexicon과 동일 기준)
SPAM = re.compile(
    r"(?:https?://|bit\.ly|official\s?App|그룹방|초대\s?코드|리딩방|오픈\s?채팅|"
    r"무료\s?체험|카톡방|텔레그램|구독\s?서비스|핫딜)"
)

SEED = 20260805
N_SAMPLE = 220


def main():
    rows = [r for r in csv.DictReader(open(BASE / "data" / "master_dataset.csv",
                                           encoding="utf-8-sig"))
            if r["source_type"] not in NEWS]
    pool = [r for r in rows
            if len(r["text"].strip()) >= 20
            and TRADE.search(r["text"])
            and not SPAM.search(r["text"])]

    print(f"커뮤니티 {len(rows):,}행 중 매매 언급 글: {len(pool):,}건 "
          f"({len(pool)/len(rows)*100:.1f}%)")

    rng = random.Random(SEED)
    sample = rng.sample(pool, min(N_SAMPLE, len(pool)))
    out_rows = [{
        "id": r["id"],
        "pool_size": len(pool),
        "source": r["source_label"],
        "stock": r["stock_or_topic"],
        "basis": "",     # 판정자: 심리주도 | 데이터주도 | 혼합 | 불명 | 매매아님
        "psych_type": "",  # 심리주도일 때: 분위기편승|군집|조바심|복수매매|공포이탈|기타
        "outcome": "",   # 손실·물림·후회 | 수익 | 불명
        "text": r["text"].replace("\n", " ")[:450],
    } for r in sample]

    p = OUT / "trade_posts.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print(f"판정 표본 {len(out_rows)}건 (seed={SEED}) → {p}")


if __name__ == "__main__":
    main()
