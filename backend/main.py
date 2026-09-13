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
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
import uuid as uuid_lib
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import Client, create_client
from agents.document_requirements import refresh_if_stale
from datagovin.client import DataGovInClient

load_dotenv(".env.local")

from agents.consent_gateway import ConsentGateway
from agents.context import AgentContext
from agents.nodes.conflict_agent import explain_non_match
from agents.orchestrator import run_graph_for_citizen
from backend.auth import get_current_user_id
from fastapi import Depends
from backend.sse import event_stream, publish_event
import asyncio

app = FastAPI(title="SchemeSaarthi API")

POLL_INTERVAL_SECONDS = 60  # demo-fast interval; real deployment would use something like 3600

async def _continuous_discovery_loop():
    while True:
        await asyncio.sleep(POLL_INTERVAL_SECONDS)
        try:
            db = get_db()
            citizens = db.table("citizens").select("id").execute().data or []
            for c in citizens:
                final_state = await asyncio.to_thread(run_graph_for_citizen, c["id"], "scheduled_check")
                for name, result in final_state.node_results.items():
                    publish_event({
                        "type": "node_result", "agent": name, "status": result.status,
                        "reason": result.reason, "citizen_id": c["id"], "scheduled": True,
                    })
                publish_event({"type": "graph_finished", "citizen_id": c["id"], "scheduled": True})
        except Exception as exc:
            publish_event({"type": "scheduler_error", "error": str(exc)})




DOC_REFRESH_CHECK_INTERVAL_SECONDS = 120  # demo-fast; real deployment checks less often

async def _document_requirements_loop():
    while True:
        await asyncio.sleep(DOC_REFRESH_CHECK_INTERVAL_SECONDS)
        try:
            db = get_db()
            citizens = db.table("citizens").select("id").execute().data or []
            for c in citizens:
                ran = await asyncio.to_thread(refresh_if_stale, db, c["id"])
                if ran:
                    publish_event({"type": "required_docs_refreshed", "citizen_id": c["id"]})
        except Exception as exc:
            publish_event({"type": "scheduler_error", "error": str(exc)})



@app.on_event("startup")
async def start_background_scheduler():
    asyncio.create_task(_continuous_discovery_loop())
    asyncio.create_task(_document_requirements_loop())


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
    rows = db.table("match_records").select("*, schemes(name, description, required_documents)").eq("citizen_id", citizen_id).execute().data
    held = db.table("citizen_documents_held").select("document_type, status").eq("citizen_id", citizen_id).execute().data or []
    held_map = {h["document_type"]: h["status"] for h in held}
    for r in rows:
        docs = (r.get("schemes") or {}).get("required_documents") or []
        r["document_status"] = [
            {"document_type": d, "held": held_map.get(d) not in (None, "expired")}
            for d in docs
        ]
    return rows


DOCUMENT_BUCKET = "citizen-documents"

@app.get("/api/citizen/{citizen_id}/documents")
def get_documents(citizen_id: str):
    db = get_db()
    held = db.table("citizen_documents_held").select("*").eq("citizen_id", citizen_id).execute().data
    for d in held:
        if d.get("storage_path"):
            d["url"] = db.storage.from_(DOCUMENT_BUCKET).get_public_url(d["storage_path"])
    return {"held": held}


@app.post("/api/citizen/{citizen_id}/documents/upload")
async def upload_document(citizen_id: str, document_type: str = Form(...), file: UploadFile = File(...)):
    db = get_db()
    contents = await file.read()
    ext = file.filename.rsplit(".", 1)[-1] if "." in file.filename else "bin"
    storage_path = f"{citizen_id}/{document_type}_{uuid_lib.uuid4().hex}.{ext}"

    db.storage.from_(DOCUMENT_BUCKET).upload(
        storage_path, contents, {"content-type": file.content_type or "application/octet-stream"}
    )

    # replace any existing row for this document type (simple "latest wins" approach)
    db.table("citizen_documents_held").delete().eq("citizen_id", citizen_id).eq("document_type", document_type).execute()
    db.table("citizen_documents_held").insert({
        "citizen_id": citizen_id, "document_type": document_type,
        "status": "held", "storage_path": storage_path,
    }).execute()

    return {"uploaded": True, "storage_path": storage_path}



@app.get("/api/citizen/{citizen_id}/required-documents")
def get_required_documents(citizen_id: str):
    db = get_db()
    return db.table("citizen_required_documents").select("*").eq("citizen_id", citizen_id).execute().data


@app.post("/api/citizen/{citizen_id}/refresh-required-documents")
def refresh_required_documents(citizen_id: str):
    db = get_db()
    ran = refresh_if_stale(db, citizen_id, force=True)
    return {"refreshed": ran}


@app.get("/api/citizen/{citizen_id}/missing-documents")
def missing_documents(citizen_id: str):
    db = get_db()
    from datetime import date
    required = db.table("citizen_required_documents").select("document_type, why_required, checklist").eq("citizen_id", citizen_id).execute().data or []
    held_rows = db.table("citizen_documents_held").select("document_type, status, expiry_date").eq("citizen_id", citizen_id).execute().data or []
    held = {r["document_type"]: r for r in held_rows}

    def is_expired(row):
        if row.get("status") == "expired":
            return True
        exp = row.get("expiry_date")
        return bool(exp and str(exp) < str(date.today()))

    missing = []
    for r in required:
        row = held.get(r["document_type"])
        if row is None or is_expired(row):
            missing.append(r)
    return missing


@app.get("/api/demographics/agricultural-income")
def agricultural_income(state: str):
    client = DataGovInClient()
    result = client.get_average_agricultural_income(state)
    if result is None:
        raise HTTPException(404, "No data for this state, or data.gov.in key not configured.")
    return result


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
    """Uses a real LLM call to match the citizen's free-text query against the scheme
    catalog — not a SQL string match. Handles vague queries like 'farmer scheme' or
    'pension for elderly', not just exact name substrings."""
    import json
    from agents.llm_client import call_json, REASONING_MODEL

    db = get_db()
    ctx = get_ctx()
    all_schemes = db.table("schemes").select("id, name, description").execute().data or []

    prompt = f"""A citizen searched for: "{scheme_name_query}"

Here is the full catalog of schemes currently available in our system:
{json.dumps(all_schemes)}

Decide which ONE scheme (if any) the citizen most likely means, even if their search is vague
or uses different words than the scheme name (e.g. "farmer scheme" could mean a scheme about
agricultural laborers). If nothing in this catalog is a reasonable match, say so honestly.

Respond with ONLY JSON:
{{"matched_scheme_id": "<the scheme id, or null if nothing matches>",
  "no_match_message": "<only if matched_scheme_id is null — one short, honest sentence noting
  this isn't in our current catalog, and suggesting they check myScheme.gov.in for the full
  government scheme list>"}}
"""
    result = call_json(
        "You match a citizen's search query to the closest scheme in a small catalog, or "
        "honestly say none match rather than forcing a bad match.",
        prompt,
        model=REASONING_MODEL,
    )

    matched_id = result.get("matched_scheme_id")
    if not matched_id:
        return {
            "scheme": None,
            "matched": False,
            "no_match_message": result.get(
                "no_match_message",
                "No scheme in our current catalog matches that — try myScheme.gov.in for the full list.",
            ),
        }

    scheme_rows = db.table("schemes").select("*").eq("id", matched_id).execute().data
    if not scheme_rows:
        return {"scheme": None, "matched": False, "no_match_message": "Matched scheme no longer exists."}
    scheme = scheme_rows[0]

    existing_match = (
        db.table("match_records").select("status")
        .eq("citizen_id", citizen_id).eq("scheme_id", scheme["id"])
        .order("created_at", desc=True).limit(1).execute().data
    )
    if existing_match and existing_match[0]["status"] in ("matched", "needs_document"):
        return {"scheme": scheme["name"], "matched": True}

    cleared = ctx.consent.get_all_for_purpose(citizen_id, "General eligibility screening")
    cleared_values = {k: v.attribute_value for k, v in cleared.items()}
    from agents.nodes.conflict_agent import explain_non_match
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


class RegisterCitizenRequest(BaseModel):
    display_name: str
    attributes: dict




@app.post("/api/auth/register-citizen")
def register_citizen(req: RegisterCitizenRequest, user_id: str = Depends(get_current_user_id)):
    db = get_db()
    existing = db.table("citizens").select("id").eq("auth_user_id", user_id).execute().data
    if existing:
        return {"citizen_id": existing[0]["id"], "already_existed": True}

    citizen = db.table("citizens").insert(
        {"display_name": req.display_name, "auth_user_id": user_id}
    ).execute().data[0]
    citizen_id = citizen["id"]

    purposes = {
        "age": "General eligibility screening",
        "income": "Income-based scheme eligibility (annual, INR)",
        "category": "SC/ST/OBC scholarship & reservation-based eligibility",
        "state": "State-specific scheme eligibility",
        "gender": "Gender-specific scheme eligibility",
        "occupation": "Occupation-based scheme eligibility",
        "disability_status": "Disability-benefit eligibility",
    }
    for key, value in req.attributes.items():
        if value:
            db.table("citizen_attributes").insert({
                "citizen_id": citizen_id, "attribute_key": key, "attribute_value": str(value),
                "consent_purpose": purposes.get(key, "General eligibility screening"),
                "consent_granted": True,
            }).execute()

    try:
        run_graph_for_citizen(citizen_id, "manual_demo_trigger")
    except Exception:
        pass
    try:
        refresh_if_stale(db, citizen_id, force=True)
    except Exception:
        pass

    return {"citizen_id": citizen_id, "already_existed": False}





@app.get("/api/auth/my-citizen-id")
def my_citizen_id(user_id: str = Depends(get_current_user_id)):
    db = get_db()
    rows = db.table("citizens").select("id").eq("auth_user_id", user_id).execute().data
    if not rows:
        raise HTTPException(404, "No citizen profile yet")
    return {"citizen_id": rows[0]["id"]}


class UpdateAttributeRequest(BaseModel):
    attribute_value: str

@app.patch("/api/attributes/{attribute_id}")
def update_attribute_value(attribute_id: str, req: UpdateAttributeRequest):
    db = get_db()
    db.table("citizen_attributes").update({"attribute_value": req.attribute_value}).eq("id", attribute_id).execute()
    return {"updated": True}



@app.get("/health")
def health():
    return {"status": "ok"}
