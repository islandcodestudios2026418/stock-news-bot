"""Sector rotation detection — money flow between sectors via ETF performance."""
import yfinance as yf
from datetime import datetime

SECTOR_ETFS = {
    "Technology": "XLK", "Financials": "XLF", "Energy": "XLE",
    "Healthcare": "XLV", "Consumer Discretionary": "XLY",
    "Consumer Staples": "XLP", "Industrials": "XLI",
    "Materials": "XLB", "Utilities": "XLU", "Real Estate": "XLRE",
    "Communications": "XLC",
}


def get_sector_rotation(period: str = "5d") -> list[dict]:
    """Rank sectors by recent performance to detect rotation."""
    results = []
    tickers_str = " ".join(SECTOR_ETFS.values())
    try:
        data = yf.download(tickers_str, period=period, progress=False, group_by="ticker")
        for sector, etf in SECTOR_ETFS.items():
            try:
                col = data[etf]["Close"].dropna()
                if len(col) < 2:
                    continue
                chg = (col.iloc[-1] / col.iloc[0] - 1) * 100
                results.append({"sector": sector, "etf": etf, "change_pct": round(float(chg), 2)})
            except (KeyError, IndexError):
                continue
    except Exception:
        pass
    results.sort(key=lambda x: x["change_pct"], reverse=True)
    # Tag rotation signals
    if len(results) >= 3:
        for r in results[:2]:
            r["signal"] = "inflow"
        for r in results[-2:]:
            r["signal"] = "outflow"
    return results
