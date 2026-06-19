import re
from typing import Optional
import requests
from bs4 import BeautifulSoup

COMMON_CAREERS_PATHS = [
    "/careers",
    "/jobs",
    "/career",
    "/about/careers",
    "/join-us",
    "/joinus",
    "/work-with-us",
]


def parse_linkedin_html_for_company(html: str) -> dict:
    """Heuristic parsing of LinkedIn job HTML to extract company name and website if present."""
    soup = BeautifulSoup(html, "html.parser")
    # Try meta tags first
    company = None
    website = None
    og_site = soup.find("meta", property="og:site_name")
    if og_site and og_site.get("content"):
        company = og_site["content"].strip()

    # Try common LinkedIn selectors
    selectors = [
        "a.topcard__org-name-link",
        "a.topcard__org-name-link span",
        "span.topcard__org-name-link",
    ]
    for sel in selectors:
        el = soup.select_one(sel)
        if el and el.get_text(strip=True):
            company = company or el.get_text(strip=True)
            break

    # company website sometimes appears as a link with hostname or via 'companyWebsite'
    link_candidates = soup.find_all("a", href=True)
    for a in link_candidates:
        href = a["href"]
        if href.startswith("http") and ("company" in a.get_text(" ").lower() or "website" in a.get_text(" ").lower()):
            website = website or href
            break

    # fallback: find any external link that looks like company homepage
    for a in link_candidates:
        href = a["href"]
        if href.startswith("http") and not href.startswith("https://www.linkedin.com"):
            website = website or href
            break

    return {"company": company, "company_website": website}


def find_careers_page(company_url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    """Given company root URL, attempt to locate a careers page using heuristics."""
    s = session or requests.Session()
    def try_url(url):
        try:
            r = s.get(url, timeout=10)
            if r.status_code == 200:
                return r.text
        except Exception:
            return None

    # Normalize
    if not company_url.startswith("http"):
        company_url = "https://" + company_url.lstrip("/")
    base = company_url.rstrip("/")

    # Check common paths
    for path in COMMON_CAREERS_PATHS:
        url = base + path
        html = try_url(url)
        if html:
            return url

    # fetch homepage and scan links
    homepage = try_url(base + "/")
    if not homepage:
        return None
    soup = BeautifulSoup(homepage, "html.parser")
    for a in soup.find_all("a", href=True):
        text = a.get_text(" ").lower()
        href = a["href"]
        if any(k in text for k in ["career", "careers", "job", "jobs", "join"] ) or re.search(r"/caree?r?s?/?", href):
            if href.startswith("http"):
                return href
            # relative
            return base + href if href.startswith("/") else base + "/" + href

    return None


def find_first_opening_on_career_page(career_url: str, session: Optional[requests.Session] = None) -> Optional[str]:
    s = session or requests.Session()
    try:
        r = s.get(career_url, timeout=10)
        r.raise_for_status()
    except Exception:
        return None
    soup = BeautifulSoup(r.text, "html.parser")
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = a.get_text(" ").lower()
        if any(k in text for k in ["apply", "job", "opening", "position"]) or re.search(r"/jobs?/|/openings?/,", href):
            if href.startswith("http"):
                return href
            base = career_url.rstrip("/")
            return base + href if href.startswith("/") else base + "/" + href
    return None
