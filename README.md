# Job Search Agent 🤖

An AI-powered agent that automatically searches Swedish job listings every weekday morning, ranks them against your profile using Claude, and sends you a personalized HTML email digest.

## What it does

1. Fetches live job listings from the Swedish Public Employment Service (Arbetsförmedlingen) open API
2. Sends up to 25 listings to Claude for intelligent ranking and analysis
3. Claude scores each job 1–10 based on your profile, writes a reason for each match and flags potential red flags
4. Delivers a clean HTML email to your inbox every weekday at 07:00

## Architecture

```
GitHub Actions (scheduler)
        ↓
Arbetsförmedlingen API (job listings)
        ↓
Claude API (ranking & analysis)
        ↓
Gmail SMTP (email digest)
```

## Tech stack

- **Python 3.11** — core script
- **Anthropic Claude API** — job ranking and market analysis
- **Arbetsförmedlingen API** — free, real-time Swedish job listings (no API key required)
- **GitHub Actions** — free cloud scheduler, runs every weekday at 07:00 CET
- **Gmail SMTP** — email delivery

## Setup

### 1. Fork or clone this repository

### 2. Create a Gmail App Password

Gmail requires a dedicated app password (not your regular password).

1. Go to [myaccount.google.com](https://myaccount.google.com)
2. Search for "App passwords" (requires 2-step verification to be enabled)
3. Select Mail → Other → name it "Job Agent"
4. Copy the 16-character password shown

### 3. Add secrets to GitHub

In your repository: **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | Value |
|---|---|
| `ANTHROPIC_API_KEY` | Your Anthropic API key |
| `GMAIL_USER` | your.email@gmail.com |
| `GMAIL_APP_PASSWORD` | The 16-character app password |
| `EMAIL_TO` | The email address to receive the digest |

### 4. Customize your profile

Open `job_agent.py` and edit the configuration section at the top:

```python
JOB_QUERIES = ["product manager", "project manager", ...]
MUNICIPALITIES = ["1480", "0180"]  # Gothenburg, Stockholm
MY_PROFILE = "Your background and what you are looking for..."
DONT_WANT = "What you want to avoid..."
```

### 5. Test manually

In your repository: **Actions → Daily Job Digest → Run workflow**

You should receive an email within 1–2 minutes.

## Municipality codes

| City | Code |
|---|---|
| Gothenburg | 1480 |
| Stockholm | 0180 |
| Malmö | 1280 |
| Lund | 1281 |
| Linköping | 0580 |

## Why I built this

Manually searching and evaluating job listings is repetitive and time-consuming. This agent automates the entire process — from fetching listings to intelligent matching — so I can focus on applying to the right roles instead of filtering through hundreds of irrelevant ones.

It also serves as a practical demonstration of building AI-powered automation pipelines using real APIs, Claude for reasoning, and GitHub Actions for orchestration.

---

*Powered by [Claude](https://anthropic.com) · Data from [Arbetsförmedlingen](https://jobtechdev.se)*
