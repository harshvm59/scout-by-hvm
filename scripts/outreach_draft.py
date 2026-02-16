"""
SCOUT by HVM — Outreach Draft Engine
Drafts personalized emails and LinkedIn messages per job listing.
Uses Claude Haiku API for personalization. Saves to data/outreach.json.
"""

import sys
import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

sys.path.insert(0, os.path.dirname(__file__))

import config
from utils import load_json, save_json, log_entry, now_iso, today_str

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic not installed. Run: pip install anthropic")
    sys.exit(1)

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def load_outreach_templates():
    """Load outreach message templates."""
    path = os.path.join(TEMPLATES_DIR, "outreach_templates.json")
    with open(path, "r") as f:
        return json.load(f)


PERSONALIZE_PROMPT = """You are a job application outreach expert. Generate personalized components for a cold email to a hiring manager/HR.

The applicant is Harsh Vardhan Mourya, Senior Program Manager at Zomato:
- 6+ years in P&L ownership, growth strategy, marketplace ops
- Drove 3% market share shift, acquired 30K users/month, launched 5 new localities
- Built data dashboards (SQL/Tableau), AI tools, automated workflows
- Previously at Urban Company (3 yrs) managing 11K+ service partners
- NIT Raipur engineer, side businesses ($2K/mo Airbnb, $141K portfolio)

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION (excerpt):
{jd}

Generate these 3 items (each on a new line, labeled):
VALUE_PROPOSITION: A 1-2 sentence value prop explaining why Harsh is uniquely qualified for THIS role (be specific to the JD)
SPECIFIC_ALIGNMENT: A 1-2 sentence alignment showing how past work directly maps to this role's requirements
HOOK: A punchy one-liner (under 30 words) for a LinkedIn connection request

Return ONLY the 3 labeled items, nothing else."""


def call_claude(prompt, max_tokens=400):
    """Call Claude Haiku for personalization."""
    client = anthropic.Anthropic()
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()


def parse_personalization(text):
    """Parse the labeled response from Claude."""
    result = {"value_proposition": "", "specific_alignment": "", "hook": ""}
    for line in text.split("\n"):
        line = line.strip()
        if line.startswith("VALUE_PROPOSITION:"):
            result["value_proposition"] = line.replace("VALUE_PROPOSITION:", "").strip()
        elif line.startswith("SPECIFIC_ALIGNMENT:"):
            result["specific_alignment"] = line.replace("SPECIFIC_ALIGNMENT:", "").strip()
        elif line.startswith("HOOK:"):
            result["hook"] = line.replace("HOOK:", "").strip()
    return result


def draft_outreach_for_job(job, templates):
    """Draft all outreach messages for a single job."""
    jd = (job.get("description") or "")[:2000]
    job_title = job.get("title", "Unknown Role")
    company = job.get("company", "Unknown Company")
    emails = job.get("emails", [])

    # Get personalized components from Claude
    personalization = parse_personalization(
        call_claude(
            PERSONALIZE_PROMPT.format(
                job_title=job_title,
                company=company,
                jd=jd,
            )
        )
    )

    drafts = {
        "job_id": job["_id"],
        "job_title": job_title,
        "company": company,
        "job_url": job.get("job_url", ""),
        "drafted_at": now_iso(),
        "status": "pending_approval",
        "messages": [],
    }

    # Cold email to HR
    email_template = templates.get("cold_email_hr", {})
    email_body = email_template.get("body", "").format(
        hr_name="Hiring Manager",
        role_title=job_title,
        company=company,
        value_proposition=personalization["value_proposition"],
        specific_alignment=personalization["specific_alignment"],
    )
    email_subject = email_template.get("subject", "").format(
        role_title=job_title,
        company=company,
    )
    drafts["messages"].append({
        "type": "email",
        "to": emails[0] if emails else f"hr@{company.lower().replace(' ', '')}.com",
        "subject": email_subject,
        "body": email_body,
        "status": "pending_approval",
        "has_real_email": len(emails) > 0,
    })

    # LinkedIn connection note
    linkedin_template = templates.get("linkedin_connection_note", {})
    linkedin_body = linkedin_template.get("body", "").format(
        hr_name="there",
        role_title=job_title,
        company=company,
        hook=personalization["hook"],
    )
    # LinkedIn notes must be under 300 characters
    if len(linkedin_body) > 300:
        linkedin_body = linkedin_body[:297] + "..."
    drafts["messages"].append({
        "type": "linkedin_note",
        "body": linkedin_body,
        "status": "draft",
    })

    # LinkedIn InMail
    inmail_template = templates.get("linkedin_inmail", {})
    inmail_body = inmail_template.get("body", "").format(
        hr_name="there",
        role_title=job_title,
        company=company,
        relevant_skills="growth strategy, P&L management, and marketplace operations",
        value_proposition=personalization["value_proposition"],
    )
    drafts["messages"].append({
        "type": "linkedin_inmail",
        "subject": inmail_template.get("subject", "").format(
            role_title=job_title, company=company
        ),
        "body": inmail_body,
        "status": "draft",
    })

    return drafts


def send_approved_emails():
    """Send emails that have been approved by the user."""
    gmail_user = os.environ.get("GMAIL_USER", "")
    gmail_password = os.environ.get("GMAIL_APP_PASSWORD", "")

    if not gmail_user or not gmail_password:
        log_entry("Gmail credentials not configured, skipping email sending", "warning")
        return 0

    outreach_data = load_json("outreach.json") or {"drafts": []}
    sent_count = 0

    for draft in outreach_data.get("drafts", []):
        for msg in draft.get("messages", []):
            if msg.get("type") == "email" and msg.get("status") == "approved":
                try:
                    mime_msg = MIMEMultipart()
                    mime_msg["From"] = gmail_user
                    mime_msg["To"] = msg["to"]
                    mime_msg["Subject"] = msg["subject"]
                    mime_msg.attach(MIMEText(msg["body"], "plain"))

                    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                        server.login(gmail_user, gmail_password)
                        server.send_message(mime_msg)

                    msg["status"] = "sent"
                    msg["sent_at"] = now_iso()
                    sent_count += 1
                    log_entry(f"Email sent to {msg['to']} for {draft['company']}")

                except Exception as e:
                    msg["status"] = "send_failed"
                    msg["error"] = str(e)
                    log_entry(f"Email send failed to {msg['to']}: {e}", "error")

    if sent_count > 0:
        save_json("outreach.json", outreach_data)
    return sent_count


def run_outreach():
    """Draft outreach for top jobs that haven't been outreached yet."""
    log_entry("Starting outreach drafting")

    jobs_data = load_json("jobs.json")
    if not jobs_data or not jobs_data.get("jobs"):
        log_entry("No jobs found for outreach", "warning")
        return

    templates = load_outreach_templates()
    jobs = jobs_data["jobs"]

    # Get jobs without outreach drafts, sorted by relevance
    no_outreach = [j for j in jobs if not j.get("_outreach_drafted")]
    no_outreach.sort(key=lambda j: j.get("_relevance_score", 0), reverse=True)
    to_draft = no_outreach[: config.TOP_JOBS_TO_OUTREACH]

    if not to_draft:
        log_entry("No new jobs for outreach drafting")
        return

    # Load existing outreach data
    outreach_data = load_json("outreach.json") or {
        "last_updated": "",
        "total_drafts": 0,
        "drafts": [],
    }

    drafted_count = 0
    for job in to_draft:
        try:
            print(f"  Drafting outreach for: {job.get('title')} @ {job.get('company')}...")
            draft = draft_outreach_for_job(job, templates)
            outreach_data["drafts"].append(draft)

            # Mark job as outreach drafted
            job["_outreach_drafted"] = True
            drafted_count += 1

        except Exception as e:
            log_entry(f"Outreach draft failed for {job.get('company')}: {e}", "error")

    # Save outreach data
    outreach_data["last_updated"] = now_iso()
    outreach_data["total_drafts"] = len(outreach_data["drafts"])
    save_json("outreach.json", outreach_data)

    # Save updated jobs
    jobs_data["last_updated"] = now_iso()
    save_json("jobs.json", jobs_data)

    # Send any previously approved emails
    sent = send_approved_emails()

    log_entry(
        f"Outreach complete: {drafted_count} new drafts, {sent} emails sent"
    )
    print(f"\nDone! {drafted_count} outreach drafts created, {sent} emails sent.")


if __name__ == "__main__":
    run_outreach()
