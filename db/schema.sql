-- SchemeSaarthi database schema (Supabase / Postgres)
-- Owner: Jaya. Apply via Supabase SQL Editor, in this order: schema.sql, then rls_policies.sql,
-- then run seed.py.
-- Every functional requirement in Section 5 of the handoff doc maps to a real table/column here.

create extension if not exists "uuid-ossp";

-- 4.1 citizens
create table citizens (
    id uuid primary key default uuid_generate_v4(),
    created_at timestamptz not null default now(),
    display_name text not null  -- synthetic, demo-only, never a real name
);

-- 4.2 citizen_attributes
-- One row per (attribute, purpose) — NOT one wide profile row — so consent is genuinely
-- per-attribute-per-purpose, not per-citizen.
create table citizen_attributes (
    id uuid primary key default uuid_generate_v4(),
    citizen_id uuid not null references citizens(id) on delete cascade,
    attribute_key text not null,        -- age | income | category | state | gender | occupation | disability_status
    attribute_value text not null,
    consent_purpose text not null,      -- e.g. "SC/ST/OBC scholarship eligibility check"
    consent_granted boolean not null default false,
    consent_timestamp timestamptz not null default now(),
    revoked_at timestamptz              -- null while active; set on revoke
);

create index idx_citizen_attributes_citizen on citizen_attributes(citizen_id);
create index idx_citizen_attributes_key on citizen_attributes(attribute_key);

-- 4.3 citizen_documents_held
create table citizen_documents_held (
    id uuid primary key default uuid_generate_v4(),
    citizen_id uuid not null references citizens(id) on delete cascade,
    document_type text not null,                 -- e.g. "income_certificate"
    status text not null check (status in ('held', 'expired', 'pending')),
    issued_date date,
    expiry_date date,
    issuing_authority text
);

-- 4.4 schemes
create table schemes (
    id uuid primary key default uuid_generate_v4(),
    name text not null,
    description text not null,
    criteria jsonb not null,               -- {age_min, age_max, income_ceiling, category, state, gender, occupation}
    required_documents jsonb not null,     -- array of document_type strings
    mutually_exclusive_with uuid[] default '{}',
    source text not null default 'seeded' check (source in ('seeded')),
    authority_level text not null check (authority_level in ('state', 'central')),
    last_updated timestamptz not null default now()
);

-- 4.5 document_rules
create table document_rules (
    id uuid primary key default uuid_generate_v4(),
    document_type text not null,
    required_for jsonb not null,           -- which scheme_id(s) / criteria this applies to
    effective_date date not null,
    issuing_authority text not null,
    validity_period_days integer
);

-- 4.6 match_records
create table match_records (
    id uuid primary key default uuid_generate_v4(),
    citizen_id uuid not null references citizens(id) on delete cascade,
    scheme_id uuid not null references schemes(id) on delete cascade,
    confidence numeric(3,2) check (confidence between 0 and 1),
    justifying_attributes jsonb not null default '[]',  -- array of citizen_attributes.id — audit trail link
    status text not null check (status in ('matched', 'needs_document', 'conflicting', 'uncertain', 'rejected')),
    rejection_reason text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index idx_match_records_citizen on match_records(citizen_id);

-- 4.7 audit_log — every agent decision, queryable/displayable directly (not app log files)
create table audit_log (
    id uuid primary key default uuid_generate_v4(),
    citizen_id uuid references citizens(id) on delete cascade,
    agent_name text not null,
    action text not null,
    justifying_attribute_ids jsonb,
    reasoning text not null,
    status text not null,           -- ok | degraded | failed | uncertain | escalated
    created_at timestamptz not null default now()
);

create index idx_audit_log_citizen on audit_log(citizen_id);
create index idx_audit_log_created on audit_log(created_at desc);

-- 4.8 notifications
create table notifications (
    id uuid primary key default uuid_generate_v4(),
    citizen_id uuid not null references citizens(id) on delete cascade,
    type text not null,             -- new_match | document_needed | conflict_detected | source_degraded
    message text not null,
    channel text not null default 'in_app',
    delivery_status text not null default 'sent' check (delivery_status in ('sent', 'failed', 'escalated')),
    created_at timestamptz not null default now()
);

-- 4.9 Simulated-feed / demo-control tables
create table scheme_source (
    id uuid primary key default uuid_generate_v4(),
    payload jsonb not null,          -- shape matches a `schemes` row; Discovery Agent reads new rows
    seen boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table document_rule_source (
    id uuid primary key default uuid_generate_v4(),
    payload jsonb not null,
    seen boolean not null default false,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table cached_snapshot (
    id uuid primary key default uuid_generate_v4(),
    source_table text not null check (source_table in ('scheme_source', 'document_rule_source')),
    snapshot jsonb not null,
    captured_at timestamptz not null default now()
);

create table demo_control_flags (
    id integer primary key default 1 check (id = 1),   -- single-row table
    source_offline boolean not null default false,
    simulate_delivery_failure boolean not null default false
);
insert into demo_control_flags (id) values (1);

-- Also used by Discovery Agent to track "already seen" watermark per source
create table discovery_watermark (
    source_table text primary key,
    last_checked_at timestamptz not null default now()
);
insert into discovery_watermark (source_table) values ('scheme_source'), ('document_rule_source');
