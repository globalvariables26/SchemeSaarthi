"""
Groq LLM client wrapper — Owner: Ishaan.

Two tiers, per the orchestration doc's free-tier plan:
  - REASONING_MODEL (70B) — Matching, Conflict/Explainability, Discovery's "is this new" call.
    Capped at 1,000 req/day free tier — don't loop this in test scripts.
  - FAST_MODEL (8B) — Notifications, checklists, consent-purpose plain-language text.
    Capped at 14,400 req/day — fine to hit harder while testing.

Both calls request JSON-mode structured output so callers get parseable dicts back, not free
text they have to regex out.
"""
from __future__ import annotations

import json
import os
from typing import Any

from groq import Groq

REASONING_MODEL = "openai/gpt-oss-120b"
FAST_MODEL = "openai/gpt-oss-20b"

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        api_key = os.environ["GROQ_API_KEY"]
        _client = Groq(api_key=api_key)
    return _client


def call_json(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = REASONING_MODEL,
    max_tokens: int = 800,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """Call Groq, requesting a JSON object back. Raises on transport/API errors — callers
    (agent nodes) MUST wrap this in try/except and convert failures into a `status: failed`
    NodeResult, per the 'no node exception ever escapes unhandled' rule (Section 3.7)."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt + "\nRespond ONLY with a valid JSON object, no prose, no markdown fences."},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    return json.loads(content)


def call_text(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str = FAST_MODEL,
    max_tokens: int = 300,
    temperature: float = 0.3,
) -> str:
    """Plain-text call for things like notification copy or a plain-language consent purpose
    string, where JSON mode would be overkill."""
    client = _get_client()
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content.strip()
