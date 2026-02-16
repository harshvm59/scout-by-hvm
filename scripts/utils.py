"""
SCOUT by HVM — Utility Functions
Deduplication, relevance scoring, JSON I/O, logging
"""

import hashlib
import json
import os
from datetime import datetime, timezone

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")


def ensure_data_dir():
    """Create data directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "tailored"), exist_ok=True)


def generate_job_id(title, company, location):
    """Deterministic hash for deduplication."""
    raw = f"{title}{company}{location}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def load_json(filename):
    """Load a JSON file from the data directory."""
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None


def save_json(filename, data):
    """Save data as JSON to the data directory."""
    ensure_data_dir()
    path = os.path.join(DATA_DIR, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def now_iso():
    """Current UTC timestamp as ISO string."""
    return datetime.now(timezone.utc).isoformat()


def today_str():
    """Today's date as YYYY-MM-DD."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def score_relevance(job, config):
    """
    Score a job 0-100 for relevance to Harsh's profile.
    Higher = more relevant.
    """
    score = 0
    title = (job.get("title") or "").lower()
    description = (job.get("description") or "").lower()
    text = f"{title} {description}"

    # ── Title keyword matching (max 40 pts) ──
    title_hits = sum(1 for kw in config.TITLE_KEYWORDS_HIGH if kw in title)
    score += min(40, title_hits * 12)

    # ── Description must-have keywords (max 25 pts) ──
    must_hits = sum(1 for kw in config.DESCRIPTION_KEYWORDS_MUST if kw in text)
    score += min(25, must_hits * 5)

    # ── Description nice-to-have keywords (max 20 pts) ──
    nice_hits = sum(1 for kw in config.DESCRIPTION_KEYWORDS_NICE if kw in text)
    score += min(20, nice_hits * 3)

    # ── Salary boost (max 15 pts) ──
    min_salary = job.get("min_amount") or 0
    max_salary = job.get("max_amount") or 0
    salary = max(min_salary, max_salary)
    if salary >= config.SALARY_BOOST_THRESHOLD:
        score += 15
    elif salary >= config.MIN_SALARY_PREFERRED:
        score += 8

    # ── Penalty: exclude keywords in title ──
    if any(kw in title for kw in config.EXCLUDE_TITLE_KEYWORDS):
        score = 0

    return min(100, score)


def deduplicate_jobs(new_jobs, existing_jobs):
    """
    Merge new jobs into existing, deduplicating by job_id.
    New jobs overwrite existing ones with the same ID.
    Returns the merged list.
    """
    existing_map = {j["_id"]: j for j in existing_jobs}
    for job in new_jobs:
        existing_map[job["_id"]] = job
    return list(existing_map.values())


def log_entry(message, level="info"):
    """Append a log entry to data/log.json."""
    log_data = load_json("log.json") or {"entries": []}
    log_data["entries"].append({
        "timestamp": now_iso(),
        "level": level,
        "message": message,
    })
    # Keep last 500 entries
    log_data["entries"] = log_data["entries"][-500:]
    save_json("log.json", log_data)
    print(f"[{level.upper()}] {message}")
