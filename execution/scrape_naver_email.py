import os
import smtplib
import time
import re
from datetime import datetime, timedelta
import locale
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from urllib.parse import urlparse, parse_qs, quote, unquote
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

try:
    locale.setlocale(locale.LC_TIME, "ko_KR.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "Korean_Korea.949")
    except:
        pass

# Determine the absolute path to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, ".tmp")

def load_config(mode="full"):
    """Load config and filter recipients based on mode."""
    # Always load local .env in the project root
    local_env_path = os.path.join(BASE_DIR, ".env")
    load_dotenv(local_env_path)
    
    all_recipients = [
        "kevin@quebon.com",
        "kee@quebon.com", 
        "jason@quebon.com",
        "carly@quebon.com",
        "co@quebon.com",
        "sophie@quebon.com",
        "june@quebon.com"
    ]
    
    if mode == "test":
        recipients = ["kevin@quebon.com", "jason@quebon.com"]
    else:
        recipients = all_recipients

    return {
        "smtp_server": os.getenv("SMTP_SERVER"),
        "smtp_port": int(os.getenv("SMTP_PORT", 587)),
        "sender_email": os.getenv("SENDER_EMAIL"),
        "sender_password": os.getenv("SENDER_PASSWORD"),
        "receiver_email": recipients
    }

def normalize_url(url):
    """Normalize Naver blog URLs to a standard format."""
    if not url:
        return ""
    if "search.naver.com" in url and "url=" in url:
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        if "url" in params:
            url = unquote(params["url"][0])
    
    # Standardize to blog.naver.com/id/post_number if possible, strip query params
    parsed = urlparse(url)
    normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    return normalized.rstrip("/")

def parse_date_text(date_text):
    """
    Parse Korean date text and determine if it's within the last 7 days.
    Returns (is_within_7_days, date_label)
    """
    if not date_text:
        return False, None
        
    now = datetime.now()
    today = now.date()
    
    # 1) N시간 전 (N hours ago)
    if "시간 전" in date_text:
        return True, date_text
    
    # 2) N일 전 (N days ago)
    match_day = re.search(r"(\d+)\s*일\s*전", date_text)
    if match_day:
        days = int(match_day.group(1))
        return days <= 7, date_text
    
    # 3) YYYY.MM.DD.
    match_date = re.search(r"(\d{4})\.(\d{2})\.(\d{2})\.", date_text)
    if match_date:
        try:
            year, month, day = map(int, match_date.groups())
            post_date = datetime(year, month, day).date()
            diff = (today - post_date).days
            # Requirement: 0~7 days
            return 0 <= diff <= 7, date_text
        except ValueError:
            return False, None
            
    # 4) 1주 전 (Specific case for 7 days ago - Naver usually marks 7 days as 1주 전)
    if "1주 전" in date_text:
        return True, date_text
        
    # 5) 어제 (Yesterday)
    if "어제" in date_text:
        return True, date_text
        
    # 6) 방금 전, N분 전 (Just now, N mins ago)
    if "방금 전" in date_text or "분 전" in date_text:
        return True, date_text
            
    return False, None

def scrape_naver_blog(scrape_only=False):
    """Scrape Naver for blog results for '깨봉수학' using refined card-based extraction."""
    results = []
    
    chrome_options = Options()
    chrome_options.add_experimental_option("detach", True)
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36")
    
    # GitHub Actions 환경일 경우 Headless 모드 추가
    if os.environ.get("GITHUB_ACTIONS") == "true":
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")

    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    wait = WebDriverWait(driver, 20)
    
    # Stats for logging
    total_cards_count = 0
    kept_count = 0
    skipped_count = 0
    
    try:
        query = quote("깨봉수학")
        # User preferred URL: ssc=tab.blog.all (Explicit Blog Tab)
        search_url = f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={query}&sm=tab_opt&nso=so%3Ar%2Cp%3A1w"
        
        if scrape_only:
            print(f"\n[DEBUG] Navigating to: {search_url}")
            
        driver.get(search_url)
        
        # Primary container selectors (Nexearch Fender, Blog Tab Fender, and Standard List styles)
        card_selectors = [
            "div.fds-web-doc-root.fds-web-normal-doc-root",
            "div.fds-ugc-single-intention-item-list-tab > div", # Blog Tab organic results
            "li[class*='lst']",                                 # Standard List / Ads
            "li.bx",                                           # Standard Card / Filter
            "div.total_area"                                    # Older style
        ]
        
        cards = []
        best_selector = None
        
        for selector in card_selectors:
            try:
                # Shorter wait for each, but we already waited 20s if nothing found?
                # Actually, let's wait for ANY of them.
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                cards = driver.find_elements(By.CSS_SELECTOR, selector)
                if cards:
                    best_selector = selector
                    if scrape_only:
                        print(f"[DEBUG] Found {len(cards)} cards using selector: {best_selector}")
                    break
            except:
                continue

        if not cards:
            if scrape_only:
                print(f"[DEBUG] Timed out or no cards found with any known selectors.")
            os.makedirs(TMP_DIR, exist_ok=True)
            driver.save_screenshot(os.path.join(TMP_DIR, "timeout_screenshot.png"))
            with open(os.path.join(TMP_DIR, "naver_page_source.html"), 'w', encoding='utf-8') as f:
                f.write(driver.page_source)
            return []

        total_cards_count = len(cards)
        seen_urls = set()
        
        for idx, card in enumerate(cards, 1):
            decision = "SKIPPED"
            reason = ""
            current_title = ""
            current_url = ""
            current_date = ""
            
            try:
                # Flexible extraction based on selector or fallback
                # 1) Try Fender style (Integrated Search)
                title_elem = None
                
                # Title & URL Candidates
                title_selectors = [
                    "span.sds-comps-text-type-headline1", # Fender
                    "a.api_txt_lines.total_tit",         # New Blog Tab
                    "a.title_link",                       # Standard List
                    "dt > a",                             # Old List
                    ".title"                              # Generic
                ]
                
                for t_sel in title_selectors:
                    try:
                        title_elem = card.find_element(By.CSS_SELECTOR, t_sel)
                        current_title = title_elem.text.strip()
                        if current_title:
                            # If it's an <a> tag, get href directly. If not, look for ancestor <a>.
                            if title_elem.tag_name == "a":
                                current_url = title_elem.get_attribute("href")
                            else:
                                try:
                                    url_elem = title_elem.find_element(By.XPATH, "./ancestor::a[@href]")
                                    current_url = url_elem.get_attribute("href")
                                except:
                                    pass
                            
                            if current_url: break
                    except:
                        continue
                
                # 3) Extract date_text
                # Try specific date elements first
                date_selectors = [
                    "span.sub_time",
                    "span.date",
                    "span.sds-comps-text-type-caption",
                    "span.sds-comps-info-list-item-text", # Common in Fender for dates
                    ".caption",
                    ".date"
                ]
                for d_sel in date_selectors:
                    try:
                        date_elem = card.find_element(By.CSS_SELECTOR, d_sel)
                        current_date = date_elem.text.strip()
                        if current_date and re.search(r"(\d|전|방금|어제)", current_date): 
                            break
                        else:
                            current_date = ""
                    except:
                        continue
                
                # Fallback Date: Search for ALL elements containing date-like text
                if not current_date:
                    try:
                        # Find spans containing common date keywords
                        date_keywords = ["시간 전", "일 전", "주 전", "어제", "방금 전", "분 전"]
                        for kw in date_keywords:
                            try:
                                kw_elem = card.find_element(By.XPATH, f".//span[contains(text(), '{kw}')]")
                                current_date = kw_elem.text.strip()
                                if current_date: break
                            except:
                                continue
                            if current_date: break
                    except:
                        pass
                
                # Fallback: regex on the whole card text
                if not current_date:
                    card_text = card.text
                    date_match = re.search(r"(\d+\s*시간\s*전|\d+\s*일\s*전|\d{4}\.\d{2}\.\d{2}\.|1주\s*전|어제|방금\s*전|\d+\s*분\s*전)", card_text)
                    if date_match:
                        current_date = date_match.group(1).strip()
                
                # Normalize URL for deduplication/filtering
                if current_url:
                    current_url = normalize_url(current_url)
                
                if not current_title or not current_url or not current_date:
                    reason = f"Missing components (Title:{bool(current_title)}, URL:{bool(current_url)}, Date:{bool(current_date)})"
                elif current_url in seen_urls:
                    reason = "Duplicate URL"
                else:
                    # 4) Check if title contains '깨봉수학'
                    if "깨봉수학" not in current_title:
                        reason = "Title does not contain '깨봉수학'"
                    else:
                        # 5) Domain filtering: Only include recognized blog platforms
                        parsed_url = urlparse(current_url)
                        domain = parsed_url.netloc.lower()
                        
                        allowed_domains = [
                            "blog.naver.com", 
                            "tistory.com", 
                            "brunch.co.kr", 
                            "post.naver.com", 
                            "blog.daum.net"
                        ]
                        
                        is_allowed_domain = any(allowed in domain for allowed in allowed_domains)
                        
                        if not is_allowed_domain:
                            reason = f"Domain '{domain}' is not an allowed blog platform"
                        else:
                            # 6) Enforce 1-week filter logic
                            is_within_7_days, _ = parse_date_text(current_date)
                            if is_within_7_days:
                                decision = "KEPT"
                                results.append({
                                    "title": current_title,
                                    "url": current_url,
                                    "date": current_date
                                })
                                seen_urls.add(current_url)
                                kept_count += 1
                            else:
                                reason = "Outside 7-day range"
                        
            except Exception as e:
                decision = "ERROR"
                reason = str(e)
            
            if decision != "KEPT":
                skipped_count += 1
                
            if scrape_only:
                log_line = f"[{idx}] {decision}: {current_title or 'N/A'}"
                if reason:
                    log_line += f" ({reason})"
                print(log_line)
                if current_url:
                    print(f"    URL: {current_url}")
                if current_date:
                    print(f"    Date: {current_date}")

        if scrape_only:
            print(f"\n=== SCRAPE SUMMARY ===")
            print(f"Total cards found: {total_cards_count}")
            print(f"Kept count: {kept_count}")
            print(f"Skipped count: {skipped_count}")
            print("======================\n")

        # Diagnostics
        os.makedirs(TMP_DIR, exist_ok=True)
        driver.save_screenshot(os.path.join(TMP_DIR, "naver_scrap_result.png"))
        with open(os.path.join(TMP_DIR, "naver_page_source.html"), "w", encoding="utf-8") as f:
            f.write(driver.page_source)
            
    except Exception as e:
        print(f"Critical error during scraping: {e}")
        os.makedirs(TMP_DIR, exist_ok=True)
        driver.save_screenshot(os.path.join(TMP_DIR, "error_screenshot.png"))
    finally:
        driver.quit()
            
    return results

def send_email(results, config):
    """Compose and send the email with formatted results."""
    if not config["sender_email"] or not config["sender_password"]:
        print("Error: Mail configuration is incomplete.")
        return

    msg = MIMEMultipart()
    msg['From'] = config["sender_email"]
    
    # Handle multiple recipients
    if isinstance(config["receiver_email"], list):
        msg['To'] = ", ".join(config["receiver_email"])
    else:
        msg['To'] = config["receiver_email"]
        
    msg['Subject'] = "깨봉수학 위클리 블로그 스크랩"
    
    body = "안녕하세요.\n깨봉수학 위클리 블로그 스크랩 결과 공유드립니다.\n\n"
    
    if results:
        for i, res in enumerate(results, 1):
            # Format: 제목 (date_text)\nurl
            body += f"{i}. {res['title']} ({res['date']})\n{res['url']}\n\n"
    else:
        body += "최근 7일 내 발행된 블로그 포스트가 없습니다.\n\n"
        
    body += "감사합니다."
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(config["smtp_server"], config["smtp_port"])
        server.starttls()
        server.login(config["sender_email"], config["sender_password"])
        
        # Send to multiple recipients
        recipients = config["receiver_email"] if isinstance(config["receiver_email"], list) else [config["receiver_email"]]
        server.send_message(msg, to_addrs=recipients)
        
        server.quit()
        print("Email sent successfully!")
    except Exception as e:
        print(f"Failed to send email: {e}")

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Naver Blog Scraping (7-Day Filter)')
    parser.add_argument('--scrape-only', action='store_true', help='Scrape and log without sending email.')
    parser.add_argument('--mode', choices=['test', 'full'], default='full', help='Recipient mode: test (Kevin only) or full (Everyone).')
    args = parser.parse_args()

    config = load_config(mode=args.mode)
    
    if args.mode == 'test':
        print(f"[INFO] Running in TEST mode. Recipients: {config['receiver_email']}")
    else:
        print(f"[INFO] Running in FULL mode. Recipients: {len(config['receiver_email'])} people")

    results = scrape_naver_blog(scrape_only=args.scrape_only)
    
    if not args.scrape_only:
        send_email(results, config)

if __name__ == "__main__":
    main()
