"""
SCOUT by HVM — Resume Tailoring Engine
Uses Claude Haiku API to tailor resume sections per job listing.
Processes top N jobs daily, saves tailored versions to data/tailored/
"""

import sys
import os
import json

sys.path.insert(0, os.path.dirname(__file__))

import config
from utils import load_json, save_json, log_entry, now_iso, today_str

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic")
    sys.exit(1)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def load_base_resume():
    """Load the structured base resume."""
    path = os.path.join(TEMPLATES_DIR, "base_resume.json")
    with open(path, "r") as f:
        return json.load(f)


TAILOR_SUMMARY_PROMPT = """You are a resume optimization expert. Rewrite this professional summary for a resume, tailoring it to the specific job description below.

Rules:
1. Keep ALL facts truthful — do NOT invent metrics, companies, or achievements
2. Emphasize the most relevant experience for THIS specific role
3. Match the terminology and language used in the job description
4. Keep it to 2-3 concise sentences
5. Return ONLY the rewritten summary, nothing else

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{jd}

ORIGINAL SUMMARY:
{summary}

TAILORED SUMMARY:"""

TAILOR_BULLET_PROMPT = """You are a resume optimization expert. Rewrite this resume bullet point to better match the job description, while keeping it truthful.

Rules:
1. Keep the core achievement and metric from the original bullet
2. Adjust terminology to match the job description's language
3. Emphasize aspects most relevant to THIS specific role
4. Keep it concise (under 30 words)
5. Do NOT fabricate metrics or achievements
6. Return ONLY the rewritten bullet, nothing else

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION (excerpt):
{jd}

ORIGINAL BULLET:
{bullet}

REWRITTEN BULLET:"""

SKILLS_REORDER_PROMPT = """Given this job description and these skill categories, reorder the skills within each category to put the most relevant ones first. Also suggest up to 2 additional relevant skills per category if they are truthfully possessed by a Senior Program Manager at Zomato.

Return ONLY valid JSON in the same format as the input.

JOB DESCRIPTION:
{jd}

SKILLS:
{skills}

REORDERED SKILLS (JSON only):"""


def call_claude(prompt, max_tokens=300):
    """Call Claude Haiku for tailoring."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def tailor_resume_for_job(job, base_resume):
    """Tailor the full resume for a specific job listing."""
    jd = (job.get("description") or "")[:3000]  # Truncate to save tokens
    job_title = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")

    tailored = json.loads(json.dumps(base_resume))  # Deep copy

    # Tailor summary
    try:
        tailored["summary"] = call_claude(
            TAILOR_SUMMARY_PROMPT.format(
                job_title=job_title,
                company=company,
                jd=jd,
                summary=base_resume["summary"],
            )
        )
    except Exception as e:
        log_entry(f"Summary tailoring failed for {company}/{job_title}: {e}", "error")

    # Tailor experience bullets
    for exp in tailored["experience"]:
        for i in exp.get("tailorable_indices", []):
            if i < len(exp["bullets"]):
                try:
                    exp["bullets"][i] = call_claude(
                        TAILOR_BULLET_PROMPT.format(
                            job_title=job_title,
                            company=company,
                            jd=jd[:2000],
                            bullet=exp["bullets"][i],
                        ),
                        max_tokens=150,
                    )
                except Exception as e:
                    log_entry(f"Bullet tailoring failed: {e}", "error")

    # Reorder skills
    try:
        skills_json = call_claude(
            SKILLS_REORDER_PROMPT.format(
                jd=jd[:2000],
                skills=json.dumps(base_resume["skills"], indent=2),
            ),
            max_tokens=500,
        )
        # Try to parse the response as JSON
        parsed = json.loads(skills_json)
        if isinstance(parsed, dict):
            tailored["skills"] = parsed
    except (json.JSONDecodeError, Exception) as e:
        log_entry(f"Skills reorder failed (keeping original): {e}", "error")

    return tailored


def run_tailoring():
    """Process top jobs that haven't been tailored yet."""
    log_entry("Starting resume tailoring")

    jobs_data = load_json("jobs.json")
    if not jobs_data or not jobs_data.get("jobs"):
        log_entry("No jobs found to tailor", "warning")
        return

    base_resume = load_base_resume()
    jobs = jobs_data["jobs"]

    # Get untailored jobs, sorted by relevance score
    untailored = [j for j in jobs if not j.get("_tailored")]
    untailored.sort(key=lambda j: j.get("_relevance_score", 0), reverse=True)
    to_tailor = untailored[: config.TOP_JOBS_TO_TAILOR]

    if not to_tailor:
        log_entry("No new jobs to tailor")
        return

    tailored_count = 0
    for job in to_tailor:
        job_id = job["_id"]
        company = job.get("company", "unknown").replace(" ", "_").replace("/", "-")[:30]
        role = job.get("title", "unknown").replace(" ", "_").replace("/", "-")[:30]
        filename = f"tailored/{today_str()}_{company}_{role}_{job_id}.json"

        try:
            print(f"  Tailoring resume for: {job.get('title')} @ {job.get('company')}...")
            tailored = tailor_resume_for_job(job, base_resume)

            # Save tailored resume
            output = {
                "job_id": job_id,
                "job_title": job.get("title"),
                "company": job.get("company"),
                "job_url": job.get("job_url"),
                "tailored_at": now_iso(),
                "resume": tailored,
            }
            save_json(filename, output)

            # Mark job as tailored
            job["_tailored"] = True
            job["_tailored_file"] = filename
            tailored_count += 1

        except Exception as e:
            log_entry(f"Failed to tailor for {company}: {e}", "error")

    # Save updated jobs with _tailored flags
    jobs_data["last_updated"] = now_iso()
    save_json("jobs.json", jobs_data)

    log_entry(f"Tailoring complete: {tailored_count}/{len(to_tailor)} resumes tailored")
    print(f"\nDone! {tailored_count} resumes tailored.")


if __name__ == "__main__":
    run_tailoring()
