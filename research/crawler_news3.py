# -*- coding: utf-8 -*-
"""뉴스 보완 수집: ① 네이버 금융 메인뉴스 ② 구글뉴스 RSS 키워드 검색"""
import csv
import time
from pathlib import Path
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

KEYWORDS = ["주식 FOMO", "뇌동매매", "벼락거지", "빚투", "영끌 투자", "패닉셀",
            "추격매수", "개미 투자자 손실", "주식 중독", "투자 심리 불안", "코스피 개인 순매수"]


def naver_main_news(pages: int = 3) -> list[dict]:
    rows = []
    for page in range(1, pages + 1):
        url = f"https://finance.naver.com/news/mainnews.naver?page={page}"
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = "euc-kr"
        soup = BeautifulSoup(res.text, "html.parser")
        for a in soup.select("dd.articleSubject a, dt.articleSubject a"):
            t = a.get_text(strip=True)
            if t:
                rows.append({"source": "naver_main_news", "stock": "금융메인", "date": "", "text": t})
        for s in soup.select("dd.articleSummary"):
            txt = s.get_text(" ", strip=True).split("  ")[0].strip()
            if len(txt) > 20:
                rows.append({"source": "naver_main_desc", "stock": "금융메인", "date": "", "text": txt})
        time.sleep(0.4)
    print(f"[naver_main] {len(rows)}건")
    return rows


def google_news_rss(keyword: str, limit: int = 30) -> list[dict]:
    url = ("https://news.google.com/rss/search?q=" + requests.utils.quote(keyword)
           + "&hl=ko&gl=KR&ceid=KR:ko")
    rows = []
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        root = ElementTree.fromstring(res.content)
        for item in root.iter("item"):
            title = item.findtext("title") or ""
            date = item.findtext("pubDate") or ""
            if title:
                rows.append({"source": "gnews", "stock": keyword, "date": date, "text": title})
            if len(rows) >= limit:
                break
    except Exception as e:
        print(f"  [warn] {keyword}: {e}")
    print(f"[gnews] {keyword}: {len(rows)}건")
    return rows


def main():
    all_rows = naver_main_news()
    for kw in KEYWORDS:
        all_rows.extend(google_news_rss(kw))
        time.sleep(0.5)
    seen, uniq = set(), []
    for r in all_rows:
        if r["text"] not in seen:
            seen.add(r["text"])
            uniq.append(r)
    out = DATA_DIR / "raw_news.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "stock", "date", "text"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n총 {len(uniq)}건 저장 → {out}")


if __name__ == "__main__":
    main()
