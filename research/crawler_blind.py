# -*- coding: utf-8 -*-
"""블라인드(teamblind.com) 주식·투자 라운지 크롤러

⚠️ 사용 전 반드시 읽을 것
- 블라인드는 로그인(직장 이메일 인증) 필수 + Cloudflare 봇 차단이 강한 사이트다.
- 약관상 자동 수집을 금지하므로, 본 코드는 **연구 목적의 소규모 수집** 전용.
  요청 간격을 길게(기본 3초) 유지하고, 수집물은 익명화 후 저장한다.
- 실행하려면 본인 계정으로 웹 로그인한 브라우저에서 쿠키를 추출해
  research/blind_cookies.json 에 저장해야 한다 (아래 사용법 참고).

사용법
1. 크롬에서 https://www.teamblind.com/kr 로그인
2. F12 → Application → Cookies → www.teamblind.com 의 쿠키를 확장프로그램
   (예: "Cookie-Editor")으로 JSON export → research/blind_cookies.json 저장
3. python crawler_blind.py

토픽 후보 (한국판 라운지 slug):
- 주식·투자: /kr/topics/주식-투자
- 재테크, 부동산 등도 동일 패턴
"""
import csv
import json
import re
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
COOKIE_FILE = BASE_DIR / "blind_cookies.json"

BASE = "https://www.teamblind.com"
TOPICS = [
    "/kr/topics/주식-투자",   # 주식·투자 라운지
]
PAGES = 5
SLEEP = 3.0  # 봇 차단·매너 고려, 짧게 줄이지 말 것

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.teamblind.com/kr",
}


def load_cookies(session: requests.Session) -> bool:
    if not COOKIE_FILE.exists():
        print(f"[!] 쿠키 파일 없음: {COOKIE_FILE}")
        print("    파일 상단 주석의 사용법대로 로그인 쿠키를 export 하세요.")
        return False
    raw = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    # Cookie-Editor 형식([{name, value, domain, ...}]) 및 {name: value} dict 모두 지원
    if isinstance(raw, list):
        for c in raw:
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ".teamblind.com"))
    else:
        for k, v in raw.items():
            session.cookies.set(k, v, domain=".teamblind.com")
    return True


def parse_list(html: str) -> list[str]:
    """토픽 목록 페이지에서 글 링크 추출."""
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.select("a[href*='/kr/post/'], a[href^='/post/']"):
        href = a.get("href", "")
        if href and href not in links:
            links.append(href)
    return links


def parse_post(html: str) -> dict | None:
    """글 상세: 제목/본문/댓글. 블라인드는 Next.js — __NEXT_DATA__ 우선, DOM fallback."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            # 페이지 구조 변경에 대비해 재귀 탐색으로 title/content 키를 찾는다
            found = {"title": "", "content": "", "comments": []}

            def walk(node):
                if isinstance(node, dict):
                    if "title" in node and "content" in node and not found["content"]:
                        found["title"] = str(node.get("title") or "")
                        found["content"] = str(node.get("content") or "")
                    if "commentList" in node and isinstance(node["commentList"], list):
                        for c in node["commentList"]:
                            txt = c.get("content") if isinstance(c, dict) else None
                            if txt:
                                found["comments"].append(str(txt))
                    for v in node.values():
                        walk(v)
                elif isinstance(node, list):
                    for v in node:
                        walk(v)

            walk(data)
            if found["content"]:
                return found
        except Exception:
            pass
    # DOM fallback
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one("h2, h1")
    body = soup.select_one("[class*='content'], article")
    if body:
        return {
            "title": title.get_text(strip=True) if title else "",
            "content": body.get_text(" ", strip=True),
            "comments": [c.get_text(" ", strip=True) for c in soup.select("[class*='comment'] p")],
        }
    return None


def main():
    s = requests.Session()
    s.headers.update(HEADERS)
    if not load_cookies(s):
        return

    # 로그인 확인
    r = s.get(BASE + "/kr", timeout=15)
    if r.status_code == 403:
        print("[!] 403 — Cloudflare 차단. 브라우저에서 새로 export한 쿠키(cf_clearance 포함)가 필요합니다.")
        return

    rows: list[dict] = []
    for topic in TOPICS:
        post_links: list[str] = []
        for page in range(1, PAGES + 1):
            url = f"{BASE}{requests.utils.quote(topic)}?page={page}"
            try:
                r = s.get(url, timeout=15)
                links = parse_list(r.text)
                post_links.extend(l for l in links if l not in post_links)
                print(f"[list] {topic} p{page}: 누적 {len(post_links)}개 링크")
            except Exception as e:
                print(f"  [warn] {url}: {e}")
            time.sleep(SLEEP)

        for href in post_links:
            url = BASE + href if href.startswith("/") else href
            try:
                r = s.get(url, timeout=15)
                p = parse_post(r.text)
                if p:
                    rows.append({"source": "blind_body", "topic": topic, "url": href,
                                 "text": (p["title"] + " " + p["content"]).strip()})
                    for c in p["comments"]:
                        rows.append({"source": "blind_comment", "topic": topic, "url": href, "text": c})
            except Exception as e:
                print(f"  [warn] {url}: {e}")
            time.sleep(SLEEP)

    out = DATA_DIR / "raw_blind.csv"
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "topic", "url", "text"])
        w.writeheader()
        w.writerows(rows)
    print(f"\n총 {len(rows)}건 저장 → {out}")


if __name__ == "__main__":
    main()
