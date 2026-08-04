# -*- coding: utf-8 -*-
"""전체 수집 원본을 추적 가능한 단일 CSV로 통합 저장.

목적: 문서에 인용된 모든 문장이 어느 크롤러의 어느 행에서 왔는지 100% 역추적 가능하게 한다.
      각 행에 고유 ID를 부여하므로 인용문에 `DM-000914` 같은 식으로 출처를 달 수 있다.

출력:
  data/master_dataset.csv   전체 5,022행 + 출처 메타 + 감정 태그
  output/dataset_manifest.md 파일별 행수·수집일·크롤러 대응표
"""
import csv
import hashlib
from collections import Counter
from pathlib import Path

from analyze import emotion_tag

BASE = Path(__file__).parent
DATA = BASE / "data"
OUT = BASE / "output"
OUT.mkdir(exist_ok=True)

# 파일 → (크롤러 스크립트, 채널 설명)
PROVENANCE = {
    "raw_texts.csv": ("crawler.py", "네이버 종목토론방 제목 + 네이버 통합검색 뉴스"),
    "raw_details.csv": ("crawler_detail.py", "네이버 종목토론방 본문 + CBOX 댓글"),
    "raw_news.csv": ("crawler_news3.py", "네이버 금융 메인뉴스 + 구글뉴스 RSS"),
    "raw_dcinside.csv": ("crawler_dcinside.py", "디시인사이드 주식갤 4개(제목·본문)"),
    "raw_youtube.csv": ("crawler_youtube.py", "유튜브 댓글(삼프로TV·슈카월드)"),
    "raw_blind.csv": ("crawler_blind.py", "블라인드 주식·투자 라운지(쿠키 필요)"),
}

SOURCE_LABEL = {
    "board": "토론방 제목", "board_body": "토론방 본문", "board_comment": "토론방 댓글",
    "dc_title": "디시 제목", "dc_body": "디시 본문", "dc_comment": "디시 댓글",
    "yt_comment": "유튜브 댓글", "gnews": "구글뉴스", "news": "네이버뉴스",
    "news_desc": "네이버뉴스 요약", "naver_main_news": "네이버 금융 메인뉴스",
    "naver_main_desc": "네이버 금융 메인뉴스 요약", "fin_news": "네이버 금융뉴스",
    "blind_body": "블라인드 본문", "blind_comment": "블라인드 댓글",
}


def main():
    master = []
    per_file = Counter()
    seq = 0

    for fname in PROVENANCE:
        p = DATA / fname
        if not p.exists():
            continue
        script, channel = PROVENANCE[fname]
        with open(p, encoding="utf-8-sig") as f:
            for line_no, r in enumerate(csv.DictReader(f), start=2):
                text = (r.get("text") or "").strip()
                if not text:
                    continue
                seq += 1
                src = r.get("source", "")
                master.append({
                    "id": f"DM-{seq:06d}",
                    "source_file": fname,
                    "source_line": line_no,
                    "crawler": script,
                    "channel": channel,
                    "source_type": src,
                    "source_label": SOURCE_LABEL.get(src, src),
                    "stock_or_topic": r.get("stock", ""),
                    "date": r.get("date", ""),
                    "likes": r.get("likes", ""),
                    "nid": r.get("nid", ""),
                    "emotion_tags": "|".join(emotion_tag(text)),
                    "char_len": len(text),
                    "text_sha1": hashlib.sha1(text.encode("utf-8")).hexdigest()[:12],
                    "text": text.replace("\n", " ").replace("\r", " "),
                })
                per_file[fname] += 1

    out = DATA / "master_dataset.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(master[0].keys()))
        w.writeheader()
        w.writerows(master)

    # 매니페스트
    # 주의: 분석 모집단은 '커뮤니티'만. 뉴스는 기자 문체라 감정 렉시콘이 부정확하게 걸려 제외한다.
    NEWS_SRC = {"gnews", "news", "news_desc", "naver_main_news", "naver_main_desc", "fin_news"}
    comm = [r for r in master if r["source_type"] not in NEWS_SRC]
    news = [r for r in master if r["source_type"] in NEWS_SRC]
    comm_tagged = sum(1 for r in comm if r["emotion_tags"])
    news_tagged = sum(1 for r in news if r["emotion_tags"])

    by_src = Counter(r["source_label"] for r in master)
    by_emo = Counter(t for r in comm for t in r["emotion_tags"].split("|") if t)
    tagged = comm_tagged + news_tagged

    with open(OUT / "dataset_manifest.md", "w", encoding="utf-8") as f:
        f.write("# 수집 데이터 매니페스트\n\n")
        f.write(f"통합 파일: `data/master_dataset.csv` — **{len(master):,}행**\n\n")
        f.write("각 행은 고유 ID(`DM-000001` 형식)를 가지며, "
                "`source_file` + `source_line`으로 원본 CSV의 정확한 위치를 역추적할 수 있다. "
                "`text_sha1`은 본문 해시로 내용 변조 여부를 확인하는 데 쓴다.\n\n")

        f.write("## 크롤러별 수집량\n\n| 원본 파일 | 크롤러 | 채널 | 행수 |\n|---|---|---|---|\n")
        for fname, n in per_file.most_common():
            script, channel = PROVENANCE[fname]
            f.write(f"| `{fname}` | [{script}]({script}) | {channel} | {n:,} |\n")
        f.write(f"| **합계** | | | **{len(master):,}** |\n\n")

        f.write("## 소스 타입별 분포\n\n| 유형 | 행수 |\n|---|---|\n")
        for k, v in by_src.most_common():
            f.write(f"| {k} | {v:,} |\n")

        f.write("\n## 감정 태깅 — 수치 층위 주의\n\n")
        f.write("문서마다 다른 숫자가 나오는 것을 막기 위해 층위를 분리해 기록한다.\n\n")
        f.write("| 층위 | 값 | 설명 |\n|---|---|---|\n")
        f.write(f"| 전체 수집 | {len(master):,}행 | master_dataset.csv 전체 |\n")
        f.write(f"| **분석 모집단(커뮤니티)** | **{len(comm):,}행** | "
                "뉴스 제외 — 기자 문체라 감정 렉시콘이 부정확하게 걸림 |\n")
        f.write(f"| **감정 1개 이상 태깅** | **{comm_tagged:,}행 "
                f"({comm_tagged/len(comm)*100:.1f}%)** | 커뮤니티 모집단 대비 |\n")
        f.write(f"| **태그 발생 횟수** | **{sum(by_emo.values()):,}회** | "
                "한 행이 복수 감정에 걸릴 수 있어 행수보다 큼 |\n")
        f.write(f"| (참고) 뉴스 태깅 | {news_tagged:,}행 | "
                "**분석에 사용하지 않음.** 통합 파일에는 태그가 남아 있으니 필터할 것 |\n\n")
        f.write("> 보고서·PRD에 인용할 공식 수치는 **커뮤니티 "
                f"{len(comm):,}행 중 {comm_tagged:,}행({comm_tagged/len(comm)*100:.1f}%), "
                f"태그 발생 {sum(by_emo.values()):,}회**다.\n\n")
        f.write("### 감정별 발생 횟수 (커뮤니티 기준)\n\n| 감정 | 발생 횟수 |\n|---|---|\n")
        for k, v in by_emo.most_common():
            f.write(f"| {k} | {v:,} |\n")

        f.write("\n## 검증\n\n")
        f.write("문서에 인용된 모든 원문은 [verify_quotes.py](verify_quotes.py)로 대조하며, "
                "결과는 `output/quote_verification.csv`에 파일명·행번호·전문과 함께 기록된다.\n")

    print(f"통합 완료: {len(master):,}행 → {out}")
    for fname, n in per_file.most_common():
        print(f"  {fname:24} {n:>6,}행")
    print(f"\n[분석 모집단] 커뮤니티 {len(comm):,}행 중 태깅 {comm_tagged:,}행 "
          f"({comm_tagged/len(comm)*100:.1f}%), 태그 발생 {sum(by_emo.values()):,}회")
    print(f"[참고] 뉴스 {len(news):,}행 중 태깅 {news_tagged:,}행 — 분석 제외")
    print(f"매니페스트 → {OUT / 'dataset_manifest.md'}")


if __name__ == "__main__":
    main()
