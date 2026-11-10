"""Input checks that keep Intents Pay from handling secrets or moving funds.

Live (non-dry) quotes are the only 1-Click call that allocates a deposit
address. They still do not broadcast a transfer. The caller must present a
one-time confirmation token that this plugin issued for the same payment,
plus the payer's own refund address.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

# Public addresses used only so a dry quote satisfies 1-Click's format check.
# They are never substituted into a live quote. Same placeholders as the
# invoice-link live dry-run script. A dry quote does not create a deposit.
EVM_DRY_PLACEHOLDER = "0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045"
SOL_DRY_PLACEHOLDER = "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM"
EVM_CHAINS = {
    "eth",
    "arb",
    "base",
    "op",
    "pol",
    "bsc",
    "avax",
    "gnosis",
    "bera",
    "scroll",
    "xlayer",
    "monad",
    "plasma",
    "adi",
}
_DRY_PLACEHOLDERS = {EVM_DRY_PLACEHOLDER.lower(), SOL_DRY_PLACEHOLDER}

_NEAR_ACCOUNT = re.compile(r"^(?=.{2,64}$)(([a-z\d]+[-_])*[a-z\d]+\.)*([a-z\d]+[-_])*[a-z\d]+$")
_NEAR_IMPLICIT = re.compile(r"^[0-9a-f]{64}$")
_EVM = re.compile(r"^0x[0-9a-fA-F]{40}$")
_B58 = "1-9A-HJ-NP-Za-km-z"
_SOL = re.compile(rf"^[{_B58}]{{32,44}}$")
_TRON = re.compile(rf"^T[{_B58}]{{33}}$")
_TON = re.compile(r"^(?:[EUk0][Qf][A-Za-z0-9_-]{46}|-?[01]:[0-9a-fA-F]{64})$")
_BTC = re.compile(rf"^(?:bc1[02-9ac-hj-np-z]{{11,71}}|[13][{_B58}]{{25,34}})$")
_SEED = re.compile(r"^[a-z]+(?: [a-z]+){11}$|^[a-z]+(?: [a-z]+){23}$")
_LONG_ED25519 = re.compile(rf"^ed25519:[{_B58}]{{70,}}$")
_PEM = re.compile(r"-----BEGIN [A-Z ]+-----")
_SECRET_WORDS = re.compile(
    r"(seed phrase|recovery phrase|mnemonic|private key|secret key|wallet key)",
    re.IGNORECASE,
)


class InputError(ValueError):
    """A caller-facing validation error. Safe to return as tool JSON."""


def is_near_account(account_id: str) -> bool:
    text = account_id.strip().lower()
    return bool(_NEAR_IMPLICIT.fullmatch(text) or _NEAR_ACCOUNT.fullmatch(text))


def normalize_near_account(account_id: str) -> str:
    text = str(account_id or "").strip().lower()
    if not is_near_account(text):
        raise InputError(
            f"{account_id!r} is not a NEAR account id. "
            "Use a name like name.near or a 64-character hex implicit account."
        )
    return text


def parse_amount(raw: Any) -> Decimal:
    if isinstance(raw, bool) or raw is None:
        raise InputError("amount is required")
    text = str(raw).strip().replace(",", "").replace("_", "")
    if not text or text.startswith("-") or text.startswith("+"):
        raise InputError("amount must be a positive number such as 10 or 10.50")
    try:
        value = Decimal(text)
    except InvalidOperation as exc:
        raise InputError("amount must be a positive number such as 10 or 10.50") from exc
    if not value.is_finite() or value <= 0:
        raise InputError("amount must be a positive number such as 10 or 10.50")
    return value


def normalize_amount(raw: Any) -> str:
    value = parse_amount(raw)
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def to_base_units(amount: Decimal, decimals: int) -> str:
    if decimals < 0 or decimals > 36:
        raise InputError(f"unsupported token decimals: {decimals}")
    scaled = amount * (Decimal(10) ** decimals)
    if scaled != scaled.to_integral_value():
        raise InputError(
            f"amount {amount} has more decimal places than this token allows ({decimals})"
        )
    return str(int(scaled))


def as_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off", ""}:
        return False
    raise InputError(f"expected true or false, got {value!r}")


def refund_address_error(chain: str, address: str) -> str | None:
    """Return an error string when ``address`` does not match ``chain``, else None."""
    chain_id = (chain or "").strip().lower()
    text = (address or "").strip()
    if not text:
        return f"Enter a {chain_id or 'refund'} address so a failed swap can be refunded."
    if chain_id in EVM_CHAINS:
        ok = bool(_EVM.fullmatch(text))
        hint = "a 0x address with 40 hex characters"
    elif chain_id == "near":
        ok = is_near_account(text.lower())
        hint = "a NEAR account like name.near"
    elif chain_id == "sol":
        ok = bool(_SOL.fullmatch(text))
        hint = "a base58 Solana address (32–44 characters)"
    elif chain_id == "tron":
        ok = bool(_TRON.fullmatch(text))
        hint = "a Tron address starting with T"
    elif chain_id == "ton":
        ok = bool(_TON.fullmatch(text))
        hint = "a TON address like UQ… or EQ…"
    elif chain_id == "btc":
        ok = bool(_BTC.fullmatch(text))
        hint = "a Bitcoin address (bc1…, 1…, or 3…)"
    else:
        return None
    if ok:
        return None
    label = chain_id.upper() if chain_id else "that chain"
    return f"That doesn't look like a valid {label} refund address. Expected {hint}."


def dry_refund_placeholder(chain: str, recipient: str) -> str | None:
    """Public placeholder for a dry quote, or None when the chain is unknown."""
    chain_id = (chain or "").strip().lower()
    if chain_id in EVM_CHAINS:
        return EVM_DRY_PLACEHOLDER
    if chain_id == "sol":
        return SOL_DRY_PLACEHOLDER
    if chain_id == "near":
        return recipient
    return None


def is_dry_placeholder(address: str) -> bool:
    text = (address or "").strip()
    return text.lower() in _DRY_PLACEHOLDERS or text == EVM_DRY_PLACEHOLDER


def secret_material_error(value: str) -> str | None:
    """Refuse strings that look like a seed phrase, PEM block, or signing key."""
    text = value.strip()
    if not text:
        return None
    if _PEM.search(text) or _SECRET_WORDS.search(text) or _LONG_ED25519.match(text):
        return (
            "Intents Pay does not accept seed phrases or signing keys. "
            "Remove that value and send only a public account address."
        )
    if _SEED.fullmatch(text):
        return (
            "That value looks like a 12- or 24-word seed phrase. "
            "Intents Pay never accepts one. Rephrase the memo, or drop the field."
        )
    return None


def scan_for_secrets(value: Any, *, field: str = "input") -> None:
    if isinstance(value, str):
        error = secret_material_error(value)
        if error:
            raise InputError(f"{field}: {error}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            scan_for_secrets(item, field=str(key))
        return
    if isinstance(value, list):
        for item in value:
            scan_for_secrets(item, field=field)
