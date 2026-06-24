"""Alert priority scoring — ranks alerts by actionability and urgency."""

# Score weights by alert type (higher = more important)
SCORES = {
    "death_cross": 95, "golden_cross": 90,
    "oversold": 85, "overbought": 80,
    "squeeze": 85,
    "eps_surprise": 80,
    "insider_buy": 75, "insider_sell": 70,
    "drop": 70, "surge": 65,
    "volume_spike": 60,
    "options_flow": 55,
    "rating": 50,
    "earnings_upcoming": 45,
    "filing": 30,
    "event": 20,
    "macro": 15,
}

URGENCY_LEVELS = [(80, "🔴 CRITICAL"), (60, "🟠 HIGH"), (40, "🟡 MEDIUM"), (0, "🟢 LOW")]


def _classify_alert(text: str) -> str:
    """Map alert text to a score category."""
    t = text.lower()
    if "death cross" in t: return "death_cross"
    if "golden cross" in t: return "golden_cross"
    if "oversold" in t: return "oversold"
    if "overbought" in t: return "overbought"
    if "short" in t and ("squeeze" in t or "high" in t): return "squeeze"
    if "eps surprise" in t: return "eps_surprise"
    if "insider buy" in t: return "insider_buy"
    if "insider sell" in t: return "insider_sell"
    if "drop" in t: return "drop"
    if "surge" in t: return "surge"
    if "volume spike" in t: return "volume_spike"
    if "unusual" in t and "flow" in t: return "options_flow"
    if any(x in t for x in ["upgrade", "downgrade", "rating", "⭐"]): return "rating"
    if "earnings on" in t: return "earnings_upcoming"
    if "sec" in t or "filed" in t: return "filing"
    if "dividend" in t or "📅" in t: return "event"
    return "event"


def score_alert(text: str) -> int:
    """Score a single alert string."""
    return SCORES.get(_classify_alert(text), 10)


def score_ticker_alerts(alert_entry: dict) -> dict:
    """Add score and urgency to a ticker's alert entry."""
    alerts = alert_entry.get("alerts", [])
    scores = [score_alert(a) for a in alerts]
    max_score = max(scores) if scores else 0
    total_score = sum(scores)

    urgency = "🟢 LOW"
    for threshold, label in URGENCY_LEVELS:
        if max_score >= threshold:
            urgency = label
            break

    return {**alert_entry, "max_score": max_score, "total_score": total_score, "urgency": urgency}


def rank_alerts(alerts: list[dict]) -> list[dict]:
    """Score and sort alerts by priority (highest first)."""
    scored = [score_ticker_alerts(a) for a in alerts]
    scored.sort(key=lambda x: x["total_score"], reverse=True)
    return scored
