# Codex Invite Pipeline

Utilities for a staged Codex SSO invite pipeline:

1. Log in seed accounts and save Codex `auth.json` files.
2. Use seed auth files to send workspace referral invites.
3. Log in invited accounts and save their `auth.json` files.
4. Run protocol activation for invited accounts.

## Files

- `codex_protocol_login.py` - direct Codex OAuth + SSO login, supports CSV batch mode.
- `codex_invitation_helper.py` - single-account invite and invite quota probing.
- `codex_invitation_batch.py` - concurrent seed-account invitation.
- `codex_activation_helper.py` - single-account protocol activation.
- `codex_activation_batch.py` - concurrent invited-account activation.
- `sentinel.py`, `sentinel_quickjs.py`, `openai_sentinel_quickjs.js` - Sentinel token helpers.
- `codex_sso_login.py` - browser-based fallback login helper.

## Local-Only Data

Do not commit runtime data. The following are intentionally ignored:

- `accounts/`
- `runs/`
- `*.csv`
- `*auth*.json`
- `.venv/`
- logs and Python caches

These files can contain emails, passwords, access tokens, refresh tokens, and account IDs.

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

## Pipeline

Create a CSV from the example format:

```text
user1@example.com,YourPassword
user2@example.com,YourPassword
```

Log in seed accounts:

```bash
.venv/bin/python codex_protocol_login.py \
  --csv runs/example/seed_accounts.csv \
  --out-dir runs/example/seeds \
  --proxy http://127.0.0.1:7897 \
  --concurrency 10 \
  --retries 2 \
  --skip-existing
```

Invite from seed accounts:

```bash
.venv/bin/python codex_invitation_batch.py \
  --auth-dir runs/example/seeds \
  --domain example.com \
  --per-account 5 \
  --concurrency 10 \
  --proxy http://127.0.0.1:7897 \
  --save-back \
  --out runs/example/invite_results.json
```

Build invited-account CSV from successful invites:

```bash
jq -r '.[].invites[]?.email | . + ",YourPassword"' \
  runs/example/invite_results.json > runs/example/invitee_accounts.csv
```

Log in invited accounts:

```bash
.venv/bin/python codex_protocol_login.py \
  --csv runs/example/invitee_accounts.csv \
  --out-dir runs/example/invitees \
  --proxy http://127.0.0.1:7897 \
  --concurrency 10 \
  --retries 2 \
  --skip-existing
```

Activate invited accounts:

```bash
.venv/bin/python codex_activation_batch.py \
  --auth-dir runs/example/invitees \
  --concurrency 10 \
  --proxy http://127.0.0.1:7897 \
  --save-back
```
