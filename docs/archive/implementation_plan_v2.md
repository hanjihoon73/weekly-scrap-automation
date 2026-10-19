# 주간 스크랩 자동화 GitHub Actions 마이그레이션 계획 (v2)

현재 로컬 환경(배치 및 윈도우 스케줄러)에서 실행되는 네이버 블로그 스크랩 발송을 GitHub Actions를 사용하여 클라우드 환경에서 자동 실행되도록 리팩토링하는 계획입니다.

## 사용자 확인 필요

> [!IMPORTANT]
> GitHub 리포지토리에 반영한 후, GitHub 저장소의 **Settings > Secrets and variables > Actions** 경로에서 다음 환경 변수(Secrets)를 등록해야 합니다. (기존 `.env`에 있는 정보를 등록하시면 됩니다.)
> 1. `SMTP_SERVER` (예: smtp.gmail.com)
> 2. `SMTP_PORT` (예: 587)
> 3. `SENDER_EMAIL` (예: mkt@equalkey.com)
> 4. `SENDER_PASSWORD` (앱 비밀번호)

> [!WARNING]
> 현재 로컬의 윈도우 스케줄러를 그대로 두면, 로컬과 GitHub Actions 양쪽에서 중복 발송될 수 있습니다. 프로젝트가 GitHub에 반영되고 Actions가 성공적으로 동작함을 확인하신 후에는 `setup_scheduler.ps1` 등을 통해 생성한 로컬의 스케줄러 작업들을 수동으로 삭제해 주시기 바랍니다.

## 제안하는 변경 사항

---

### 구성 및 의존성 추가
* GitHub Actions 환경에서 패키지를 매번 새롭게 설치할 수 있도록 의존성 명세 파일을 추가합니다. GitHub Actions 서버는 매 실행 시 초기화된 가상 환경(`ubuntu-latest`)을 제공하므로 필요한 라이브러리 및 폰트가 매번 설치되도록 구성할 예정입니다.

#### [NEW] requirements.txt
* `python-dotenv`, `selenium`, `webdriver-manager` 패키지 목록 기술

---

### 스크래퍼 코드 보완
* GitHub Actions 서버에는 디스플레이(UI)가 없으므로 브라우저를 `Headless`(창 없는 모드)로 실행해야 합니다. 기존 코드가 로컬에서는 창을 띄울 수 있도록 유지하되, GitHub Actions 환경일 때만 백그라운드로 실행되도록 옵션을 추가합니다.

#### [MODIFY] execution/scrape_naver_email.py
* `GITHUB_ACTIONS` 환경 변수가 존재할 경우 Chrome 브라우저 옵션에 `--headless=new`, `--no-sandbox`, `--disable-dev-shm-usage` 등을 추가하는 로직 구현.

---

### GitHub Actions 워크플로우 생성
* 윈도우 스케줄러가 하고 있던 예약 실행을 GitHub Actions의 문법으로 구현합니다.

#### [NEW] .github/workflows/scraper.yml
1. **환경 매번 설정**: 실행 시마다 `ubuntu-latest` 환경에 필수 한글 폰트(`fonts-nanum`) 및 `requirements.txt`에 명시된 파이썬 라이브러리가 새롭게 설치되도록 명시합니다. (스크린샷 등의 작업 시 한글이 깨지지 않기 위함)
2. **트리거 처리**:
    - **수동 실행 (테스트 및 전체 발송)**: `workflow_dispatch`를 사용하여 사용자가 GitHub 화면에서 `full`(전체) 혹은 `test`(테스트) 모드를 선택하여 수동(버튼 클릭)으로 발송을 진행할 수 있게 합니다.
    - **자동 예약 실행 (전체 발송)**: `schedule` (cron) 문법을 사용하여 매주 금요일 12:20 KST (UTC 03:20)에 **전체 발송(`full`)만** 동작하게 설정합니다. 테스트용 스케줄인 12:01은 삭제되었습니다.
