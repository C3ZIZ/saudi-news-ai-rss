import feedparser
import json
import os
from datetime import datetime
import google.generativeai as genai
from newspaper import Article
import time
API_KEY = os.environ.get("GEMINI_API_KEY")


if API_KEY:
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
else:
    print("No API Found! No AI Summaries.")
    model = None


# Sources so we get news (simple)
rss_sources = {
    "saudi_general": [
        "https://www.arabnews.com/cat/1/rss.xml",
        "https://saudigazette.com.sa/rssFeed/74"
    ],
    "saudi_business_tech": [
        "https://saudigazette.com.sa/rssFeed/72"
    ],
    "global_tech": [
        "https://www.theverge.com/rss/index.xml",
        "https://www.wired.com/feed/rss"
    ]
}

# --- FUNCTIONS ---
def extract_text(url):
    try:
        article = Article(url)
        article.download()
        article.parse()
        return article.text[:1500] # Limit text to save speed/tokens
    except:
        return None

def summarize_with_ai(text):
    if not model or not text: return "Summary unavailable."
    try:
        # Instruction: Summarize in Arabic
        prompt = f"Summarize this news article into exactly one professional Arabic sentence (Media style): {text}"
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        return "AI Processing Failed."

def fetch_feed(category, urls):
    items = []
    for url in urls:
        print(f"Checking {url}...")
        try:
            feed = feedparser.parse(url)
            # Limit to top 2 articles per source to keep runtimes fast
            for entry in feed.entries[:2]:
                print(f"  > Found: {entry.title}")
                
                # Extract & Summarize
                full_text = extract_text(entry.link)
                summary = summarize_with_ai(full_text)
                
                items.append({
                    "id": entry.link,
                    "title": entry.title,
                    "link": entry.link,
                    "source": feed.feed.get('title', 'Unknown Source'),
                    "category": category,
                    "published": entry.get("published", str(datetime.now())),
                    "summary_ai": summary
                })
                time.sleep(1) # Be polite to servers
        except Exception as e:
            print(f"  X Error: {e}")
    return items



print("Start Point...")
all_news = []

for cat, urls in rss_sources.items():
    all_news.extend(fetch_feed(cat, urls))

# Structure: api/YYYY-MM-DD/news.json
today = datetime.now().strftime('%Y-%m-%d')
folder_path = f"api/{today}"
os.makedirs(folder_path, exist_ok=True)

# Save Daily Archive
archive_path = f"{folder_path}/news.json"
with open(archive_path, "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

# Save 'Latest' endpoint (Overwrite daily)
with open("api/latest.json", "w") as f:
    json.dump(all_news, f, indent=2, ensure_ascii=False)

print(f"Saved {len(all_news)} articles.")