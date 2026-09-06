# Sher — Frontend / UI-UX (frontend/) — step by step

Branch: `sher/frontend` (then feature branches like `sher/admin-panel`, `sher/dashboard`)
You own: everything in `frontend/`. Nobody else should edit files in this folder.

## Step 1 — scaffold Next.js (see `frontend/README.md` for exact commands)

```bash
cd frontend
npx create-next-app@14.2.5 . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
npm install @supabase/supabase-js framer-motion
```

Create `frontend/.env.local` (gitignored) with the anon Supabase key (get from Hunar/Jaya,
**never** the service role key) and the backend URL — see `frontend/README.md` for the exact
variable names.

## Step 2 — get the Admin Panel working FIRST (this is the demo centerpiece)

A working stub already exists at `frontend/app/admin/page.tsx` — it wires up all 4 admin
actions and an SSE listener that dumps raw events to the screen. Your job:

1. Get it rendering (`npm run dev`, visit `http://localhost:3000/admin`).
2. Replace `DEMO_CITIZEN_ID` with the real citizen_id Jaya's seed script prints.
3. Click each button once with the backend running (Hunar's part must be up first:
   `uvicorn backend.main:app --reload`). **What to expect:** clicking "Inject New Scheme"
   should add new lines to the event list on screen within ~1 second, ending in a
   `graph_finished` event.
4. Now the actual design work: replace the raw JSON event list with an animated node-graph
   diagram (6 boxes: Consent, Discovery, Matching, Document, Conflict, Notification, plus the
   Orchestrator as the routing arrows between them). Use `framer-motion` to highlight the
   active node and animate a distinct color/pulse on any `plan_change` event — **this
   highlight-on-replan moment is the single most important visual in the whole project**,
   since it's literally the thing the judges are told to watch for.

## Step 3 — Dashboard (`/dashboard`)

- Fetch `GET /api/citizen/{id}/matches`, render one card per scheme: name, status badge
  (`matched` = green, `needs_document` = amber, `conflicting` = red, `uncertain` = gray),
  confidence as a percentage.
- Optional upgrade: subscribe to Supabase Realtime on `match_records` (filtered by
  `citizen_id`) instead of a one-time fetch, so the dashboard updates live during the demo
  without a manual refresh.

## Step 4 — remaining four surfaces (after 2 and 3 work)

Build `/onboarding`, `/documents`, `/notifications`, `/explore` per the route table in
`frontend/README.md`. Each just needs to call the matching backend endpoint and render the
response — none of these need the live-graph animation complexity of `/admin`.

## What to click / test at each step

- After every new page: open browser DevTools → Console tab. A red CORS error means Hunar's
  `CORS_ALLOWED_ORIGIN` doesn't match your dev server's actual origin — tell him the exact
  origin shown in your browser's address bar.
- After wiring Supabase Realtime anywhere: toggle your Supabase project's **Database →
  Replication** setting to confirm Realtime is enabled for that table (it's off by default on
  new tables) — ask Jaya/Hunar to check this in the Supabase dashboard if subscriptions don't
  fire.

## What NOT to do

- Don't put `SUPABASE_SERVICE_ROLE_KEY` anywhere in `frontend/` — only the anon key, only in
  `frontend/.env.local`, and only for read-only Realtime subscriptions / public data. All
  writes (consent revoke, admin actions) go through the FastAPI backend, never directly to
  Supabase from the browser.
- Don't hardcode API URLs — use `process.env.NEXT_PUBLIC_BACKEND_URL` everywhere so switching
  from localhost to the deployed Railway/Render URL is a one-line env var change.
- Don't touch `agents/`, `backend/`, or `db/` files.

## Deployment

1. Push `frontend/` to `main` via PR.
2. Vercel → "Add New Project" → import your GitHub repo → set root directory to `frontend/`.
3. Add `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, `NEXT_PUBLIC_BACKEND_URL`
   (pointing at Hunar's deployed Railway/Render URL) in Vercel's Environment Variables.
4. Deploy, then tell Hunar the resulting Vercel URL so he can set it as `CORS_ALLOWED_ORIGIN`.

## Commit checklist before opening a PR

- [ ] `npm run build` succeeds with no type errors
- [ ] Every route renders without crashing even if a backend call fails (wrap fetches in
      try/catch, show a friendly "couldn't load" state instead of a blank/broken page)
- [ ] No `.env.local` committed
- [ ] Admin panel's plan-change highlight actually fires when you toggle "source offline" and
      re-run the graph — verify this yourself before the team rehearsal, not during it
