# 소급 데이터 수집 (PRD §5.4, FR-27~31)

기억이나 자가보고가 아니라 **실측 생체 데이터**로 개인 베이스라인을 산출한다.
PRD의 Phase A를 짧게 만들기 위해, 이미 존재하는 과거 데이터를 먼저 끌어온다.

## 1. 가민 데이터 내보내기

Garmin Connect → 계정 관리 → 데이터 내보내기
https://www.garmin.com/ko-KR/account/datamanagement/exportdata/

요청 후 이메일로 다운로드 링크가 온다 (보통 수 시간~며칠).

```bash
python ingest/garmin_ingest.py "C:\경로\garmin_export.zip"
```

산출물:
- `ingest/data/garmin_daily.csv` — 일자별 안정시심박·최대심박·수면·깊은수면·스트레스·Body Battery
- `ingest/output/baseline_report.md` — 개인 베이스라인, 거래일/비거래일 비교

## 2. 거래 기록 추가 (선택, 그러나 핵심)

`ingest/data/trades.csv` 에 매매한 날짜를 넣으면 **매매한 날 vs 안 한 날**의 생체 지표를 비교한다.
증권사 HTS/MTS에서 거래내역을 CSV로 내려받아 그대로 넣으면 된다. `date`(또는 `일자`) 컬럼만 있으면 동작한다.

```csv
date,stock,side
2026-06-12,삼성전자,매수
```

이 비교표가 PRD §5.4 온보딩 화면의 원재료이며, H1 검증의 출발점이다.

## ⚠️ 보안

이 스크립트는 **이메일 계정 정보를 입력받지 않는다.** 체결통보 메일을 쓰려면
메일 앱에서 직접 내보낸 파일이나 증권사 거래내역 CSV만 사용한다.
FR-28(IMAP 소급 파싱)은 인증 처리 설계가 끝난 뒤 별도 구현한다.
