#!/usr/bin/env python3
"""
Populate the jobs database from cleaned job JSON file.
"""

import sqlite3
import json
from pathlib import Path
import argparse
from typing import List, Dict

from scraper.job_utils import clean_job_record, validate_job_record


def load_jobs(json_path: Path) -> List[Dict]:
    """Load jobs from JSON file."""
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def insert_jobs(db_path: Path, jobs: List[Dict]) -> None:
    """
    Insert jobs into the database.
    Uses REPLACE to handle duplicates (same jobUrl).
    
    Args:
        db_path: Path to database file
        jobs: List of job dictionaries
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    skipped = 0
    
    for job in jobs:
        cleaned_job = clean_job_record(job)
        if not validate_job_record(cleaned_job):
            skipped += 1
            continue

        job_url = cleaned_job["jobUrl"]
        job_title = cleaned_job["jobTitle"]
        company_name = cleaned_job["companyName"]
        company_url = cleaned_job.get("companyUrl")
        careers_page_url = cleaned_job.get("careersPageUrl")
        source = cleaned_job["source"]
        source_hash = cleaned_job["source_hash"]
        
        # Check if job already exists
        cursor.execute("SELECT COUNT(*) FROM jobs WHERE jobUrl = ?", (job_url,))
        exists = cursor.fetchone()[0] > 0
        
        try:
            cursor.execute("""
                INSERT INTO jobs
                (jobUrl, jobTitle, companyName, companyUrl, careersPageUrl, source, source_hash, last_seen_at, updated_at, is_active)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, 1)
                ON CONFLICT(jobUrl) DO UPDATE SET
                    jobTitle = excluded.jobTitle,
                    companyName = excluded.companyName,
                    companyUrl = excluded.companyUrl,
                    careersPageUrl = excluded.careersPageUrl,
                    source = excluded.source,
                    source_hash = excluded.source_hash,
                    last_seen_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = 1
            """, (job_url, job_title, company_name, company_url, careers_page_url, source, source_hash))
            
            if exists:
                updated += 1
            else:
                inserted += 1
        except sqlite3.Error as e:
            print(f"Error inserting job {job_url}: {e}")
            skipped += 1
    
    conn.commit()
    conn.close()
    
    print(f"Database population complete:")
    print(f"  Inserted: {inserted} new jobs")
    print(f"  Updated: {updated} existing jobs")
    print(f"  Skipped: {skipped} invalid entries")
    print(f"  Total: {len(jobs)} jobs processed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate jobs database from JSON")
    parser.add_argument(
        "--jobs",
        type=Path,
        default=Path("scraped_careers_jobs_list_cleaned.json"),
        help="Path to cleaned jobs JSON file"
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("jobs.db"),
        help="Path to database file"
    )
    args = parser.parse_args()
    
    # Check files exist
    if not args.jobs.exists():
        raise SystemExit(f"Jobs file not found: {args.jobs}")
    
    if not args.db.exists():
        raise SystemExit(f"Database not initialized. Run: python init_jobs_db.py")
    
    # Load and insert jobs
    jobs = load_jobs(args.jobs)
    print(f"Loaded {len(jobs)} jobs from {args.jobs}")
    
    insert_jobs(args.db, jobs)


if __name__ == "__main__":
    main()
