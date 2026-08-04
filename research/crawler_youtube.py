# -*- coding: utf-8 -*-
"""유튜브 주식방송 댓글 크롤러 — 삼프로TV, 슈카월드

API 키 없이 동작:
- 채널 핸들(@3protv 등) → 채널 페이지에서 channelId 추출
- 최신 영상 목록: 유튜브 공식 RSS (feeds/videos.xml?channel_id=...) — 최근 15개
- 댓글: youtube-comment-downloader (비공식이지만 안정적, pip install youtube-comment-downloader)

주식 관련 영상만 필터링(제목 키워드)한 뒤 영상당 댓글 상한까지 수집.
출력: data/raw_youtube.csv (source: yt_comment)

참고: 공식 YouTube Data API v3(commentThreads.list)로 바꾸면 더 안정적.
      그 경우 YOUTUBE_API_KEY 환경변수 + google-api-python-client 사용.
"""
import csv
import re
import time
from pathlib import Path
from xml.etree import ElementTree

import requests
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_POPULAR

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "ko"}

CHANNELS = {
    "@3protv": "삼프로TV",
    "@syukaworld": "슈카월드",
}

# 주식/시장 관련 영상만 (제목 필터). 비우면 전체 수집
TITLE_KEYWORDS = ["주식", "증시", "코스피", "코스닥", "나스닥", "반도체", "폭락", "급등",
                  "금리", "환율", "투자", "시장", "매수", "매도", "버블", "삼성전자", "미국"]

VIDEOS_PER_CHANNEL = 10   # 채널당 영상 수 (필터 통과분 기준)
COMMENTS_PER_VIDEO = 200  # 영상당 댓글 상한


def resolve_channel_id(handle: str) -> str | None:
    """@핸들 → channelId (채널 페이지 HTML에서 추출)."""
    try:
        r = requests.get(f"https://www.youtube.com/{handle}", headers=HEADERS, timeout=15)
        ids = re.findall(r'"(?:channelId|browseId|externalId)":"(UC[\w-]{22})"', r.text)
        return list(dict.fromkeys(ids)) or None
    except Exception as e:
        print(f"  [warn] {handle} 채널ID 실패: {e}")
        return None


def recent_videos(channel_id: str) -> list[dict]:
    """공식 RSS로 최신 영상 목록 (최대 15개)."""
    url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    r = requests.get(url, headers=HEADERS, timeout=15)
    if r.status_code != 200 or not r.content.lstrip().startswith(b"<?xml"):
        print(f"  [warn] RSS 실패 (HTTP {r.status_code})")
        return []
    root = ElementTree.fromstring(r.content)
    ns = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015"}
    out = []
    for e in root.findall("a:entry", ns):
        out.append({
            "videoId": e.findtext("yt:videoId", "", ns),
            "title": e.findtext("a:title", "", ns),
            "published": e.findtext("a:published", "", ns),
        })
    return out


def videos_from_page(handle: str) -> list[dict]:
    """RSS 불가 채널 폴백: /videos 페이지의 ytInitialData에서 videoId+제목 추출."""
    try:
        r = requests.get(f"https://www.youtube.com/{handle}/videos", headers=HEADERS, timeout=15)
        vids = list(dict.fromkeys(re.findall(r'"videoId":"([\w-]{11})"', r.text)))[:30]
        out = []
        for vid in vids:
            # 제목은 oEmbed로 확인 (안정적 공개 API)
            try:
                o = requests.get(
                    f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={vid}&format=json",
                    headers=HEADERS, timeout=10)
                title = o.json().get("title", "") if o.status_code == 200 else ""
            except Exception:
                title = ""
            out.append({"videoId": vid, "title": title, "published": ""})
            time.sleep(0.2)
        return out
    except Exception as e:
        print(f"  [warn] videos page {handle}: {e}")
        return []


def fetch_comments(video_id: str, limit: int) -> list[dict]:
    dl = YoutubeCommentDownloader()
    out = []
    try:
        for c in dl.get_comments_from_url(
                f"https://www.youtube.com/watch?v={video_id}", sort_by=SORT_BY_POPULAR):
            txt = (c.get("text") or "").strip()
            if txt:
                out.append({"text": txt, "likes": c.get("votes", 0), "date": c.get("time", "")})
            if len(out) >= limit:
                break
    except Exception as e:
        print(f"  [warn] comments {video_id}: {e}")
    return out


def main():
    rows: list[dict] = []
    for handle, name in CHANNELS.items():
        cids = resolve_channel_id(handle)
        if not cids:
            print(f"[{name}] 채널ID 추출 실패 — 건너뜀")
            continue
        videos = []
        for cid in cids[:5]:  # 페이지에 섞인 타 채널 ID 대비, RSS가 뜨는 첫 ID 사용
            videos = recent_videos(cid)
            if videos:
                break
        if not videos:  # RSS 비활성 채널 폴백
            videos = videos_from_page(handle)
        if TITLE_KEYWORDS:
            videos = [v for v in videos if any(k in v["title"] for k in TITLE_KEYWORDS)] or videos
        videos = videos[:VIDEOS_PER_CHANNEL]
        print(f"[{name}] 대상 영상 {len(videos)}개")
        n = 0
        for v in videos:
            comments = fetch_comments(v["videoId"], COMMENTS_PER_VIDEO)
            for c in comments:
                rows.append({"source": "yt_comment", "stock": name, "nid": v["videoId"],
                             "date": c["date"], "likes": c["likes"],
                             "text": c["text"]})
            n += len(comments)
            print(f"  - {v['title'][:40]}… : 댓글 {len(comments)}건")
            time.sleep(1.0)
        print(f"[{name}] 댓글 합계 {n}건")

    seen, uniq = set(), []
    for r in rows:
        if r["text"] not in seen:
            seen.add(r["text"])
            uniq.append(r)

    out = DATA_DIR / "raw_youtube.csv"
    if not uniq:
        print("\n수집 0건 — 기존 파일을 덮어쓰지 않고 종료")
        return
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["source", "stock", "nid", "date", "likes", "text"])
        w.writeheader()
        w.writerows(uniq)
    print(f"\n총 {len(uniq)}건 저장 → {out}")


if __name__ == "__main__":
    main()
