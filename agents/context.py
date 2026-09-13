"""Shared dependencies every node needs — Owner: Ishaan."""
from __future__ import annotations

import os
from dataclasses import dataclass

from supabase import Client, create_client

from agents.consent_gateway import ConsentGateway


@dataclass
class AgentContext:
    db: Client
    consent: ConsentGateway


def build_context() -> AgentContext:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]  # agents run server-side, need RLS-bypass
    db = create_client(url, key)
    return AgentContext(db=db, consent=ConsentGateway(db))
