"""Plain-text invoice cards the agent can paste into chat."""

from __future__ import annotations

from typing import Any

_STATUS_LABELS = {
    "PENDING_DEPOSIT": "Waiting for the payer to send funds",
    "KNOWN_DEPOSIT_TX": "Deposit transaction seen",
    "INCOMPLETE_DEPOSIT": "Deposit is short of the quoted amount",
    "PROCESSING": "Swap in progress",
    "SUCCESS": "Payment settled",
    "REFUNDED": "Funds were refunded to the refund address",
    "FAILED": "Swap failed",
}


def status_label(status: str | None) -> str:
    if not status:
        return "Unknown"
    return _STATUS_LABELS.get(status, status.replace("_", " ").title())


def is_final_status(status: str | None) -> bool:
    return status in {"SUCCESS", "REFUNDED", "FAILED"}


def render_summary(record: dict[str, Any]) -> str:
    """Shareable card. Dry cards never include a deposit address."""
    number = record.get("number") or record.get("id") or "quote"
    lines = [
        f"Intents Pay {number}",
        f"Due: {record.get('amount')} {record.get('currency')} to {record.get('recipient')}",
    ]
    if record.get("memo"):
        lines.append(f"Memo: {record['memo']} (invoice note only, not sent on-chain)")
    lines.append(
        f"Pay with: {record.get('pay_from_symbol')} on {record.get('origin_chain')}"
    )
    if record.get("amount_in_formatted"):
        usd = record.get("amount_in_usd")
        usd_bit = f" (about ${usd})" if usd else ""
        lines.append(
            f"Payer sends about: {record['amount_in_formatted']} {record.get('pay_from_symbol')}{usd_bit}"
        )
    if record.get("amount_out_formatted"):
        lines.append(
            f"Recipient gets: {record['amount_out_formatted']} {record.get('currency')}"
        )
    if record.get("time_estimate"):
        lines.append(f"Estimated settlement after deposit: {record['time_estimate']}s")
    if record.get("dry", True):
        lines.append("Quote: dry run. No deposit address was created. No funds can be sent.")
    else:
        lines.append(
            f"Deposit on {record.get('origin_chain')}: {record.get('deposit_address')}"
        )
        if record.get("deposit_memo"):
            lines.append(f"Deposit memo (required): {record['deposit_memo']}")
        if record.get("deadline"):
            lines.append(f"Deposit deadline: {record['deadline']}")
        lines.append(
            "Intents Pay did not move funds. The payer sends this from their own wallet."
        )
    signature = record.get("signature_valid")
    if signature is True:
        lines.append("1-Click signature: verified.")
    elif signature is False:
        lines.append("1-Click signature: FAILED. Do not send funds against this quote.")
    lines.append("Safety: this plugin never asks for a seed phrase or signing key.")
    return "\n".join(lines)
