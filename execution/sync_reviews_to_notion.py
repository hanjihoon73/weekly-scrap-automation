"""
QB 후기 노션 동기화 스크립트 (블로그 전용)
=================================================
매주 네이버 블로그 검색 결과를 수집해 노션 'QUEBON_Reviews' DB에 신규 후기를 등록하고,
기존 후기의 공개 상태를 재점검합니다.

처리 흐름
  1) 검색 수집   : scrape_naver_email.scrape_naver_blog() 재사용 (제목 필터만 넓힘)
  2) 중복 확인   : 노션 DB '링크' 기준으로 이미 등록된 글은 건너뜀
  3) 상세 수집   : 모바일 블로그 페이지에서 제목·작성일·닉네임·본문 추출
  4) 커넥터즈 판정: 본문 규칙 기반 (문구 / '커넥터즈' 언급 / sh.quebon.tv 간편링크)
  5) 자동 태깅   : Claude API로 키워드·자녀 학년 추출 → 분류는 키워드에서 자동 계산
  6) 노션 등록   : 신규 행 생성
  7) 상태 재점검 : 공개 상태인 기존 블로그 행을 다시 열어 비공개·삭제 전환 여부 갱신

실행 예
  python execution/sync_reviews_to_notion.py              # 실제 반영
  python execution/sync_reviews_to_notion.py --dry-run    # 노션에 쓰지 않고 결과만 출력
  python execution/sync_reviews_to_notion.py --skip-recheck
  python execution/sync_reviews_to_notion.py --urls "https://blog.naver.com/id/123,..."  # 검색 없이 지정 URL만 처리

필요 환경변수 (GitHub Secrets)
  NOTION_TOKEN        : 노션 내부 통합 토큰
  NOTION_DATABASE_ID  : QUEBON_Reviews 데이터베이스 ID
  ANTHROPIC_API_KEY   : Claude API 키 (없으면 태깅을 건너뛰고 해당 칸을 비워 둠)
  CLAUDE_MODEL        : (선택) 태깅 모델, 기본값 claude-haiku-5-5
"""

import os
import re
import sys
import json
import time
import argparse
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

# 같은 폴더의 기존 스크래퍼 함수 재사용
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# ---------------------------------------------------------------------------
# 1. 설정값
# ---------------------------------------------------------------------------
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
# Secret이 비어 있으면 Actions가 빈 문자열을 넘기므로 `or 기본값` 형태로 처리
NOTION_DATABASE_ID = os.getenv("NOTION_DATABASE_ID") or "36368543839a4c7dab3209e6b87cafb7"
NOTION_VERSION = os.getenv("NOTION_VERSION") or "2022-06-28"    # 단일 데이터소스 DB 기준 안정 버전
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY") or None
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL") or "claude-haiku-5-5"

SEARCH_QUERY = "깨봉수학"
TITLE_PATTERN = r"깨봉|QUEBON"            # 메일보다 넓은 제목 필터 ('깨봉 수학', 'QUEBON' 표기 포함)
MOBILE_UA = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
             "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
REQUEST_DELAY = 1.0                       # 블로그 요청 간 간격(초)
BODY_LIMIT = 6000                         # 태깅에 보내는 본문 최대 길이
RECHECK_MAX_RATIO = 0.2                   # 재점검 시 비공개 감지가 전체의 20% 초과면 반영 보류

# 커넥터즈 판정 규칙: 하나라도 걸리면 Yes (기존 61건 검증: 39/47 일치, 오탐 0)
CONNECTORS_RE = re.compile(r"깨봉\s*커넥터즈\s*활동|커넥터즈|sh\.quebon\.tv")

# 키워드·분류 체계 (노션 옵션 순서와 동일하게 유지)
AXES = {
    "시작 계기": ["첫수학", "수포자", "학원·선행대체", "홈스쿨링"],
    "학습 성과": ["성적향상", "단원평가", "개념이해", "연산력", "사고력"],
    "태도": ["태도변화", "자기주도"],
    "심화": ["영재원", "경시대회", "최상위·심화"],
    "구매 검토": ["타사비교", "가격·할인", "장단점"],
    "기타": ["강연회", "장기이용"],
}
KEYWORD_ORDER = [k for ks in AXES.values() for k in ks]
AXIS_ORDER = list(AXES)
GRADE_ORDER = ["5세", "6세", "7세", "초1", "초2", "초3", "초4", "초5", "초6",
               "중1", "중2", "중3", "고1", "고2", "고3", "성인"]


# ---------------------------------------------------------------------------
# 2. 유틸
# ---------------------------------------------------------------------------
def clean(text):
    """공백·보이지 않는 문자 정리"""
    text = (text or "").replace("​", "").replace("﻿", "")
    return re.sub(r"\s+", " ", text).strip()


def cut_title(title, limit=30):
    """제목 30자 이내로 자르기 (초과 시 말줄임)"""
    title = clean(title)
    return title if len(title) <= limit else title[: limit - 1] + "…"


def parse_naver_ids(url):
    """네이버 블로그 URL에서 (blogId, logNo) 추출. 실패 시 (None, None)"""
    parsed = urlparse(url)
    if "blog.naver.com" not in parsed.netloc:
        return None, None
    qs = parse_qs(parsed.query)
    if "blogId" in qs and "logNo" in qs:                       # PostView.naver?blogId=..&logNo=..
        return qs["blogId"][0], qs["logNo"][0]
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[1].isdigit():                 # /{blogId}/{logNo}
        return parts[0], parts[1]
    return None, None


def canonical_url(url):
    """노션 '링크' 저장 형식으로 통일: https://blog.naver.com/{blogId}/{logNo}"""
    blog_id, log_no = parse_naver_ids(url)
    if blog_id:
        return f"https://blog.naver.com/{blog_id}/{log_no}"
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}{p.path}".rstrip("/")


def parse_post_date(text, now=None):
    """'2026. 9. 11. 14:15' / '3시간 전' / '어제' 등을 YYYY-MM-DD로 변환. 실패 시 None"""
    now = now or datetime.now()
    text = clean(text)
    m = re.search(r"(\d{4})\.\s*(\d{1,2})\.\s*(\d{1,2})", text)
    if m:
        return f"{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d}"
    if re.search(r"방금|분\s*전|시간\s*전", text):
        return now.strftime("%Y-%m-%d")
    if "어제" in text:
        return (now - timedelta(days=1)).strftime("%Y-%m-%d")
    m = re.search(r"(\d+)\s*일\s*전", text)
    if m:
        return (now - timedelta(days=int(m[1]))).strftime("%Y-%m-%d")
    return None


def is_connector(body):
    """커넥터즈 판정 (본문 규칙 기반)"""
    return bool(CONNECTORS_RE.search(body or ""))


def order_keywords(keywords):
    """허용된 키워드만 남기고 기준 순서로 정렬"""
    return [k for k in KEYWORD_ORDER if k in set(keywords or [])]


def axes_from_keywords(keywords):
    """키워드에서 분류를 계산 (기준 순서 유지)"""
    ks = set(keywords)
    return [a for a in AXIS_ORDER if ks & set(AXES[a])]


def order_grades(grades):
    """허용된 학년 옵션만 남기고 기준 순서로 정렬"""
    return [g for g in GRADE_ORDER if g in set(grades or [])]


# ---------------------------------------------------------------------------
# 3. 블로그 상세 수집
# ---------------------------------------------------------------------------
def fetch_post(url, session=None):
    """
    블로그 글 상세 정보 수집.
    반환: dict(title, date, nickname, body, ok) — 본문을 못 찾으면 ok=False (비공개·삭제 가능성)
    """
    session = session or requests.Session()
    blog_id, log_no = parse_naver_ids(url)
    target = f"https://m.blog.naver.com/{blog_id}/{log_no}" if blog_id else url

    res = session.get(target, headers={"User-Agent": MOBILE_UA}, timeout=20)
    res.raise_for_status()
    soup = BeautifulSoup(res.text, "html.parser")

    def pick(selectors, attr=None):
        for sel in selectors:
            el = soup.select_one(sel)
            if not el:
                continue
            val = el.get("content") if el.name == "meta" else el.get_text(" ")
            if clean(val):
                return clean(val)
        return ""

    title = pick([".se-title-text", ".tit_h3", "h3.se_textarea", 'meta[property="og:title"]'])
    date_text = pick([".blog_date", "p.date", ".se_publishDate", 'meta[property="article:published_time"]'])
    nickname = pick(['meta[property="naverblog:nickname"]', ".blog_author strong", ".user_name", ".nick"])

    # 본문: 스마트에디터 단락 단위로 줄바꿈 유지
    main = soup.select_one(".se-main-container, #viewTypeSelector, .post_ct")
    body = ""
    if main:
        for el in main.select(".se-documentTitle, script, style"):
            el.decompose()
        paras = [clean(p.get_text(" ")) for p in main.select(".se-text-paragraph, p")]
        body = "\n".join(p for p in paras if p) or clean(main.get_text(" "))
    elif not blog_id:
        body = clean(soup.get_text(" "))  # 네이버 외 플랫폼: 페이지 전체 텍스트로 대체

    return {
        "title": title,
        "date": parse_post_date(date_text),
        "nickname": nickname,
        "body": body,
        "ok": bool(body),
    }


# ---------------------------------------------------------------------------
# 4. Claude 자동 태깅
# ---------------------------------------------------------------------------
TAG_PROMPT = """당신은 깨봉수학(초등 수학 온라인 학습 서비스) 학부모 후기를 분류하는 담당자입니다.
아래 후기 본문을 읽고 JSON 하나만 출력하세요. 설명 문장은 쓰지 마세요.

[키워드 후보와 정의] - 본문에 근거가 분명한 것만 1~4개 선택
- 첫수학: 유아·예비초 시기 첫 수학 학습으로 시작
- 수포자: 아이 또는 부모의 수학 거부감·수포자 걱정을 직접 다룸
- 학원·선행대체: 학원·선행·학습지 대신 깨봉을 선택
- 홈스쿨링: 엄마표·아빠표, 교구 활용 등 집에서 함께 하는 학습 기록
- 성적향상: 시험 점수·성적 향상을 구체적으로 언급
- 단원평가: 학교 단원평가·수학 시험 결과·대비를 언급
- 개념이해: 원리·개념 이해 중심 학습을 강조
- 연산력: 연산·구구단·계산 속도 향상
- 사고력: 사고력·문제해결력·서술형 대응
- 태도변화: 수학을 재미있어함, 자신감 등 정서·태도 변화
- 자기주도: 스스로 계획·학습하는 모습
- 영재원 / 경시대회: 실제 영재원·경시대회 준비·참가·결과 (단, "영재도 아니다" 같은 부정 언급은 제외)
- 최상위·심화: 최상위 문제집, 심화·선행 고난도 과정 병행
- 타사비교: 다른 학원·학습지·온라인 서비스와 비교
- 가격·할인: 가격·구독료·할인 혜택을 주요하게 다룸 (글 끝 할인코드 안내만 있으면 제외)
- 장단점: 장점과 단점을 정리
- 강연회: 조봉한 박사 강연·특강 후기
- 장기이용: 2년 이상 이용

[자녀 학년] - 글 작성 시점 기준, 본문에 근거가 있을 때만
- 선택지: 5세, 6세, 7세, 초1~초6, 중1~중3, 고1~고3, 성인
- "예비 초N"은 초(N-1)로 변환 (예: 예비 초3 → 초2), "예비초"(학년 없음)는 7세
- 자녀가 여럿이면 모두 포함, 근거가 없거나 불분명하면 빈 배열

[출력 형식]
{"keywords": ["..."], "grades": ["..."], "note": "학년·키워드 판단에서 추정했거나 확인이 필요한 점이 있으면 한 줄, 없으면 빈 문자열"}

[후기 제목]
{title}

[후기 본문]
{body}
"""


def tag_review(title, body):
    """Claude API로 키워드·학년 태깅. 키가 없거나 실패하면 빈 결과 반환"""
    empty = {"keywords": [], "grades": [], "note": ""}
    if not ANTHROPIC_API_KEY or not body:
        return empty
    import anthropic  # 태깅을 쓸 때만 임포트

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = TAG_PROMPT.replace("{title}", title).replace("{body}", body[:BODY_LIMIT])
    for attempt in range(2):  # 1회 재시도
        try:
            msg = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
            data = json.loads(re.search(r"\{.*\}", text, re.S).group(0))  # JSON 부분만 파싱
            return {
                "keywords": order_keywords(data.get("keywords")),
                "grades": order_grades(data.get("grades")),
                "note": clean(data.get("note", "")),
            }
        except Exception as e:
            print(f"  [WARN] 태깅 실패({attempt + 1}/2): {e}")
            time.sleep(2)
    return empty


# ---------------------------------------------------------------------------
# 5. 노션 API
# ---------------------------------------------------------------------------
class Notion:
    """노션 REST API 최소 래퍼"""

    def __init__(self, token, database_id, version=NOTION_VERSION):
        self.db = database_id
        self.s = requests.Session()
        self.s.headers.update({
            "Authorization": f"Bearer {token}",
            "Notion-Version": version,
            "Content-Type": "application/json",
        })

    def _req(self, method, path, **kw):
        # 429(요청 과다) 시 Retry-After만큼 대기 후 재시도
        for _ in range(3):
            r = self.s.request(method, f"https://api.notion.com/v1{path}", timeout=30, **kw)
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            if r.status_code >= 400:
                raise RuntimeError(f"Notion {method} {path} {r.status_code}: {r.text[:300]}")
            return r.json()
        raise RuntimeError("Notion API rate limit 반복")

    def query(self, filter_=None):
        """DB 전체 조회 (페이지네이션 처리)"""
        payload, results = {"page_size": 100}, []
        if filter_:
            payload["filter"] = filter_
        while True:
            data = self._req("POST", f"/databases/{self.db}/query", json=payload)
            results += data["results"]
            if not data.get("has_more"):
                return results
            payload["start_cursor"] = data["next_cursor"]

    def existing_links(self):
        """이미 등록된 '링크' 집합"""
        links = set()
        for p in self.query():
            url = p["properties"].get("링크", {}).get("url")
            if url:
                links.add(canonical_url(url))
        return links

    def create(self, properties):
        return self._req("POST", "/pages", json={"parent": {"database_id": self.db}, "properties": properties})

    def update(self, page_id, properties):
        return self._req("PATCH", f"/pages/{page_id}", json={"properties": properties})


def rt(text):
    """노션 rich_text 값 생성"""
    return {"rich_text": [{"text": {"content": text[:1900]}}]} if text else {"rich_text": []}


def ms(values):
    """노션 multi_select 값 생성"""
    return {"multi_select": [{"name": v} for v in values]}


def build_properties(item):
    """수집·태깅 결과를 노션 속성 페이로드로 변환"""
    props = {
        "제목": {"title": [{"text": {"content": cut_title(item["title"])}}]},
        "링크": {"url": item["url"]},
        "종류": {"select": {"name": "블로그"}},
        "상태": {"select": {"name": "공개"}},
        "커넥터즈": {"select": {"name": "Yes" if item["connector"] else "No"}},
        "작성자 닉네임": rt(item.get("nickname", "")),
        "키워드": ms(item["keywords"]),
        "분류": ms(axes_from_keywords(item["keywords"])),
        "자녀 학년": ms(item["grades"]),
        "비고": rt(item.get("note", "")),
    }
    if item.get("date"):
        props["작성일"] = {"date": {"start": item["date"]}}
    return props


# ---------------------------------------------------------------------------
# 6. 메인 처리
# ---------------------------------------------------------------------------
def collect_new(urls, known_links, dry_run=False):
    """신규 URL 상세 수집 + 판정 + 태깅"""
    session, items = requests.Session(), []
    for raw in urls:
        url = canonical_url(raw)
        if url in known_links:
            print(f"[SKIP] 이미 등록됨: {url}")
            continue
        try:
            post = fetch_post(url, session)
        except Exception as e:
            print(f"[ERROR] 상세 수집 실패: {url} ({e})")
            continue
        if not post["ok"]:
            print(f"[SKIP] 본문 없음(비공개·삭제 가능성): {url}")
            continue
        tags = tag_review(post["title"], post["body"])
        item = {"url": url, **post, **tags, "connector": is_connector(post["body"])}
        if not ANTHROPIC_API_KEY:
            item["note"] = "자동 태깅 미실행(API 키 없음)"
        items.append(item)
        known_links.add(url)
        print(f"[NEW] {cut_title(post['title'])} | {post['date']} | {post['nickname']} | "
              f"커넥터즈:{'Yes' if item['connector'] else 'No'} | 키워드:{item['keywords']} | 학년:{item['grades']}")
        time.sleep(REQUEST_DELAY)
    return items


def recheck_status(notion, dry_run=False):
    """공개 상태인 블로그 행을 다시 열어 본문이 사라졌으면 '비공개'로 갱신"""
    rows = notion.query({"and": [
        {"property": "종류", "select": {"equals": "블로그"}},
        {"property": "상태", "select": {"equals": "공개"}},
    ]})
    session, changed = requests.Session(), []
    today = datetime.now().strftime("%Y-%m-%d")
    for p in rows:
        url = p["properties"]["링크"].get("url")
        if not url:
            continue
        try:
            ok = fetch_post(url, session)["ok"]
            if not ok:                      # 일시 오류 방지를 위해 한 번 더 확인
                time.sleep(3)
                ok = fetch_post(url, session)["ok"]
        except requests.HTTPError as e:
            # 404 등은 삭제로 간주하지 않고 확인 필요로만 기록 (네이버는 비공개도 다른 페이지로 응답)
            print(f"[WARN] 재점검 요청 실패: {url} ({e})")
            continue
        except Exception as e:
            print(f"[WARN] 재점검 오류: {url} ({e})")
            continue
        if not ok:
            changed.append((p, url))
            print(f"[STATUS] 비공개 전환 감지: {url}")
        time.sleep(REQUEST_DELAY)

    # 안전장치: 감지 건수가 비정상적으로 많으면 네이버 차단 등 일시 오류로 보고 반영하지 않음
    limit = max(3, int(len(rows) * RECHECK_MAX_RATIO))
    if len(changed) > limit:
        print(f"[WARN] 비공개 감지 {len(changed)}건 > 허용 {limit}건 → 일시 오류 가능성으로 반영 생략")
        return []

    for p, url in changed:
        old_note = "".join(t["plain_text"] for t in p["properties"]["비고"]["rich_text"])
        note = f"{old_note} / 비공개·삭제 전환 확인({today})".strip(" /")
        if not dry_run:
            notion.update(p["id"], {"상태": {"select": {"name": "비공개"}}, "비고": rt(note)})
    return [url for _, url in changed]


def write_summary(new_items, changed, dry_run):
    """GitHub Actions 실행 요약 작성"""
    lines = [f"## QB 후기 노션 동기화 {'(DRY RUN)' if dry_run else ''}",
             f"- 신규 등록: {len(new_items)}건", f"- 비공개 전환: {len(changed)}건", ""]
    for it in new_items:
        lines.append(f"- [{cut_title(it['title'])}]({it['url']}) · 커넥터즈 {'Yes' if it['connector'] else 'No'}"
                     f" · {', '.join(it['keywords']) or '키워드 없음'}")
    for url in changed:
        lines.append(f"- 비공개 전환: {url}")
    text = "\n".join(lines)
    print("\n" + text)
    path = os.getenv("GITHUB_STEP_SUMMARY")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(text + "\n")


def main():
    parser = argparse.ArgumentParser(description="QB 블로그 후기 → 노션 동기화")
    parser.add_argument("--dry-run", action="store_true", help="노션에 쓰지 않고 결과만 출력")
    parser.add_argument("--skip-recheck", action="store_true", help="기존 행 공개 상태 재점검 생략")
    parser.add_argument("--urls", help="검색 대신 처리할 URL 목록(쉼표 구분)")
    args = parser.parse_args()

    if not NOTION_TOKEN:
        sys.exit("[FATAL] NOTION_TOKEN 이 설정되지 않았습니다.")
    if not ANTHROPIC_API_KEY:
        print("[WARN] ANTHROPIC_API_KEY 가 없어 자동 태깅을 건너뜁니다.")

    notion = Notion(NOTION_TOKEN, NOTION_DATABASE_ID)
    known = notion.existing_links()
    print(f"[INFO] 노션 기존 등록 링크: {len(known)}건")

    # 1) 수집 대상 URL 확보
    if args.urls:
        urls = [u.strip() for u in args.urls.split(",") if u.strip()]
    else:
        from scrape_naver_email import scrape_naver_blog
        found = scrape_naver_blog(scrape_only=True, title_pattern=TITLE_PATTERN, query_text=SEARCH_QUERY)
        urls = [r["url"] for r in found]
    print(f"[INFO] 검색 수집 URL: {len(urls)}건")

    # 2) 신규 상세 수집·태깅 → 노션 등록
    new_items = collect_new(urls, known, args.dry_run)
    for it in new_items:
        props = build_properties(it)
        if args.dry_run:
            print(json.dumps(props, ensure_ascii=False)[:600])
        else:
            notion.create(props)

    # 3) 기존 행 상태 재점검
    changed = [] if args.skip_recheck else recheck_status(notion, args.dry_run)

    write_summary(new_items, changed, args.dry_run)


if __name__ == "__main__":
    main()
