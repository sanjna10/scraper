#!/usr/bin/env python3
"""
Refresh jobs from career pages recorded in the database.
This script scrapes each unique career page, inserts new jobs, and marks missing jobs inactive.
"""

import argparse
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

from scraper.job_utils import canonicalize_url, clean_job_record, validate_job_record


JOB_KEYWORDS = [
    "job",
    "position",
    "opening",
    "role",
    "engineer",
    "developer",
    "designer",
    "manager",
    "analyst",
    "consultant",
    "specialist",
    "architect",
    "scientist",
    "product",
    "marketing",
    "sales",
    "finance",
]

UNWANTED_TEXT = [
    "follow us",
    "instagram",
    "search jobs",
    "explore jobs",
    "explore roles",
    "open roles",
    "apply now",
    "view all",
    "see all",
    "careers",
    "hiring",
    "job opportunities",
    "social media",
    "facebook",
    "twitter",
    "linkedin",
    "subscribe",
    "newsletter",
    "contact us",
    "back to",
    "home",
    "help",
    "faq",
    "privacy",
    "terms",
    "cookie",
]


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip()).replace("\u00a0", " ").strip()


def ensure_schema(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(jobs)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    if "source_hash" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN source_hash TEXT")
    if "is_active" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN is_active BOOLEAN DEFAULT 1")
    if "last_seen_at" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN last_seen_at TIMESTAMP")
    if "updated_at" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN updated_at TIMESTAMP")
    if "removed_at" not in existing_columns:
        cursor.execute("ALTER TABLE jobs ADD COLUMN removed_at TIMESTAMP")

    conn.commit()
    conn.close()


def get_unique_career_pages(db_path: Path) -> List[Tuple[str, str, str]]:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT careersPageUrl, companyName, companyUrl FROM jobs WHERE careersPageUrl IS NOT NULL"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def fetch_page(url: str, session: requests.Session) -> Optional[str]:
    try:
        response = session.get(url, timeout=15)
        response.raise_for_status()
        return response.text
    except Exception:
        return None


def looks_like_job_title(text: str) -> bool:
    cleaned = normalize_text(text)
    if len(cleaned) < 5 or len(cleaned) > 200:
        return False
    lower = cleaned.lower()
    if any(unwanted in lower for unwanted in UNWANTED_TEXT):
        return False
    if any(keyword in lower for keyword in JOB_KEYWORDS):
        return True
    return False


def extract_jobs_from_careers_page(html: str, careers_url: str, company_name: str, company_url: str) -> List[Dict]:
    soup = BeautifulSoup(html, "html.parser")
    jobs: List[Dict] = []
    seen: set = set()

    # Search anchors with job-related text
    for a in soup.find_all("a", href=True):
        text = normalize_text(a.get_text(" "))
        href = a["href"].strip()
        if not text:
            continue
        if not looks_like_job_title(text):
            continue
        if href.lower().startswith("javascript:"):
            continue

        if href.startswith("/"):
            base = careers_url.split("?")[0].rstrip("/")
            job_url = base + href
        elif href.startswith("http"):
            job_url = href
        else:
            base = careers_url.rstrip("/")
            job_url = base + "/" + href

        job_url = job_url.split("#")[0]
        if job_url in seen:
            continue
        seen.add(job_url)

        jobs.append(
            {
                "jobUrl": job_url,
                "jobTitle": text,
                "companyName": company_name,
                "companyUrl": company_url,
                "careersPageUrl": careers_url,
                "source": "web_scrape",
            }
        )

    # Fallback: search job blocks for title-like patterns
    if not jobs:
        for selector in ["div", "article", "li", "section"]:
            for block in soup.select(selector):
                title_text = normalize_text(block.get_text(" "))
                if looks_like_job_title(title_text) and title_text not in seen:
                    jobs.append(
                        {
                            "jobUrl": careers_url,
                            "jobTitle": title_text[:200],
                            "companyName": company_name,
                            "companyUrl": company_url,
                            "careersPageUrl": careers_url,
                            "source": "web_scrape",
                        }
                    )
                    seen.add(title_text)
                    if len(jobs) >= 10:
                        break
            if jobs:
                break

    return jobs


def sync_career_page_jobs(db_path: Path, careers_url: str, scraped_jobs: List[Dict], now: str) -> Tuple[int, int, int]:
    careers_page_url = canonicalize_url(careers_url)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT jobUrl FROM jobs WHERE careersPageUrl = ?", (careers_page_url,))
    existing = {row[0] for row in cursor.fetchall()}

    inserted = 0
    updated = 0
    deactivated = 0
    skipped = 0
    scraped_urls = set()

    for raw_job in scraped_jobs:
        cleaned_job = clean_job_record({**raw_job, "careersPageUrl": careers_page_url})
        if not validate_job_record(cleaned_job):
            skipped += 1
            continue

        job_url = cleaned_job["jobUrl"]
        job_title = cleaned_job["jobTitle"]
        company_name = cleaned_job["companyName"]
        company_url = cleaned_job.get("companyUrl")
        source = cleaned_job["source"]
        source_hash = cleaned_job["source_hash"]
        scraped_urls.add(job_url)

        if job_url in existing:
            cursor.execute(
                "UPDATE jobs SET jobTitle = ?, companyName = ?, companyUrl = ?, source = ?, source_hash = ?, careersPageUrl = ?, is_active = 1, last_seen_at = ?, updated_at = ?, removed_at = NULL WHERE jobUrl = ?",
                (job_title, company_name, company_url, source, source_hash, careers_page_url, now, now, job_url),
            )
            updated += 1
        else:
            cursor.execute(
                "INSERT INTO jobs (jobUrl, jobTitle, companyName, companyUrl, careersPageUrl, source, source_hash, is_active, last_seen_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (job_url, job_title, company_name, company_url, careers_page_url, source, source_hash, now, now),
            )
            inserted += 1

    # Deactivate jobs no longer found on the careers page
    missing_urls = existing - scraped_urls
    if missing_urls:
        cursor.executemany(
            "UPDATE jobs SET is_active = 0, updated_at = ?, removed_at = ? WHERE jobUrl = ? AND is_active = 1",
            [(now, now, url) for url in missing_urls],
        )
        deactivated = cursor.rowcount

    conn.commit()
    conn.close()
    return inserted, updated, deactivated

    conn.commit()
    conn.close()
    return inserted, updated, deactivated


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh jobs from career pages in the database.")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("jobs.db"),
        help="Path to jobs database",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of career pages to refresh",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress",
    )
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}")

    ensure_schema(args.db)

    pages = get_unique_career_pages(args.db)
    if args.limit:
        pages = pages[: args.limit]

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
        }
    )

    total_inserted = 0
    total_updated = 0
    total_deactivated = 0

    now = datetime.utcnow().isoformat(sep=" ", timespec="seconds")

    for idx, (careers_url, company_name, company_url) in enumerate(pages, start=1):
        careers_url = canonicalize_url(careers_url)
        print(f"[{idx}/{len(pages)}] Refreshing {company_name} | {careers_url}")
        html = fetch_page(careers_url, session)
        if not html:
            print(f"  ✗ Failed to fetch careers page")
            continue

        scraped_jobs = extract_jobs_from_careers_page(html, careers_url, company_name, company_url)
        print(f"  → Found {len(scraped_jobs)} scraped jobs")
        inserted, updated, deactivated = sync_career_page_jobs(args.db, careers_url, scraped_jobs, now)
        total_inserted += inserted
        total_updated += updated
        total_deactivated += deactivated
        if args.verbose:
            print(f"  + inserted={inserted}, updated={updated}, deactivated={deactivated}")

    print("\nRefresh complete")
    print(f"Inserted: {total_inserted}")
    print(f"Updated: {total_updated}")
    print(f"Deactivated: {total_deactivated}")


if __name__ == "__main__":
    main()
