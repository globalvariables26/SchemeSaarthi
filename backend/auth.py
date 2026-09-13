"""JWT verification — confirms the frontend's Supabase login token is real, by asking Supabase
directly rather than decoding the token locally. Slightly slower (one extra network call) but
avoids needing to match Supabase's exact signing method (legacy shared secret vs newer signing
keys), which differs between projects."""
import os
import requests
from fastapi import Header, HTTPException

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_ANON_KEY = os.environ["SUPABASE_ANON_KEY"]


def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]

    response = requests.get(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={"Authorization": f"Bearer {token}", "apikey": SUPABASE_ANON_KEY},
        timeout=10,
    )
    if response.status_code != 200:
        raise HTTPException(401, f"Invalid token: {response.text}")

    return response.json()["id"]