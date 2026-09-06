"""
Orchestrator / Planner — Owner: Ishaan.

Per the orchestration doc's Section 2.2: the Orchestrator is NOT a node that "does work" — it
is the graph's routing logic itself (conditional edges + a lightweight planning node that picks
the next node from current state and failure flags). This is what makes "sequence agents,
re-plan on failure" a structurally enforced property instead of something only described in a
docstring.

Build order note (Section 11): get this skeleton running end-to-end with STUB nodes first,
confirm the graph executes, THEN swap in the real node bodies (which already exist in
agents/nodes/*.py) — swapping is just changing the imports below, nothing else changes.
"""
from __future__ import annotations

from datetime import datetime, timezone
from functools import partial
from typing import Literal

from langgraph.graph import END, StateGraph

from agents.context import AgentContext, build_context
from agents.nodes import (
    conflict_agent,
    consent_agent,
    discovery_agent,
    document_agent,
    matching_agent,
    notification_agent,
)
from agents.state import GraphState, ReplanEvent

NODE_ORDER = [
    "ConsentProfileAgent",
    "DiscoveryAgent",
    "MatchingAgent",
    "DocumentAgent",
    "ConflictExplainabilityAgent",
    "NotificationAgent",
]


def _record_replan(state: GraphState, from_node: str, to_node: str, reason: str) -> None:
    """The ONLY place replan_events gets written, per Section 5's spec that this field is
    Orchestrator-only. Also mirrors into audit_log implicitly via the node's own write_audit
    calls — this list is specifically for the SSE-driven live 'plan changed' visualization
    (Section 2.3), so keep it lightweight."""
    state.replan_events.append(ReplanEvent(from_node=from_node, to_node=to_node, reason=reason))


def _wrap(node_fn, agent_name: str, ctx: AgentContext):
    """Wraps a node function so that even if the node itself somehow raises (it shouldn't —
    every node already has its own try/except per Section 3.7), the graph doesn't crash.
    Belt-and-braces for the 'must not silently stop' requirement."""
    def _inner(state: GraphState) -> GraphState:
        try:
            return node_fn(state, ctx)
        except Exception as exc:  # noqa: BLE001
            from agents.state import NodeResult
            state.node_results[agent_name] = NodeResult(status="failed", reason=f"Uncaught: {exc}")
            return state
    return _inner


def _route_after_discovery(state: GraphState) -> Literal["matching", "notify_and_end"]:
    result = state.node_results.get("DiscoveryAgent")
    if result and result.status == "failed":
        # No cache available either — nothing to match against; skip straight to notifying
        # the citizen that discovery failed, per "must not silently stop".
        _record_replan(state, "MatchingAgent", "NotificationAgent",
                        reason=f"DiscoveryAgent failed with no fallback: {result.reason}")
        return "notify_and_end"
    if result and result.status == "degraded":
        _record_replan(state, "MatchingAgent", "MatchingAgent",
                        reason=f"DiscoveryAgent degraded (using cached snapshot): {result.reason} — continuing plan.")
    return "matching"


def _route_after_matching(state: GraphState) -> Literal["document", "notify_and_end"]:
    result = state.node_results.get("MatchingAgent")
    if result and result.status == "failed":
        _record_replan(state, "DocumentAgent", "NotificationAgent",
                        reason=f"MatchingAgent failed: {result.reason}")
        return "notify_and_end"
    return "document"


def build_graph(ctx: AgentContext | None = None):
    ctx = ctx or build_context()
    graph = StateGraph(GraphState)

    graph.add_node("consent", _wrap(consent_agent.run, "ConsentProfileAgent", ctx))
    graph.add_node("discovery", _wrap(discovery_agent.run, "DiscoveryAgent", ctx))
    graph.add_node("matching", _wrap(matching_agent.run, "MatchingAgent", ctx))
    graph.add_node("document", _wrap(document_agent.run, "DocumentAgent", ctx))
    graph.add_node("conflict", _wrap(conflict_agent.run, "ConflictExplainabilityAgent", ctx))
    graph.add_node("notify", _wrap(notification_agent.run, "NotificationAgent", ctx))

    graph.set_entry_point("consent")
    graph.add_edge("consent", "discovery")
    graph.add_conditional_edges("discovery", _route_after_discovery, {
        "matching": "matching", "notify_and_end": "notify",
    })
    graph.add_conditional_edges("matching", _route_after_matching, {
        "document": "document", "notify_and_end": "notify",
    })
    graph.add_edge("document", "conflict")
    graph.add_edge("conflict", "notify")
    graph.add_edge("notify", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_graph_for_citizen(citizen_id: str, trigger: str) -> GraphState:
    from agents.state import TriggerType
    initial_state = GraphState(citizen_id=citizen_id, trigger=TriggerType(trigger))
    result = get_graph().invoke(initial_state)
    # LangGraph returns a dict-like when using a Pydantic schema in some versions — normalize:
    return result if isinstance(result, GraphState) else GraphState(**result)
