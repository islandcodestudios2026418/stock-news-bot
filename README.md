# 📡 Stock News Bot

Automated US stock monitoring system that tracks news, technicals, and events for a watchlist of stocks, then delivers actionable alerts to Discord.

## Features

- **Price & Volume Alerts** — 5-day drops/surges, volume spikes
- **Technical Indicators** — RSI (overbought/oversold), MACD, golden/death cross
- **Earnings Calendar** — Upcoming dates, EPS estimates, surprise detection
- **SEC Filings** — 8-K, Form 4 insider trades (with dollar values), 13F
- **Analyst Ratings** — Upgrades, downgrades, initiations
- **Options Flow** — Unusual volume/OI ratio (institutional signals)
- **Short Interest** — Squeeze potential (>15% float or >5 days to cover)
- **Sector Rotation** — Money flow via 11 SPDR sector ETFs
- **Correlation Alerts** — Systemic selloff/rally detection
- **Macro Calendar** — FOMC meetings, Treasury auctions
- **Alert Deduplication** — Won't send the same alert twice (30-day memory)
- **Priority Scoring** — Alerts ranked by urgency (CRITICAL → LOW)
- **Discord Delivery** — Color-coded embeds with urgency labels

## Setup

```bash
git clone https://github.com/islandcodestudios2026418/stock-news-bot.git
cd stock-news-bot
pip install -r requirements.txt
```

Requirements: Python 3.10+, `yfinance`, `requests`

For Discord delivery, set:
```bash
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_ID/YOUR_TOKEN"
```

## Commands

### Market Intelligence
```bash
python main.py summary       # Full market dashboard (best daily command)
python main.py watchlist     # Detailed JSON alerts for all watchlist stocks
python main.py scan          # Full pipeline: trends + divergence + watchlist
python main.py correlation   # Detect systemic selloff/rally
```

### Per-Ticker Data
```bash
python main.py check AAPL NVDA   # Price + fundamentals + events
python main.py technicals NVDA   # RSI, MACD, MA crossovers
python main.py earnings TSLA     # Earnings date + EPS data
python main.py options NVDA      # Unusual options activity
python main.py short AMD         # Short interest
python main.py filings AAPL      # Recent SEC filings
python main.py ratings GOOGL     # Analyst rating changes
python main.py insider NVDA      # Insider trades with dollar values
```

### Market-Wide
```bash
python main.py sectors       # Sector ETF rotation (5d)
python main.py macro         # Upcoming macro events
```

### Discord Delivery
```bash
python main.py deliver           # Alerts → dedup → Discord (for cron)
python main.py deliver_summary   # Dashboard → Discord embed
```

### Watchlist Management
```bash
python main.py add COIN PLTR     # Add tickers
python main.py remove COIN       # Remove ticker
python main.py threshold price_drop_pct -7  # Adjust alert thresholds
python main.py history           # View past alert history
```

## Watchlist Config (watchlist.json)

```json
{
  "tickers": ["NVDA", "AAPL", "TSLA", "MSFT", "GOOGL", "AMD", "META", "AMZN"],
  "alerts": {
    "price_drop_pct": -5,
    "price_surge_pct": 5,
    "volume_spike_threshold": 2.0,
    "earnings_days_ahead": 7
  }
}
```

## Example Output

```
📊 Market Dashboard — 2026-06-24 13:22

🏛️ Macro Events (7d):
  • 2026-06-25 — Treasury Auction (Note) [medium]

⚠️ Correlation Alert: systemic_selloff (6/8 stocks down >3%)
  Avg 5d change: -4.0%

🔄 Sector Rotation (5d):
  📈 Utilities (XLU) +0.7%
  📉 Communications (XLC) -4.2%

📐 Technical Signals:
  • MSFT RSI=16.9 — oversold, macd_bearish
  • NVDA RSI=34.8 — macd_bearish

💰 Upcoming Earnings:
  • TSLA — 2026-07-23
  • GOOGL — 2026-07-24

🚨 Alerts (8 tickers):
  • GOOGL $346.13 (-7.3% 5d) — 🔴 5d drop -7.3%
  • META $562.20 (-6.3% 5d) — 🔴 5d drop -6.3%
```

## Alert Priority Scoring

| Priority | Score | Examples |
|----------|-------|---------|
| 🔴 CRITICAL | 80+ | Death/golden cross, oversold RSI, squeeze signal |
| 🟠 HIGH | 60-79 | EPS surprise, insider buy, price drop >5% |
| 🟡 MEDIUM | 40-59 | Volume spike, options flow, analyst rating |
| 🟢 LOW | <40 | SEC filing, upcoming event, earnings date |

## Web Dashboard (Zeabur)

The bot includes a FastAPI web server that serves a live dashboard:

```bash
python web.py   # Starts on port 8080 (or $PORT)
```

**Endpoints:**
- `GET /` — HTML dashboard (auto-refreshes every 5 min)
- `GET /api/summary` — JSON summary
- `GET /api/alerts` — JSON alerts
- `POST /api/refresh` — Trigger manual rescan

**Scheduled scans:** 8:30 AM ET pre-market + every hour during market hours (Mon-Fri).

**Deploy to Zeabur:**
1. Push repo to GitHub
2. Connect in Zeabur dashboard → auto-detects Dockerfile
3. Set env vars: `DISCORD_WEBHOOK_URL`, `DISCORD_CRITICAL_WEBHOOK_URL` (optional)
4. Dashboard is live at your Zeabur URL

## Automation (Cron)

```bash
# Pre-market summary (run before US market open)
0 14 * * 1-5 cd ~/stock-news-bot && python main.py deliver_summary

# Post-market alerts (run after US market close)
30 20 * * 1-5 cd ~/stock-news-bot && python main.py deliver
```

## Architecture

```
main.py (CLI router)
├── watchlist.py (orchestrator — parallel ThreadPoolExecutor)
│   ├── price.py (yfinance batch download)
│   ├── technicals.py (RSI, MACD, MA crossovers)
│   ├── earnings.py (EPS estimates/actuals)
│   ├── edgar.py (SEC filings + insider trades)
│   ├── ratings.py (analyst upgrades/downgrades)
│   ├── options_flow.py (unusual vol/OI)
│   ├── short_interest.py (squeeze detection)
│   └── news.py (headlines)
├── correlation.py (systemic selloff/rally)
├── sector_rotation.py (ETF performance ranking)
├── macro.py (FOMC, Treasury auctions)
├── scoring.py (priority ranking)
├── dedup.py (alert history, 30-day purge)
└── discord_hook.py (webhook delivery)
```

## Data Sources

All free, no API keys required:
- **yfinance** — Price, volume, fundamentals, earnings, options, ratings, insider trades
- **SEC EDGAR** — 8-K, Form 4, 13F filings (public API)
- **TreasuryDirect** — Upcoming auction dates
- **Google Trends** — Trending keyword detection (for divergence mode)
