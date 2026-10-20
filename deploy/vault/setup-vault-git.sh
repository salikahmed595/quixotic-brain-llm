#!/bin/bash
# One-time setup of private Obsidian contributor repositories on the EC2 server (run as root). Owner request 2026-10-20.
#   sudo bash deploy/vault/setup-vault-git.sh ai.yourcompany.com
# Then per person:  sudo bash deploy/vault/add-contributor.sh ceo "ssh-ed25519 AAAA... ceo-laptop"   (docs/DEPLOYMENT.md §7)
# Layout: /srv/vault/work (backend's approved vault, never served), /srv/vault/contributors/<name>.git (one private repository
# per person, created by the app when an admin links them), /srv/vault/contributors/_views (backend working copies).
set -euo pipefail
domain="${1:?usage: setup-vault-git.sh <your domain>}"
here="$(cd "$(dirname "$0")" && pwd)"
id -u vault >/dev/null 2>&1 || useradd --system --uid 10001 --create-home --home-dir /srv/vault --shell /usr/bin/git-shell vault
install -d -o vault -g vault -m 750 /srv/vault /srv/vault/.ssh /srv/vault/work /srv/vault/contributors /srv/vault/bin
install -o root -g root -m 755 "$here/vault-shell" /srv/vault/bin/vault-shell
touch /srv/vault/.ssh/authorized_keys && chown vault:vault /srv/vault/.ssh/authorized_keys && chmod 600 /srv/vault/.ssh/authorized_keys
if [ ! -f /srv/vault/contributors/hooks.env ]; then
  # The hooks run on this host (outside Docker), so they reach the app through Caddy's HTTPS address.
  secret=$(grep -E '^QB_HERMES_SHARED_SECRET=' /opt/quixotic/.env | cut -d= -f2- || true)
  [ -n "$secret" ] || { echo "set QB_HERMES_SHARED_SECRET in /opt/quixotic/.env first"; exit 1; }
  printf 'QUIXOTIC_API_URL=https://%s\nQB_HERMES_SHARED_SECRET=%s\n' "$domain" "$secret" > /srv/vault/contributors/hooks.env
  chown vault:vault /srv/vault/contributors/hooks.env; chmod 600 /srv/vault/contributors/hooks.env
fi
grep -q '^QB_VAULT_CONTRIBUTORS_DIR=' /opt/quixotic/.env || echo "QB_VAULT_CONTRIBUTORS_DIR=/srv/vault/contributors" >> /opt/quixotic/.env
echo "Ready. Restart: docker compose -f docker-compose.prod.yml up -d ; then add each person's key with add-contributor.sh."
