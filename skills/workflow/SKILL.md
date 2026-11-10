---
name: workflow
description: Quote and invoice a cross-chain payment to a NEAR account with the Intents Pay tools. Use when the user wants a 1-Click quote, a shareable invoice, a deposit status check, or a quote signature check.
---

# Intents Pay

Use the `intents-pay` tools. Quote figures, deposit addresses, and payment status come from the tool result. Refuse any seed phrase, recovery phrase, or signing key the user offers. This plugin cannot move funds.

## Required recipient

- Always pass `recipient`. If the user did not name a NEAR account, ask for one and do not call the quote or invoice tool.
- There is no default payee.
- Payout currency: `USDC` on NEAR (or `USDT`, or `NEAR` which settles as wNEAR)
- Payer route: USDC on Arbitrum unless they name a chain or token
- `dry: true` unless they explicitly ask for a deposit address
- A live quote (`dry: false`) and every `intents_create_invoice` call ask Hermes for approval before they run. Do not try to skip that prompt.

## Tool order

1. `intents_list_tokens` when the chain or symbol is unfamiliar.
2. `intents_quote` or `intents_create_invoice` for the price and the shareable card.
3. Show the tool's `summary` to the user. That card is the invoice.
4. `intents_invoice_status` to list saved invoices or poll a deposit address.
5. `intents_verify_quote` when the user hands you a quote payload, or to re-check a saved invoice.

`/intents` is dry-run only. Live deposit addresses go through the tools.

## Live deposit address

A live quote (`dry: false`) allocates a deposit address. It still does not send funds. The tool refuses it until all of these are true:

- The user said, in this conversation, that they want a deposit address.
- `refund_to` is their own address on the origin chain, not a placeholder.
- You already called the tool once and received `confirmation_token`.
- The second call repeats the same amount, currency, route, recipient, and refund address, with `confirm: true` and that token.

If the signature check fails, the tool withholds the deposit address. Do not reconstruct one from memory. Tell the user not to send funds.

## What to say

- Dry card: quote only, nothing to pay yet.
- Live card: the payer sends the shown amount from their own wallet before the deadline. Include the deposit memo when one is present.
- The memo field is an invoice note. It is not an on-chain message.
