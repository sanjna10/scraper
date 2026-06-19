import argparse
import json
import os
import sys
from pathlib import Path

# When running the CLI directly as a script (python3 scraper/main.py), ensure the package root
# is on sys.path so imports like `from scraper...` work consistently.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scraper.linkedin_adapter import fetch_linkedin_job_html
from scraper.company_crawler import (
    parse_linkedin_html_for_company,
    find_careers_page,
    find_first_opening_on_career_page,
)
from scraper.apify_adapter import fetch_company_websites_from_apify, fetch_linkedin_jobs_from_apify


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", help="LinkedIn job URL")
    parser.add_argument("--use-api", action="store_true", help="Call configured third-party API to fetch LinkedIn HTML")
    parser.add_argument("--apify-search", action="store_true", help="Run Apify LinkedIn job search instead of a single URL")
    parser.add_argument("--apify-company-websites", action="store_true", help="Run Apify company website lookup actor")
    parser.add_argument("--query", help="Search query for Apify actor")
    parser.add_argument("--location", help="Location for Apify actor")
    parser.add_argument("--jobs-to-fetch", type=int, default=10, help="Number of jobs to fetch via Apify")
    parser.add_argument("--companies", help="JSON array of LinkedIn company URLs for company website lookup")
    parser.add_argument("--apify-token", help="Apify API token")
    args = parser.parse_args()

    if args.apify_company_websites:
        if not args.companies:
            raise SystemExit("--companies is required for --apify-company-websites")
        token = args.apify_token or os.environ.get("APIFY_TOKEN")
        companies = json.loads(args.companies)
        results = fetch_company_websites_from_apify(companies=companies, apify_token=token)
        print(json.dumps(results, indent=2))
        return

    if args.apify_search:
        if not args.query or not args.location:
            raise SystemExit("--query and --location are required for --apify-search")
        token = args.apify_token or os.environ.get("APIFY_TOKEN")
        jobs = fetch_linkedin_jobs_from_apify(
            query=args.query,
            location=args.location,
            jobs_to_fetch=args.jobs_to_fetch,
            apify_token=token,
        )
        print(json.dumps(jobs, indent=2))
        return

    if not args.url:
        raise SystemExit("--url is required unless --apify-search is used")

    html = fetch_linkedin_job_html(args.url, use_api=args.use_api)
    info = parse_linkedin_html_for_company(html)
    company = info.get("company")
    company_site = info.get("company_website")

    result = {"company": company, "company_website": company_site, "career_page": None, "opening": None}

    if company_site:
        career = find_careers_page(company_site)
        result["career_page"] = career
        if career:
            opening = find_first_opening_on_career_page(career)
            result["opening"] = opening

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
