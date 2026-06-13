"""Map trending keywords to stock tickers using sector_map.json."""
import json
from pathlib import Path

SECTOR_MAP = json.loads((Path(__file__).parent / "sector_map.json").read_text())
NEGATIVE_KW = [k.lower() for k in SECTOR_MAP["negative_keywords"]]

# Well-known ticker/company direct matches
DIRECT_MAP = {
    "aapl": "AAPL", "apple": "AAPL", "nvidia": "NVDA", "nvda": "NVDA",
    "tesla": "TSLA", "tsla": "TSLA", "google": "GOOGL", "googl": "GOOGL",
    "microsoft": "MSFT", "msft": "MSFT", "amazon": "AMZN", "amzn": "AMZN",
    "meta": "META", "netflix": "NFLX", "coinbase": "COIN", "roblox": "RBLX",
    "amd": "AMD", "intel": "INTC", "palantir": "PLTR", "snowflake": "SNOW",
}


def is_negative(keyword: str) -> bool:
    kw = keyword.lower()
    return any(neg in kw for neg in NEGATIVE_KW)


def map_keywords_to_tickers(keywords: list[dict]) -> list[dict]:
    """Map list of {keyword, score} to {keyword, score, tickers, connection_type, sector}.
    
    Filters out geographic-only and negative keywords.
    """
    results = []
    for item in keywords:
        kw = item["keyword"]
        score = item.get("score", 1)

        if is_negative(kw):
            continue

        kw_lower = kw.lower()

        # 1. Direct company/ticker match
        for token in kw_lower.split():
            if token in DIRECT_MAP:
                results.append({"keyword": kw, "score": score, "tickers": [DIRECT_MAP[token]],
                                "connection_type": "direct", "sector": "Direct"})
                break
        else:
            # 2. Sector pattern match
            for pat in SECTOR_MAP["patterns"]:
                if any(p in kw_lower for p in pat["keywords"]):
                    results.append({"keyword": kw, "score": score, "tickers": pat["tickers"],
                                    "connection_type": "sector", "sector": pat["sector"]})
                    break
            # No match = skip (don't guess geographic)

    return results
