"""Gather real-time trend & stock data for Kiro CLI to analyze."""
import json
import sys
import os
from datetime import datetime

# Fix Unicode output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

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


def summary():
    """Compact market dashboard — all signals in one text block for Discord."""
    from watchlist import scan_watchlist
    from macro import get_macro_events
    from earnings import get_batch_earnings
    from sector_rotation import get_sector_rotation
    from correlation import get_correlation_alert
    from technicals import get_batch_technicals

    config = json.loads(open("watchlist.json").read())
    tickers = config.get("tickers", [])

    # Macro
    macro = get_macro_events(days_ahead=7)
    lines = [f"📊 **Market Dashboard** — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
    if macro:
        lines.append("\n🏛️ **Macro Events (7d):**")
        for e in macro[:5]:
            lines.append(f"  • {e['date']} — {e['event']} [{e['impact']}]")

    # Correlation alert
    corr = get_correlation_alert(tickers)
    if corr.get("alert"):
        lines.append(f"\n⚠️ **Correlation Alert:** {corr['signal']}")
        lines.append(f"  Avg 5d change: {corr['avg_change_5d']:+.1f}%")

    # Sector rotation
    rotation = get_sector_rotation()
    if rotation:
        inflows = [r for r in rotation if r.get("signal") == "inflow"]
        outflows = [r for r in rotation if r.get("signal") == "outflow"]
        lines.append("\n🔄 **Sector Rotation (5d):**")
        for r in inflows:
            lines.append(f"  📈 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")
        for r in outflows:
            lines.append(f"  📉 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")

    # Technical signals summary
    techs = get_batch_technicals(tickers)
    notable_techs = [(t, d) for t, d in techs.items() if d.get("signals")]
    if notable_techs:
        lines.append("\n📐 **Technical Signals:**")
        for t, d in notable_techs:
            sigs = ", ".join(d["signals"])
            lines.append(f"  • {t} RSI={d.get('rsi','-')} — {sigs}")

    # Earnings
    earnings = get_batch_earnings(tickers)
    upcoming_earn = [(t, e["upcoming"]) for t, e in earnings.items() if e.get("upcoming")]
    if upcoming_earn:
        lines.append("\n💰 **Upcoming Earnings:**")
        for t, e in upcoming_earn:
            est = f" (est ${e['eps_estimate']:.2f})" if e.get("eps_estimate") else ""
            lines.append(f"  • {t} — {e['date']}{est}")

    # Watchlist alerts summary
    alerts = scan_watchlist()
    if alerts:
        lines.append(f"\n🚨 **Alerts ({len(alerts)} tickers):**")
        for a in alerts:
            top_alert = a["alerts"][0] if a["alerts"] else ""
            lines.append(f"  • {a['ticker']} ${a['price']:.2f} ({a['change_5d_pct']:+.1f}% 5d) — {top_alert}")

    if not macro and not upcoming_earn and not alerts and not rotation:
        lines.append("\n✅ All quiet. No notable events or alerts.")

    output = "\n".join(lines)
    print(output)
    return output


def deliver_summary():
    """Send summary dashboard to Discord as a single embed."""
    import os
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        print("❌ DISCORD_WEBHOOK_URL not set", file=sys.stderr)
        return
    text = summary()
    # Discord embed has 4096 char description limit
    payload = {
        "embeds": [{
            "title": f"📊 Market Dashboard — {datetime.now().strftime('%Y-%m-%d')}",
            "description": text[:4096],
            "color": 0x3498DB,
        }]
    }
    import requests
    r = requests.post(url, json=payload, timeout=10)
    if r.status_code == 204:
        print("✅ Summary delivered to Discord", file=sys.stderr)
    else:
        print(f"❌ Discord delivery failed: {r.status_code}", file=sys.stderr)


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else None
    if cmd == "check":
        check_tickers(sys.argv[2:])
    elif cmd == "scan":
        scan()
    elif cmd == "deliver":
        deliver()
    elif cmd == "deliver_summary":
        deliver_summary()
    elif cmd == "summary":
        summary()
    elif cmd == "watchlist":
        from watchlist import scan_watchlist
        print(json.dumps(scan_watchlist(), indent=2))
    elif cmd == "add":
        from watchlist import add_ticker
        for t in sys.argv[2:]:
            print(add_ticker(t))
    elif cmd == "remove":
        from watchlist import remove_ticker
        for t in sys.argv[2:]:
            print(remove_ticker(t))
    elif cmd == "threshold":
        from watchlist import set_threshold
        if len(sys.argv) >= 4:
            print(set_threshold(sys.argv[2], float(sys.argv[3])))
        else:
            print("Usage: threshold <key> <value>")
    elif cmd == "history":
        from dedup import _load
        history = _load()
        # Show recent alerts sorted by date
        items = sorted(history.items(), key=lambda x: x[1], reverse=True)
        print(f"📜 Alert History ({len(items)} total, showing last 20):")
        for key, ts in items[:20]:
            print(f"  {ts[:16]} — {key[:12]}...")
    elif cmd == "filings":
        from edgar import get_batch_filings
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_filings(tickers), indent=2))
    elif cmd == "ratings":
        from ratings import get_batch_ratings
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_ratings(tickers), indent=2))
    elif cmd == "earnings":
        from earnings import get_batch_earnings
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_earnings(tickers), indent=2))
    elif cmd == "macro":
        from macro import get_macro_events
        print(json.dumps(get_macro_events(), indent=2))
    elif cmd == "options":
        from options_flow import get_batch_options_flow
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_options_flow(tickers), indent=2))
    elif cmd == "short":
        from short_interest import get_batch_short_interest
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_short_interest(tickers), indent=2))
    elif cmd == "sectors":
        from sector_rotation import get_sector_rotation
        print(json.dumps(get_sector_rotation(), indent=2))
    elif cmd == "insider":
        from edgar import get_insider_trades
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps({t: get_insider_trades(t) for t in tickers}, indent=2))
    elif cmd == "technicals":
        from technicals import get_batch_technicals
        tickers = sys.argv[2:] or json.loads(open("watchlist.json").read()).get("tickers", [])
        print(json.dumps(get_batch_technicals(tickers), indent=2))
    elif cmd == "correlation":
        from correlation import get_correlation_alert
        tickers = sys.argv[2:] or None
        print(json.dumps(get_correlation_alert(tickers), indent=2))
    else:
        gather()
