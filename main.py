"""Gather real-time trend & stock data for Kiro CLI to analyze."""
import json
import sys
from datetime import datetime
from trends import get_trending_keywords
from price import get_stock_data, get_batch_stock_data


def gather():
    """Fetch Google Trends keywords, print JSON (legacy behavior)."""
    keywords = get_trending_keywords(top_n=20)
    print(json.dumps({"trending_keywords": keywords, "generated_at": datetime.now().isoformat()}, indent=2))


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


def scan():
    """Full pipeline: trends → map → price → divergence → search queries for Kiro."""
    from mapper import map_keywords_to_tickers
    from divergence import detect_divergence
    from events import get_upcoming_events
    from search_queries import generate_search_queries

    print("1. Fetching Google Trends...", file=sys.stderr)
    keywords = get_trending_keywords(top_n=20)

    print("2. Mapping keywords → tickers...", file=sys.stderr)
    mapped = map_keywords_to_tickers(keywords)
    if not mapped:
        print(json.dumps({"signals": [], "search_queries": [], "note": "No mappable keywords today"}))
        return

    all_tickers = list({t for m in mapped for t in m["tickers"]})

    print(f"3. Fetching stock data for {len(all_tickers)} tickers...", file=sys.stderr)
    stock_data = get_batch_stock_data(all_tickers)

    print("4. Detecting divergence...", file=sys.stderr)
    signals = detect_divergence(mapped, stock_data)
    for sig in signals:
        sig["events"] = get_upcoming_events(sig["ticker"])

    print("5. Generating search queries for Kiro...", file=sys.stderr)
    search_queries = generate_search_queries(mapped)

    report = {
        "generated_at": datetime.now().isoformat(),
        "keywords_scanned": len(keywords),
        "mapped_companies": len(mapped),
        "signals": signals,
        "search_queries": search_queries,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "check":
        check_tickers(sys.argv[2:])
    elif cmd == "scan":
        scan()
    else:
        gather()
