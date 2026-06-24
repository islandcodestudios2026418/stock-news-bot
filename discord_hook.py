"""Discord webhook delivery — send stock alerts as embeds with multi-channel support."""
import os, requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")
CRITICAL_WEBHOOK_URL = os.environ.get("DISCORD_CRITICAL_WEBHOOK_URL", "")

# Urgency → color mapping
URGENCY_COLORS = {
    "🔴 CRITICAL": 0xFF0000,
    "🟠 HIGH": 0xFF8C00,
    "🟡 MEDIUM": 0xFFD700,
    "🟢 LOW": 0x00FF00,
}


def _build_embed(alert: dict) -> dict:
    """Build a single Discord embed from an alert entry."""
    ticker = alert["ticker"]
    name = alert.get("name", ticker)
    price = alert.get("price", 0)
    chg5 = alert.get("change_5d_pct", 0)
    urgency = alert.get("urgency", "🟢 LOW")
    color = URGENCY_COLORS.get(urgency, 0x00FF00 if chg5 >= 0 else 0xFF0000)

    desc = "\n".join(alert["alerts"])
    news = alert.get("news", [])
    if news:
        desc += "\n\n**Headlines:**\n" + "\n".join(f"• {n['title']}" for n in news[:3])

    return {
        "title": f"{urgency} {ticker} — ${price:.2f} ({chg5:+.1f}% 5d)",
        "description": desc[:4096],
        "color": color,
        "footer": {"text": name},
    }


def _send_to_webhook(url: str, embeds: list[dict], content: str) -> bool:
    """Send embeds to a webhook URL."""
    payload = {"content": content, "embeds": embeds[:10]}
    r = requests.post(url, json=payload, timeout=10)
    return r.status_code == 204


def send_alerts(alerts: list[dict], webhook_url: str = None) -> bool:
    """Send scored alerts to Discord. Critical alerts go to separate channel if configured."""
    url = webhook_url or WEBHOOK_URL
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL not set")
    if not alerts:
        return False

    # Split critical vs normal
    critical = [a for a in alerts if a.get("urgency") == "🔴 CRITICAL"]
    normal = [a for a in alerts if a.get("urgency") != "🔴 CRITICAL"]

    sent = False

    # Send critical to dedicated channel if available
    if critical and CRITICAL_WEBHOOK_URL:
        embeds = [_build_embed(a) for a in critical[:10]]
        sent = _send_to_webhook(CRITICAL_WEBHOOK_URL, embeds,
                               f"🚨 **CRITICAL ALERTS** ({len(critical)} tickers)")

    # Send all to main channel
    embeds = [_build_embed(a) for a in alerts[:10]]
    result = _send_to_webhook(url, embeds, f"📡 **Stock Alerts** ({len(alerts)} tickers)")
    return sent or result
