"""
SCOUT by HVM — Job Scraping Pipeline
Scrapes LinkedIn, Indeed, Glassdoor, Google Jobs via python-jobspy.
Scores, deduplicates, and saves to data/jobs.json.
"""

import sys
import os
import math
import traceback

sys.path.insert(0, os.path.dirname(__file__))

import config
from utils import (
    generate_job_id, score_relevance, deduplicate_jobs,
    load_json, save_json, log_entry, now_iso, today_str,
)

try:
    from jobspy import scrape_jobs
except ImportError:
    print("ERROR: python-jobspy not installed. Run: pip install python-jobspy")
    sys.exit(1)


def scrape_all():
    """Run the full scraping pipeline."""
    log_entry("Starting daily job scrape")
    all_new_jobs = []
    errors = []

    for query in config.SEARCH_QUERIES:
        for location in config.LOCATIONS:
            try:
                print(f"  Scraping: '{query}' in '{location}'...")
                df = scrape_jobs(
                    site_name=config.SITES,
                    search_term=query,
                    location=location,
                    results_wanted=config.RESULTS_PER_QUERY,
                    hours_old=config.HOURS_OLD,
                    country_indeed="India",
                    description_format="markdown",
                )

                if df is None or df.empty:
                    continue

                for _, row in df.iterrows():
                    job = {}
                    # Core fields
                    job["title"] = row.get("title", "")
                    job["company"] = row.get("company_name", "") or row.get("company", "")
                    job["company_url"] = row.get("company_url", "")
                    job["job_url"] = row.get("job_url", "")
                    job["location"] = row.get("location", "")
                    job["is_remote"] = bool(row.get("is_remote", False))
                    job["description"] = row.get("description", "")
                    job["job_type"] = row.get("job_type", "")
                    job["source"] = row.get("site", "")
                    job["date_posted"] = str(row.get("date_posted", ""))
                    job["emails"] = row.get("emails", []) if isinstance(row.get("emails"), list) else []

                    # Salary
                    min_amt = row.get("min_amount")
                    max_amt = row.get("max_amount")
                    job["min_amount"] = float(min_amt) if min_amt and not (isinstance(min_amt, float) and math.isnan(min_amt)) else None
                    job["max_amount"] = float(max_amt) if max_amt and not (isinstance(max_amt, float) and math.isnan(max_amt)) else None
                    job["currency"] = row.get("currency", "")
                    job["salary_source"] = row.get("salary_source", "")

                    # Internal fields
                    job["_id"] = generate_job_id(
                        job["title"], job["company"], job["location"]
                    )
                    job["_scraped_at"] = now_iso()
                    job["_scraped_date"] = today_str()
                    job["_search_query"] = query
                    job["_relevance_score"] = score_relevance(job, config)
                    job["_status"] = "new"
                    job["_tailored"] = False
                    job["_outreach_drafted"] = False
                    job["_outreach_sent"] = False

                    if job["_relevance_score"] >= config.MIN_RELEVANCE_SCORE:
                        all_new_jobs.append(job)

            except Exception as e:
                err_msg = f"Scrape failed: '{query}' @ '{location}': {e}"
                errors.append(err_msg)
                log_entry(err_msg, "error")
                traceback.print_exc()

    # Deduplicate within this run
    seen = {}
    for j in all_new_jobs:
        seen[j["_id"]] = j
    all_new_jobs = list(seen.values())

    # Merge with existing jobs
    existing_data = load_json("jobs.json") or {"last_updated": "", "total_jobs": 0, "jobs": []}
    existing_jobs = existing_data.get("jobs", [])
    merged = deduplicate_jobs(all_new_jobs, existing_jobs)

    # Sort by relevance score (highest first)
    merged.sort(key=lambda j: j.get("_relevance_score", 0), reverse=True)

    # Save
    output = {
        "last_updated": now_iso(),
        "total_jobs": len(merged),
        "new_today": len(all_new_jobs),
        "jobs": merged,
    }
    save_json("jobs.json", output)

    log_entry(
        f"Scrape complete: {len(all_new_jobs)} new jobs found, "
        f"{len(merged)} total after dedup, {len(errors)} errors"
    )
    print(f"\nDone! {len(all_new_jobs)} new jobs, {len(merged)} total.")
    return output


if __name__ == "__main__":
    scrape_all()
