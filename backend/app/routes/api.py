"""All HTTP endpoints under /api. Grouped by section; keep handlers thin."""

import json
import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from .. import auth, db, instruments
from ..brokers import kite, upstox
from ..brokers.kite import BrokerError
from ..config import settings
from ..http import get_client
from ..importers import cas_import, csv_import
from ..importers.presets import PRESETS, TEMPLATE_CSV, public_presets
from ..models import Instrument
from ..prices import finnhub, fx, service
from ..ratelimit import misc_limiter, quotes_limiter, upload_limiter

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# ---- meta ------------------------------------------------------------------

@router.get("/health")
def health() -> dict:
    return {"ok": True, "version": settings.version}


@router.get("/config")
def public_config() -> dict:
    return {
        "googleClientId": settings.google_client_id or None,
        "finnhub": finnhub.enabled(),
        "brokers": public_presets(),
        "quoteTtl": settings.quote_ttl_seconds,
    }


@router.get("/search", dependencies=[Depends(misc_limiter)])
async def search(q: str = Query(..., min_length=2, max_length=60), kinds: str = "IN_EQ,MF,US_EQ") -> dict:
    results = instruments.search(q, kinds=kinds, limit=15)
    if "US_EQ" in kinds and finnhub.enabled():
        try:
            r = await get_client().get(
                "https://finnhub.io/api/v1/search", params={"q": q, "token": settings.finnhub_api_key}
            )
            if r.status_code == 200:
                for it in (r.json().get("result") or [])[:10]:
                    sym = it.get("symbol", "")
                    if sym and "." not in sym and it.get("type") in {"Common Stock", "ETP", "ADR"}:
                        results.append({"type": "US_EQ", "symbol": sym, "exchange": "US",
                                        "name": it.get("description", ""), "isin": "", "sector": ""})
        except Exception as e:
            log.info("finnhub search failed: %s", e)
    return {"results": results}


# ---- quotes ----------------------------------------------------------------

class QuotesIn(BaseModel):
    keys: List[str]


@router.post("/quotes", dependencies=[Depends(quotes_limiter)])
async def quotes(body: QuotesIn) -> dict:
    if len(body.keys) > settings.max_instruments_per_request:
        raise HTTPException(413, f"At most {settings.max_instruments_per_request} instruments per request")
    insts, invalid = [], []
    for k in dict.fromkeys(body.keys):  # de-dupe, keep order
        try:
            insts.append(Instrument.parse(k))
        except ValueError:
            invalid.append(k)
    got = await service.get_quotes(insts)
    rate = await fx.usd_inr()
    missing = [i.key for i in insts if i.key not in got and i.type != "OTHER"]
    return {
        "quotes": {k: q.to_dict() for k, q in got.items()},
        "fx": {"USDINR": rate.get("rate"), "source": rate.get("source"), "ts": rate.get("ts")},
        "missing": missing,
        "invalid": invalid,
        "ts": time.time(),
    }


# ---- imports ---------------------------------------------------------------

async def _read_body(request: Request) -> bytes:
    cl = request.headers.get("content-length")
    if cl and int(cl) > settings.max_upload_bytes:
        raise HTTPException(413, "File too large (max 5 MB)")
    data = b""
    async for chunk in request.stream():
        data += chunk
        if len(data) > settings.max_upload_bytes:
            raise HTTPException(413, "File too large (max 5 MB)")
    if not data:
        raise HTTPException(400, "Empty upload")
    return data


@router.get("/import/template.csv")
def template_csv() -> PlainTextResponse:
    return PlainTextResponse(
        TEMPLATE_CSV, media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tilefolio-template.csv"},
    )


@router.post("/import/file", dependencies=[Depends(upload_limiter)])
async def import_file(request: Request, broker: str = "generic", filename: str = "upload.csv") -> dict:
    """Raw-body upload (Content-Type: application/octet-stream) — avoids a multipart dependency."""
    if broker not in PRESETS:
        raise HTTPException(400, f"Unknown broker preset '{broker}'")
    data = await _read_body(request)
    try:
        return csv_import.import_file(data, filename, broker).to_dict()
    except ValueError as e:
        raise HTTPException(422, str(e))


@router.post("/import/cas", dependencies=[Depends(upload_limiter)])
async def import_cas(request: Request) -> dict:
    """Body: raw PDF bytes. Password in X-CAS-Password header. Nothing is stored or logged."""
    data = await _read_body(request)
    if not data.startswith(b"%PDF"):
        raise HTTPException(422, "That doesn't look like a PDF")
    password = request.headers.get("x-cas-password", "")
    try:
        return cas_import.import_cas(data, password).to_dict()
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(501, str(e))


# ---- bring-your-own-key broker sync (stateless) -----------------------------

class KiteIn(BaseModel):
    api_key: str
    api_secret: str
    request_token: str


class UpstoxIn(BaseModel):
    client_id: str
    client_secret: str
    code: str
    redirect_uri: str


@router.post("/brokers/kite/holdings", dependencies=[Depends(upload_limiter)])
async def kite_holdings(body: KiteIn) -> dict:
    try:
        return (await kite.fetch_holdings(body.api_key, body.api_secret, body.request_token)).to_dict()
    except BrokerError as e:
        raise HTTPException(502, str(e))


@router.post("/brokers/upstox/holdings", dependencies=[Depends(upload_limiter)])
async def upstox_holdings(body: UpstoxIn) -> dict:
    try:
        return (await upstox.fetch_holdings(
            body.client_id, body.client_secret, body.code, body.redirect_uri)).to_dict()
    except BrokerError as e:
        raise HTTPException(502, str(e))


class BrokerRequestIn(BaseModel):
    broker: str
    note: Optional[str] = None


@router.post("/broker-requests", dependencies=[Depends(misc_limiter)])
def broker_request(body: BrokerRequestIn, request: Request) -> dict:
    name = body.broker.strip()[:80]
    if not name:
        raise HTTPException(400, "Broker name required")
    with db.connect() as c:
        c.execute(
            "INSERT INTO broker_requests(broker, note, user_id) VALUES(?,?,?)",
            (name, (body.note or "")[:500], auth.current_user_id(request)),
        )
    return {"ok": True}


# ---- auth + sync -----------------------------------------------------------

class GoogleIn(BaseModel):
    credential: str


@router.post("/auth/google", dependencies=[Depends(misc_limiter)])
async def google_login(body: GoogleIn, response: Response) -> dict:
    info = await auth.verify_google_credential(body.credential)
    uid = auth.upsert_user(info["sub"], info.get("email", ""), info.get("name", ""))
    token = auth.make_session(uid)
    response.set_cookie(
        auth.COOKIE, token, max_age=auth.MAX_AGE, httponly=True,
        samesite="lax", secure=settings.cookie_secure, path="/",
    )
    return {"user": auth.get_user(uid), "token": token}


@router.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(auth.COOKIE, path="/")
    return {"ok": True}


@router.get("/auth/me")
def me(request: Request) -> dict:
    uid = auth.current_user_id(request)
    return {"user": auth.get_user(uid) if uid else None}


@router.get("/state")
def get_state(uid: int = Depends(auth.require_user)) -> dict:
    with db.connect() as c:
        row = c.execute("SELECT state_json, updated_at FROM user_state WHERE user_id = ?", (uid,)).fetchone()
    if not row:
        return {"state": None, "updatedAt": 0}
    return {"state": json.loads(row["state_json"]), "updatedAt": row["updated_at"]}


@router.put("/state")
async def put_state(request: Request, uid: int = Depends(auth.require_user)) -> dict:
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "JSON only")  # also blocks simple cross-site form posts
    raw = await _read_body(request)
    if len(raw) > settings.max_state_bytes:
        raise HTTPException(413, "State too large")
    try:
        body = json.loads(raw)
        state, updated_at = body["state"], int(body["updatedAt"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(400, "Expected {state, updatedAt}")
    with db.connect() as c:
        row = c.execute("SELECT updated_at FROM user_state WHERE user_id = ?", (uid,)).fetchone()
        if row and row["updated_at"] > updated_at:
            raise HTTPException(409, "Server has newer state")
        c.execute(
            "INSERT INTO user_state(user_id, state_json, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET state_json=excluded.state_json, updated_at=excluded.updated_at",
            (uid, json.dumps(state), updated_at),
        )
    return {"ok": True, "updatedAt": updated_at}


@router.delete("/state")
def delete_state(uid: int = Depends(auth.require_user)) -> dict:
    with db.connect() as c:
        c.execute("DELETE FROM user_state WHERE user_id = ?", (uid,))
    return {"ok": True}
