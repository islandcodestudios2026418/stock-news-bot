"""Fetch trending topics from Google Trends (US) via RSS feed."""
import requests
import xml.etree.ElementTree as ET


DAILY_TRENDS_URL = "https://trends.google.com/trending/rss?geo=US"


def get_trending_keywords(top_n=20):
    """Get trending search topics in the US via Google Trends RSS.
    
    Returns list of dicts: [{"keyword": str, "score": int}, ...]
    """
    all_trending = {}
    
    try:
        resp = requests.get(DAILY_TRENDS_URL, timeout=10)
        resp.raise_for_status()
        root = ET.fromstring(resp.content)
        
        # RSS items are in channel/item
        ns = {'ht': 'https://trends.google.com/trending/rss'}
        for item in root.findall('.//item'):
            title = item.findtext('title', '')
            if title:
                all_trending[title] = all_trending.get(title, 0) + 1
            
            # Get approximate traffic if available
            traffic = item.findtext('ht:approx_traffic', '', ns)
            if traffic:
                # e.g. "500,000+" -> weight higher
                try:
                    num = int(traffic.replace(',', '').replace('+', ''))
                    all_trending[title] = max(all_trending.get(title, 0), num // 100000)
                except ValueError:
                    pass
    except Exception as e:
        print(f"  [trends] RSS fetch failed: {e}")

    sorted_kws = sorted(all_trending.items(), key=lambda x: -x[1])
    return [{"keyword": k, "score": v} for k, v in sorted_kws[:top_n]]
