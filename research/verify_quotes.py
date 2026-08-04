# -*- coding: utf-8 -*-
"""인용문 검증 — PRD/기획안에 인용한 모든 원문이 실제 수집 데이터에 존재하는지 대조.

할루시네이션 방지 장치. 인용문을 하드코딩해두고 raw CSV 전체를 스캔해
어느 파일 몇 번째 행에서 나왔는지, 원문 전체가 무엇인지 기록한다.

출력:
  output/quote_verification.csv  — 인용문별 검증 결과 (파일/행번호/원문/메타)
  콘솔                            — PASS/FAIL 요약
"""
import csv
import io
import sys
from pathlib import Path

DATA = Path(__file__).parent / "data"
OUT = Path(__file__).parent / "output"
OUT.mkdir(exist_ok=True)

# Windows 콘솔(cp949)에서 한글·기호가 깨지지 않도록 UTF-8 강제
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

# ⚠️ 문자열 존재 확인만으로는 부족하다.
#    실제로 DM-001898("심란해서 잠도 안온다")을 수면-매매 연결 근거로 인용했다가,
#    원문의 불면 원인이 매매가 아니라 재취업 직장 걱정임이 드러나 인용을 철회했다.
#    → 각 인용에 '이 인용으로 무엇을 주장하는가(claim)'를 함께 적고,
#      full_text를 눈으로 읽어 주장과 맥락이 맞는지 사람이 확인해야 한다.
#    스크립트는 존재 여부만 보증하며, 맥락 타당성은 보증하지 않는다.

# (라벨, 검색할 고유 부분문자열, 이 인용으로 뒷받침하려는 주장)
QUOTES = [
    ("원형1-에코7억", "나이40 다시 재취업", "고점 추격 후 물림이 삶의 계획(파이어족)을 바꿨다"),
    ("원형1-퇴직금연쇄", "계좌를 못멸어보고", "손실 국면에서 계좌 확인을 회피하는 행동이 나타난다"),
    ("원형1-불패", "2009년부터 투자하며", "장기 성공 경험이 과신으로 이어진다"),
    ("원형1-배터리아저씨", "배터리 아저씨 덕분에", "인플루언서가 진입 트리거로 작동한다"),
    ("원형2-등산포기", "등산을 포기하고", "신체 활동이 차트 응시로 대체된다"),
    ("원형2-단타", "적당히 내리면 사고 적당히 오르면", "고빈도 모니터링이 전략으로 정당화된다"),
    ("원형2-우연신호", "내가 어제 우연히 만든 신호", "자기만의 신호 체계를 만들어 진입을 합리화한다"),
    ("원형3-항상이런마음", "내일 항상 이런 마음을 가진다", "패턴을 자각하면서도 반복한다 (PP4)"),
    ("원형3-내탓", "내가 멍청한 탓", "손실을 자기 귀인하는 유형이 존재한다"),
    ("원형3-장초반", "오늘 장초반에 팔았어야", "실시간 우유부단과 불안이 동시에 나타난다"),
    ("원형4-풀미수", "풀미수베팅", "레버리지 사용자가 스스로 신경 쓰인다고 인지한다"),
    ("원형4-강제청산", "강제 청산당했다", "강제청산 계좌의 62%가 35세 이하 (뉴스 인용)"),
    ("원형4-몰빵", "신용미수전재산몰빵", "전재산 레버리지 투입 표현이 실재한다"),
    ("PP-벼락거지", "아빠! 우리는 왜 집이 없어요", "상대적 박탈감이 가족 맥락으로 표현된다"),
    ("PP-3억손실", "3억 손실", "대규모 손실 진술이 토론방에 실재한다"),
    ("PP-26만원물림", "26만원위에서 물렸으면", "고점 물림이 장기 고통으로 인식된다"),
    ("PP-불장퍼랭이", "불장에 혼자 퍼랭이", "소외 공포가 표현된다"),
    ("PP-지금이라도", "지금이라도 늦지 않았다", "FOMO 권유 문화가 커뮤니티에 존재한다"),
    ("PP-37층낙엽", "37층 낙엽", "장기 물림의 정서적 표현"),
    ("PP-반토막자기혐오", "내가 왜 이따우껄 처다봤는지", "손실이 자기혐오와 신체 증상으로 이어진다"),
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
    for label, needle, claim in QUOTES:
        hits = [r for r in rows if needle in (r.get("text") or "")]
        if hits:
            n_pass += 1
            for h in hits:
                results.append({
                    "label": label,
                    "claim": claim,
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
                "label": label, "claim": claim, "search_string": needle, "status": "NOT_FOUND",
                "file": "", "line": "", "source": "", "stock": "", "date": "", "full_text": "",
            })
            print(f"  ❌ {label:22} → 원문에서 찾을 수 없음")

    out = OUT / "quote_verification.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["label", "claim", "search_string", "status",
                                          "file", "line", "source", "stock", "date", "full_text"])
        w.writeheader()
        w.writerows(results)

    print(f"\n{n_pass}/{len(QUOTES)} 인용문 '존재' 확인 → {out}")
    print("⚠️  이 스크립트는 문자열 존재만 보증한다. 인용이 claim을 실제로 뒷받침하는지는")
    print("   full_text를 사람이 읽고 확인해야 한다. (DM-001898 오독 사례 참조)")
    if n_pass < len(QUOTES):
        print("❌ 원문에서 찾을 수 없는 인용이 있습니다. 문서에서 제거하거나 수정하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
