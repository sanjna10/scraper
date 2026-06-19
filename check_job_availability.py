#!/usr/bin/env python3
"""
Cron job script to check if jobs still exist.
Queries each job URL and records availability status.
"""

import sqlite3
import requests
from pathlib import Path
import argparse
from datetime import datetime
from typing import Tuple, Optional


def get_pending_jobs(db_path: Path, limit: int = None) -> list:
    """
    Get jobs that need status checking.
    Prioritizes jobs that haven't been checked or were checked long ago.
    
    Args:
        db_path: Path to database
        limit: Max jobs to check in this run
    
    Returns:
        List of (jobUrl, jobTitle, companyName) tuples
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = """
    SELECT DISTINCT j.jobUrl, j.jobTitle, j.companyName
    FROM jobs j
    LEFT JOIN job_status_checks sc ON j.jobUrl = sc.jobUrl
    GROUP BY j.jobUrl
    ORDER BY MAX(sc.checked_at) ASC NULLS FIRST
    """
    
    if limit:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    jobs = cursor.fetchall()
    conn.close()
    
    return jobs


def check_job_status(job_url: str, timeout: int = 10) -> Tuple[int, bool, Optional[str]]:
    """
    Check if a job URL is still accessible.
    
    Args:
        job_url: URL to check
        timeout: Request timeout in seconds
    
    Returns:
        Tuple of (http_status, is_available, error_message)
    """
    try:
        response = requests.head(job_url, timeout=timeout, allow_redirects=True)
        http_status = response.status_code
        is_available = http_status == 200
        error_msg = None
    except requests.Timeout:
        http_status = None
        is_available = False
        error_msg = "Timeout"
    except requests.ConnectionError:
        http_status = None
        is_available = False
        error_msg = "Connection error"
    except Exception as e:
        http_status = None
        is_available = False
        error_msg = str(e)
    
    return http_status, is_available, error_msg


def record_check(db_path: Path, job_url: str, http_status: int, is_available: bool, error_msg: str) -> None:
    """
    Record a status check in the database.
    
    Args:
        db_path: Path to database
        job_url: Job URL checked
        http_status: HTTP status code
        is_available: Whether job is available
        error_msg: Error message if any
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Insert status check
    cursor.execute("""
        INSERT INTO job_status_checks (jobUrl, status, http_status, is_available, error_message)
        VALUES (?, ?, ?, ?, ?)
    """, (job_url, "available" if is_available else "unavailable", http_status, is_available, error_msg))
    
    # Check if status changed and record in history
    cursor.execute("""
        SELECT status FROM job_status_checks
        WHERE jobUrl = ?
        ORDER BY checked_at DESC
        LIMIT 2
    """, (job_url,))
    
    results = cursor.fetchall()
    if len(results) >= 2:
        current_status = "available" if is_available else "unavailable"
        previous_status = results[1][0]
        
        if current_status != previous_status:
            cursor.execute("""
                INSERT INTO job_history (jobUrl, status_change, from_status, to_status)
                VALUES (?, ?, ?, ?)
            """, (job_url, "status_changed", previous_status, current_status))
    
    conn.commit()
    conn.close()


def run_cron(db_path: Path, jobs_to_check: int = 50, verbose: bool = False) -> None:
    """
    Run the cron job to check job availability.
    
    Args:
        db_path: Path to database
        jobs_to_check: Number of jobs to check in this run
        verbose: Print detailed output
    """
    if not db_path.exists():
        raise SystemExit(f"Database not found: {db_path}")
    
    jobs = get_pending_jobs(db_path, limit=jobs_to_check)
    
    if not jobs:
        print("No jobs to check")
        return
    
    print(f"Checking {len(jobs)} jobs...")
    print(f"Started at {datetime.now().isoformat()}\n")
    
    available_count = 0
    unavailable_count = 0
    error_count = 0
    
    for i, job in enumerate(jobs, start=1):
        job_url = job[0]
        job_title = job[1][:50]
        company_name = job[2]
        
        # Check status
        http_status, is_available, error_msg = check_job_status(job_url)
        
        # Record result
        record_check(db_path, job_url, http_status, is_available, error_msg)
        
        # Print progress
        status_str = "✓ AVAILABLE" if is_available else "✗ UNAVAILABLE" if http_status else "⚠ ERROR"
        
        if is_available:
            available_count += 1
        elif http_status:
            unavailable_count += 1
        else:
            error_count += 1
        
        if verbose or not is_available:
            print(f"[{i}/{len(jobs)}] {status_str} | {company_name} | {job_title}")
            if error_msg:
                print(f"         Error: {error_msg}")
    
    print(f"\n" + "=" * 60)
    print(f"CRON JOB SUMMARY")
    print(f"=" * 60)
    print(f"Available: {available_count}")
    print(f"Unavailable: {unavailable_count}")
    print(f"Errors: {error_count}")
    print(f"Total checked: {len(jobs)}")
    print(f"Completed at {datetime.now().isoformat()}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Check job availability (cron job)")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path("jobs.db"),
        help="Path to database file"
    )
    parser.add_argument(
        "--jobs",
        type=int,
        default=50,
        help="Number of jobs to check per run"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output"
    )
    args = parser.parse_args()
    
    run_cron(args.db, args.jobs, args.verbose)


if __name__ == "__main__":
    main()
