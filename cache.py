"""Simple TTL cache for API results — avoids redundant calls within same session."""
import json, time
from pathlib import Path

CACHE_DIR = Path(__file__).parent / ".cache"
DEFAULT_TTL = 300  # 5 minutes


def get(key: str, ttl: int = DEFAULT_TTL):
    """Get cached value if fresh. Returns None if expired/missing."""
    path = CACHE_DIR / f"{key}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
        if time.time() - data["ts"] < ttl:
            return data["val"]
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def put(key: str, value):
    """Store value in cache."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = CACHE_DIR / f"{key}.json"
    path.write_text(json.dumps({"ts": time.time(), "val": value}))


def clear():
    """Remove all cached files."""
    if CACHE_DIR.exists():
        for f in CACHE_DIR.glob("*.json"):
            f.unlink()
