"""
Discovery Agent — Owner: Ishaan.

Responsibility (fixed): watches scheme_source / document_rule_source for new/changed entries.
Decides what counts as "new" vs "already seen". Must survive a source going offline or
returning malformed data (one of the two required live-demo failure paths).

The actual fetch is deterministic code (DB reads), NOT an LLM call. The 70B model is used only
for the judgment call "is this materially new/changed" when the diff isn't a simple bool
(kept simple here: `seen` flag does that job deterministically for the hackathon scope, with
the LLM call reserved for producing a human-readable summary of what changed, which the
Notification Agent also uses).
"""
from __future__ import annotations

from agents.audit import write_audit
from agents.context import AgentContext
from agents.llm_client import FAST_MODEL, call_text
from agents.state import GraphState, NodeResult


def _check_source_offline(ctx: AgentContext) -> bool:
    row = ctx.db.table("demo_control_flags").select("source_offline").eq("id", 1).execute().data
    return bool(row and row[0]["source_offline"])


def _fetch_unseen(ctx: AgentContext, table: str) -> list[dict]:
    if _check_source_offline(ctx):
        raise ConnectionError(f"{table} is offline (demo_control_flags.source_offline=true)")
    result = ctx.db.table(table).select("*").eq("seen", False).execute()
    return result.data or []


def _use_cached_snapshot(ctx: AgentContext, table: str) -> list[dict]:
    result = (
        ctx.db.table("cached_snapshot")
        .select("snapshot")
        .eq("source_table", table)
        .order("captured_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["snapshot"] if rows else []


def run(state: GraphState, ctx: AgentContext) -> GraphState:
    try:
        new_schemes = _fetch_unseen(ctx, "scheme_source")
        new_rules = _fetch_unseen(ctx, "document_rule_source")

        # snapshot what we successfully fetched, so a future offline event has something to
        # fall back to
        if new_schemes:
            ctx.db.table("cached_snapshot").insert({
                "source_table": "scheme_source", "snapshot": new_schemes,
            }).execute()
        if new_rules:
            ctx.db.table("cached_snapshot").insert({
                "source_table": "document_rule_source", "snapshot": new_rules,
            }).execute()

        if new_schemes:
            state.new_scheme_payload = new_schemes[0]["payload"]
            ctx.db.table("scheme_source").update({"seen": True}).eq("id", new_schemes[0]["id"]).execute()
        if new_rules:
            state.new_rule_payload = new_rules[0]["payload"]
            ctx.db.table("document_rule_source").update({"seen": True}).eq("id", new_rules[0]["id"]).execute()

        if new_schemes or new_rules:
            summary = call_text(
                system_prompt="Summarize a scheme/document-rule feed change in one short "
                              "sentence for a citizen-facing notification feed.",
                user_prompt=f"New scheme payloads: {new_schemes}\nNew rule payloads: {new_rules}",
                model=FAST_MODEL,
                max_tokens=80,
            )
        else:
            summary = "No new or changed entries since last check."

        status = "ok"
        reason = summary
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DiscoveryAgent",
            action="poll_sources", reasoning=reason, status=status,
        )
        state.node_results["DiscoveryAgent"] = NodeResult(
            status=status, reason=reason,
            output={"new_scheme_count": len(new_schemes), "new_rule_count": len(new_rules)},
        )

    except ConnectionError as exc:
        # THE deliberate source-offline failure path — fall back to cached snapshot.
        cached_schemes = _use_cached_snapshot(ctx, "scheme_source")
        cached_rules = _use_cached_snapshot(ctx, "document_rule_source")
        had_cache = bool(cached_schemes or cached_rules)
        status = "degraded" if had_cache else "failed"
        reason = (
            f"Source unreachable ({exc}); fell back to cached snapshot."
            if had_cache else f"Source unreachable ({exc}); no cached snapshot available."
        )
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DiscoveryAgent",
            action="poll_sources", reasoning=reason, status=status,
        )
        state.node_results["DiscoveryAgent"] = NodeResult(
            status=status, reason=reason,
            output={"used_cache": had_cache},
        )
    except Exception as exc:  # noqa: BLE001
        state.node_results["DiscoveryAgent"] = NodeResult(status="failed", reason=str(exc))
        write_audit(
            ctx.db, citizen_id=state.citizen_id, agent_name="DiscoveryAgent",
            action="poll_sources", reasoning=f"Exception: {exc}", status="failed",
        )
    return state
