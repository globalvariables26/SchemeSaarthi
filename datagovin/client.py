"""
data.gov.in OGD API client — real, tested, working dataset wired in.

Resource: "State/UTs-wise Average Monthly Income Per Agricultural Household" (Rajya Sabha,
via data.gov.in), confirmed working 2026-09. Used ONLY for demographic context shown during
onboarding — never for scheme eligibility rules, per the project's explicit design constraint.
"""
from __future__ import annotations

import os
import requests

BASE_URL = "https://api.data.gov.in/resource"
AGRI_INCOME_RESOURCE_ID = "163e46ee-0292-47b1-bcbc-b46b25b60c8d"

_cache: dict[str, float] = {}


class DataGovInClient:
    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("DATA_GOV_IN_API_KEY", "")

    def get_average_agricultural_income(self, state: str) -> dict | None:
        """Returns {"state": ..., "average_monthly_income": ..., "source": ...} or None if the
        state isn't in this dataset or the API call fails."""
        if not self.api_key:
            return None

        global _cache
        if not _cache:
            try:
                response = requests.get(
                    f"{BASE_URL}/{AGRI_INCOME_RESOURCE_ID}",
                    params={"api-key": self.api_key, "format": "json", "limit": 50},
                    headers={"User-Agent": "curl/8.4.0"},
                    timeout=15,
                )


                response.raise_for_status()
                records = response.json().get("records", [])
                _cache = {
                    r["state_group_of_uts"].strip().lower(): float(r["average_monthly_income_rs__"])
                    for r in records
                }
            except Exception:
                return None

        match = _cache.get(state.strip().lower())
        if match is None:
            return None
        return {
            "state": state,
            "average_monthly_income": match,
            "source": "data.gov.in — State/UTs-wise Average Monthly Income Per Agricultural "
                      "Household, July 2018-June 2019 (via Rajya Sabha)",
        }