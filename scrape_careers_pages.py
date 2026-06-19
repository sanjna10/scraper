#!/usr/bin/env python3
"""
Scrape careers pages from company websites and extract job listings.
Reads company profiles from apify output and attempts to find and scrape job openings.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import re


# Common careers page paths
COMMON_CAREERS_PATHS = [
    "/careers",
    "/jobs",
    "/career",
    "/about/careers",
    "/join-us",
    "/joinus",
    "/work-with-us",
    "/hiring",
    "/opportunities",
    "/positions",
]


def find_careers_page(company_url: str, company_website: str, session: requests.Session) -> Optional[str]:
    """
    Attempt to locate a careers page for a company.
    
    Args:
        company_url: LinkedIn company URL
        company_website: Company website URL
        session: Requests session for HTTP calls
    
    Returns:
        URL of careers page if found, None otherwise
    """
    if not company_website:
        return None

    def try_url(url: str) -> Optional[str]:
        try:
            r = session.get(url, timeout=10)
            if r.status_code == 200:
                return r.text
        except Exception as e:
            return None
        return None

    # Normalize base URL
    base = company_website.strip().rstrip("/")
    if not base.startswith("http"):
        base = "https://" + base

    # Try common paths
    for path in COMMON_CAREERS_PATHS:
        url = base + path
        html = try_url(url)
        if html:
            return url

    # Fetch homepage and scan for career links
    try:
        homepage = try_url(base + "/")
        if not homepage:
            return None
        
        soup = BeautifulSoup(homepage, "html.parser")
        for a in soup.find_all("a", href=True):
            text = a.get_text(" ").lower()
            href = a["href"]
            
            # Check if link text contains career-related keywords
            if any(k in text for k in ["career", "careers", "job", "jobs", "join", "hiring"]):
                if href.startswith("http"):
                    return href
                # Handle relative URLs
                if href.startswith("/"):
                    return base + href
                else:
                    return base + "/" + href
    except Exception as e:
        pass

    return None


def scrape_jobs_from_careers_page(
    careers_url: str,
    company_name: str,
    company_url: str,
    session: requests.Session
) -> List[Dict]:
    """
    Scrape job listings from a careers page.
    
    Args:
        careers_url: URL of careers page
        company_name: Name of the company
        company_url: LinkedIn company URL
        session: Requests session
    
    Returns:
        List of job dictionaries
    """
    jobs = []
    
    try:
        r = session.get(careers_url, timeout=10)
        r.raise_for_status()
    except Exception as e:
        print(f"  ⚠ Failed to fetch {careers_url}: {e}", file=sys.stderr)
        return jobs

    try:
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Find all job listings (look for common patterns)
        job_containers = []
        
        # Pattern 1: Job listings in divs/articles with job-related classes
        for selector in [
            "div[class*='job']",
            "article[class*='job']",
            "li[class*='job']",
            "div[class*='position']",
            "div[class*='opening']",
        ]:
            job_containers.extend(soup.select(selector))
        
        # Pattern 2: Look for job titles and links
        job_links = soup.find_all("a", href=True)
        for link in job_links[:50]:  # Limit to first 50 links
            text = link.get_text(strip=True)
            href = link.get("href", "")
            
            # Check if this looks like a job posting link
            if any(k in text.lower() or k in href.lower() for k in ["job", "position", "opening", "role", "engineer", "developer"]):
                if text and len(text) > 3:
                    # Construct full URL
                    if href.startswith("http"):
                        job_url = href
                    elif href.startswith("/"):
                        job_url = careers_url.split("?")[0].rstrip("/") + href
                    else:
                        job_url = careers_url.rstrip("/") + "/" + href
                    
                    job = {
                        "jobUrl": job_url,
                        "jobTitle": text[:200],
                        "companyName": company_name,
                        "companyUrl": company_url,
                        "careersPageUrl": careers_url,
                        "source": "web_scrape",
                    }
                    
                    # Avoid duplicates
                    if not any(j["jobUrl"] == job["jobUrl"] for j in jobs):
                        jobs.append(job)
        
        if not jobs:
            # Fallback: extract any text that looks like a job title
            body_text = soup.get_text()
            lines = body_text.split("\n")
            for line in lines:
                line = line.strip()
                if 10 < len(line) < 200 and any(k in line.lower() for k in ["engineer", "developer", "designer", "manager", "analyst"]):
                    job = {
                        "jobTitle": line,
                        "companyName": company_name,
                        "companyUrl": company_url,
                        "careersPageUrl": careers_url,
                        "source": "web_scrape",
                    }
                    jobs.append(job)
                    if len(jobs) >= 10:
                        break
    
    except Exception as e:
        print(f"  ⚠ Error parsing careers page: {e}", file=sys.stderr)

    return jobs


def process_company(
    company: Dict,
    session: requests.Session,
    verbose: bool = False
) -> Dict:
    """
    Process a single company: find careers page and scrape jobs.
    
    Args:
        company: Company dict from apify output
        session: Requests session
        verbose: Print debug info
    
    Returns:
        Company dict with added careers data
    """
    company_name = company.get("name", "Unknown")
    company_url = company.get("linkedinUrl", "")
    company_website = company.get("website", "")
    
    if verbose:
        print(f"Processing: {company_name}")
    
    # Try to find careers page
    careers_url = find_careers_page(company_url, company_website, session)
    
    if careers_url:
        if verbose:
            print(f"  ✓ Found careers page: {careers_url}")
        
        jobs = scrape_jobs_from_careers_page(careers_url, company_name, company_url, session)
        
        if verbose:
            print(f"  ✓ Scraped {len(jobs)} jobs")
        
        company["careersPageUrl"] = careers_url
        company["scrapedJobs"] = jobs
    else:
        if verbose:
            print(f"  ✗ Could not find careers page")
        company["careersPageUrl"] = None
        company["scrapedJobs"] = []
    
    return company


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape careers pages from company websites and extract job listings."
    )
    parser.add_argument(
        "--companies-input",
        type=Path,
        default=Path("apify_software_engineer_usa_20_company_websites.json"),
        help="Path to company profiles JSON file from Apify.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_careers_jobs.json"),
        help="Path to write scraped jobs JSON.",
    )
    parser.add_argument(
        "--jobs-only",
        type=Path,
        help="Optional: also write a flattened list of just the jobs to this file.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed progress messages.",
    )
    args = parser.parse_args()

    # Load company data
    try:
        with args.companies_input.open("r", encoding="utf-8") as f:
            companies = json.load(f)
    except FileNotFoundError:
        raise SystemExit(f"File not found: {args.companies_input}")
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON in {args.companies_input}: {e}")

    if not isinstance(companies, list):
        companies = [companies]

    print(f"Loaded {len(companies)} companies")

    # Create a session for HTTP requests
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    })

    # Process each company
    enriched_companies = []
    all_jobs = []

    for i, company in enumerate(companies, start=1):
        print(f"\n[{i}/{len(companies)}] {company.get('name', 'Unknown')}")
        
        enriched = process_company(company, session, verbose=args.verbose)
        enriched_companies.append(enriched)
        
        # Collect all jobs
        for job in enriched.get("scrapedJobs", []):
            all_jobs.append(job)

    # Write enriched company data
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(enriched_companies, f, indent=2)
    print(f"\nSaved enriched company data to {args.output}")

    # Write jobs-only file if requested
    if args.jobs_only:
        with args.jobs_only.open("w", encoding="utf-8") as f:
            json.dump(all_jobs, f, indent=2)
        print(f"Saved {len(all_jobs)} jobs to {args.jobs_only}")
    else:
        print(f"Scraped {len(all_jobs)} total jobs from careers pages")

    # Print summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    companies_with_careers = sum(1 for c in enriched_companies if c.get("careersPageUrl"))
    print(f"Companies with careers pages found: {companies_with_careers}/{len(companies)}")
    print(f"Total jobs scraped: {len(all_jobs)}")
    if companies_with_careers > 0:
        avg_jobs = len(all_jobs) / companies_with_careers if companies_with_careers > 0 else 0
        print(f"Average jobs per company: {avg_jobs:.1f}")


if __name__ == "__main__":
    main()
