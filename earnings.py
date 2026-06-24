"""Earnings calendar — upcoming/recent earnings dates with EPS surprise detection."""
import yfinance as yf
from datetime import datetime, timedelta


def get_earnings(ticker: str, days_ahead: int = 14, days_back: int = 7) -> dict:
    """Get upcoming and recent earnings for a ticker with EPS data."""
    try:
        t = yf.Ticker(ticker)
        cal = t.calendar
        earnings_dates = t.earnings_dates
        result = {"upcoming": None, "recent": [], "surprise": None}

        # Upcoming earnings from calendar
        if cal is not None and isinstance(cal, dict):
            ed = cal.get("Earnings Date")
            if ed:
                result["upcoming"] = {
                    "date": str(ed[0])[:10] if isinstance(ed, list) else str(ed)[:10],
                    "eps_estimate": cal.get("EPS Estimate"),
                    "revenue_estimate": cal.get("Revenue Estimate"),
                }

        # Recent earnings with surprise from earnings_dates
        if earnings_dates is not None and not earnings_dates.empty:
            now = datetime.now()
            cutoff_back = now - timedelta(days=days_back)
            cutoff_ahead = now + timedelta(days=days_ahead)

            for idx, row in earnings_dates.iterrows():
                date = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
                if hasattr(date, 'replace') and date.tzinfo:
                    date = date.replace(tzinfo=None)

                eps_est = row.get("EPS Estimate")
                eps_act = row.get("Reported EPS")
                surprise_pct = row.get("Surprise(%)")

                entry = {
                    "date": date.strftime("%Y-%m-%d"),
                    "eps_estimate": float(eps_est) if eps_est and eps_est == eps_est else None,
                    "eps_actual": float(eps_act) if eps_act and eps_act == eps_act else None,
                    "surprise_pct": float(surprise_pct) if surprise_pct and surprise_pct == surprise_pct else None,
                }

                if cutoff_back <= date <= now and entry["eps_actual"] is not None:
                    result["recent"].append(entry)
                    if entry["surprise_pct"] is not None:
                        result["surprise"] = entry
                elif now < date <= cutoff_ahead and result["upcoming"] is None:
                    result["upcoming"] = entry

        return result
    except Exception:
        return {"upcoming": None, "recent": [], "surprise": None}


def get_batch_earnings(tickers: list[str]) -> dict:
    """Get earnings data for multiple tickers."""
    return {t: get_earnings(t) for t in tickers}
