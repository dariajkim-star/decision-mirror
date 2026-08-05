# -*- coding: utf-8 -*-
"""가민 커넥트 웹 CSV 수집기 — 주간 수면·안정시심박 + 일별 HRV

garmin_ingest.py(전체 내보내기 zip용)와 별개로, 커넥트 웹에서 지표별로
내려받은 CSV를 파싱한다. daria 실데이터 형식 기준:

  수면.csv            주간 집계 (기간, 평균 점수·기간·취침시간)
  안정 시 심박수.csv   주간 (MM/DD/YYYY, bpm)
  HRV 상태.csv        일별 (야간 HRV, 기준 범위, 7일 평균) — 결측 '--' 다수

출력:
  data/garmin_weekly.csv   주 단위 통합
  data/garmin_hrv_daily.csv 일별 HRV
  output/baseline_report.md 개인 베이스라인 (실데이터)

사용법:
  python garmin_csv_ingest.py <수면.csv> <안정시심박.csv> <HRV.csv>
"""
import csv
import io
import re
import statistics
import sys
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = BASE / "output"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _dur_to_min(s: str) -> float | None:
    """'6h 50분' → 410."""
    if not s or s.strip() in ("--", ""):
        return None
    h = re.search(r"(\d+)\s*h", s)
    m = re.search(r"(\d+)\s*분", s)
    if not h and not m:
        return None
    return (int(h.group(1)) * 60 if h else 0) + (int(m.group(1)) if m else 0)


def _clock_to_min(s: str) -> float | None:
    """'2:26 AM' → 자정 기준 분(다음날 새벽은 +). '10:43 PM' → -77 (전날 밤)."""
    if not s or s.strip() in ("--", ""):
        return None
    m = re.match(r"(\d+):(\d+)\s*(AM|PM)", s.strip())
    if not m:
        return None
    hh, mm, ap = int(m.group(1)), int(m.group(2)), m.group(3)
    hh = hh % 12 + (12 if ap == "PM" else 0)
    v = hh * 60 + mm
    # 취침시간으로서 해석: 오후(PM)면 자정 이전 → 음수로 접어 연속 척도化
    return v - 1440 if v >= 12 * 60 else v


def _ms(s: str) -> float | None:
    if not s or s.strip() in ("--", ""):
        return None
    m = re.search(r"(\d+)\s*ms", s)
    return float(m.group(1)) if m else None


def _open_kr(path: Path):
    """가민 CSV는 utf-8-sig 또는 cp949 — 둘 다 시도."""
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp949"):
        try:
            return io.StringIO(raw.decode(enc))
        except UnicodeDecodeError:
            continue
    return io.StringIO(raw.decode("utf-8", errors="replace"))


def parse_sleep(path: Path) -> list[dict]:
    """주간 수면. 날짜 필드에 미인용 쉼표가 있어(예: '12월 31일, 2025 - 1월 6일, 2026')
    셀 수가 7을 넘으면 앞쪽 셀들을 날짜로 재결합한다."""
    rows = []
    rdr = csv.reader(_open_kr(path))
    header = next(rdr)
    n = len(header)  # 7
    for cells in rdr:
        if not cells or not any(cells):
            continue
        if len(cells) > n:
            extra = len(cells) - n
            cells = [", ".join(cells[: 1 + extra])] + cells[1 + extra:]
        r = dict(zip(header, cells))
        score = (r.get("평균 점수") or "").strip()
        rows.append({
            "week": (r.get("날짜") or "").strip(),
            "sleep_score": float(score) if score and score != "--" else None,
            "sleep_min": _dur_to_min(r.get("평균 기간", "")),
            "bedtime_min": _clock_to_min(r.get("평균 취침 시간", "")),
            "quality": (r.get("평균 품질") or "").strip(),
        })
    return rows


def parse_rhr(path: Path) -> list[dict]:
    rows = []
    if True:
        rdr = csv.reader(_open_kr(path))
        next(rdr)  # 헤더(첫 칸 무명)
        for cells in rdr:
            if len(cells) >= 2 and cells[0].strip():
                try:
                    rows.append({"week_start": cells[0].strip(),
                                 "resting_hr": float(cells[1])})
                except ValueError:
                    pass
    return rows


def parse_hrv(path: Path) -> list[dict]:
    rows = []
    if True:
        for r in csv.DictReader(_open_kr(path)):
            base = r.get("기준", "")
            bm = re.match(r"(\d+)ms\s*-\s*(\d+)ms", base.strip()) if base else None
            rows.append({
                "date": r.get("날짜", "").strip(),
                "hrv_ms": _ms(r.get("야간 HRV", "")),
                "base_lo": float(bm.group(1)) if bm else None,
                "base_hi": float(bm.group(2)) if bm else None,
                "avg7": _ms(r.get("7일 평균", "")),
            })
    return rows


def fmt_stats(vals: list[float], unit: str = "") -> str:
    v = [x for x in vals if x is not None]
    if not v:
        return "—"
    s = f"{statistics.mean(v):.1f}{unit}"
    if len(v) > 1:
        s += f" (±{statistics.stdev(v):.1f}, n={len(v)})"
    return s


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    sleep = parse_sleep(Path(sys.argv[1]))
    rhr = parse_rhr(Path(sys.argv[2]))
    hrv = parse_hrv(Path(sys.argv[3]))

    # 저장
    with open(DATA / "garmin_weekly.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["week", "sleep_score", "sleep_min",
                                          "bedtime_min", "quality"])
        w.writeheader()
        w.writerows(sleep)
    with open(DATA / "garmin_hrv_daily.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["date", "hrv_ms", "base_lo", "base_hi", "avg7"])
        w.writeheader()
        w.writerows(hrv)

    sl = [r["sleep_min"] for r in sleep if r["sleep_min"]]
    sc = [r["sleep_score"] for r in sleep if r["sleep_score"]]
    bt = [r["bedtime_min"] for r in sleep if r["bedtime_min"] is not None]
    rh = [r["resting_hr"] for r in rhr]
    hv = [r["hrv_ms"] for r in hrv if r["hrv_ms"]]
    hrv_missing = sum(1 for r in hrv if r["hrv_ms"] is None)

    # 취침 자정 이후 비율·수면 부족 주
    late = sum(1 for b in bt if b > 0)          # 자정 넘어 취침
    very_late = sum(1 for b in bt if b >= 120)  # 새벽 2시 이후
    short_weeks = [r for r in sleep if r["sleep_min"] and r["sleep_min"] < 330]
    below_base = [r for r in hrv if r["hrv_ms"] and r["base_lo"] and r["hrv_ms"] < r["base_lo"]]

    with open(OUT / "baseline_report.md", "w", encoding="utf-8") as f:
        f.write("# 개인 베이스라인 리포트 — 가민 실데이터\n\n")
        f.write("> ⚠️ 수면·심박은 **주간 집계**라 일 단위 분석(매매일 대조)은 불가.\n"
                "> 일 단위 연결은 가민 전체 내보내기(zip) 또는 일별 CSV + 거래내역이 필요하다.\n\n")

        f.write("## 전체 베이스라인\n\n| 지표 | 값 | 기간 |\n|---|---|---|\n")
        f.write(f"| 안정시 심박 (주평균) | {fmt_stats(rh, 'bpm')} | {rhr[0]['week_start']} ~ {rhr[-1]['week_start']} |\n")
        f.write(f"| 수면 시간 (주평균) | {fmt_stats(sl, '분')} = {statistics.mean(sl)/60:.1f}시간 | 53주 |\n")
        f.write(f"| 수면 점수 (주평균) | {fmt_stats(sc)} | |\n")
        f.write(f"| 야간 HRV (일별) | {fmt_stats(hv, 'ms')} | 최근 28일 |\n\n")

        f.write("## 시그널이 될 만한 관찰\n\n")
        f.write(f"- **취침 시간이 자정을 넘긴 주: {late}/{len(bt)}주** — 새벽 2시 이후 취침 주도 {very_late}주\n")
        f.write(f"- **주평균 수면 5.5시간 미만인 주: {len(short_weeks)}주** — 최저 4h 0분(9월), 4h 24분(4월)\n")
        f.write(f"- HRV가 개인 기준 하한 아래로 내려간 날: {len(below_base)}일 / 측정 {len(hv)}일")
        for r in below_base:
            f.write(f" ({r['date']} {r['hrv_ms']:.0f}ms < {r['base_lo']:.0f}ms)")
        f.write("\n")
        f.write(f"- **HRV 결측 {hrv_missing}/{len(hrv)}일 ({hrv_missing/len(hrv)*100:.0f}%)** — "
                "워치 야간 착용이 불규칙. H10 보완 또는 착용 습관이 필요\n\n")

        f.write("## PRD 연결\n\n")
        f.write("- 개인 기준선(FR-5)의 초기값: 안정시 심박 ~47bpm, 야간 HRV 기준 48–64ms(가민 자체 산출)\n")
        f.write("- 수면 변동성이 매우 크다(주평균 4h~10h41m) → L1 문구('어젯밤 수면')의 정보 가치가 높은 프로파일\n")
        f.write("- 다음 단계: **거래내역 CSV**(ingest/data/trades.csv)가 오면 저수면·HRV 하락 주와 매매 빈도의 상관을 확인한다(OI-3)\n")

    print(f"수면 {len(sleep)}주 / 심박 {len(rhr)}주 / HRV {len(hrv)}일 (결측 {hrv_missing})")
    print(f"→ {OUT / 'baseline_report.md'}")


if __name__ == "__main__":
    main()
