"""Market sentiment — Fear/Greed indicator via VIX and market breadth."""
import yfinance as yf


def get_sentiment() -> dict:
    """Calculate a market sentiment score (0=extreme fear, 100=extreme greed).
    
    Uses VIX level as primary indicator:
    - VIX < 12: Extreme greed
    - VIX 12-18: Greed
    - VIX 18-25: Neutral
    - VIX 25-35: Fear
    - VIX > 35: Extreme fear
    """
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist.empty:
            return {"score": 50, "label": "Neutral", "vix": None}

        vix_val = float(hist["Close"].iloc[-1])
        vix_5d_ago = float(hist["Close"].iloc[0]) if len(hist) >= 2 else vix_val
        vix_change = vix_val - vix_5d_ago

        # Convert VIX to fear/greed score (inverse relationship)
        if vix_val < 12:
            score = 90
        elif vix_val < 15:
            score = 75
        elif vix_val < 18:
            score = 60
        elif vix_val < 22:
            score = 50
        elif vix_val < 25:
            score = 40
        elif vix_val < 30:
            score = 25
        elif vix_val < 35:
            score = 15
        else:
            score = 5

        # Adjust for VIX direction (rising VIX = more fear)
        if vix_change > 3:
            score = max(0, score - 10)
        elif vix_change < -3:
            score = min(100, score + 10)

        # Label
        if score >= 75:
            label = "Extreme Greed"
        elif score >= 55:
            label = "Greed"
        elif score >= 45:
            label = "Neutral"
        elif score >= 25:
            label = "Fear"
        else:
            label = "Extreme Fear"

        return {
            "score": score, "label": label,
            "vix": round(vix_val, 1), "vix_change_5d": round(vix_change, 1),
        }
    except Exception:
        return {"score": 50, "label": "Neutral", "vix": None}
