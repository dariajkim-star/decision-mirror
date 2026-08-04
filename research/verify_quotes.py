# -*- coding: utf-8 -*-
"""인용문 검증 — PRD/기획안에 인용한 모든 원문이 실제 수집 데이터에 존재하는지 대조.

할루시네이션 방지 장치. 인용문을 하드코딩해두고 raw CSV 전체를 스캔해
어느 파일 몇 번째 행에서 나왔는지, 원문 전체가 무엇인지 기록한다.

출력:
  output/quote_verification.csv  — 인용문별 검증 결과 (파일/행번호/원문/메타)
  콘솔                            — PASS/FAIL 요약
"""
import csv
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# PRD·기획안에 인용한 문장들. (라벨, 검색할 고유 부분문자열)
QUOTES = [
    ("원형1-에코7억", "나이40 다시 재취업"),
    ("원형1-퇴직금연쇄", "계좌를 못멸어보고"),
    ("원형1-불패", "2009년부터 투자하며"),
    ("원형1-수면", "심란해서 잠도 안온다"),
    ("원형1-배터리아저씨", "배터리 아저씨 덕분에"),
    ("원형2-등산포기", "등산을 포기하고"),
    ("원형2-단타", "적당히 내리면 사고 적당히 오르면"),
    ("원형2-우연신호", "내가 어제 우연히 만든 신호"),
    ("원형3-항상이런마음", "내일 항상 이런 마음을 가진다"),
    ("원형3-내탓", "내가 멍청한 탓"),
    ("원형3-장초반", "오늘 장초반에 팔았어야"),
    ("원형4-풀미수", "풀미수베팅"),
    ("원형4-강제청산", "강제 청산당했다"),
    ("원형4-몰빵", "신용미수전재산몰빵"),
    ("PP-벼락거지", "아빠! 우리는 왜 집이 없어요"),
    ("PP-3억손실", "3억 손실"),
    ("PP-26만원물림", "26만원위에서 물렸으면"),
    ("PP-불장퍼랭이", "불장에 혼자 퍼랭이"),
    ("PP-지금이라도", "지금이라도 늦지 않았다"),
    ("PP-37층낙엽", "37층 낙엽"),
    ("PP-반토막자기혐오", "내가 왜 이따우껄 처다봤는지"),
]


def load_all() -> list[dict]:
    """모든 raw CSV를 파일명·행번호와 함께 로드."""
    rows = []
    for p in sorted(DATA.glob("raw_*.csv")):
        with open(p, encoding="utf-8-sig") as f:
            for i, r in enumerate(csv.DictReader(f), start=2):  # 헤더가 1행
                r["_file"] = p.name
                r["_line"] = i
                rows.append(r)
    return rows


def main():
    rows = load_all()
    files = sorted({r["_file"] for r in rows})
    print(f"검증 대상: {len(rows):,}행 / {len(files)}개 파일")
    for fn in files:
        n = sum(1 for r in rows if r["_file"] == fn)
        print(f"  - {fn}: {n:,}행")
    print()

    results = []
    n_pass = 0
    for label, needle in QUOTES:
        hits = [r for r in rows if needle in (r.get("text") or "")]
        if hits:
            n_pass += 1
            for h in hits:
                results.append({
                    "label": label,
                    "search_string": needle,
                    "status": "FOUND",
                    "file": h["_file"],
                    "line": h["_line"],
                    "source": h.get("source", ""),
                    "stock": h.get("stock", ""),
                    "date": h.get("date", ""),
                    "full_text": (h.get("text") or "").replace("\n", " "),
                })
            print(f"  ✅ {label:22} → {hits[0]['_file']}:{hits[0]['_line']} ({len(hits)}건)")
        else:
            results.append({
                "label": label, "search_string": needle, "status": "NOT_FOUND",
                "file": "", "line": "", "source": "", "stock": "", "date": "", "full_text": "",
            })
            print(f"  ❌ {label:22} → 원문에서 찾을 수 없음")

    out = OUT / "quote_verification.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["label", "search_string", "status", "file",
                                          "line", "source", "stock", "date", "full_text"])
        w.writeheader()
        w.writerows(results)

    print(f"\n{n_pass}/{len(QUOTES)} 인용문 검증 통과 → {out}")
    if n_pass < len(QUOTES):
        print("⚠️  검증 실패 항목이 있습니다. 해당 인용문을 문서에서 제거하거나 수정하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
