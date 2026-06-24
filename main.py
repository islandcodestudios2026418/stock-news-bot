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
    """Full pipeline: trends → map → price → divergence → search queries + watchlist."""
    from mapper import map_keywords_to_tickers
    from divergence import detect_divergence
    from events import get_upcoming_events
    from search_queries import generate_search_queries
    from watchlist import scan_watchlist

    print("1. Fetching Google Trends...", file=sys.stderr)
    keywords = get_trending_keywords(top_n=20)

    print("2. Mapping keywords → tickers...", file=sys.stderr)
    mapped = map_keywords_to_tickers(keywords)

    signals, search_queries = [], []
    if mapped:
        all_tickers = list({t for m in mapped for t in m["tickers"]})
        print(f"3. Fetching stock data for {len(all_tickers)} tickers...", file=sys.stderr)
        stock_data = get_batch_stock_data(all_tickers)

        print("4. Detecting divergence...", file=sys.stderr)
        signals = detect_divergence(mapped, stock_data)
        for sig in signals:
            sig["events"] = get_upcoming_events(sig["ticker"])

        print("5. Generating search queries...", file=sys.stderr)
        search_queries = generate_search_queries(mapped)
    else:
        print("3-5. No mappable keywords, skipping divergence.", file=sys.stderr)

    print("6. Scanning watchlist...", file=sys.stderr)
    watchlist_alerts = scan_watchlist()

    report = {
        "generated_at": datetime.now().isoformat(),
        "keywords_scanned": len(keywords),
        "mapped_companies": len(mapped),
        "signals": signals,
        "search_queries": search_queries,
        "watchlist_alerts": watchlist_alerts,
    }
    print(json.dumps(report, indent=2))


def deliver():
    """Scan watchlist → deduplicate → send new alerts to Discord."""
    from watchlist import scan_watchlist
    from dedup import deduplicate
    from discord_hook import send_alerts

    print("Scanning watchlist...", file=sys.stderr)
    alerts = scan_watchlist()
    print(f"  {len(alerts)} tickers with alerts", file=sys.stderr)

    new_alerts = deduplicate(alerts)
    print(f"  {len(new_alerts)} tickers with NEW alerts (after dedup)", file=sys.stderr)

    if not new_alerts:
        print("No new alerts to deliver.", file=sys.stderr)
        return

    sent = send_alerts(new_alerts)
    if sent:
        print(f"✅ Delivered {len(new_alerts)} alerts to Discord", file=sys.stderr)
    else:
        print("❌ Discord delivery failed", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "check":
        check_tickers(sys.argv[2:])
    elif cmd == "scan":
        scan()
    elif cmd == "deliver":
        deliver()
    elif cmd == "watchlist":
        from watchlist import scan_watchlist
        print(json.dumps(scan_watchlist(), indent=2))
    elif cmd == "filings":
        from edgar import get_batch_filings
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_filings(tickers), indent=2))
    elif cmd == "ratings":
        from ratings import get_batch_ratings
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_ratings(tickers), indent=2))
    else:
        gather()
