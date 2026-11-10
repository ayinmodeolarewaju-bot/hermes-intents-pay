"""Slash command and ``hermes intents-pay`` CLI. Both stay on the dry-quote path unless the CLI repeats a confirmation token."""

from __future__ import annotations

import argparse
import json
from typing import Any

from .runtime import make_deps
from .service import create_invoice, list_tokens, payment_status, quote_payment


def parse_slash(raw: str) -> tuple[str, dict[str, Any]] | tuple[None, str]:
    """Parse ``/intents`` text into ``(action, args)`` or ``(None, usage)``."""
    parts = (raw or "").strip().split()
    if not parts or parts[0] in {"help", "-h", "--help"}:
        return None, _usage()
    action = parts[0].lower()
    rest = parts[1:]
    if action == "tokens":
        args: dict[str, Any] = {}
        if rest:
            args["symbol"] = rest[0]
        if len(rest) > 1:
            args["chain"] = rest[1]
        return "tokens", args
    if action == "status":
        if not rest:
            return "status", {}
        token = rest[0]
        if token.startswith("0x") or len(token) > 48:
            return "status", {"deposit_address": token}
        return "status", {"invoice_id": token}
    if action in {"quote", "invoice"}:
        if not rest:
            return None, _usage()
        args = {"amount": rest[0], "dry": True}
        index = 1
        if index < len(rest) and rest[index].upper() in {"USDC", "USDT", "NEAR"}:
            args["currency"] = rest[index].upper()
            index += 1
        while index < len(rest):
            word = rest[index].lower()
            if word == "from" and index + 1 < len(rest):
                args["origin_chain"] = rest[index + 1]
                index += 2
                if index < len(rest) and rest[index].lower() not in {"to", "memo"}:
                    args["pay_from"] = rest[index]
                    index += 1
                continue
            if word == "to" and index + 1 < len(rest):
                args["recipient"] = rest[index + 1]
                index += 2
                continue
            if word == "memo":
                args["memo"] = " ".join(rest[index + 1 :])
                break
            return None, _usage()
        if not args.get("recipient"):
            return None, (
                "A recipient NEAR account is required. "
                "Example: /intents quote 25 USDC from arb to name.near"
            )
        return action, args
    return None, _usage()


def _usage() -> str:
    return (
        "Usage:\n"
        "/intents tokens [SYMBOL] [CHAIN]\n"
        "/intents quote AMOUNT [USDC|USDT|NEAR] from CHAIN [TOKEN] to ACCOUNT memo TEXT\n"
        "/intents invoice AMOUNT [USDC|USDT|NEAR] to ACCOUNT memo TEXT\n"
        "ACCOUNT is required. There is no default recipient.\n"
        "/intents status [INVOICE_ID]\n"
        "Slash commands are dry-run only. They never create a deposit address."
    )


def slash_command(raw_args: str, **kwargs: Any) -> str:
    parsed = parse_slash(raw_args)
    if parsed[0] is None:
        return str(parsed[1])
    action, args = parsed
    deps = kwargs.get("_deps") or make_deps(kwargs.get("ctx"))
    if action == "tokens":
        result = list_tokens(args, deps)
    elif action == "quote":
        result = quote_payment(args, deps, kind="quote")
    elif action == "invoice":
        result = create_invoice(args, deps)
    else:
        result = payment_status(args, deps)
    summary = result.get("summary")
    if summary:
        return str(summary)
    return json.dumps(result, indent=2, default=str)


def setup_cli(subparser: argparse.ArgumentParser) -> None:
    commands = subparser.add_subparsers(dest="intents_action")
    quote = commands.add_parser("quote", help="Dry-run quote, or a confirmed live quote")
    quote.add_argument("--amount", required=True)
    quote.add_argument("--currency", default="USDC")
    quote.add_argument("--from-chain", default="arb")
    quote.add_argument("--from-token", default=None)
    quote.add_argument("--recipient", required=True, help="NEAR account that receives the payment. Required.")
    quote.add_argument("--memo", default="")
    quote.add_argument("--live", action="store_true", help="Request a deposit address. Requires --refund-to and a prior token.")
    quote.add_argument("--refund-to", default=None)
    quote.add_argument("--confirm-token", default=None)
    tokens = commands.add_parser("tokens", help="List 1-Click tokens")
    tokens.add_argument("--symbol", default=None)
    tokens.add_argument("--chain", default=None)
    status = commands.add_parser("status", help="List invoices or check a deposit")
    status.add_argument("--invoice", default=None)
    status.add_argument("--deposit-address", default=None)
    subparser.set_defaults(func=handle_cli)


def handle_cli(args: argparse.Namespace) -> None:
    action = getattr(args, "intents_action", None)
    deps = make_deps()
    if action == "tokens":
        result = list_tokens({"symbol": args.symbol, "chain": args.chain}, deps)
    elif action == "quote":
        payload: dict[str, Any] = {
            "amount": args.amount,
            "currency": args.currency,
            "origin_chain": args.from_chain,
            "memo": args.memo,
            "dry": not args.live,
        }
        if args.from_token:
            payload["pay_from"] = args.from_token
        payload["recipient"] = args.recipient
        if args.refund_to:
            payload["refund_to"] = args.refund_to
        if args.confirm_token:
            payload["confirmation_token"] = args.confirm_token
            payload["confirm"] = True
        result = quote_payment(payload, deps, kind="quote")
    elif action == "status":
        result = payment_status(
            {"invoice_id": args.invoice, "deposit_address": args.deposit_address},
            deps,
        )
    else:
        print(
            "Usage: hermes intents-pay quote --amount 10 [--currency USDC] [--from-chain arb]\n"
            "       hermes intents-pay tokens [--symbol USDC] [--chain arb]\n"
            "       hermes intents-pay status [--invoice ID]"
        )
        return
    summary = result.get("summary")
    if summary:
        print(summary)
        if result.get("confirmation_token"):
            print("\nconfirmation_token:", result["confirmation_token"])
            print("Re-run with --live --refund-to YOUR_ADDRESS --confirm-token", result["confirmation_token"])
        return
    print(json.dumps(result, indent=2, default=str))
