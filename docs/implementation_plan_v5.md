# 주간 후기 노션 자동 동기화 구현 계획 (v5)

이 문서는 기존 주간 블로그 스크랩(메일 발송)을 유지하면서, 같은 수집 결과를 활용해 노션 `QUEBON_Reviews` DB에 후기를 자동 등록·관리하는 기능을 추가하기 위한 구현 계획입니다.

---

## 1. 배경 및 목표

* **배경:** 후기 블로그 링크가 커넥터즈 운영 페이지 곳곳에 흩어져 있어, 2026-11-03 노션 `QUEBON_Reviews` DB로 통합 정리함 (블로그 59건 + 인스타 6건).
* **목표:** 매주 신규 블로그 후기를 사람 손 없이 DB에 쌓고, 키워드·분류·커넥터즈 여부까지 자동으로 채워 후기 분석에 바로 쓸 수 있게 함.
* **범위:** 블로그만 대상. 인스타는 로그인·약관 이슈로 이번 범위에서 제외.

---

## 2. 결정 사항

| 항목 | 결정 |
|---|---|
| 구조 | 같은 저장소, **별도 워크플로우**. 스크래핑 함수만 공유해 메일 발송과 실패를 분리 |
| 자동 태깅 | Claude API로 키워드·자녀 학년 태깅, 분류는 코드에서 계산 |
| 커넥터즈 판정 | 본문에 `깨봉 커넥터즈 활동` / `커넥터즈` / `sh.quebon.tv` 포함 시 Yes |
| 인스타 | 제외 |

---

## 3. 프로젝트 폴더 구조 및 변경 파일

```text
weekly-scrap-automation/
├── .github/
│   └── workflows/
│       ├── scraper.yml                 # (변경 없음) 메일 발송 — 금 12:20
│       └── review_sync.yml             # [신규] 노션 동기화 — 금 12:50
├── directives/
│   └── sync_reviews_notion.md          # [신규] 동기화 지침
├── docs/
│   └── implementation_plan_v5.md       # [현재 문서]
├── execution/
│   ├── scrape_naver_email.py           # [수정] scrape_naver_blog()에 title_pattern·query_text 옵션 추가 (기본값 = 기존 동작)
│   └── sync_reviews_to_notion.py       # [신규] 수집·판정·태깅·노션 반영
└── requirements.txt                    # [수정] requests, beautifulsoup4, anthropic 추가
```

---

## 4. 처리 흐름

1. 노션 DB 기존 `링크` 조회 → 중복 기준
2. `scrape_naver_blog(title_pattern="깨봉|QUEBON")`로 최근 1주 블로그 수집
3. 신규 글 상세 수집 (모바일 페이지: 제목·작성일·닉네임·본문)
4. 커넥터즈 규칙 판정
5. Claude 태깅 (키워드 1~4개, 자녀 학년, 확인 필요 메모)
6. 노션 행 생성 (키워드·분류·학년은 기준 순서로 정렬)
7. 공개 상태 기존 행 재점검 → 비공개 전환 반영 (20% 초과 감지 시 보류)
8. GitHub Actions 실행 요약(Step Summary)에 신규·전환 내역 기록

---

## 5. 사전 준비 (최초 1회)

1. **노션 통합 생성:** 노션 설정 → 연결(Integrations) → 내부 통합 생성 → 토큰 복사
2. **DB 연결:** `QUEBON_Reviews` DB 페이지 → `···` → 연결 추가 → 위 통합 선택
3. **GitHub Secrets 등록:**
   * `NOTION_TOKEN`: 노션 통합 토큰
   * `NOTION_DATABASE_ID`: `36368543839a4c7dab3209e6b87cafb7` (미등록 시 이 값이 기본값)
   * `ANTHROPIC_API_KEY`: Claude API 키
4. **테스트 실행:** Actions → `Weekly Review Notion Sync` → Run workflow → `dry_run=true`로 결과 확인 후 `false`로 실제 반영

---

## 6. 검증 결과 (로컬, 2026-11-03)

* 커넥터즈 판정: 기존 61건 대비 Yes 39/47 일치, 오탐 0
* URL 정규화·날짜 변환·키워드 정렬·분류 계산·노션 페이로드 생성: 테스트 통과
* 비공개 감지 및 일괄 차단 시 반영 보류 로직: 테스트 통과
* 기존 메일 스크래퍼: 기본값 호출 시 동작 동일 (시그니처 호환)
* **미검증:** 실제 네이버·노션·Claude API 호출 → 최초 `dry_run` 실행으로 확인 필요

---

## 7. 리스크 및 대응

| 리스크 | 대응 |
|---|---|
| 네이버 페이지 구조 변경 | 선택자 다중 대체(fallback), 실패 시 directive의 Self-Annealing 절차 |
| GitHub 러너 IP 차단 | 요청 간 1초 지연, 재점검 20% 안전장치 |
| 태깅 품질 편차 | 정의가 포함된 프롬프트, 허용 옵션 외 값 자동 제거, 비고에 확인 필요 메모 |
| 커넥터즈 오판(이미지 고지) | 월 1회 커넥터즈 명단과 대조해 수동 보정 |
| 제목 필터 확대로 무관 글 유입 | Step Summary로 주간 검토, 필요 시 `TITLE_PATTERN` 조정 |
