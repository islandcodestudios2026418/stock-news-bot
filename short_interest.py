"""Short interest tracking — squeeze potential detection."""
import yfinance as yf


def get_short_interest(ticker: str) -> dict | None:
    """Get short interest metrics for a ticker."""
    try:
        info = yf.Ticker(ticker).info
        short_pct = info.get("shortPercentOfFloat")
        short_ratio = info.get("shortRatio")  # days to cover
        if short_pct is None and short_ratio is None:
            return None
        return {
            "short_pct_float": round(short_pct * 100, 1) if short_pct else None,
            "days_to_cover": round(short_ratio, 1) if short_ratio else None,
            "squeeze_signal": (short_pct or 0) > 0.15 or (short_ratio or 0) > 5,
        }
    except Exception:
        return None


def get_batch_short_interest(tickers: list[str]) -> dict:
    """Get short interest for multiple tickers."""
    return {t: get_short_interest(t) for t in tickers}
