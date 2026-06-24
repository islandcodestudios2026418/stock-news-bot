"""US market hours detection — know when data is fresh vs stale."""
from datetime import datetime, timezone, timedelta

ET = timezone(timedelta(hours=-4))  # Eastern Time (simplified, doesn't handle DST perfectly)

# US market holidays 2026 (NYSE closed)
HOLIDAYS_2026 = {
    "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07",
    "2026-11-26", "2026-12-25",
}


def get_market_status() -> dict:
    """Get current US market session status."""
    now_et = datetime.now(ET)
    date_str = now_et.strftime("%Y-%m-%d")
    weekday = now_et.weekday()  # 0=Mon, 6=Sun
    hour = now_et.hour
    minute = now_et.minute
    time_val = hour * 60 + minute

    if weekday >= 5 or date_str in HOLIDAYS_2026:
        session = "closed"
        label = "Weekend" if weekday >= 5 else "Holiday"
    elif time_val < 4 * 60:  # Before 4:00 AM
        session = "closed"
        label = "Overnight"
    elif time_val < 9 * 60 + 30:  # 4:00 AM - 9:30 AM
        session = "pre_market"
        label = "Pre-Market"
    elif time_val < 16 * 60:  # 9:30 AM - 4:00 PM
        session = "open"
        label = "Market Open"
    elif time_val < 20 * 60:  # 4:00 PM - 8:00 PM
        session = "after_hours"
        label = "After-Hours"
    else:
        session = "closed"
        label = "Overnight"

    return {
        "session": session,
        "label": label,
        "et_time": now_et.strftime("%H:%M ET"),
        "is_trading": session == "open",
        "data_fresh": session in ("open", "after_hours"),
    }
