import os
import json
import httpx
from bs4 import BeautifulSoup
from curl_cffi import requests as curl_requests
import anthropic


client = anthropic.Anthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


EXTRACT_PROMPT = """Extract structured information from this job posting text.
Return ONLY a valid JSON object with these exact keys (use null if not found):
{
  "company": "Company name",
  "position": "Job title",
  "job_description": "2-4 sentence summary of role responsibilities",
  "required_skills": "comma-separated list of key technical skills",
  "visa_sponsorship": "yes" or "no" or "unknown",
  "location": "City, State or Country",
  "remote_type": "remote" or "hybrid" or "onsite" or "unknown",
  "salary_range": "e.g. $120k-$150k or null if not mentioned"
}

Job posting text:
"""


# ── Custom exceptions ─────────────────────────────────────

class ScrapeError(Exception):
    pass


class ScrapeTimeoutError(ScrapeError):
    pass


class ScrapeHTTPError(ScrapeError):
    pass


class ExtractionError(ScrapeError):
    pass


# ── HTTPX ─────────────────────────────────────────────────

def fetch_with_httpx(url: str) -> str:
    timeout = httpx.Timeout(
        connect=10.0,
        read=30.0,
        write=10.0,
        pool=10.0,
    )

    try:
        with httpx.Client(
            headers=HEADERS,
            follow_redirects=True,
            timeout=timeout,
        ) as client_http:

            resp = client_http.get(url)
            resp.raise_for_status()

            return resp.text

    except httpx.ReadTimeout as e:
        raise ScrapeTimeoutError(
            f"HTTPX read timeout: {url}"
        ) from e

    except httpx.ConnectTimeout as e:
        raise ScrapeTimeoutError(
            f"HTTPX connection timeout: {url}"
        ) from e

    except httpx.HTTPStatusError as e:
        raise ScrapeHTTPError(
            f"HTTPX returned HTTP {e.response.status_code}"
        ) from e

    except httpx.RequestError as e:
        raise ScrapeHTTPError(
            f"HTTPX request failed: {e}"
        ) from e


# ── curl_cffi fallback ────────────────────────────────────

def fetch_with_curl(url: str) -> str:
    try:
        resp = curl_requests.get(
            url,
            impersonate="chrome",
            timeout=30,
            allow_redirects=True,
        )

        resp.raise_for_status()

        return resp.text

    except Exception as e:
        raise ScrapeHTTPError(
            f"curl_cffi HTTP request failed: {e}"
        ) from e


# ── Fetch + parse HTML ────────────────────────────────────

def fetch_page_text(url: str) -> str:
    # Try HTTPX first
    try:
        html = fetch_with_httpx(url)

    # If HTTPX fails, fall back to curl_cffi
    except ScrapeError as first_error:
        print(f"HTTPX failed: {first_error}")
        print("Trying curl_cffi HTTP request...")

        try:
            html = fetch_with_curl(url)

        except ScrapeError as second_error:
            raise ScrapeHTTPError(
                f"Both HTTP methods failed. "
                f"HTTPX: {first_error}; "
                f"curl_cffi: {second_error}"
            ) from second_error

    soup = BeautifulSoup(html, "html.parser")

    for tag in soup([
        "script",
        "style",
        "nav",
        "footer",
        "header",
        "noscript",
    ]):
        tag.decompose()

    text = soup.get_text(
        separator=" ",
        strip=True,
    )

    text = " ".join(text.split())

    if not text:
        raise ScrapeError(
            "Page downloaded successfully, but no readable text was found."
        )

    # Keep only first 8000 chars for token limit
    return text[:8000]


# ── Claude extraction ─────────────────────────────────────

def extract_job_data(text: str) -> dict:
    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": EXTRACT_PROMPT + text,
                }
            ],
        )

        raw = message.content[0].text.strip()

        # Strip markdown code fences
        if raw.startswith("```"):
            raw = raw.strip("`").strip()

            if raw.startswith("json"):
                raw = raw[4:].strip()

        return json.loads(raw)

    except json.JSONDecodeError as e:
        raise ExtractionError(
            f"Claude returned invalid JSON: {raw}"
        ) from e

    except anthropic.APIError as e:
        raise ExtractionError(
            f"Claude API error: {e}"
        ) from e


# ── Main public scraper function ──────────────────────────

def scrape_job_url(url: str) -> dict:
    text = fetch_page_text(url)

    data = extract_job_data(text)

    data["url"] = url

    return data
