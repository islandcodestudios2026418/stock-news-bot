"""Technical indicators — RSI, MACD, moving average crossovers. No extra deps (pure yfinance)."""
import yfinance as yf


def _rsi(closes: list[float], period: int = 14) -> float | None:
    """Calculate RSI from close prices."""
    if len(closes) < period + 1:
        return None
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas[-period:]]
    losses = [-d if d < 0 else 0 for d in deltas[-period:]]
    avg_gain = sum(gains) / period
    avg_loss = sum(losses) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 1)


def _ema(data: list[float], period: int) -> list[float]:
    """Exponential moving average."""
    if len(data) < period:
        return []
    k = 2 / (period + 1)
    ema = [sum(data[:period]) / period]
    for price in data[period:]:
        ema.append(price * k + ema[-1] * (1 - k))
    return ema


def _macd(closes: list[float]) -> dict | None:
    """MACD (12, 26, 9) — returns line, signal, histogram."""
    if len(closes) < 35:
        return None
    ema12 = _ema(closes, 12)
    ema26 = _ema(closes, 26)
    # Align: ema12 starts at index 12, ema26 at index 26 → offset = 14
    offset = 26 - 12
    macd_line = [ema12[i + offset] - ema26[i] for i in range(len(ema26))]
    if len(macd_line) < 9:
        return None
    signal = _ema(macd_line, 9)
    hist = macd_line[-1] - signal[-1] if signal else 0
    return {"macd": round(macd_line[-1], 3), "signal": round(signal[-1], 3), "histogram": round(hist, 3)}


def get_technicals(ticker: str) -> dict:
    """Get RSI, MACD, and MA crossover signals for a ticker."""
    try:
        hist = yf.Ticker(ticker).history(period="6mo")
        if hist.empty or len(hist) < 50:
            return {}
        closes = hist["Close"].tolist()

        rsi = _rsi(closes)
        macd = _macd(closes)
        ma50 = sum(closes[-50:]) / 50
        ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
        price = closes[-1]

        signals = []
        if rsi is not None:
            if rsi >= 70:
                signals.append("overbought")
            elif rsi <= 30:
                signals.append("oversold")
        if macd and macd["histogram"] > 0 and macd["macd"] > macd["signal"]:
            signals.append("macd_bullish")
        elif macd and macd["histogram"] < 0:
            signals.append("macd_bearish")
        if ma200:
            if price > ma50 > ma200:
                signals.append("above_both_ma")
            elif price < ma50 < ma200:
                signals.append("below_both_ma")
            # Golden/death cross: check if MA50 just crossed MA200
            prev_closes = closes[-51:-1]
            prev_ma50 = sum(prev_closes[-50:]) / 50
            prev_ma200 = sum(closes[-201:-1]) / 200 if len(closes) >= 201 else None
            if prev_ma200:
                if prev_ma50 < prev_ma200 and ma50 > ma200:
                    signals.append("golden_cross")
                elif prev_ma50 > prev_ma200 and ma50 < ma200:
                    signals.append("death_cross")

        return {
            "rsi": rsi, "macd": macd, "ma50": round(ma50, 2),
            "ma200": round(ma200, 2) if ma200 else None,
            "price": round(price, 2), "signals": signals,
        }
    except Exception:
        return {}


def get_batch_technicals(tickers: list[str]) -> dict:
    """Get technical indicators for multiple tickers."""
    return {t: get_technicals(t) for t in tickers}
