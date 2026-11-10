# Changelog

## 1.1.0

- Quotes and invoices require an explicit NEAR `recipient`. There is no built-in or configured default payee. A missing recipient returns an error and does not call 1-Click.
- `pre_tool_call` returns Hermes's approve directive before `intents_create_invoice` and before a non-dry `intents_quote`, so Hermes shows its approval prompt before a payable request is created. Dry quotes, token lists, status checks, and signature checks stay read-only and do not ask.
- Requires Hermes `>=0.23.0`, which honors `{"action": "approve"}` from that hook.

## 1.0.0

- Initial Intents Pay tools, desktop pane, and dry-quote flow.
