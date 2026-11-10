"""Hermes approval gate for payable Intents Pay tool calls.

``pre_tool_call`` runs before the tool handler. Returning
``{"action": "approve", ...}`` escalates that call to Hermes's human-approval
prompt. Denial, timeout, and gate errors fail closed inside Hermes, so the
handler does not run.

Read-only tools (token list, dry quote, status, signature check) return no
directive. A quote becomes payable when ``dry`` is false, because that asks
1-Click for a deposit address. Creating an invoice is always treated as a
payable request.
"""

from __future__ import annotations

from typing import Any

from .safety import as_bool

# Tools that can create a payable request or a deposit address.
PAYABLE_TOOLS = frozenset({"intents_create_invoice", "intents_quote"})


def _is_dry(args: dict[str, Any]) -> bool:
    try:
        return as_bool(args.get("dry"), default=True)
    except Exception:
        # An unreadable flag is treated as payable so the call cannot skip the prompt.
        return False


def approval_directive(tool_name: str, args: dict[str, Any] | None) -> dict[str, str] | None:
    """Return Hermes's approve directive, or None when the call is read-only."""
    payload = args if isinstance(args, dict) else {}
    if tool_name == "intents_create_invoice" or (
        tool_name == "intents_quote" and not _is_dry(payload)
    ):
        recipient = str(payload.get("recipient") or payload.get("payout_account") or "").strip()
        who = f" to {recipient}" if recipient else ""
        return {
            "action": "approve",
            "message": (
                f"Intents Pay is about to create a payable {tool_name} request{who}. "
                "Nothing is broadcast by the plugin, but a deposit address or invoice can be used to send funds. "
                "Approve only if this recipient is the one you named."
            ),
            "rule_key": f"intents-pay:{tool_name}",
        }
    return None


def pre_tool_call(tool_name: str, args: dict | None = None, task_id: str = "", **kwargs: Any):
    """``pre_tool_call`` callback. Hermes ignores a None return."""
    return approval_directive(tool_name, args if isinstance(args, dict) else {})
