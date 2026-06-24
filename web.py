"""FastAPI web server — serves stock dashboard as HTML + JSON API."""
import json, os, sys, threading
from datetime import datetime, timezone
from contextlib import asynccontextmanager

# Fix Unicode on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

# --- Cached dashboard state ---
_state = {"summary": "", "alerts": [], "updated_at": None}
_lock = threading.Lock()


def _run_scan():
    """Execute summary scan and cache results."""
    try:
        from watchlist import scan_watchlist
        from macro import get_macro_events
        from earnings import get_batch_earnings
        from sector_rotation import get_sector_rotation
        from correlation import get_correlation_alert
        from technicals import get_batch_technicals
        from sentiment import get_sentiment
        from levels import get_batch_levels
        from market_hours import get_market_status

        config = json.loads(open("watchlist.json").read())
        tickers = config.get("tickers", [])
        mkt = get_market_status()

        lines = [f"📊 Market Dashboard — {datetime.now().strftime('%Y-%m-%d %H:%M')}"]
        status_emoji = {"open": "🟢", "pre_market": "🟡", "after_hours": "🟡", "closed": "🔴"}
        lines[0] += f"  {status_emoji.get(mkt['session'], '⚪')} {mkt['label']} ({mkt['et_time']})"

        sent = get_sentiment()
        if sent.get("vix"):
            bar = "█" * (sent["score"] // 10) + "░" * (10 - sent["score"] // 10)
            lines.append(f"\n🧠 Sentiment: {sent['label']} ({sent['score']}/100) [{bar}]")
            lines.append(f"  VIX: {sent['vix']} ({sent['vix_change_5d']:+.1f} 5d)")

        macro = get_macro_events(days_ahead=7)
        if macro:
            lines.append("\n🏛️ Macro Events (7d):")
            for e in macro[:5]:
                lines.append(f"  • {e['date']} — {e['event']} [{e['impact']}]")

        corr = get_correlation_alert(tickers)
        if corr.get("alert"):
            lines.append(f"\n⚠️ Correlation Alert: {corr['signal']}")
            lines.append(f"  Avg 5d change: {corr['avg_change_5d']:+.1f}%")

        rotation = get_sector_rotation()
        if rotation:
            inflows = [r for r in rotation if r.get("signal") == "inflow"]
            outflows = [r for r in rotation if r.get("signal") == "outflow"]
            lines.append("\n🔄 Sector Rotation (5d):")
            for r in inflows:
                lines.append(f"  📈 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")
            for r in outflows:
                lines.append(f"  📉 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")

        techs = get_batch_technicals(tickers)
        notable = [(t, d) for t, d in techs.items() if d.get("signals")]
        if notable:
            lines.append("\n📐 Technical Signals:")
            for t, d in notable:
                lines.append(f"  • {t} RSI={d.get('rsi','-')} — {', '.join(d['signals'])}")

        lvls = get_batch_levels(tickers)
        near = [(t, l) for t, l in lvls.items() if l.get("support_pct") and abs(l["support_pct"]) < 3]
        if near:
            lines.append("\n🎯 Near Key Levels:")
            for t, l in near:
                lines.append(f"  • {t} ${l['price']} — support ${l['nearest_support']} ({l['support_pct']:+.1f}%)")

        earnings = get_batch_earnings(tickers)
        upcoming = [(t, e["upcoming"]) for t, e in earnings.items() if e.get("upcoming")]
        if upcoming:
            lines.append("\n💰 Upcoming Earnings:")
            for t, e in upcoming:
                est = f" (est ${e['eps_estimate']:.2f})" if e.get("eps_estimate") else ""
                lines.append(f"  • {t} — {e['date']}{est}")

        alerts = scan_watchlist()
        if alerts:
            lines.append(f"\n🚨 Alerts ({len(alerts)} tickers):")
            for a in alerts:
                top = a["alerts"][0] if a["alerts"] else ""
                lines.append(f"  • {a['ticker']} ${a['price']:.2f} ({a['change_5d_pct']:+.1f}% 5d) — {top}")

        with _lock:
            _state["summary"] = "\n".join(lines)
            _state["alerts"] = alerts or []
            _state["updated_at"] = datetime.now(timezone.utc).isoformat()

        print(f"[scan] Updated at {_state['updated_at']}", file=sys.stderr)
    except Exception as e:
        print(f"[scan] Error: {e}", file=sys.stderr)


# --- Scheduler ---
scheduler = BackgroundScheduler()
# Pre-market scan: 8:30 AM ET = 12:30 UTC (Mon-Fri)
scheduler.add_job(_run_scan, CronTrigger(hour=12, minute=30, day_of_week="mon-fri"), id="premarket")
# Also run every 2 hours during market hours (13:30-20:00 UTC = 9:30 AM - 4 PM ET)
scheduler.add_job(_run_scan, CronTrigger(hour="13-20", minute=0, day_of_week="mon-fri"), id="intraday")


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_run_scan, daemon=True).start()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Stock News Bot", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with _lock:
        text = _state["summary"] or "Loading..."
        updated = _state["updated_at"] or "never"
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Dashboard</title>
<style>
body{{font-family:monospace;background:#1a1a2e;color:#e0e0e0;padding:2rem;max-width:800px;margin:0 auto}}
pre{{white-space:pre-wrap;line-height:1.6;font-size:14px}}
.updated{{color:#888;font-size:12px;margin-bottom:1rem}}
h1{{color:#3498db;margin-bottom:0.5rem}}
</style></head><body>
<h1>📡 Stock News Bot</h1>
<div class="updated">Last updated: {updated}</div>
<pre>{text}</pre>
<script>setTimeout(()=>location.reload(),300000)</script>
</body></html>"""
    return html


@app.get("/api/summary")
def api_summary():
    with _lock:
        return JSONResponse({"summary": _state["summary"], "updated_at": _state["updated_at"]})


@app.get("/api/alerts")
def api_alerts():
    with _lock:
        return JSONResponse({"alerts": _state["alerts"], "updated_at": _state["updated_at"]})


@app.post("/api/refresh")
def api_refresh():
    """Trigger manual rescan."""
    threading.Thread(target=_run_scan, daemon=True).start()
    return JSONResponse({"status": "refresh started"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
