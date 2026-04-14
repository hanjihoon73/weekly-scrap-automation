import requests
from bs4 import BeautifulSoup
import json
import os
import argparse
from datetime import datetime

def scrape_blog(url):
    print(f"Scraping {url}...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Simple extraction logic (can be refined per blog)
        title = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'No Title'
        content = ""
        # Try to find common content containers
        article = soup.find('article') or soup.find('div', class_='content') or soup.find('main')
        if article:
            content = article.get_text(separator='\n', strip=True)
        else:
            content = soup.get_text(separator='\n', strip=True)

        data = {
            "url": url,
            "title": title,
            "content": content[:1000] + "...", # Truncate for now
            "scraped_at": datetime.now().isoformat()
        }
        
        return data
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return {"url": url, "error": str(e)}

def save_to_tmp(data, filename):
    os.makedirs('.tmp', exist_ok=True)
    filepath = os.path.join('.tmp', filename)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved results to {filepath}")

def main():
    parser = argparse.ArgumentParser(description='Scrape blog content.')
    parser.add_argument('--urls', type=str, help='Comma-separated list of URLs')
    args = parser.parse_args()

    if not args.urls:
        print("No URLs provided. Use --urls 'url1,url2'")
        return

    urls = [url.strip() for url in args.urls.split(',')]
    results = []

    for url in urls:
        result = scrape_blog(url)
        results.append(result)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_to_tmp(results, f"scrap_results_{timestamp}.json")

if __name__ == "__main__":
    main()
