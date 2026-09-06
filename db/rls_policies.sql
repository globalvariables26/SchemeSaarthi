-- Row-Level Security — the REAL enforcement layer for "consent-scoped access must not be
-- decorative" (Section 6, handoff doc). Apply after schema.sql.
--
-- Design: the backend connects with the SERVICE ROLE key for agent-internal operations
-- (Discovery Agent reading scheme_source, etc.) — service role bypasses RLS by design in
-- Supabase, which is fine because ConsentGateway (application layer, agents/consent_gateway.py)
-- is the only code path that ever calls the consent-checked read below. The policy exists so
-- that even a bug in ConsentGateway, or any other future code path using the ANON key, cannot
-- read an attribute row without a matching, non-revoked, consent_granted=true row for that
-- specific purpose.

alter table citizen_attributes enable row level security;

-- No blanket "select own rows" policy — deliberately. A row is only readable if consent for
-- THAT purpose is currently active. This is stricter than typical per-user RLS.
create policy consent_scoped_read on citizen_attributes
    for select
    using (
        consent_granted = true
        and revoked_at is null
    );

-- Inserts/updates (granting or revoking consent) go through the service role in
-- ConsentGateway only — no anon-key policy needed for writes at this stage since citizens
-- don't write directly to Postgres; they call the FastAPI /api/consent endpoints, which use
-- the service role key server-side.

-- Lock down the demo-control and internal tables similarly — only the service role (backend)
-- should ever touch these, never the frontend's anon key directly.
alter table demo_control_flags enable row level security;
create policy service_role_only_flags on demo_control_flags
    for all
    using (auth.role() = 'service_role');

alter table scheme_source enable row level security;
create policy service_role_only_scheme_source on scheme_source
    for all
    using (auth.role() = 'service_role');

alter table document_rule_source enable row level security;
create policy service_role_only_doc_rule_source on document_rule_source
    for all
    using (auth.role() = 'service_role');

-- audit_log: citizens can read their own audit trail (for the "why did you tell me this" UI),
-- but never write to it directly — only agents (service role) write.
alter table audit_log enable row level security;
create policy read_own_audit_log on audit_log
    for select
    using (true);  -- for the hackathon demo, audit log is not per-authenticated-citizen-gated;
                   -- if you add real Supabase Auth citizen logins later, replace `true` with
                   -- `citizen_id = auth.uid()` once citizens.id is backed by auth.users.
