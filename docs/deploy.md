# Deployment

```
git push main ──► GitHub Actions (.github/workflows/deploy.yml)
                   ├─ backend/** or deploy/** changed ─► pytest ─► ssh tilefolio@VPS "deploy <sha>"
                   │                                            (tarball on stdin → new release → restart
                   │                                             → health check → auto-rollback on failure)
                   └─ frontend/** changed ─► svelte-check + build ─► GitHub Pages
                                              (waits for the backend deploy when both changed)
Browser ──► https://<user>.github.io/<repo>/   (static SPA)
        ──► https://139-84-221-234.sslip.io/api/*  (Caddy :443 → 127.0.0.1:8000, CORS + client-access gate)
```

PRs run the tests and the build but never deploy. **Git is the only way to change production.** Don't edit
files on the server by hand. The next deploy would overwrite them, and there would be no record.

## Server layout (Vultr VPS)
| Path | What |
|---|---|
| `/opt/tilefolio/releases/<utc>-<sha>/backend` | one dir per release, each with its own `.venv` (last 5 kept) |
| `/opt/tilefolio/current` | symlink to the live release |
| `/etc/tilefolio/env` | runtime config (`TF_*`), root:tilefolio 640. **Not in git.** Edit, then `systemctl restart tilefolio` |
| `/var/lib/tilefolio` | SQLite data (users, synced state, NAV history). Back this up |
| `/usr/local/bin/tilefolio-deploy` | release manager (`deploy/remote-deploy.sh`) |
| `tilefolio.service`, `/etc/caddy/Caddyfile` | app on 127.0.0.1:8000; Caddy is the only public listener (80/443, auto TLS) |

The CI SSH key can only run `tilefolio-deploy` (forced command + `restrict`), with these verbs:
`deploy <sha>`, `rollback`, `status`, `logs`.

## One-time setup
1. **SSH key to the server** (you type the root password once):
   `ssh-copy-id root@139.84.221.234`
2. **CI deploy key** (stays out of the repo):
   `ssh-keygen -t ed25519 -N '' -f ~/.ssh/tilefolio_ci -C tilefolio-ci`
3. **Bootstrap the server.** Installs Caddy, uv, the systemd unit and the firewall, and turns off SSH password login.
   Generate one URL-safe value and use it in both places:
   ```bash
   CLIENT_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
   gh secret set TILEFOLIO_CLIENT_TOKEN -R SuperThinking/tilefolio --body "$CLIENT_TOKEN"
   make bootstrap CORS_ORIGIN=https://<github-user>.github.io CLIENT_TOKEN="$CLIENT_TOKEN"
   ```
   The backend checks the exact configured origin, the `X-Tilefolio-Client` value and a valid `X-Client-UUID` on
   every API request except the public deployment health probe. The client token is visible in the static bundle, so
   it is an abuse-control gate, not a confidential API credential.
4. **GitHub repo**: create it, then run `bash deploy/github-setup.sh`. It sets the variables and secrets,
   enables Pages (source = Actions) and pushes `main`. It reads `GH_TOKEN` from the env or from `.env`, and it's safe to re-run.
   Optionally, under Settings → Environments → `production`,
   add required reviewers so that production deploys need approval.
5. Optional integrations go in `/etc/tilefolio/env`:
   - Google sign-in: set `TF_GOOGLE_CLIENT_ID`, and add `https://<user>.github.io` as an authorised JS origin.
   - `TF_FINNHUB_API_KEY`.
   - `TF_METRICS_TOKEN` (optional, then scrape `https://<host>/internal/metrics` with `X-Metrics-Token`; keep this
     token server-side).
   - Broker apps need their redirect URL set to `https://<user>.github.io/<repo>/connect/<kite|upstox>`.

## Day-to-day (humans and agents)
| Task | How |
|---|---|
| Ship a change | branch → PR (CI must be green) → merge to `main` → auto deploy |
| Watch a deploy | `gh run watch` / `gh run list --workflow deploy` |
| What's live? | `make deploy-status` → `{"ok":true,"version":"<sha>"}` (compare with `git rev-parse origin/main`) |
| Roll back | `gh workflow run deploy -f ref=<older-sha> -f target=backend` (or `target=both`). Emergency: `ssh root@HOST sudo -u tilefolio tilefolio-deploy rollback` |
| Redeploy everything | `gh workflow run deploy -f ref=main -f target=both` |
| Server logs | `ssh root@HOST journalctl -u tilefolio -n 200` |
| Change runtime config | edit `/etc/tilefolio/env` on the server and restart. Document new keys in `backend/.env.example` and `config.py` |
| Change server setup (unit, Caddy, deploy script) | edit `deploy/*`, merge, then re-run `make bootstrap …` (bootstrap files aren't pushed by CI) |

## Notes and limits
- `sslip.io` is a free wildcard DNS service. If it goes down, the API hostname stops resolving. For anything
  long-lived, point your own domain's A record at the server, then update `BACKEND_HOST`, re-run bootstrap and update `CORS_ORIGIN`.
- The repo, the Pages site and the API are all public. Uploaded CAS and broker files are parsed in memory and never stored.
  Synced state (holdings) is stored in `/var/lib/tilefolio`.
- Single process, single box, so rate limits and the quote cache are in memory. Anonymous request metrics are stored
  as hourly aggregates in SQLite (`api_clients`, `api_client_buckets`, `api_request_metrics`).

## API metrics and visualization

The backend records request count, status, latency, endpoint, hourly activity and anonymous unique-client counts.
For a quick check, configure `TF_METRICS_TOKEN` and run:

```bash
curl -H "X-Metrics-Token: $TF_METRICS_TOKEN" https://<host>/internal/metrics
```

Point Prometheus at that endpoint and build a small Grafana dashboard with panels for `tilefolio_api_requests_total`,
`tilefolio_unique_clients_24h`, request duration, error rate, and requests by endpoint. Do not expose the metrics
endpoint to the public frontend.
