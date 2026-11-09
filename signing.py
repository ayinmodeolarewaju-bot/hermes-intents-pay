"""Verify NEAR Intents 1-Click quote signatures locally.

The algorithm matches ``verifyQuoteSignature`` in
``@defuse-protocol/one-click-sdk-typescript`` (the public 1-Click manager key).
The signed message is a base58-encoded SHA-256 of a canonical JSON object.
Ed25519 is checked over the UTF-8 bytes of that base58 string.

This module holds a public verification key only. It cannot sign quotes and it
never sees a wallet key.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_INDEX = {char: index for index, char in enumerate(_ALPHABET)}

# Public key published by the 1-Click TypeScript SDK. Not a secret.
ONE_CLICK_MANAGER_PUB_KEY = "ed25519:reYaWhvwu8Jzo3WUM3zhn6VrhuMEF4eADL17qtRVifc"
_ED25519_PREFIX = "ed25519:"

_REQUEST_KEYS = (
    "dry",
    "swapType",
    "slippageTolerance",
    "originAsset",
    "depositType",
    "destinationAsset",
    "amount",
    "refundTo",
    "refundType",
    "recipient",
    "recipientType",
    "deadline",
)
_OPTIONAL_REQUEST_KEYS = (
    "quoteWaitingTimeMs",
    "referral",
    "virtualChainRecipient",
    "virtualChainRefundRecipient",
    "customRecipientMsg",
)
_DRY_QUOTE_KEYS = (
    "amountIn",
    "amountInFormatted",
    "amountInUsd",
    "minAmountIn",
    "amountOut",
    "amountOutFormatted",
    "amountOutUsd",
    "minAmountOut",
)
_FULL_QUOTE_KEYS = _DRY_QUOTE_KEYS + (
    "depositAddress",
    "depositMemo",
    "deadline",
    "timeWhenInactive",
    "timeEstimate",
    "refundFee",
    "withdrawFee",
)


def b58encode(data: bytes) -> str:
    """Encode bytes as Bitcoin base58 (no checksum)."""
    number = int.from_bytes(data, "big")
    characters: list[str] = []
    while number:
        number, remainder = divmod(number, 58)
        characters.append(_ALPHABET[remainder])
    padding = 0
    for byte in data:
        if byte == 0:
            padding += 1
        else:
            break
    body = "".join(reversed(characters)) if characters else ""
    return ("1" * padding) + body


def b58decode(text: str) -> bytes:
    """Decode Bitcoin base58 (no checksum)."""
    number = 0
    for char in text:
        try:
            digit = _INDEX[char]
        except KeyError as exc:
            raise ValueError(f"invalid base58 character: {char!r}") from exc
        number = number * 58 + digit
    padding = 0
    for char in text:
        if char == "1":
            padding += 1
        else:
            break
    raw = number.to_bytes((number.bit_length() + 7) // 8, "big") if number else b""
    return (b"\x00" * padding) + raw


def _js_number(value: Any) -> Any:
    """Match JSON.stringify: integral floats become integers (``1`` not ``1.0``)."""
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _js_number(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_js_number(item) for item in value]
    return value


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialize the way ``json-stable-stringify`` does: sorted keys, no spaces."""
    return json.dumps(
        _js_number(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def _truthy(value: Any) -> bool:
    """JavaScript truthiness for the SDK's ``value ? value : undefined`` checks."""
    if value is None or value is False:
        return False
    if value == 0 or value == "" or value == [] or value == {}:
        return False
    return True


def signed_payload(response: dict[str, Any]) -> dict[str, Any]:
    """Build the exact object the 1-Click manager signs."""
    request = response.get("quoteRequest")
    quote = response.get("quote")
    if not isinstance(request, dict) or not isinstance(quote, dict):
        raise ValueError("quote response is missing quoteRequest or quote")
    timestamp = response.get("timestamp")
    if not isinstance(timestamp, str) or not timestamp:
        raise ValueError("quote response is missing timestamp")

    payload: dict[str, Any] = {}
    for key in _REQUEST_KEYS:
        if key not in request:
            raise ValueError(f"quote request is missing {key}")
        payload[key] = request[key]
    for key in _OPTIONAL_REQUEST_KEYS:
        if _truthy(request.get(key)):
            payload[key] = request[key]

    dry = bool(request.get("dry"))
    quote_keys = _DRY_QUOTE_KEYS if dry else _FULL_QUOTE_KEYS
    for key in quote_keys:
        if dry:
            if key not in quote:
                raise ValueError(f"quote is missing {key}")
            payload[key] = quote[key]
        elif _truthy(quote.get(key)):
            payload[key] = quote[key]
    payload["timestamp"] = timestamp
    return payload


def quote_hash(response: dict[str, Any]) -> str:
    """Return the base58 SHA-256 digest the signature covers."""
    message = canonical_json(signed_payload(response)).encode("utf-8")
    return b58encode(hashlib.sha256(message).digest())


def _decode_ed25519(value: str) -> bytes:
    encoded = value[len(_ED25519_PREFIX) :] if value.startswith(_ED25519_PREFIX) else value
    return b58decode(encoded)


def verify_quote_signature(
    response: dict[str, Any],
    manager_public_key: str = ONE_CLICK_MANAGER_PUB_KEY,
) -> bool:
    """Return True when ``response`` was signed by the 1-Click manager key.

    Any malformed payload returns False. A failed check must withhold fields
    the payer would send funds to, such as ``depositAddress``.
    """
    try:
        signature = response.get("signature")
        if not isinstance(signature, str) or not signature:
            return False
        signature_bytes = _decode_ed25519(signature)
        public_key_bytes = _decode_ed25519(manager_public_key)
        if len(signature_bytes) != 64 or len(public_key_bytes) != 32:
            return False
        message = quote_hash(response).encode("utf-8")
        Ed25519PublicKey.from_public_bytes(public_key_bytes).verify(signature_bytes, message)
        return True
    except (InvalidSignature, ValueError, TypeError, KeyError):
        return False
