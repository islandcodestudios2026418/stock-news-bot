"""Watchlist monitoring — alerts for price/volume/event/filing/rating anomalies."""
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from price import get_batch_stock_data
from events import get_upcoming_events

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> dict:
    if not WATCHLIST_PATH.exists():
        return {"tickers": [], "alerts": {}}
    return json.loads(WATCHLIST_PATH.read_text())


def save_watchlist(config: dict):
    WATCHLIST_PATH.write_text(json.dumps(config, indent=2))


def add_ticker(ticker: str) -> str:
    config = load_watchlist()
    t = ticker.upper()
    if t in config["tickers"]:
        return f"{t} already in watchlist"
    config["tickers"].append(t)
    save_watchlist(config)
    return f"Added {t} to watchlist"


def remove_ticker(ticker: str) -> str:
    config = load_watchlist()
    t = ticker.upper()
    if t not in config["tickers"]:
        return f"{t} not in watchlist"
    config["tickers"].remove(t)
    save_watchlist(config)
    return f"Removed {t} from watchlist"


def set_threshold(key: str, value: float) -> str:
    config = load_watchlist()
    if "alerts" not in config:
        config["alerts"] = {}
    config["alerts"][key] = value
    save_watchlist(config)
    return f"Set {key} = {value}"


def _fetch_ticker_data(ticker: str, days: int = 7) -> dict:
    """Fetch all supplementary data for a single ticker (runs in thread)."""
    from news import get_news
    from edgar import get_recent_filings, get_insider_trades
    from ratings import get_recent_ratings
    from earnings import get_earnings
    from options_flow import get_options_flow
    from short_interest import get_short_interest
    from technicals import get_technicals

    return {
        "events": get_upcoming_events(ticker),
        "filings": get_recent_filings(ticker, days=days),
        "ratings": get_recent_ratings(ticker, days=days),
        "earnings": get_earnings(ticker, days_ahead=days),
        "options": get_options_flow(ticker),
        "short": get_short_interest(ticker),
        "technicals": get_technicals(ticker),
        "insider": get_insider_trades(ticker, days=days),
        "news": get_news(ticker, 3),
    }


def scan_watchlist() -> list[dict]:
    """Check watchlist stocks for alert conditions. Uses parallel fetching."""
    config = load_watchlist()
    tickers = config.get("tickers", [])
    if not tickers:
        return []

    alerts_cfg = config.get("alerts", {})
    drop_thresh = alerts_cfg.get("price_drop_pct", -5)
    surge_thresh = alerts_cfg.get("price_surge_pct", 5)
    vol_thresh = alerts_cfg.get("volume_spike_threshold", 2.0)
    earnings_days = alerts_cfg.get("earnings_days_ahead", 7)

    # Batch price fetch (already uses yfinance batch download)
    stock_data = get_batch_stock_data(tickers)

    # Parallel fetch supplementary data per ticker
    ticker_extras = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(_fetch_ticker_data, t, earnings_days): t for t in tickers}
        for future in as_completed(futures):
            t = futures[future]
            try:
                ticker_extras[t] = future.result()
            except Exception:
                ticker_extras[t] = {}

    alerts = []
    for ticker in tickers:
        data = stock_data.get(ticker)
        if not data:
            continue

        extra = ticker_extras.get(ticker, {})
        triggered = []
        chg5 = data["change_5d_pct"]

        # Price alerts
        if chg5 <= drop_thresh:
            triggered.append(f"🔴 5d drop {chg5:.1f}%")
        elif chg5 >= surge_thresh:
            triggered.append(f"🟢 5d surge +{chg5:.1f}%")
        if data["volume_spike"] >= vol_thresh:
            triggered.append(f"📊 Volume spike {data['volume_spike']:.1f}x")

        # Events
        now = datetime.now()
        for ev in extra.get("events", []):
            try:
                ev_date = datetime.strptime(ev["date"], "%Y-%m-%d")
                if 0 <= (ev_date - now).days <= earnings_days:
                    triggered.append(f"📅 {ev['event']} on {ev['date']}")
            except (ValueError, KeyError):
                pass

        # SEC filings
        for f in extra.get("filings", []):
            triggered.append(f"📋 SEC {f['form']} filed {f['filed']}")

        # Analyst ratings
        for r in extra.get("ratings", []):
            triggered.append(f"⭐ {r['action']}: {r['firm']} → {r['to_grade']}")

        # Earnings
        earn = extra.get("earnings", {})
        if earn.get("upcoming"):
            triggered.append(f"💰 Earnings on {earn['upcoming']['date']}")
        if earn.get("surprise"):
            s = earn["surprise"]
            triggered.append(f"💥 EPS surprise {s['surprise_pct']:+.1f}% on {s['date']}")

        # Options flow
        options = extra.get("options", [])
        if options:
            top = options[0]
            triggered.append(f"🎯 Unusual {top['type']} flow: ${top['strike']} exp {top['expiration']} ({top['vol_oi_ratio']}x vol/OI)")

        # Short interest
        si = extra.get("short")
        if si and si.get("squeeze_signal"):
            triggered.append(f"🩳 High short: {si['short_pct_float']}% float, {si['days_to_cover']}d to cover")

        # Insider trades
        insider = extra.get("insider", [])
        for b in [t for t in insider if t["direction"] == "BUY" and t["value_usd"] > 100_000][:2]:
            triggered.append(f"🟢 Insider BUY: {b['insider'][:20]} ${b['value_usd']:,}")
        for s in [t for t in insider if t["direction"] == "SELL" and t["value_usd"] > 1_000_000][:2]:
            triggered.append(f"🔻 Insider SELL: {s['insider'][:20]} ${s['value_usd']:,}")

        # Technical signals
        tech = extra.get("technicals", {})
        for sig in tech.get("signals", []):
            if sig == "overbought":
                triggered.append(f"📈 RSI overbought ({tech['rsi']})")
            elif sig == "oversold":
                triggered.append(f"📉 RSI oversold ({tech['rsi']})")
            elif sig == "golden_cross":
                triggered.append("✨ Golden Cross (MA50 > MA200)")
            elif sig == "death_cross":
                triggered.append("💀 Death Cross (MA50 < MA200)")

        if triggered:
            alerts.append({
                "ticker": ticker,
                "name": data["name"],
                "price": data["price"],
                "change_5d_pct": chg5,
                "change_30d_pct": data["change_30d_pct"],
                "volume_spike": data["volume_spike"],
                "alerts": triggered,
                "events": extra.get("events", []),
                "filings": extra.get("filings", []),
                "ratings": extra.get("ratings", []),
                "news": extra.get("news", []),
            })

    return alerts
