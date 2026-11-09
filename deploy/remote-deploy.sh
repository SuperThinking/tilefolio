#!/usr/bin/env bash
# Tilefolio release manager — installed on the server as /usr/local/bin/tilefolio-deploy.
#
# The CI deploy key is pinned to this script via a forced command in
# ~tilefolio/.ssh/authorized_keys, so that key can only run these verbs:
#
#   deploy <version>   read a .tar.gz of the repo's backend/ on stdin, install it as a new release,
#                      switch, restart, health-check; auto-rollback if the new release is unhealthy
#   rollback           switch back to the previous release
#   status             print the live release and /api/health
#   logs               last 200 lines of the service log
#
# From CI:     git archive --format=tar.gz HEAD backend | ssh tilefolio@HOST "deploy $SHA"
# As root:     sudo -u tilefolio tilefolio-deploy status
set -euo pipefail

APP=/opt/tilefolio
RELEASES=$APP/releases
KEEP=5
export UV_CACHE_DIR=$APP/.cache/uv UV_PYTHON_INSTALL_DIR=$APP/python UV_NO_PROGRESS=1

read -r ACTION ARG _ <<<"${SSH_ORIGINAL_COMMAND:-${*:-status}}"

log() { echo "[tilefolio-deploy] $*" >&2; }
die() { log "ERROR: $*"; exit 1; }
health() { curl -fsS --max-time 5 http://127.0.0.1:8000/api/health; }
live() { readlink -f "$APP/current" 2>/dev/null || true; }

switch_to() {  # atomic symlink swap + restart
  ln -sfn "$1" "$APP/current.new" && mv -Tf "$APP/current.new" "$APP/current"
  sudo /usr/bin/systemctl restart tilefolio
}

wait_healthy() {  # $1 = expected version
  for _ in $(seq 1 40); do
    sleep 1
    if health 2>/dev/null | grep -q "\"version\":\"$1\""; then return 0; fi
  done
  return 1
}

case "${ACTION:-}" in
  deploy)
    [[ "${ARG:-}" =~ ^[0-9A-Za-z._-]{1,64}$ ]] || die "usage: deploy <version>  (git sha or [A-Za-z0-9._-])"
    rel="$RELEASES/$(date -u +%Y%m%dT%H%M%SZ)-$ARG"
    mkdir -p "$rel"
    tar -xzf - -C "$rel" || die "could not read release tarball from stdin"
    [[ -f "$rel/backend/pyproject.toml" ]] || die "tarball has no backend/pyproject.toml"
    echo "$ARG" > "$rel/backend/VERSION"
    log "installing dependencies for $ARG"
    (cd "$rel/backend" && uv sync --frozen --no-dev --quiet) || die "uv sync failed; live release untouched"

    prev="$(live)"
    log "switching ${prev##*/} -> ${rel##*/}"
    switch_to "$rel"
    if wait_healthy "$ARG"; then
      log "healthy: $(health)"
    else
      log "new release failed its health check; recent logs:"
      sudo /usr/bin/journalctl -u tilefolio -n 40 --no-pager >&2 || true
      if [[ -n "$prev" && -d "$prev" ]]; then
        log "rolling back to ${prev##*/}"
        switch_to "$prev"
      fi
      rm -rf "$rel"
      exit 1
    fi
    # prune old releases, never the live one
    cur="$(live)"
    ls -1dt "$RELEASES"/*/ 2>/dev/null | sed 's#/$##' | tail -n +$((KEEP + 1)) | while read -r old; do
      [[ "$old" == "$cur" ]] || rm -rf "$old"
    done
    ;;
  rollback)
    cur="$(live)"
    prev="$(ls -1dt "$RELEASES"/*/ 2>/dev/null | sed 's#/$##' | grep -vxF "$cur" | head -n1 || true)"
    [[ -n "$prev" ]] || die "no previous release to roll back to"
    log "rolling back ${cur##*/} -> ${prev##*/}"
    switch_to "$prev"
    wait_healthy "$(cat "$prev/backend/VERSION")" || die "previous release is not healthy either"
    health
    ;;
  status)
    echo "live: $(basename "$(live)")"
    echo "releases:"; ls -1t "$RELEASES" 2>/dev/null | sed 's/^/  /'
    echo "health: $(health 2>&1 || echo DOWN)"
    ;;
  logs)
    sudo /usr/bin/journalctl -u tilefolio -n 200 --no-pager
    ;;
  *)
    die "unknown command '${ACTION:-}'. Allowed: deploy <version> | rollback | status | logs"
    ;;
esac
