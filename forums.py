"""Fetch early signals from niche professional forums (HN, Reddit, Lobste.rs)."""
import requests

SOURCES = [
    {"name": "HackerNews", "url": "https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=20&query="},
    {"name": "Reddit/stocks", "url": "https://www.reddit.com/r/stocks/hot.json?limit=15"},
    {"name": "Reddit/wallstreetbets", "url": "https://www.reddit.com/r/wallstreetbets/hot.json?limit=15"},
]

HEADERS = {"User-Agent": "stock-news-bot/1.0"}


def _fetch_hn(query: str = "") -> list[dict]:
    """Fetch top HackerNews stories, optionally filtered by query."""
    url = f"https://hn.algolia.com/api/v1/search?tags=story&hitsPerPage=20"
    if query:
        url += f"&query={query}"
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        return [{"title": h["title"], "points": h.get("points", 0),
                 "source": "HackerNews", "url": f"https://news.ycombinator.com/item?id={h['objectID']}"}
                for h in hits if h.get("points", 0) >= 50]
    except Exception:
        return []


def _fetch_reddit(subreddit: str) -> list[dict]:
    """Fetch hot posts from a subreddit."""
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=15"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        posts = r.json().get("data", {}).get("children", [])
        return [{"title": p["data"]["title"], "points": p["data"].get("score", 0),
                 "source": f"r/{subreddit}", "url": f"https://reddit.com{p['data']['permalink']}"}
                for p in posts if p["data"].get("score", 0) >= 20]
    except Exception:
        return []


def get_forum_signals(sectors: list[str] = None) -> list[dict]:
    """Get combined forum signals. Returns [{title, points, source, url}] sorted by points."""
    results = []
    results.extend(_fetch_hn())
    for sub in ["stocks", "wallstreetbets"]:
        results.extend(_fetch_reddit(sub))
    return sorted(results, key=lambda x: -x["points"])
