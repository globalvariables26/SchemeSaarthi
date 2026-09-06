# Hunar — Backend (backend/) — step by step

Branch: `hunar/backend` (then feature branches like `hunar/sse-endpoint`)
You own: everything in `backend/`. Nobody else should edit files in this folder.
You are also the likely person to **create the shared Supabase project** (coordinate with Jaya
— whoever does it, share the 3 keys with the team over a private channel, never in GitHub).

## Step 1 — create the shared Supabase project (do this WITH Jaya, once, together)

1. Go to https://supabase.com → sign up (GitHub login is fine) → "New Project".
2. Name it `schemesaarthi`, pick any region close to you, set a DB password (save it somewhere
   safe — a password manager, not a chat).
3. Once created, go to **Project Settings → API**. Copy these three values into a private note
   shared with the team (e.g. a pinned message in your team's private chat, NOT a GitHub issue
   or public channel):
   - `Project URL` → `SUPABASE_URL`
   - `anon public` key → `SUPABASE_ANON_KEY`
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (⚠️ this one bypasses all security —
     never put it in frontend code, only backend `.env.local`)
4. Everyone (you, Ishaan, Jaya, Sher) pastes these into their own local `.env.local` — never
   into a file that gets committed.

## Step 2 — apply the schema (coordinate with Jaya — she owns `db/`, but you'll likely be the
one actually clicking "Run" in the Supabase SQL editor the first time, together)

1. Supabase dashboard → SQL Editor → New query.
2. Paste the entire contents of `db/schema.sql` → Run. Confirm no errors (check the Table
   Editor tab afterward — you should see `citizens`, `schemes`, `match_records`, etc.)
3. New query → paste `db/rls_policies.sql` → Run.
4. Ask Jaya to run `python db/seed.py` (real scheme names are already filled in — see
   `db/seed.py`, no more research needed there) and give you the printed `citizen_id` — you'll
   need it for testing every endpoint below.

## Step 3 — run the backend locally

```bash
pip install -r requirements.txt
cp .env.example .env.local     # fill in the 4 real values
uvicorn backend.main:app --reload --port 8000
```

Visit `http://localhost:8000/health` — should return `{"status": "ok"}`. If it doesn't start,
the error is almost always a missing/misnamed env var — check `.env.local` matches
`.env.example`'s variable names exactly.

Visit `http://localhost:8000/docs` — FastAPI's auto-generated interactive API docs. Use this to
test every endpoint by hand before Sher's frontend exists — click "Try it out" on each one.

## Step 4 — test each endpoint, in this order

1. `GET /api/citizen/{citizen_id}/attributes` — should list 7 seeded attributes.
2. `POST /api/graph/run` with `{"citizen_id": "<id>", "trigger": "manual_demo_trigger"}` —
   should return `node_results` for all 6 agent nodes and a non-empty `current_matches`.
3. `GET /api/citizen/{citizen_id}/matches` — should reflect what step 2 just wrote.
4. `GET /api/citizen/{citizen_id}/notifications` — should show messages generated in step 2.
5. `GET /api/citizen/{citizen_id}/audit-log` — should show one row per agent decision.
6. `POST /api/admin/toggle-source-offline` with `{"offline": true}`, then repeat step 2 —
   `DiscoveryAgent`'s status in the response should now be `degraded` or `failed`, and
   `replan_events` in the raw graph state should be non-empty (check via a Python shell if the
   `/api/graph/run` JSON doesn't show it directly — extend the endpoint's response if you want
   it visible there too, that's your call as backend owner).
7. Toggle source back online (`{"offline": false}`) before moving on.
8. `GET /api/graph-events` (SSE) — this won't render nicely in `/docs`; test it with:
   ```bash
   curl -N http://localhost:8000/api/graph-events
   ```
   in one terminal, then trigger `POST /api/graph/run` in another — you should see events
   stream into the first terminal in real time.

## What NOT to do

- Don't query `citizen_attributes` directly anywhere in `backend/` except the one documented
  exception (`get_attributes` — reading a citizen's OWN consent state for the onboarding UI).
  Every other read of attribute data must go through `ConsentGateway`, imported from `agents/`.
- Don't put the `SUPABASE_SERVICE_ROLE_KEY` anywhere that ships to the browser — it stays
  server-side only, in `backend/.env.local` and later in Railway/Render's env var dashboard.
- Don't touch `agents/`, `frontend/`, or `db/` files — flag issues to Ishaan/Sher/Jaya instead.
  If you need a new field in `GraphState` or a new endpoint's data shape, ask Ishaan to add it.

## Deployment (once local works end-to-end)

1. Push `backend/`, `agents/`, `requirements.txt` to `main` via PR.
2. Create a Railway (or Render) project, connect your GitHub repo.
3. Set start command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
4. Add all 4 env vars from `.env.example` in Railway/Render's dashboard (real values).
5. Set `CORS_ALLOWED_ORIGIN` to your deployed Vercel frontend URL once Sher has one.
6. Test `GET /health` on the deployed URL before telling the team it's ready.
7. **Before the actual demo:** test the SSE endpoint on the deployed version specifically —
   some free-tier hosts proxy SSE differently than localhost. Do this at least a day early,
   not the morning of the demo.

## Commit checklist before opening a PR

- [ ] `uvicorn backend.main:app --reload` starts with no errors
- [ ] All endpoints in Step 4 return the expected shape (checked via `/docs`)
- [ ] No `.env.local` or real key committed
- [ ] CORS origin matches whatever Sher's `npm run dev` actually serves on (usually
      `http://localhost:3000`)
