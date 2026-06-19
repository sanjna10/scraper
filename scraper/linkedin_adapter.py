import os
import requests

THIRD_PARTY_API_URL = os.environ.get("THIRD_PARTY_API_URL")
THIRD_PARTY_API_KEY = os.environ.get("THIRD_PARTY_API_KEY")


def fetch_linkedin_job_html(linkedin_url: str, use_api: bool = False) -> str:
    """Fetch LinkedIn job page HTML.

    If `use_api` is True, POST to THIRD_PARTY_API_URL with JSON {url, api_key}.
    Otherwise, return the mock sample HTML file.
    """
    if use_api:
        if not THIRD_PARTY_API_URL:
            raise RuntimeError("THIRD_PARTY_API_URL not configured")
        payload = {"url": linkedin_url}
        if THIRD_PARTY_API_KEY:
            payload["api_key"] = THIRD_PARTY_API_KEY
        resp = requests.post(THIRD_PARTY_API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        # Accept either raw HTML body or JSON {html: ...}
        try:
            j = resp.json()
            return j.get("html") or resp.text
        except ValueError:
            return resp.text

    # fallback: use sample file
    sample = os.path.join(os.path.dirname(__file__), "..", "samples", "mock_linkedin.html")
    sample = os.path.abspath(sample)
    with open(sample, "r", encoding="utf-8") as f:
        return f.read()
