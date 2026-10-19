#!/bin/bash
# One-time setup of the shared Obsidian vault repository on the EC2 server (run as root).
# docs/HERMES_TELEGRAM_OBSIDIAN_PLAN.md H4. Usage:  sudo bash setup-vault-git.sh
# Then add each person's key:  sudo bash add-vault-key.sh ceo "ssh-ed25519 AAAA... ceo-laptop"
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
# uid 10001 = the user inside the Quixotic AI container, so the API and SSH pushes share /srv/vault.
id -u vault >/dev/null 2>&1 || useradd --system --uid 10001 --create-home --home-dir /srv/vault --shell /usr/bin/git-shell vault
install -d -o vault -g vault -m 750 /srv/vault /srv/vault/.ssh /srv/vault/work
[ -d /srv/vault/vault.git ] || sudo -u vault git init --bare -b main /srv/vault/vault.git
install -o vault -g vault -m 755 "$here/pre-receive" /srv/vault/vault.git/hooks/pre-receive
install -o vault -g vault -m 755 "$here/post-receive" /srv/vault/vault.git/hooks/post-receive
if [ ! -f /srv/vault/hooks.env ]; then
  printf 'QUIXOTIC_API_URL=http://127.0.0.1:8000\nQB_HERMES_SHARED_SECRET=CHANGE-ME\n' > /srv/vault/hooks.env
  chown vault:vault /srv/vault/hooks.env; chmod 600 /srv/vault/hooks.env
  echo "Edit /srv/vault/hooks.env: your domain and the API's QB_HERMES_SHARED_SECRET."
fi
touch /srv/vault/.ssh/authorized_keys && chown vault:vault /srv/vault/.ssh/authorized_keys && chmod 600 /srv/vault/.ssh/authorized_keys
echo "Vault repository ready: vault@<server>:/srv/vault/vault.git. In .env set QB_VAULT_REMOTE=/srv/vault/vault.git"
