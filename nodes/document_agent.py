"""
Document Agent — Owner: Ishaan.

Responsibility (fixed): compares scheme.required_documents against citizen_documents_held
(deterministic — no LLM for the comparison itself). Decides which documents are missing or
newly required. LLM (8B) only turns the missing-doc list into a plain-language checklist.

Failure mode to implement: a document_rule change (surfaced by Discovery Agent as
state.new_rule_payload) can make an existing profile incomplete — re-run the comparison for
documents touched by that rule.
"""
from __future__ import annotations

from datetime import date

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import FAST_MODEL, call_text
from agents.state import GraphState, NodeResult, PendingDocument


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

        # Only look at documents relevant to schemes the citizen matched or is uncertain on —
        # avoids nagging about documents for schemes they're flatly ineligible for.
        relevant_scheme_ids = [
            m.scheme_id for m in state.current_matches if m.status in ("matched", "needs_document", "uncertain")
        ]
        schemes = (
            ctx.db.table("schemes").select("id, name, required_documents")
            .in_("id", relevant_scheme_ids).execute().data
            if relevant_scheme_ids else []
        )

        missing_doc_types: set[str] = set()
        for scheme in schemes:
            for doc_type in scheme["required_documents"]:
                doc_row = held.get(doc_type)
                if doc_row is None:
                    missing_doc_types.add(doc_type)
                elif _is_expired(doc_row):
                    missing_doc_types.add(doc_type)

        # If a new document rule just came in (from Discovery Agent), re-check anyone whose
        # profile touches that document type — for the demo, "anyone" = this citizen, since only
        # the demo citizen is shown live, but a fuller build would loop over all citizens here.
        if state.new_rule_payload:
            rule_doc_type = state.new_rule_payload.get("document_type")
            if rule_doc_type and rule_doc_type not in held:
                missing_doc_types.add(rule_doc_type)

        for doc_type in missing_doc_types:
            checklist_text = call_text(
                system_prompt="Write a short, numbered, plain-language checklist (2-4 steps) "
                              "for an Indian citizen to obtain a specific government document. "
                              "Name a plausible local office (e.g. Tehsildar, Gram Panchayat, "
                              "municipal office) where relevant.",
                user_prompt=f"Document needed: {doc_type}",
                model=FAST_MODEL,
                max_tokens=150,
            )
            pending.append(PendingDocument(
                document_type=doc_type,
                reason="Missing or expired, required by a matched/uncertain scheme.",
                checklist=[line.strip() for line in checklist_text.split("\n") if line.strip()],
            ))
            # reflect in match status: any match needing this doc moves to needs_document
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
    except Exception as exc:  # noqa: BLE001
        state.node_results["DocumentAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DocumentAgent",
            action="check_documents", reasoning=f"Exception: {exc}", status="failed",
        )
    return state
