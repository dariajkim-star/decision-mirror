# -*- coding: utf-8 -*-
"""네이버 종목토론방 본문 + 댓글 크롤러

구조 (2026-08 기준 리버스엔지니어링):
- 글 목록: finance.naver.com/item/board.naver?code={종목}&page={n}  → nid 추출
- 본문:   m.stock.naver.com/front-api/discussion/detail?id={nid}   → JSON (contentHtml)
- 댓글:   apis.naver.com CBOX API, ticket=finance, objectId={nid}

출력: data/raw_details.csv (source: board_body | board_comment)
"""
import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
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

PAGES_PER_STOCK = 5      # 목록 페이지 수 (페이지당 글 20개)
COMMENT_PAGE_SIZE = 100  # 댓글 페이지 크기
SLEEP = 0.3              # 요청 간격 (예의)


def list_nids(code: str, pages: int) -> list[str]:
    """목록에서 게시글 nid 수집."""
    nids: list[str] = []
    for page in range(1, pages + 1):
        url = f"https://finance.naver.com/item/board.naver?code={code}&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            res.encoding = res.apparent_encoding
            soup = BeautifulSoup(res.text, "html.parser")
            for a in soup.select("td.title a"):
                m = re.search(r"nid=(\d+)", a.get("href", ""))
                if m and m.group(1) not in nids:
                    nids.append(m.group(1))
        except Exception as e:
            print(f"  [warn] list {code} p{page}: {e}")
        time.sleep(SLEEP)
    return nids


def fetch_body(nid: str) -> dict | None:
    """본문 API. contentHtml에서 텍스트 추출."""
    url = f"https://m.stock.naver.com/front-api/discussion/detail?id={nid}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        d = res.json().get("result", {})
        html = d.get("contentHtml") or ""
        body = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
        return {
            "nid": nid,
            "title": d.get("title", ""),
            "body": body,
            "date": d.get("writtenAt", ""),
            "views": d.get("viewCount", 0),
            "likes": d.get("recommendCount", 0),
        }
    except Exception as e:
        print(f"  [warn] body {nid}: {e}")
        return None


def fetch_comments(nid: str) -> list[dict]:
    """CBOX 댓글 API (페이지네이션)."""
    out: list[dict] = []
    page = 1
    while True:
        url = (
            "https://apis.naver.com/commentBox/cbox/web_naver_list_jsonp.json"
            f"?ticket=finance&templateId=default&pool=cbox12&lang=ko&country=KR"
            f"&objectId={nid}&pageSize={COMMENT_PAGE_SIZE}&listType=OBJECT&sort=NEW&page={page}"
        )
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            d = json.loads(re.sub(r"^_callback\(|\);?$", "", res.text.strip()))
            result = d.get("result", {})
            lst = result.get("commentList") or []
            for c in lst:
                txt = (c.get("contents") or "").strip()
                if txt:
                    out.append({"text": txt, "date": c.get("regTime", ""),
                                "likes": c.get("sympathyCount", 0)})
            total = (result.get("count") or {}).get("total", 0)
            if len(out) >= total or not lst:
                break
            page += 1
        except Exception as e:
            print(f"  [warn] comments {nid}: {e}")
            break
    return out


def fetch_one(args: tuple[str, str]) -> list[dict]:
    name, nid = args
    out: list[dict] = []
    b = fetch_body(nid)
    if b:
        text = (b["title"] + " " + b["body"]).strip()
        out.append({"source": "board_body", "stock": name, "nid": nid,
                    "date": b["date"], "likes": b["likes"], "text": text})
    for c in fetch_comments(nid):
        out.append({"source": "board_comment", "stock": name, "nid": nid,
                    "date": c["date"], "likes": c["likes"], "text": c["text"]})
    time.sleep(SLEEP)
    return out


def main():
    rows: list[dict] = []
    jobs: list[tuple[str, str]] = []
    for code, name in STOCKS.items():
        nids = list_nids(code, PAGES_PER_STOCK)
        jobs.extend((name, nid) for nid in nids)
        print(f"[{name}] 글 {len(nids)}건 대기열 추가", flush=True)

    with ThreadPoolExecutor(max_workers=4) as ex:
        for i, result in enumerate(ex.map(fetch_one, jobs), 1):
            rows.extend(result)
            if i % 100 == 0:
                print(f"  진행 {i}/{len(jobs)} (누적 {len(rows)}건)", flush=True)

    # 중복 제거
    seen, uniq = set(), []
    for r in rows:
        key = (r["source"], r["text"])
        if key not in seen:
            seen.add(key)
            uniq.append(r)

    out = DATA_DIR / "raw_details.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "stock", "nid", "date", "likes", "text"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n총 {len(uniq)}건 저장 → {out}")


if __name__ == "__main__":
    main()
