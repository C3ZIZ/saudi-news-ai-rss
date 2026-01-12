# sa-news-ai-rss
An AI-powered RSS workflow that collects Saudi (general, business, tech) and global tech headlines, extracts the article text, and summarizes each story into one Arabic sentence.

## How it works
- Fetch RSS feeds defined in [aggregator.py](aggregator.py#L13-L34) using a browser-like `requests.Session` to avoid bot blocking.
- Skip recently-seen links by reading past JSON files ([get_seen_ids](aggregator.py#L36-L52)).
- Download each article with `newspaper3k`, cap extracted text to 2,000 chars, then summarize via Gemini ([summarize_with_ai](aggregator.py#L68-L93)).
- Rate-limit gently and surface safety blocks; only take a couple of items per source to stay light ([fetch_feed](aggregator.py#L95-L145)).
- Write results to date-stamped JSON and mirror to `api/latest.json` for easy consumption.

## Why it is built this way
- **Bot evasion:** Browser-like headers and per-source throttling reduce RSS and article blocking.
- **Duplication control:** Short history prevents reposting the same link across runs.
- **Graceful degradation:** If AI or extraction fails, the JSON still ships with errors noted rather than breaking the run.
- **Static API:** Output is plain JSON files, easy to serve from any static host or CDN.

## Setup
1) Install Python deps:
```bash
pip install -r requirements.txt
```
2) Export your Gemini API key:
```bash
export GEMINI_API_KEY="YOUR_KEY"
```
3) Run the collector:
```bash
python aggregator.py
```

## API usage
- Latest combined feed: [api/latest.json](api/latest.json)
- Historical by date: [api/YYYY-MM-DD/news.json](api/2026-01-12/news.json) (replace with any run date)

Example fetch:
```bash
curl -s https://your-host/api/latest.json | jq '.[0]'
```
Fields per item: `id` (URL), `title`, `link`, `source`, `category`, `published`, `summary_ai`.

## Notes
- Ensure your host serves the `api/` directory as static files.
- Gemini summaries require the env var; without it, `summary_ai` contains an error message instead.
