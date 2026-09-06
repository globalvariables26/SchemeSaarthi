# SchemeSaarthi frontend — Owner: Sher

Next.js (App Router) + Tailwind. Talks to the FastAPI backend (Hunar, `localhost:8000` locally)
and to Supabase directly for Realtime subscriptions (dashboard, notifications).

## First-time setup

```bash
cd frontend
npx create-next-app@14.2.5 . --typescript --tailwind --app --no-src-dir --import-alias "@/*"
# when prompted about overwriting files, keep this package.json / keep existing files where asked
npm install @supabase/supabase-js framer-motion
```

Create `frontend/.env.local` (gitignored):
```
NEXT_PUBLIC_SUPABASE_URL=<from team>
NEXT_PUBLIC_SUPABASE_ANON_KEY=<from team — the ANON key only, never service role>
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
```

## The six surfaces (routes) — build in THIS order

Per the orchestration doc: **admin panel + dashboard first** — those two are what's on screen
during the live failure-injection demo moment. The other four matter for judging depth but
aren't the live-demo centerpiece.

1. `/admin` — buttons: inject new scheme, change document rule, toggle source offline,
   simulate delivery failure. Subscribes to `GET /api/graph-events` (SSE) and renders a live
   animated node graph — this is the single most important screen for the demo. See
   `app/admin/page.tsx` stub already in this repo.
2. `/dashboard` — match cards (scheme name, status, confidence badge). Pull via
   `GET /api/citizen/{id}/matches`, or subscribe to `match_records` via Supabase Realtime for
   live updates without polling.
3. `/onboarding` — per-attribute consent toggle list (`GET /api/citizen/{id}/attributes`,
   `POST /api/consent/{attribute_id}/revoke`), plain-language purpose text.
4. `/documents` — held vs missing documents + checklist (`GET /api/citizen/{id}/documents`,
   plus `pending_documents` from the last `/api/graph/run` response).
5. `/notifications` — chronological feed (`GET /api/citizen/{id}/notifications`, or Realtime
   subscribe to `notifications` table).
6. `/explore` — search box hitting `GET /api/citizen/{id}/explore?scheme_name_query=...`.

## Component/animation libraries — use in this priority order

1. **kokonutui.com** / **bklit.ui** — dashboard cards, confidence badges, status chips.
2. **motion.dev** / **motion-primitives.com** (or `framer-motion`, already in package.json) —
   the admin panel's live node-graph animation. This is where animation actually earns its
   place: showing the plan visibly change is the core demo requirement.
3. **haikei.com** — only if there's time left, for the onboarding/landing page background.

## Testing your work before opening a PR

- `npm run dev`, confirm each route renders without a crash even with an empty/mock backend
  response (don't let one missing field crash the whole page — use optional chaining / default
  empty arrays).
- With the backend running locally (`uvicorn backend.main:app --reload`) and seed data loaded,
  click every admin panel button once and confirm you see a new SSE event render on screen.
- Check the browser console for CORS errors — if you see one, `CORS_ALLOWED_ORIGIN` in the
  backend's `.env.local` needs to match your frontend's actual origin.
