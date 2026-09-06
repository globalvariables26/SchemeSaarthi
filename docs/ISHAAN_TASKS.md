# Ishaan — AI-ML core (agents/) — step by step

Branch: `ishaan/agents` (then feature branches like `ishaan/matching-agent-tests`)
You own: everything in `agents/`. Nobody else should edit files in this folder.

## What's already scaffolded for you (in this handoff)

- `agents/state.py` — the shared Pydantic state object every node reads/writes
- `agents/consent_gateway.py` — the ONLY class allowed to read `citizen_attributes`
- `agents/llm_client.py` — Groq wrapper (`call_json` for structured output, `call_text` for plain text)
- `agents/context.py` — bundles the Supabase client + ConsentGateway for every node
- `agents/audit.py` — `write_audit()` helper every node calls
- `agents/nodes/*.py` — all 7 agents, with real logic already written against the spec in
  `SchemeSaarthi_Technical_Orchestration.md` Section 3
- `agents/orchestrator.py` — the LangGraph graph, wired with conditional routing

**Your job is not to write these from scratch — it's to get them running, test them against
real seeded data, fix whatever breaks, and extend them (better prompts, more failure-mode
coverage) as time allows.**

## Step 1 — account/tooling setup

1. Go to https://console.groq.com → sign up (no card needed) → API Keys → Create Key.
   Paste it into your local `.env.local` as `GROQ_API_KEY=...`. **Never paste this into a
   GitHub commit, a Slack/Discord message that's logged, or this chat.**
2. Get the three Supabase values (`SUPABASE_URL`, `SUPABASE_ANON_KEY`,
   `SUPABASE_SERVICE_ROLE_KEY`) from Hunar or Jaya once they've created the shared Supabase
   project (Step 1 of their docs) — share these over a private channel, not a public repo/PR.
3. In VS Code: open the repo, `python -m venv venv`, activate it, `pip install -r requirements.txt`.

## Step 2 — get ConsentGateway working in isolation FIRST

Per the phased build order (Section 11), this must work before anything else depends on it.

```bash
python
>>> from dotenv import load_dotenv; load_dotenv(".env.local")
>>> from agents.context import build_context
>>> ctx = build_context()
>>> ctx.consent.get("<citizen_id from db/seed.py output>", "age", "General eligibility screening")
```

**What to expect:** this will likely return `None` at first, because `db/seed.py` seeds
attribute-SPECIFIC purpose strings (e.g. `"Income-based scheme eligibility (annual, INR)"` for
income), not the generic `"General eligibility screening"` string for every attribute. Look at
`db/seed.py`'s `attributes` list to see the exact purpose string seeded for each key, and test
with the matching purpose. (`consent_agent.py`'s fallback loop already handles this mismatch
for the full graph run — this manual test is just to confirm the gateway itself works.)

**Test revocation:**
```python
>>> attr_id = "<copy the id from the citizen_attributes table in Supabase's table editor>"
>>> ctx.consent.revoke(attr_id)
>>> ctx.consent.get("<citizen_id>", "age", "General eligibility screening")  # should now be None
```
If it's `None` after revoking — gateway works. If it still returns a value, check
`db/rls_policies.sql` was actually applied (ask Jaya) and check `revoked_at` got set in the
Supabase table editor.

## Step 3 — run the LangGraph skeleton end-to-end

```bash
python
>>> from dotenv import load_dotenv; load_dotenv(".env.local")
>>> from agents.orchestrator import run_graph_for_citizen
>>> state = run_graph_for_citizen("<citizen_id>", "manual_demo_trigger")
>>> state.node_results
```

**What to expect the first time:** every agent should report a `NodeResult` with some status.
Since `db/seed.py` seeds no rows in `scheme_source`/`document_rule_source` yet, the Discovery
Agent will report `status: "ok"`, `reason: "No new or changed entries since last check."`
Matching Agent should evaluate the 3 seeded schemes and return `matched` for at least one
(the demo citizen is seeded to match the Rural Women Livelihood Grant). If you get a Groq API
error, check your `GROQ_API_KEY` and that you haven't blown the 1,000/day cap on the 70B model.

**Test the failure paths (do this before the actual demo, not the morning of):**
```python
# Simulate source-offline:
>>> ctx.db.table("demo_control_flags").update({"source_offline": True}).eq("id", 1).execute()
>>> state = run_graph_for_citizen("<citizen_id>", "manual_demo_trigger")
>>> state.node_results["DiscoveryAgent"].status   # should be "degraded" or "failed"
>>> state.replan_events                            # should show a plan_change entry
>>> ctx.db.table("demo_control_flags").update({"source_offline": False}).eq("id", 1).execute()
```

## What NOT to do

- Don't let any node raise an unhandled exception — every node already wraps its body in
  try/except; if you add new logic inside a node, keep it inside that try block.
- Don't have any node other than `consent_agent.py` call `ctx.consent` directly and cache the
  result across node calls — every node should re-derive what it needs from
  `state.cleared_attributes`, which only the Consent Agent populates.
- Don't loop the 70B model (`REASONING_MODEL`) more than necessary while testing — you have
  1,000 requests/day. Use the 8B model (`FAST_MODEL`) for anything that doesn't need real
  reasoning.
- Don't touch `backend/`, `frontend/`, or `db/` files — flag issues to Hunar/Sher/Jaya instead.

## Commit checklist before opening a PR

- [ ] `python -c "from agents.orchestrator import get_graph; get_graph()"` runs without error
- [ ] A full `run_graph_for_citizen` call produces a non-empty `current_matches` list
- [ ] Both failure paths (source offline, and forcing a Matching Agent LLM error by feeding a
      malformed scheme criteria) produce a `status: failed/degraded` + a `replan_events` entry
- [ ] No `.env.local` or real key committed (`git status` check)
