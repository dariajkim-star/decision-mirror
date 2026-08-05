# -*- coding: utf-8 -*-
"""정밀도 측정용 층화 표본 생성.

렉시콘의 정확도를 주장하려면 독립적인 정답(gold standard)이 필요하다.
v1 태깅분 / v2 태깅분 / 양쪽 미태깅분에서 층화 추출해, 이 표본에 대해서만
독립 판정을 받고 정밀도·재현율을 계산한다.

출력: output/gold_sample.csv  (판정자가 label 컬럼을 채운다)
"""
import csv
import io
import random
import sys
from pathlib import Path

# ⚠️ 재현성 주의: 이 표본은 analyze.py가 아직 v1 렉시콘이던 시점(2026-08-05)에 생성됐다.
#    이후 analyze.py는 lexicon.py(v2)로 위임되어 v1 층은 재현되지 않는다.
#    표본 자체는 output/gold_sample.csv 로 고정 보존되어 채점 재현에는 문제 없다.
import analyze as v1
import lexicon as v2

BASE = Path(__file__).parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NEWS = {"gnews", "news", "news_desc", "naver_main_news", "naver_main_desc", "fin_news"}
SEED = 20260804
N_PER_STRATUM = 60


def main():
    rows = [r for r in csv.DictReader(open(BASE / "data" / "master_dataset.csv",
                                           encoding="utf-8-sig"))
            if r["source_type"] not in NEWS and len(r["text"].strip()) >= 10]

    strata = {"v1_only": [], "v2_only": [], "both": [], "neither": []}
    for r in rows:
        a, b = bool(v1.emotion_tag(r["text"])), bool(v2.emotion_tag(r["text"]))
        key = "both" if (a and b) else "v1_only" if a else "v2_only" if b else "neither"
        strata[key].append(r)

    print("층별 모집단:")
    for k, v in strata.items():
        print(f"  {k:10} {len(v):>5,}")

    rng = random.Random(SEED)
    sample = []
    for name, pool in strata.items():
        n = min(N_PER_STRATUM, len(pool))
        for r in rng.sample(pool, n):
            sample.append({
                "id": r["id"],
                "stratum": name,
                "stratum_size": len(pool),
                "v1_tags": "|".join(v1.emotion_tag(r["text"])),
                "v2_tags": "|".join(v2.emotion_tag(r["text"])),
                "v2_matches": "|".join(f"{e}:{m}" for e, m in v2.match_detail(r["text"])),
                "label": "",          # 판정자가 채움: 감정 태그(복수는 |) 또는 NONE
                "text": r["text"].replace("\n", " ")[:400],
            })
    rng.shuffle(sample)

    p = OUT / "gold_sample.csv"
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(sample[0].keys()))
        w.writeheader()
        w.writerows(sample)
    print(f"\n표본 {len(sample)}건 → {p}")
    print(f"(층별 최대 {N_PER_STRATUM}건, seed={SEED})")


if __name__ == "__main__":
    main()
