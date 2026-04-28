#!/usr/bin/env python3
"""
Job Search Agent — Enhanced
Fetches job listings daily from Sweden, Norway and Denmark,
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
#  CONFIGURATION
# ============================================================

# Swedish job search queries — aligned with target roles
JOB_QUERIES_SE = [
    "project manager",
    "projektledare",
    "delivery manager",
    "program manager",
    "project coordinator",
    "projektkoordinator",
    "operations coordinator",
    "delivery coordinator",
    "management consultant",
    "digital consultant",
    "transformation consultant",
    "IT-konsult",
]

# Norwegian job search queries
JOB_QUERIES_NO = [
    "project manager",
    "prosjektleder",
    "delivery manager",
    "program manager",
    "project coordinator",
    "prosjektkoordinator",
    "management consultant",
    "digital konsulent",
    "IT konsulent",
]

# Danish job search queries
JOB_QUERIES_DK = [
    "project manager",
    "projektleder",
    "delivery manager",
    "program manager",
    "project coordinator",
    "projektkoordinator",
    "management consultant",
    "digital konsulent",
    "IT konsulent",
]

# Swedish municipality codes
MUNICIPALITIES_SE = [
    "1480",  # Gothenburg
    "0180",  # Stockholm
    "1280",  # Malmö
    "1281",  # Lund
]

MY_PROFILE = """
Name: Pedram Hajigholi
Location: Gothenburg, Sweden
Open to: On-site or hybrid in Gothenburg, Stockholm, Malmö, Lund, Oslo, Copenhagen — OR fully remote anywhere. No geographical restrictions.
Seniority: Open to any level — priority is getting into the right environment with real ownership and growth potential.

BACKGROUND:
- Technical Project Manager with 7+ years across automotive, tech and consulting
- Volvo Cars (2023–2025): Led cross-functional delivery across software, hardware and function owners in complex automotive programs with multiple dependencies
- QUFY AB (2023–2025): Founded and ran own consulting firm in engineering/IT/digital — managed consultants, client relationships, sales and budgets — 200% revenue growth in one year
- ZEEKR/Geely Design (2022–2023): Led digital and marketing content projects across global markets (China and Europe)
- Volvo Trucks (2021): Project planning and quality assurance in large-scale automotive programs
- CEVT (2018–2021): Prototype and material development projects, PLM systems, 3D printing
- Master's in Mechanical Engineering / Product Development — LTU + NTU Singapore
- Certified in Applied Scrum for Agile Project Management
- Languages: Swedish (native), English (full professional), Persian (native)

CORE STRENGTHS:
- Creating structure and clarity in ambiguous, fast-moving environments
- Driving alignment across technical, business and operational stakeholders
- Cross-functional leadership, dependency management, removing blockers
- Entrepreneurial mindset — has built and run a business
- Strong communicator — direct, clear, results-oriented
- Growing interest and hands-on experience with AI and automation tools

WHAT I AM LOOKING FOR:
- Environments where operations, delivery, business and technology intersect
- Roles focused on process improvement, AI/automation, digital transformation or operational efficiency
- Real ownership and impact — not just coordination or meeting management
- Companies undergoing digital transformation, scaling, or building modern ops/product functions
- Growth toward strategic and technical seniority over time

IDEAL COMPANY TYPES (in priority order):
1. Tech/SaaS companies
2. Modern consulting firms (Accenture, Capgemini, McKinsey Digital, similar)
3. Large organizations (500+) undergoing digital transformation
4. Structured startups with clear direction and growth
5. Any industry including automotive — neutral on sector

TARGET ROLES (any of these are relevant):
- Project Manager / Senior Project Manager
- Delivery Manager
- Program Manager
- Consultant / Senior Consultant (PM or ops focus)
- Project Coordinator
- Operations Coordinator
- Delivery Coordinator
"""

DONT_WANT = """
- Purely administrative coordination roles with no real influence or ownership
- Pure sales roles with no project or product component
- Unstructured startups under 10 employees
- Roles that are purely hands-on technical development (coding/engineering)
- Companies going through bankruptcy or major downsizing
- Roles with no growth potential or learning trajectory
- Junior roles that are clearly below the candidate's experience level
- Roles requiring fluency in Norwegian or Danish (candidate speaks Swedish and English only)
"""

# ============================================================
#  CREDENTIALS
# ============================================================

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
GMAIL_USER        = os.environ["GMAIL_USER"]
GMAIL_APP_PASS    = os.environ["GMAIL_APP_PASSWORD"]
EMAIL_TO          = os.environ.get("EMAIL_TO", GMAIL_USER)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)


# ============================================================
#  STEP 1 — FETCH SWEDISH JOBS
# ============================================================

def fetch_jobs_sweden(queries, municipalities, limit_per_query=20):
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
                    job["_country"] = "Sweden"
                    all_jobs.append(job)
        except Exception as e:
            print(f"  SE warning: failed query '{query}': {e}")

    return all_jobs


# ============================================================
#  STEP 2 — FETCH NORWEGIAN JOBS
# ============================================================

def fetch_jobs_norway(queries, limit_per_query=10):
    all_jobs = []
    seen_ids = set()

    for query in queries:
        try:
            r = requests.get(
                "https://arbeidsplassen.nav.no/api/v2/ads/search",
                params={"q": query, "size": limit_per_query},
                headers={"Accept": "application/json"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            for job in data.get("content", []):
                job_id = str(job.get("id", ""))
                if job_id not in seen_ids:
                    seen_ids.add(job_id)
                    # Normalize to common format
                    normalized = {
                        "id": job_id,
                        "headline": job.get("title", ""),
                        "employer": {"name": job.get("employer", {}).get("name", "")},
                        "workplace_address": {
                            "municipality": job.get("location", {}).get("municipal", "Oslo")
                        },
                        "description": {"text": job.get("description", "")},
                        "webpage_url": job.get("applicationUrl", "") or job.get("source", ""),
                        "publication_date": job.get("published", ""),
                        "_country": "Norway"
                    }
                    all_jobs.append(normalized)
        except Exception as e:
            print(f"  NO warning: failed query '{query}': {e}")

    return all_jobs


# ============================================================
#  STEP 3 — FETCH DANISH JOBS
# ============================================================

def fetch_jobs_denmark(queries, limit_per_query=10):
    all_jobs = []
    seen_ids = set()

    for query in queries:
        try:
            r = requests.get(
                "https://job.jobnet.dk/CV/FindWork",
                params={
                    "Offset": 0,
                    "SortValue": "BestMatch",
                    "SearchString": query,
                    "Region": "Storkøbenhavn",
                    "PageSize": limit_per_query,
                },
                headers={"Accept": "application/json"},
                timeout=15,
            )
            r.raise_for_status()
            data = r.json()
            for job in data.get("JobPositionPostings", []):
                job_id = str(job.get("Id", ""))
                if job_id not in seen_ids:
                    seen_ids.add(job_id)
                    normalized = {
                        "id": job_id,
                        "headline": job.get("Headline", ""),
                        "employer": {"name": job.get("EmployerName", "")},
                        "workplace_address": {
                            "municipality": job.get("WorkPlaceAddress", {}).get("City", "Copenhagen")
                        },
                        "description": {"text": job.get("JobPositionInformation", {}).get("Description", "")},
                        "webpage_url": f"https://job.jobnet.dk/CV/FindWork/Details/{job_id}",
                        "publication_date": job.get("PostingCreated", ""),
                        "_country": "Denmark"
                    }
                    all_jobs.append(normalized)
        except Exception as e:
            print(f"  DK warning: failed query '{query}': {e}")

    return all_jobs


# ============================================================
#  STEP 4 — ANALYZE WITH CLAUDE
# ============================================================

def analyze_jobs(jobs, profile, dont_want):
    # Send up to 40 jobs to Claude for analysis
    sample = []
    for i, j in enumerate(jobs[:40]):
        sample.append({
            "id":        i,
            "title":     j.get("headline", ""),
            "company":   j.get("employer", {}).get("name", ""),
            "location":  j.get("workplace_address", {}).get("municipality", ""),
            "country":   j.get("_country", "Sweden"),
            "desc":      (j.get("description", {}).get("text", "") or "")[:500],
            "url":       j.get("webpage_url", "") or j.get("application_details", {}).get("url", ""),
            "published": (j.get("publication_date", "") or "")[:10],
        })

    prompt = f"""You are an expert career coach specializing in the Scandinavian job market. 
Analyze the job listings below and match them carefully against the candidate profile.

CANDIDATE PROFILE:
{profile}

AVOID:
{dont_want}

JOB LISTINGS ({len(sample)} total from Sweden, Norway and Denmark):
{json.dumps(sample, ensure_ascii=False)}

Instructions:
- Score each job 1-10 based on genuine fit with the profile
- Be strict — only score 8+ if it is a real strong match
- Consider both the role title AND the company type
- Flag red flags honestly (high competition, wrong industry, travel requirements etc.)
- Prioritize roles where the candidate can have real ownership and impact
- Consider location fit based on the candidate's stated preferences

Respond ONLY with JSON (no backticks or markdown):
{{
  "ranked_jobs": [
    {{
      "id": <int>,
      "score": <1-10>,
      "reason": "<2-3 sentences explaining specifically why this matches the profile>",
      "red_flag": "<specific warning or empty string>",
      "tags": ["<tag1>", "<tag2>", "<tag3>"],
      "action": "apply now" | "consider" | "monitor"
    }}
  ],
  "market_insight": "<2-3 sentences about today's market across Sweden, Norway and Denmark>",
  "summary": "<1 sentence summarizing today's search results>"
}}

Return top 8 jobs sorted by score descending. JSON only."""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = msg.content[0].text.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"Warning: Claude returned unexpected format: {e}")
        raise


# ============================================================
#  STEP 5 — BUILD HTML EMAIL
# ============================================================

def build_html(jobs, analysis, date_str):
    ranked  = analysis.get("ranked_jobs", [])
    insight = analysis.get("market_insight", "")
    summary = analysis.get("summary", "")

    country_flag = {"Sweden": "🇸🇪", "Norway": "🇳🇴", "Denmark": "🇩🇰"}

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
        country   = j.get("_country", "Sweden")
        flag      = country_flag.get(country, "")
        url       = j.get("webpage_url", "") or j.get("application_details", {}).get("url", "")
        published = (j.get("publication_date", "") or "")[:10]

        tags_html = "".join(
            f'<span style="background:#f3f4f6;color:#374151;padding:2px 8px;'
            f'border-radius:12px;font-size:11px;margin-right:4px">{t}</span>'
            for t in r.get("tags", [])
        )
        rf_html = (
            f'<p style="color:#dc2626;font-size:12px;margin:8px 0 0">⚠ {r["red_flag"]}</p>'
            if r.get("red_flag") else ""
        )
        url_html = (
            f'<div style="margin-top:12px">'
            f'<a href="{url}" style="font-size:12px;color:#2563eb;text-decoration:none;font-weight:500">View listing →</a>'
            f'</div>' if url else ""
        )

        cards += f"""
        <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:18px;margin-bottom:12px">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px">
            <div style="font-size:11px;color:#9ca3af;font-weight:500;text-transform:uppercase;letter-spacing:0.5px">
              #{i+1} &middot; {flag} {country} &middot; {published}
            </div>
            <div style="display:flex;gap:6px;align-items:center">
              <span style="font-size:13px;font-weight:700;color:{score_color(r['score'])}">{r['score']}/10</span>
              <span style="font-size:10px;font-weight:500;padding:3px 10px;border-radius:20px;{action_style(r.get('action','consider'))}">{r.get('action','consider').upper()}</span>
            </div>
          </div>
          <div style="font-size:16px;font-weight:600;color:#111827;margin-bottom:3px">{title}</div>
          <div style="font-size:13px;color:#6b7280;margin-bottom:10px">{company} &middot; {location}</div>
          <div style="font-size:13px;color:#374151;line-height:1.65">{r['reason']}</div>
          {rf_html}
          <div style="margin-top:12px">{tags_html}</div>
          {url_html}
        </div>"""

    total_countries = len(set(j.get("_country", "Sweden") for j in jobs))

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f9fafb;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
  <div style="max-width:620px;margin:0 auto;padding:28px 16px">
    <div style="margin-bottom:24px">
      <div style="font-size:11px;font-weight:500;color:#9ca3af;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
        Job Search Agent &middot; {date_str} &middot; 🇸🇪 🇳🇴 🇩🇰
      </div>
      <div style="font-size:24px;font-weight:700;color:#111827">Your jobs today</div>
      <div style="font-size:14px;color:#6b7280;margin-top:6px;line-height:1.5">{summary}</div>
    </div>
    {cards}
    <div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin-top:8px">
      <div style="font-size:11px;font-weight:500;color:#9ca3af;text-transform:uppercase;letter-spacing:0.5px;margin-bottom:8px">Market Insight</div>
      <div style="font-size:13px;color:#374151;line-height:1.65">💡 {insight}</div>
    </div>
    <div style="margin-top:24px;text-align:center;font-size:11px;color:#9ca3af">
      Sent by your Job Search Agent &middot; Powered by Claude &middot; {len(jobs)} listings reviewed across {total_countries} countries
    </div>
  </div>
</body>
</html>"""


# ============================================================
#  STEP 6 — SEND EMAIL
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

    all_jobs = []

    print("Step 1: Fetching Swedish jobs (Gothenburg, Stockholm, Malmö, Lund)...")
    se_jobs = fetch_jobs_sweden(JOB_QUERIES_SE, MUNICIPALITIES_SE)
    print(f"  → Found {len(se_jobs)} Swedish listings")
    all_jobs.extend(se_jobs)

    print("Step 2: Fetching Norwegian jobs (Oslo)...")
    no_jobs = fetch_jobs_norway(JOB_QUERIES_NO)
    print(f"  → Found {len(no_jobs)} Norwegian listings")
    all_jobs.extend(no_jobs)

    print("Step 3: Fetching Danish jobs (Copenhagen)...")
    dk_jobs = fetch_jobs_denmark(JOB_QUERIES_DK)
    print(f"  → Found {len(dk_jobs)} Danish listings")
    all_jobs.extend(dk_jobs)

    print(f"Total: {len(all_jobs)} unique listings across 3 countries")

    if not all_jobs:
        print("No jobs found, exiting.")
        return

    print(f"Step 4: Claude analyzing top {min(len(all_jobs), 40)} listings...")
    analysis = analyze_jobs(all_jobs, MY_PROFILE, DONT_WANT)

    print("Step 5: Building and sending email...")
    html = build_html(all_jobs, analysis, date_str)
    send_email(html, date_str)

    print("=== Done! ===")


if __name__ == "__main__":
    main()
