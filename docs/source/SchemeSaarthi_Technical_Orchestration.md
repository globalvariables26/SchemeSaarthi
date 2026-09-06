# SchemeSaarthi — Technical Orchestration & Build Plan

**Purpose of this document:** this is the concrete engineering design that turns the finalized
problem statement and agent responsibilities (see `SchemeSaarthi_Handoff_for_Orchestration.md`
and `SchemeSaarthi_Problem_Solution_Brief.docx`) into something buildable. It specifies exact
frameworks, libraries, data schema, agent-to-agent communication, and a phased build order.
**No feature or agent responsibility is re-decided here — only how to build what was already
decided.** A team/account with no prior context should be able to start coding directly from
this file plus the two source documents.

---

## 1. Stack at a glance

| Layer | Choice | Why |
|---|---|---|
| Agent orchestration | **LangGraph** (Python) | Explicit state graph, built-in support for conditional re-routing/re-planning, checkpointing, and human/admin-triggered interrupts — matches the "visible re-planning" demo requirement better than a linear chain |
| LLM | **Groq API** — `llama-3.3-70b-versatile` for reasoning agents, `llama-3.1-8b-instant` for cheap/fast classification steps | Genuinely free (no card, no credits system) — gated only by rate limits: 70B model gets 1,000 requests/day, 8B model gets 14,400/day, both at 30 req/min. Both support tool-calling and JSON structured output, which the agents need. Limits are per-organization (per API key set), not shared with anything else you run |
| Backend API | **FastAPI** (Python) | Same language as the agent layer — no serialization boundary between orchestration and API; async-native, fits SSE/WebSocket for live demo updates |
| Database | **Supabase (Postgres)** | Row-Level Security gives you a *real*, DB-enforced consent gate (not just app-code discipline); built-in auth; realtime subscriptions are useful for pushing live updates to the dashboard during the demo |
| Frontend | **Next.js (React) + Tailwind CSS** | Pairs natively with Supabase JS SDK; server components suit a dashboard-heavy app; easy Vercel deploy |
| UI polish | **kokonutui.com / bklit.ui** (components), **motion.dev / motion-primitives.com** (animation), **haikei.com** (backgrounds) | Ready-made, fast to integrate, keeps focus on the agent logic which is what's actually being judged |
| Real external data | **data.gov.in OGD API** | Only legitimate real-data channel per the constraints (Section 6 of handoff doc) |
| Simulated feeds | Seeded Postgres tables + an admin-only Next.js panel that writes to them | Needed because no real live scheme-change feed exists; must be admin-triggerable for the demo |
| Hosting | **Vercel** (frontend) + **Railway or Render** (FastAPI + LangGraph backend) + **Supabase Cloud** (DB/auth) | All have usable free tiers, all deploy from GitHub on push |
| Secrets | `.env` (local) + Vercel/Railway environment variable dashboards + `.gitignore` | No credentials in repo, per explicit constraint |

---

## 2. Orchestration framework — LangGraph in detail

### 2.0 A note on Groq's free-tier limits

The 70B model (used for Matching, Conflict/Explainability, and the Discovery Agent's
"is this new" judgment) is capped at **1,000 requests/day** on the free tier — comfortably
enough for development and rehearsal, but don't loop it in a test script hundreds of times the
morning of the demo. The 8B model (notifications, checklists, consent-purpose text) has a much
higher **14,400/day** cap and can absorb heavier testing. If the team ever needs more headroom
than the free tier gives close to a deadline, Groq's paid Developer tier removes the card-free
constraint the brief doesn't require you to keep — but for Stage 1, the free tier is sufficient
if you're deliberate about not re-running full graph tests unnecessarily in the final hours.

### 2.1 Why LangGraph over alternatives
- **CrewAI** is simpler to start with but hides the planning/re-planning logic behind its own
  abstractions — harder to make the "plan visibly changes on screen" demo requirement concrete.
- **A custom state machine** gives full control but means building checkpointing, conditional
  edges, and interrupt handling from scratch — not worth it under hackathon time pressure.
- **LangGraph** gives you a directed graph of nodes (agents) and edges (control flow) with:
  - **Conditional edges** — exactly what "Orchestrator re-plans on failure" needs.
  - **A shared, typed state object** passed between nodes — natural fit for the per-citizen
    "working state" described in Section 5.
  - **Checkpointing** — lets you snapshot state before/after each agent runs, which is *also*
    your audit log's raw material (Section 6.5).
  - **Interrupt/resume** — used for the admin panel's "inject a new scheme mid-demo" action:
    it interrupts the graph, injects new data, and resumes from the Discovery Agent node.

### 2.2 Graph structure

Model each of the 7 required agents as a LangGraph **node**. The Orchestrator is not a normal
node that "does work" — it is the **graph's routing logic itself** (the conditional edges +
a lightweight planning node that decides the next node based on current state and any
failure flags). This keeps the Orchestrator's responsibility ("sequence agents, re-plan on
failure") structurally enforced rather than just described in a docstring.

```
                     ┌─────────────────────┐
                     │   Orchestrator /     │◄──────────────┐
                     │   Planner (routing)  │                │
                     └──────────┬───────────┘                │
                                │ decides next node            │
        ┌───────────┬──────────┼───────────┬────────────┐    │
        ▼           ▼          ▼           ▼            ▼    │
   Consent &    Discovery   Matching    Document     Conflict &│
   Profile        Agent      Agent       Agent      Explain-  │
    Agent                                             ability │
        │           │          │           │            │    │
        └───────────┴──────────┴───────────┴────────────┘    │
                                │                              │
                        failure/new-data flag ─────────────────┘
                                │
                                ▼
                        Notification Agent
                                │
                                ▼
                          Outcome / dashboard update
```

Each node:
1. Reads only the slice of shared state it's allowed to (enforced per Section 6.3 for the
   Consent & Profile Agent specifically).
2. Does its work (LLM call, DB query, data.gov.in call, etc.).
3. Writes its result — including a `status` field (`ok` / `degraded` / `failed`) and a
   human-readable `reason` string — back to shared state.
4. Returns control to the Orchestrator routing function, which reads that `status` field to
   decide the next node. A `failed` status is what triggers a **visible re-plan**: the
   Orchestrator node emits a state-change event (Section 2.3) before routing to a fallback path
   (e.g., cached data source, or skip-and-flag-for-Notification-Agent).

### 2.3 Making re-planning *visible* (the demo requirement)

Don't just log re-planning to a console. Two concrete mechanisms:

- **Server-Sent Events (SSE) endpoint** (`/api/graph-events`) that streams every node
  transition and every state-field change as JSON events, in the order they happen. The
  frontend admin/demo panel subscribes to this and renders a live "flowchart" (simple
  animated diagram, highlight the active node) — this is what the audience watches during
  the failure-injection moment.
- **Every Orchestrator re-route writes an explicit `plan_change` record** (old next-node,
  new next-node, trigger reason) to the audit log table, which the Notification Agent also
  turns into a plain-language line for the notification feed ("Data source X failed —
  switched to cached scheme list Y").

---

## 3. Per-agent build spec

For each agent: what it's built from, what tools/APIs it calls, and its failure/adapt behavior.

### 3.1 Consent & Profile Agent
- **Not primarily an LLM agent** — mostly a data-access gateway. Implement as a Python
  service class (`ConsentGateway`) that is the *only* code path allowed to read
  `citizen_attributes` rows (enforced by Postgres Row-Level Security, see 6.3).
- LLM use: only for turning a consent request into plain language for the onboarding UI
  ("this lets us check your SC/ST/OBC scholarship eligibility") — 8B-tier, cheap, low-stakes.
- Tools: Supabase client (Python) for reads/writes to `citizen_attributes` and `consent_log`.
- Failure mode to implement: **mid-session revocation**. Expose a `revoke(attribute_id)` method
  that immediately flips the consent flag; every other agent must re-check consent status on
  each read, not cache it — cheapest way to do this is to make `ConsentGateway.get(attribute,
  purpose)` the *only* getter, with no attribute value ever copied into another agent's local
  state for longer than one node execution.

### 3.2 Discovery Agent
- LangGraph node backed by a 70B-tier LLM call **only for judging "is this materially new
  or changed"** — the actual data fetch is deterministic code, not an LLM call.
- Tools:
  - Polls the seeded `scheme_source` and `document_rule_source` tables (Section 4) for rows
    with `updated_at` newer than this agent's last-checked watermark.
  - Calls the data.gov.in API client (Section 7) for demographic context refresh (not scheme
    data itself — schemes are seeded, per constraints).
- Failure mode to implement: **source offline / malformed data**. Wrap the fetch in a
  try/except; on failure, write `status: "failed"`, `reason: "source unreachable"`, and check
  a `cached_snapshot` table for the last good version. If it exists, mark `status: "degraded"`
  and proceed using the cached snapshot — this is one of your two demo failure-injection paths.

### 3.3 Matching Agent
- 70B-tier LLM call, but **constrained**: pass it the scheme's structured criteria object
  and the citizen's *cleared* attributes only (fetched exclusively through `ConsentGateway`),
  and require a structured JSON response: `{applies: bool, confidence: 0-1, missing_data:
  [...], reasoning: str}`. Use Groq's JSON mode / tool-call response format (`response_format:
  {"type": "json_object"}`, or Groq's native tool-calling schema) so you get valid JSON back,
  not free text you have to parse.
- Failure mode to implement: **ambiguous/partial data**. If `missing_data` is non-empty,
  agent must NOT force a `applies: true/false` — write `status: "uncertain"` and let the
  Document Agent and Notification Agent handle it (e.g. "we need your income certificate to
  confirm this match").

### 3.4 Document Agent
- Mostly deterministic: compares `scheme.required_documents` against
  `citizen_documents_held` (both structured, from the DB) — no LLM needed for the comparison
  itself.
- LLM use (8B-tier): turning a missing-document list into a step-by-step checklist with
  plain-language guidance ("visit your local Tehsildar office for an income certificate").
- Failure mode to implement: **new rule makes an existing profile incomplete**. Triggered by
  the Discovery Agent flagging a `document_rule` change — Document Agent re-runs the
  comparison for every citizen whose profile touches that document type, not just the demo
  citizen (even if only the demo citizen is shown live).

### 3.5 Conflict & Explainability Agent
- 70B-tier LLM call over the citizen's full current match set (from `match_records`),
  prompted specifically to look for: (a) mutual-exclusivity flags between schemes (seed this
  as a field on scheme records — `mutually_exclusive_with: [scheme_id, ...]`), and (b)
  same-document-type requirements sourced from different authorities (state vs. central) with
  different rules.
- Also generates the "why/why-not" explanation for the Why-Not-Matched Explorer surface —
  same LLM call type, different prompt: given a scheme the citizen does NOT match, name the
  specific disqualifying criterion and whether it's fixable (has a remediation path, e.g.
  renewing an expired certificate) or fixed (e.g. an age cutoff).
- Failure mode to implement: **central vs. state rule mismatch for the same document type**
  — this is a seeded test case (Section 4.4), not something you need real conflicting data for.

### 3.6 Notification Agent
- 8B-tier LLM call to turn a structured event (`new_match`, `document_needed`,
  `conflict_detected`, `source_degraded`) into a plain-language notification string.
- Tools: for the hackathon demo, "delivery" can be simulated as a row insert into a
  `notifications` table that the frontend subscribes to via Supabase Realtime — no need to
  build actual SMS/email/push infrastructure for Stage 1, but design the `notifications` table
  with a `channel` field so real delivery is a drop-in later.
- Failure mode to implement: **delivery failure → retry or escalate**. Simulate by having a
  `simulate_delivery_failure` flag the admin panel can set on a specific notification; on
  failure, agent retries once, then writes a `status: "escalated"` row that the audit log and
  UI both surface, rather than failing silently.

### 3.7 Orchestrator / Planner
- Not a separate LLM-heavy node — it's the LangGraph conditional-routing logic described in
  2.2, plus one lightweight LLM call (8B-tier) used only to produce the human-readable
  "here's what changed and why" summary line shown on the admin panel during re-planning.
- Must-have implementation detail: **every node's failure is caught by the graph, never
  allowed to raise unhandled** — wrap each node function in a try/except that converts any
  exception into a `status: "failed"` state write, so the Orchestrator always has something to
  route on. This is what "must not silently stop" means concretely.

---

## 4. Data layer — schema (Supabase / Postgres)

Design goal: every functional requirement in Section 5 of the handoff doc maps to a real
table/column, not a vague JSON blob.

### 4.1 `citizens`
`id (uuid, pk)`, `created_at`, `display_name` (synthetic, demo-only)

### 4.2 `citizen_attributes`
`id (uuid, pk)`, `citizen_id (fk)`, `attribute_key` (e.g. `age`, `income`, `category`,
`state`, `gender`, `occupation`, `disability_status`), `attribute_value`, `consent_purpose`,
`consent_granted (bool)`, `consent_timestamp`, `revoked_at (nullable)`

This is the table Row-Level Security locks down (Section 6.3) — one row per attribute per
purpose, not one wide "profile" row, so consent is genuinely per-attribute-per-purpose as the
brief requires.

### 4.3 `citizen_documents_held`
`id`, `citizen_id (fk)`, `document_type`, `status` (`held` / `expired` / `pending`),
`issued_date`, `expiry_date (nullable)`, `issuing_authority`

### 4.4 `schemes`
`id`, `name`, `description`, `criteria` (jsonb — structured: age_min/max, income_ceiling,
category, state, gender, occupation), `required_documents` (jsonb array of document_type),
`mutually_exclusive_with` (array of scheme ids — for the Conflict Agent), `source`
(`seeded` — per constraints, this is authored content, label it honestly), `authority_level`
(`state` / `central`), `last_updated`

**Seed at least one deliberate conflict pair** (two mutually-exclusive schemes) and **one
deliberate state-vs-central document mismatch** (same `document_type`, different
`issuing_authority` rules) so the Conflict Agent has real data to demonstrate against, not
just handle hypothetically.

### 4.5 `document_rules`
`id`, `document_type`, `required_for` (jsonb — which scheme/criteria it applies to),
`effective_date`, `issuing_authority`, `validity_period_days (nullable)`

### 4.6 `match_records`
`id`, `citizen_id (fk)`, `scheme_id (fk)`, `confidence (0-1)`, `justifying_attributes`
(jsonb array of `citizen_attributes.id` — this is the audit trail link),
`status` (`matched` / `needs_document` / `conflicting` / `uncertain` / `rejected`),
`rejection_reason (nullable)`, `created_at`, `updated_at`

### 4.7 `audit_log`
`id`, `citizen_id (fk)`, `agent_name`, `action`, `justifying_attribute_ids (jsonb array,
nullable)`, `reasoning (text)`, `status`, `created_at`

Every agent writes here on every decision — this table is what the audit-trail UI surface
queries directly, not application logs.

### 4.8 `notifications`
`id`, `citizen_id (fk)`, `type`, `message`, `channel`, `delivery_status`
(`sent`/`failed`/`escalated`), `created_at`

### 4.9 Simulated-feed / demo-control tables
- `scheme_source` — the "external feed" the Discovery Agent watches; admin panel INSERTs
  here to simulate "a new scheme was published."
- `document_rule_source` — same pattern, for rule changes.
- `cached_snapshot` — last-known-good copy of the above two, used for the fallback demo path.
- `demo_control_flags` — single-row table the admin panel toggles: `source_offline (bool)`,
  `simulate_delivery_failure (bool)`. Discovery/Notification Agents check this table as part of
  their normal execution — this is how "take a source offline" becomes a real code path
  instead of a mocked stub.

---

## 5. Shared state schema (LangGraph state object)

Keep this typed (Pydantic model) so every node's read/write is validated, not ad hoc:

- `citizen_id`
- `trigger` — what started this graph run (`new_scheme`, `rule_change`, `scheduled_check`,
  `manual_demo_trigger`)
- `cleared_attributes` — populated only via `ConsentGateway`, never written directly by any
  other node
- `current_matches` — working list the Matching/Conflict agents read and update
- `pending_documents` — working list from the Document Agent
- `node_results` — dict of `{agent_name: {status, reason, output}}`, appended to by every node
  — this doubles as your audit trail's raw material and your SSE event source
- `replan_events` — list of `{from_node, to_node, reason, timestamp}`, written only by the
  Orchestrator routing function

---

## 6. Backend structure (FastAPI)

### 6.1 Key endpoints
- `POST /api/graph/run` — triggers a graph run for a citizen (`trigger` field as above)
- `GET /api/graph-events` (SSE) — streams node transitions/state changes for the live demo
- `POST /api/admin/inject-scheme` — writes to `scheme_source`, then triggers a graph run
- `POST /api/admin/inject-rule-change` — writes to `document_rule_source`, triggers a run
- `POST /api/admin/toggle-source-offline` — flips `demo_control_flags.source_offline`
- `GET /api/citizen/{id}/matches`, `/documents`, `/notifications`, `/audit-log` — power the
  four citizen-facing dashboard surfaces
- `POST /api/consent/{attribute_id}/revoke` — calls `ConsentGateway.revoke`

### 6.2 Auth
Use **Supabase Auth** directly (email/password or magic link is enough for a hackathon demo)
— the frontend gets a Supabase session token, FastAPI verifies it via Supabase's JWT
verification on protected routes. Don't build a separate auth system.

### 6.3 Making consent-scoped access structurally real
Two layers, not one:
- **Application layer:** `ConsentGateway` is the only class permitted to query
  `citizen_attributes` — enforce this by convention in code review, but back it with —
- **Database layer (the real enforcement):** Postgres Row-Level Security policy on
  `citizen_attributes` that only allows a row to be returned if a matching, non-revoked
  `consent_granted = true` row exists for the requesting purpose. This means even a bug in
  application code can't leak an unconsented attribute — the DB itself refuses the row. This
  is what turns "consent-scoped access must be real, not decorative" from a design promise
  into an enforced constraint.

### 6.4 Secrets management
`.env.local` (gitignored) for local dev with `GROQ_API_KEY`, `SUPABASE_URL`,
`SUPABASE_SERVICE_ROLE_KEY`, `DATA_GOV_IN_API_KEY`. In deployment, set the same as environment
variables in Vercel (frontend-safe keys only — anon key, not service role) and Railway/Render
(backend secrets). Add a `.env.example` with empty values to the repo so the third account
building this knows what's needed without ever seeing real values.

---

## 7. data.gov.in integration — concrete plan

### 7.1 What it's for (per the constraint)
Real demographic/socioeconomic context that plausibly feeds citizen-profile fields —
**not** scheme criteria or eligibility rules, which stay self-authored.

### 7.2 Mechanics
1. Register a free account at data.gov.in and generate an API key.
2. Base pattern: `https://api.data.gov.in/resource/<resource_id>?api-key=<key>&format=json
   &limit=<n>&filters[<field>]=<value>`
3. **Do not hardcode resource IDs from this document** — I was not able to independently
   verify current, working resource IDs for SECC/BPL-style datasets at the time of writing
   (data.gov.in's catalog and resource IDs change over time, and search results for this
   category returned dataset *listing pages*, not confirmed live API resource IDs). The
   handoff doc is explicit about this too: **search the catalog at build time.**
4. Concrete search terms to use directly on data.gov.in's catalog search (not a general web
   search) when building: `"Socio Economic Caste Census"`, `"BPL households state wise"`,
   `"district wise social category"`, `"below poverty line ration cards"`. Filter results to
   ones showing `"mode": "api"` (visible on the resource's page and in the resource's `/api`
   URL) — not every listed dataset has a live API, only some do.
5. Once a working resource_id is found, build a small `DataGovInClient` wrapper (Python,
   `requests`) with: `get_resource(resource_id, filters=None, limit=100)`, response caching to
   the `cached_snapshot` table (this data doubles as your offline-fallback demo path), and a
   clear error path if the key/resource is invalid — surface this as a Discovery Agent
   `status: "degraded"` event, same pattern as the scheme-source-offline failure mode.
6. Map whatever fields the found dataset actually has (e.g. state-wise household/income
   aggregates) onto **realistic default values for the synthetic demo citizen profile** — e.g.
   if the dataset gives a state's average rural household income bracket, use that to seed a
   plausible `income` value rather than inventing an arbitrary number. This is what "plausibly
   feeds citizen-profile fields" means in practice — real aggregate context shaping synthetic
   individual data, not a claim that the individual data itself is real.

---

## 8. Frontend — six surfaces, mapped to routes

Next.js App Router structure:

| Surface (from brief) | Route | Key components |
|---|---|---|
| Onboarding & consent center | `/onboarding` | Per-attribute toggle list with plain-language purpose text (from Consent Agent), progress stepper |
| Dashboard | `/dashboard` | Match cards (status + confidence badge), pulls from `match_records` via Supabase Realtime |
| Document vault & checklist | `/documents` | Held vs. missing document list, step-by-step checklist per missing item |
| Notification feed | `/notifications` | Chronological feed, subscribes to `notifications` table |
| Why-not-matched explorer | `/explore` | Search schemes, shows disqualifying criterion + fixable/fixed label for non-matches |
| Demo/admin control panel | `/admin` (auth-gated, separate from citizen login) | Buttons: inject new scheme, change document rule, toggle source offline, simulate delivery failure; live SSE-driven node graph visualization |

**Build order within frontend:** get the admin panel and dashboard working first and wired to
real backend state — those two are what the live demo actually shows. Onboarding, document
vault, and the explainability explorer matter for judging the *product* but aren't what's on
screen during the failure-injection moment.

**Component/animation libraries** (from earlier research) — use in this order of priority:
kokonutui.com / bklit.ui for the dashboard cards and charts (confidence indicators, status
badges), motion.dev / motion-primitives.com for the admin panel's live node-graph animation
(this is where animation actually earns its place — showing the plan visibly change), haikei.com
only if there's time left for the onboarding/landing page background.

---

## 9. Deployment plan

1. Frontend → **Vercel**, connected to the GitHub repo, auto-deploy on push to `main`.
2. Backend (FastAPI + LangGraph) → **Railway** or **Render** free tier, connected the same way.
   Needs a `Procfile` or equivalent start command (`uvicorn main:app --host 0.0.0.0 --port
   $PORT`).
3. Database/auth → **Supabase Cloud** project (free tier) — same project used by both frontend
   (via Supabase JS client, anon key) and backend (via Supabase Python client, service role key
   for the RLS-bypassing operations agents legitimately need, e.g. Discovery Agent reading
   `scheme_source`).
4. Confirm CORS is configured on FastAPI to allow the deployed Vercel domain.
5. Test the full failure-injection demo path **on the deployed version**, not just locally —
   SSE over some free-tier hosts can behave differently under a proxy; verify before the actual
   demo.

---

## 10. Testing / failure-injection approach for the demo

Build the admin panel's failure triggers as **real code paths that exercise the actual agent
logic**, not hardcoded canned responses:
- "Inject new scheme" → real INSERT into `scheme_source` → real Discovery Agent poll picks it
  up on its next cycle (trigger this poll on-demand from the admin action, don't wait for a
  timer during a live demo) → real Matching Agent run → real Notification Agent write.
- "Take source offline" → flips `demo_control_flags.source_offline` → Discovery Agent's fetch
  function checks this flag and raises a simulated `ConnectionError` → real fallback-to-cache
  logic runs, not a scripted message.
- Rehearse the exact click sequence and time it — the 3–5 minute script in the brief (Section
  7) is tight; the admin panel should require as few clicks as possible per demo beat.

---

## 11. Phased build order (no code — sequence only)

1. **Supabase project + schema** — create all tables from Section 4, set up RLS policy on
   `citizen_attributes` first (this is foundational, not a later add-on).
2. **Seed data** — synthetic citizen(s), schemes (including the deliberate conflict pair and
   state/central mismatch), document rules. Do this before building agents so there's real
   data to test against immediately.
3. **`ConsentGateway` + Consent & Profile Agent** — build and test attribute-read gating in
   isolation before anything else depends on it.
4. **LangGraph skeleton** — all 7 nodes as stubs that just pass state through, Orchestrator
   routing logic wired up, confirm the graph runs end-to-end with stub nodes.
5. **Discovery + Matching + Document agents** — real logic, tested against seeded data.
6. **Conflict & Explainability agent** — needs the above three working first since it reads
   their output.
7. **Notification agent + SSE event stream** — wire up real-time visibility.
8. **FastAPI endpoints** — expose the graph and admin actions.
9. **Frontend: admin panel + dashboard first** (per Section 8's build-order note), then the
   remaining four surfaces.
10. **data.gov.in integration** — do this in parallel with step 9 once a real working resource
    ID is confirmed (Section 7.4); it's not a blocker for anything else.
11. **Full failure-injection rehearsal** on the deployed version (Section 10).
12. **Audit log UI + why-not-matched explorer** — last, since they're judged on depth/polish
    but aren't the live-demo centerpiece.

---

## 12. Open items still needing a decision at build time

- Exact data.gov.in resource ID(s) — must be found via live catalog search, not assumed
  (Section 7.3–7.4).
- Whether to use Supabase Realtime or plain polling for the citizen-facing dashboard (Realtime
  is nicer but adds a small amount of setup complexity — polling every few seconds is an
  acceptable fallback if time is short).
- Final choice between Railway and Render for backend hosting — pick whichever the team
  already has more familiarity with; functionally equivalent for this project's needs.
