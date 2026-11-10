"""Request one live dry quote and verify its signature. Never sets dry=false."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = "intents_pay_plugin"


def load():
    if PKG in sys.modules:
        return sys.modules[PKG]
    spec = importlib.util.spec_from_file_location(
        PKG,
        ROOT / "__init__.py",
        submodule_search_locations=[str(ROOT)],
    )
    module = importlib.util.module_from_spec(spec)
    module.__package__ = PKG
    module.__path__ = [str(ROOT)]
    sys.modules[PKG] = module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


def main() -> int:
    load()
    from intents_pay_plugin.client import OneClickClient
    from intents_pay_plugin.ledger import Ledger
    from intents_pay_plugin.runtime import Deps, Settings
    from intents_pay_plugin.service import quote_payment

    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("recipient is required. Example: python scripts/live_dry_quote.py name.near")
        return 2
    client = OneClickClient()
    result = quote_payment(
        {
            "amount": "25",
            "currency": "USDC",
            "pay_from": "USDC",
            "origin_chain": "arb",
            "recipient": sys.argv[1].strip(),
            "memo": "hermes intents pay dry run",
            "dry": True,
        },
        Deps(client=client, ledger=Ledger(memory=True), settings=Settings()),
    )
    print(result.get("summary") or result)
    print("---")
    print("ok:", result.get("ok"), "dry:", result.get("dry"), "signature:", result.get("signature_valid"))
    print("deposit:", result.get("deposit_address"))
    if not result.get("ok") or result.get("dry") is not True or result.get("signature_valid") is not True:
        return 1
    if result.get("deposit_address"):
        print("dry quote unexpectedly included a deposit address")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
