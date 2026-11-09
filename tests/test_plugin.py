"""Unit tests with mocked 1-Click responses. No network."""

from __future__ import annotations

import json
from pathlib import Path

import intents_pay_plugin.cli as cli
import intents_pay_plugin.client as client_mod
import intents_pay_plugin.safety as safety
import intents_pay_plugin.service as service
import intents_pay_plugin.signing as signing
import intents_pay_plugin.tokens as tokens
import intents_pay_plugin.tools as tools
from intents_pay_plugin.ledger import Ledger
from intents_pay_plugin.runtime import Deps, Settings

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "dry_quote.json").read_text())

NEAR_USDC = "nep141:17208628f84f5d6ad33f0da3bbbeb27ffcb398eac501a31bd6ad2011e36133a1"
ARB_USDC = "nep141:arb-0xaf88d065e77c8cc2239327c5edb3a432268e5831.omft.near"
ARB_USDT0 = "nep141:arb-0xfd086bc7cd5c481dcc9c85ebe478a1c0b69fcbb9.omft.near"
WRAP_NEAR = "nep141:wrap.near"

SAMPLE_TOKENS = [
    {"assetId": NEAR_USDC, "decimals": 6, "blockchain": "near", "symbol": "USDC", "price": 1},
    {"assetId": "nep141:usdt.tether-token.near", "decimals": 6, "blockchain": "near", "symbol": "USDT", "price": 1},
    {"assetId": WRAP_NEAR, "decimals": 24, "blockchain": "near", "symbol": "wNEAR", "price": 3},
    {"assetId": ARB_USDC, "decimals": 6, "blockchain": "arb", "symbol": "USDC", "price": 1},
    {"assetId": ARB_USDT0, "decimals": 6, "blockchain": "arb", "symbol": "USDT0", "price": 1},
    {"assetId": "nep141:pol-usdc.omft.near", "decimals": 6, "blockchain": "pol", "symbol": "USDC", "price": 1},
    {"assetId": "nep245:v2_1.omni.hot.tg:137_usdc", "decimals": 6, "blockchain": "pol", "symbol": "USDC", "price": 1},
    {"assetId": "nep141:sol-5ce3bf3a31af18be40ba30f721101b4341690186.omft.near", "decimals": 6, "blockchain": "sol", "symbol": "USDC", "price": 1},
]


class FakeClient:
    def __init__(self, quote=None, tokens_list=None, status=None, error=None):
        self.quote = quote if quote is not None else FIXTURE
        self.tokens_list = tokens_list if tokens_list is not None else SAMPLE_TOKENS
        self.status_body = status or {
            "status": "PROCESSING",
            "updatedAt": "2026-11-09T23:00:00Z",
            "correlationId": "cid",
            "swapDetails": {"originTxHash": "0xabc"},
        }
        self.error = error
        self.calls = []

    def get_tokens(self):
        return self.tokens_list

    def request_quote(self, body):
        self.calls.append(json.loads(json.dumps(body)))
        if self.error and body.get("dry") is False:
            raise client_mod.OneClickError(self.error)
        raw = json.loads(json.dumps(self.quote))
        if not body["dry"]:
            raw["quote"]["depositAddress"] = "0x" + "cd" * 20
            raw["quote"]["deadline"] = "2026-11-09T23:30:00.000Z"
            raw["quoteRequest"]["dry"] = False
        return raw

    def get_status(self, deposit_address, deposit_memo=None):
        self.calls.append(("status", deposit_address, deposit_memo))
        return dict(self.status_body)


def make_deps(client=None, **overrides):
    return Deps(
        client=client or FakeClient(),
        ledger=overrides.get("ledger") or Ledger(memory=True),
        settings=overrides.get("settings") or Settings(),
        unattended=overrides.get("unattended", False),
        verify=overrides.get("verify"),
    )


def test_base58_hello_and_public_key_length():
    assert signing.b58encode(b"hello") == "Cn8eVZg"
    # Cross-check a known vector used by base58 libraries: "hello" is Cn8eVZg.
    assert signing.b58decode("Cn8eVZg") == b"hello"
    raw = signing.b58decode(signing.ONE_CLICK_MANAGER_PUB_KEY.split(":", 1)[1])
    assert len(raw) == 32


def test_live_dry_quote_signature_and_tamper():
    assert signing.verify_quote_signature(FIXTURE) is True
    tampered = json.loads(json.dumps(FIXTURE))
    tampered["quote"]["amountIn"] = str(int(tampered["quote"]["amountIn"]) - 1)
    assert signing.verify_quote_signature(tampered) is False
    assert signing.verify_quote_signature({"quote": {}, "quoteRequest": {}, "signature": "ed25519:aa"}) is False


def test_amounts_accounts_and_refunds():
    assert safety.to_base_units(safety.parse_amount("10.5"), 6) == "10500000"
    assert safety.to_base_units(safety.parse_amount("1"), 24) == "1" + "0" * 24
    try:
        safety.to_base_units(safety.parse_amount("1.1234567"), 6)
        raise AssertionError("expected decimal error")
    except safety.InputError:
        pass
    assert safety.is_near_account("purefile1686.near")
    assert not safety.is_near_account("Bad Account")
    assert safety.refund_address_error("arb", "0x" + "ab" * 20) is None
    assert safety.refund_address_error("arb", "not-an-address")
    assert safety.secret_material_error("abandon " * 11 + "about")
    assert safety.secret_material_error("please pay this invoice") is None


def test_token_preference_and_usdt_alias():
    pol = tokens.find_token(SAMPLE_TOKENS, "USDC", "pol")
    assert pol["assetId"].startswith("nep141:")
    usdt = tokens.find_token(SAMPLE_TOKENS, "USDT", "arb")
    assert usdt["symbol"] == "USDT0"
    assert tokens.destination_for("NEAR") == ("NEAR", "near")


def test_dry_quote_is_default_and_verifies():
    fake = FakeClient()
    result = service.quote_payment({"amount": "25", "recipient": "purefile1686.near"}, make_deps(fake))
    assert result["ok"] is True
    assert result["dry"] is True
    assert result["deposit_address"] is None
    assert result["signature_valid"] is True
    assert result["funds_moved"] is False
    assert "purefile1686.near" in result["summary"]
    assert "No deposit address" in result["summary"]
    assert fake.calls[0]["dry"] is True
    assert fake.calls[0]["swapType"] == "EXACT_OUTPUT"
    assert fake.calls[0]["amount"] == "25000000"
    assert fake.calls[0]["originAsset"] == ARB_USDC
    assert fake.calls[0]["destinationAsset"] == NEAR_USDC
    assert fake.calls[0]["recipient"] == "purefile1686.near"
    assert "appFees" not in fake.calls[0]
    assert "customRecipientMsg" not in fake.calls[0]
    assert fake.calls[0]["referral"] == "hermes-intents-pay"
    assert result["id"].startswith("ip_")


def test_usdt_and_near_routes():
    fake = FakeClient()
    usdt = service.quote_payment(
        {"amount": "5", "currency": "USDT", "pay_from": "USDT", "origin_chain": "arb"},
        make_deps(fake),
    )
    assert usdt["ok"] is True
    assert usdt["pay_from_symbol"] == "USDT0"
    assert fake.calls[-1]["originAsset"] == ARB_USDT0
    near = service.quote_payment({"amount": "1", "currency": "NEAR"}, make_deps(fake))
    assert near["ok"] is True
    assert fake.calls[-1]["destinationAsset"] == WRAP_NEAR
    assert fake.calls[-1]["amount"] == "1" + "0" * 24
    assert fake.calls[-1]["originAsset"] == ARB_USDC


def test_live_quote_requires_confirmation_token_and_refund():
    fake = FakeClient()
    deps = make_deps(fake)
    blocked = service.quote_payment({"amount": "25", "dry": False}, deps)
    assert blocked["ok"] is False
    assert fake.calls == []

    preview = service.quote_payment(
        {
            "amount": "25",
            "dry": False,
            "refund_to": "0x" + "11" * 20,
            "confirm": True,
        },
        deps,
    )
    assert preview["status"] == "confirmation_required"
    assert preview["deposit_address"] is None
    assert preview["confirmation_token"]
    assert all(call["dry"] is True for call in fake.calls)

    mismatch = service.quote_payment(
        {
            "amount": "26",
            "dry": False,
            "refund_to": "0x" + "11" * 20,
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        },
        deps,
    )
    assert mismatch["ok"] is False
    assert mismatch["code"] == "confirmation_mismatch"

    live = service.quote_payment(
        {
            "amount": "25",
            "dry": False,
            "refund_to": "0x" + "11" * 20,
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        },
        make_deps(fake, ledger=deps.ledger, verify=lambda _response: True),
    )
    assert live["ok"] is True
    assert live["dry"] is False
    assert live["deposit_address"].startswith("0x")
    assert fake.calls[-1]["dry"] is False
    assert "did not move funds" in live["summary"].lower() or "did not send" in live["summary"].lower() or "own wallet" in live["summary"].lower()


def test_bad_signature_withholds_deposit_address():
    fake = FakeClient()
    deps = make_deps(fake, verify=lambda _response: False)
    preview = service.quote_payment(
        {"amount": "2", "dry": False, "refund_to": "0x" + "22" * 20},
        deps,
    )
    refused = service.quote_payment(
        {
            "amount": "2",
            "dry": False,
            "refund_to": "0x" + "22" * 20,
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        },
        deps,
    )
    assert refused["ok"] is False
    assert refused["signature_valid"] is False
    blob = json.dumps(refused)
    assert "0xcdcd" not in blob
    assert "deposit_address" not in refused or refused.get("deposit_address") in (None, "")


def test_placeholder_refund_and_unattended_and_secrets_do_not_call_live():
    fake = FakeClient()
    placeholder = service.quote_payment(
        {
            "amount": "3",
            "dry": False,
            "refund_to": safety.EVM_DRY_PLACEHOLDER,
            "confirm": True,
            "confirmation_token": "nope",
        },
        make_deps(fake),
    )
    assert placeholder["ok"] is False
    assert fake.calls == []

    unattended = service.quote_payment(
        {"amount": "3", "dry": False, "refund_to": "0x" + "33" * 20, "confirm": True, "confirmation_token": "t"},
        make_deps(fake, unattended=True),
    )
    assert unattended["code"] == "unattended"
    assert fake.calls == []

    secret = service.create_invoice(
        {"amount": "3", "memo": "abandon " * 11 + "about"},
        make_deps(fake),
    )
    assert secret["ok"] is False
    assert "seed" in secret["error"].lower()
    assert fake.calls == []


def test_invoice_status_and_verify_roundtrip():
    fake = FakeClient()
    deps = make_deps(fake)
    created = service.create_invoice(
        {"amount": "10", "memo": "design sprint", "recipient": "PureFile1686.near"},
        deps,
    )
    assert created["recipient"] == "purefile1686.near"
    assert "design sprint" in created["summary"]
    listed = service.payment_status({}, deps)
    assert listed["invoices"][0]["id"] == created["id"]
    dry_status = service.payment_status({"invoice_id": created["number"]}, deps)
    assert dry_status["status"] == "DRY_QUOTE"
    assert not any(call[0] == "status" for call in fake.calls if isinstance(call, tuple))

    checked = service.verify_quote({"invoice_id": created["id"]}, deps)
    assert checked["signature_valid"] is True
    assert checked["deposit_address"] is None

    preview = service.quote_payment(
        {"amount": "10", "dry": False, "refund_to": "0x" + "44" * 20, "kind": "invoice"},
        deps,
    )
    live = service.create_invoice(
        {
            "amount": "10",
            "dry": False,
            "refund_to": "0x" + "44" * 20,
            "confirm": True,
            "confirmation_token": preview["confirmation_token"],
        },
        make_deps(fake, ledger=deps.ledger, verify=lambda _response: True),
    )
    status = service.payment_status({"invoice_id": live["id"]}, make_deps(fake, ledger=deps.ledger))
    assert status["status"] == "PROCESSING"
    assert status["deposit_address"] == live["deposit_address"]


def test_list_tokens_summary_and_client_errors():
    fake = FakeClient()
    summary = service.list_tokens({}, make_deps(fake))
    assert summary["ok"] is True
    assert "arb" in summary["chains"]
    assert summary["tokens"] == []
    assert any(row["symbol"] == "USDC" for row in summary["stables"])
    filtered = service.list_tokens({"symbol": "USDC", "chain": "sol"}, make_deps(fake))
    assert filtered["match_count"] == 1

    def transport(method, url, headers, body):
        assert headers["User-Agent"].startswith("hermes-intents-pay/")
        if url.endswith("/missing"):
            return 400, {"message": "nope"}
        return 200, {"quote": {"amountIn": "1"}, "ok": True}

    http = client_mod.OneClickClient(transport=transport)
    try:
        http._request("GET", "/missing", None)
        raise AssertionError("expected error")
    except client_mod.OneClickError as exc:
        assert "nope" in str(exc)
    assert http._request("GET", "/ok", None)["ok"] is True


def test_slash_parser_is_dry_only():
    action, args = cli.parse_slash("quote 25 USDC from arb USDC to purefile1686.near memo design sprint")
    assert action == "quote"
    assert args["amount"] == "25"
    assert args["currency"] == "USDC"
    assert args["origin_chain"] == "arb"
    assert args["pay_from"] == "USDC"
    assert args["recipient"] == "purefile1686.near"
    assert args["memo"] == "design sprint"
    assert args["dry"] is True
    assert cli.parse_slash("help")[0] is None
    tokens_action, token_args = cli.parse_slash("tokens USDT arb")
    assert tokens_action == "tokens"
    assert token_args == {"symbol": "USDT", "chain": "arb"}


def test_tool_handler_returns_json():
    fake = FakeClient()
    raw = tools.intents_quote({"amount": "1"}, _deps=make_deps(fake))
    payload = json.loads(raw)
    assert payload["ok"] is True
    assert payload["dry"] is True


def test_register_matches_manifest_and_desktop_surface():
    plugin = sys_plugin()
    ctx = FakeCtx()
    plugin.register(ctx)
    declared = _declared_tools()
    assert [item["name"] for item in ctx.tools] == declared
    assert ctx.commands == ["intents"]
    assert ctx.cli == ["intents-pay"]
    assert "workflow" in ctx.skills
    desktop = (ROOT / "desktop" / "plugin.js").read_text(encoding="utf-8")
    for banned in (
        "eval(",
        "new Function",
        "import(",
        ".prototype",
        "data-slot",
        "data-testid",
        "data-tour",
        "data-sidebar",
        "hermesDesktop",
        "MutationObserver",
    ):
        assert banned not in desktop
    source = "\n".join(path.read_text(encoding="utf-8") for path in ROOT.glob("*.py"))
    assert "auth.json" not in source
    assert "seed phrase" not in source.lower() or "does not accept" in source.lower()


def sys_plugin():
    import intents_pay_plugin

    return intents_pay_plugin


def _declared_tools():
    names = []
    capture = False
    for line in (ROOT / "plugin.yaml").read_text(encoding="utf-8").splitlines():
        if line.startswith("provides_tools:"):
            capture = True
            continue
        if capture:
            if line.strip().startswith("- "):
                names.append(line.split("- ", 1)[1].strip())
            elif line.strip():
                break
    return names


class FakeCtx:
    def __init__(self):
        self.tools = []
        self.commands = []
        self.skills = []
        self.cli = []

    def register_tool(self, **kwargs):
        self.tools.append(kwargs)

    def register_skill(self, name, path):
        assert Path(path).is_file()
        self.skills.append(name)

    def register_command(self, name, handler, description="", args_hint=""):
        assert callable(handler)
        self.commands.append(name)

    def register_cli_command(self, **kwargs):
        assert callable(kwargs["setup_fn"])
        assert callable(kwargs["handler_fn"])
        self.cli.append(kwargs["name"])

    def get_config(self, key, default=None):
        return default

    def current_cron_execution(self):
        return None
