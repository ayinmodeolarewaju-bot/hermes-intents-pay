"""Tool handlers. Each returns a JSON string and never raises."""

from __future__ import annotations

import json
from typing import Any

from .runtime import make_deps
from .service import create_invoice, list_tokens, payment_status, quote_payment, verify_quote

_BOUND_CTX: Any = None


def bind_context(ctx: Any) -> None:
    global _BOUND_CTX
    _BOUND_CTX = ctx


def _deps(kwargs: dict[str, Any]):
    override = kwargs.get("_deps")
    if override is not None:
        return override
    return make_deps(_BOUND_CTX)


def _dump(payload: dict[str, Any]) -> str:
    return json.dumps(payload, default=str)


def intents_list_tokens(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        return _dump(list_tokens(args or {}, _deps(kwargs)))
    except Exception as exc:  # noqa: BLE001 — tool handlers must not raise
        return _dump({"ok": False, "error": f"intents_list_tokens failed: {exc}", "funds_moved": False})


def intents_quote(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        return _dump(quote_payment(args or {}, _deps(kwargs)))
    except Exception as exc:  # noqa: BLE001
        return _dump({"ok": False, "error": f"intents_quote failed: {exc}", "funds_moved": False})


def intents_create_invoice(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        return _dump(create_invoice(args or {}, _deps(kwargs)))
    except Exception as exc:  # noqa: BLE001
        return _dump({"ok": False, "error": f"intents_create_invoice failed: {exc}", "funds_moved": False})


def intents_invoice_status(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        return _dump(payment_status(args or {}, _deps(kwargs)))
    except Exception as exc:  # noqa: BLE001
        return _dump({"ok": False, "error": f"intents_invoice_status failed: {exc}", "funds_moved": False})


def intents_verify_quote(args: dict[str, Any], **kwargs: Any) -> str:
    try:
        return _dump(verify_quote(args or {}, _deps(kwargs)))
    except Exception as exc:  # noqa: BLE001
        return _dump({"ok": False, "error": f"intents_verify_quote failed: {exc}", "funds_moved": False})


HANDLERS = {
    "intents_list_tokens": intents_list_tokens,
    "intents_quote": intents_quote,
    "intents_create_invoice": intents_create_invoice,
    "intents_invoice_status": intents_invoice_status,
    "intents_verify_quote": intents_verify_quote,
}
