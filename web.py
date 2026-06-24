"""FastAPI web server — stock dashboard with ticker cards + history."""
import json, os, sys, threading
from datetime import datetime, timezone, date
from contextlib import asynccontextmanager
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

SNAPSHOTS_DIR = Path("snapshots")
SNAPSHOTS_DIR.mkdir(exist_ok=True)

_state = {"summary": "", "alerts": [], "tickers": {}, "updated_at": None}
_lock = threading.Lock()


def _get_ticker_data(ticker):
    """Fetch all data for a single ticker."""
    from price import get_stock_data
    from technicals import get_batch_technicals
    from earnings import get_batch_earnings
    from ratings import get_batch_ratings
    from levels import get_batch_levels

    data = get_stock_data(ticker) or {}
    techs = get_batch_technicals([ticker]).get(ticker, {})
    earn = get_batch_earnings([ticker]).get(ticker, {})
    rate = get_batch_ratings([ticker]).get(ticker, {})
    lvl = get_batch_levels([ticker]).get(ticker, {})

    return {**data, "technicals": techs, "earnings": earn, "ratings": rate, "levels": lvl}


def _run_scan():
    """Execute scan, cache results, save daily snapshot."""
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

        # Build text summary
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
        techs = get_batch_technicals(tickers)
        lvls = get_batch_levels(tickers)
        earnings = get_batch_earnings(tickers)
        alerts = scan_watchlist()

        # Build per-ticker card data
        ticker_cards = {}
        for a in (alerts or []):
            t = a["ticker"]
            ticker_cards[t] = {
                "price": a.get("price", 0),
                "change_5d_pct": a.get("change_5d_pct", 0),
                "volume_ratio": a.get("volume_ratio", 1.0),
                "alerts": a.get("alerts", []),
                "rsi": techs.get(t, {}).get("rsi"),
                "signals": techs.get(t, {}).get("signals", []),
                "support": lvls.get(t, {}).get("nearest_support"),
                "resistance": lvls.get(t, {}).get("nearest_resistance"),
                "earnings_date": earnings.get(t, {}).get("upcoming", {}).get("date") if earnings.get(t, {}).get("upcoming") else None,
            }

        # Continue text summary
        if rotation:
            inflows = [r for r in rotation if r.get("signal") == "inflow"]
            outflows = [r for r in rotation if r.get("signal") == "outflow"]
            lines.append("\n🔄 Sector Rotation (5d):")
            for r in inflows:
                lines.append(f"  📈 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")
            for r in outflows:
                lines.append(f"  📉 {r['sector']} ({r['etf']}) {r['change_pct']:+.1f}%")

        notable = [(t, d) for t, d in techs.items() if d.get("signals")]
        if notable:
            lines.append("\n📐 Technical Signals:")
            for t, d in notable:
                lines.append(f"  • {t} RSI={d.get('rsi','-')} — {', '.join(d['signals'])}")

        with _lock:
            _state["summary"] = "\n".join(lines)
            _state["alerts"] = alerts or []
            _state["tickers"] = ticker_cards
            _state["updated_at"] = datetime.now(timezone.utc).isoformat()

        # Save daily snapshot
        snap_file = SNAPSHOTS_DIR / f"{date.today().isoformat()}.json"
        snap_data = {"summary": _state["summary"], "tickers": ticker_cards, "updated_at": _state["updated_at"]}
        snap_file.write_text(json.dumps(snap_data, indent=2), encoding="utf-8")

        print(f"[scan] Updated at {_state['updated_at']}", file=sys.stderr)
    except Exception as e:
        print(f"[scan] Error: {e}", file=sys.stderr)


# --- Scheduler ---
scheduler = BackgroundScheduler()
scheduler.add_job(_run_scan, CronTrigger(hour=12, minute=30, day_of_week="mon-fri"), id="premarket")
scheduler.add_job(_run_scan, CronTrigger(hour="13-20", minute=0, day_of_week="mon-fri"), id="intraday")


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=_run_scan, daemon=True).start()
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="Stock News Bot", lifespan=lifespan)


DASHBOARD_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stock Dashboard</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,system-ui,sans-serif;background:#0f0f1a;color:#e0e0e0;padding:1.5rem}}
.header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:1.5rem}}
h1{{color:#3498db;font-size:1.5rem}}
.updated{{color:#666;font-size:0.75rem}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:1rem;margin-bottom:2rem}}
.card{{background:#1a1a2e;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;transition:border-color .2s}}
.card:hover{{border-color:#3498db}}
.card-head{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:0.5rem}}
.ticker{{font-weight:700;font-size:1.2rem;color:#fff}}
.price{{font-size:1.1rem}}
.change{{font-size:0.9rem;font-weight:600;padding:2px 8px;border-radius:4px}}
.up{{color:#00e676;background:#00e67615}}
.down{{color:#ff5252;background:#ff525215}}
.meta{{font-size:0.75rem;color:#888;margin-top:0.5rem}}
.signals{{margin-top:0.5rem;display:flex;flex-wrap:wrap;gap:4px}}
.sig{{font-size:0.7rem;background:#2a2a4a;padding:2px 6px;border-radius:3px;color:#aaa}}
.summary-box{{background:#1a1a2e;border-radius:12px;padding:1.5rem;border:1px solid #2a2a4a}}
pre{{white-space:pre-wrap;line-height:1.6;font-size:13px;font-family:monospace}}
.refresh-btn{{background:#3498db;color:#fff;border:none;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:0.8rem}}
.refresh-btn:hover{{background:#2980b9}}
</style></head><body>
<div class="header">
  <h1>📡 Stock News Bot</h1>
  <div><button class="refresh-btn" onclick="refresh()">↻ Refresh</button>
  <span class="updated">Updated: {updated}</span></div>
</div>
<div class="grid">{cards}</div>
<div class="summary-box"><pre>{summary}</pre></div>
<script>
function refresh(){{fetch('/api/refresh',{{method:'POST'}}).then(()=>setTimeout(()=>location.reload(),45000))}}
setTimeout(()=>location.reload(),300000);
</script>
</body></html>"""


def _render_cards(tickers):
    if not tickers:
        return '<div class="card"><span class="ticker">Loading...</span></div>'
    cards = []
    for t, d in sorted(tickers.items(), key=lambda x: abs(x[1].get("change_5d_pct", 0)), reverse=True):
        pct = d.get("change_5d_pct", 0)
        cls = "up" if pct >= 0 else "down"
        sign = "+" if pct >= 0 else ""
        rsi_str = f"RSI {d['rsi']:.0f}" if d.get("rsi") else ""
        sigs = "".join(f'<span class="sig">{s}</span>' for s in d.get("signals", []))
        meta_parts = [x for x in [rsi_str, f"Vol {d.get('volume_ratio',1):.1f}x" if d.get("volume_ratio",1) > 1.5 else "", f"Earn: {d['earnings_date']}" if d.get("earnings_date") else ""] if x]
        cards.append(f"""<div class="card">
<div class="card-head"><span class="ticker">{t}</span><span class="change {cls}">{sign}{pct:.1f}%</span></div>
<div class="price">${d.get('price',0):.2f}</div>
<div class="meta">{' · '.join(meta_parts)}</div>
<div class="signals">{sigs}</div></div>""")
    return "\n".join(cards)


@app.get("/", response_class=HTMLResponse)
def dashboard():
    with _lock:
        summary = _state["summary"] or "Scanning..."
        updated = _state["updated_at"] or "loading..."
        tickers = _state["tickers"]
    return DASHBOARD_HTML.format(updated=updated, cards=_render_cards(tickers), summary=summary)


@app.get("/api/summary")
def api_summary():
    with _lock:
        return JSONResponse({"summary": _state["summary"], "updated_at": _state["updated_at"]})


@app.get("/api/alerts")
def api_alerts():
    with _lock:
        return JSONResponse({"alerts": _state["alerts"], "updated_at": _state["updated_at"]})


@app.get("/api/ticker/{symbol}")
def api_ticker(symbol: str):
    """Per-ticker detail endpoint."""
    data = _get_ticker_data(symbol.upper())
    return JSONResponse(data)


@app.get("/api/history")
def api_history(days: int = 7):
    """Return recent daily snapshots."""
    files = sorted(SNAPSHOTS_DIR.glob("*.json"), reverse=True)[:days]
    history = []
    for f in files:
        try:
            history.append({"date": f.stem, **json.loads(f.read_text(encoding="utf-8"))})
        except Exception:
            pass
    return JSONResponse(history)


@app.post("/api/refresh")
def api_refresh():
    threading.Thread(target=_run_scan, daemon=True).start()
    return JSONResponse({"status": "refresh started"})


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
