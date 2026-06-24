"""Macro economic calendar — upcoming market-moving events."""
import requests
from datetime import datetime, timedelta

# Key recurring events (approximate schedules)
# These are updated periodically; this is a best-effort approach using public APIs
FRED_API_BASE = "https://api.stlouisfed.org/fred"


def get_macro_events(days_ahead: int = 14) -> list[dict]:
    """Fetch upcoming macro events from multiple sources."""
    events = []
    events.extend(_fed_meetings(days_ahead))
    events.extend(_treasury_auctions(days_ahead))
    events.sort(key=lambda x: x["date"])
    return events


def _fed_meetings(days_ahead: int) -> list[dict]:
    """Get FOMC meeting dates from the Fed's known schedule."""
    # 2025-2026 FOMC scheduled meetings (announced annually)
    fomc_dates = [
        "2026-01-28", "2026-03-18", "2026-05-06", "2026-06-17",
        "2026-07-29", "2026-09-16", "2026-11-04", "2026-12-16",
    ]
    now = datetime.now()
    cutoff = now + timedelta(days=days_ahead)
    results = []
    for d in fomc_dates:
        dt = datetime.strptime(d, "%Y-%m-%d")
        if now <= dt <= cutoff:
            results.append({"date": d, "event": "FOMC Meeting", "impact": "high",
                           "description": "Federal Reserve interest rate decision"})
    return results


def _treasury_auctions(days_ahead: int) -> list[dict]:
    """Fetch upcoming Treasury auction dates from TreasuryDirect."""
    try:
        url = "https://www.treasurydirect.gov/TA_WS/securities/upcoming?format=json"
        r = requests.get(url, timeout=10)
        if r.status_code != 200:
            return []
        data = r.json()
        now = datetime.now()
        cutoff = now + timedelta(days=days_ahead)
        results = []
        seen = set()
        for item in data[:20]:
            adate = item.get("auctionDate", "")[:10]
            sec_type = item.get("securityType", "")
            key = f"{adate}_{sec_type}"
            if key in seen:
                continue
            seen.add(key)
            try:
                dt = datetime.strptime(adate, "%Y-%m-%d")
                if now <= dt <= cutoff:
                    results.append({"date": adate, "event": f"Treasury Auction ({sec_type})",
                                   "impact": "medium", "description": f"{sec_type} auction"})
            except ValueError:
                continue
        return results[:5]
    except Exception:
        return []


def get_macro_summary() -> dict:
    """Quick summary of upcoming macro events."""
    events = get_macro_events(days_ahead=7)
    high = [e for e in events if e["impact"] == "high"]
    return {"events_7d": events, "high_impact_count": len(high)}
