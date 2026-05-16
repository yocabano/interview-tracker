import os
import time
import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

SPONSOR_LIST_URL = os.environ.get(
    "SPONSOR_LIST_URL",
    "https://raw.githubusercontent.com/yocabano/interview-tracker/main/data/sponsors.html",
)

_cache: dict = {"text": "", "fetched_at": 0.0}
CACHE_TTL = 3600  # re-fetch from GitHub once per hour


def _fetch_text() -> str:
    resp = httpx.get(SPONSOR_LIST_URL, timeout=10, follow_redirects=True)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    return soup.get_text(separator=" ").lower()


def _get_sponsor_text() -> str:
    now = time.time()
    if not _cache["text"] or now - _cache["fetched_at"] > CACHE_TTL:
        try:
            _cache["text"] = _fetch_text()
            _cache["fetched_at"] = now
        except Exception:
            pass  # keep stale cache if fetch fails
    return _cache["text"]


def is_sponsor(company_name: str) -> bool:
    if not company_name:
        return False
    text = _get_sponsor_text()
    return company_name.strip().lower() in text
