#!/bin/bash
# Add one Obsidian contributor's laptop key (owner request 2026-10-20; docs/DEPLOYMENT.md §7).
#   sudo bash deploy/vault/add-contributor.sh ceo "ssh-ed25519 AAAA... ceo-laptop"
# The key may only pull/push /srv/vault/contributors/<name>.git (vault-shell). Then link `<name>` to the person's account in
# System -> Integrations -> Obsidian branch: the app creates the repository with the notes that person may see.
set -euo pipefail
name="$1"; key="$2"
[[ "$name" =~ ^[a-z0-9][a-z0-9_-]{0,39}$ ]] || { echo "name: lowercase letters, numbers, - or _"; exit 1; }
[[ "$key" =~ ^(ssh-ed25519|ecdsa-sha2-nistp256|ssh-rsa)\  ]] || { echo "paste the PUBLIC key (ssh-ed25519 AAAA...)"; exit 1; }
line="restrict,command=\"/srv/vault/bin/vault-shell $name\" $key"     # restrict = no shell, pty, forwarding
grep -qF "$key" /srv/vault/.ssh/authorized_keys && { echo "this key is already added"; exit 1; }
echo "$line" >> /srv/vault/.ssh/authorized_keys
echo "Added. On the laptop: git clone vault@<server>:contributors/$name.git && cd $name && git checkout -b proposals/$name && git push -u origin proposals/$name"
