# Tilefolio

A minimal, full-screen **portfolio treemap** for Indian stocks, US stocks and Indian mutual funds. It's built to sit
on a monitor or projector. The screen shows only the treemap. A hidden ⚙ in the top-right opens everything else.

- **Import:** guided broker exports (Zerodha, Groww, Upstox, INDmoney), any CSV/XLSX, a CAMS/KFintech **CAS PDF**
  for all mutual funds, or manual entry. There's also a "Request a broker" button.
- **Optional direct sync:** bring your own Kite Connect Personal or Upstox API key.
- **Live-ish prices:** polled every 30 s–5 min and shared through a server-side cache. Tiles are coloured by **day %** or **total %**.
- **Manage holdings:** edit qty, avg or price (price override), plus broker and sector.
- **Privacy:** a hotkey `h` hides every amount. Separate toggles cover tile values and the total portfolio value.
- **Grouping:** flat, asset class, broker or sector.
- **Themes:** Terminal, Dark, Light, Colorblind and Paper presets, plus custom themes (editor and JSON import/export).
- **Local-first:** no signup needed. Optional Google sign-in syncs across devices.

## Quick start
```bash
# needs: uv, Node 18+. Packages install from the internal mirrors
# (backend/pyproject.toml [tool.uv.index], frontend/.npmrc)
make install          # backend deps (uv) + frontend deps (npm)
make test             # backend tests
make dev-backend      # terminal 1 → http://127.0.0.1:8000
make dev-frontend     # terminal 2 → http://127.0.0.1:5173  (open this)
```
To build for production, run `make run`. It builds `frontend/dist` and serves it from FastAPI on 127.0.0.1:8000.

Configuration is through `backend/.env` (see `.env.example`). Everything is optional locally. Set `TF_SESSION_SECRET` and
`TF_COOKIE_SECURE=1` in production. Set `TF_GOOGLE_CLIENT_ID` to enable sign-in, and `TF_FINNHUB_API_KEY` for Finnhub US quotes.

In production, set `TF_CLIENT_TOKEN` on the backend and the same value as the GitHub Actions secret
`TILEFOLIO_CLIENT_TOKEN`; the frontend build sends it as `X-Tilefolio-Client`. Every frontend request also sends an
anonymous browser UUID as `X-Client-UUID`. The UUID is not connected to Google accounts. These controls reduce casual
API abuse, but a browser-delivered token is not a true secret—use a server-side proxy or user authentication if the
data must not be obtainable by copied browser requests.

## Hotkeys
`s` settings · `h` hide amounts · `g` cycle grouping · `f` fullscreen · `Esc` close

## Deploying on a VPS
The app binds **127.0.0.1 only**. Put Caddy in front (`deploy/Caddyfile`) and run it under systemd
(`deploy/tilefolio.service`). Run a single worker: the rate limiter and quote cache are in-process.

## Data sources and caveats
See [docs/data-sources.md](docs/data-sources.md). Short version:
- Prices come from free, unofficial or personal-use sources (Yahoo, Finnhub free tier, AMFI, mfapi.in). They may be
  delayed or throttled. **Get a licensed data feed before a commercial launch.**
- Brokers currently restrict multi-user API apps (SEBI retail-algo framework). That's why file import comes first.
  Confirm regulatory and privacy obligations with Legal/Compliance before going public.
- CAS PDFs contain PAN and other PII. They're parsed in memory and never stored.

Not investment advice.
