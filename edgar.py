"""SEC EDGAR filing alerts — 8-K, Form 4 (insider trades), 13F."""
import requests
import yfinance as yf
from datetime import datetime, timedelta

HEADERS = {"User-Agent": "StockNewsBot/1.0 (personal use)"}
EFTS_BASE = "https://efts.sec.gov/LATEST/search-index?q="
FILINGS_BASE = "https://efts.sec.gov/LATEST/search-index"
EDGAR_SEARCH = "https://efts.sec.gov/LATEST/search-index"

# SEC full-text search API
SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"


def get_cik(ticker: str) -> str | None:
    """Resolve ticker to CIK via SEC company tickers JSON."""
    try:
        url = "https://www.sec.gov/files/company_tickers.json"
        r = requests.get(url, headers=HEADERS, timeout=10)
        data = r.json()
        for entry in data.values():
            if entry.get("ticker", "").upper() == ticker.upper():
                return str(entry["cik_str"]).zfill(10)
    except Exception:
        pass
    return None


def get_recent_filings(ticker: str, form_types: list[str] = None, days: int = 14) -> list[dict]:
    """Fetch recent filings for a ticker from EDGAR full-text search API."""
    if form_types is None:
        form_types = ["8-K", "4", "13F-HR"]

    cik = get_cik(ticker)
    results = []
    date_from = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    for form_type in form_types:
        try:
            params = {
                "q": f"\"{ticker}\"",
                "dateRange": "custom",
                "startdt": date_from,
                "enddt": datetime.now().strftime("%Y-%m-%d"),
                "forms": form_type,
            }
            url = "https://efts.sec.gov/LATEST/search-index"
            r = requests.get(url, params=params, headers=HEADERS, timeout=10)
            if r.status_code != 200:
                results.extend(_get_filings_rss(ticker, form_type, days))
                continue
            data = r.json()
            for hit in (data.get("hits", {}).get("hits", []) or [])[:5]:
                src = hit.get("_source", {})
                # Filter: only include if company CIK matches
                ciks = src.get("ciks", [])
                if cik and cik not in ciks:
                    continue
                names = src.get("display_names", [])
                desc = names[0] if names else src.get("entity_name", "")
                adsh = src.get("adsh", "").replace("-", "")
                filing_cik = ciks[1] if len(ciks) > 1 else (ciks[0] if ciks else "")
                results.append({
                    "form": form_type,
                    "filed": src.get("file_date", ""),
                    "description": desc,
                    "url": f"https://www.sec.gov/Archives/edgar/data/{filing_cik}/{adsh}" if adsh else "",
                })
        except Exception:
            results.extend(_get_filings_rss(ticker, form_type, days))

    return results


def _get_filings_rss(ticker: str, form_type: str, days: int) -> list[dict]:
    """Fallback: fetch filings via EDGAR company RSS feed."""
    cik = get_cik(ticker)
    if not cik:
        return []
    try:
        url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type={form_type}&dateb=&owner=include&count=5&search_text=&output=atom"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return []
        # Simple XML parse without extra deps
        entries = r.text.split("<entry>")[1:]
        results = []
        cutoff = datetime.now() - timedelta(days=days)
        for entry in entries[:5]:
            title = _extract_xml(entry, "title")
            updated = _extract_xml(entry, "updated")[:10]
            link = _extract_xml_attr(entry, "link", "href")
            try:
                filed_dt = datetime.strptime(updated, "%Y-%m-%d")
                if filed_dt < cutoff:
                    continue
            except ValueError:
                pass
            results.append({
                "form": form_type,
                "filed": updated,
                "description": title,
                "url": link,
            })
        return results
    except Exception:
        return []


def _extract_xml(text: str, tag: str) -> str:
    start = text.find(f"<{tag}>")
    end = text.find(f"</{tag}>")
    if start == -1 or end == -1:
        return ""
    return text[start + len(tag) + 2:end].strip()


def _extract_xml_attr(text: str, tag: str, attr: str) -> str:
    start = text.find(f"<{tag} ")
    if start == -1:
        return ""
    chunk = text[start:text.find(">", start) + 1]
    attr_start = chunk.find(f'{attr}="')
    if attr_start == -1:
        return ""
    val_start = attr_start + len(attr) + 2
    val_end = chunk.find('"', val_start)
    return chunk[val_start:val_end]


def get_insider_trades(ticker: str, days: int = 14) -> list[dict]:
    """Parse Form 4 filings with buy/sell direction and dollar values via yfinance."""
    try:
        t = yf.Ticker(ticker)
        trades = t.insider_transactions
        if trades is None or trades.empty:
            return []
        from datetime import datetime, timedelta
        cutoff = datetime.now() - timedelta(days=days)
        results = []
        for _, row in trades.iterrows():
            start_date = row.get("Start Date")
            if start_date and hasattr(start_date, 'to_pydatetime'):
                start_date = start_date.to_pydatetime()
                if hasattr(start_date, 'replace') and start_date.tzinfo:
                    start_date = start_date.replace(tzinfo=None)
                if start_date < cutoff:
                    continue
            text = str(row.get("Text", ""))
            shares = row.get("Shares", 0) or 0
            value = row.get("Value", 0) or 0
            insider = str(row.get("Insider", ""))
            is_buy = "Purchase" in text or "Buy" in text
            is_sell = "Sale" in text or "Sell" in text
            results.append({
                "date": start_date.strftime("%Y-%m-%d") if start_date else "",
                "insider": insider,
                "direction": "BUY" if is_buy else "SELL" if is_sell else "OTHER",
                "shares": int(shares),
                "value_usd": int(value),
                "text": text[:80],
            })
        return results[:10]
    except Exception:
        return []


def get_batch_filings(tickers: list[str], days: int = 14) -> dict:
    """Fetch recent filings for multiple tickers."""
    return {t: get_recent_filings(t, days=days) for t in tickers}
