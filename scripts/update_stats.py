"""
SCOUT by HVM — Stats Aggregator
Reads jobs.json, outreach.json, tailored/ files and produces stats.json
for the dashboard to consume.
"""

import sys
import os
import glob
from datetime import datetime, timezone, timedelta
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))

from utils import load_json, save_json, log_entry, now_iso, today_str, DATA_DIR


def run_stats():
    """Aggregate all pipeline data into stats.json for the dashboard."""
    log_entry("Updating dashboard stats")

    jobs_data = load_json("jobs.json") or {"jobs": []}
    outreach_data = load_json("outreach.json") or {"drafts": []}
    jobs = jobs_data.get("jobs", [])
    drafts = outreach_data.get("drafts", [])

    # ── Core Metrics ────────────────────────────────────────────
    total_jobs = len(jobs)
    today = today_str()

    new_today = sum(1 for j in jobs if j.get("_scraped_date") == today)
    tailored_count = sum(1 for j in jobs if j.get("_tailored"))
    outreach_drafted = len(drafts)
    outreach_sent = sum(
        1 for d in drafts
        for m in d.get("messages", [])
        if m.get("status") == "sent"
    )
    outreach_pending = sum(
        1 for d in drafts
        for m in d.get("messages", [])
        if m.get("status") == "pending_approval"
    )

    # ── Score Distribution ──────────────────────────────────────
    score_buckets = {"90-100": 0, "70-89": 0, "50-69": 0, "30-49": 0, "0-29": 0}
    for j in jobs:
        s = j.get("_relevance_score", 0)
        if s >= 90:
            score_buckets["90-100"] += 1
        elif s >= 70:
            score_buckets["70-89"] += 1
        elif s >= 50:
            score_buckets["50-69"] += 1
        elif s >= 30:
            score_buckets["30-49"] += 1
        else:
            score_buckets["0-29"] += 1

    # ── Source Breakdown ────────────────────────────────────────
    source_counts = Counter(j.get("source", "unknown") for j in jobs)

    # ── Location Breakdown ──────────────────────────────────────
    location_counts = Counter()
    for j in jobs:
        loc = j.get("location", "Unknown")
        # Normalize to city level
        city = loc.split(",")[0].strip() if loc else "Unknown"
        location_counts[city] += 1

    # ── Status Pipeline ─────────────────────────────────────────
    status_counts = Counter(j.get("_status", "new") for j in jobs)

    # ── Daily Activity (last 14 days) ───────────────────────────
    daily_activity = []
    for i in range(14):
        dt = datetime.now(timezone.utc) - timedelta(days=i)
        date_str = dt.strftime("%Y-%m-%d")
        day_jobs = [j for j in jobs if j.get("_scraped_date") == date_str]
        day_tailored = sum(1 for j in day_jobs if j.get("_tailored"))
        day_drafts = sum(
            1 for d in drafts
            if d.get("drafted_at", "").startswith(date_str)
        )
        daily_activity.append({
            "date": date_str,
            "jobs_found": len(day_jobs),
            "resumes_tailored": day_tailored,
            "outreach_drafted": day_drafts,
        })
    daily_activity.reverse()  # Oldest first for chart

    # ── Top Companies ───────────────────────────────────────────
    company_counts = Counter(j.get("company", "Unknown") for j in jobs)
    top_companies = [
        {"company": c, "count": n}
        for c, n in company_counts.most_common(15)
    ]

    # ── Salary Insights ─────────────────────────────────────────
    salaries = []
    for j in jobs:
        s = j.get("max_amount") or j.get("min_amount")
        if s and s > 0:
            salaries.append(s)
    avg_salary = int(sum(salaries) / len(salaries)) if salaries else 0
    max_salary = int(max(salaries)) if salaries else 0
    min_salary = int(min(salaries)) if salaries else 0
    jobs_with_salary = len(salaries)

    # ── Pipeline Funnel ─────────────────────────────────────────
    funnel = {
        "discovered": total_jobs,
        "relevant_50plus": sum(1 for j in jobs if j.get("_relevance_score", 0) >= 50),
        "tailored": tailored_count,
        "outreach_drafted": outreach_drafted,
        "outreach_sent": outreach_sent,
        "applied": status_counts.get("applied", 0),
        "interview": status_counts.get("interview", 0),
    }

    # ── Tailored Files Count ────────────────────────────────────
    tailored_dir = os.path.join(DATA_DIR, "tailored")
    tailored_files = glob.glob(os.path.join(tailored_dir, "*.json")) if os.path.exists(tailored_dir) else []

    # ── Build Final Stats ───────────────────────────────────────
    stats = {
        "last_updated": now_iso(),
        "hero": {
            "total_jobs": total_jobs,
            "new_today": new_today,
            "resumes_tailored": tailored_count,
            "outreach_sent": outreach_sent,
            "outreach_pending": outreach_pending,
            "tailored_files": len(tailored_files),
        },
        "funnel": funnel,
        "score_distribution": score_buckets,
        "source_breakdown": dict(source_counts),
        "location_breakdown": dict(location_counts.most_common(10)),
        "status_pipeline": dict(status_counts),
        "daily_activity": daily_activity,
        "top_companies": top_companies,
        "salary": {
            "average": avg_salary,
            "max": max_salary,
            "min": min_salary,
            "jobs_with_salary": jobs_with_salary,
        },
    }

    save_json("stats.json", stats)
    log_entry(f"Stats updated: {total_jobs} jobs, {tailored_count} tailored, {outreach_sent} outreach sent")
    print(f"\nStats updated! {total_jobs} total jobs tracked.")


if __name__ == "__main__":
    run_stats()
