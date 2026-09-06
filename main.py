"""
FastAPI backend — Owner: Hunar.

Run locally: uvicorn backend.main:app --reload --port 8000
Depends on agents/ (Ishaan) and db/ (Jaya) already being set up — see README run order.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client

load_dotenv(".env.local")

from agents.consent_gateway import ConsentGateway
from agents.context import AgentContext
from agents.nodes.conflict_agent import explain_non_match
from agents.orchestrator import run_graph_for_citizen
from backend.sse import event_stream, publish_event

app = FastAPI(title="SchemeSaarthi API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.environ.get("CORS_ALLOWED_ORIGIN", "http://localhost:3000")],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db() -> Client:
    return create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])


def get_ctx() -> AgentContext:
    db = get_db()
    return AgentContext(db=db, consent=ConsentGateway(db))


# ---------------------------------------------------------------------------
# Graph run + SSE
# ---------------------------------------------------------------------------

class GraphRunRequest(BaseModel):
    citizen_id: str
    trigger: str = "manual_demo_trigger"


@app.post("/api/graph/run")
def run_graph(req: GraphRunRequest):
    publish_event({"type": "graph_started", "citizen_id": req.citizen_id, "trigger": req.trigger,
                    "timestamp": datetime.now(timezone.utc).isoformat()})
    try:
        final_state = run_graph_for_citizen(req.citizen_id, req.trigger)
    except Exception as exc:  # noqa: BLE001
        publish_event({"type": "graph_error", "error": str(exc)})
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    for name, result in final_state.node_results.items():
        publish_event({"type": "node_result", "agent": name, "status": result.status, "reason": result.reason})
    for ev in final_state.replan_events:
        publish_event({"type": "plan_change", "from": ev.from_node, "to": ev.to_node, "reason": ev.reason})
    publish_event({"type": "graph_finished", "citizen_id": req.citizen_id})

    return {
        "node_results": {k: v.model_dump() for k, v in final_state.node_results.items()},
        "replan_events": [e.model_dump() for e in final_state.replan_events],
        "current_matches": [m.model_dump() for m in final_state.current_matches],
        "pending_documents": [d.model_dump() for d in final_state.pending_documents],
    }


@app.get("/api/graph-events")
async def graph_events():
    """SSE endpoint the admin panel subscribes to for the live node-transition visualization
    (Section 2.3 of the orchestration doc). This is what makes re-planning VISIBLE, not just
    logged."""
    return await event_stream()


# ---------------------------------------------------------------------------
# Admin / demo control panel actions
# ---------------------------------------------------------------------------

class InjectSchemeRequest(BaseModel):
    payload: dict
    citizen_id: str


@app.post("/api/admin/inject-scheme")
def inject_scheme(req: InjectSchemeRequest):
    db = get_db()
    db.table("scheme_source").insert({"payload": req.payload, "seen": False}).execute()
    publish_event({"type": "admin_action", "action": "inject_scheme", "payload": req.payload})
    # trigger the poll on-demand (don't wait for a timer, per Section 10)
    final_state = run_graph_for_citizen(req.citizen_id, "new_scheme")
    return {"triggered": True, "node_results": {k: v.model_dump() for k, v in final_state.node_results.items()}}


class InjectRuleChangeRequest(BaseModel):
    payload: dict
    citizen_id: str


@app.post("/api/admin/inject-rule-change")
def inject_rule_change(req: InjectRuleChangeRequest):
    db = get_db()
    db.table("document_rule_source").insert({"payload": req.payload, "seen": False}).execute()
    publish_event({"type": "admin_action", "action": "inject_rule_change", "payload": req.payload})
    final_state = run_graph_for_citizen(req.citizen_id, "rule_change")
    return {"triggered": True, "node_results": {k: v.model_dump() for k, v in final_state.node_results.items()}}


class ToggleSourceOfflineRequest(BaseModel):
    offline: bool


@app.post("/api/admin/toggle-source-offline")
def toggle_source_offline(req: ToggleSourceOfflineRequest):
    db = get_db()
    db.table("demo_control_flags").update({"source_offline": req.offline}).eq("id", 1).execute()
    publish_event({"type": "admin_action", "action": "toggle_source_offline", "offline": req.offline})
    return {"source_offline": req.offline}


class ToggleDeliveryFailureRequest(BaseModel):
    simulate_failure: bool


@app.post("/api/admin/toggle-delivery-failure")
def toggle_delivery_failure(req: ToggleDeliveryFailureRequest):
    db = get_db()
    db.table("demo_control_flags").update({"simulate_delivery_failure": req.simulate_failure}).eq("id", 1).execute()
    return {"simulate_delivery_failure": req.simulate_failure}


# ---------------------------------------------------------------------------
# Citizen-facing dashboard endpoints
# ---------------------------------------------------------------------------

@app.get("/api/citizen/{citizen_id}/matches")
def get_matches(citizen_id: str):
    db = get_db()
    rows = db.table("match_records").select("*, schemes(name, description)").eq("citizen_id", citizen_id).execute().data
    return rows


@app.get("/api/citizen/{citizen_id}/documents")
def get_documents(citizen_id: str):
    db = get_db()
    held = db.table("citizen_documents_held").select("*").eq("citizen_id", citizen_id).execute().data
    return {"held": held}


@app.get("/api/citizen/{citizen_id}/notifications")
def get_notifications(citizen_id: str):
    db = get_db()
    rows = db.table("notifications").select("*").eq("citizen_id", citizen_id).order("created_at", desc=True).execute().data
    return rows


@app.get("/api/citizen/{citizen_id}/audit-log")
def get_audit_log(citizen_id: str):
    db = get_db()
    rows = db.table("audit_log").select("*").eq("citizen_id", citizen_id).order("created_at", desc=True).execute().data
    return rows


@app.get("/api/citizen/{citizen_id}/explore")
def explore_scheme(citizen_id: str, scheme_name_query: str):
    """Why-Not-Matched Explorer: search a scheme by (partial) name; if the citizen doesn't
    currently match it, explain why."""
    db = get_db()
    ctx = get_ctx()
    schemes = db.table("schemes").select("*").ilike("name", f"%{scheme_name_query}%").execute().data
    if not schemes:
        raise HTTPException(status_code=404, detail="No matching scheme found.")
    scheme = schemes[0]

    existing_match = (
        db.table("match_records").select("status")
        .eq("citizen_id", citizen_id).eq("scheme_id", scheme["id"])
        .order("created_at", desc=True).limit(1).execute().data
    )
    if existing_match and existing_match[0]["status"] == "matched":
        return {"scheme": scheme["name"], "matched": True}

    cleared = ctx.consent.get_all_for_purpose(citizen_id, "General eligibility screening")
    cleared_values = {k: v.attribute_value for k, v in cleared.items()}
    explanation = explain_non_match(ctx, scheme, cleared_values)
    return {"scheme": scheme["name"], "matched": False, **explanation}


# ---------------------------------------------------------------------------
# Consent endpoints
# ---------------------------------------------------------------------------

@app.post("/api/consent/{attribute_id}/revoke")
def revoke_consent(attribute_id: str):
    ctx = get_ctx()
    ctx.consent.revoke(attribute_id)
    publish_event({"type": "consent_revoked", "attribute_id": attribute_id})
    return {"revoked": True}


@app.get("/api/citizen/{citizen_id}/attributes")
def get_attributes(citizen_id: str):
    """For the onboarding/consent-center UI — lists attributes and their consent state.
    NOTE: this reads citizen_attributes directly for display purposes (showing a citizen their
    OWN consent toggles is not the same threat model as an agent reading data cross-purpose) —
    still goes through the service-role client, gated by the fact this is the citizen's own id.
    """
    db = get_db()
    rows = db.table("citizen_attributes").select("*").eq("citizen_id", citizen_id).execute().data
    return rows


@app.get("/health")
def health():
    return {"status": "ok"}
