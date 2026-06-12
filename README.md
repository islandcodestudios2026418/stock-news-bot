# Stock News Bot — Trend-Price Divergence Detector

Finds stocks where Google Trends hype is high but stock price hasn't reacted yet.

## Architecture

```
OpenAB cron (daily) → @mention Kiro CLI → runs Python scripts → Kiro analyzes & replies in Discord
```

## Setup (on Zeabur/OpenAB environment)

```bash
git clone https://github.com/islandcodestudios2026418/stock-news-bot.git
cd stock-news-bot
pip install -r requirements.txt
```

## Usage (by Kiro CLI)

```bash
# Step 1: Get trending keywords
python main.py

# Step 2: After mapping keywords → tickers, check specific stocks
python main.py check AAPL NVDA COIN TSLA
```

## OpenAB Cron Prompt

Set this as the daily cron message in OpenAB config:

```
Run the daily stock trend-divergence scan:
1. Run `python ~/stock-news-bot/main.py` to get trending keywords
2. Map the keywords to related US publicly traded companies
3. Run `python ~/stock-news-bot/main.py check <TICKERS>` for those companies
4. Report which stocks have HIGH trend buzz but LOW price movement (divergence = buy signal)
5. Include upcoming events (earnings, shareholder meetings) as risk flags
```

## Signal Logic

- Trending keyword score high → topic is hot
- Related stock 5-day price change < 3% → market hasn't reacted
- Fundamentals OK (revenue growing, margins positive) → not a dying company
- **Divergence = potential buy opportunity**
