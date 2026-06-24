"""Analyst rating changes tracker via yfinance."""
import yfinance as yf
from datetime import datetime, timedelta


def get_recent_ratings(ticker: str, days: int = 14) -> list[dict]:
    """Fetch recent analyst upgrades/downgrades for a ticker."""
    try:
        t = yf.Ticker(ticker)
        recs = t.upgrades_downgrades
        if recs is None or recs.empty:
            return []
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        for idx, row in recs.iterrows():
            date = idx.to_pydatetime() if hasattr(idx, 'to_pydatetime') else idx
            if hasattr(date, 'replace') and date.tzinfo:
                date = date.replace(tzinfo=None)
            if date < cutoff:
                continue
            results.append({
                "date": date.strftime("%Y-%m-%d"),
                "firm": row.get("Firm", ""),
                "to_grade": row.get("ToGrade", ""),
                "from_grade": row.get("FromGrade", ""),
                "action": row.get("Action", ""),
            })
        return results[:5]
    except Exception:
        return []


def get_batch_ratings(tickers: list[str], days: int = 14) -> dict:
    """Fetch recent ratings for multiple tickers."""
    return {t: get_recent_ratings(t, days=days) for t in tickers}
