"""Gather real-time trend & stock data for Kiro CLI to analyze."""
import json
from trends import get_trending_keywords
from price import get_stock_data


def gather():
    """Fetch Google Trends + stock data for trending-related tickers, print JSON report."""
    print("Fetching US Google Trends...", flush=True)
    keywords = get_trending_keywords(top_n=20)
    
    # Collect stock data for any tickers Kiro identifies
    # This is called separately after Kiro maps keywords → tickers
    report = {
        "trending_keywords": keywords,
        "generated_at": __import__("datetime").datetime.now().isoformat(),
    }
    print(json.dumps(report, indent=2))


def check_tickers(tickers: list[str]):
    """Fetch price + fundamentals + events for given tickers."""
    from events import get_upcoming_events
    results = {}
    for t in tickers:
        data = get_stock_data(t)
        if data:
            data["events"] = get_upcoming_events(t)
            results[t] = data
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        # Usage: python main.py check AAPL NVDA COIN
        check_tickers(sys.argv[2:])
    else:
        gather()
