# Catalog submission (do not open this PR from automation)

Prepared for the Hermes Agent Plugin Hackathon. This file is the catalog change. It is **not** opened here. The plugin repository is private today, so it is not eligible until the steps below are done.

## Where the entry goes

- Repository: `https://github.com/NousResearch/hermes-agent`
- Path: `plugin-catalog/intents-pay.yaml`
- One new file. No other edits.
- Base branch: `main`
- The submitter must be the owner of `ayinmodeolarewaju-bot/hermes-intents-pay` (catalog rule 5).

## Pin

`sha` below is the plugin commit to pin: a full 40-character id, not a branch or tag. Image URLs must use that same commit. If this line still says `SHA_TO_PIN`, read the branch tip of this repo after the pin-recording commit and copy the `sha:` value from there.

```yaml
name: intents-pay
repo: https://github.com/ayinmodeolarewaju-bot/hermes-intents-pay
sha: SHA_TO_PIN
description: >
  Crypto invoices and cross-chain payment quotes for a NEAR account via the
  NEAR Intents 1-Click API. Dry quotes by default. Never moves funds and never
  handles signing keys.
maintainer: ayinmodeolarewaju-bot
tier: community
category: tools
requires_hermes: ">=0.22.0"
version: "1.0.0"
title: Intents Pay
docs_url: https://github.com/ayinmodeolarewaju-bot/hermes-intents-pay
image: https://raw.githubusercontent.com/ayinmodeolarewaju-bot/hermes-intents-pay/SHA_TO_PIN/docs/screenshots/banner.png
screenshots:
  - https://raw.githubusercontent.com/ayinmodeolarewaju-bot/hermes-intents-pay/SHA_TO_PIN/docs/screenshots/dry-quote.png
  - https://raw.githubusercontent.com/ayinmodeolarewaju-bot/hermes-intents-pay/SHA_TO_PIN/docs/screenshots/usdt-quote.png
readme: true
platforms: []
known_issues:
  - "Dry quotes on EVM and Solana send a public placeholder refund address so 1-Click can check the format. No deposit is created. A live quote rejects that placeholder and requires the payer's own refund address plus a one-time confirmation token."
  - "Verification for this release used live dry quotes only. Completing a mainnet deposit address is gated and was not part of the test run."
capabilities:
  provides_tools:
    - intents_list_tokens
    - intents_quote
    - intents_create_invoice
    - intents_invoice_status
    - intents_verify_quote
  provides_hooks: []
  provides_middleware: []
  requires_env: []
```

`subdir` is omitted because `plugin.yaml` is at the repository root.

Suggested PR title: `catalog: add intents-pay`

## PR description to paste

Intents Pay lets Hermes price and invoice a payment to a NEAR account through the NEAR Intents 1-Click API (`https://1click.chaindefuser.com`).

Surfaces:

- Five tools: token list, dry/live quote, invoice, status, local Ed25519 quote verification
- `/intents` slash command (dry quotes only)
- `hermes intents-pay` CLI
- Bundled skill `intents-pay:workflow`
- Desktop pane (`desktop/plugin.js`) plus dashboard routes (`dashboard/plugin_api.py`)

Rule 13 disclosure:

- Outbound HTTPS to `1click.chaindefuser.com` only: `GET /v0/tokens`, `POST /v0/quote`, `GET /v0/status`. No deposit submission, no transfer broadcast.
- Optional partner key `INTENTS_PAY_API_KEY`, read with `agent.secret_scope.get_secret` and sent only as `X-API-Key`. Quotes work with no key. 1-Click may add a small app fee when the key is absent. This plugin adds no fee.
- Writes a JSON invoice ledger under the profile plugin-data directory. No telemetry, no shell commands, no background process, no credential-file reads.
- Dry quotes on EVM and Solana use well-known public placeholder refund addresses so the API can validate address format. Live quotes require the payer's own refund address and a one-time confirmation token bound to the payment. Cron and other unattended runs cannot create a live quote.
- A quote whose signature does not verify does not reveal a deposit address.

Screenshots are the files named in `screenshots:` (rendered from the 9 Nov 2026 Hermes CLI session; the transcript is `docs/demo/hermes-session.txt` in the pinned tree).

Local check already run on Hermes Agent v0.23.0:

```text
hermes plugins validate <plugin> --install-deps   # ok, security scan safe, no warnings
hermes plugins doctor <plugin> --ci               # 5 tools
```

## What has to happen before the catalog PR is eligible

1. Make `https://github.com/ayinmodeolarewaju-bot/hermes-intents-pay` **public**. Catalog CI clones the pinned commit anonymously. A private repo fails that clone.
2. Confirm the pinned commit is the one named `sha:` above, and that this tree contains `plugin.yaml`, `__init__.py`, and the screenshots.
3. Open the PR yourself (owner account) against `NousResearch/hermes-agent`, adding only `plugin-catalog/intents-pay.yaml`. Do not set `tier` to `official` or `verified`.
4. Wait until the catalog CI job is green. It clones this repo at `sha` and runs `hermes plugins validate --install-deps`.
5. Post a demo video under 90 seconds on X, tag `@NousResearch`, and show the plugin working. Shot list: `DEMO_SCRIPT.md`.
6. Submit the catalog PR link and the X link at `https://form.typeform.com/to/FwJLvOln`. Deadline: 11 Nov 2026, 5 PM EST.

Hackathon entry is the plugin. This repository's own pull request only lands the source. It is not the catalog PR.
