# Jaya — Dataset & data layer (db/, datagovin/) — step by step

Branch: `jaya/db-and-data` (then feature branches like `jaya/datagovin-resource-id`)
You own: everything in `db/` and `datagovin/`. Nobody else should edit files in these folders.

**Good news:** the scheme research (real scheme names, eligibility criteria, the deliberate
mutually-exclusive pair, the state/central document mismatch) has already been done and is
filled into `db/seed.py` for you — modeled on real DAY-NRLM / PMEGP-style central and state
livelihood schemes. You don't need to browse myScheme yourself. Your work is mostly running
scripts and clicking through the Supabase dashboard, plus one account signup only you can do
(Step 3 below — it needs a real email/OTP, so nobody can create it on your behalf).

## Step 1 — help set up the shared Supabase project (with Hunar — see his doc, Step 1)

You don't have to be the one who clicks "New Project," but be present, since you'll be running
the schema/seed scripts against it constantly.

## Step 2 — apply the schema, then seed

1. Supabase dashboard → SQL Editor → paste `db/schema.sql` → Run.
2. Check the Table Editor tab — you should see 13 new tables.
3. New query → paste `db/rls_policies.sql` → Run.
4. Locally: `pip install -r requirements.txt`, `cp .env.example .env.local` (fill in real
   values), then:
   ```bash
   python db/seed.py
   ```
   **What to expect:** prints confirmation lines ending in `Demo citizen_id to use in API
   calls / frontend: <uuid>`. **Copy this UUID and share it with Ishaan, Hunar, and Sher.**
5. Spot-check in the Table Editor: `schemes` should have 3 rows, one pair with
   `mutually_exclusive_with` pointing at each other; `document_rules` should have 2 rows with
   the same `document_type` but different `issuing_authority`.

## Step 3 — data.gov.in account (the one thing that needs a real human)

1. Register at https://data.gov.in → generate an API key (My Account → API Keys). Put it in
   your `.env.local` as `DATA_GOV_IN_API_KEY`.
2. Search data.gov.in's own catalog (not Google) for "Socio Economic Caste Census" or "BPL
   households state wise" — open a result, check its page shows an API option, and note the
   resource_id shown in its API URL.
3. Test it with one plain URL in your browser (fill in the resource_id and your key):
   `https://api.data.gov.in/resource/<resource_id>?api-key=<your-key>&format=json&limit=5`
4. If it returns real JSON — plug the resource_id into `datagovin/client.py`'s
   `get_resource()` calls and use a plausible field (e.g. a state's average household income
   bracket) to make `db/seed.py`'s citizen `income` value more realistic. Note in your commit
   message which dataset the number came from.
5. If nothing usable turns up after a genuine try — that's a fine, expected outcome (flagged
   as uncertain in the original brief too). Leave a comment in `datagovin/client.py` noting
   what you tried, and keep the synthetic seeded income value as-is.

## What NOT to do

- Don't touch `agents/`, `backend/`, or `frontend/` files.
- Don't re-run `db/seed.py` casually once the team is testing against real citizen_ids — it
  always inserts fresh rows. If you need a clean slate, tell the team first, then use the
  `reset_demo_data()` function in `seed.py`.

## Commit checklist before opening a PR

- [ ] `db/schema.sql` and `db/rls_policies.sql` run clean on the shared Supabase project
- [ ] `python db/seed.py` runs and prints a citizen_id
- [ ] No `.env.local` or real API key committed
