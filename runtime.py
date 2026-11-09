"""Host settings, the optional partner key, and the shared ledger.

Secrets are read with ``agent.secret_scope.get_secret`` when Hermes is the
host. This module does not open credential files or key stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ledger import Ledger, hermes_ledger_path
from .tokens import API_BASE, DEFAULT_RECIPIENT

PLUGIN_ID = "intents-pay"
API_KEY_ENV = "INTENTS_PAY_API_KEY"


@dataclass
class Settings:
    api_base: str = API_BASE
    default_recipient: str = DEFAULT_RECIPIENT
    slippage_bps: int = 100
    api_key: str | None = None


@dataclass
class Deps:
    client: Any
    ledger: Ledger
    settings: Settings
    unattended: bool = False
    verify: Any = None


def read_api_key() -> str | None:
    """Partner key via Hermes secret scope. Missing key is normal."""
    try:
        from agent.secret_scope import get_secret
    except Exception:
        return None
    try:
        value = get_secret(API_KEY_ENV)
    except Exception:
        return None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _config_value(ctx: Any, key: str, default: Any) -> Any:
    if ctx is None or not hasattr(ctx, "get_config"):
        return default
    try:
        value = ctx.get_config(key, default=default)
    except TypeError:
        try:
            value = ctx.get_config(key)
        except Exception:
            return default
    except Exception:
        return default
    if value is None or value == "":
        return default
    return value


def _settings_from_mapping(mapping: dict[str, Any] | None, settings: Settings) -> Settings:
    if not isinstance(mapping, dict):
        return settings
    if mapping.get("api_base"):
        settings.api_base = str(mapping["api_base"]).strip() or settings.api_base
    if mapping.get("default_recipient"):
        settings.default_recipient = str(mapping["default_recipient"]).strip()
    if mapping.get("slippage_bps") not in (None, ""):
        try:
            settings.slippage_bps = int(mapping["slippage_bps"])
        except (TypeError, ValueError):
            pass
    return settings


def settings_from_host(ctx: Any = None) -> Settings:
    settings = Settings(api_key=read_api_key())
    if ctx is not None:
        settings.api_base = str(_config_value(ctx, "api_base", settings.api_base))
        settings.default_recipient = str(
            _config_value(ctx, "default_recipient", settings.default_recipient)
        )
        try:
            settings.slippage_bps = int(_config_value(ctx, "slippage_bps", settings.slippage_bps))
        except (TypeError, ValueError):
            pass
        return settings
    try:
        from hermes_cli.config import load_config_readonly

        loaded = load_config_readonly() or {}
        entries = ((loaded.get("plugins") or {}).get("entries") or {}).get(PLUGIN_ID) or {}
        settings = _settings_from_mapping(entries.get("settings") or {}, settings)
    except Exception:
        pass
    return settings


def is_unattended(ctx: Any) -> bool:
    """True during cron, where nobody can confirm a live quote."""
    if ctx is None:
        return False
    probe = getattr(ctx, "current_cron_execution", None)
    if not callable(probe):
        return False
    try:
        return probe() is not None
    except Exception:
        return False


def open_ledger() -> Ledger:
    path = hermes_ledger_path()
    if path is not None:
        return Ledger(path)
    return Ledger(memory=True)


def make_deps(ctx: Any = None, **overrides: Any) -> Deps:
    from .client import OneClickClient

    settings = overrides.get("settings") or settings_from_host(ctx)
    client = overrides.get("client") or OneClickClient(settings.api_base, api_key=settings.api_key)
    ledger = overrides.get("ledger") or open_ledger()
    return Deps(
        client=client,
        ledger=ledger,
        settings=settings,
        unattended=overrides.get("unattended", is_unattended(ctx)),
        verify=overrides.get("verify"),
    )
