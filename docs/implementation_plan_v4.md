# GitHub Actions 네이티브 Keepalive 구현 계획 (v4)

이 문서는 서드파티 액션(`keepalive-workflow`)의 깃허브 정책 차단 문제를 해결하고, 외부 의존성 없이 네이티브 쉘 스크립트를 통해 60일 비활성화를 안전하고 영구적으로 방지하기 위한 구현 계획입니다.

---

## 1. 발생한 문제 및 원인 분석

* **발생 에러:** `Error: Repository access blocked` (워크플로우 시작 시 액션 다운로드 단계에서 발생)
* **원인:** 워크플로우에서 참조하던 외부 액션 저장소(`gautamkrishnar/keepalive-workflow`)가 GitHub Trust & Safety 팀에 의해 이용약관(ToS) 위반 사유로 **리포지토리 접근 차단(Block)**되었습니다.
* **해결 방향:** 불안정한 외부 서드파티 액션을 완전히 제거하고, GitHub Actions 러너에서 직접 동작하는 **경량 네이티브 Git 쉘 스크립트**로 전환합니다.

---

## 2. 프로젝트 폴더 구조 및 파일 구성

```text
weekly-scrap-automation/
├── .github/
│   └── workflows/
│       └── scraper.yml             # [수정] 차단된 서드파티 액션을 네이티브 Git 스크립트로 교체
├── directives/                     # 블로그 수집 대상 및 지침 파일
├── docs/                           # 프로젝트 문서 폴더
│   ├── archive/                    # 이전 버전 문서 보관소
│   │   ├── implementation_plan_v2.md
│   │   └── implementation_plan_v3.md
│   └── implementation_plan_v4.md   # [현재 문서] v4 구현 계획서
├── execution/                      # 파이썬 실행 스크립트 모음
│   ├── scrape_naver_email.py       # 메인 스크래퍼 및 이메일 발송
│   └── scrape_naver_test_email.py  # 테스트 모드 발송
├── requirements.txt                # 파이썬 의존성 패키지 목록
└── Agent.md
```

---

## 3. 구현 내용

### `.github/workflows/scraper.yml` 수정
* **외부 액션 제거:** `gautamkrishnar/keepalive-workflow@v1` 제거
* **네이티브 Git 스텝 추가:**
  1. `git log -1 --format=%ct`로 마지막 커밋 시점과 현재 시간의 차이를 일(day) 단위로 계산
  2. 마지막 커밋 이후 **45일 미만**이면: 아무 작업도 하지 않고 정상 종료 (커밋 기록 깨끗하게 유지)
  3. 마지막 커밋 이후 **45일 이상** 경과 시: `.github/keepalive.txt` 파일에 타임스탬프를 갱신하고 커밋 & 푸시하여 60일 타이머를 리셋
  4. 커밋 메시지에 `[skip ci]`를 포함하여 불필요한 액션 재트리거 방지
