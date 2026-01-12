import feedparser
import json
import os
from datetime import datetime, timedelta
import google.generativeai as genai
from newspaper import Article
import time
import random
import traceback  # <--- NEW: For detailed error logs

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")

if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash-lite')
else:
    print("API_KEY NOT FOUND. AI Summary will be disabled.")
    model = None

rss_sources = {
    "saudi_general": [
        "https://saudigazette.com.sa/rssFeed/74",
        "https://www.arabnews.com/cat/1/rss.xml" 
    ],
    "saudi_business_tech": [
        "https://saudigazette.com.sa/rssFeed/72",
        "https://www.argaam.com/en/rss/ho-main-news?sectionid=1524",
        "https://thesaudiboom.com/feed"
    ],
    "global_tech": [
        "https://www.wired.com/feed/rss",
        "https://www.theverge.com/rss/index.xml"
    ]
}

# functions

def get_seen_ids(days_back=3):
    seen_ids = set()
    today = datetime.now().date()
    print(f"--- Checking history (Last {days_back} days) ---")
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
        article = Article(url)
        article.download()
        article.parse()
        if not article.text:
            return None
        return article.text[:2000]
    except Exception as e:
        print(f"    ! Text Extract Failed: {e}")
        return None

def summarize_with_ai(text):
    # 1. Check if AI is disabled
    if not API_KEY: 
        return "Error: API Key Missing"
    
    # 2. Check if text extraction failed
    if not text: 
        return "Error: No text extracted from article source"

    # 3. Try to Summarize (With detailed logging)
    for attempt in range(3):
        try:
            prompt = f"Summarize this news article into exactly one professional Arabic sentence (Media style): {text}"
            response = model.generate_content(prompt)
            return response.text.strip()
            
        except Exception as e:
            error_msg = str(e)
            print(f"    ! AI Attempt {attempt+1} Error: {error_msg}")
            
            # If Rate Limit, wait and retry
            if "429" in error_msg:
                print("      -> Hit Rate Limit. Waiting 20s...")
                time.sleep(20)
            # If blocked by safety filters
            elif "finish_reason" in error_msg.lower():
                return f"Error: Content Safety Blocked ({error_msg})"
            # Other errors
            else:
                traceback.print_exc() # Print full details to console
                if attempt == 2: # If last attempt failed
                    return f"AI Failed: {error_msg}"
                    
    return "Error: AI Rate Limit Exceeded"

def fetch_feed(category, urls, blocklist):
    items = []
    for url in urls:
        print(f"\nChecking Source: {url}...")
        try:
            feed = feedparser.parse(url)
            if not feed.entries:
                print("  ! No entries found (Check URL)")
                
            for entry in feed.entries[:2]: # Top 2 per source
                
                # Check Duplicates
                if entry.link in blocklist:
                    print(f"  [SKIP] Duplicate: {entry.title[:30]}...")
                    continue
                
                print(f"  > Processing: {entry.title[:50]}...")
                
                # Extract
                full_text = extract_text(entry.link)
                
                # Summarize
                summary = summarize_with_ai(full_text)
                
                # Log success/fail visually
                if "Error:" in summary:
                    print(f"X {summary}")
                else:
                    print(f" Summary generated")

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
            print(f"  X Feed Error: {e}")
    return items


print("Starting News Aggregation")

# 1. Get History
history_blocklist = get_seen_ids(days_back=3)

# 2. Fetch News
all_news = []
for cat, urls in rss_sources.items():
    all_news.extend(fetch_feed(cat, urls, history_blocklist))

# 3. Save
today = datetime.now().strftime('%Y-%m-%d')
folder_path = f"api/{today}"
os.makedirs(folder_path, exist_ok=True)

with open(f"{folder_path}/news.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

with open("api/latest.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

print(f"\n--- Done. Saved {len(all_news)} articles. ---")