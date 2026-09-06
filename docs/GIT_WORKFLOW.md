# Git Workflow — 4-person team, one branch per person (+ per-feature sub-branches)

Goal: nobody works directly on `main`, nobody edits another person's folder without asking,
and conflicts stay rare because each person's code lives in a different top-level folder.

## Folder ownership → merge conflict prevention

```
agents/     → Ishaan only
backend/    → Hunar only
frontend/   → Sher only
db/         → Jaya only
docs/       → anyone, but announce in your team chat before editing someone else's task file
```

If you ever need to touch a file outside your folder (e.g. Hunar needs to import something
from `agents/`), **don't edit it yourself** — message the owner, or open a PR against their
branch and let them merge it.

## One-time setup (whoever creates the repo — pick one person, e.g. Hunar)

```bash
# 1. Create the repo on GitHub first (empty, no README) — call it schemesaarthi
git clone https://github.com/<org-or-username>/schemesaarthi.git
cd schemesaarthi

# 2. Copy in everything from this scaffold, then:
git add .
git commit -m "Initial scaffold: folder structure, schema, agent stubs, docs"
git branch -M main
git push -u origin main

# 3. Protect main so nobody pushes to it directly (GitHub UI):
#    Settings → Branches → Add branch protection rule → main
#    → check "Require a pull request before merging"
```

## Everyone else: clone and create your own branch

```bash
git clone https://github.com/<org-or-username>/schemesaarthi.git
cd schemesaarthi
git checkout -b ishaan/agents        # Ishaan
git checkout -b hunar/backend        # Hunar
git checkout -b sher/frontend        # Sher
git checkout -b jaya/db-and-data     # Jaya
```

Naming pattern going forward: `<name>/<short-feature>`, e.g. `ishaan/matching-agent`,
`hunar/sse-endpoint`, `sher/admin-panel`, `jaya/seed-conflict-pair`. Cutting a fresh small
branch per feature (off your own main working branch, or off `main`) keeps PRs reviewable.

## Daily loop for each person

```bash
git checkout main
git pull origin main                 # get everyone's latest merged work
git checkout ishaan/agents           # (or your branch)
git merge main                       # bring your branch up to date, resolve conflicts here
                                      # ... do your work, staying inside your folder ...
git add <your files only>
git commit -m "Discovery agent: source-offline fallback to cached_snapshot"
git push -u origin ishaan/agents
```

Then open a Pull Request on GitHub: `ishaan/agents` → `main`. At least one other teammate
reviews and approves before merging (even a quick skim — this is what catches "oops I edited
your file" early). After merging, delete the branch and cut the next feature branch fresh
from an updated `main`.

## Commit message convention (keeps the history readable for judges too)

`<area>: <what changed>` — e.g.
- `agents: implement ConsentGateway.revoke with immediate re-check`
- `backend: add /api/admin/inject-scheme endpoint`
- `frontend: admin panel live node-graph via SSE`
- `db: seed deliberate mutually-exclusive scheme pair`

## Rules

1. Never `git push --force` to `main`.
2. Never commit `.env`, `.env.local`, or any file containing a real API key — `.gitignore`
   already excludes these; double-check with `git status` before every commit.
3. Small, frequent commits/PRs beat one giant end-of-day merge — merge conflicts get
   exponentially worse the longer branches diverge.
4. If you get a merge conflict inside your own folder only (e.g. two of Ishaan's own
   branches), resolve it yourself. If it's across folders, that means someone touched a file
   they don't own — talk to that person before resolving.
