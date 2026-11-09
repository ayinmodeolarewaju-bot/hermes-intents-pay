"""Invoice and quote operations shared by tools, the CLI, and the desktop API."""

from __future__ import annotations

import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from .client import OneClickError
from .render import is_final_status, render_summary, status_label
from .runtime import Deps
from .safety import (
    InputError,
    as_bool,
    dry_refund_placeholder,
    is_dry_placeholder,
    normalize_amount,
    normalize_near_account,
    parse_amount,
    refund_address_error,
    scan_for_secrets,
    to_base_units,
)
from .signing import verify_quote_signature
from .tokens import (
    REFERRAL,
    compact_token,
    chains_of,
    destination_for,
    find_by_asset_id,
    find_token,
    parse_currency,
)

_CONFIRM_TTL_SECONDS = 600
_QUOTE_HORIZON = timedelta(minutes=30)
_SLIPPAGE_MIN = 0
_SLIPPAGE_MAX = 2000
_ASSET_ID_PREFIXES = ("nep141:", "nep245:", "1cs_v1:")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _deadline(moment: datetime | None = None) -> str:
    stamp = (moment or _now()) + _QUOTE_HORIZON
    return stamp.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _error(message: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": False,
        "error": message,
        "funds_moved": False,
        "private_keys_handled": False,
    }
    payload.update(extra)
    return payload


def _verifier(deps: Deps):
    return deps.verify or verify_quote_signature


def list_tokens(args: dict[str, Any], deps: Deps) -> dict[str, Any]:
    try:
        scan_for_secrets(args)
        symbol = str(args.get("symbol") or "").strip()
        chain = str(args.get("chain") or args.get("blockchain") or "").strip().lower()
        include_all = as_bool(args.get("include_all"), default=False)
        limit = int(args.get("limit") or 40)
        limit = max(1, min(limit, 200))
    except (InputError, TypeError, ValueError) as exc:
        return _error(str(exc))

    try:
        tokens, live = _load_tokens(deps)
    except OneClickError as exc:
        return _error(str(exc))

    if symbol or chain:
        rows = []
        for token in tokens:
            if chain and str(token.get("blockchain") or "").lower() != chain:
                continue
            if symbol and not _symbol_ok(token, symbol):
                continue
            rows.append(compact_token(token))
        truncated = len(rows) > limit
        return {
            "ok": True,
            "live": live,
            "token_count": len(tokens),
            "match_count": len(rows),
            "truncated": truncated,
            "chains": chains_of(tokens),
            "tokens": rows[:limit],
            "funds_moved": False,
        }

    stables = [
        compact_token(token)
        for token in tokens
        if str(token.get("symbol") or "").upper() in {"USDC", "USDT", "USDT0", "WNEAR", "NEAR"}
    ]
    return {
        "ok": True,
        "live": live,
        "token_count": len(tokens),
        "chains": chains_of(tokens),
        "stables": stables[:limit] if not include_all else stables,
        "tokens": [compact_token(token) for token in tokens[:limit]] if include_all else [],
        "note": (
            "Pass symbol or chain to filter. Stablecoin and NEAR rows are included "
            "so a quote can be chosen without downloading every asset."
        ),
        "funds_moved": False,
    }


def _symbol_ok(token: dict[str, Any], symbol: str) -> bool:
    from .tokens import symbol_matches

    return symbol_matches(str(token.get("symbol") or ""), symbol)


def quote_payment(args: dict[str, Any], deps: Deps, *, kind: str = "quote") -> dict[str, Any]:
    try:
        scan_for_secrets(args)
        plan = _plan(args, deps)
    except InputError as exc:
        return _error(str(exc))
    except OneClickError as exc:
        return _error(str(exc))

    if plan["dry"]:
        return _execute(plan, deps, kind=kind, dry=True)

    if deps.unattended:
        return _error(
            "A live quote needs a person to confirm it. This run is unattended, so no deposit address was requested.",
            code="unattended",
        )
    refund_error = refund_address_error(plan["origin_chain"], plan["refund_to"])
    if refund_error:
        return _error(refund_error)
    if is_dry_placeholder(plan["refund_to"]):
        return _error(
            "That refund address is a public dry-run placeholder. Pass the payer's own refund address on the origin chain."
        )

    token = str(args.get("confirmation_token") or "").strip()
    confirmed = as_bool(args.get("confirm"), default=False)
    if not confirmed or not token:
        preview = _execute(plan, deps, kind=kind, dry=True, persist=False)
        if not preview.get("ok"):
            return preview
        issued = _issue_confirmation(deps, plan)
        preview["status"] = "confirmation_required"
        preview["confirmation_token"] = issued
        preview["confirmation_expires_in_seconds"] = _CONFIRM_TTL_SECONDS
        preview["dry"] = True
        preview["deposit_address"] = None
        preview["next_step"] = (
            "Show this dry preview to the user. A live deposit address is created only "
            "after they explicitly agree. Then call this tool again with the same "
            "payment fields, confirm=true, confirmation_token, and refund_to. "
            "Intents Pay still will not send the funds."
        )
        preview["summary"] = render_summary({**preview, "dry": True, "deposit_address": None})
        return preview

    pending = _take_confirmation(deps, token, plan)
    if pending is not None:
        return pending
    return _execute(plan, deps, kind=kind, dry=False)


def create_invoice(args: dict[str, Any], deps: Deps) -> dict[str, Any]:
    return quote_payment(args, deps, kind="invoice")


def payment_status(args: dict[str, Any], deps: Deps) -> dict[str, Any]:
    try:
        scan_for_secrets(args)
    except InputError as exc:
        return _error(str(exc))

    invoice_id = str(args.get("invoice_id") or args.get("id") or "").strip()
    deposit_address = str(args.get("deposit_address") or "").strip()
    deposit_memo = str(args.get("deposit_memo") or "").strip() or None

    if not invoice_id and not deposit_address:
        return _list_invoices(deps)

    record = _find_invoice(deps, invoice_id) if invoice_id else None
    if invoice_id and record is None:
        return _error(f"No saved invoice with id {invoice_id}")
    if record and not deposit_address:
        deposit_address = str(record.get("deposit_address") or "")
        deposit_memo = deposit_memo or record.get("deposit_memo")

    if not deposit_address:
        summary = render_summary(record or {})
        return {
            "ok": True,
            "invoice": _public_record(record or {}),
            "status": "DRY_QUOTE",
            "status_label": "Dry quote only. There is no deposit to track.",
            "final": False,
            "summary": summary,
            "funds_moved": False,
        }

    try:
        raw = deps.client.get_status(deposit_address, deposit_memo)
    except OneClickError as exc:
        return _error(str(exc), deposit_address=deposit_address)

    status = str(raw.get("status") or "")
    update = {
        "payment_status": status,
        "status_label": status_label(status),
        "final": is_final_status(status),
        "status_updated_at": raw.get("updatedAt"),
        "correlation_id": raw.get("correlationId"),
    }
    if record:
        record = _update_invoice(deps, record["id"], update)
    result = {
        "ok": True,
        "status": status,
        "status_label": status_label(status),
        "final": is_final_status(status),
        "updated_at": raw.get("updatedAt"),
        "correlation_id": raw.get("correlationId"),
        "deposit_address": deposit_address,
        "deposit_memo": deposit_memo,
        "swap_details": raw.get("swapDetails"),
        "funds_moved": False,
        "note": "Status is read from 1-Click. Intents Pay does not submit or send a deposit.",
    }
    if record:
        result["invoice"] = _public_record(record)
        result["summary"] = render_summary(record)
    return result


def verify_quote(args: dict[str, Any], deps: Deps) -> dict[str, Any]:
    try:
        scan_for_secrets(args)
    except InputError as exc:
        return _error(str(exc))

    payload = args.get("quote") or args.get("quote_response")
    invoice_id = str(args.get("invoice_id") or "").strip()
    if payload is None and invoice_id:
        record = _find_invoice(deps, invoice_id)
        if record is None:
            return _error(f"No saved invoice with id {invoice_id}")
        payload = record.get("raw_quote")
    if not isinstance(payload, dict):
        return _error("Pass quote (the full 1-Click quote response) or invoice_id.")

    valid = bool(_verifier(deps)(payload))
    quote = payload.get("quote") if isinstance(payload.get("quote"), dict) else {}
    deposit = quote.get("depositAddress") if valid else None
    return {
        "ok": True,
        "signature_valid": valid,
        "deposit_address": deposit,
        "deposit_address_withheld": bool(quote.get("depositAddress")) and not valid,
        "correlation_id": payload.get("correlationId"),
        "timestamp": payload.get("timestamp"),
        "algorithm": "ed25519 over base58(sha256(canonical quote JSON)), 1-Click manager public key",
        "funds_moved": False,
        "warning": None
        if valid
        else "Signature check failed. Do not send funds to any deposit address in this payload.",
    }


def _load_tokens(deps: Deps) -> tuple[list[dict[str, Any]], bool]:
    from .tokens import FALLBACK_TOKENS

    try:
        return deps.client.get_tokens(), True
    except OneClickError:
        return list(FALLBACK_TOKENS), False


def _plan(args: dict[str, Any], deps: Deps) -> dict[str, Any]:
    settings = deps.settings
    currency = parse_currency(args.get("currency") or args.get("pay_currency") or "USDC")
    if currency not in {"USDC", "USDT", "NEAR"}:
        raise InputError("currency must be USDC, USDT, or NEAR")
    amount_human = normalize_amount(args.get("amount"))
    amount = parse_amount(amount_human)
    recipient = normalize_near_account(
        args.get("recipient") or args.get("payout_account") or settings.default_recipient
    )
    memo = str(args.get("memo") or "").strip()
    if len(memo) > 280:
        raise InputError("memo must be 280 characters or fewer")
    swap_type = str(args.get("swap_type") or "EXACT_OUTPUT").strip().upper()
    if swap_type not in {"EXACT_OUTPUT", "EXACT_INPUT"}:
        raise InputError("swap_type must be EXACT_OUTPUT or EXACT_INPUT")
    slippage = args.get("slippage_bps", settings.slippage_bps)
    try:
        slippage_bps = int(slippage)
    except (TypeError, ValueError) as exc:
        raise InputError("slippage_bps must be an integer") from exc
    if slippage_bps < _SLIPPAGE_MIN or slippage_bps > _SLIPPAGE_MAX:
        raise InputError(f"slippage_bps must be between {_SLIPPAGE_MIN} and {_SLIPPAGE_MAX}")

    pay_from = str(args.get("pay_from") or args.get("payer_symbol") or "").strip()
    origin_chain = str(args.get("origin_chain") or args.get("payer_chain") or "").strip().lower()
    origin_asset = str(args.get("origin_asset") or "").strip()
    if origin_asset and not origin_asset.startswith(_ASSET_ID_PREFIXES):
        raise InputError("origin_asset must be a 1-Click asset id (nep141:, nep245:, or 1cs_v1:)")

    if not pay_from and not origin_asset:
        pay_from = "USDC" if currency == "NEAR" else currency
    if not origin_chain and not origin_asset:
        origin_chain = "near" if pay_from.upper() in {"NEAR", "WNEAR"} else "arb"

    dry = as_bool(args.get("dry"), default=True)
    refund_to = str(args.get("refund_to") or args.get("refund_address") or "").strip()

    tokens, live_tokens = _load_tokens(deps)
    dest_symbol, dest_chain = destination_for(currency)
    destination = find_token(tokens, dest_symbol, dest_chain)
    if destination is None:
        raise InputError(f"1-Click has no {currency} payout asset on NEAR right now.")

    if origin_asset:
        origin = find_by_asset_id(tokens, origin_asset)
        if origin is None:
            raise InputError(f"origin_asset {origin_asset} is not in the 1-Click token list")
    else:
        origin = find_token(tokens, pay_from, origin_chain)
        if origin is None:
            raise InputError(
                f"No {pay_from} asset on {origin_chain}. "
                "Call intents_list_tokens with that symbol or chain to see supported ids."
            )

    resolved_chain = str(origin.get("blockchain") or origin_chain)
    if dry and not refund_to:
        placeholder = dry_refund_placeholder(resolved_chain, recipient)
        if not placeholder:
            raise InputError(
                "Dry quotes on this chain still need refund_to so 1-Click can validate the address format. "
                "No deposit is created and the address is not charged."
            )
        refund_to = placeholder
        refund_is_placeholder = True
    else:
        refund_is_placeholder = False
    if not dry and not refund_to:
        raise InputError(
            "A live quote requires refund_to, the payer's own address on the origin chain. "
            "Nothing is sent yet, but 1-Click needs a refund target before it will mint a deposit address."
        )

    priced = origin if swap_type == "EXACT_INPUT" else destination
    base_amount = to_base_units(amount, int(priced.get("decimals") or 0))
    return {
        "kind_currency": currency,
        "amount_human": amount_human,
        "amount": amount,
        "base_amount": base_amount,
        "recipient": recipient,
        "memo": memo,
        "swap_type": swap_type,
        "slippage_bps": slippage_bps,
        "dry": dry,
        "refund_to": refund_to,
        "refund_is_placeholder": refund_is_placeholder,
        "origin": origin,
        "destination": destination,
        "origin_chain": resolved_chain,
        "pay_from_symbol": str(origin.get("symbol")),
        "live_tokens": live_tokens,
        "canonical": {
            "amount": amount_human,
            "currency": currency,
            "recipient": recipient,
            "memo": memo,
            "swap_type": swap_type,
            "slippage_bps": slippage_bps,
            "refund_to": refund_to,
            "origin_asset": origin.get("assetId"),
            "destination_asset": destination.get("assetId"),
            "base_amount": base_amount,
        },
    }


def _quote_body(plan: dict[str, Any], *, dry: bool) -> dict[str, Any]:
    return {
        "dry": dry,
        "swapType": plan["swap_type"],
        "slippageTolerance": plan["slippage_bps"],
        "originAsset": plan["origin"]["assetId"],
        "depositType": "ORIGIN_CHAIN",
        "destinationAsset": plan["destination"]["assetId"],
        "amount": plan["base_amount"],
        "recipient": plan["recipient"],
        "recipientType": "DESTINATION_CHAIN",
        "refundTo": plan["refund_to"],
        "refundType": "ORIGIN_CHAIN",
        "deadline": _deadline(),
        "referral": REFERRAL,
    }


def _execute(plan: dict[str, Any], deps: Deps, *, kind: str, dry: bool, persist: bool = True) -> dict[str, Any]:
    body = _quote_body(plan, dry=dry)
    try:
        raw = deps.client.request_quote(body)
    except OneClickError as exc:
        return _error(str(exc))

    valid = bool(_verifier(deps)(raw))
    quote = raw.get("quote") if isinstance(raw.get("quote"), dict) else {}
    deposit_address = quote.get("depositAddress") if (not dry and valid) else None
    if not dry and not valid:
        return _error(
            "1-Click returned a live quote whose signature did not verify. The deposit address was withheld.",
            signature_valid=False,
            correlation_id=raw.get("correlationId"),
            funds_moved=False,
        )

    record = _record_from_quote(plan, raw, kind=kind, dry=dry, valid=valid, deposit_address=deposit_address)
    if persist:
        saved = _save_invoice(deps, record)
    else:
        saved = record
    public = _public_record(saved)
    public["ok"] = True
    public["summary"] = render_summary(public)
    public["live_tokens"] = plan["live_tokens"]
    if dry and plan["refund_is_placeholder"]:
        public["refund_note"] = (
            "Dry run used a public placeholder refund address so 1-Click could check the format. "
            "It is not the payer's address and no deposit was created."
        )
    return public


def _record_from_quote(
    plan: dict[str, Any],
    raw: dict[str, Any],
    *,
    kind: str,
    dry: bool,
    valid: bool,
    deposit_address: str | None,
) -> dict[str, Any]:
    quote = raw.get("quote") if isinstance(raw.get("quote"), dict) else {}
    now = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    identifier = "ip_" + uuid.uuid4().hex[:12]
    number = "IP-" + _now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4].upper()
    return {
        "id": identifier,
        "number": number,
        "kind": kind,
        "created_at": now,
        "amount": plan["amount_human"],
        "currency": plan["kind_currency"],
        "recipient": plan["recipient"],
        "memo": plan["memo"],
        "swap_type": plan["swap_type"],
        "slippage_bps": plan["slippage_bps"],
        "pay_from_symbol": plan["pay_from_symbol"],
        "origin_chain": plan["origin_chain"],
        "origin_asset": plan["origin"].get("assetId"),
        "destination_asset": plan["destination"].get("assetId"),
        "amount_in": quote.get("amountIn"),
        "amount_in_formatted": quote.get("amountInFormatted"),
        "amount_in_usd": quote.get("amountInUsd"),
        "amount_out": quote.get("amountOut"),
        "amount_out_formatted": quote.get("amountOutFormatted"),
        "amount_out_usd": quote.get("amountOutUsd"),
        "min_amount_out": quote.get("minAmountOut"),
        "time_estimate": quote.get("timeEstimate"),
        "deadline": None if dry else quote.get("deadline"),
        "dry": dry,
        "deposit_address": deposit_address,
        "deposit_memo": quote.get("depositMemo") if deposit_address else None,
        "signature_valid": valid,
        "correlation_id": raw.get("correlationId"),
        "timestamp": raw.get("timestamp"),
        "signature": raw.get("signature"),
        "payment_status": "DRY_QUOTE" if dry else "PENDING_DEPOSIT",
        "funds_moved": False,
        "raw_quote": raw,
    }


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    hidden = {"raw_quote"}
    public = {key: value for key, value in record.items() if key not in hidden}
    public["funds_moved"] = False
    public["private_keys_handled"] = False
    return public


def _save_invoice(deps: Deps, record: dict[str, Any]) -> dict[str, Any]:
    def mutate(data: dict[str, Any]) -> dict[str, Any]:
        data.setdefault("invoices", []).append(record)
        return record

    return deps.ledger.update(mutate)


def _update_invoice(deps: Deps, invoice_id: str, fields: dict[str, Any]) -> dict[str, Any] | None:
    found: dict[str, Any] | None = None

    def mutate(data: dict[str, Any]) -> None:
        nonlocal found
        for record in data.get("invoices") or []:
            if record.get("id") == invoice_id or record.get("number") == invoice_id:
                record.update(fields)
                found = record
                return

    deps.ledger.update(mutate)
    return found


def _find_invoice(deps: Deps, invoice_id: str) -> dict[str, Any] | None:
    data = deps.ledger.read()
    for record in data.get("invoices") or []:
        if record.get("id") == invoice_id or record.get("number") == invoice_id:
            return record
    return None


def _list_invoices(deps: Deps) -> dict[str, Any]:
    data = deps.ledger.read()
    rows = []
    for record in reversed(data.get("invoices") or []):
        rows.append(
            {
                "id": record.get("id"),
                "number": record.get("number"),
                "kind": record.get("kind"),
                "amount": record.get("amount"),
                "currency": record.get("currency"),
                "recipient": record.get("recipient"),
                "dry": record.get("dry"),
                "payment_status": record.get("payment_status"),
                "created_at": record.get("created_at"),
                "deposit_address": record.get("deposit_address"),
            }
        )
        if len(rows) >= 20:
            break
    return {
        "ok": True,
        "invoices": rows,
        "note": "Pass invoice_id or deposit_address to read 1-Click status.",
        "funds_moved": False,
    }


def _issue_confirmation(deps: Deps, plan: dict[str, Any]) -> str:
    token = secrets.token_urlsafe(18)
    expires = time.time() + _CONFIRM_TTL_SECONDS

    def mutate(data: dict[str, Any]) -> None:
        pending = data.setdefault("pending", {})
        _prune_pending(pending)
        pending[token] = {"expires": expires, "canonical": plan["canonical"]}

    deps.ledger.update(mutate)
    return token


def _take_confirmation(deps: Deps, token: str, plan: dict[str, Any]) -> dict[str, Any] | None:
    """Return an error dict when the token cannot be used. None means it was consumed."""
    error: dict[str, Any] | None = None

    def mutate(data: dict[str, Any]) -> None:
        nonlocal error
        pending = data.setdefault("pending", {})
        _prune_pending(pending)
        entry = pending.get(token)
        if not isinstance(entry, dict):
            error = _error(
                "Unknown confirmation token. Request the preview again and use the token it returns.",
                code="confirmation_required",
            )
            return
        if entry.get("canonical") != plan["canonical"]:
            error = _error(
                "That confirmation token belongs to a different amount, asset, recipient, or refund address. "
                "Request a new preview.",
                code="confirmation_mismatch",
            )
            return
        pending.pop(token, None)

    deps.ledger.update(mutate)
    return error


def _prune_pending(pending: dict[str, Any]) -> None:
    now = time.time()
    expired = [
        key
        for key, value in pending.items()
        if not isinstance(value, dict) or float(value.get("expires") or 0) < now
    ]
    for key in expired:
        pending.pop(key, None)
