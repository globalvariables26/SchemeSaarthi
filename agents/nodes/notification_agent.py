"""
Notification Agent — Owner: Ishaan.

Lifecycle fix: instead of inserting a new row every cycle (causing duplicates) or silently
skipping (causing stale content to linger), this compares the latest existing notification for
the same dedupe_key. If content is unchanged, nothing happens. If it changed (or is new),
the old one(s) for that dedupe_key are deleted and a fresh one is inserted.
"""
from __future__ import annotations

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import FAST_MODEL, call_text
from agents.state import GraphState, NodeResult


def _simulate_delivery_failure_flag(ctx: AgentContext) -> bool:
    row = ctx.db.table("demo_control_flags").select("simulate_delivery_failure").eq("id", 1).execute().data
    return bool(row and row[0]["simulate_delivery_failure"])


def _latest_notification(ctx: AgentContext, citizen_id: str, dedupe_key: str) -> dict | None:
    rows = (
        ctx.db.table("notifications").select("id, message, checklist")
        .eq("citizen_id", citizen_id).eq("dedupe_key", dedupe_key)
        .order("created_at", desc=True).limit(1).execute().data
    )
    return rows[0] if rows else None


def _replace_notification(ctx: AgentContext, citizen_id: str, ntype: str, dedupe_key: str,
                           message: str, document_type: str | None, checklist: list[str] | None) -> str:
    ctx.db.table("notifications").delete().eq("citizen_id", citizen_id).eq("dedupe_key", dedupe_key).execute()

    attempts = 0
    while attempts < 2:
        attempts += 1
        if _simulate_delivery_failure_flag(ctx) and attempts == 1:
            continue
        ctx.db.table("notifications").insert({
            "citizen_id": citizen_id, "type": ntype, "message": message, "dedupe_key": dedupe_key,
            "channel": "in_app", "delivery_status": "sent",
            "document_type": document_type, "checklist": checklist,
        }).execute()
        return "sent"
    ctx.db.table("notifications").insert({
        "citizen_id": citizen_id, "type": ntype, "message": message, "dedupe_key": dedupe_key,
        "channel": "in_app", "delivery_status": "escalated",
        "document_type": document_type, "checklist": checklist,
    }).execute()
    return "escalated"


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        events: list[tuple[str, str, str, str | None, list[str] | None]] = []

        for m in state.current_matches:
            if m.status == "matched":
                events.append((
                    "new_match", f"You may qualify for {m.scheme_name}. Confidence: {m.confidence:.0%}.",
                    f"match:{m.scheme_id}", None, None,
                ))
            elif m.status == "conflicting":
                events.append((
                    "conflict_detected", f"{m.scheme_name} conflicts with another scheme you matched — check the Conflict tab.",
                    f"conflict:{m.scheme_id}", None, None,
                ))

        for pd in state.pending_documents:
            events.append((
                "document_needed",
                f"You're missing or have an expired {pd.document_type.replace('_', ' ')}. {pd.reason}",
                f"doc:{pd.document_type}", pd.document_type, pd.checklist,
            ))

        for node_name, result in state.node_results.items():
            if result.status == "degraded":
                events.append((
                    "source_degraded", f"{node_name}: {result.reason}",
                    f"degraded:{node_name}", None, None,
                ))

        delivered = []
        unchanged = 0
        active_keys = {key for _, _, key, _, _ in events}

        for ntype, raw_message, dedupe_key, document_type, checklist in events:
            existing = _latest_notification(ctx, state.citizen_id, dedupe_key)

            message = call_text(
                system_prompt="Rewrite this as one short, warm, plain-language citizen "
                              "notification (2-3 full sentences, always finish your sentences). "
                              "Plain text only, no markdown, no asterisks. Never claim this is "
                              "an official determination — matches are always preliminary.",
                user_prompt=raw_message,
                model=FAST_MODEL,
                max_tokens=180,
            )

            if existing and existing["message"] == message and (existing.get("checklist") or []) == (checklist or []):
                unchanged += 1
                continue  # nothing changed — leave the existing notification as-is

            delivery_status = _replace_notification(ctx, state.citizen_id, ntype, dedupe_key, message, document_type, checklist)
            delivered.append({"type": ntype, "message": message, "delivery_status": delivery_status})

        # Clean up notifications for issues that are no longer current (e.g. a document that
        # got uploaded since the last run, or a match that's no longer active).
        all_existing = ctx.db.table("notifications").select("id, dedupe_key").eq("citizen_id", state.citizen_id).execute().data or []
        stale_ids = [r["id"] for r in all_existing if r["dedupe_key"] not in active_keys]
        if stale_ids:
            for sid in stale_ids:
                ctx.db.table("notifications").delete().eq("id", sid).execute()

        status = "escalated" if any(d["delivery_status"] == "escalated" for d in delivered) else "ok"
        reason = f"{len(delivered)} notification(s) added/updated, {unchanged} unchanged, {len(stale_ids)} cleared as resolved."
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="NotificationAgent",
            action="deliver_notifications", reasoning=reason, status=status,
        )
        state.node_results["NotificationAgent"] = NodeResult(status=status, reason=reason, output={"delivered": delivered})
    except Exception as exc:  # noqa: BLE001
        state.node_results["NotificationAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="NotificationAgent",
            action="deliver_notifications", reasoning=f"Exception: {exc}", status="failed",
        )
    return state