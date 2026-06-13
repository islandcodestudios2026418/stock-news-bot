"""Detect divergence between trending hype and stock price movement."""
from mapper import is_negative


def detect_divergence(mapped_companies: list[dict], stock_data: dict) -> list[dict]:
    """Find stocks where hype is high but price hasn't reacted.
    
    RSS scores: approx_traffic >500K=high(3), >100K=medium(2), else 1.
    Being on Google Trends at all = minimum score 1, threshold >= 1.
    """
    signals = []

    for company in mapped_companies:
        if is_negative(company["keyword"]):
            continue

        # Normalize trend_score from RSS traffic
        raw_score = company.get("score", 1)
        if raw_score >= 5:
            trend_score = 3  # >500K traffic
        elif raw_score >= 1:
            trend_score = 2  # >100K traffic
        else:
            trend_score = 1  # on trends = noteworthy

        for ticker in company.get("tickers", []):
            data = stock_data.get(ticker)
            if not data:
                continue

            price_change = abs(data["change_5d_pct"])
            if price_change > 3:
                continue

            # Basic fundamentals check
            rev_growth = data.get("revenue_growth") or 0
            margin = data.get("profit_margin") or 0
            if rev_growth < -0.1 and margin < 0:
                continue

            strength = trend_score / max(price_change, 0.1)

            signals.append({
                "ticker": ticker,
                "name": data["name"],
                "keyword": company["keyword"],
                "connection_type": company.get("connection_type", "sector"),
                "sector": company.get("sector"),
                "trend_score": trend_score,
                "price_change_5d": data["change_5d_pct"],
                "price_change_30d": data["change_30d_pct"],
                "volume_spike": data["volume_spike"],
                "revenue_growth": rev_growth,
                "strength": round(strength, 2),
                "price": data["price"],
            })

    return sorted(signals, key=lambda x: -x["strength"])
