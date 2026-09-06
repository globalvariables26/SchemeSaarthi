SchemeSaarthi — Handoff Package for Orchestration & Tooling Design
Context for whoever is reading this: this is a Stage 1 submission for an agentic AI hackathon
(Tech Zephyr 4.0, IIT Bhubaneswar). The problem statement, features, and agent responsibilities
below are final and already decided — your job is to design the concrete orchestration
(framework choice, tool/API integration plan, data layer, and how the agents actually talk to each
other), not to re-pick the problem or the feature set. A separate account will use whatever you
produce here to actually build the project, so write your output to be equally self-contained for
that handoff.
---
1. Problem statement (final)
India runs 3,000+ central and state welfare schemes. The Government's own myScheme portal
already indexes 800+ of them for on-demand, pull-based discovery: a citizen enters age, income,
category, gender, occupation, state, and gets a list of possible matches. Despite this, rural scheme
awareness is estimated as low as 30% among eligible citizens, and large sums in benefits go
unclaimed every year — because discovery only happens if the citizen thinks to go check, and because
eligibility/document rules change continuously underneath them (a new mandatory document, a
changed certificate validity window, a state-vs-central rule mismatch).
SchemeSaarthi's job: flip this from pull to push. Continuously watch for new or changed
schemes and document rules, match them against a specific citizen's consented profile without
being asked, and help the citizen get any missing paperwork ready — with an explicit consent and
audit layer myScheme does not have.
2. Why this must be agentic (do not lose this framing)
A single-prompt chatbot answers a scheme-eligibility question once, from static data, when asked.
SchemeSaarthi must hold state over time, decide what to check and when, use tools to fetch/verify
information, evaluate whether its own matches are still valid, and re-plan when something changes
(a new scheme appears, a rule changes, a data source fails, two schemes conflict). This is the
justification to keep visible in the architecture — every agent below should map back to one of:
Goal → Decision → Action → Evaluation → Adaptation → Outcome.
3. Required agents and their exact responsibilities
Design your orchestration around these seven roles. You may combine or split them technically, but
every responsibility listed must be traceable to a specific component in your design.
Agent	Responsibility	Decides	Must be able to fail/adapt on
Consent & Profile Agent	Owns the citizen's attribute set (age, income, occupation, social category, disability status, state, gender, documents held)	Whether a given attribute may be used for a given match request; nothing else may read an attribute this agent hasn't cleared	Citizen revokes consent mid-session
Discovery Agent	Watches scheme and document-rule data sources for new/changed entries	What counts as "new" vs. "already seen"	A data source going offline or returning malformed data
Matching Agent	Compares a citizen's cleared attributes against a scheme's criteria	Whether a scheme applies, and at what confidence	Ambiguous/partial data → must express uncertainty, not force a match
Document Agent	Tracks documents held vs. required; drafts acquisition checklists	Which documents are missing or newly required	A new rule making an existing profile incomplete
Conflict & Explainability Agent	Evaluates the current match set for contradictions; generates "why/why-not" explanations	Whether two matched schemes are mutually exclusive; which is better for the citizen	Central vs. state rule mismatch for the same document type
Notification Agent	Decides when/how to inform the citizen of a new match, conflict, or document need	Timing and channel; confirms delivery	Delivery failure → retry or escalate
Orchestrator / Planner	Sequences all agents against the citizen's overall goal	The order of operations; re-plans when any agent reports failure	Any downstream agent failing — must not silently stop
4. Required live-demo behavior (this drives your architecture choices)
The demo must show, in a single 3–5 minute run, something changing mid-demo and the system
reacting without being re-prompted:
A new scheme is injected via an admin/demo panel → Discovery Agent picks it up → Matching Agent
evaluates it against the demo citizen profile → Notification Agent surfaces it.
A document rule changes, OR a data source is deliberately taken offline → Orchestrator detects
the failure/change → re-plans (falls back to a cached source, or re-runs the affected agents) →
explains what happened.
Whatever framework/stack you choose must make this re-planning step visibly demonstrable, not
just logged in a console — the audience needs to see the plan change on screen.
5. Data model (functional requirements, not final schema)
You decide the concrete schema, but it must support:
Per-citizen profile: a set of attributes, each with its own consent flag, consent purpose, and
timestamp (so the Consent & Profile Agent can answer "is attribute X clear for purpose Y" and "when
was this consented").
Scheme records: criteria (structured — age range, income ceiling, category, state, etc.),
required documents, source, last-updated timestamp.
Document-rule records: what's required, for whom, effective date, issuing authority
(state/central — needed for the conflict agent).
Match records: which scheme, which citizen, confidence, justifying attributes (for the audit
trail), status (matched / needs-document / conflicting / rejected-with-reason).
Audit log: every decision any agent makes, with which consented attribute justified it —
this needs to be queryable and displayable, not just written to a log file.
6. Explicit constraints (do not violate these in your design)
Real data source: data.gov.in only, never scraping. myScheme's Terms of Use explicitly
prohibit bots/scrapers ("prohibited unless expressly authorized by myScheme in writing"), and the
rulebook's Responsible AI section rules out unauthorized access — so myScheme (or any dataset
someone else scraped from it) is off-limits as a data source. The one legitimate real-data channel
is India's Open Government Data (OGD) Platform, data.gov.in — a genuine official API (free
API key from a data.gov.in account, per-dataset resource IDs, filterable JSON queries, no
scraping involved). Use it for real demographic/socioeconomic context (e.g. SECC-derived data)
that plausibly feeds citizen-profile fields. Part of your job at this stage is to identify which
specific data.gov.in datasets (resource IDs) are actually usable for this — search the catalog at
build time; don't assume a dataset exists without checking.
The scheme-eligibility ruleset itself is still self-authored, not fetched. No open API (not
myScheme, not data.gov.in) publishes a ready-made "scheme criteria + required documents" dataset.
Model it on real scheme structures, but it's built/seeded content, not a live integration. Design
your data layer so this is easy to keep current as more schemes are added by hand.
No DigiLocker, no Aadhaar, no live citizen document integration for this stage. All citizen
profiles and documents-held records are synthetic/seeded.
No real credentials in the repo — the rulebook explicitly disqualifies teams for this. If your
design needs API keys (LLM provider, hosting), specify how they're kept out of version control
(env vars + `.gitignore`, secrets manager, etc.) as part of your deliverable.
Consent-scoped access must be real, not decorative. The Matching Agent must not be able to
read an attribute the Consent & Profile Agent hasn't cleared — this should be enforced structurally
(e.g., attribute access goes through a single gated interface), not just as a comment or convention.
Every match must be labeled preliminary, never presented as an official determination — mirror
how myScheme itself frames its results.
7. What's genuinely open for you to decide
LLM/agent orchestration framework (e.g. LangGraph, CrewAI, a custom state machine, etc.) and why.
How agents communicate (shared state store, message passing, direct function calls).
The concrete data layer/database choice.
How you simulate the external scheme/document-rule feeds (mock API, seeded database with an
admin-triggerable "publish new scheme" action, etc.) — this needs to support the live-demo
requirement in Section 4.
Which specific data.gov.in datasets (by resource ID) are worth pulling in for demographic/
socioeconomic realism, and how that data maps onto citizen-profile fields.
Frontend approach for the six product surfaces: onboarding/consent center, dashboard, document
vault, notification feed, why-not-matched explorer, and the demo/admin control panel.
How you'll host/deploy a runnable version for the Stage 1 submission requirement.
Testing/failure-injection approach for the demo's "break something live" moment.
8. Deliverable expected back from this stage
A concrete technical architecture and tool list mapped one-to-one against the seven agents in
Section 3, plus a proposed data schema, plus a plan for simulating the external feeds — written so
that a third account, with no memory of this conversation, can start building directly from it.
