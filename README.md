# SchemeSaarthi

**An agentic government-benefits guide for Indian citizens.**

SchemeSaarthi continuously watches for welfare scheme eligibility and document requirements
that apply to a citizen's consented profile, and proactively tells them — instead of the
citizen having to go looking, the way every existing scheme-discovery tool (like myScheme)
requires today.

Built for Tech Zephyr 4.0, IIT Bhubaneswar — Agentic AI Hackathon.

---

## Why this is agentic, not a chatbot

| | A chatbot | SchemeSaarthi |
|---|---|---|
| When does it act? | Only when asked | Continuously, on a schedule, unprompted |
| Does it hold state? | No | Yes — persisted, consent-scoped citizen profile |
| Does it use tools? | Text generation only | Live web search, database queries, document uploads |
| Does it evaluate itself? | No | Flags uncertainty, never forces a match |
| Does it adapt? | No | Re-plans when a source fails or a rule changes |

---

## Architecture

**7 LangGraph agents**, each with a single responsibility, orchestrated with conditional
routing that re-plans on failure (not just a linear script):

- **Consent & Profile Agent** — gates every attribute read through `ConsentGateway`; nothing
  downstream can read data the citizen hasn't consented to for that specific purpose.
- **Discovery Agent** — watches for new/changed scheme and document-rule entries; falls back
  to a cached snapshot if a source goes offline.
- **Matching Agent** — real LLM reasoning per scheme against the citizen's cleared attributes;
  expresses uncertainty rather than forcing a match on incomplete data.
- **Document Agent** — compares required vs. held documents; determines baseline KYC
  requirements (Aadhaar, PAN, APAAR) using a real AI+web-search call scoped to the citizen's
  age/category/state, not a hardcoded list.
- **Conflict & Explainability Agent** — flags mutually-exclusive scheme pairs and state-vs-
  central document rule mismatches; generates "why/why-not" explanations on demand.
- **Notification Agent** — deduplicates and updates citizen-facing alerts; retries and
  escalates on simulated delivery failure.
- **Orchestrator** — the LangGraph routing logic itself; re-plans the execution path when any
  agent reports degraded/failed status.

**Stack:** LangGraph · FastAPI · Supabase (Postgres + Auth + Storage + RLS) · Next.js ·
Groq (`openai/gpt-oss-120b` for reasoning, `groq/compound-mini` for AI+web-search document
requirement discovery) · data.gov.in OGD API.

---

## What's real vs. what's honestly scoped

- **Scheme matching, conflict detection, document requirement discovery, and the why-not-
  matched explanations are genuinely live AI reasoning** — a fresh LLM call per decision,
  not pre-scripted text.
- **The scheme catalog itself is self-authored**, modeled on real Government of India scheme
  structures (DAY-NRLM, PMEGP, PM-KISAN, Ayushman Bharat, and others). This is a deliberate
  choice, not a shortcut: no API — not myScheme, not data.gov.in — publishes a machine-
  readable "scheme criteria + required documents" dataset, and myScheme's own Terms of Use
  explicitly prohibit scraping. We verified this rather than assumed it.
- **Real data.gov.in integration** feeds live demographic context (state-wise average
  agricultural household income) into onboarding — genuinely fetched, not hardcoded.
- **Consent enforcement is structural**, not decorative — enforced both in application code
  (`ConsentGateway`) and at the database layer via Postgres Row-Level Security.

---

## Running locally

See `docs/MASTER_SETUP_GUIDE.md` for full step-by-step setup (Supabase project, schema, seed
data, environment variables, and running each service).

```bash
# Backend
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev
```

## Team

| Person | Focus |
|---|---|
| Ishaan | Agents — LangGraph orchestration, matching/conflict/document logic |
| Hunar | Backend — FastAPI, database, deployment |
| Sher | Frontend — Next.js, UI/UX |
| Jaya | Data layer — schema, seed data |
