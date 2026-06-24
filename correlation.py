"""Correlation alerts — detect when watchlist stocks move together unusually."""
import yfinance as yf
import json
from pathlib import Path


def get_correlation_alert(tickers: list[str] = None, threshold: float = 0.8) -> dict:
    """Detect unusual co-movement. If most stocks drop/surge together, flag systemic risk."""
    if not tickers:
        wl = Path(__file__).parent / "watchlist.json"
        tickers = json.loads(wl.read_text()).get("tickers", [])
    if len(tickers) < 3:
        return {"alert": False}

    try:
        data = yf.download(" ".join(tickers), period="5d", progress=False, group_by="ticker")
        changes = {}
        for t in tickers:
            try:
                col = data[t]["Close"].dropna()
                if len(col) >= 2:
                    changes[t] = (col.iloc[-1] / col.iloc[0] - 1) * 100
            except (KeyError, IndexError):
                continue

        if len(changes) < 3:
            return {"alert": False}

        vals = list(changes.values())
        dropping = [t for t, v in changes.items() if v < -3]
        surging = [t for t, v in changes.items() if v > 3]

        # Systemic signal: >60% of stocks moving same direction >3%
        drop_ratio = len(dropping) / len(changes)
        surge_ratio = len(surging) / len(changes)

        alert = False
        signal = ""
        if drop_ratio >= 0.6:
            alert = True
            signal = f"systemic_selloff ({len(dropping)}/{len(changes)} stocks down >3%)"
        elif surge_ratio >= 0.6:
            alert = True
            signal = f"broad_rally ({len(surging)}/{len(changes)} stocks up >3%)"

        avg_change = sum(vals) / len(vals)
        return {
            "alert": alert,
            "signal": signal,
            "avg_change_5d": round(avg_change, 2),
            "changes": {t: round(v, 2) for t, v in changes.items()},
            "dropping": dropping,
            "surging": surging,
        }
    except Exception:
        return {"alert": False}
