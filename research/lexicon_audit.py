# -*- coding: utf-8 -*-
"""렉시콘 진단 — 어떤 키워드가 몇 건을 태깅했고, 그중 오탐이 무엇인지 드러낸다.

적대적 리뷰에서 '충동·중독' 태그의 약 35%가 오탐으로 지적됨
(예: "식중독확산"←중독, "전기차 올인 전략"←올인). §2.1의 관찰 4개가
이 태깅 위에 서 있으므로 정밀화 전에 원인부터 특정한다.

출력: output/lexicon_audit.md — 키워드별 발화 건수 + 원문 샘플
"""
import csv
import io
import sys
from collections import Counter, defaultdict
from pathlib import Path

from analyze import LEXICON

BASE = Path(__file__).parent
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NEWS = {"gnews", "news", "news_desc", "naver_main_news", "naver_main_desc", "fin_news"}


def load_community() -> list[dict]:
    p = BASE / "data" / "master_dataset.csv"
    with open(p, encoding="utf-8-sig") as f:
        return [r for r in csv.DictReader(f) if r["source_type"] not in NEWS]


def main():
    rows = load_community()
    print(f"커뮤니티 {len(rows):,}행")

    # 키워드별 발화 추적
    fires: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in rows:
        t = r["text"].lower()
        for emo, words in LEXICON.items():
            for w in words:
                if w in t:
                    fires[(emo, w)].append(r)

    with open(OUT / "lexicon_audit.md", "w", encoding="utf-8") as f:
        f.write("# 렉시콘 진단 — 키워드별 발화 내역\n\n")
        f.write(f"대상: 커뮤니티 {len(rows):,}행\n\n")
        f.write("각 키워드가 몇 건을 태깅했는지, 그 원문이 무엇인지 나열한다. "
                "발화 건수가 많은데 원문이 엉뚱하면 그 키워드가 오탐의 주범이다.\n\n")

        for emo in LEXICON:
            f.write(f"## {emo}\n\n")
            kws = [(w, len(fires[(emo, w)])) for w in LEXICON[emo] if fires[(emo, w)]]
            kws.sort(key=lambda x: -x[1])
            dead = [w for w in LEXICON[emo] if not fires[(emo, w)]]

            f.write("| 키워드 | 발화 |\n|---|---|\n")
            for w, n in kws:
                f.write(f"| `{w}` | {n} |\n")
            if dead:
                f.write(f"\n미발화 키워드: {', '.join('`'+w+'`' for w in dead)}\n")

            f.write("\n### 원문 샘플\n\n")
            for w, n in kws:
                f.write(f"**`{w}`** ({n}건)\n\n")
                for r in fires[(emo, w)][:8]:
                    txt = r["text"][:130].replace("\n", " ")
                    f.write(f"- `{r['id']}` {txt}\n")
                f.write("\n")

    # 콘솔 요약
    for emo in LEXICON:
        kws = sorted([(w, len(fires[(emo, w)])) for w in LEXICON[emo] if fires[(emo, w)]],
                     key=lambda x: -x[1])
        top = ", ".join(f"{w}({n})" for w, n in kws[:6])
        print(f"\n[{emo}] 상위 발화: {top}")

    print(f"\n→ {OUT / 'lexicon_audit.md'}")


if __name__ == "__main__":
    main()
