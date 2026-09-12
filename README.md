# 🕵️ Detective Agentic AI — Criminal Profiling & RAG Intelligence Platform

> AI-powered suspect profiling, behavioural risk scoring, ChromaDB precedent retrieval, and B2B agency outreach — built for detective agencies, law enforcement, and legal professionals.

**Live Demo:** [https://skilluphackathon2026-crvfgw9pkgzk3bzrmhwmfq.streamlit.app](https://skilluphackathon2026-crvfgw9pkgzk3bzrmhwmfq.streamlit.app)

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Prerequisites](#prerequisites)
  - [Local Setup](#local-setup)
  - [Environment Variables](#environment-variables)
- [Running the App](#running-the-app)
- [Running Tests](#running-tests)
- [Lead Verification Tool](#lead-verification-tool)
- [Subscription & Billing](#subscription--billing)
- [Admin Portal](#admin-portal)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

Detective Agentic AI is a multi-module Streamlit application that combines **Retrieval-Augmented Generation (RAG)**, **agentic AI orchestration**, and **B2B outreach automation** into a single investigative intelligence platform.

Investigators enter suspect observations (name/alias, age, behaviours, MO, and traits). The system:

1. Queries a **ChromaDB vector database** of historical criminal case precedents.
2. Runs an **AI analysis pipeline** to generate a structured risk profile, tendency score, and matched precedents.
3. Produces a **downloadable PDF dossier** containing the full assessment.
4. Enables admins to run **automated cold-email outreach** to detective agencies discovered via a four-stage web-scraping waterfall.

---

## Architecture

```
┌─────────────────────────────────────────────┐
│              Streamlit Frontend              │
│              frontend/app.py                 │
│  ┌──────────┐ ┌──────────┐ ┌─────────────┐  │
│  │ Profiler │ │ Billing  │ │ Admin/B2B   │  │
│  │   Tab    │ │   Tab    │ │   Portal    │  │
│  └────┬─────┘ └────┬─────┘ └──────┬──────┘  │
└───────┼────────────┼──────────────┼──────────┘
        │            │              │
        ▼            ▼              ▼
 ┌─────────────┐ ┌──────────┐ ┌────────────────┐
 │ agent/      │ │ agent/   │ │ agent/         │
 │ analyzer.py │ │ billing  │ │ outreach.py    │
 │ (RAG + LLM) │ │ .py      │ │ (Lead Scraper  │
 └──────┬──────┘ └──────────┘ │  + yagmail)    │
        │                     └────────────────┘
        ▼
 ┌─────────────┐   ┌──────────────────────┐
 │  rag/       │   │  case_parser/        │
 │  retriever  │──▶│  parser.py           │
 │  .py        │   │  (JSON case ingester)│
 └──────┬──────┘   └──────────────────────┘
        │
        ▼
 ┌─────────────┐
 │  ChromaDB   │
 │  Vector DB  │
 │ (persistent)│
 └─────────────┘
```

---

## Features

| Feature | Description |
|---|---|
| **Suspect Profiling** | Structured input for name/alias, age, observed behaviours, MO, and traits |
| **RAG Precedent Matching** | ChromaDB vector search against 15+ indexed criminal case precedents |
| **Risk & Tendency Scoring** | AI-generated risk classification and tendency score (0–100) |
| **PDF Dossier Export** | Downloadable executive summary with risk metrics and matched precedents via `fpdf2` |
| **Case Indexer** | Upload custom JSON case files to extend the vector knowledge base |
| **B2B Lead Scraping** | Four-stage discovery waterfall: OpenStreetMap → DuckDuckGo → Wikipedia → Seed fallback |
| **Cold Email Outreach** | Automated personalised email campaigns via `yagmail` with Gmail authentication |
| **UPI Payment Gateway** | QR code + UPI ID generation (`qrcode`/`segno`) for subscription payments |
| **UTR Verification** | Manual payment verification with JSON persistence (`data/payments.json`) |
| **Subscription Tiers** | Starter ₹500/mo · Pro ₹1,000/mo · Enterprise ₹2,000/mo with quota enforcement |
| **Admin Portal** | PIN-protected admin panel for payment approvals and B2B outreach management |
| **Lead Verification** | Standalone CLI tool scoring leads via Nominatim + website keyword analysis |

---

## Project Structure

```
.
├── Detective Agentic AI/
│   ├── frontend/
│   │   └── app.py                  # Streamlit entry point & tab manager
│   ├── agent/
│   │   ├── analyzer.py             # DetectiveAgent: RAG pipeline + AI analysis
│   │   ├── billing.py              # Subscription tiers, UTR/payment state machine
│   │   └── outreach.py             # Lead scraper + yagmail cold-email engine
│   ├── rag/
│   │   ├── retriever.py            # ChromaDB collection manager & query interface
│   │   └── vector_search.py        # Embedding + similarity search helpers
│   ├── case_parser/
│   │   └── parser.py               # JSON case file ingester for vector DB indexing
│   ├── cases/
│   │   └── case_001.json … case_015.json   # Bundled criminal precedent case files
│   ├── data/
│   │   ├── leads.json              # Persisted scraped lead records
│   │   └── trial_usage.json        # Per-session free trial usage counters
│   ├── tests/
│   │   ├── test_billing.py
│   │   ├── test_imports.py
│   │   ├── test_outreach.py
│   │   ├── test_profiler.py
│   │   └── test_rag_retriever.py
│   ├── .env.example                # Environment variable template
│   └── requirements.txt
├── verify_leads.py                 # Standalone lead verification CLI tool
├── requirements.txt                # Root-level dependencies
└── Screenshots_and_Explainations.md
```

---

## Getting Started

### Prerequisites

- Python **3.10+**
- `pip` or a virtual environment manager (`venv` / `conda`)
- A Gmail account with an **App Password** enabled (for outreach features)
- A UPI VPA for the billing/payment screen (optional for local dev)

### Local Setup

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd "SkillUp Hackathon"

# 2. Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -r "Detective Agentic AI/requirements.txt"

# 4. Copy and configure environment variables
cp "Detective Agentic AI/.env.example" "Detective Agentic AI/.env"
# Edit .env and fill in ADMIN_PIN, SENDER_EMAIL, UPI_VPA, UPI_NAME, PLATFORM_URL
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ADMIN_PIN` | Yes | 3-digit numeric PIN for the admin portal |
| `SENDER_EMAIL` | Yes | Gmail address used for cold-email outreach |
| `UPI_VPA` | Yes | UPI Virtual Payment Address shown on billing page |
| `UPI_NAME` | Yes | Display name shown on the UPI QR code |
| `PLATFORM_URL` | Yes | Public app URL embedded in cold emails |
| `GMAIL_APP_PASSWORD` | Optional | Can be entered at runtime in the Admin UI instead |

> **Security note:** Never commit `.env` to version control. On Streamlit Cloud, add all secrets under **Settings → Secrets** using TOML format.

---

## Running the App

```bash
cd "Detective Agentic AI"
streamlit run frontend/app.py
```

The app starts at `http://localhost:8501` by default.

---

## Running Tests

```bash
cd "Detective Agentic AI"
python -m pytest tests/ -v
```

The test suite covers billing state transitions, outreach lead persistence, profiler output schema, RAG retriever queries, and critical import paths.

---

## Lead Verification Tool

A standalone CLI tool that scores scraped detective agency leads without modifying the Streamlit app.

```bash
# Basic usage
python verify_leads.py --input scraped_leads.csv --output verified_leads.csv

# Test on a small sample first
python verify_leads.py --input scraped_leads.csv --output verified_leads.csv --sample 10
```

**Input CSV columns:** `agency_name`, `location`, `website`, `phone`, `contact_email`

**Output columns added:** `verification_status`, `verification_score`, `verified_sources`, `verified_at`, `profession`

**Scoring logic:**

| Signal | Points |
|---|---|
| Nominatim name match (≥ 35% token overlap) | +50 |
| Nominatim keyword match | +35 |
| Nominatim found (any result) | +10 |
| Website contains detective/investigation keywords | +30 |
| Website reachable (no matching keywords) | +10 |
| Phone number present | +10 |
| Profession = Police | −10 |
| Profession = Lawyer | −5 |

**Status thresholds:** `Verified` ≥ 70 · `Needs Review` ≥ 40 · `Unverified` < 40

> Rate limiting: the tool enforces a 1.1-second delay between Nominatim requests to comply with the service's usage policy.

---

## Subscription & Billing

| Plan | Price | Evaluations | Features |
|---|---|---|---|
| **Free Trial** | ₹0 | 25 | Standard profiling, PDF export |
| **Starter Agency** | ₹500/month | 100 | Standard RAG precedent search, basic PDF export |
| **Pro Agency** | ₹1,000/month | 500 | Faster ChromaDB vector search, custom JSON case indexing |
| **Enterprise SaaS** | ₹2,000/month | Unlimited | Private vector database, dedicated API, priority support |

Payments are made via UPI/QR code. Users submit their **UTR (transaction reference ID)** through the app. Admins review and approve submissions via the Admin Portal to unlock the selected plan.

---

## Admin Portal

The admin panel is PIN-protected (3-digit `ADMIN_PIN` from environment).

**Access:** In the sidebar, enter the admin PIN to unlock two additional tabs:

- **📢 B2B Agency Acquisition** — search for detective agencies by keyword and location, review scraped leads, compose and send personalised cold emails via Gmail.
- **🛠️ Admin Payment Approvals** — view all pending UTR submissions, verify payment details, approve or reject plan activations.

---

## Deployment

### Streamlit Cloud (recommended)

1. Push the repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Set **Main file path** to `Detective Agentic AI/frontend/app.py`.
4. Under **Settings → Secrets**, add all variables from `.env.example` in TOML format:

```toml
ADMIN_PIN = "739"
SENDER_EMAIL = "you@gmail.com"
UPI_VPA = "yourname@upi"
UPI_NAME = "Your Name"
PLATFORM_URL = "https://your-app.streamlit.app"
```

### Docker (self-hosted)

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -r "Detective Agentic AI/requirements.txt"
EXPOSE 8501
CMD ["streamlit", "run", "Detective Agentic AI/frontend/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
```

---

## Roadmap

- [ ] Explainable AI reasoning with evidence-to-conclusion traceability
- [ ] Multi-agent collaboration (behaviour analysis, evidence analysis, precedent matching)
- [ ] Automated payment gateway integration (Razorpay / Stripe) with real-time UTR verification
- [ ] Support for PDF, DOCX, audio transcript, and image case file ingestion
- [ ] Advanced knowledge graphs connecting suspects, cases, evidence, locations, and events
- [ ] OAuth-secured Gmail integration (replace App Password flow)
- [ ] Role-based access control with per-agency isolated vector databases
- [ ] Real-time intelligence monitoring and automated case alerts
- [ ] Cross-case pattern discovery and AI-assisted timeline generation
- [ ] CRM integration for lead management and outreach campaign analytics

---

## Contributing

1. Fork the repository and create a feature branch: `git checkout -b feat/your-feature`
2. Follow the existing code style (type hints, module-level docstrings, `logging` over `print`).
3. Add or update tests in `Detective Agentic AI/tests/` for any changed behaviour.
4. Ensure all tests pass: `python -m pytest tests/ -v`
5. Open a pull request with a clear description of the change and why it is needed.

---

## License

This project was built for the **IBM SkillUp Hackathon 2026**. All rights reserved by the authors.
Development was assisted by **IBM Bob** (IBM SkillsBuild AI Assistant) for code generation, architecture design, module refactoring, and Streamlit state management.
