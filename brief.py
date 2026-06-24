"""Smart market brief — generates 3-5 actionable bullet points from scan data."""


def generate_brief(tickers: dict, sentiment: dict = None, correlation: dict = None,
                   macro: list = None, rotation: list = None) -> list[str]:
    """Return list of actionable insight strings from current market data."""
    points = []

    # 1. Systemic risk warning
    if correlation and correlation.get("alert"):
        avg = correlation.get("avg_change_5d", 0)
        sig = correlation["signal"]
        if "selloff" in sig:
            points.append(f"⚠️ Systemic selloff detected — avg {avg:+.1f}% across watchlist. Consider reducing exposure or hedging.")
        else:
            points.append(f"🚀 Broad rally underway — avg {avg:+.1f}%. Momentum favors longs but watch for overextension.")

    # 2. Sentiment extremes
    if sentiment and sentiment.get("score") is not None:
        score = sentiment["score"]
        vix = sentiment.get("vix", 0)
        if score >= 80:
            points.append(f"🔥 Extreme greed (VIX {vix}) — historically poor time to add risk. Tighten stops.")
        elif score <= 20:
            points.append(f"💎 Extreme fear (VIX {vix}) — contrarian buy zone. Quality names may be oversold.")

    # 3. Individual ticker action items
    oversold = [(t, d) for t, d in tickers.items() if d.get("rsi") and d["rsi"] < 30]
    overbought = [(t, d) for t, d in tickers.items() if d.get("rsi") and d["rsi"] > 70]
    big_drops = [(t, d) for t, d in tickers.items() if d.get("change_5d_pct", 0) < -7]
    near_support = [(t, d) for t, d in tickers.items() if d.get("support") and d.get("price") and d["support"] > 0 and abs((d["price"] - d["support"]) / d["price"] * 100) < 2]
    earnings_soon = [(t, d) for t, d in tickers.items() if d.get("earnings_date")]

    if oversold:
        names = ", ".join(t for t, _ in oversold[:3])
        points.append(f"📉 Oversold: {names} — RSI < 30. Watch for reversal signals before buying dip.")

    if overbought:
        names = ", ".join(t for t, _ in overbought[:3])
        points.append(f"📈 Overbought: {names} — RSI > 70. Consider taking partial profits.")

    if big_drops and not oversold:
        names = ", ".join(f"{t} ({d['change_5d_pct']:+.1f}%)" for t, d in big_drops[:3])
        points.append(f"🔴 Sharp drops: {names}. Check for catalysts before catching knives.")

    if near_support:
        names = ", ".join(f"{t} (${d.get('support',0):.0f})" for t, d in near_support[:2])
        points.append(f"🎯 Near support: {names}. Bounce likely if level holds; stop below.")

    if earnings_soon:
        names = ", ".join(f"{t} ({d['earnings_date']})" for t, d in earnings_soon[:3])
        points.append(f"💰 Earnings ahead: {names}. Size positions accordingly; expect volatility.")

    # 4. Sector rotation insight
    if rotation:
        inflows = [r for r in rotation if r.get("signal") == "inflow"]
        outflows = [r for r in rotation if r.get("signal") == "outflow"]
        if inflows and outflows:
            into = inflows[0]["sector"]
            out_of = outflows[0]["sector"]
            points.append(f"🔄 Money rotating: {out_of} → {into}. Favor {into} names near-term.")

    # 5. Macro awareness
    if macro:
        high_impact = [e for e in macro if e.get("impact") == "high"]
        if high_impact:
            evt = high_impact[0]
            points.append(f"🏛️ High-impact event: {evt['event']} on {evt['date']}. Reduce size before if uncertain.")

    # Cap at 5 most important
    return points[:5] if points else ["✅ Markets quiet — no immediate action needed. Stay patient."]
