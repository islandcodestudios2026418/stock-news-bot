"""Alert deduplication — skip already-sent alerts using a local history file."""
import json, hashlib
from pathlib import Path
from datetime import datetime, timedelta

HISTORY_PATH = Path(__file__).parent / "alert_history.json"
MAX_AGE_DAYS = 30  # purge entries older than this


def _load() -> dict:
    if HISTORY_PATH.exists():
        return json.loads(HISTORY_PATH.read_text())
    return {}


def _save(history: dict):
    HISTORY_PATH.write_text(json.dumps(history, indent=2))


def _alert_key(ticker: str, alert_text: str) -> str:
    """Deterministic key for an alert (ticker + normalized text)."""
    raw = f"{ticker}:{alert_text}"
    return hashlib.md5(raw.encode()).hexdigest()


def deduplicate(alerts: list[dict]) -> list[dict]:
    """Filter alerts list, removing already-sent items. Updates history."""
    history = _load()
    cutoff = (datetime.now() - timedelta(days=MAX_AGE_DAYS)).isoformat()

    # Purge old entries
    history = {k: v for k, v in history.items() if v > cutoff}

    new_alerts = []
    for alert in alerts:
        ticker = alert["ticker"]
        unseen = [a for a in alert["alerts"] if _alert_key(ticker, a) not in history]
        if unseen:
            # Mark as seen
            for a in unseen:
                history[_alert_key(ticker, a)] = datetime.now().isoformat()
            new_alerts.append({**alert, "alerts": unseen})

    _save(history)
    return new_alerts
