.PHONY: install test dev-backend dev-frontend build run bootstrap deploy-status

# Optional, gitignored: PYPI_MIRROR / NPM_MIRROR for machines that must install through a mirror.
-include mirrors.mk

install:
ifdef PYPI_MIRROR
	cd backend && uv venv -q --allow-existing && uv export --frozen --no-emit-project -q -o .venv/requirements.txt \
	  && uv pip install -q --index-url $(PYPI_MIRROR) -r .venv/requirements.txt
else
	cd backend && uv sync --frozen
endif
ifdef NPM_MIRROR
	cd frontend && npm ci --registry $(NPM_MIRROR) --replace-registry-host=always
else
	cd frontend && npm ci
endif

test:
	cd backend && uv run --no-sync python -m pytest -q

dev-backend:
	cd backend && uv run --no-sync uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

dev-frontend:
	cd frontend && npm run dev

build:
	cd frontend && npm run build

run: build
	cd backend && uv run --no-sync python -m app.main

# ---- deployment (see docs/deploy.md) ---------------------------------------
DEPLOY_HOST ?= 139.84.221.234
BACKEND_HOST ?= 139-84-221-234.sslip.io
CORS_ORIGIN ?=
CLIENT_TOKEN ?=
CI_PUBKEY ?= $(HOME)/.ssh/tilefolio_ci.pub

# One-time / idempotent server setup over your root SSH key.
bootstrap:
	@test -n "$(CORS_ORIGIN)" || { echo "set CORS_ORIGIN=https://<github-user>.github.io"; exit 1; }
	@test -n "$(CLIENT_TOKEN)" || { echo "set CLIENT_TOKEN to the same value as GitHub secret TILEFOLIO_CLIENT_TOKEN"; exit 1; }
	@test -f "$(CI_PUBKEY)" || { echo "missing $(CI_PUBKEY) (ssh-keygen -t ed25519 -N '' -f $(basename $(CI_PUBKEY)) -C tilefolio-ci)"; exit 1; }
	bundle=$$(tar czf - -C deploy remote-deploy.sh tilefolio.service Caddyfile | base64 | tr -d '\n'); \
	ssh root@$(DEPLOY_HOST) "TF_BUNDLE=$$bundle bash -s -- '$(BACKEND_HOST)' '$(CORS_ORIGIN)' '$$(cat $(CI_PUBKEY))' '$(CLIENT_TOKEN)'" < deploy/bootstrap.sh

deploy-status:
	curl -fsS https://$(BACKEND_HOST)/api/health; echo
