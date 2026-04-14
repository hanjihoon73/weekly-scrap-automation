@echo off
chcp 65001 > nul
echo ==============================================
echo       위클리 블로그 스크랩 자동화 프로그램
echo ==============================================
echo.

echo [1/2] 필요한 패키지(라이브러리)를 설치(확인)합니다...
pip install python-dotenv selenium webdriver-manager -q
echo.

echo [2/2] 실행할 작업을 선택해주세요.
echo 1: 예약 발송 자동 등록 (매주 금요일 12:01, 12:20 자동 발송)
echo 2: [수동] 테스트 결과 발송 (Kevin, Jason 에게만 전송)
echo 3: [수동] 전체 결과 발송 (팀원 전체에게 전송)
echo 4: 종료
echo.

set /p choice="번호를 입력하고 엔터를 누르세요 [1/2/3/4]: "

if "%choice%"=="1" (
    echo.
    echo 윈도우 스케줄러에 예약 발송 작업을 등록합니다...
    powershell -ExecutionPolicy Bypass -File setup_scheduler.ps1
) else if "%choice%"=="2" (
    echo.
    echo 테스트 발송을 시작합니다...
    python execution\scrape_naver_test_email.py
) else if "%choice%"=="3" (
    echo.
    echo 전체 발송을 시작합니다...
    python execution\scrape_naver_email.py --mode full
) else if "%choice%"=="4" (
    echo.
    echo 프로그램을 종료합니다.
) else (
    echo.
    echo 잘못된 입력입니다. 프로그램을 종료합니다.
)

echo.
pause
