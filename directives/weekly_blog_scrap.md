# Directive: Weekly Blog Scraping

## Goal
Extract content from a list of blog URLs and save the results into organized files for weekly review.

## Inputs
- A list of URLs (provided manually or via a source file).

## Tools & Scripts
- `execution/scrape_blogs.py`: Captures title, author, date, and main content from a given URL.

## Step-by-Step Instructions
1. **Initialize Environment**: Ensure `.env` is configured with necessary API keys (if required by the scraping script).
2. **Run Execution Script**:
   ```bash
   python execution/scrape_blogs.py --urls "url1, url2"
   ```
3. **Review Intermediate Data**: Scraped content will be saved in `.tmp/` as JSON or Markdown files.
4. **Final Output**: The script can optionally compile these into a summary document or a Google Sheet.

## Edge Cases
- **Paywalls/Logins**: If a site is protected, the script should log a warning and skip.
- **Dynamic Content**: If content is loaded via JS, a headless browser (like Playwright or Selenium) might be needed in the execution script.
- **Rate Limiting**: The script should include delays between requests.

## Self-Annealing
- If a specific blog format changes and scraping fails, update `execution/scrape_blogs.py` to handle the new selector and update this directive with any new dependencies.
