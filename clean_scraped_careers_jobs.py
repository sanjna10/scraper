#!/usr/bin/env python3
"""
Clean raw scraped careers jobs JSON into a validated, canonicalized jobs file.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

from scraper.job_utils import clean_job_record, validate_job_record


def load_raw_jobs(path: Path) -> List[Dict]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def clean_jobs(raw_jobs: List[Dict]) -> Tuple[List[Dict], int, int, int]:
    cleaned_jobs: List[Dict] = []
    seen_urls = set()
    skipped = 0
    duplicates = 0

    for job in raw_jobs:
        cleaned = clean_job_record(job)
        if not validate_job_record(cleaned):
            skipped += 1
            continue

        # Remove jobs whose URL does not end with a number (keep only URLs ending with digits)
        if not re.search(r"\d+$", cleaned.get("jobUrl", "")):
            skipped += 1
            continue
 

        job_url = cleaned["jobUrl"]
        if job_url in seen_urls:
            duplicates += 1
            continue

        seen_urls.add(job_url)
        cleaned_jobs.append(cleaned)

    return cleaned_jobs, skipped, duplicates, len(raw_jobs)


def save_cleaned_jobs(path: Path, jobs: List[Dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a cleaned jobs JSON file from raw scraped careers job data."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("scraped_careers_jobs_list.json"),
        help="Path to the raw scraped careers jobs JSON file.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("scraped_careers_jobs_list_cleaned.json"),
        help="Path to write the cleaned jobs JSON file.",
    )
    args = parser.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Input file not found: {args.input}")

    raw_jobs = load_raw_jobs(args.input)
    cleaned_jobs, skipped, duplicates, total = clean_jobs(raw_jobs)
    save_cleaned_jobs(args.output, cleaned_jobs)

    print(f"Cleaned jobs written to {args.output}")
    print(f"  Total raw jobs: {total}")
    print(f"  Cleaned jobs: {len(cleaned_jobs)}")
    print(f"  Skipped invalid: {skipped}")
    print(f"  Duplicates removed: {duplicates}")


if __name__ == "__main__":
    main()
