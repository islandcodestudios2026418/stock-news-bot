"""Fetch upcoming corporate events (earnings, dividends)."""
import yfinance as yf


def get_upcoming_events(ticker: str) -> list[dict]:
    """Get upcoming events for a ticker."""
    events = []
    try:
        stock = yf.Ticker(ticker)
        cal = stock.calendar
        if not cal or not isinstance(cal, dict):
            return events
        
        # Only keep actual date events
        date_keys = {"Earnings Date", "Ex-Dividend Date", "Dividend Date"}
        for key, val in cal.items():
            if key not in date_keys or val is None:
                continue
            if isinstance(val, list):
                events.append({"event": key, "date": str(val[0])})
            else:
                events.append({"event": key, "date": str(val)})
    except Exception:
        pass
    return events
