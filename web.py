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

_state = {"summary": "", "alerts": [], "tickers": {}, "brief": [], "updated_at": None}
_health = {"started_at": datetime.now(timezone.utc).isoformat(), "scans": 0, "errors": 0, "last_error": None}
_lock = threading.Lock()


def _get_ticker_data(ticker):
    """Fetch all data for a single ticker."""
    from price import get_stock_data
    from technicals import get_batch_technicals
    from earnings import get_batch_earnings
    from ratings import get_batch_ratings
    from levels import get_batch_levels
    from news import get_news

    data = get_stock_data(ticker) or {}
    techs = get_batch_technicals([ticker]).get(ticker, {})
    earn = get_batch_earnings([ticker]).get(ticker, {})
    rate = get_batch_ratings([ticker]).get(ticker, {})
    lvl = get_batch_levels([ticker]).get(ticker, {})
    headlines = get_news(ticker, max_items=5)

    return {**data, "technicals": techs, "earnings": earn, "ratings": rate, "levels": lvl, "news": headlines}


def _run_scan():
    """Execute scan with retry, cache results, save daily snapshot."""
    for attempt in range(3):
        try:
            _do_scan()
            _health["scans"] += 1
            return
        except Exception as e:
            _health["errors"] += 1
            _health["last_error"] = f"{datetime.now(timezone.utc).isoformat()}: {e}"
            print(f"[scan] Attempt {attempt+1} failed: {e}", file=sys.stderr)
            if attempt < 2:
                import time; time.sleep(5)
    print("[scan] All retries exhausted", file=sys.stderr)


def _do_scan():
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
    techs = get_batch_technicals(tickers)
    lvls = get_batch_levels(tickers)
    earnings = get_batch_earnings(tickers)
    alerts = scan_watchlist()

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

        # Generate actionable brief
        from brief import generate_brief
        _state["brief"] = generate_brief(ticker_cards, sentiment=sent, correlation=corr, macro=macro, rotation=rotation)

    snap_file = SNAPSHOTS_DIR / f"{date.today().isoformat()}.json"
    snap_data = {"summary": _state["summary"], "tickers": ticker_cards, "updated_at": _state["updated_at"]}
    snap_file.write_text(json.dumps(snap_data, indent=2), encoding="utf-8")

    # Auto-deliver new alerts to Discord
    try:
        from dedup import deduplicate
        from scoring import rank_alerts
        from discord_hook import send_alerts as discord_send
        new_alerts = deduplicate(alerts or [])
        if new_alerts:
            ranked = rank_alerts(new_alerts)
            # Prepend brief to first alert's description
            brief_text = "\n".join(_state.get("brief", []))
            if brief_text and ranked:
                ranked[0]["alerts"] = [f"**📋 Brief:**\n{brief_text}", ""] + ranked[0].get("alerts", [])
            discord_send(ranked)
            print(f"[scan] Discord: delivered {len(ranked)} new alerts", file=sys.stderr)
    except Exception as de:
        print(f"[scan] Discord delivery skipped: {de}", file=sys.stderr)

    print(f"[scan] Updated at {_state['updated_at']}", file=sys.stderr)


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
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="theme-color" content="#0f0f1a">
<link rel="manifest" href="/manifest.json">
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
.ticker{{font-weight:700;font-size:1.2rem;color:#fff;text-decoration:none}}
.ticker:hover{{text-decoration:underline}}
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
.wl-section{{margin-bottom:2rem;background:#1a1a2e;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a}}
.wl-form{{display:flex;gap:8px;margin-bottom:0.8rem}}
.wl-form input{{background:#0f0f1a;border:1px solid #2a2a4a;color:#e0e0e0;padding:6px 10px;border-radius:6px;font-size:0.85rem;width:120px}}
.wl-tags{{display:flex;flex-wrap:wrap;gap:6px}}
.wl-tag{{background:#2a2a4a;padding:4px 10px;border-radius:4px;font-size:0.8rem;display:flex;align-items:center;gap:4px}}
.wl-tag button{{background:none;border:none;color:#ff5252;cursor:pointer;font-size:1rem;line-height:1}}
.brief{{background:#1a2a1a;border:1px solid #2a4a2a;border-radius:12px;padding:1.2rem;margin-bottom:1.5rem}}
.brief h2{{font-size:0.95rem;color:#00e676;margin-bottom:0.6rem}}
.brief li{{margin-bottom:0.4rem;font-size:0.85rem;line-height:1.4}}
.config-row{{display:flex;align-items:center;gap:8px;margin-top:0.6rem;flex-wrap:wrap}}
.config-row label{{font-size:0.75rem;color:#888;min-width:140px}}
.config-row input{{background:#0f0f1a;border:1px solid #2a2a4a;color:#e0e0e0;padding:4px 8px;border-radius:4px;width:70px;font-size:0.8rem}}
</style></head><body>
<div class="header">
  <h1>📡 Stock News Bot</h1>
  <div><button class="refresh-btn" onclick="refresh()">↻ Refresh</button>
  <span class="updated">Updated: {updated}</span></div>
</div>
{brief_html}
<div class="grid">{cards}</div>
<div class="wl-section">
  <div class="wl-form"><input id="wl-input" placeholder="e.g. TSLA" onkeydown="if(event.key==='Enter')addTicker()">
  <button class="refresh-btn" onclick="addTicker()">+ Add</button></div>
  <div class="wl-tags" id="wl-tags">{watchlist_tags}</div>
  <div id="config-section">{config_html}</div>
</div>
<div class="summary-box"><pre>{summary}</pre></div>
<script>
function refresh(){{fetch('/api/refresh',{{method:'POST'}}).then(()=>setTimeout(poll,45000))}}
function addTicker(){{const i=document.getElementById('wl-input');const t=i.value.trim().toUpperCase();if(!t)return;fetch('/api/watchlist/add',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload())}}
function removeTicker(t){{fetch('/api/watchlist/remove',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{ticker:t}})}}).then(()=>location.reload())}}
function saveConfig(){{const inputs=document.querySelectorAll('.cfg-input');const body={{}};inputs.forEach(i=>body[i.name]=parseFloat(i.value));fetch('/api/config',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(body)}}).then(()=>{{document.getElementById('cfg-msg').textContent='✓ Saved';setTimeout(()=>document.getElementById('cfg-msg').textContent='',2000)}})}}
let lastUpdate='';
function poll(){{fetch('/api/summary').then(r=>r.json()).then(d=>{{if(d.updated_at&&d.updated_at!==lastUpdate){{lastUpdate=d.updated_at;document.querySelector('.updated').textContent='Updated: '+d.updated_at;location.reload()}}}}catch(e=>{{}})}}
setInterval(poll,60000);
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
<div class="card-head"><a href="/ticker/{t}" class="ticker">{t}</a><span class="change {cls}">{sign}{pct:.1f}%</span></div>
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
        brief = _state.get("brief", [])
    config = json.loads(open("watchlist.json").read())
    wl_tags = "".join(f'<span class="wl-tag">{t}<button onclick="removeTicker(\'{t}\')">×</button></span>' for t in config.get("tickers", []))
    if brief:
        brief_items = "".join(f"<li>{b}</li>" for b in brief)
        brief_html = f'<div class="brief"><h2>🧠 Market Brief</h2><ul>{brief_items}</ul></div>'
    else:
        brief_html = ""
    alerts_cfg = config.get("alerts", {})
    cfg_rows = "".join(f'<div class="config-row"><label>{k}</label><input class="cfg-input" name="{k}" value="{v}"></div>' for k, v in alerts_cfg.items())
    config_html = f'{cfg_rows}<div class="config-row"><button class="refresh-btn" onclick="saveConfig()">Save Thresholds</button><span id="cfg-msg" style="color:#00e676;font-size:0.75rem"></span></div>' if cfg_rows else ""
    return DASHBOARD_HTML.format(updated=updated, cards=_render_cards(tickers), summary=summary, watchlist_tags=wl_tags, brief_html=brief_html, config_html=config_html)


@app.get("/api/summary")
def api_summary():
    with _lock:
        return JSONResponse({"summary": _state["summary"], "brief": _state.get("brief", []), "updated_at": _state["updated_at"]})


@app.get("/api/alerts")
def api_alerts():
    with _lock:
        return JSONResponse({"alerts": _state["alerts"], "updated_at": _state["updated_at"]})


@app.get("/api/ticker/{symbol}")
def api_ticker(symbol: str):
    """Per-ticker detail endpoint."""
    data = _get_ticker_data(symbol.upper())
    return JSONResponse(data)


@app.get("/api/watchlist")
def api_watchlist():
    config = json.loads(open("watchlist.json").read())
    return JSONResponse(config)


@app.get("/api/config")
def api_config():
    """Return alert threshold configuration."""
    config = json.loads(open("watchlist.json").read())
    return JSONResponse(config.get("alerts", {}))


@app.post("/api/config")
def api_config_update(body: dict):
    """Update alert thresholds. Accepts partial updates."""
    config = json.loads(open("watchlist.json").read())
    alerts = config.get("alerts", {})
    for k, v in body.items():
        if k in alerts:
            alerts[k] = float(v)
    config["alerts"] = alerts
    Path("watchlist.json").write_text(json.dumps(config, indent=2))
    return JSONResponse({"message": "Config updated", "alerts": alerts})


@app.post("/api/watchlist/add")
def api_watchlist_add(body: dict):
    from watchlist import add_ticker
    ticker = body.get("ticker", "").upper()
    if not ticker:
        return JSONResponse({"error": "ticker required"}, status_code=400)
    msg = add_ticker(ticker)
    return JSONResponse({"message": msg, "ticker": ticker})


@app.post("/api/watchlist/remove")
def api_watchlist_remove(body: dict):
    from watchlist import remove_ticker
    ticker = body.get("ticker", "").upper()
    if not ticker:
        return JSONResponse({"error": "ticker required"}, status_code=400)
    msg = remove_ticker(ticker)
    return JSONResponse({"message": msg, "ticker": ticker})


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


@app.get("/health")
def health():
    with _lock:
        updated = _state["updated_at"]
    return JSONResponse({
        "status": "ok",
        "uptime_since": _health["started_at"],
        "scans_completed": _health["scans"],
        "errors": _health["errors"],
        "last_error": _health["last_error"],
        "last_scan": updated,
    })


@app.get("/manifest.json")
def manifest():
    return JSONResponse({
        "name": "Stock News Bot",
        "short_name": "StockBot",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#0f0f1a",
        "theme_color": "#0f0f1a",
        "icons": [{"src": "https://em-content.zobj.net/source/twitter/408/satellite_1f4e1.png", "sizes": "72x72", "type": "image/png"}]
    })


@app.post("/api/refresh")
def api_refresh():
    threading.Thread(target=_run_scan, daemon=True).start()
    return JSONResponse({"status": "refresh started"})


@app.get("/ticker/{symbol}", response_class=HTMLResponse)
def ticker_page(symbol: str):
    """Dedicated ticker detail page."""
    t = symbol.upper()
    data = _get_ticker_data(t)
    techs = data.get("technicals", {})
    earn = data.get("earnings", {})
    rate = data.get("ratings", {})
    lvl = data.get("levels", {})

    price = data.get("price", 0)
    chg5 = data.get("change_5d_pct", 0)
    chg30 = data.get("change_30d_pct", 0)
    name = data.get("name", t)
    sector = data.get("sector", "")

    cls = "up" if chg5 >= 0 else "down"
    rsi = techs.get("rsi", "-")
    macd = techs.get("macd_signal", "")
    signals = ", ".join(techs.get("signals", [])) or "None"

    sup = f"${lvl['nearest_support']:.2f}" if lvl.get("nearest_support") else "-"
    res = f"${lvl['nearest_resistance']:.2f}" if lvl.get("nearest_resistance") else "-"

    earn_date = earn.get("upcoming", {}).get("date", "-") if earn.get("upcoming") else "-"
    earn_est = f"${earn['upcoming']['eps_estimate']:.2f}" if earn.get("upcoming", {}).get("eps_estimate") else "-"

    rating_str = ""
    if isinstance(rate, list) and rate:
        rating_str = "<br>".join(f"{'↑' if r.get('action')=='up' else '↓'} {r.get('firm','')} → {r.get('to_grade','')}" for r in rate[:3])
    else:
        rating_str = "No recent changes"

    headlines = data.get("news", [])
    if headlines:
        news_html = "".join(f'<div class="row"><a href="{h.get("url","#")}" target="_blank">{h.get("title","")}</a></div>' for h in headlines[:5])
    else:
        news_html = "No recent news"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{t} — Stock Detail</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,system-ui,sans-serif;background:#0f0f1a;color:#e0e0e0;padding:1.5rem;max-width:700px;margin:0 auto}}
a{{color:#3498db;text-decoration:none}}
h1{{margin-bottom:0.3rem}}
.sub{{color:#888;font-size:0.85rem;margin-bottom:1.5rem}}
.section{{background:#1a1a2e;border-radius:12px;padding:1.2rem;border:1px solid #2a2a4a;margin-bottom:1rem}}
.section h2{{font-size:1rem;color:#3498db;margin-bottom:0.6rem}}
.row{{display:flex;justify-content:space-between;padding:0.3rem 0;border-bottom:1px solid #1f1f3a}}
.row:last-child{{border:none}}
.label{{color:#888}}
.up{{color:#00e676}} .down{{color:#ff5252}}
</style></head><body>
<a href="/">← Dashboard</a>
<h1>{t} — ${price:.2f} <span class="{cls}">({'+' if chg5>=0 else ''}{chg5:.1f}% 5d)</span></h1>
<div class="sub">{name} · {sector}</div>

<div class="section"><h2>📐 Technicals</h2>
<div class="row"><span class="label">RSI</span><span>{rsi}</span></div>
<div class="row"><span class="label">MACD</span><span>{macd}</span></div>
<div class="row"><span class="label">Signals</span><span>{signals}</span></div>
<div class="row"><span class="label">30d Change</span><span class="{cls}">{chg30:+.1f}%</span></div>
</div>

<div class="section"><h2>🎯 Levels</h2>
<div class="row"><span class="label">Support</span><span>{sup}</span></div>
<div class="row"><span class="label">Resistance</span><span>{res}</span></div>
</div>

<div class="section"><h2>💰 Earnings</h2>
<div class="row"><span class="label">Next Date</span><span>{earn_date}</span></div>
<div class="row"><span class="label">EPS Estimate</span><span>{earn_est}</span></div>
</div>

<div class="section"><h2>📊 Analyst Ratings</h2>
<div>{rating_str}</div>
</div>

<div class="section"><h2>📰 News</h2>
<div>{news_html}</div>
</div>
</body></html>"""
    return html


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
