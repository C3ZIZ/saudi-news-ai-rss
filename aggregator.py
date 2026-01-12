import feedparser
import json
import os
from datetime import datetime, timedelta
import google.generativeai as genai
from newspaper import Article, Config
import time
import random
import traceback
import requests

API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
else:
    model = None

rss_sources = {
    "saudi_general": [
        "https://saudigazette.com.sa/rssFeed/74",
        "https://news.google.com/rss/search?q=site:www.arabnews.com/saudi-arabia&hl=en-US&gl=US&ceid=US:en"
    ],
    "saudi_business_tech": [
        "https://saudigazette.com.sa/rssFeed/72",
        "https://www.argaam.com/en/rss/ho-main-news?sectionid=1524",
        "https://news.google.com/rss/search?q=Saudi+Arabia+NEOM+Artificial+Intelligence+Technology&hl=en-US&gl=US&ceid=US:en"
    ],
    "global_tech": [
        "https://www.wired.com/feed/rss",
        "https://www.theverge.com/rss/index.xml"
    ]
}

def get_seen_ids(days_back=3):
    # Deduplicate against articles stored in the last few days
    seen_ids = set()
    today = datetime.now().date()
    for i in range(1, days_back + 1):
        prev_date = today - timedelta(days=i)
        date_str = prev_date.strftime('%Y-%m-%d')
        file_path = f"api/{date_str}/news.json"
        if os.path.exists(file_path):
            try:
                with open(file_path, "r") as f:
                    data = json.load(f)
                    for item in data:
                        seen_ids.add(item.get('id'))
            except:
                pass
    return seen_ids

def extract_text(url):
    try:
        # Configure Newspaper to mimic a real browser and avoid short timeouts
        config = Config()
        config.browser_user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        config.request_timeout = 20
        
        article = Article(url, config=config)
        article.download()
        article.parse()
        
        if not article.text:
            return None
        return article.text[:2000]
    except Exception as e:
        print(f"Text Extract Failed: {e}")
        return None

def summarize_with_ai(text):
    if not API_KEY: 
        return "Error: API Key Missing"
    
    if not text: 
        return "Error: No text extracted from article source\nClick the link to read the full story."

    for attempt in range(3):
        try:
            prompt = f"Summarize this news article into exactly one professional Arabic sentence (Media style): {text}"
            response = model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            # Retry gently on rate limits; surface safety blocks to the caller
            if "429" in error_msg:
                time.sleep(20)
            elif "finish_reason" in error_msg.lower():
                return f"Error: Content Safety Blocked ({error_msg})"
            else:
                if attempt == 2: 
                    return f"AI Failed: {error_msg}"
                    
    return "Error: AI Rate Limit Exceeded"

def fetch_feed(category, urls, blocklist):
    # Use a Session to look like a real browser user
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })

    items = []
    for url in urls:
        print(f"Checking Source: {url}")
        try:
            # increased timeout and verify=True (standard SSL)
            response = session.get(url, timeout=20) 
            
            # Check if we actually got text content
            if len(response.content) < 100:
                print("  ! Error: Empty response from server")
                continue

            feed = feedparser.parse(response.content)
            
            if not feed.entries:
                print("  ! No entries found (Check URL or Blocking)")
                continue
                
            for entry in feed.entries[:2]:  # Process only a couple of headlines per source to stay lightweight
                if entry.link in blocklist:
                    print(f"  Skipping Duplicate: {entry.title}")
                    continue
                
                print(f"  Processing: {entry.title}")
                
                full_text = extract_text(entry.link)
                summary = summarize_with_ai(full_text)
                
                items.append({
                    "id": entry.link,
                    "title": entry.title,
                    "link": entry.link,
                    "source": feed.feed.get('title', 'Unknown'),
                    "category": category,
                    "published": entry.get("published", str(datetime.now())),
                    "summary_ai": summary
                })
                time.sleep(2) 
        except Exception as e:
            print(f"  Feed Error: {e}")
    return items

# Keep a short history to avoid reprocessing recent links
history_blocklist = get_seen_ids(days_back=3)

all_news = []
for cat, urls in rss_sources.items():
    all_news.extend(fetch_feed(cat, urls, history_blocklist))

today = datetime.now().strftime('%Y-%m-%d')
folder_path = f"api/{today}"
os.makedirs(folder_path, exist_ok=True)

with open(f"{folder_path}/news.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

with open("api/latest.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

print(f"Done. Saved {len(all_news)} articles.")