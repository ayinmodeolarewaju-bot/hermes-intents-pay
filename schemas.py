"""Tool schemas shown to the Hermes model."""

from __future__ import annotations

_SAFETY = (
    "Never ask the user for a seed phrase, private key, or signing key. "
    "This tool does not broadcast a transaction or move funds. "
    "dry defaults to true and returns prices only. "
    "A live deposit address requires refund_to (the payer's own origin-chain address) "
    "and a confirmation_token from a previous call the user explicitly accepted."
)

INTENTS_LIST_TOKENS = {
    "name": "intents_list_tokens",
    "description": (
        "List tokens and chains the NEAR Intents 1-Click API can swap. "
        "Use this before a quote when the payer's chain or token symbol is unclear. "
        "Without filters, returns the chain list plus USDC, USDT, and NEAR rows. "
        "Pass symbol (USDC, USDT, NEAR, ETH, ...) and/or chain (arb, eth, base, sol, near, ...) to filter."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "symbol": {
                "type": "string",
                "description": "Token symbol to match, such as USDC, USDT, NEAR, or ETH. USDT also matches USDT0.",
            },
            "chain": {
                "type": "string",
                "description": "1-Click blockchain id, such as arb, eth, base, sol, near, bsc, or op.",
            },
            "include_all": {
                "type": "boolean",
                "description": "When true and no symbol or chain is set, include the first page of every token. Default false.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum rows to return (1-200). Default 40.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

INTENTS_QUOTE = {
    "name": "intents_quote",
    "description": (
        "Get a NEAR Intents 1-Click quote for paying a NEAR account from another chain. "
        "Default is a dry EXACT_OUTPUT quote: amount is what the recipient should receive "
        "in currency (USDC, USDT, or NEAR), and the response says what the payer sends. "
        "recipient is required and there is no default payee. "
        "Default payer route is USDC on Arbitrum. "
        + _SAFETY
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "amount": {
                "type": "string",
                "description": "Human amount, such as 25 or 10.5. For EXACT_OUTPUT this is what the recipient gets. For EXACT_INPUT this is what the payer sends.",
            },
            "currency": {
                "type": "string",
                "description": "What the NEAR recipient is paid: USDC, USDT, or NEAR. Default USDC. NEAR settles as wNEAR.",
                "enum": ["USDC", "USDT", "NEAR"],
            },
            "recipient": {
                "type": "string",
                "description": "NEAR account that receives the payout. Required. There is no default.",
            },
            "pay_from": {
                "type": "string",
                "description": "Symbol the payer sends, such as USDC, USDT, ETH, or NEAR. Default matches currency, except NEAR invoices default to USDC.",
            },
            "origin_chain": {
                "type": "string",
                "description": "Chain the payer sends from: arb, eth, base, sol, near, and other 1-Click ids. Default arb.",
            },
            "origin_asset": {
                "type": "string",
                "description": "Optional exact 1-Click asset id from intents_list_tokens. Overrides pay_from and origin_chain.",
            },
            "swap_type": {
                "type": "string",
                "description": "EXACT_OUTPUT (default, recipient receives amount) or EXACT_INPUT (payer sends amount).",
                "enum": ["EXACT_OUTPUT", "EXACT_INPUT"],
            },
            "slippage_bps": {
                "type": "integer",
                "description": "Slippage in basis points. 100 means 1 percent. Default 100.",
            },
            "memo": {
                "type": "string",
                "description": "Invoice note stored locally. It is not submitted as an on-chain message.",
            },
            "dry": {
                "type": "boolean",
                "description": "True (default) returns a price and does not create a deposit address. False asks for a live quote and is refused unless confirm and confirmation_token are set.",
            },
            "refund_to": {
                "type": "string",
                "description": "Payer's own address on the origin chain. Required for a live quote. Ignored as a placeholder on dry quotes when omitted.",
            },
            "confirm": {
                "type": "boolean",
                "description": "Set true only after the user has explicitly agreed to request a deposit address. Must be paired with confirmation_token from the previous response.",
            },
            "confirmation_token": {
                "type": "string",
                "description": "One-time token returned when a live quote was previewed. Binds the amount, assets, recipient, and refund address.",
            },
        },
        "required": ["amount", "recipient"],
        "additionalProperties": False,
    },
}

INTENTS_CREATE_INVOICE = {
    "name": "intents_create_invoice",
    "description": (
        "Create a shareable invoice for a NEAR account and attach a 1-Click quote. "
        "Same payment fields as intents_quote. Persists an invoice id the user can check later. "
        "The summary is the shareable card. Dry by default, so the card has no deposit address. "
        + _SAFETY
    ),
    "parameters": INTENTS_QUOTE["parameters"],
}

INTENTS_INVOICE_STATUS = {
    "name": "intents_invoice_status",
    "description": (
        "Read a saved Intents Pay invoice, or ask 1-Click for the status of a deposit address. "
        "Omit both ids to list recent invoices. A dry invoice has no deposit, so there is nothing "
        "to track on-chain until a confirmed live quote exists. This does not submit a transaction."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "invoice_id": {
                "type": "string",
                "description": "Invoice id (ip_...) or number (IP-...) from intents_create_invoice or intents_quote.",
            },
            "deposit_address": {
                "type": "string",
                "description": "1-Click deposit address from a confirmed live quote.",
            },
            "deposit_memo": {
                "type": "string",
                "description": "Deposit memo, when the live quote included one. Required by 1-Click for some chains.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

INTENTS_VERIFY_QUOTE = {
    "name": "intents_verify_quote",
    "description": (
        "Verify a 1-Click quote signature locally with the published manager public key. "
        "Pass the full quote response, or an invoice_id whose raw quote was saved. "
        "When the signature is invalid, any deposit address is withheld. "
        "Verification uses a public key only."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "quote": {
                "type": "object",
                "description": "Full JSON object returned by POST /v0/quote (quote, quoteRequest, signature, timestamp).",
            },
            "invoice_id": {
                "type": "string",
                "description": "Saved invoice id or number, used when quote is omitted.",
            },
        },
        "required": [],
        "additionalProperties": False,
    },
}

TOOL_SCHEMAS = {
    "intents_list_tokens": INTENTS_LIST_TOKENS,
    "intents_quote": INTENTS_QUOTE,
    "intents_create_invoice": INTENTS_CREATE_INVOICE,
    "intents_invoice_status": INTENTS_INVOICE_STATUS,
    "intents_verify_quote": INTENTS_VERIFY_QUOTE,
}
