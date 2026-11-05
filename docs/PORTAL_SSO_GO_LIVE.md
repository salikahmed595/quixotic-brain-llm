# Portal sign-in: go-live guide for Salik

## What this change does

People who work at Quixotic can sign in to Maqsad from the Portal (Saleshub) with one click, from the office only. Anyone who is an admin in the Portal becomes an admin in Maqsad. The Portal also tells Maqsad when someone is removed or changed there.

It adds one database column (`users.portal_user_id`, migration 018). It only adds; it removes nothing. The migration runs by itself when the `api` container starts.

## It stays OFF until you set a key

Nothing changes for anyone until `QB_PORTAL_PUBLIC_KEY` has a value in `/opt/quixotic/.env`. Deploying the code (steps a to f) is safe on its own. Step g is what switches the feature on.

## Warning

`git pull` brings in every commit on `main` that is not on production yet, not only this change. Check what is coming first with `git log HEAD..origin/main --oneline`.

## Steps

All commands run on the server (65.1.137.241) in `/opt/quixotic`.

**a. Merge the pull request** on GitHub (`feat/portal-sso` into `main`).

**b. Note the current commit** so we can go back:

    git rev-parse HEAD

Write it down. Rollback for this step: nothing to undo.

**c. Take a backup:**

    docker compose -f docker-compose.prod.yml exec -T api python -m backend.ops.backup create --dir /srv/vault/backups --s3

Rollback: nothing to undo.

**d. Deploy the code:**

    git pull
    docker compose -f docker-compose.prod.yml up -d --build

Rollback: `git checkout <commit noted in b>` then `docker compose -f docker-compose.prod.yml up -d --build`. The new column stays in the database; it is harmless and the old code ignores it. Restore the backup only as a last resort.

**e. Check it came up:**

    curl -s https://maqsad.quixoticcreatives.com/v1/health

It should answer healthy. Then check that migration 018 applied, by confirming the column `users.portal_user_id` exists (for example, run `\d users` in psql inside the database container and look for `portal_user_id`).

**f. Make sure admin two-step sign-in is on.** In `/opt/quixotic/.env` the line must read `QB_ADMIN_MFA_REQUIRED=true`. If you change it, run `up -d` (not `restart`).

**g. Switch the feature on.** Copy the file first: `cp /opt/quixotic/.env /opt/quixotic/.env.bak`. Saizaz will send you a small file called `maqsad.env` privately. Add its 4 lines to `/opt/quixotic/.env`:

- `QB_PORTAL_PUBLIC_KEY`
- `QB_PORTAL_ISSUER`
- `QB_PORTAL_HOOK_SECRET`
- `QB_PORTAL_SESSION_TTL_SECONDS`

Then apply it:

    docker compose -f docker-compose.prod.yml up -d

A plain `restart` does not re-read the file. Do not paste these values in chat, tickets or git.
Rollback: empty the `QB_PORTAL_PUBLIC_KEY` value (leave the line, set nothing after `=`) and run `up -d` again. The feature is off again.

**h. Check the door is there:**

    curl -s -o /dev/null -w "%{http_code}" -X POST https://maqsad.quixoticcreatives.com/v1/auth/portal -d token=x

The answer must be `401`. A `404` means the new code is not running (go back to step d).

**i. Tell Saizaz it is done.** He will do the first sign-in test from the Portal.

## Rollback summary

1. Feature off: empty `QB_PORTAL_PUBLIC_KEY`, then `up -d`.
2. Code back: `git checkout <commit from b>`, then `up -d --build`.
3. Last resort: restore the backup from step c.
