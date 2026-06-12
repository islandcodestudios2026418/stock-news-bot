"""Detect divergence between trending hype and stock price movement."""


def detect_divergence(mapped_companies: list[dict], stock_data: dict) -> list[dict]:
    """Find stocks where hype is high but price hasn't reacted.
    
    Signal criteria:
    - Trend score >= 3 (sustained presence in trends)
    - 5-day price change < 3% (hasn't moved much)
    - Fundamentals OK (revenue growth > 0 OR profit margin > 0)
    
    Returns list of signals sorted by strength.
    """
    signals = []
    
    for company in mapped_companies:
        for ticker in company.get("tickers", []):
            data = stock_data.get(ticker)
            if not data:
                continue
            
            trend_score = company.get("trend_score", 0)
            price_change = abs(data["change_5d_pct"])
            
            # Core divergence: high hype + low price movement
            if trend_score < 3 or price_change > 3:
                continue
            
            # Basic fundamentals check (not a dying company)
            rev_growth = data.get("revenue_growth") or 0
            margin = data.get("profit_margin") or 0
            if rev_growth < -0.1 and margin < 0:
                continue
            
            # Signal strength: higher trend + lower price move = stronger
            strength = trend_score / max(price_change, 0.1)
            
            signals.append({
                "ticker": ticker,
                "name": data["name"],
                "keyword": company["keyword"],
                "connection": company["connection"],
                "trend_score": trend_score,
                "price_change_5d": data["change_5d_pct"],
                "price_change_30d": data["change_30d_pct"],
                "volume_spike": data["volume_spike"],
                "revenue_growth": rev_growth,
                "sector": data.get("sector"),
                "strength": round(strength, 2),
                "price": data["price"],
            })
    
    return sorted(signals, key=lambda x: -x["strength"])
