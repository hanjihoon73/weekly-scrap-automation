# Directive: Weekly Review → Notion Sync

## Goal
매주 네이버 블로그에서 깨봉수학 후기를 수집해 노션 `QUEBON_Reviews` DB에 신규 등록하고, 기존 후기의 공개 상태를 갱신한다.

## Inputs
- 검색어: `깨봉수학` (블로그 탭, 최근 1주)
- 제목 필터: `깨봉|QUEBON` (대소문자 무시) — 메일 발송용 필터(`깨봉수학`)보다 넓음
- 노션 DB: `QUEBON_Reviews` (Marketing Group > Reviews)
- Secrets: `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `ANTHROPIC_API_KEY`

## Tools & Scripts
- `execution/sync_reviews_to_notion.py`: 수집·판정·태깅·노션 반영
- `execution/scrape_naver_email.py`의 `scrape_naver_blog()`를 재사용 (`title_pattern`, `query_text` 옵션)
- `.github/workflows/review_sync.yml`: 매주 금요일 12:50 KST 자동 실행

## Step-by-Step
1. 노션 DB의 기존 `링크` 목록을 읽어 중복 기준으로 사용
2. 네이버 블로그 검색 → 제목 필터 통과 URL 수집
3. 신규 URL마다 모바일 페이지(`m.blog.naver.com/{id}/{logNo}`)에서 제목·작성일·닉네임·본문 추출
4. 커넥터즈 판정: 본문에 `깨봉 커넥터즈 활동` / `커넥터즈` / `sh.quebon.tv` 중 하나라도 있으면 `Yes`
5. Claude API로 `키워드`(1~4개)·`자녀 학년` 태깅 → `분류`는 키워드에서 자동 계산
6. 노션에 행 생성: 종류=블로그, 상태=공개, 제목 30자 이내, 키워드·분류는 기준 순서로 정렬
7. 공개 상태인 기존 블로그 행을 재방문해 본문이 없으면 `상태=비공개`, 비고에 확인일 기록
8. 품질 채점 (`execution/score_reviews.py`): 신규 글은 등록 시, 기존 공개 블로그는 `--rescore missing|all`로 채점. 지표 5개(경험 구체성·효과 근거·메시지 적합성·정보 유용성·콘텐츠 완성도, 각 0~100)와 채점 근거·인용 문장·검토 필요·채점일을 기록. 평균·별점·우수·2차 활용 후보는 노션 수식이 계산. `검토 완료` 행은 재채점하지 않음. 루브릭 원문은 노션 QUEBON_Review 페이지 토글 → 바꾸면 `SCORE_PROMPT`도 함께 수정
9. Step Summary 작성: 검색 수집 = 신규 등록 + 이미 등록됨 + 본문 없음 + 수집 실패로 건수를 대조할 수 있게 표시하고, 이미 등록된 글은 제목·DB id 목록으로 보여 줌 (메일 스크랩 건수와 노션 등록 건수 차이 확인용)

## 필드 매핑
| 노션 컬럼 | 값 출처 |
|---|---|
| 제목 | 글 제목 (30자 초과 시 말줄임) |
| 작성일 | 글 상세 페이지 날짜 |
| 작성자 닉네임 | 블로그 닉네임 메타 |
| 링크 | `https://blog.naver.com/{blogId}/{logNo}` 형식으로 통일 |
| 종류 / 상태 | 블로그 / 공개 (고정) |
| 커넥터즈 | 본문 규칙 판정 |
| 키워드 / 자녀 학년 | Claude 태깅 |
| 분류 | 키워드 → 상위 축 매핑 |
| 비고 | 태깅 시 추정·확인 필요 메모 |

## Edge Cases
- **본문 없음**: 비공개·삭제 글은 신규 등록하지 않음
- **재점검 오탐 방지**: 비공개 감지가 전체의 20%를 넘으면 네이버 일시 차단으로 보고 반영 보류
- **API 키 없음**: 태깅을 건너뛰고 비고에 `자동 태깅 미실행` 기록
- **태깅 실패**(2회 재시도 후): 행은 등록하고 비고에 `자동 태깅 실패(사유) - 키워드·학년 수동 입력 필요` 기록, Step Summary에 ⚠️ 경고 표시
- **네이버 외 도메인**: 페이지 전체 텍스트로 대체 수집
- **커넥터즈 판정 한계**: 고지 문구를 이미지로만 넣은 글은 `No`로 잡힐 수 있음 (기존 데이터 기준 39/47 일치, 오탐 0)

## Self-Annealing
- 상세 수집이 일제히 실패하면 `fetch_post()`의 선택자(`.se-main-container`, `.blog_date` 등)를 먼저 점검
- 키워드 체계를 바꾸면 노션 옵션, `AXES`, `TAG_PROMPT`를 함께 수정
- 노션 API 오류가 나면 `NOTION_VERSION`과 DB의 통합(Integration) 연결 상태를 확인
