"""
Seed script — Owner: Jaya.

Populates:
  - one synthetic demo citizen with a full consented attribute set
  - a handful of realistic schemes, INCLUDING:
      * one deliberate mutually-exclusive pair (for the Conflict Agent to catch)
      * one deliberate state-vs-central document-type mismatch (same document_type,
        different issuing_authority + validity rules)
  - matching document_rules rows
  - one citizen_documents_held row that is EXPIRED, so the Document Agent has something
    real to flag on first run

Run once after schema.sql + rls_policies.sql are applied:
    python db/seed.py

Safe to re-run? NO — this always inserts fresh rows. If you need to reset between test runs,
truncate the tables first (see reset_demo_data() below) or wipe the Supabase project's tables
via the SQL editor.
"""
import os
import uuid
from datetime import date, timedelta

from dotenv import load_dotenv
from supabase import create_client

load_dotenv(".env.local")

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_ROLE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def reset_demo_data():
    """Optional: wipe demo data between test runs. Call manually, not part of default seed."""
    for table in [
        "notifications", "audit_log", "match_records", "citizen_documents_held",
        "citizen_attributes", "citizens", "document_rules", "schemes",
        "scheme_source", "document_rule_source", "cached_snapshot",
    ]:
        supabase.table(table).delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


def seed():
    # --- 1. Demo citizen ---
    citizen = supabase.table("citizens").insert({
        "display_name": "Demo Citizen (Meera, synthetic)"
    }).execute().data[0]
    citizen_id = citizen["id"]
    print(f"Created citizen {citizen_id}")

    # --- 2. Consented attributes (one row per attribute+purpose) ---
    attributes = [
        ("age", "34", "General eligibility screening"),
        ("income", "180000", "Income-based scheme eligibility (annual, INR)"),
        ("category", "OBC", "SC/ST/OBC scholarship & reservation-based eligibility"),
        ("state", "Odisha", "State-specific scheme eligibility"),
        ("gender", "female", "Gender-specific scheme eligibility"),
        ("occupation", "agricultural_laborer", "Occupation-based scheme eligibility"),
        ("disability_status", "none", "Disability-benefit eligibility"),
    ]
    attr_ids = {}
    for key, value, purpose in attributes:
        row = supabase.table("citizen_attributes").insert({
            "citizen_id": citizen_id,
            "attribute_key": key,
            "attribute_value": value,
            "consent_purpose": purpose,
            "consent_granted": True,
        }).execute().data[0]
        attr_ids[key] = row["id"]
    print(f"Seeded {len(attributes)} consented attributes")

    # --- 3. Document held, deliberately EXPIRED so Document Agent flags it on first run ---
    supabase.table("citizen_documents_held").insert({
        "citizen_id": citizen_id,
        "document_type": "income_certificate",
        "status": "expired",
        "issued_date": str(date.today() - timedelta(days=400)),
        "expiry_date": str(date.today() - timedelta(days=35)),
        "issuing_authority": "Odisha Revenue Department",
    }).execute()
    print("Seeded one expired income_certificate")

    # --- 4. Schemes — modeled on real central/state livelihood scheme structures ---
    # Scheme A models DAY-NRLM (Deendayal Antyodaya Yojana - National Rural Livelihoods
    # Mission), the Ministry of Rural Development's flagship rural-women livelihood program,
    # implemented at state level via State Rural Livelihood Missions (e.g. Odisha's OLM/Mission
    # Shakti). Criteria/documents below are authored to be realistic, not scraped from any
    # official API (none publishes a machine-readable eligibility ruleset — see Section 8 of
    # the brief).
    scheme_a = supabase.table("schemes").insert({
        "name": "State Rural Livelihood Mission — Women's SHG Grant",
        "description": "Modeled on DAY-NRLM / state Rural Livelihood Mission support for women's "
                        "self-help groups in agricultural and allied livelihoods below an income "
                        "ceiling. Provides seed capital and interest subvention for group enterprises.",
        "criteria": {"gender": "female", "occupation": "agricultural_laborer", "income_ceiling": 250000, "state": "Odisha"},
        "required_documents": ["income_certificate", "caste_certificate"],
        "authority_level": "state",
    }).execute().data[0]

    # Scheme B models PMEGP (Prime Minister's Employment Generation Programme), a real central
    # credit-linked subsidy scheme for new micro-enterprises, KVIC-administered — deliberately
    # made mutually exclusive with Scheme A for this demo (a citizen already drawing group SHG
    # support under a state livelihood mission realistically wouldn't also draw a separate
    # individual central enterprise subsidy at the same time).
    scheme_b = supabase.table("schemes").insert({
        "name": "Central Micro-Enterprise Credit Subsidy (PMEGP-style)",
        "description": "Modeled on PMEGP — a central credit-linked capital subsidy for setting "
                        "up a new micro-enterprise. Mutually exclusive with the State Rural "
                        "Livelihood Mission grant above (a citizen can only draw one at a time).",
        "criteria": {"gender": "female", "income_ceiling": 300000},
        "required_documents": ["income_certificate"],
        "authority_level": "central",
    }).execute().data[0]

    # deliberate mutual exclusivity, both directions
    supabase.table("schemes").update({"mutually_exclusive_with": [scheme_b["id"]]}).eq("id", scheme_a["id"]).execute()
    supabase.table("schemes").update({"mutually_exclusive_with": [scheme_a["id"]]}).eq("id", scheme_b["id"]).execute()
    print(f"Seeded mutually-exclusive pair: {scheme_a['id']} <-> {scheme_b['id']}")

    scheme_c = supabase.table("schemes").insert({
        "name": "OBC Pre-Matric Scholarship (central)",
        "description": "Modeled on the Ministry of Social Justice & Empowerment's real central "
                        "Pre-Matric Scholarship for OBC students — fixed age cutoff, not fixable "
                        "by the citizen, good for testing the 'why not matched — fixed, not "
                        "fixable' explanation path.",
        "criteria": {"category": "OBC", "age_max": 18},
        "required_documents": ["caste_certificate", "income_certificate"],
        "authority_level": "central",
    }).execute().data[0]
    print(f"Seeded fixed-disqualification scheme (age cutoff) {scheme_c['id']}")

    # --- 5. Deliberate state-vs-central document mismatch (same document_type,
    #         different issuing_authority + validity window) ---
    supabase.table("document_rules").insert([
        {
            "document_type": "income_certificate",
            "required_for": {"scheme_ids": [scheme_a["id"]]},
            "effective_date": str(date.today() - timedelta(days=200)),
            "issuing_authority": "state",
            "validity_period_days": 180,
        },
        {
            "document_type": "income_certificate",
            "required_for": {"scheme_ids": [scheme_b["id"]]},
            "effective_date": str(date.today() - timedelta(days=200)),
            "issuing_authority": "central",
            "validity_period_days": 365,
        },
    ]).execute()
    print("Seeded deliberate state-vs-central income_certificate validity mismatch")

    # --- 6. demo_control_flags row already exists from schema.sql (id=1); nothing to do ---

    print("\nSeed complete.")
    print(f"Demo citizen_id to use in API calls / frontend: {citizen_id}")


if __name__ == "__main__":
    seed()
