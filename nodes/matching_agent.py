"""
Matching Agent — Owner: Ishaan.

Responsibility (fixed): compares a citizen's CLEARED attributes (via ConsentGateway only,
already populated in state.cleared_attributes by the Consent Agent node) against each scheme's
criteria. Decides whether a scheme applies and at what confidence. On ambiguous/partial data,
must express uncertainty — never force a true/false.
"""
from __future__ import annotations

import json

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import REASONING_MODEL, call_json
from agents.state import GraphState, MatchWorkingRecord, NodeResult

SYSTEM_PROMPT = """\
You are the Matching Agent for SchemeSaarthi, a government-benefits assistant. You are given a
scheme's structured eligibility criteria and a citizen's CONSENTED attributes only. Decide
whether the scheme applies. If any criterion cannot be evaluated because the needed attribute
is missing from the consented set, you MUST NOT guess — list it in missing_data and do not
force a true/false applies value.

Respond with a JSON object exactly of this shape:
{"applies": true|false|null, "confidence": 0.0-1.0, "missing_data": ["attribute_key", ...],
 "reasoning": "one or two sentences"}
"""


def _fetch_schemes(ctx: AgentContext) -> list[dict]:
    return ctx.db.table("schemes").select("*").execute().data or []


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        schemes = _fetch_schemes(ctx)
        cleared = {k: v.attribute_value for k, v in state.cleared_attributes.items()}
        justifying_ids = [v.citizen_attribute_id for v in state.cleared_attributes.values()]

        results: list[MatchWorkingRecord] = []
        for scheme in schemes:
            user_prompt = json.dumps({
                "scheme_criteria": scheme["criteria"],
                "citizen_cleared_attributes": cleared,
            })
            try:
                llm_out = call_json(SYSTEM_PROMPT, user_prompt, model=REASONING_MODEL)
            except Exception as llm_exc:  # noqa: BLE001 — per-scheme failure shouldn't kill the whole node
                results.append(MatchWorkingRecord(
                    scheme_id=scheme["id"], scheme_name=scheme["name"],
                    applies=None, confidence=0.0, missing_data=["<llm_error>"],
                    reasoning=f"Matching call failed: {llm_exc}",
                    justifying_attribute_ids=justifying_ids,
                    status="uncertain",
                ))
                continue

            missing = llm_out.get("missing_data") or []
            applies = llm_out.get("applies")
            confidence = float(llm_out.get("confidence") or 0.0)
            reasoning = llm_out.get("reasoning", "")

            if missing:
                status = "uncertain"
            elif applies is True:
                status = "matched"
            elif applies is False:
                status = "rejected"
            else:
                status = "uncertain"

            record = MatchWorkingRecord(
                scheme_id=scheme["id"], scheme_name=scheme["name"],
                applies=applies, confidence=confidence, missing_data=missing,
                reasoning=reasoning, justifying_attribute_ids=justifying_ids,
                status=status,
                rejection_reason=reasoning if status == "rejected" else None,
            )
            results.append(record)

            # persist to match_records (upsert-by-citizen+scheme kept simple: always insert;
            # a fuller build would upsert on (citizen_id, scheme_id))
            ctx.db.table("match_records").insert({
                "citizen_id": state.citizen_id,
                "scheme_id": scheme["id"],
                "confidence": confidence,
                "justifying_attributes": justifying_ids,
                "status": status,
                "rejection_reason": record.rejection_reason,
            }).execute()

        state.current_matches = results
        overall_status = "uncertain" if any(r.status == "uncertain" for r in results) else "ok"
        reason = f"Evaluated {len(results)} schemes."
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="MatchingAgent",
            action="evaluate_schemes", reasoning=reason, status=overall_status,
            justifying_attribute_ids=justifying_ids,
        )
        state.node_results["MatchingAgent"] = NodeResult(
            status=overall_status, reason=reason,
            output={"matched": sum(1 for r in results if r.status == "matched")},
        )
    except Exception as exc:  # noqa: BLE001
        state.node_results["MatchingAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="MatchingAgent",
            action="evaluate_schemes", reasoning=f"Exception: {exc}", status="failed",
        )
    return state
