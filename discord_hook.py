"""Discord webhook delivery — send stock alerts as embeds."""
import os, requests

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")


def send_alerts(alerts: list[dict], webhook_url: str = None) -> bool:
    """Send deduplicated alerts to Discord webhook. Returns True if sent."""
    url = webhook_url or WEBHOOK_URL
    if not url:
        raise ValueError("DISCORD_WEBHOOK_URL not set")
    if not alerts:
        return False

    embeds = []
    for alert in alerts[:10]:  # Discord limit: 10 embeds per message
        ticker = alert["ticker"]
        name = alert.get("name", ticker)
        price = alert.get("price", 0)
        chg5 = alert.get("change_5d_pct", 0)
        color = 0x00FF00 if chg5 >= 0 else 0xFF0000

        desc = "\n".join(alert["alerts"])
        news = alert.get("news", [])
        if news:
            desc += "\n\n**Headlines:**\n" + "\n".join(f"• {n['title']}" for n in news[:3])

        embeds.append({
            "title": f"{ticker} — ${price:.2f} ({chg5:+.1f}% 5d)",
            "description": desc,
            "color": color,
            "footer": {"text": name},
        })

    payload = {"content": f"📡 **Stock Alerts** ({len(alerts)} tickers)", "embeds": embeds}
    r = requests.post(url, json=payload, timeout=10)
    return r.status_code == 204
