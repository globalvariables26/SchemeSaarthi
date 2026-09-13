"""
Conflict & Explainability Agent — Owner: Ishaan.

Responsibility (fixed): evaluates the current match set for contradictions (mutual exclusivity,
state-vs-central document-type rule mismatches) and generates why/why-not explanations for the
Why-Not-Matched Explorer surface.

Failure mode to implement: central vs state rule mismatch for the same document type — this is
seeded test data (db/seed.py), not something requiring real conflicting data.
"""
from __future__ import annotations

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import REASONING_MODEL, call_json
from agents.state import GraphState, NodeResult

SYSTEM_PROMPT = """\
You are the Conflict & Explainability Agent for SchemeSaarthi. Given two mutually-exclusive
matched schemes for the same citizen, recommend which is the better option and explain why in
plain language, considering benefit value implied by the scheme descriptions.

Respond with JSON exactly: {"recommended_scheme_id": "...", "explanation": "..."}
"""


def _check_mutual_exclusivity(ctx: AgentContext, state: GraphState) -> list[dict]:
    matched_ids = {m.scheme_id for m in state.current_matches if m.status in ("matched", "needs_document")}
    if len(matched_ids) < 2:
        return []
    schemes = ctx.db.table("schemes").select("id, name, description, mutually_exclusive_with").in_(
        "id", list(matched_ids)
    ).execute().data or []
    by_id = {s["id"]: s for s in schemes}
    conflicts = []
    seen_pairs = set()
    for s in schemes:
        for other_id in (s.get("mutually_exclusive_with") or []):
            if other_id in matched_ids:
                pair = tuple(sorted([s["id"], other_id]))
                if pair in seen_pairs:
                    continue
                seen_pairs.add(pair)
                conflicts.append({"scheme_a": s, "scheme_b": by_id.get(other_id, {"id": other_id})})
    return conflicts


def _check_document_authority_mismatch(ctx: AgentContext, state: GraphState) -> list[dict]:
    matched_ids = {m.scheme_id for m in state.current_matches if m.status in ("matched", "needs_document")}
    if not matched_ids:
        return []
    rules = ctx.db.table("document_rules").select("*").execute().data or []
    by_doc_type: dict[str, list[dict]] = {}
    for r in rules:
        applies_to = (r.get("required_for") or {}).get("scheme_ids", [])
        if any(sid in matched_ids for sid in applies_to):
            by_doc_type.setdefault(r["document_type"], []).append(r)
    mismatches = []
    for doc_type, rule_list in by_doc_type.items():
        authorities = {r["issuing_authority"] for r in rule_list}
        if len(authorities) > 1:
            mismatches.append({"document_type": doc_type, "rules": rule_list})
    return mismatches


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        conflicts = _check_mutual_exclusivity(ctx, state)
        mismatches = _check_document_authority_mismatch(ctx, state)

        explanations = []
        for c in conflicts:
            try:
                llm_out = call_json(
                    SYSTEM_PROMPT,
                    f"Scheme A: {c['scheme_a']}\nScheme B: {c['scheme_b']}",
                    model=REASONING_MODEL,
                )
                explanations.append({**c, "recommendation": llm_out})
            except Exception as llm_exc:  # noqa: BLE001
                explanations.append({**c, "recommendation": {"explanation": f"LLM error: {llm_exc}"}})

            for m in state.current_matches:
                if m.scheme_id in (c["scheme_a"]["id"], c["scheme_b"]["id"]):
                    m.status = "conflicting"
                    ctx.db.table("match_records").update({"status": "conflicting"}).eq(
                        "citizen_id", state.citizen_id
                    ).eq("scheme_id", m.scheme_id).execute()

        status = "ok"
        if conflicts or mismatches:
            reason = f"{len(conflicts)} mutually-exclusive conflict(s), {len(mismatches)} document-authority mismatch(es) found."
        else:
            reason = "No conflicts or authority mismatches detected in current match set."

        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="ConflictExplainabilityAgent",
            action="evaluate_conflicts", reasoning=reason, status=status,
        )
        state.node_results["ConflictExplainabilityAgent"] = NodeResult(
            status=status, reason=reason,
            output={"conflicts": explanations, "document_mismatches": mismatches},
        )
    except Exception as exc:  # noqa: BLE001
        state.node_results["ConflictExplainabilityAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="ConflictExplainabilityAgent",
            action="evaluate_conflicts", reasoning=f"Exception: {exc}", status="failed",
        )
    return state


def explain_non_match(ctx: AgentContext, scheme: dict, cleared_attributes: dict[str, str]) -> dict:
    """Used by the Why-Not-Matched Explorer endpoint (backend/main.py) for a scheme the citizen
    searched for that they don't currently qualify for."""
    prompt = f"""\
Given this scheme's criteria: {scheme['criteria']}
And the citizen's consented attributes: {cleared_attributes}
Name the SPECIFIC disqualifying criterion and state whether it is "fixable" (e.g. an expired
certificate they can renew) or "fixed" (e.g. an age cutoff they cannot change).
Respond as JSON: {{"disqualifying_criterion": "...", "fixable": true|false, "explanation": "..."}}
"""
    return call_json(
        "You are the Conflict & Explainability Agent, generating a why-not-matched explanation.",
        prompt,
        model=REASONING_MODEL,
    )
