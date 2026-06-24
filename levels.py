"""Support/resistance level detection from price history."""
import yfinance as yf


def get_levels(ticker: str, period: str = "3mo") -> dict:
    """Detect support/resistance levels from recent price action."""
    try:
        hist = yf.Ticker(ticker).history(period=period)
        if hist.empty or len(hist) < 20:
            return {}

        closes = hist["Close"].tolist()
        highs = hist["High"].tolist()
        lows = hist["Low"].tolist()
        price = closes[-1]

        # Key levels: recent swing highs/lows
        resistance_candidates = []
        support_candidates = []

        for i in range(2, len(highs) - 2):
            # Local high (resistance)
            if highs[i] > highs[i-1] and highs[i] > highs[i-2] and highs[i] > highs[i+1] and highs[i] > highs[i+2]:
                resistance_candidates.append(highs[i])
            # Local low (support)
            if lows[i] < lows[i-1] and lows[i] < lows[i-2] and lows[i] < lows[i+1] and lows[i] < lows[i+2]:
                support_candidates.append(lows[i])

        # Filter: only levels above/below current price
        resistance = sorted([r for r in resistance_candidates if r > price])[:3]
        support = sorted([s for s in support_candidates if s < price], reverse=True)[:3]

        # Distance to nearest levels
        nearest_resistance = resistance[0] if resistance else None
        nearest_support = support[0] if support else None

        return {
            "price": round(price, 2),
            "resistance": [round(r, 2) for r in resistance],
            "support": [round(s, 2) for s in support],
            "nearest_resistance": round(nearest_resistance, 2) if nearest_resistance else None,
            "nearest_support": round(nearest_support, 2) if nearest_support else None,
            "resistance_pct": round((nearest_resistance / price - 1) * 100, 1) if nearest_resistance else None,
            "support_pct": round((nearest_support / price - 1) * 100, 1) if nearest_support else None,
        }
    except Exception:
        return {}


def get_batch_levels(tickers: list[str]) -> dict:
    """Get support/resistance for multiple tickers."""
    return {t: get_levels(t) for t in tickers}
