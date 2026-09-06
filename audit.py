"""Shared audit-log writer — every node calls this on every decision. Owner: Ishaan."""
from __future__ import annotations

from typing import Any, Optional

from supabase import Client


def write_audit(
    db: Client,
    *,
    citizen_id: str,
    agent_name: str,
    action: str,
    reasoning: str,
    status: str,
    justifying_attribute_ids: Optional[list[str]] = None,
) -> None:
    db.table("audit_log").insert({
        "citizen_id": citizen_id,
        "agent_name": agent_name,
        "action": action,
        "justifying_attribute_ids": justifying_attribute_ids or [],
        "reasoning": reasoning,
        "status": status,
    }).execute()
