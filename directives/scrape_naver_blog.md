# Directive: Naver Blog Scraping & Weekly Email

## Goal
Scrape Naver blog search results for "깨봉수학" from the past week and email them to kevin@quebon.com.

## Inputs
- Search Keyword: "깨봉수학"
- Period: "1주" (Last 1 week)
- SMTP Credentials: Found in `d:/Antigravity File/260127 Daily News Automation/.env`

## Tools & Scripts
- `execution/scrape_naver_email.py`: Playwright script for scraping and emailing.

## Step-by-Step Instructions
1. **Environment Setup**: The script loads credentials from the external `.env` path. No local `.env` modification is required for credentials.
2. **Execution**:
   ```bash
   python execution/scrape_naver_email.py
   ```
3. **Logic**:
   - Opens Chrome in headed mode.
   - Searches for "깨봉수학".
   - Filters by "블로그" tab and "1주" period.
   - **Filters results to only include blogs where the title contains "깨봉수학"**.
   - Collects unique results.
   - Sends an email via SMTP.
4. **Debugging**:
   - Screenshots and logs are saved in `.tmp/`.

## Edge Cases
- **No Results**: If no blogs are found, a "No results" email is sent.
- **UI Changes**: If Naver's Search UI changes, update CSS selectors in `execution/scrape_naver_email.py`.
- **Deduplication**: Results are deduplicated by URL.

## Self-Annealing
- If Naver blocks the scraper, consider adding random delays or changing the User-Agent.
- If SMTP fails, check if the external `.env` file path is still valid or if the App Password has expired.
