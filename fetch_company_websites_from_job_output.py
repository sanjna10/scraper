import argparse
import json
from pathlib import Path
from typing import List

from scraper.apify_adapter import fetch_company_websites_from_apify


def load_company_urls(job_output_path: Path) -> List[str]:
    with job_output_path.open("r", encoding="utf-8") as f:
        jobs = json.load(f)

    company_urls = []
    for job in jobs:
        url = job.get("companyUrl")
        if url and isinstance(url, str):
            company_urls.append(url)

    # Preserve original order while removing duplicates.
    seen = set()
    unique_urls = []
    for url in company_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    return unique_urls


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch company websites for LinkedIn company URLs from job output.")
    parser.add_argument(
        "--job-output",
        type=Path,
        default=Path("apify_test_output.json"),
        help="Path to the Apify job search JSON output file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("apify_company_websites_from_job_output.json"),
        help="Path to write the company website lookup results.",
    )
    parser.add_argument(
        "--apify-token",
        help="Apify API token. If omitted, APIFY_TOKEN environment variable is used.",
    )
    args = parser.parse_args()

    company_urls = load_company_urls(args.job_output)
    if not company_urls:
        raise SystemExit(f"No companyUrl values found in {args.job_output}")

    print(f"Found {len(company_urls)} unique LinkedIn company URLs in {args.job_output}")
    for url in company_urls[:20]:
        print("-", url)
    if len(company_urls) > 20:
        print(f"... and {len(company_urls) - 20} more")

    results = fetch_company_websites_from_apify(
        companies=company_urls,
        apify_token=args.apify_token,
    )

    with args.output.open("w", encoding="utf-8") as out_file:
        json.dump(results, out_file, indent=2)

    print(f"Saved {len(results)} results to {args.output}")


if __name__ == "__main__":
    main()
