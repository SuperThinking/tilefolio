#!/usr/bin/env bash
# One-time (idempotent) server setup for Tilefolio on a fresh Ubuntu/Debian VPS. Run as root:
#
#   ssh root@HOST 'bash -s' -- <PUBLIC_HOSTNAME> "<CORS_ORIGIN>" "<CI_PUBLIC_KEY>" "<CLIENT_TOKEN>" < deploy/bootstrap.sh
#
#   PUBLIC_HOSTNAME  e.g. 139-84-221-234.sslip.io (Caddy gets a Let's Encrypt cert for it)
#   CORS_ORIGIN      the frontend origin, e.g. https://<github-user>.github.io
#   CI_PUBLIC_KEY    the GitHub Actions deploy key (ssh-ed25519 ...); it gets pinned to tilefolio-deploy
#   CLIENT_TOKEN     same value as the GitHub TILEFOLIO_CLIENT_TOKEN secret (public app-access gate)
#
# Safe to re-run: re-installs the deploy script / unit / Caddyfile and keeps /etc/tilefolio/env.
# Code is NOT deployed here. The first CI run (or a manual `tilefolio-deploy deploy`) does that.
set -euo pipefail

HOSTNAME_PUBLIC=${1:?public hostname required}
CORS_ORIGIN=${2:?cors origin required}
CI_PUBKEY=${3:?CI public key required}
CLIENT_TOKEN=${4:?client token required}
REPO_RAW_DIR=$(mktemp -d)
trap 'rm -rf "$REPO_RAW_DIR"' EXIT

[[ $EUID -eq 0 ]] || { echo "run as root" >&2; exit 1; }
[[ "$CI_PUBKEY" =~ ^ssh-(ed25519|rsa)\ [A-Za-z0-9+/=]+ ]] || { echo "CI_PUBLIC_KEY doesn't look like an SSH public key" >&2; exit 1; }
[[ "$CLIENT_TOKEN" =~ ^[A-Za-z0-9_-]{32,}$ ]] || { echo "CLIENT_TOKEN must be at least 32 URL-safe characters" >&2; exit 1; }

# The deploy script, unit and Caddyfile are sent alongside this script as a base64 tarball in TF_BUNDLE
# (see `make bootstrap`), so the server never needs to clone the repo.
[[ -n "${TF_BUNDLE:-}" ]] || { echo "TF_BUNDLE missing; run via 'make bootstrap'" >&2; exit 1; }
echo "$TF_BUNDLE" | base64 -d | tar -xz -C "$REPO_RAW_DIR"

export DEBIAN_FRONTEND=noninteractive
echo "== packages"
apt-get update -qq
apt-get install -y -qq curl ca-certificates gnupg ufw unattended-upgrades debian-keyring debian-archive-keyring apt-transport-https >/dev/null

if ! command -v caddy >/dev/null; then
  echo "== caddy (official apt repo)"
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/gpg.key | gpg --dearmor --yes -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt > /etc/apt/sources.list.d/caddy-stable.list
  apt-get update -qq && apt-get install -y -qq caddy >/dev/null
fi

if ! command -v uv >/dev/null; then
  echo "== uv (official installer)"
  curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin INSTALLER_NO_MODIFY_PATH=1 sh
fi

echo "== user + dirs"
id tilefolio >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/tilefolio --shell /bin/bash tilefolio
usermod -aG systemd-journal tilefolio
install -d -o tilefolio -g tilefolio -m 755 /opt/tilefolio /opt/tilefolio/releases /opt/tilefolio/.cache
install -d -o tilefolio -g tilefolio -m 700 /opt/tilefolio/.ssh

echo "== env (kept if present)"
install -d -m 755 /etc/tilefolio
if [[ ! -f /etc/tilefolio/env ]]; then
  cat > /etc/tilefolio/env <<EOF
# Tilefolio runtime config (see backend/app/config.py). Edit, then: systemctl restart tilefolio
TF_PUBLIC_ORIGIN=https://${HOSTNAME_PUBLIC}
TF_CORS_ORIGINS=${CORS_ORIGIN}
TF_SESSION_SECRET=$(head -c 32 /dev/urandom | base64 | tr -d '/+=')
TF_COOKIE_SECURE=1
TF_CLIENT_TOKEN=${CLIENT_TOKEN}
TF_METRICS_TOKEN=
TF_GOOGLE_CLIENT_ID=
TF_FINNHUB_API_KEY=
EOF
else
  sed -i "s#^TF_CORS_ORIGINS=.*#TF_CORS_ORIGINS=${CORS_ORIGIN}#" /etc/tilefolio/env
  if grep -q '^TF_CLIENT_TOKEN=' /etc/tilefolio/env; then
    sed -i "s#^TF_CLIENT_TOKEN=.*#TF_CLIENT_TOKEN=${CLIENT_TOKEN}#" /etc/tilefolio/env
  else
    printf '\nTF_CLIENT_TOKEN=%s\n' "$CLIENT_TOKEN" >> /etc/tilefolio/env
  fi
fi
chown root:tilefolio /etc/tilefolio/env && chmod 640 /etc/tilefolio/env

echo "== deploy script, sudoers, CI key"
install -o root -g root -m 755 "$REPO_RAW_DIR/remote-deploy.sh" /usr/local/bin/tilefolio-deploy
cat > /etc/sudoers.d/tilefolio <<'EOF'
tilefolio ALL=(root) NOPASSWD: /usr/bin/systemctl restart tilefolio, /usr/bin/journalctl -u tilefolio *
EOF
chmod 440 /etc/sudoers.d/tilefolio && visudo -cf /etc/sudoers.d/tilefolio >/dev/null
# restrict = no pty / forwarding; the key can only run tilefolio-deploy (it reads SSH_ORIGINAL_COMMAND)
echo "restrict,command=\"/usr/local/bin/tilefolio-deploy\" ${CI_PUBKEY}" > /opt/tilefolio/.ssh/authorized_keys
chown tilefolio:tilefolio /opt/tilefolio/.ssh/authorized_keys && chmod 600 /opt/tilefolio/.ssh/authorized_keys

echo "== systemd + caddy"
install -m 644 "$REPO_RAW_DIR/tilefolio.service" /etc/systemd/system/tilefolio.service
systemctl daemon-reload
systemctl enable tilefolio >/dev/null 2>&1 || true
sed "s#__HOST__#${HOSTNAME_PUBLIC}#" "$REPO_RAW_DIR/Caddyfile" > /etc/caddy/Caddyfile
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile >/dev/null
systemctl enable --now caddy >/dev/null 2>&1
systemctl reload caddy

echo "== firewall (22, 80, 443 only)"
ufw allow OpenSSH >/dev/null && ufw allow 80/tcp >/dev/null && ufw allow 443/tcp >/dev/null
ufw --force enable >/dev/null

echo "== ssh: key-only login"
if [[ -s /root/.ssh/authorized_keys ]]; then
  cat > /etc/ssh/sshd_config.d/00-tilefolio.conf <<'EOF'
# Installed by tilefolio bootstrap. First match wins, so this beats cloud-init's 50-*.conf.
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
  sshd -t && (systemctl reload ssh 2>/dev/null || systemctl reload sshd)
else
  echo "!! /root/.ssh/authorized_keys is empty; leaving password login ON to avoid a lockout" >&2
fi

echo "== done. Next: push to main (CI deploys), or: tar czf - backend | ssh root@HOST 'sudo -u tilefolio tilefolio-deploy deploy manual-1'"
