"""Unusual options activity detection — spots high volume/OI ratios signaling institutional moves."""
import yfinance as yf
from datetime import datetime


def get_options_flow(ticker: str, vol_oi_threshold: float = 3.0) -> list[dict]:
    """Detect unusual options activity for a ticker.
    
    Flags contracts where volume/openInterest > threshold (institutional signal).
    """
    try:
        t = yf.Ticker(ticker)
        expirations = t.options
        if not expirations:
            return []

        # Check nearest 2 expirations only (performance)
        unusual = []
        for exp in expirations[:2]:
            chain = t.option_chain(exp)
            for side, opts in [("call", chain.calls), ("put", chain.puts)]:
                if opts.empty:
                    continue
                for _, row in opts.iterrows():
                    vol = row.get("volume", 0) or 0
                    oi = row.get("openInterest", 0) or 0
                    if oi > 100 and vol > 500 and vol / oi > vol_oi_threshold:
                        unusual.append({
                            "expiration": exp,
                            "type": side,
                            "strike": float(row["strike"]),
                            "volume": int(vol),
                            "open_interest": int(oi),
                            "vol_oi_ratio": round(vol / oi, 1),
                            "implied_vol": round(float(row.get("impliedVolatility", 0) or 0) * 100, 1),
                        })
        # Sort by vol/OI ratio descending, return top 5
        unusual.sort(key=lambda x: x["vol_oi_ratio"], reverse=True)
        return unusual[:5]
    except Exception:
        return []


def get_batch_options_flow(tickers: list[str]) -> dict:
    """Get unusual options activity for multiple tickers."""
    return {t: get_options_flow(t) for t in tickers}
