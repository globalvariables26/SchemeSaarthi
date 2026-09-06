"""
Shared LangGraph state object — Owner: Ishaan.

Every node reads/writes this typed object. Keeping it a Pydantic model (not a raw dict) means
a node writing the wrong shape fails loudly at dev time instead of silently corrupting state
for the next node — important because this doc's Section 5 spec makes `node_results` and
`replan_events` double as the audit trail and SSE event source respectively.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class TriggerType(str, Enum):
    NEW_SCHEME = "new_scheme"
    RULE_CHANGE = "rule_change"
    SCHEDULED_CHECK = "scheduled_check"
    MANUAL_DEMO_TRIGGER = "manual_demo_trigger"


NodeStatus = Literal["ok", "degraded", "failed", "uncertain", "escalated"]


class NodeResult(BaseModel):
    status: NodeStatus
    reason: str = ""
    output: dict[str, Any] = Field(default_factory=dict)


class ReplanEvent(BaseModel):
    from_node: str
    to_node: str
    reason: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ClearedAttribute(BaseModel):
    """An attribute value the ConsentGateway has confirmed is cleared for THIS purpose.
    Never construct this manually outside consent_gateway.py."""
    attribute_key: str
    attribute_value: str
    citizen_attribute_id: str  # for the audit-trail justifying_attributes link


class MatchWorkingRecord(BaseModel):
    scheme_id: str
    scheme_name: str
    applies: Optional[bool] = None       # None = not yet evaluated / uncertain
    confidence: float = 0.0
    missing_data: list[str] = Field(default_factory=list)
    reasoning: str = ""
    justifying_attribute_ids: list[str] = Field(default_factory=list)
    status: Literal["matched", "needs_document", "conflicting", "uncertain", "rejected"] = "uncertain"
    rejection_reason: Optional[str] = None


class PendingDocument(BaseModel):
    document_type: str
    reason: str
    checklist: list[str] = Field(default_factory=list)


class GraphState(BaseModel):
    citizen_id: str
    trigger: TriggerType

    cleared_attributes: dict[str, ClearedAttribute] = Field(default_factory=dict)
    current_matches: list[MatchWorkingRecord] = Field(default_factory=list)
    pending_documents: list[PendingDocument] = Field(default_factory=list)

    # {agent_name: NodeResult} — appended to by every node. This IS the audit trail's raw
    # material and the SSE event source (see backend/sse.py).
    node_results: dict[str, NodeResult] = Field(default_factory=dict)

    # Written ONLY by the Orchestrator routing function.
    replan_events: list[ReplanEvent] = Field(default_factory=list)

    # scratch fields individual nodes populate for the next node to read
    new_scheme_payload: Optional[dict[str, Any]] = None
    new_rule_payload: Optional[dict[str, Any]] = None

    class Config:
        use_enum_values = True
