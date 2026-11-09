"""Runtime configuration, read from environment variables (optionally a .env file).

Kept dependency-free on purpose (no pydantic-settings). Every knob lives here.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv(BACKEND_DIR / ".env")


def _bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # Networking: bind to localhost only; put a reverse proxy (Caddy/nginx) in front on a VPS.
    host: str = os.environ.get("TF_HOST", "127.0.0.1")
    port: int = int(os.environ.get("TF_PORT", "8000"))
    public_origin: str = os.environ.get("TF_PUBLIC_ORIGIN", "http://localhost:8000")

    data_dir: Path = Path(os.environ.get("TF_DATA_DIR", str(BACKEND_DIR / "data")))
    static_dir: Path = Path(os.environ.get("TF_STATIC_DIR", str(BACKEND_DIR.parent / "frontend" / "dist")))

    # Sessions (Google sign-in). Generate a stable secret in prod or sessions reset on restart.
    session_secret: str = os.environ.get("TF_SESSION_SECRET") or secrets.token_urlsafe(32)
    cookie_secure: bool = _bool("TF_COOKIE_SECURE", False)
    google_client_id: str = os.environ.get("TF_GOOGLE_CLIENT_ID", "")

    # Cross-origin frontend (e.g. GitHub Pages). Comma-separated exact origins; empty = same-origin only.
    cors_origins: list = field(default_factory=lambda: [
        o.strip().rstrip("/") for o in os.environ.get("TF_CORS_ORIGINS", "").split(",") if o.strip()
    ])
    # Deployed git sha (written to backend/VERSION by deploy/remote-deploy.sh); shown in /api/health.
    version: str = os.environ.get("TF_VERSION") or (
        (BACKEND_DIR / "VERSION").read_text().strip() if (BACKEND_DIR / "VERSION").exists() else "dev"
    )

    # Price providers
    finnhub_api_key: str = os.environ.get("TF_FINNHUB_API_KEY", "")
    quote_ttl_seconds: int = int(os.environ.get("TF_QUOTE_TTL", "45"))
    mf_nav_refresh_seconds: int = int(os.environ.get("TF_MF_NAV_REFRESH", str(6 * 3600)))
    fx_ttl_seconds: int = int(os.environ.get("TF_FX_TTL", "300"))
    max_instruments_per_request: int = 400

    # Instrument master refresh (NSE equity list, Nifty500 industries, AMFI schemes)
    load_instruments_on_start: bool = _bool("TF_LOAD_INSTRUMENTS", True)

    # Uploads
    max_upload_bytes: int = 5 * 1024 * 1024
    max_state_bytes: int = 1024 * 1024

    extra: dict = field(default_factory=dict)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "tilefolio.sqlite3"


settings = Settings()
settings.data_dir.mkdir(parents=True, exist_ok=True)
