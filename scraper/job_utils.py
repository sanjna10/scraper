import hashlib
import re
from urllib.parse import parse_qsl, quote, urlencode, urlparse, urlunparse

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "gclid",
    "fbclid",
    "yclid",
    "msclkid",
}


def normalize_text(text: str) -> str:
    if text is None:
        return ""
    normalized = re.sub(r"\s+", " ", text.strip())
    return normalized.replace("\u00a0", " ").strip()


def canonicalize_url(url: str) -> str:
    if not url:
        return ""

    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url
    if not urlparse(url).scheme:
        url = "https://" + url.lstrip("/")

    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    # normalize host and default ports
    if netloc.endswith(":80"):
        netloc = netloc[:-3]
    if netloc.endswith(":443"):
        netloc = netloc[:-4]

    path = re.sub(r"/+", "/", parsed.path)
    if path != "/":
        path = path.rstrip("/")

    # remove tracking query params and fragment
    qs = parse_qsl(parsed.query, keep_blank_values=True)
    qs = [(k, v) for (k, v) in qs if k.lower() not in TRACKING_PARAMS]
    qs.sort()
    query = urlencode(qs, doseq=True)

    canonical = urlunparse((scheme, netloc, path, "", query, ""))
    return canonical


def compute_source_hash(job: dict) -> str:
    parts = [
        normalize_text(job.get("jobTitle", "")),
        normalize_text(job.get("companyName", "")),
        canonicalize_url(job.get("companyUrl", "")),
        canonicalize_url(job.get("careersPageUrl", "")),
        normalize_text(job.get("source", "web_scrape")),
    ]
    payload = "|".join(parts).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def clean_job_record(job: dict) -> dict:
    cleaned = {
        "jobUrl": canonicalize_url(job.get("jobUrl", "")),
        "jobTitle": normalize_text(job.get("jobTitle", "")),
        "companyName": normalize_text(job.get("companyName", "")),
        "companyUrl": canonicalize_url(job.get("companyUrl", "")) if job.get("companyUrl") else None,
        "careersPageUrl": canonicalize_url(job.get("careersPageUrl", "")) if job.get("careersPageUrl") else None,
        "source": normalize_text(job.get("source", "web_scrape")) or "web_scrape",
    }
    cleaned["source_hash"] = compute_source_hash(cleaned)
    return cleaned


def validate_job_record(job: dict) -> bool:
    if not isinstance(job, dict):
        return False
    if not job.get("jobUrl"):
        return False
    if not job.get("jobTitle"):
        return False
    if not job.get("companyName"):
        return False
    if len(job.get("jobTitle")) < 5:
        return False
    return True
