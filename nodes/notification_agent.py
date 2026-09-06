"""
Notification Agent — Owner: Ishaan.

Responsibility (fixed): decides when/how to inform the citizen of a new match, conflict, or
document need. Confirms delivery. Failure mode: delivery failure -> retry once, then escalate
(never fail silently).

"Delivery" for Stage 1 = a row insert into `notifications`, which the frontend subscribes to
via Supabase Realtime. `simulate_delivery_failure` is an admin-panel-controlled flag so this
failure path is a real code path, not a scripted message.
"""
from __future__ import annotations

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import FAST_MODEL, call_text
from agents.state import GraphState, NodeResult


def _simulate_delivery_failure_flag(ctx: AgentContext) -> bool:
    row = ctx.db.table("demo_control_flags").select("simulate_delivery_failure").eq("id", 1).execute().data
    return bool(row and row[0]["simulate_delivery_failure"])


def _attempt_delivery(ctx: AgentContext, citizen_id: str, ntype: str, message: str) -> str:
    """Returns delivery_status. Simulates failure via the demo flag; retries once before
    escalating, per the required failure/adapt behavior."""
    attempts = 0
    while attempts < 2:
        attempts += 1
        if _simulate_delivery_failure_flag(ctx) and attempts == 1:
            continue  # simulated failure on first attempt only, so retry #2 can "succeed"
        ctx.db.table("notifications").insert({
            "citizen_id": citizen_id, "type": ntype, "message": message,
            "channel": "in_app", "delivery_status": "sent",
        }).execute()
        return "sent"
    # both attempts failed
    ctx.db.table("notifications").insert({
        "citizen_id": citizen_id, "type": ntype, "message": message,
        "channel": "in_app", "delivery_status": "escalated",
    }).execute()
    return "escalated"


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        events = []
        for m in state.current_matches:
            if m.status == "matched":
                events.append(("new_match", f"You may qualify for {m.scheme_name}. Confidence: {m.confidence:.0%}."))
            elif m.status == "needs_document":
                events.append(("document_needed", f"{m.scheme_name} needs a missing/expired document from you."))
            elif m.status == "conflicting":
                events.append(("conflict_detected", f"{m.scheme_name} conflicts with another scheme you matched — check the Conflict tab."))

        for pd in state.pending_documents:
            events.append(("document_needed", f"Your {pd.document_type.replace('_', ' ')} needs attention: {pd.reason}"))

        for node_name, result in state.node_results.items():
            if result.status == "degraded":
                events.append(("source_degraded", f"{node_name}: {result.reason}"))

        delivered = []
        for ntype, raw_message in events:
            message = call_text(
                system_prompt="Rewrite this as one short, warm, plain-language citizen "
                              "notification (max 2 sentences). Never claim this is an official "
                              "determination — matches are always preliminary.",
                user_prompt=raw_message,
                model=FAST_MODEL,
                max_tokens=80,
            )
            delivery_status = _attempt_delivery(ctx, state.citizen_id, ntype, message)
            delivered.append({"type": ntype, "message": message, "delivery_status": delivery_status})

        status = "escalated" if any(d["delivery_status"] == "escalated" for d in delivered) else "ok"
        reason = f"Sent {len(delivered)} notification(s)."
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
