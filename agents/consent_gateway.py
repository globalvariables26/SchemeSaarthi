"""
ConsentGateway — Owner: Ishaan. Build and test this BEFORE any other agent (per phased build
order, Section 11 of the orchestration doc).

This is the ONLY class in the entire codebase permitted to read `citizen_attributes`. No other
agent, endpoint, or script should query that table directly — enforce this in code review.
The real enforcement is the Postgres RLS policy in db/rls_policies.sql: even if this class had
a bug, the database itself refuses to return a row unless consent_granted=true and
revoked_at is null for that purpose.

Critical behavior: NOTHING caches an attribute value beyond one node execution. Every call to
`get()` re-checks the database, so a mid-session `revoke()` takes effect immediately for the
very next read — this is the "mid-session revocation" failure mode the handoff doc requires.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from supabase import Client

from agents.state import ClearedAttribute


class ConsentGateway:
    def __init__(self, supabase: Client):
        self._db = supabase

    def get(self, citizen_id: str, attribute_key: str, purpose: str) -> Optional[ClearedAttribute]:
        """Return the cleared attribute value for this exact (citizen, key, purpose), or None
        if no active, non-revoked, granted consent row exists. Always hits the DB — no cache."""
        result = (
            self._db.table("citizen_attributes")
            .select("id, attribute_value, consent_granted, revoked_at")
            .eq("citizen_id", citizen_id)
            .eq("attribute_key", attribute_key)
            .eq("consent_purpose", purpose)
            .eq("consent_granted", True)
            .is_("revoked_at", "null")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return None
        row = rows[0]
        return ClearedAttribute(
            attribute_key=attribute_key,
            attribute_value=row["attribute_value"],
            citizen_attribute_id=row["id"],
        )

    def get_all_for_purpose(self, citizen_id: str, purpose: str) -> dict[str, ClearedAttribute]:
        """Convenience for nodes (e.g. Matching Agent) that need several attributes cleared for
        the same stated purpose at once. Still one DB round trip per call, never cached across
        node executions."""
        result = (
            self._db.table("citizen_attributes")
            .select("id, attribute_key, attribute_value")
            .eq("citizen_id", citizen_id)
            .eq("consent_purpose", purpose)
            .eq("consent_granted", True)
            .is_("revoked_at", "null")
            .execute()
        )
        out: dict[str, ClearedAttribute] = {}
        for row in result.data or []:
            out[row["attribute_key"]] = ClearedAttribute(
                attribute_key=row["attribute_key"],
                attribute_value=row["attribute_value"],
                citizen_attribute_id=row["id"],
            )
        return out

    def revoke(self, attribute_id: str) -> None:
        """Immediately flips consent_granted off for this specific attribute row. Every
        subsequent ConsentGateway.get() call for it will return None starting now — no agent
        needs to be told separately; they just won't see the attribute on their next read."""
        self._db.table("citizen_attributes").update({
            "consent_granted": False,
            "revoked_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", attribute_id).execute()

        # Log the revocation itself for the audit trail.
        row = self._db.table("citizen_attributes").select("citizen_id, attribute_key").eq("id", attribute_id).execute().data
        if row:
            self._db.table("audit_log").insert({
                "citizen_id": row[0]["citizen_id"],
                "agent_name": "ConsentGateway",
                "action": "revoke_consent",
                "justifying_attribute_ids": [attribute_id],
                "reasoning": f"Citizen revoked consent for attribute '{row[0]['attribute_key']}'.",
                "status": "ok",
            }).execute()
