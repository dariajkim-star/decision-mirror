# -*- coding: utf-8 -*-
"""렉시콘 v1 vs v2 채점 — 층화 표본의 독립 판정 라벨 대비 정밀도·재현율.

두 판정자(A·B)의 라벨을 읽어
  1) 판정자 간 일치도(Cohen's kappa 근사)를 계산하고
  2) 두 판정자가 합의한 항목만 gold로 삼아
  3) v1·v2의 정밀도·재현율을 층화 가중으로 추정한다.

층화 추출이므로 단순 평균이 아니라 **층 크기로 가중**해야 모집단 추정치가 된다.

출력: output/lexicon_scorecard.md
"""
import csv
import io
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EMOTIONS = ["FOMO·상대적박탈감", "불안·공포", "후회·손실고통", "분노·불신", "충동·중독시그널"]


def parse(v: str) -> set[str]:
    if not v or v.strip().upper() == "NONE":
        return set()
    return {x.strip() for x in v.split("|") if x.strip() and x.strip().upper() != "NONE"}


def wilson(k: int, n: int) -> tuple[float, float]:
    """Wilson 95% 신뢰구간."""
    if n == 0:
        return (0.0, 0.0)
    z, p = 1.96, k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, (c - m) / d), min(1.0, (c + m) / d))


def main():
    a = {r["id"]: r for r in csv.DictReader(open(OUT / "gold_labeled_A.csv", encoding="utf-8-sig"))}
    b = {r["id"]: r for r in csv.DictReader(open(OUT / "gold_labeled_B.csv", encoding="utf-8-sig"))}
    ids = sorted(set(a) & set(b))
    print(f"공통 판정 {len(ids)}건")

    # ── 판정자 간 일치도 (이진: 감정 있음/없음) ──
    agree = sum(1 for i in ids if bool(parse(a[i]["label"])) == bool(parse(b[i]["label"])))
    po = agree / len(ids)
    pa1 = sum(1 for i in ids if parse(a[i]["label"])) / len(ids)
    pb1 = sum(1 for i in ids if parse(b[i]["label"])) / len(ids)
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0

    # ── 합의 항목만 gold ──
    gold = {}
    for i in ids:
        la, lb = parse(a[i]["label"]), parse(b[i]["label"])
        if bool(la) == bool(lb):          # 감정 유무가 일치할 때만 채택
            gold[i] = (la & lb) if (la and lb) else set()

    rows = {r["id"]: r for r in csv.DictReader(open(OUT / "gold_sample.csv", encoding="utf-8-sig"))}

    # ── 층화 가중 정밀도·재현율 ──
    def score(tagcol: str) -> dict:
        # 층별 카운트
        st = defaultdict(lambda: {"n": 0, "tp": 0, "pred": 0, "act": 0, "size": 0})
        for i, g in gold.items():
            r = rows[i]
            s = st[r["stratum"]]
            s["size"] = int(r["stratum_size"])
            s["n"] += 1
            pred = bool(parse(r[tagcol]))
            act = bool(g)
            s["pred"] += pred
            s["act"] += act
            s["tp"] += pred and act
        # 층 가중 합계 (각 층에서 표본 → 모집단으로 확대)
        TP = PRED = ACT = 0.0
        raw_tp = raw_pred = 0
        for s in st.values():
            if s["n"] == 0:
                continue
            w = s["size"] / s["n"]
            TP += s["tp"] * w
            PRED += s["pred"] * w
            ACT += s["act"] * w
            raw_tp += s["tp"]
            raw_pred += s["pred"]
        prec = TP / PRED if PRED else 0.0
        rec = TP / ACT if ACT else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        lo, hi = wilson(raw_tp, raw_pred)
        return {"precision": prec, "recall": rec, "f1": f1,
                "est_tagged": PRED, "est_true": ACT,
                "raw_tp": raw_tp, "raw_pred": raw_pred, "ci": (lo, hi)}

    s1, s2 = score("v1_tags"), score("v2_tags")

    with open(OUT / "lexicon_scorecard.md", "w", encoding="utf-8") as f:
        f.write("# 렉시콘 정밀도 채점표\n\n")
        f.write(f"층화 표본 {len(ids)}건에 대해 **두 명의 독립 판정자**가 라벨링했다. "
                "판정자는 렉시콘 출력을 보지 않고 원문만 읽었다.\n\n")
        f.write("## 판정자 간 신뢰도\n\n")
        f.write(f"- 단순 일치율: **{po*100:.1f}%**\n")
        f.write(f"- Cohen's kappa: **{kappa:.3f}** "
                f"({'우수' if kappa>=.8 else '양호' if kappa>=.6 else '보통' if kappa>=.4 else '낮음'})\n")
        f.write(f"- 합의 항목만 gold로 채택: **{len(gold)}건** "
                f"(불일치 {len(ids)-len(gold)}건 제외)\n\n")

        f.write("## 정밀도·재현율 (층 크기로 가중한 모집단 추정)\n\n")
        f.write("| | v1 (단순 문자열) | v2 (패턴 기반) |\n|---|---|---|\n")
        f.write(f"| **정밀도** | {s1['precision']*100:.1f}% | **{s2['precision']*100:.1f}%** |\n")
        f.write(f"| 정밀도 95% CI | [{s1['ci'][0]*100:.0f}–{s1['ci'][1]*100:.0f}%] | "
                f"[{s2['ci'][0]*100:.0f}–{s2['ci'][1]*100:.0f}%] |\n")
        f.write(f"| **재현율** | {s1['recall']*100:.1f}% | {s2['recall']*100:.1f}% |\n")
        f.write(f"| F1 | {s1['f1']*100:.1f}% | {s2['f1']*100:.1f}% |\n")
        f.write(f"| 태깅 추정 건수 | {s1['est_tagged']:,.0f} | {s2['est_tagged']:,.0f} |\n\n")

        f.write(f"판정자 합의 기준 **실제 감정 보유 문서 추정치: {s2['est_true']:,.0f}건** "
                f"(커뮤니티 4,576행 대비 {s2['est_true']/4576*100:.1f}%)\n\n")
        f.write("> 이 추정치가 보고서에 쓸 공식 수치다. "
                "렉시콘 태깅 건수(v1 615 / v2 336)는 정밀도 보정 전 원시값이므로 단독 인용하지 않는다.\n")

    print(f"\n판정자 일치율 {po*100:.1f}% / kappa {kappa:.3f} / gold {len(gold)}건")
    print(f"v1 정밀도 {s1['precision']*100:.1f}%  재현율 {s1['recall']*100:.1f}%")
    print(f"v2 정밀도 {s2['precision']*100:.1f}%  재현율 {s2['recall']*100:.1f}%")
    print(f"실제 감정 보유 추정 {s2['est_true']:,.0f}건 ({s2['est_true']/4576*100:.1f}%)")
    print(f"→ {OUT / 'lexicon_scorecard.md'}")


if __name__ == "__main__":
    main()
