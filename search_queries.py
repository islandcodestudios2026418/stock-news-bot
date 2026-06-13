"""Generate targeted web search queries for each keyword+sector pair."""

# Forum/community suffixes by sector for more precise searches
SECTOR_FORUMS = {
    "ISP": ["downdetector", "reddit broadband", "dslreports"],
    "Energy": ["oilprice.com", "reddit energy", "seeking alpha energy"],
    "Gaming": ["reddit gaming", "resetera", "steam community"],
    "Space/Satellite": ["reddit space", "nasaspaceflight forum"],
    "Tech/Apple": ["macrumors forum", "reddit apple", "hacker news"],
    "Sports Media": ["reddit cordcutters", "reddit sports"],
    "AI": ["hacker news", "reddit machinelearning", "reddit localllama"],
    "EV": ["reddit electricvehicles", "insideevs forum", "tesla motors club"],
    "Crypto": ["reddit cryptocurrency", "bitcointalk", "crypto twitter"],
    "Semiconductors": ["reddit hardware", "anandtech forum", "hacker news"],
    "Cloud": ["hacker news", "reddit devops", "reddit aws"],
    "Streaming": ["reddit cordcutters", "reddit television"],
    "Cybersecurity": ["reddit netsec", "hacker news", "bleepingcomputer"],
    "Pharma/GLP1": ["reddit loseit", "reddit pharmacy", "medscape forum"],
    "Social Media": ["reddit technology", "hacker news", "the verge"],
    "Direct": ["reddit stocks", "seeking alpha", "stocktwits"],
}


def generate_search_queries(mapped: list[dict]) -> list[dict]:
    """Generate web search queries for Kiro to execute.
    
    For each mapped keyword+sector, produce 2 queries:
    1. keyword + sector-specific forum/community
    2. keyword + "stock impact" or "stock price"
    
    Returns: [{query, keyword, sector, purpose}]
    """
    queries = []
    seen = set()

    for item in mapped:
        kw = item["keyword"]
        sector = item.get("sector", "Direct")
        forums = SECTOR_FORUMS.get(sector, ["reddit", "seeking alpha"])

        # Query 1: sector-specific community discussion
        q1 = f"{kw} {forums[0]}"
        if q1 not in seen:
            seen.add(q1)
            queries.append({"query": q1, "keyword": kw, "sector": sector, "purpose": "forum_sentiment"})

        # Query 2: stock/market impact
        q2 = f"{kw} stock impact"
        if q2 not in seen:
            seen.add(q2)
            queries.append({"query": q2, "keyword": kw, "sector": sector, "purpose": "market_relevance"})

    return queries
