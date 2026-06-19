#!/usr/bin/env python3
"""
Initialize the jobs database schema.
Creates tables for tracking jobs and their availability status.
"""

import sqlite3
from pathlib import Path
import argparse


DB_PATH = Path("jobs.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    jobUrl TEXT PRIMARY KEY,
    jobTitle TEXT NOT NULL,
    companyName TEXT NOT NULL,
    companyUrl TEXT,
    careersPageUrl TEXT,
    source TEXT DEFAULT 'web_scrape',
    source_hash TEXT,
    is_active BOOLEAN DEFAULT 1,
    last_seen_at TIMESTAMP,
    updated_at TIMESTAMP,
    removed_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_status_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jobUrl TEXT NOT NULL,
    status TEXT DEFAULT 'unknown',
    http_status INTEGER,
    is_available BOOLEAN,
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    error_message TEXT,
    FOREIGN KEY (jobUrl) REFERENCES jobs(jobUrl) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS job_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    jobUrl TEXT NOT NULL,
    status_change TEXT,
    from_status TEXT,
    to_status TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (jobUrl) REFERENCES jobs(jobUrl) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(companyName);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_status_checks_job ON job_status_checks(jobUrl);
CREATE INDEX IF NOT EXISTS idx_status_checks_date ON job_status_checks(checked_at);
"""


def initialize_db(db_path: Path = DB_PATH, force: bool = False) -> None:
    """
    Initialize the database with schema.
    
    Args:
        db_path: Path to the database file
        force: If True, recreate the database (WARNING: deletes existing data)
    """
    if force and db_path.exists():
        db_path.unlink()
        print(f"Deleted existing database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Execute schema
    for statement in SCHEMA.split(";"):
        statement = statement.strip()
        if statement:
            cursor.execute(statement)
    
    conn.commit()
    conn.close()
    
    print(f"Database initialized: {db_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialize the jobs database")
    parser.add_argument(
        "--db",
        type=Path,
        default=DB_PATH,
        help="Path to database file"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate database (deletes existing data)"
    )
    args = parser.parse_args()
    
    initialize_db(args.db, args.force)
