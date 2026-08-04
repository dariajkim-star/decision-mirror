# 크롤링 채널 리서치 (2026-08-04)

한국 개인 주식투자자 감정 데이터를 수집할 수 있는 채널 조사 결과. (웹 리서치 에이전트 수행)

## 우선순위 Top 5

| 순위 | 채널 | 투자자층 | 크롤링 난이도 | 접근 방법 |
|---|---|---|---|---|
| 1 | **네이버 종목토론실** | 전 연령, 종목 보유자 — 감정 밀도 최고 | 하 (구현 완료 ✅) | `board.naver?code={코드}&page={n}` 목록 → `front-api/discussion/detail?id={nid}` 본문 → CBOX(`ticket=finance, objectId={nid}`) 댓글. [crawler_detail.py](crawler_detail.py) |
| 2 | **디시 주식갤러리군** | 2030 남성, 고위험·극단 표현 — FOMO/"한강" 언어의 원산지 | 중 | 목록 `gall.dcinside.com/mgallery/board/lists/?id={갤}`, 갤 5개: kjusick(국내), tenbagger(해외), stockus(미국), neostock, krstock. 차단 시 m.dcinside.com 또는 dcinside-python3-api |
| 3 | **유튜브 주식방송 댓글** | 전 연령. 폭락일 라이브 댓글에 공포 집중 | 하 (공식 API) | YouTube Data API v3 `commentThreads.list`. 삼프로TV, 슈카월드, 김작가TV. 일 10,000 쿼터 |
| 4 | **증권플러스 종목톡** | 2030 앱 투자자 | 중 (SPA) | `stockplus.com/m/stocks/KOREA-A{코드}/debates` — 내부 XHR JSON 엔드포인트 확인 필요 |
| 5 | **에펨코리아 주식게시판** | 2030 남성, 수익/손실 인증글 풍부 | 상 (Cloudflare) | `fmkorea.com/stock`, cloudscraper/Playwright 필요, 요청 간격 길게 |

## 기타 후보

- **뽐뿌 주식포럼** (`ppomppu.co.kr/zboard/zboard.php?id=stock`): 3040 실속형, 크롤링 쉬움, 감정 강도 중간
- **클리앙 주식모임**: 3050 IT직군, 차분함 → 감정 데이터로는 약함
- **텔레그램 주식방**: Telethon으로 공개 채널 수집 쉬우나 리딩방 광고 노이즈 큼. 보조용
- **팍스넷·씽크풀**: 4060 고령층, 정적 HTML로 쉬우나 트래픽 급감. 보조용
- **레딧**: 한국어 데이터 극소. 비추천

## 접근 장벽이 큰 채널 (주의)

- **블라인드**: 직장인 실명인증 — 연봉 맥락의 절실한 글이 많아 데이터 가치는 높으나, 앱 로그인 필수 + Cloudflare + 약관상 수집 금지. [crawler_blind.py](crawler_blind.py)는 본인 로그인 쿠키 기반 소규모 연구용으로만 작성해둠
- **토스증권 커뮤니티**: 앱 전용, 공개 API 없음, 약관 금지. 2030 신규투자자 데이터로는 최상급이지만 수집 불가
- **네이버 카페** (월급쟁이 부자들 등): 로그인+가입 필요, 봇 차단 강함

## 공통 수칙

- robots.txt·약관 확인, 요청 간격 1~3초
- 닉네임 등 개인정보는 익명화 후 저장
- 수집물은 연구(모델 학습·문제정의) 용도로 한정
