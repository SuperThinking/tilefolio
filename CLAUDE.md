# CLAUDE.md: Tilefolio

Guidance for AI agents (Claude Code, Hermes, …) working in this repo. Keep this file current.
Update it in the same change whenever you add a module, endpoint, setting, provider or convention.

## What this is
A minimal, projector-friendly **portfolio treemap** for Indian stocks, US stocks and Indian mutual funds.
The UI is just the treemap plus a hidden gear icon (top-right) that opens a settings drawer. The product is
**public multi-user and local-first**: it works with no login, using browser storage. Optional Google sign-in
backs up state to the server.

## Layout
```
backend/            Python 3.11+ FastAPI (uv). Serves /api/* and the built SPA from frontend/dist
  app/config.py     All env settings (TF_*). No pydantic-settings; dataclass + os.environ
  app/db.py         stdlib sqlite3; schema in SCHEMA; one short-lived connection per unit of work
  app/models.py     Instrument / Holding / Quote / ImportResult + the instrument KEY format
  app/prices/       Providers (yahoo, finnhub, mfnav, fx) + service.py (shared TTL cache + routing)
  app/importers/    csv_import.py (generic alias-based CSV/XLSX parser), presets.py (per-broker
                    steps/aliases), cas_import.py (PDF text via pypdfium2 → MF Central or casparser),
                    mfcentral_import.py (MF Central detailed CAS: own parser, FIFO cost, advisor→platform)
  app/brokers/      kite.py, upstox.py: stateless bring-your-own-key OAuth exchange + holdings
  app/instruments.py NSE equity list + Nifty500 industries + AMFI schemes -> SQLite (search, ISIN lookup)
  app/auth.py       Google ID-token verify + itsdangerous session token (Bearer header, or cookie same-origin)
  app/security.py   anonymous client UUID validation + optional public app-access token/origin gate
  app/routes/api.py Every endpoint (thin handlers)
  tests/            pytest; HTTP mocked with httpx.MockTransport (see conftest.Router)
frontend/           Svelte 5 (runes) + Vite; deps: d3-hierarchy, d3-interpolate only
  src/App.svelte            shell: view + gear + drawer + hotkeys + OAuth redirect handling
  src/lib/views/            visualizations; registry.js lists them (add new views here)
  src/lib/components/       SettingsPanel + tabs (Holdings, Import, Display, Themes, Account), ImportPreview, Summary
  src/lib/stores/           state.js (holdings/settings/themes, persisted), quotes.js (poller), persisted.js
  src/lib/portfolio.js      pure maths: value, day/total change, FX to base currency
  src/lib/themes.js         preset themes, colour scale, theme sanitising
  src/lib/brokers.js        BYO-key connect flows (redirect to broker → /connect/<id> → backend exchange)
  src/lib/sync.js           Google sign-in + last-write-wins sync
docs/data-sources.md  API research, limits, licensing caveats. Read it before touching providers
deploy/               bootstrap.sh (server setup), remote-deploy.sh (release manager), systemd unit, Caddyfile
.github/workflows/deploy.yml  CI/CD: PR → tests; main → backend to VPS + frontend to GitHub Pages
docs/deploy.md        Deployment runbook. Read it before touching deploy/ or CI
```

## Commands
```bash
# backend
make install && make test                 # (or: cd backend && uv sync --frozen && uv run pytest -q)
uv run python -m app.main                 # http://127.0.0.1:8000  (serves frontend/dist if built)
# frontend
cd frontend && npm install && npm run dev  # http://127.0.0.1:5173, proxies /api → :8000
npm run build                              # outputs frontend/dist for the backend to serve
make test / make dev-backend / make dev-frontend / make build
```

## Package registries
- Committed lockfiles (`backend/uv.lock`, `frontend/package-lock.json`) use the **public** registries. CI and the server
  install from them (`uv sync --frozen`, `npm ci`).
- A machine that must use a private mirror puts `PYPI_MIRROR` / `NPM_MIRROR` in a gitignored `mirrors.mk`. Then `make install`
  installs the same pinned versions and hashes through the mirror (`uv export` → `uv pip install --index-url`,
  `npm ci --replace-registry-host=always`), and `make test` / `make dev-*` use `uv run --no-sync`.
  **Never commit mirror URLs** (no `[[tool.uv.index]]`, no `.npmrc`). If you add a dependency on a mirror machine,
  relock with public URLs (`uv lock` / `npm install` without the mirror), or swap the hosts back in the lockfile.
- npm scripts run Vite through `"$npm_node_execpath"` on purpose. `npm run` puts every ancestor's
  `node_modules/.bin` on PATH, and a stray `node` package in a parent dir (e.g. `~/node_modules`, Node 16) can
  shadow the real Node and break Vite 6 (needs Node ≥18). Keep that pattern when adding scripts.

## Deployment (see docs/deploy.md)
- Frontend → GitHub Pages; backend → Vultr VPS behind Caddy at `https://139-84-221-234.sslip.io`. Both are deployed by
  `.github/workflows/deploy.yml` on push to `main`, each only when its paths change (frontend waits for the backend).
- **Agents ship through git only.** Branch → PR (CI green) → merge. Never hand-edit the server, never deploy from a
  dirty tree, and never put secrets in the repo (runtime config is `/etc/tilefolio/env` on the server, CI uses repo secrets).
- Verify a deploy with `make deploy-status` (`version` = the deployed git sha). Roll back with
  `gh workflow run deploy -f ref=<sha> -f target=backend`. The server also auto-rolls back if the health check fails.
- Frontend build vars: `VITE_API_BASE` (backend origin, empty = same origin) and `VITE_BASE` (`/<repo>/` on Pages).
  Use `apiUrl()` from `api.js` for any URL to the backend, and `import.meta.env.BASE_URL` for in-app paths. Never
  hard-code `/api/...` hrefs or `/` as the app root.
- Changing `deploy/bootstrap.sh`, the unit, the Caddyfile or `remote-deploy.sh` needs `make bootstrap` re-run (CI only ships `backend/`).
- Backend changes must keep `/api/health` returning `{"ok": true, "version": ...}`; the deploy health check depends on it.

## Core conventions
- **Instrument key** (shared by backend and frontend; never change it lightly):
  `IN_EQ:<NSE|BSE>:<SYMBOL>`, `US_EQ:<TICKER>`, `MF:<AMFI_CODE>`, `OTHER:<holding id>` (manual, no quote).
- **Holding JSON** (camelCase, see `models.Holding.to_dict` and `state.js normalizeHolding`):
  `{id,key,type,symbol,exchange,name,qty,avgPrice,currency,broker,sector,isin,priceOverride}`.
  `priceOverride != null` means a user-edited price that beats the live quote, and day change is then null.
- **Local-first**: the browser (localStorage `tf.*`) is the source of truth. The server stores one JSON blob per
  signed-in user (`user_state`) with last-write-wins on `updatedAt` (409 on stale writes). Synced:
  `{holdings, settings, customThemes}`. **Never sync broker keys.**
- **Re-sync semantics** (`replaceScope` in state.js): a broker import replaces existing holdings with the same
  (broker, type) pairs. A CAS import replaces **all** mutual funds, because a CAS covers every platform. The import preview
  lets the user untick asset types (e.g. drop broker MFs when funds come from the CAS) to avoid double counting.
- **Unknown cost** = `avgPrice 0` (`costKnown: false`). Such rows show Total % as "—" and are excluded from the total
  change/% in `totalsOf`. MF Central statements usually have this for units bought before the statement period.
- **View pipeline** (`portfolio.js`): `enrich` (all holdings, Holdings tab) → `viewModel` = `filterRows`
  (settings.visibleTypes / hiddenBrokers) → `mergeRows` (settings.mergeAccounts; same instrument key across accounts
  → one tile with `parts[]`; skipped when groupBy = broker; OTHER never merges) → `totalsOf`. Views only receive
  the view model, so the summary always reflects what's on screen (a tag shows when filters are active).
- **Hotkeys** (App.svelte `onKey`): s settings, h privacy, 1–4 toggle IN/US/MF/Other, 0 clear filters, m merge,
  g grouping, f fullscreen, Esc close. **Hold Tab** shows `HotkeysOverlay` (only when no drawer/dialog is open,
  so Tab keeps moving focus in forms). The list lives in `src/lib/hotkeys.js`; update it with every new shortcut.
- **Quotes**: one shared server-side cache (`prices/service.py`), TTL `TF_QUOTE_TTL` (45s), MF 15 min.
  The client polls `POST /api/quotes {keys}` every `settings.refreshSec` (≥15s) while the tab is visible.
- **Adding a price provider**: implement `async fetch_quotes(list[Instrument]) -> {key: Quote}`, then add it to
  `_routes()` in `prices/service.py` (order = fallback chain). Mock its URL in tests.
- **Adding a broker (file import)**: add an entry in `importers/presets.py`. Add aliases to `ALIASES` in
  `csv_import.py` only if its headers don't already map. Add a test with a realistic header row.
- **Adding a broker (API sync)**: new module in `app/brokers/` (stateless, return `ImportResult`), an endpoint in
  `routes/api.py`, a connector in `frontend/src/lib/brokers.js`, and `connect: [...]` in its preset.
- **Adding a view**: `frontend/src/lib/views/<Name>.svelte` taking `{rows, totals, settings, theme}`, registered in
  `views/registry.js`. It automatically appears in Display → View.
- **Adding a setting**: default in `DEFAULT_SETTINGS` (state.js) and a control in `DisplayTab.svelte`. Old saved
  settings merge with the defaults automatically.
- **Themes**: tokens in `THEME_KEYS`. Every token becomes a CSS var `--<key>`. Presets in `PRESET_THEMES`.
  Imported themes go through `sanitizeTheme` (hex colours only, so no CSS injection).

## Python compatibility note
Runs on Python 3.11–3.14 (dev env: 3.14 via uv). The code also stays compatible with Python 3.8 / pydantic v1 / FastAPI 0.73 so tests can also run in an
older env. Practically: use `typing.List/Optional` in FastAPI-facing modules (`routes/`, `auth.py`,
`ratelimit.py`), and **do not** add `from __future__ import annotations` there, because it breaks FastAPI
dependency resolution on old versions. Other modules may use it.

## Security / privacy rules (must keep)
- Server binds **127.0.0.1** only (`TF_HOST`). Expose it through a reverse proxy (deploy/Caddyfile). Never 0.0.0.0.
- CAS PDFs and broker exports are parsed **in memory**, never written to disk or logged (they contain PAN/PII).
- Broker API secrets and tokens pass through `/api/brokers/*` statelessly. Never store them and never log request bodies.
- Sessions: signed token from `/api/auth/google`. A cross-origin frontend (Pages) stores it in localStorage `tf.session` and
  sends `Authorization: Bearer` (third-party cookies are blocked). Same-origin also gets an HttpOnly SameSite=Lax cookie.
  CORS: exact origins from `TF_CORS_ORIGINS`, `allow_credentials=False`. `PUT /api/state` requires JSON.
- Rate limits live in `ratelimit.py` (in-memory, single process). Use Redis if you scale out.
- Every non-health API request must include a valid `X-Client-UUID`. Production also sets `TF_CLIENT_TOKEN`, which the
  static frontend receives as build-time `VITE_CLIENT_TOKEN` and sends as `X-Tilefolio-Client`; this is an abuse gate,
  not a secret. API request analytics are aggregated in SQLite and exposed only through token-protected
  `/internal/metrics` for Prometheus.
- Outbound requests use an honest generic User-Agent (`app/http.py`). Don't impersonate browsers or
  tune headers to evade provider rate limits or bot checks. On 403/429 providers trip a `Backoff`, so
  honour it. Never put user identity in outbound headers.

## Known constraints (see docs/data-sources.md)
- Multi-user broker OAuth needs broker approval (SEBI retail-algo framework, 2025-26). Upstox paused new
  multi-user apps in Mar 2026, and Kite apps are single-user by default. Hence **file import first, BYO key second**.
- Yahoo and Finnhub free tiers are personal/non-commercial. Swap in a licensed feed before a commercial launch.
- MF day change = latest NAV vs previous stored NAV (NAVs publish in the evening).
- casparser does not support MF Central statements. They're detected by the `MFCentralDetailCAS` marker and parsed by
  `mfcentral_import.py`. NSDL/CDSL depository CAS is rejected with a clear message (not supported yet).
- MF Central "Advisor" → platform: registration codes INZ000031633 = Zerodha and INZ000208032 = Groww (Nextbillion)
  were observed in real statements. Other platforms are matched by name keywords (best effort).
- Tests for statement parsers must use **synthetic** text fixtures. Never commit real statements or PII.
- Groww has no free API (paid Trade API). INDmoney has no public holdings API for third parties.

## Testing
`cd backend && uv run pytest -q`. All network access is mocked. The frontend has no test runner yet, so
`npm run check` (svelte-check) plus `npm run build` are the gate. Keep pure logic in `portfolio.js` / `themes.js`
/ `format.js` so it's easy to unit-test later (vitest).
