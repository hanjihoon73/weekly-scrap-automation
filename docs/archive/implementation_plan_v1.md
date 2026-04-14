# 주간 스크랩 자동화 GitHub Actions 마이그레이션 계획

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
* GitHub Actions 환경에서 패키지를 설치할 수 있도록 의존성 명세 파일을 추가합니다.

#### [NEW] requirements.txt
* `python-dotenv`, `selenium`, `webdriver-manager` 패키지 목록 기술

---

### 스크래퍼 코드 보완
* GitHub Actions 서버에는 디스플레이(UI)가 없으므로 브라우저를 `Headless`(창 없는 모드)로 실행해야 합니다. 기존 코드가 로컬에서는 창을 띄울 수 있도록 유지하되, GitHub Actions 환경일 때만 백그라운드로 실행되도록 옵션을 추가합니다.

#### [MODIFY] execution/scrape_naver_email.py
* `GITHUB_ACTIONS` 환경 변수가 존재할 경우 Chrome 브라우저 옵션에 `--headless=new`, `--no-sandbox`, `--disable-dev-shm-usage` 등을 추가하는 로직 구현.

---

### GitHub Actions 워크플로우 생성
* 윈도우 스케줄러가 하고 있던 예약 실행을 GitHub Actions의 Cron 문법으로 구현합니다.

#### [NEW] .github/workflows/scraper.yml
* 한국 시간(KST) 기준 매주 금요일 12:01 및 12:20에 실행. (UTC 기준으로는 금요일 03:01, 03:20에 해당)
* Python 환경 세팅 및 패키지 설치(`pip install -r requirements.txt`).
* `GitHub Secrets`를 환경 변수로 주입받아 스크립트 실행.

## 확인 및 진행
위 방식대로 구현을 진행해도 될까요? 승인해주시면 코드를 작성하겠습니다!
