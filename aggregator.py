import feedparser
import json
import os
from datetime import datetime
import google.generativeai as genai
from newspaper import Article
import time
import random

# --- CONFIGURATION ---
API_KEY = os.environ.get("GEMINI_API_KEY")

# Configure AI
if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    print("WARNING: GEMINI_API_KEY not found.")

# Verified Sources
rss_sources = {
    "saudi_general": [
        "https://www.arabnews.com/cat/1/rss.xml", 
        "https://saudigazette.com.sa/rssFeed/74"
    ],
    "saudi_business_tech": [
        "https://www.argaam.com/en/company/newsrss",
        "https://saudigazette.com.sa/rssFeed/72"
    ],
    "global_tech": [
        "https://www.wired.com/feed/rss",
        "https://www.theverge.com/rss/index.xml"
    ]
}

# Functions
def extract_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text[:2000] # Limit chars
    except:
        return None

def summarize_with_ai(text):
    if not API_KEY or not text: return "Summary unavailable."
    
    # Switch to the STABLE model (1.5 Flash)
    model = genai.GenerativeModel('gemini-2.5-flash-lite') 
    
    prompt = f"Summarize this news article into exactly one professional Arabic sentence (Media style): {text}"
    
    # RETRY LOGIC (The Fix)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if "429" in str(e):
                # If rate limited, wait 20-40 seconds then retry
                wait_time = 20 + random.randint(1, 10)
                print(f"    ! Rate limit hit. Waiting {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"    ! AI Error: {e}")
                return "AI Processing Failed."
    
    return "Summary unavailable (Rate Limit)."

def fetch_feed(category, urls):
    items = []
    for url in urls:
        print(f"Checking {url}...")
        try:
            feed = feedparser.parse(url)
            # Limit to top 1-2 articles per source to be safe
            for entry in feed.entries[:2]:
                print(f"  > Found: {entry.title}")
                
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
                # Standard polite delay between items
                time.sleep(5) 
        except Exception as e:
            print(f"  X Error: {e}")
    return items


print("Starting News Aggregation")
all_news = []

for cat, urls in rss_sources.items():
    all_news.extend(fetch_feed(cat, urls))

# Save Files
today = datetime.now().strftime('%Y-%m-%d')
folder_path = f"api/{today}"
os.makedirs(folder_path, exist_ok=True)

with open(f"{folder_path}/news.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

with open("api/latest.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

print(f"Saved {len(all_news)} articles.")