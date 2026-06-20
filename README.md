# LinkedIn Job Scraper Pipeline

A Python pipeline for collecting LinkedIn job and company data, scraping company careers pages, cleaning results, persisting jobs to SQLite, and checking job availability.

## Overview

This repository supports two main workflows:

1. **Apify-driven flow**
   - Search LinkedIn jobs using Apify.
   - Resolve company websites from LinkedIn company URLs.
   - Discover careers pages and scrape job listings.
   - Clean and canonicalize the scraped job records.
   - Persist jobs in SQLite.
   - Refresh listings and verify live job availability.

2. **Direct LinkedIn URL flow**
   - Fetch a LinkedIn job page.
   - Extract company metadata.
   - Discover the company's careers page.
   - Optionally find a first opening link.

## Flow Chart

```mermaid
flowchart LR
   A[Apify Job Search] --> B[Company Website Lookup]
   B --> C[Find Careers Page]
   C --> D[Scrape Careers Page Jobs]
   D --> E[Clean & Canonicalize (scraper/job_utils.py)]
   E --> F[SQLite DB (jobs table)]
   F --> G[Refresh Careers Pages (refresh_careers_jobs_db.py)]
   F --> H[Check Job Availability (check_job_availability.py)]
   G --> F
   H --> F
```

## Repository Structure

 - `scraper/`
  - `main.py` — CLI entry point for the package.
  - `apify_adapter.py` — Apify actor wrappers and call helpers.
  - `job_utils.py` — job normalization, URL canonicalization, and validation utilities.
  - `linkedin_adapter.py` — fetch LinkedIn HTML by API or sample file.
  - `company_crawler.py` — parse LinkedIn HTML and discover careers/opening pages.
- `fetch_company_websites_from_job_output.py` — convert Apify job search output into company website lookup input.
- `scrape_careers_pages.py` — discover careers pages and scrape job listings from company websites.
- `clean_scraped_careers_jobs.py` — normalize, validate, dedupe, and write cleaned jobs JSON.
- `init_jobs_db.py` — initialize the SQLite database structure.
- `populate_jobs_db.py` — insert cleaned jobs into SQLite with conflict handling.
- `refresh_careers_jobs_db.py` — refresh jobs from active career pages and deactivate missing jobs.
- `check_job_availability.py` — run periodic job availability checks.
- `samples/mock_linkedin.html` — fallback sample HTML for LinkedIn scraping.

## Detailed File Flow

### `scraper/main.py`

The package CLI entry point.

- Ensures the package root is on `sys.path` when run directly.
- Supports these flows:
  - `--apify-search` — launch Apify LinkedIn job search.
  - `--apify-company-websites` — launch Apify company website lookup.
  - `--url` — parse a LinkedIn job page directly.
- Uses:
  - `scraper.apify_adapter` for Apify API calls.
  - `scraper.linkedin_adapter` for LinkedIn HTML fetching.
  - `scraper.company_crawler` for page parsing.

### `scraper/apify_adapter.py`

Handles Apify actor execution.

Functions:

- `_get_apify_client(apify_token)` — load the Apify API token from environment or parameter.
- `_run_actor(client, actor_id, run_input)` — call an Apify actor and return dataset items.
- `fetch_linkedin_jobs_from_apify(...)` — run the LinkedIn job search actor.
- `fetch_company_websites_from_apify(...)` — run the company website lookup actor.

### `fetch_company_websites_from_job_output.py`

Transforms Apify job search JSON into company lookup input.

Functions:

- `load_company_urls(job_output_path)` — load Apify job output and extract unique `companyUrl` values.
- `main()` — invoke `fetch_company_websites_from_apify()` and write the results.

### `scrape_careers_pages.py`

Finds careers pages and scrapes job listings.

Functions:

- `find_careers_page(company_url, company_website, session)`
  - tries common careers page paths like `/careers`, `/jobs`, `/join-us`.
  - scans the homepage for career-related anchor links.
  - returns a career page URL or `None`.

- `scrape_jobs_from_careers_page(careers_url, company_name, company_url, session)`
  - fetches career page HTML.
  - searches for job-related links and containers.
  - builds job dictionaries including `jobUrl`, `jobTitle`, `companyName`, `companyUrl`, `careersPageUrl`, and `source`.
  - provides a fallback for extracting job-like text.

- `process_company(company, session, verbose)`
  - locates the career page and scrapes jobs for one company.
  - augments the company record with `careersPageUrl` and `scrapedJobs`.

- `main()`
  - loads company profiles from JSON.
  - processes each company.
  - writes enriched output and optional jobs-only JSON.

### `clean_scraped_careers_jobs.py`

Normalizes raw scraped jobs and writes cleaned JSON.

Functions:

- `load_raw_jobs(path)` — load raw scraped job JSON.
- `clean_jobs(raw_jobs)` — clean, validate, and dedupe jobs.
- `save_cleaned_jobs(path, jobs)` — write cleaned JSON.
- `main()` — run the cleaning process and print stats.

### `scraper/job_utils.py`

Shared utility functions for job records.

Functions:

- `normalize_text(text)` — trim and collapse whitespace.
- `canonicalize_url(url)` — normalize URLs and remove tracking parameters.
- `compute_source_hash(job)` — compute SHA256 fingerprint for deduplication.
- `clean_job_record(job)` — canonicalize fields and attach `source_hash`.
- `validate_job_record(job)` — ensure required fields exist.

### `init_jobs_db.py`

Creates the SQLite job database.

Functions:

- `initialize_db(db_path, force)` — create the tables and optionally recreate the DB.

Schema:

- `jobs`
  - `jobUrl` (PK)
  - `jobTitle`
  - `companyName`
  - `companyUrl`
  - `careersPageUrl`
  - `source`
  - `source_hash`
  - `is_active`
  - `last_seen_at`
  - `updated_at`
  - `removed_at`
  - `scraped_at`
  - `created_at`

- `job_status_checks`
- `job_history`

### `populate_jobs_db.py`

Loads cleaned jobs and writes them into SQLite.

Functions:

- `load_jobs(json_path)` — load cleaned job JSON.
- `insert_jobs(db_path, jobs)` — clean, validate, and upsert jobs into `jobs`.
- `main()` — validate paths and execute insertion.

### `refresh_careers_jobs_db.py`

Refreshes jobs from careers pages and deactivates missing entries.

Functions:

- `ensure_schema(db_path)` — add missing columns for schema compatibility.
- `get_unique_career_pages(db_path)` — query distinct career pages.
- `fetch_page(url, session)` — load page HTML.
- `looks_like_job_title(text)` — heuristics for job title detection.
- `extract_jobs_from_careers_page(html, careers_url, company_name, company_url)` — extract job links from page HTML.
- `sync_career_page_jobs(db_path, careers_url, scraped_jobs, now)` — insert/update/deactivate jobs.
- `main()` — refresh each careers page and update the database.

### `check_job_availability.py`

Runs periodic job availability checks.

Functions:

- `get_pending_jobs(db_path, limit)` — select jobs that need checking.
- `check_job_status(job_url, timeout)` — send an HTTP HEAD request.
- `record_check(db_path, job_url, http_status, is_available, error_msg)` — store checks and history.
- `run_cron(db_path, jobs_to_check, verbose)` — process a batch of jobs.
- `main()` — parse arguments and run the cron task.

### `scraper/linkedin_adapter.py`

Fetches LinkedIn job page HTML.

Functions:

- `fetch_linkedin_job_html(linkedin_url, use_api)`
  - uses a configured third-party API when `use_api=True`.
  - falls back to local sample HTML when not using API.

### `scraper/company_crawler.py`

Parses LinkedIn HTML and discovers career/opening links.

Functions:

- `parse_linkedin_html_for_company(html)` — extract company name and website.
- `find_careers_page(company_url, session)` — locate a careers page from the company website.
- `find_first_opening_on_career_page(career_url, session)` — find the first job opening link.

## End-to-End Flow

### Apify-driven flow

1. Run Apify LinkedIn job search:
   ```bash
   python -m scraper.main --apify-search --query "Software Engineer" --location "USA"
   ```
   - Output can be saved to `apify_software_engineer_usa_20_jobs.json`.

2. Resolve company websites:
   ```bash
   python fetch_company_websites_from_job_output.py --job-output apify_software_engineer_usa_20_jobs.json --output apify_software_engineer_usa_20_company_websites.json
   ```

3. Scrape careers pages:
   ```bash
   python scrape_careers_pages.py --companies-input apify_software_engineer_usa_20_company_websites.json --output scraped_careers_jobs.json --jobs-only scraped_careers_jobs_list.json
   ```

4. Clean scraped jobs:
   ```bash
   python clean_scraped_careers_jobs.py --input scraped_careers_jobs_list.json --output scraped_careers_jobs_list_cleaned.json
   ```

5. Initialize the database:
   ```bash
   python init_jobs_db.py --db jobs.db
   ```

6. Populate the database:
   ```bash
   python populate_jobs_db.py --jobs scraped_careers_jobs_list_cleaned.json --db jobs.db
   ```

7. Refresh career page jobs:
   ```bash
   python refresh_careers_jobs_db.py --db jobs.db --verbose
   ```

8. Check availability:
   ```bash
   python check_job_availability.py --db jobs.db --jobs 50 --verbose
   ```

### Direct LinkedIn URL flow

1. Run:
   ```bash
   python -m scraper.main --url "<linkedin_job_url>"
   ```

2. Optionally use API HTML fetching:
   ```bash
   python -m scraper.main --url "<linkedin_job_url>" --use-api
   ```

## Notes

- Keep `apify_software_engineer_usa_20_jobs.json` and `apify_software_engineer_usa_20_company_websites.json` for API evidence.
- The cleaned JSON file `scraped_careers_jobs_list_cleaned.json` is the validated input for database population.
- `jobs.db` tracks active jobs, refresh data, and availability history.

## Requirements

- Python 3.13+
- `requests`
- `beautifulsoup4`
- `apify-client`

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## License

This repository is provided as a prototype for LinkedIn job scraping and career page extraction.
