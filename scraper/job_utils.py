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


def is_likely_job_posting(job_url: str, job_title: str = "") -> bool:
    """
    Heuristic to decide whether a URL refers to an individual job posting
    (vs. a generic careers/listing page). Returns True if the URL looks
    like a job detail page.

    Heuristics used:
    - Last path segment is a numeric id (3+ digits) or a long hex/uuid-like string
    - Query string contains id/job/position indicators
    - Path contains job/apply/position keywords
    - Fallback to job-title keywords (e.g. 'engineer', 'developer') if present
    """
    if not job_url:
        return False

    try:
        url = canonicalize_url(job_url)
    except Exception:
        url = job_url or ""

    parsed = urlparse(url)
    path = (parsed.path or "").rstrip("/")
    last = path.split("/")[-1] if path else ""

    # Check query string for id-like parameters
    qs = (parsed.query or "").lower()
    if qs:
        if re.search(r'(\b(job|id|position|posting)\b)=', qs):
            return True
        if re.search(r'\b[0-9]{3,}\b', qs):
            return True

    # Last path segment patterns
    if re.fullmatch(r'[0-9]{3,}', last):
        return True
    if re.fullmatch(r'[0-9a-f]{6,}', last, re.IGNORECASE):
        return True
    if re.fullmatch(r'[0-9a-fA-F\-]{8,36}', last):
        return True

    # Path or last segment containing job/apply keywords
    if re.search(r'\b(job|apply|position|opening|posting)\b', path, re.IGNORECASE):
        return True

    # Fallback: title contains job-like keywords and appears descriptive
    if job_title and len(job_title) > 6 and re.search(r'engineer|developer|designer|manager|analyst|sales|marketing|software|senior|junior', job_title, re.IGNORECASE):
        return True

    return False
