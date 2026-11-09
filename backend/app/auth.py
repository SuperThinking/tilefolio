"""Optional Google sign-in (for cross-device sync only — the app works fully signed-out).

Flow: frontend uses Google Identity Services to get an ID token ("credential"), POSTs it here;
we verify it against Google's tokeninfo endpoint, upsert the user and return a signed session
token. Same-origin deployments also get it as an HttpOnly, SameSite=Lax cookie; a cross-origin
frontend (GitHub Pages) sends it as `Authorization: Bearer <token>` because browsers block
third-party cookies.
"""

import time
from typing import Optional

from fastapi import HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from . import db
from .config import settings
from .http import get_client

COOKIE = "tf_session"
MAX_AGE = 30 * 24 * 3600
TOKENINFO_URL = "https://oauth2.googleapis.com/tokeninfo"
_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

_signer = URLSafeTimedSerializer(settings.session_secret, salt="tf-session")


async def verify_google_credential(credential: str) -> dict:
    if not settings.google_client_id:
        raise HTTPException(503, "Google sign-in is not configured on this server")
    r = await get_client().get(TOKENINFO_URL, params={"id_token": credential})
    if r.status_code != 200:
        raise HTTPException(401, "Invalid Google credential")
    info = r.json()
    if info.get("aud") != settings.google_client_id or info.get("iss") not in _ISSUERS:
        raise HTTPException(401, "Google credential was not issued for this app")
    if int(info.get("exp", 0)) < time.time():
        raise HTTPException(401, "Google credential expired")
    if str(info.get("email_verified")).lower() != "true":
        raise HTTPException(401, "Google email not verified")
    return info


def upsert_user(sub: str, email: str, name: str) -> int:
    with db.connect() as c:
        c.execute(
            "INSERT INTO users(google_sub, email, name) VALUES(?,?,?) "
            "ON CONFLICT(google_sub) DO UPDATE SET email=excluded.email, name=excluded.name",
            (sub, email, name),
        )
        return c.execute("SELECT id FROM users WHERE google_sub = ?", (sub,)).fetchone()["id"]


def make_session(user_id: int) -> str:
    return _signer.dumps({"uid": user_id})


def current_user_id(request: Request) -> Optional[int]:
    header = request.headers.get("authorization", "")
    raw = header[7:].strip() if header[:7].lower() == "bearer " else request.cookies.get(COOKIE)
    if not raw:
        return None
    try:
        return int(_signer.loads(raw, max_age=MAX_AGE)["uid"])
    except (BadSignature, SignatureExpired, KeyError, ValueError, TypeError):
        return None


def require_user(request: Request) -> int:
    uid = current_user_id(request)
    if uid is None:
        raise HTTPException(401, "Sign in to sync")
    return uid


def get_user(uid: int) -> Optional[dict]:
    with db.connect() as c:
        row = c.execute("SELECT id, email, name FROM users WHERE id = ?", (uid,)).fetchone()
    return dict(row) if row else None
