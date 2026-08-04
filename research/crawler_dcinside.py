# -*- coding: utf-8 -*-
"""디시인사이드 주식갤러리군 크롤러

대상 갤러리 (마이너갤 포함):
- kjusick   국내주식 마이너갤
- tenbagger 해외주식 마이너갤
- stockus   미국주식 마이너갤
- neostock  주식 갤러리
- krstock   한국주식 갤러리

구조:
- 목록: gall.dcinside.com/mgallery/board/lists/?id={갤}&page={n} (일반갤은 /board/lists/)
- 본문: 목록의 링크 → /board/view/?id=...&no=...
- 차단(429/403) 시 모바일 엔드포인트(m.dcinside.com)로 폴백

출력: data/raw_dcinside.csv (source: dc_title | dc_body | dc_comment)

주의: 요청 간격을 지키고(기본 1초), 대량 수집 금지. 욕설·은어가 많아
분석 전 전처리(비속어 필터 또는 그대로 감정 강도 신호로 활용) 필요.
"""
import csv
import json
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
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://gall.dcinside.com/",
}

# 갤러리 id → (이름, 마이너갤 여부)
GALLERIES = {
    "kjusick": ("국내주식갤", True),
    "tenbagger": ("해외주식갤", True),
    "stockus": ("미국주식갤", True),
    "neostock": ("주식갤", True),
    "krstock": ("한국주식갤", True),
}

LIST_PAGES = 3      # 갤러리당 목록 페이지 수 (페이지당 글 50개)
BODY_LIMIT = 60     # 갤러리당 본문까지 수집할 글 수 (제목은 전부 수집)
SLEEP = 1.0


def gall_base(minor: bool) -> str:
    return "https://gall.dcinside.com/mgallery/board" if minor else "https://gall.dcinside.com/board"


def crawl_list(gid: str, name: str, minor: bool) -> list[dict]:
    """목록 페이지: 제목 + 글 번호(no) 수집."""
    posts: list[dict] = []
    for page in range(1, LIST_PAGES + 1):
        url = f"{gall_base(minor)}/lists/?id={gid}&page={page}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code != 200:
                print(f"  [warn] {gid} 목록 p{page}: HTTP {res.status_code}")
                continue
            soup = BeautifulSoup(res.text, "html.parser")
            for tr in soup.select("tr.ub-content"):
                a = tr.select_one("td.gall_tit a:not(.reply_numbox)")
                no = tr.get("data-no")
                subj = tr.select_one("td.gall_subject")
                subject = subj.get_text(strip=True) if subj else ""
                if a and no and subject not in ("공지", "설문", "AD", "광고"):
                    title = a.get_text(" ", strip=True)
                    # 말머리/댓글수 제거
                    title = re.sub(r"\[\d+\]$", "", title).strip()
                    if title:
                        posts.append({"no": no, "title": title})
        except Exception as e:
            print(f"  [warn] {gid} 목록 p{page}: {e}")
        time.sleep(SLEEP)
    print(f"[{name}] 목록 {len(posts)}건")
    return posts


def crawl_body(gid: str, no: str, minor: bool) -> tuple[str, list[str]]:
    """본문 + 댓글. 실패 시 빈 값."""
    url = f"{gall_base(minor)}/view/?id={gid}&no={no}"
    body, comments = "", []
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code != 200:
            return body, comments
        soup = BeautifulSoup(res.text, "html.parser")
        w = soup.select_one("div.write_div")
        if w:
            body = w.get_text(" ", strip=True)
        # 댓글: 페이지 내 렌더링분 (JS 추가 로드분은 comment API 필요)
        for c in soup.select("p.usertxt.ub-word"):
            txt = c.get_text(" ", strip=True)
            if txt and txt != "-":
                comments.append(txt)
        # 댓글이 비어 있으면 comment_box API 시도
        if not comments:
            comments = fetch_comments_api(gid, no, url)
    except Exception as e:
        print(f"  [warn] {gid}/{no}: {e}")
    return body, comments


def fetch_comments_api(gid: str, no: str, referer: str) -> list[str]:
    """디시 댓글 AJAX API (board/comment). e_s_n_o 토큰이 필요해 실패할 수 있음."""
    try:
        res = requests.post(
            "https://gall.dcinside.com/board/comment/",
            headers={**HEADERS, "Referer": referer, "X-Requested-With": "XMLHttpRequest"},
            data={"id": gid, "no": no, "cmt_id": gid, "cmt_no": no,
                  "focus_cno": "", "focus_pno": "", "es_no": "", "comment_page": "1", "sort": "D"},
            timeout=10,
        )
        d = res.json()
        return [re.sub(r"<[^>]+>", " ", c.get("memo", "")).strip()
                for c in d.get("comments") or [] if c.get("memo")]
    except Exception:
        return []


def main():
    rows: list[dict] = []
    for gid, (name, minor) in GALLERIES.items():
        posts = crawl_list(gid, name, minor)
        for p in posts:
            rows.append({"source": "dc_title", "stock": name, "nid": p["no"],
                         "date": "", "likes": "", "text": p["title"]})
        n_body = n_cmt = 0
        for p in posts[:BODY_LIMIT]:
            body, comments = crawl_body(gid, p["no"], minor)
            if body:
                rows.append({"source": "dc_body", "stock": name, "nid": p["no"],
                             "date": "", "likes": "", "text": body})
                n_body += 1
            for c in comments:
                rows.append({"source": "dc_comment", "stock": name, "nid": p["no"],
                             "date": "", "likes": "", "text": c})
                n_cmt += 1
            time.sleep(SLEEP)
        print(f"[{name}] 본문 {n_body}건, 댓글 {n_cmt}건")

    seen, uniq = set(), []
    for r in rows:
        key = (r["source"], r["text"])
        if key not in seen and len(r["text"]) > 1:
            seen.add(key)
            uniq.append(r)

    out = DATA_DIR / "raw_dcinside.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "stock", "nid", "date", "likes", "text"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n총 {len(uniq)}건 저장 → {out}")


if __name__ == "__main__":
    main()
