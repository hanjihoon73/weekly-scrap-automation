# GitHub Actions 60일 비활성화 방지(Keepalive) 구현 계획 (v3)

이 문서는 깃허브 정책상 60일간 커밋이나 활동이 없을 경우 주간 스크랩 스케줄러가 자동으로 비활성화(Disabled)되는 문제를 방지하기 위해, 워크플로우에 자동 활동 갱신(Keepalive) 기능을 추가하는 계획입니다. 비개발 직군도 쉽게 이해할 수 있도록 구성되었습니다.

---

## 1. 배경 및 목적

* **문제 상황:** 리포지토리에 사람의 직접적인 활동(코드 커밋 등)이 60일 이상 없으면, 매주 정기 실행되던 깃허브 액션 스케줄러가 자동으로 정지됩니다.
* **해결 목적:** 마지막 커밋 후 50일 이상 지났을 때 깃허브 액션이 스스로 가벼운 활동(더미 커밋)을 기록하도록 하여, 관리자가 신경 쓰지 않아도 매주 스크랩이 중단 없이 영구적으로 동작하도록 만듭니다.

---

## 2. 프로젝트 폴더 구조 및 파일 구성

```text
weekly-scrap-automation/
├── .github/
│   └── workflows/
│       └── scraper.yml             # [수정] 깃허브 액션 실행 스케줄 및 Keepalive 스텝 추가
├── directives/                     # 블로그 수집 대상 및 지침 파일
├── docs/                           # 프로젝트 문서 폴더
│   ├── archive/                    # 이전 버전 문서 보관소
│   │   └── implementation_plan_v2.md
│   └── implementation_plan_v3.md   # [현재 문서] v3 구현 계획서
├── execution/                      # 파이썬 실행 스크립트 모음
│   ├── scrape_naver_email.py       # 메인 스크래퍼 및 이메일 발송
│   └── scrape_naver_test_email.py  # 테스트 모드 발송
├── requirements.txt                # 파이썬 의존성 패키지 목록
└── Agent.md
```

---

## 3. 구현 내용

### `.github/workflows/scraper.yml` 수정
1. **커밋 권한 부여 (`permissions: contents: write`)**: 워크플로우가 깃허브 리포지토리에 활동 기록(커밋)을 남길 수 있도록 권한을 추가합니다.
2. **Keepalive 액션 추가 (`gautamkrishnar/keepalive-workflow@v1`)**:
   * 매주 스크랩 작업이 완료된 후 실행됩니다.
   * 마지막 커밋 이후 50일이 지나지 않았다면 아무 작업도 하지 않아 커밋 히스토리를 깨끗하게 유지합니다.
   * 마지막 커밋 이후 50일이 경과하면 자동으로 더미 활동을 기록하여 60일 비활성화 제한 타이머를 0으로 리셋합니다.

---

## 4. 사용자 사전/사후 확인 필요 사항 (GitHub 설정)

> [!IMPORTANT]
> 깃허브 리포지토리의 보안 정책상 워크플로우에 쓰기 권한이 허용되어 있어야 합니다.
> * GitHub 리포지토리 웹페이지 접속 → **Settings** → **Actions** → **General**
> * 화면 하단의 **Workflow permissions** 섹션에서 **Read and write permissions**가 선택되어 있는지 확인이 필요합니다.
