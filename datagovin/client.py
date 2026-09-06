"""
data.gov.in OGD API client — Owner: Jaya.

IMPORTANT — read Section 7 of SchemeSaarthi_Technical_Orchestration.md before touching this
file. Do NOT hardcode a guessed resource_id without testing it first (a plain browser URL test
is enough, see docs/JAYA_TASKS.md Step 3).

Steps for Jaya:
1. Register a free account at https://data.gov.in and generate an API key
   (My Account > API Keys). Put it in .env.local as DATA_GOV_IN_API_KEY.
2. Go to https://data.gov.in/catalogs and search (on the SITE'S search, not a general web
   search) for: "Socio Economic Caste Census", "BPL households state wise",
   "district wise social category", "below poverty line ration cards".
3. On each candidate dataset's page, confirm it shows an API option (not just a downloadable
   file) — only API-mode datasets work with get_resource() below.
4. Copy the resource_id (a UUID in the dataset's API URL) into a config value once confirmed —
   do NOT commit it as a guess; leave a TODO comment if not yet confirmed at hackathon time.
5. This data feeds REALISTIC DEMOGRAPHIC DEFAULTS for the synthetic demo citizen profile
   (e.g. a state's average rural household income bracket -> a plausible `income` seed value).
   It is NEVER used as the scheme-eligibility ruleset itself — that stays hand-authored in
   db/seed.py per the handoff doc's explicit constraint (already filled in with real,
   researched scheme names/criteria — see db/seed.py).
"""
from __future__ import annotations

import os

import requests

BASE_URL = "https://api.data.gov.in/resource"


class DataGovInClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DATA_GOV_IN_API_KEY", "")

    def get_resource(self, resource_id: str, filters: dict | None = None, limit: int = 100) -> dict:
        """Fetch a page of records from a data.gov.in resource. Raises requests.RequestException
        on network failure or a non-2xx response — callers (e.g. Discovery Agent's demographic
        refresh) must catch this and degrade gracefully, same pattern as the scheme-source
        offline failure mode."""
        if not self.api_key:
            raise ValueError("DATA_GOV_IN_API_KEY is not set — check your .env.local")

        params = {"api-key": self.api_key, "format": "json", "limit": limit}
        if filters:
            for field, value in filters.items():
                params[f"filters[{field}]"] = value

        url = f"{BASE_URL}/{resource_id}"
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        return response.json()


def cache_snapshot(supabase_client, resource_id: str, records: list[dict]) -> None:
    """Store a fetched batch in cached_snapshot so it doubles as offline-fallback data, per
    Section 7.5 point 5. Use source_table='scheme_source' is WRONG here — data.gov.in data is
    demographic context, not scheme data; if you want to cache it, add a distinct
    source_table value like 'datagovin_demographic' (requires loosening the check constraint
    in db/schema.sql — do that in a jaya/ branch PR if needed, don't edit schema.sql silently)."""
    raise NotImplementedError(
        "Decide on a cache strategy once a real resource_id is confirmed — see docstring."
    )
