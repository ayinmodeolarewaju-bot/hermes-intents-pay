"""Resolve 1-Click token rows to a destination payout and an origin asset.

Symbol matching follows invoice-link: USDT also matches the omnichain USDT0
listing, and NEAR payouts settle as wNEAR (``nep141:wrap.near``).
"""

from __future__ import annotations

from typing import Any

INVOICE_CURRENCIES = ("USDC", "USDT", "NEAR")
DEFAULT_ORIGIN_CHAIN = "arb"
API_BASE = "https://1click.chaindefuser.com"
REFERRAL = "hermes-intents-pay"

# Used only when GET /v0/tokens cannot be reached. Ids match the public list.
FALLBACK_TOKENS: list[dict[str, Any]] = [
    {
        "assetId": "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1",
        "decimals": 6,
        "blockchain": "near",
        "symbol": "USDC",
        "price": 1,
    },
    {
        "assetId": "nep141:usdt.tether-token.near",
        "decimals": 6,
        "blockchain": "near",
        "symbol": "USDT",
        "price": 1,
    },
    {
        "assetId": "nep141:wrap.near",
        "decimals": 24,
        "blockchain": "near",
        "symbol": "wNEAR",
        "price": 0,
    },
    {
        "assetId": "nep141:arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near",
        "decimals": 6,
        "blockchain": "arb",
        "symbol": "USDC",
        "price": 1,
    },
    {
        "assetId": "nep141:arb-0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9.omft.near",
        "decimals": 6,
        "blockchain": "arb",
        "symbol": "USDT0",
        "price": 1,
    },
    {
        "assetId": "nep141:eth-0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48.omft.near",
        "decimals": 6,
        "blockchain": "eth",
        "symbol": "USDC",
        "price": 1,
    },
    {
        "assetId": "nep141:base-0x833589fcd6edb6e08f4c7c32d4f71b54bda02913.omft.near",
        "decimals": 6,
        "blockchain": "base",
        "symbol": "USDC",
        "price": 1,
    },
    {
        "assetId": "nep141:sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near",
        "decimals": 6,
        "blockchain": "sol",
        "symbol": "USDC",
        "price": 1,
    },
]


def parse_currency(raw: Any, *, default: str = "USDC") -> str:
    text = str(raw or default).strip().upper()
    if text in {"USDT", "USDT0"}:
        return "USDT"
    if text in {"NEAR", "WNEAR"}:
        return "NEAR"
    if text == "USDC":
        return "USDC"
    return text


def symbol_matches(token_symbol: str, want: str) -> bool:
    left = (token_symbol or "").upper()
    right = (want or "").upper()
    if not left or not right:
        return False
    if left == right:
        return True
    if right == "USDT" and left == "USDT0":
        return True
    if right in {"NEAR", "WNEAR"} and left in {"NEAR", "WNEAR"}:
        return True
    return False


def _score(token: dict[str, Any], want: str) -> int:
    symbol = str(token.get("symbol") or "")
    asset_id = str(token.get("assetId") or "")
    score = 0
    if symbol.upper() == want.upper():
        score += 10
    elif symbol_matches(symbol, want):
        score += 5
    if asset_id.startswith("nep141:"):
        score += 4
    if "omft.near" in asset_id or asset_id.endswith("wrap.near"):
        score += 2
    if asset_id.startswith("nep245:"):
        score -= 3
    return score


def find_token(
    tokens: list[dict[str, Any]],
    symbol: str,
    chain: str,
) -> dict[str, Any] | None:
    chain_id = (chain or "").strip().lower()
    want = (symbol or "").strip()
    matches = [
        token
        for token in tokens
        if str(token.get("blockchain") or "").lower() == chain_id
        and symbol_matches(str(token.get("symbol") or ""), want)
    ]
    if not matches:
        return None
    return max(matches, key=lambda token: _score(token, want))


def find_by_asset_id(tokens: list[dict[str, Any]], asset_id: str) -> dict[str, Any] | None:
    for token in tokens:
        if token.get("assetId") == asset_id:
            return token
    return None


def destination_for(currency: str) -> tuple[str, str]:
    """Return ``(symbol, chain)`` the recipient is paid in."""
    if currency == "NEAR":
        return "NEAR", "near"
    return currency, "near"


def compact_token(token: dict[str, Any]) -> dict[str, Any]:
    return {
        "asset_id": token.get("assetId"),
        "symbol": token.get("symbol"),
        "blockchain": token.get("blockchain"),
        "decimals": token.get("decimals"),
        "price_usd": token.get("price"),
    }


def chains_of(tokens: list[dict[str, Any]]) -> list[str]:
    found = {str(token.get("blockchain")) for token in tokens if token.get("blockchain")}
    return sorted(found)
