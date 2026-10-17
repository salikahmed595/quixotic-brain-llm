#!/bin/bash
# Lets one person's laptop push ONLY refs/heads/proposals/<name>. Usage: sudo bash add-vault-key.sh <name> "<public key>"
# Link the same <name> to their account in Quixotic AI: System -> Integrations -> Obsidian branch.
set -euo pipefail
name="$1"; key="$2"
[[ "$name" =~ ^[a-z0-9_-]+$ ]] || { echo "name: lowercase letters, numbers, - or _"; exit 1; }
line="command=\"QUIXOTIC_BRANCH=$name git-shell -c \\\"\$SSH_ORIGINAL_COMMAND\\\"\",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty $key"
echo "$line" >> /srv/vault/.ssh/authorized_keys
echo "Added. On the laptop: git clone vault@<server>:/srv/vault/vault.git && git checkout -b proposals/$name && git push -u origin proposals/$name"
