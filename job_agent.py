#!/usr/bin/env python3
"""
Job Search Agent
Fetches job listings daily from the Swedish Public Employment Service API,
analyzes and ranks them using Claude, then sends a formatted HTML email digest.
"""

import os
import json
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import anthropic

# ============================================================
#  CONFIGURATION — customize this to your profile
# ============================================================

JOB_QUERIES = [
    "product manager",
    "project manager",
    "digital project manager",
    "product owner",
]

MUNICIPALITIES = [
    "1480",  # Gothenburg
    "0180",  # Stockholm
    # "1280",  # Malmö — uncomment if needed
]

MY_PROFILE = """
Experienced in digital product development and project management.
Skilled in agile methodology, stakeholder management and data-driven decision making.
Looking for roles as Product Manager, Product Owner, Project Manager or Project Coordinator.
Prefer companies with at least 20 employees, ideally in tech, e-commerce or SaaS.
"""

DONT_WANT = "Pure sales roles, startups under 10 employees, more than 1 hour commute"

# ============================================================
#  LOAD CREDENTIALS FROM ENVIRONMENT VARIABLES
# ============================================================

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASSWORD"]
EMAIL_TO          = os.environ.get("EMAIL_TO", GMAIL_USER)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ============================================================
#  STEP 1 — FETCH JOBS
# ============================================================

def fetch_jobs(queries, municipalities, limit_per_query=15):
    all_jobs = []
    seen_ids = set()

    for query in queries:
        params = [("q", query), ("limit", limit_per_query)]
        for m in municipalities:
            params.append(("municipality", m))

        try:
            r = requests.get(
                "https://jobsearch.api.jobtechdev.se/search",
                params=params,
                timeout=15,
            )
            r.raise_for_status()
            for job in r.json().get("hits", []):
                job_id = job.get("id", "")
                if job_id not in seen_ids:
                    seen_ids.add(job_id)
                    all_jobs.append(job)
        except Exception as e:
            print(f"Warning: failed query '{query}': {e}")

    print(f"Found {len(all_jobs)} unique listings")
    return all_jobs


# ============================================================
#  STEP 2 — ANALYZE WITH CLAUDE
# ============================================================

def analyze_jobs(jobs, profile, dont_want):
    sample = []
    for i, j in enumerate(jobs[:25]):
        sample.append({
            "id":        i,
            "title":     j.get("headline", ""),
            "company":   j.get("employer", {}).get("name", ""),
            "location":  j.get("workplace_address", {}).get("municipality", ""),
            "desc":      (j.get("description", {}).get("text", "") or "")[:400],
            "url":       j.get("webpage_url", "") or j.get("application_details", {}).get("url", ""),
            "published": (j.get("publication_date", "") or "")[:10],
        })

    prompt = f"""You are an expert career coach. Analyze the job listings below and match them against the candidate profile.

PROFILE:
{profile}

AVOID:
{dont_want}

JOB LISTINGS ({len(sample)} total):
{json.dumps(sample, ensure_ascii=False)}

Respond ONLY with JSON (no backticks or markdown):
{{
  "ranked_jobs": [
    {{
      "id": <int>,
      "score": <1-10>,
      "reason": "<2-3 sentences explaining why this matches the profile>",
      "red_flag": "<warning or empty string>",
      "tags": ["<tag1>", "<tag2>", "<tag3>"],
      "action": "apply now" | "consider" | "monitor"
    }}
  ],
  "market_insight": "<2-3 sentences about today's market based on these listings>",
  "summary": "<1 sentence summarizing today's search>"
}}

Return top 7 jobs sorted by score descending. JSON only."""

    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
    return json.loads(raw)


# ============================================================
#  STEP 3 — BUILD HTML EMAIL
# ============================================================

def build_html(jobs, analysis, date_str):
    ranked  = analysis.get("ranked_jobs", [])
    insight = analysis.get("market_insight", "")
    summary = analysis.get("summary", "")

    def score_color(s):
        if s >= 8: return "#16a34a"
        if s >= 6: return "#d97706"
        return "#6b7280"

    def action_style(a):
        if a == "apply now":  return "background:#16a34a;color:#fff"
        if a == "consider":   return "background:#d97706;color:#fff"
        return "background:#e5e7eb;color:#374151"

    cards = ""
    for i, r in enumerate(ranked):
        if r["id"] >= len(jobs):
            continue
        j         = jobs[r["id"]]
        title     = j.get("headline", "")
        company   = j.get("employer", {}).get("name", "")
        location  = j.get("workplace_address", {}).get("municipality", "")
        url       = j.get("webpage_url", "") or j.get("application_details", {}).get("url", "")
        published = (j.get("publication_date", "") or "")[:10]
        tags_html = "".join(
            f'<span style="background:#f3f4f6;color:#374151;padding:2px 8px;'
            f'border-radius:12px;font-size:11px;margin-right:4px">{t}</span>'
            for t in r.get("tags", [])
        )
        rf_html = (
            f'<p style="color:#dc2626;font-size:12px;margin:6px 0 0">⚠ {r["red_flag"]}</p>'
            if r.get("red_flag") else ""
        )
        url_html = (
            f'<div style="margin-top:10px">'
            f'<a href="{url}" style="font-size:12px;color:#2563eb;text-decoration:none">View listing →</a>'
            f'</div>' if url else ""
        )
        cards += f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px">
            <div style="font-size:11px;color:#9ca3af;font-weight:500;text-transform:uppercase;letter-spacing:0.5px">#{i+1} &middot; {published}</div>
            <div style="display:flex;gap:6px;align-items:center">
              <span style="font-size:12px;font-weight:600;color:{score_color(r['score'])}">{r['score']}/10</span>
              <span style="font-size:10px;font-weight:500;padding:2px 9px;border-radius:20px;{action_style(r.get('action','consider'))}">{r.get('action','consider').upper()}</span>
            </div>
          </div>
          <div style="font-size:15px;font-weight:600;color:#111827;margin-bottom:2px">{title}</div>
          <div style="font-size:12px;color:#6b7280;margin-bottom:8px">{company} &middot; {location}</div>
          <div style="font-size:13px;color:#374151;line-height:1.6">{r['reason']}</div>
          {rf_html}
          <div style="margin-top:10px">{tags_html}</div>
          {url_html}
        </div>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:600px;margin:0 auto;padding:24px 16px">
    <div style="margin-bottom:20px">
      <div style="font-size:11px;font-weight:500;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Job Search Agent &middot; {date_str}</div>
      <div style="font-size:22px;font-weight:700;color:#111827">Your jobs today</div>
      <div style="font-size:14px;color:#6b7280;margin-top:4px">{summary}</div>
    </div>
    {cards}
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:14px;margin-top:6px">
      <div style="font-size:11px;font-weight:500;color:#9ca3af;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:6px">Market Insight</div>
      <div style="font-size:13px;color:#374151;line-height:1.6">💡 {insight}</div>
    </div>
    <div style="margin-top:20px;text-align:center;font-size:11px;color:#9ca3af">
      Sent by your Job Search Agent &middot; Powered by Claude
    </div>
  </div>
</body>
</html>"""


# ============================================================
#  STEP 4 — SEND EMAIL
# ============================================================

def send_email(html, date_str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"Your jobs today — {date_str}"
    msg["From"]    = GMAIL_USER
    msg["To"]      = EMAIL_TO
    msg.attach(MIMEText(html, "html", "utf-8"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
        smtp.login(GMAIL_USER, GMAIL_APP_PASS)
        smtp.sendmail(GMAIL_USER, EMAIL_TO, msg.as_string())

    print(f"✓ Email sent to {EMAIL_TO}")


# ============================================================
#  RUN
# ============================================================

def main():
    date_str = datetime.now().strftime("%B %-d, %Y")
    print(f"=== Job Search Agent starting — {date_str} ===")

    print("Step 1: Fetching jobs from the Swedish Public Employment Service...")
    jobs = fetch_jobs(JOB_QUERIES, MUNICIPALITIES)
    if not jobs:
        print("No jobs found, exiting.")
        return

    print(f"Step 2: Claude analyzing {min(len(jobs), 25)} listings...")
    analysis = analyze_jobs(jobs, MY_PROFILE, DONT_WANT)

    print("Step 3: Building and sending email...")
    html = build_html(jobs, analysis, date_str)
    send_email(html, date_str)

    print("=== Done! ===")


if __name__ == "__main__":
    main()
