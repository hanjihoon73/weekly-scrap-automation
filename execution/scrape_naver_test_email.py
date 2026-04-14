import sys
import os

# Add the current directory to sys.path to allow importing from the execution folder
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

from scrape_naver_email import main, load_config, scrape_naver_blog, send_email

def run_test_mode():
    """ Runs the scraper in test mode (sends to kevin@quebon.com and jason@quebon.com) """
    print("Starting Weekly Blog Scrap [TEST MODE - Kevin & Jason]")
    
    # Load config in test mode (filters recipients)
    config = load_config(mode="test")
    
    # Scrape results
    results = scrape_naver_blog(scrape_only=False)
    
    if results:
        # Send email to test recipients
        send_email(results, config)
        print("Test email sent successfullly to kevin@quebon.com and jason@quebon.com")
    else:
        print("No results found to send.")

if __name__ == "__main__":
    run_test_mode()
