# Full-stack testing guide — run this together, not solo, before rehearsing the demo

Do this once everyone's individual pieces pass their own checklist (see the per-person docs).

## Pre-flight (5 min)

1. Jaya confirms `db/schema.sql` + `db/rls_policies.sql` are applied and `python db/seed.py`
   has been run exactly once against the shared Supabase project. Note the printed
   `citizen_id` — everyone needs it.
2. Everyone pulls latest `main` and merges it into their branch.
3. Everyone's `.env.local` has the same 4 shared values (Groq key can differ per person if you
   each made your own account — fine, since Groq's free tier is per-API-key).

## Full local run

```bash
# Terminal 1 — backend (Hunar)
uvicorn backend.main:app --reload --port 8000

# Terminal 2 — frontend (Sher)
cd frontend && npm run dev

# Terminal 3 — free for manual curl/python testing
```

1. Open `http://localhost:3000/admin`. Confirm the SSE connection is live (no console errors).
2. Click **Run Full Graph Now**. Expect: events stream in ending with `graph_finished`, and
   `http://localhost:3000/dashboard` shows at least one `matched` scheme card afterward.
3. Click **Inject New Scheme**. Expect: a `node_result` event for `DiscoveryAgent` reporting a
   non-zero `new_scheme_count`, followed by `MatchingAgent` evaluating it, ending in a new
   notification visible at `/notifications`.
4. Click **Take Source Offline**, then **Run Full Graph Now** again. Expect: a `plan_change`
   event appears (highlighted differently in the UI per Sher's admin panel work),
   `DiscoveryAgent`'s status is `degraded` (if a cached snapshot exists from step 3) or
   `failed` (if nothing was ever cached yet — run step 3 once before testing this so a cache
   exists). Click **Bring Source Online** again afterward.
5. Click **Simulate Delivery Failure**, then **Run Full Graph Now**. Expect: at least one
   notification's `delivery_status` ends up `escalated` (visible via
   `GET /api/citizen/{id}/audit-log` or the notifications feed if Sher surfaces delivery status
   there). Turn the flag back off afterward.
6. Visit `/explore`, search for a scheme name the citizen doesn't match (e.g. the OBC
   Pre-Matric Scholarship, since the demo citizen is age 34, over the 18 age cutoff). Expect: a
   response naming the age cutoff as a "fixed" (not fixable) disqualifying criterion.
7. Visit `/onboarding`, revoke one attribute's consent (e.g. `income`). Re-run the graph.
   Expect: `ConsentProfileAgent`'s output no longer includes `income` in `cleared_keys`, and
   any match that depended on the income ceiling now shows `uncertain` instead of `matched`.

## Rehearsing the actual 3–5 minute demo script

Follow Section 7 of `SchemeSaarthi_Problem_Solution_Brief.docx` exactly, using the flow above
as your click sequence. Time yourselves at least twice before the real demo — SSE and Groq API
calls both add a few seconds of real latency that a scripted walkthrough won't reveal until you
run it live.

## If something breaks during integration testing

- **Backend won't start** → check `.env.local` matches `.env.example` exactly, check Supabase
  project isn't paused (free-tier Supabase projects pause after a week of inactivity — go to
  the dashboard and un-pause it, this is a common last-minute surprise).
- **Frontend gets CORS errors** → Hunar's `CORS_ALLOWED_ORIGIN` must exactly match the origin
  shown in the browser address bar (including port).
- **Graph run returns all `failed`** → almost always a Groq API key issue or a rate-limit hit;
  check `console.groq.com`'s usage dashboard.
- **No SSE events appear** → confirm you're running a single `uvicorn` worker (the in-memory
  pub/sub in `backend/sse.py` doesn't work across multiple worker processes) and that no
  browser extension is blocking EventSource connections.
