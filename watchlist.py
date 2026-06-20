"""Watchlist monitoring — alerts for price/volume/event anomalies."""
import json
from datetime import datetime, timedelta
from pathlib import Path
from price import get_batch_stock_data
from events import get_upcoming_events

WATCHLIST_PATH = Path(__file__).parent / "watchlist.json"


def load_watchlist() -> dict:
    if not WATCHLIST_PATH.exists():
        return {"tickers": [], "alerts": {}}
    return json.loads(WATCHLIST_PATH.read_text())


def scan_watchlist() -> list[dict]:
    """Check watchlist stocks for alert conditions."""
    from news import get_news
    config = load_watchlist()
    tickers = config.get("tickers", [])
    if not tickers:
        return []

    alerts_cfg = config.get("alerts", {})
    drop_thresh = alerts_cfg.get("price_drop_pct", -5)
    surge_thresh = alerts_cfg.get("price_surge_pct", 5)
    vol_thresh = alerts_cfg.get("volume_spike_threshold", 2.0)
    earnings_days = alerts_cfg.get("earnings_days_ahead", 7)

    stock_data = get_batch_stock_data(tickers)
    alerts = []

    for ticker in tickers:
        data = stock_data.get(ticker)
        if not data:
            continue

        triggered = []
        chg5 = data["change_5d_pct"]
        if chg5 <= drop_thresh:
            triggered.append(f"🔴 5d drop {chg5:.1f}%")
        elif chg5 >= surge_thresh:
            triggered.append(f"🟢 5d surge +{chg5:.1f}%")

        if data["volume_spike"] >= vol_thresh:
            triggered.append(f"📊 Volume spike {data['volume_spike']:.1f}x")

        events = get_upcoming_events(ticker)
        now = datetime.now()
        for ev in events:
            try:
                ev_date = datetime.strptime(ev["date"], "%Y-%m-%d")
                if 0 <= (ev_date - now).days <= earnings_days:
                    triggered.append(f"📅 {ev['event']} on {ev['date']}")
            except (ValueError, KeyError):
                pass

        if triggered:
            alerts.append({
                "ticker": ticker,
                "name": data["name"],
                "price": data["price"],
                "change_5d_pct": chg5,
                "change_30d_pct": data["change_30d_pct"],
                "volume_spike": data["volume_spike"],
                "alerts": triggered,
                "events": events,
                "news": get_news(ticker, 3),
            })

    return alerts
