"""Fetch stock price and fundamentals from Yahoo Finance."""
import yfinance as yf


def get_stock_data(ticker: str, period="1mo") -> dict | None:
    """Get price movement and key fundamentals for a ticker."""
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        if hist.empty:
            return None
        
        info = stock.info or {}
        current_price = float(hist['Close'].iloc[-1])
        price_5d_ago = float(hist['Close'].iloc[-5]) if len(hist) >= 5 else current_price
        price_30d_ago = float(hist['Close'].iloc[0]) if len(hist) >= 20 else price_5d_ago
        
        vol_recent = float(hist['Volume'].iloc[-5:].mean()) if len(hist) >= 5 else float(hist['Volume'].mean())
        vol_avg = float(hist['Volume'].mean())
        volume_spike = vol_recent / vol_avg if vol_avg > 0 else 1.0
        
        return {
            "ticker": ticker,
            "price": round(current_price, 2),
            "change_5d_pct": round((current_price - price_5d_ago) / price_5d_ago * 100, 2) if price_5d_ago else 0,
            "change_30d_pct": round((current_price - price_30d_ago) / price_30d_ago * 100, 2) if price_30d_ago else 0,
            "volume_spike": round(float(volume_spike), 2),
            "market_cap": info.get("marketCap"),
            "revenue_growth": info.get("revenueGrowth"),
            "profit_margin": info.get("profitMargins"),
            "sector": info.get("sector"),
            "name": info.get("shortName", ticker),
        }
    except Exception as e:
        print(f"  [price] {ticker} failed: {e}")
        return None


def get_batch_stock_data(tickers: list[str]) -> dict:
    """Fetch stock data for multiple tickers."""
    results = {}
    for t in set(tickers):
        data = get_stock_data(t)
        if data:
            results[t] = data
    return results
