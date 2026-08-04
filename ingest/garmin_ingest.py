# -*- coding: utf-8 -*-
"""가민 소급 데이터 수집기 — PRD FR-27, FR-29 구현

목적: 기억이나 자가보고가 아니라 실제 생체 데이터로 개인 베이스라인을 산출한다.
      (PP5 — 사용자가 말하는 감정과 실제 상태는 일치하지 않을 수 있다)

입력 (둘 중 아무거나):
  A. Garmin Connect "데이터 내보내기" 결과 zip 또는 압축 해제 폴더
     → https://www.garmin.com/ko-KR/account/datamanagement/exportdata/
     → 요청 후 이메일로 링크가 오며 보통 수 시간~며칠 소요
  B. Garmin Connect 웹에서 개별 다운로드한 CSV (심박/수면/스트레스)

출력:
  data/garmin_daily.csv     일자별 통합 지표
  output/baseline_report.md 개인 베이스라인 + 장중/장외 구분 요약

사용법:
  python garmin_ingest.py <내보내기_경로>
"""
import csv
import io
import json
import re
import statistics
import sys
import zipfile
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = BASE / "output"
DATA.mkdir(exist_ok=True)
OUT.mkdir(exist_ok=True)

# Windows 콘솔(cp949)에서 한글·기호 출력이 깨지지 않도록 UTF-8 강제
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 한국 증시 개장 시간 (KST). 장중/장외 구분용.
MARKET_OPEN = (9, 0)
MARKET_CLOSE = (15, 30)


# ────────────────────────────────────────────────────────────
# 1. 파일 탐색 — 가민 내보내기 구조는 버전마다 다르므로 넓게 훑는다
# ────────────────────────────────────────────────────────────
def collect_json_files(root: Path) -> dict[str, list[Path]]:
    """내보내기 폴더에서 관심 있는 JSON들을 분류해 수집."""
    buckets = defaultdict(list)
    patterns = {
        "sleep": ["sleepdata", "sleep_data", "_sleep"],
        "uds": ["udsfile", "uds_file"],              # 일일 요약 (심박·스트레스·걸음)
        "wellness": ["wellness", "biometric"],
        "hr": ["heartrate", "heart_rate"],
        "stress": ["stress"],
    }
    for p in root.rglob("*.json"):
        low = p.name.lower()
        for key, keys in patterns.items():
            if any(k in low for k in keys):
                buckets[key].append(p)
                break
    return buckets


def unzip_if_needed(path: Path) -> Path:
    if path.is_dir():
        return path
    if path.suffix.lower() == ".zip":
        dest = path.parent / (path.stem + "_extracted")
        if not dest.exists():
            print(f"압축 해제 중… → {dest}")
            with zipfile.ZipFile(path) as z:
                z.extractall(dest)
        # 내부에 또 zip이 있는 경우 (가민이 종종 중첩 압축)
        for inner in list(dest.rglob("*.zip")):
            sub = inner.parent / inner.stem
            if not sub.exists():
                try:
                    with zipfile.ZipFile(inner) as z:
                        z.extractall(sub)
                except Exception:
                    pass
        return dest
    raise SystemExit(f"경로가 폴더도 zip도 아닙니다: {path}")


# ────────────────────────────────────────────────────────────
# 2. 파싱 — 키 이름이 버전마다 달라 후보를 순회한다
# ────────────────────────────────────────────────────────────
def _first(d: dict, *keys):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return None


def _to_date(v) -> str | None:
    if v is None:
        return None
    s = str(v)
    m = re.search(r"(\d{4})[-/](\d{2})[-/](\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    if s.isdigit() and len(s) >= 10:  # epoch
        try:
            ts = int(s[:13]) / (1000 if len(s) >= 13 else 1)
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except Exception:
            return None
    return None


def parse_records(paths: list[Path]) -> list[dict]:
    """JSON 파일들에서 dict 레코드를 평평하게 뽑아낸다."""
    recs = []
    for p in paths:
        try:
            obj = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception:
            continue
        if isinstance(obj, dict):
            # 리스트를 품은 dict인 경우 가장 긴 리스트를 취한다
            lists = [v for v in obj.values() if isinstance(v, list) and v]
            obj = max(lists, key=len) if lists else [obj]
        if isinstance(obj, list):
            recs.extend(r for r in obj if isinstance(r, dict))
    return recs


def build_daily(root: Path) -> dict[str, dict]:
    buckets = collect_json_files(root)
    daily: dict[str, dict] = defaultdict(dict)

    # 수면
    for r in parse_records(buckets.get("sleep", [])):
        d = _to_date(_first(r, "calendarDate", "sleepStartTimestampGMT", "date"))
        if not d:
            continue
        sec = _first(r, "sleepTimeSeconds", "totalSleepSeconds", "sleepTimeInSeconds")
        deep = _first(r, "deepSleepSeconds", "deepSleepDurationInSeconds")
        if sec:
            daily[d]["sleep_min"] = round(int(sec) / 60)
        if deep:
            daily[d]["deep_sleep_min"] = round(int(deep) / 60)

    # 일일 요약 (심박·스트레스·Body Battery)
    for key in ("uds", "wellness", "hr", "stress"):
        for r in parse_records(buckets.get(key, [])):
            d = _to_date(_first(r, "calendarDate", "date", "statisticsStartDate"))
            if not d:
                continue
            rhr = _first(r, "restingHeartRate", "restingHR", "minAvgHeartRate")
            maxhr = _first(r, "maxHeartRate", "maxHeartRateValue")
            stress = _first(r, "averageStressLevel", "avgStressLevel", "overallStressLevel")
            bb = _first(r, "bodyBatteryMostRecentValue", "bodyBatteryHighestValue")
            steps = _first(r, "totalSteps", "steps")
            if rhr and int(rhr) > 0:
                daily[d]["resting_hr"] = int(rhr)
            if maxhr and int(maxhr) > 0:
                daily[d]["max_hr"] = int(maxhr)
            if stress is not None and int(stress) >= 0:
                daily[d]["avg_stress"] = int(stress)
            if bb:
                daily[d]["body_battery"] = int(bb)
            if steps:
                daily[d]["steps"] = int(steps)

    return dict(daily)


# ────────────────────────────────────────────────────────────
# 3. 거래일 매칭 — 주말·공휴일 제외 (간이. 정식 캘린더는 추후 교체)
# ────────────────────────────────────────────────────────────
KRX_HOLIDAYS_2026 = {
    "2026-01-01", "2026-02-16", "2026-02-17", "2026-02-18", "2026-03-01",
    "2026-05-05", "2026-05-24", "2026-06-06", "2026-08-15", "2026-09-24",
    "2026-09-25", "2026-09-26", "2026-10-03", "2026-10-09", "2026-12-25",
}


def is_trading_day(d: str) -> bool:
    dt = date.fromisoformat(d)
    return dt.weekday() < 5 and d not in KRX_HOLIDAYS_2026


# ────────────────────────────────────────────────────────────
# 4. 거래 기록 (선택) — 체결 내역 CSV가 있으면 매칭
# ────────────────────────────────────────────────────────────
def load_trades() -> set[str]:
    """data/trades.csv 가 있으면 거래한 날짜 집합을 반환.

    기대 형식: date 컬럼(YYYY-MM-DD) 하나만 있어도 동작.
    증권사 거래내역 CSV를 그대로 넣고 컬럼명만 맞춰도 된다.
    ⚠️ 이메일 계정 정보는 이 스크립트에 절대 입력하지 않는다.
       체결통보는 메일 앱에서 직접 내보낸 파일로만 다룬다.
    """
    p = DATA / "trades.csv"
    if not p.exists():
        return set()
    days = set()
    with open(p, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            for k, v in r.items():
                if k and "date" in k.lower() or (k and "일자" in k):
                    d = _to_date(v)
                    if d:
                        days.add(d)
                    break
    return days


# ────────────────────────────────────────────────────────────
# 5. 리포트
# ────────────────────────────────────────────────────────────
def summarize(vals: list[float]) -> str:
    if not vals:
        return "—"
    m = statistics.mean(vals)
    if len(vals) > 1:
        return f"{m:.1f} (±{statistics.stdev(vals):.1f}, n={len(vals)})"
    return f"{m:.1f} (n=1)"


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n❌ 내보내기 경로를 지정하세요.")
        print("   예: python garmin_ingest.py \"C:\\Users\\user\\Downloads\\garmin_export.zip\"")
        sys.exit(1)

    root = unzip_if_needed(Path(sys.argv[1]))
    daily = build_daily(root)
    if not daily:
        print("❌ 인식 가능한 데이터를 찾지 못했습니다.")
        print("   Garmin Connect > 계정 관리 > 데이터 내보내기 로 받은 zip인지 확인하세요.")
        sys.exit(1)

    trades = load_trades()
    rows = []
    for d in sorted(daily):
        r = {"date": d, "is_trading_day": is_trading_day(d),
             "traded": d in trades if trades else ""}
        r.update(daily[d])
        rows.append(r)

    cols = ["date", "is_trading_day", "traded", "resting_hr", "max_hr",
            "sleep_min", "deep_sleep_min", "avg_stress", "body_battery", "steps"]
    out = DATA / "garmin_daily.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    # 베이스라인
    def col(name, filt=None):
        return [r[name] for r in rows if name in r and r[name] != ""
                and (filt is None or filt(r))]

    with open(OUT / "baseline_report.md", "w", encoding="utf-8") as f:
        f.write("# 개인 베이스라인 리포트\n\n")
        f.write(f"기간: {rows[0]['date']} ~ {rows[-1]['date']} ({len(rows)}일)\n\n")
        f.write("> 자가보고가 아니라 실측 데이터다. PP5(사용자가 말하는 감정과 실제 상태의 불일치)에 대한 대응.\n\n")

        f.write("## 전체 베이스라인\n\n| 지표 | 평균 (±SD) |\n|---|---|\n")
        for name, label in [("resting_hr", "안정시 심박"), ("max_hr", "최대 심박"),
                            ("sleep_min", "수면(분)"), ("deep_sleep_min", "깊은수면(분)"),
                            ("avg_stress", "평균 스트레스"), ("body_battery", "Body Battery")]:
            f.write(f"| {label} | {summarize(col(name))} |\n")

        f.write("\n## 거래일 vs 비거래일\n\n")
        f.write("| 지표 | 거래일(장 열림) | 비거래일(주말·공휴일) |\n|---|---|---|\n")
        for name, label in [("resting_hr", "안정시 심박"), ("sleep_min", "수면(분)"),
                            ("avg_stress", "평균 스트레스")]:
            a = summarize(col(name, lambda r: r["is_trading_day"]))
            b = summarize(col(name, lambda r: not r["is_trading_day"]))
            f.write(f"| {label} | {a} | {b} |\n")

        if trades:
            f.write(f"\n## 실제 매매한 날 vs 안 한 날 (거래 기록 {len(trades)}일 확보)\n\n")
            f.write("| 지표 | 매매한 날 | 매매 안 한 날 |\n|---|---|---|\n")
            for name, label in [("resting_hr", "안정시 심박"), ("sleep_min", "수면(분)"),
                                ("avg_stress", "평균 스트레스"), ("body_battery", "Body Battery")]:
                a = summarize(col(name, lambda r: r["traded"] is True))
                b = summarize(col(name, lambda r: r["is_trading_day"] and r["traded"] is False))
                f.write(f"| {label} | {a} | {b} |\n")
            f.write("\n> 이 표가 PRD §5.4 온보딩 화면의 원재료다.\n")
        else:
            f.write("\n## 실제 매매한 날 비교\n\n")
            f.write("`data/trades.csv`(date 컬럼 포함)를 넣으면 매매한 날과 안 한 날의 "
                    "생체 지표를 비교한다. 증권사 거래내역을 CSV로 내려받아 그대로 넣으면 된다.\n")

    print(f"✅ {len(rows)}일치 처리 → {out}")
    print(f"✅ 베이스라인 리포트 → {OUT / 'baseline_report.md'}")
    if not trades:
        print("ℹ️  data/trades.csv 를 추가하면 매매일 비교까지 산출됩니다.")


if __name__ == "__main__":
    main()
