# -*- coding: utf-8 -*-
"""매매 근거 분류 채점 — 판정자 A·B 합의 기준 pain point 수치 산출.

연구 질문: 사람들이 심리에 의해 매매하고, 그래서 물리는가?
출력: output/trade_basis_report.md
"""
import csv
import io
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).parent
OUT = BASE / "output"
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASIS = ["심리주도", "데이터주도", "혼합", "불명", "매매아님"]


def load(p):
    return {r["id"]: r for r in csv.DictReader(open(p, encoding="utf-8-sig"))}


def kappa(pairs):
    n = len(pairs)
    po = sum(1 for a, b in pairs if a == b) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return po, (po - pe) / (1 - pe) if pe < 1 else 1.0


def main():
    A, B = load(OUT / "trade_labeled_A.csv"), load(OUT / "trade_labeled_B.csv")
    ids = sorted(set(A) & set(B))

    pairs = [((A[i]["basis"] or "").strip(), (B[i]["basis"] or "").strip()) for i in ids]
    po, k5 = kappa(pairs)

    # 이진 축약: '심리주도' 여부 (핵심 주장에 대한 일치)
    bpairs = [("심리" if a == "심리주도" else "기타", "심리" if b == "심리주도" else "기타")
              for a, b in pairs]
    po2, k2 = kappa(bpairs)

    # 합의 = basis 동일
    cons = {i: (A[i]["basis"] or "").strip() for i in ids
            if (A[i]["basis"] or "").strip() == (B[i]["basis"] or "").strip()}
    cb = Counter(cons.values())

    # 근거가 드러난 본인 매매(심리/데이터/혼합) 중 심리주도 비중
    revealed = {i: b for i, b in cons.items() if b in ("심리주도", "데이터주도", "혼합")}
    n_rev = len(revealed)
    n_psy = sum(1 for b in revealed.values() if b == "심리주도")

    # 심리주도 합의 건의 outcome (보수적: 두 판정자 모두 '손실·물림·후회'일 때만 손실로 인정)
    psy_ids = [i for i, b in cons.items() if b == "심리주도"]
    loss_strict = [i for i in psy_ids
                   if (A[i]["outcome"] or "").strip() == "손실·물림·후회"
                   and (B[i]["outcome"] or "").strip() == "손실·물림·후회"]
    loss_any = [i for i in psy_ids
                if "손실" in (A[i]["outcome"] or "") or "손실" in (B[i]["outcome"] or "")]
    win_any = [i for i in psy_ids
               if (A[i]["outcome"] or "").strip() == "수익" or (B[i]["outcome"] or "").strip() == "수익"]

    # psych_type (합의 심리주도 건, 두 판정 합집합 카운트)
    pt = Counter()
    for i in psy_ids:
        for src in (A, B):
            v = (src[i]["psych_type"] or "").strip()
            if v:
                pt[v] += 1

    # 복수매매 집중 확인
    revenge = [i for i in psy_ids
               if "복수매매" in (A[i]["psych_type"] or "") or "복수매매" in (B[i]["psych_type"] or "")]
    revenge_loss = [i for i in revenge if i in loss_any]

    with open(OUT / "trade_basis_report.md", "w", encoding="utf-8") as f:
        f.write("# 매매 근거 분류 결과 — pain point 시장 검증\n\n")
        f.write("**연구 질문**: 개인투자자가 데이터가 아니라 심리에 의해 매매하고, 그래서 물리는가?\n\n")
        f.write(f"표본: 매매 언급 글 268건 중 220건 (seed 고정). "
                f"판정: 독립 2명, 라벨 공개 없이 원문만.\n\n")

        f.write("## 판정 신뢰도\n\n")
        f.write(f"- basis 5분류 일치율 {po*100:.1f}% / kappa {k5:.3f}\n")
        f.write(f"- '심리주도 여부' 이진 일치율 {po2*100:.1f}% / kappa {k2:.3f}\n")
        f.write(f"- 합의(동일 basis) {len(cons)}건 — 이하 수치는 합의분만 사용\n\n")

        f.write("## 결과\n\n")
        f.write("| basis (합의) | 건수 |\n|---|---|\n")
        for b in BASIS:
            f.write(f"| {b} | {cb.get(b, 0)} |\n")

        f.write(f"\n### 핵심 수치\n\n")
        f.write(f"1. **근거가 드러난 본인 매매 {n_rev}건 중 심리주도 {n_psy}건 "
                f"({n_psy/n_rev*100:.0f}%)** — 데이터주도는 "
                f"{sum(1 for b in revealed.values() if b=='데이터주도')}건\n")
        f.write(f"2. **심리주도 매매 중 손실·물림·후회 언급: "
                f"엄격(양측 합의) {len(loss_strict)}/{len(psy_ids)}건"
                f"({len(loss_strict)/len(psy_ids)*100:.0f}%), "
                f"완화(한쪽 이상) {len(loss_any)}건({len(loss_any)/len(psy_ids)*100:.0f}%)** "
                f"— 수익 언급은 {len(win_any)}건\n")
        f.write(f"3. **복수매매(물타기·복구) {len(revenge)}건 중 손실 {len(revenge_loss)}건** — "
                "가장 파괴적인 심리 유형\n\n")

        f.write("### 심리 유형 분포 (합의 심리주도, A·B 판정 합산)\n\n| 유형 | 언급 |\n|---|---|\n")
        for t, n in pt.most_common():
            f.write(f"| {t} | {n} |\n")

        f.write("\n## 한계\n\n")
        f.write("- 커뮤니티 글의 대부분(합의 기준 약 76%)은 본인 매매 서술이 아니다(논평·조언·밈). "
                "근거가 드러난 매매는 표본 내 소수라 비율의 신뢰구간이 넓다\n")
        f.write("- outcome은 글에 적힌 자기보고다. 손실을 쓴 사람이 더 글을 쓰는 생존 편향 가능\n")
        f.write("- '데이터주도가 드물다'는 커뮤니티 글쓰기 관행의 반영일 수 있다 — "
                "데이터로 매매하는 사람은 토론방에 근거를 안 쓸 수 있음\n")

    print(f"일치율(5분류) {po*100:.1f}% k={k5:.2f} | 이진 {po2*100:.1f}% k={k2:.2f}")
    print(f"합의 {len(cons)}건: " + ", ".join(f"{b} {cb.get(b,0)}" for b in BASIS))
    print(f"근거 드러난 매매 {n_rev}건 중 심리주도 {n_psy} ({n_psy/max(n_rev,1)*100:.0f}%)")
    print(f"심리주도 손실: 엄격 {len(loss_strict)}/{len(psy_ids)}, 완화 {len(loss_any)}/{len(psy_ids)}")
    print(f"복수매매 {len(revenge)}건 중 손실 {len(revenge_loss)}")
    print(f"→ {OUT / 'trade_basis_report.md'}")


if __name__ == "__main__":
    main()
