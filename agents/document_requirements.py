"""
Determines a citizen's baseline required documents. Tries Groq's compound-mini (real web
search) first; falls back to a plain reasoning-model call using its own knowledge if compound
fails for any reason (rate limit, account restriction, etc.) — this keeps the feature alive
even under Groq's free-tier constraints, at the cost of the fallback path not being live-web.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone

from groq import Groq

REFRESH_INTERVAL_HOURS = 48

_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=os.environ["GROQ_API_KEY"])
    return _client


def _extract_json(text: str) -> list[dict]:
    text = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
    match = re.search(r"\[.*\]", text, re.DOTALL)
    return json.loads(match.group(0) if match else text)


def _build_prompt(profile: dict) -> str:
    return f"""Determine the CURRENT list of mandatory Indian government identity/eligibility
documents a citizen with this profile should hold in 2026:
{json.dumps(profile)}

Include baseline KYC documents (Aadhaar, PAN if 18+) AND any newer/recently introduced
requirements (for example APAAR ID for students). Only include documents genuinely relevant to
this exact profile (age, category, occupation, state).

Respond with ONLY a JSON array, no other text, in this exact shape:
[{{"document_type": "snake_case_name", "why_required": "one sentence", "checklist": ["step 1", "step 2", "step 3", "step 4"]}}]
"""


def determine_required_documents(profile: dict) -> list[dict]:
    prompt = _build_prompt(profile)
    try:
        response = _get_client().chat.completions.create(
            model="groq/compound-mini",
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_json(response.choices[0].message.content)
    except Exception:
        # Fallback: no live web search, but still a genuine AI determination from the
        # model's own knowledge, so the feature degrades instead of breaking outright.
        response = _get_client().chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[{"role": "user", "content": prompt}],
        )
        return _extract_json(response.choices[0].message.content)


def refresh_if_stale(db, citizen_id: str, force: bool = False) -> bool:
    existing = db.table("citizen_required_documents").select("last_checked").eq(
        "citizen_id", citizen_id).order("last_checked", desc=True).limit(1).execute().data

    if existing and not force:
        last = datetime.fromisoformat(existing[0]["last_checked"].replace("Z", "+00:00"))
        if datetime.now(timezone.utc) - last < timedelta(hours=REFRESH_INTERVAL_HOURS):
            return False

    attr_rows = db.table("citizen_attributes").select("attribute_key, attribute_value").eq(
        "citizen_id", citizen_id).eq("consent_granted", True).is_("revoked_at", "null").execute().data
    profile = {r["attribute_key"]: r["attribute_value"] for r in attr_rows}
    if not profile:
        return False

    try:
        docs = determine_required_documents(profile)
    except Exception:
        return False

    db.table("citizen_required_documents").delete().eq("citizen_id", citizen_id).execute()
    for d in docs:
        db.table("citizen_required_documents").insert({
            "citizen_id": citizen_id,
            "document_type": d["document_type"],
            "why_required": d.get("why_required", ""),
            "checklist": d.get("checklist", []),
        }).execute()
    return True