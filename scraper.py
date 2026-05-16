import os
import json
import httpx
from bs4 import BeautifulSoup
import anthropic

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

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


def fetch_page_text(url: str) -> str:
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15) as client_http:
        resp = client_http.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    text = soup.get_text(separator=" ", strip=True)
    # Keep only first 8000 chars to stay within token limits
    return " ".join(text.split())[:8000]


def extract_job_data(text: str) -> dict:
    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": EXTRACT_PROMPT + text}],
    )
    raw = message.content[0].text.strip()
    # Strip markdown code fences if present
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw)


def scrape_job_url(url: str) -> dict:
    text = fetch_page_text(url)
    data = extract_job_data(text)
    data["url"] = url
    return data
