"""Fetch recent news headlines for stocks via yfinance."""
import yfinance as yf


def get_news(ticker: str, max_items: int = 5) -> list[dict]:
    """Fetch latest news headlines for a ticker."""
    try:
        items = yf.Ticker(ticker).news or []
        results = []
        for item in items[:max_items]:
            c = item.get("content", {})
            results.append({
                "title": c.get("title", ""),
                "published": c.get("pubDate", ""),
                "source": c.get("provider", {}).get("displayName", ""),
                "url": c.get("canonicalUrl", {}).get("url", ""),
            })
        return results
    except Exception:
        return []


def get_batch_news(tickers: list[str], max_per: int = 3) -> dict:
    """Fetch news for multiple tickers."""
    return {t: get_news(t, max_per) for t in tickers}
