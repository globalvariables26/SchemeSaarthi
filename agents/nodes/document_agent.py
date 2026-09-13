"""
Document Agent — Owner: Ishaan.

Compares scheme.required_documents against citizen_documents_held, AND separately checks a
fixed baseline of ID documents (Aadhaar, PAN) that every adult citizen needs regardless of
which scheme they matched.
"""
from __future__ import annotations

from datetime import date

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import FAST_MODEL, call_text
from agents.state import GraphState, NodeResult, PendingDocument

BASELINE_KYC_DOCS = {
    "pan_card": 18,
    "aadhaar_card": 0,
}


def _held_documents(ctx: AgentContext, citizen_id: str) -> dict[str, dict]:
    rows = ctx.db.table("citizen_documents_held").select("*").eq("citizen_id", citizen_id).execute().data or []
    return {r["document_type"]: r for r in rows}


def _is_expired(doc_row: dict) -> bool:
    if doc_row.get("status") == "expired":
        return True
    expiry = doc_row.get("expiry_date")
    if expiry and str(expiry) < str(date.today()):
        return True
    return False


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        held = _held_documents(ctx, state.citizen_id)
        pending: list[PendingDocument] = []
        missing_doc_types: set[str] = set()

        relevant_scheme_ids = [
            m.scheme_id for m in state.current_matches if m.status in ("matched", "needs_document", "uncertain")
        ]
        schemes = (
            ctx.db.table("schemes").select("id, name, required_documents")
            .in_("id", relevant_scheme_ids).execute().data
            if relevant_scheme_ids else []
        )
        for scheme in schemes:
            for doc_type in scheme["required_documents"]:
                doc_row = held.get(doc_type)
                if doc_row is None or _is_expired(doc_row):
                    missing_doc_types.add(doc_type)

        age_attr = state.cleared_attributes.get("age")
        age_val = None
        if age_attr:
            try:
                age_val = int(age_attr.attribute_value)
            except ValueError:
                age_val = None

        for doc_type, min_age in BASELINE_KYC_DOCS.items():
            if age_val is not None and age_val >= min_age and doc_type not in held:
                missing_doc_types.add(doc_type)

        if state.new_rule_payload:
            rule_doc_type = state.new_rule_payload.get("document_type")
            if rule_doc_type and rule_doc_type not in held:
                missing_doc_types.add(rule_doc_type)

        for doc_type in missing_doc_types:
            checklist_text = call_text(
                system_prompt="Write a numbered plain-language checklist of exactly 4 short steps "
                              "for an Indian citizen to obtain a specific government document. "
                              "Plain text only - no markdown, no asterisks, no bold. Name a plausible "
                              "local office (e.g. Tehsildar, Gram Panchayat, UIDAI center, "
                              "NSDL/UTIITSL center) where relevant. Keep each step under 15 words.",
                user_prompt=f"Document needed: {doc_type}",
                model=FAST_MODEL,
                max_tokens=250,
            )
            pending.append(PendingDocument(
                document_type=doc_type,
                reason="Missing or expired.",
                checklist=[line.strip() for line in checklist_text.split("\n") if line.strip()],
            ))
            for m in state.current_matches:
                if m.status == "matched":
                    m.status = "needs_document"

        state.pending_documents = pending
        status = "ok"
        reason = f"{len(pending)} document(s) flagged as missing/expired." if pending else "All required documents on file."
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DocumentAgent",
            action="check_documents", reasoning=reason, status=status,
        )
        state.node_results["DocumentAgent"] = NodeResult(
            status=status, reason=reason, output={"missing_count": len(pending)},
        )
    except Exception as exc:
        state.node_results["DocumentAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DocumentAgent",
            action="check_documents", reasoning=f"Exception: {exc}", status="failed",
        )
    return state