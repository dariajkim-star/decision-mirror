# -*- coding: utf-8 -*-
"""네이버 종목토론방 + 금융 뉴스 크롤러 (No_FOMO 리서치용)

수집 대상
1. 종목토론방(finance.naver.com/item/board.naver) 게시글 제목 — 개인투자자 정서의 원천
2. 네이버 뉴스 검색 — FOMO/뇌동매매/벼락거지 등 키워드별 최신 기사 제목·요약
"""
import csv
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Referer": "https://finance.naver.com/",
}

# 개인투자자 관심이 몰리는 대표 종목 (대형주 + 변동성 큰 종목 혼합)
STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "373220": "LG에너지솔루션",
    "005380": "현대차",
    "035720": "카카오",
    "035420": "NAVER",
    "247540": "에코프로비엠",
    "086520": "에코프로",
    "196170": "알테오젠",
    "042700": "한미반도체",
}

NEWS_KEYWORDS = [
    "주식 FOMO",
    "뇌동매매",
    "벼락거지",
    "주식 물렸다",
    "빚투 영끌",
    "개미 투자자 손실",
    "주식 중독",
    "패닉셀",
]


def crawl_board(code: str, name: str, pages: int = 5) -> list[dict]:
    """종목토론방 게시글 제목 수집."""
    rows = []
    for page in range(1, pages + 1):
        url = f"https://finance.naver.com/item/board.naver?code={code}&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            res.encoding = res.apparent_encoding  # 네이버가 utf-8/euc-kr 혼용
            soup = BeautifulSoup(res.text, "html.parser")
            for tr in soup.select("table.type2 tr"):
                a = tr.select_one("td.title a")
                if not a:
                    continue
                title = a.get("title") or a.get_text(strip=True)
                date_td = tr.select_one("td span.tah")
                date = date_td.get_text(strip=True) if date_td else ""
                if title:
                    rows.append({"source": "board", "stock": name, "date": date, "text": title})
        except Exception as e:
            print(f"  [warn] {name} p{page}: {e}")
        time.sleep(0.5)
    print(f"[board] {name}: {len(rows)}건")
    return rows


def crawl_news(keyword: str, pages: int = 3) -> list[dict]:
    """네이버 뉴스 검색 결과(제목+요약) 수집."""
    rows = []
    for page in range(pages):
        start = page * 10 + 1
        url = (
            "https://search.naver.com/search.naver?where=news&query="
            + requests.utils.quote(keyword)
            + f"&sort=1&start={start}"
        )
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            soup = BeautifulSoup(res.text, "html.parser")
            # 뉴스 카드 구조가 자주 바뀌므로 여러 셀렉터 시도
            items = soup.select("a.news_tit")
            descs = soup.select("div.news_dsc, a.api_txt_lines.dsc_txt_wrap")
            if not items:  # 신형 레이아웃 fallback
                items = [a for a in soup.select("a[href*='news.naver.com'], a[href*='n.news.naver.com']") if len(a.get_text(strip=True)) > 15]
            for a in items:
                title = a.get("title") or a.get_text(strip=True)
                if title:
                    rows.append({"source": "news", "stock": keyword, "date": "", "text": title})
            for d in descs:
                txt = d.get_text(strip=True)
                if txt:
                    rows.append({"source": "news_desc", "stock": keyword, "date": "", "text": txt})
        except Exception as e:
            print(f"  [warn] news '{keyword}' p{page}: {e}")
        time.sleep(0.7)
    print(f"[news] {keyword}: {len(rows)}건")
    return rows


def main():
    all_rows: list[dict] = []
    for code, name in STOCKS.items():
        all_rows.extend(crawl_board(code, name))
    for kw in NEWS_KEYWORDS:
        all_rows.extend(crawl_news(kw))

    # 중복 제거
    seen = set()
    uniq = []
    for r in all_rows:
        key = r["text"]
        if key not in seen:
            seen.add(key)
            uniq.append(r)

    out = DATA_DIR / "raw_texts.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "stock", "date", "text"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n총 {len(uniq)}건 저장 → {out}")


if __name__ == "__main__":
    main()
