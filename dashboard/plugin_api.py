"""Dashboard routes mounted at /api/plugins/intents-pay/.

The desktop pane calls these. They share the quote service with the agent
tools. Live deposit addresses still require the confirmation token.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

from fastapi import APIRouter, Request

router = APIRouter()
_ROOT = Path(__file__).resolve().parents[1]


def _modules():
    for name, module in list(sys.modules.items()):
        if getattr(module, "PLUGIN_ID", None) == "intents-pay":
            service = sys.modules.get(name + ".service")
            runtime = sys.modules.get(name + ".runtime")
            if service is not None and runtime is not None:
                return service, runtime
    package = "intents_pay_plugin"
    if package not in sys.modules:
        spec = importlib.util.spec_from_file_location(
            package,
            _ROOT / "__init__.py",
            submodule_search_locations=[str(_ROOT)],
        )
        module = importlib.util.module_from_spec(spec)
        module.__package__ = package
        module.__path__ = [str(_ROOT)]
        sys.modules[package] = module
        assert spec.loader is not None
        spec.loader.exec_module(module)
    return importlib.import_module(package + ".service"), importlib.import_module(package + ".runtime")


def _deps():
    _service, runtime = _modules()
    return runtime.make_deps()


@router.get("/health")
async def health() -> dict:
    return {"ok": True, "plugin": "intents-pay", "funds_moved": False}


@router.get("/tokens")
async def tokens(symbol: str = "", chain: str = "") -> dict:
    service, _runtime = _modules()
    return service.list_tokens({"symbol": symbol, "chain": chain}, _deps())


@router.get("/invoices")
async def invoices() -> dict:
    service, _runtime = _modules()
    return service.payment_status({}, _deps())


@router.post("/quote")
async def quote(request: Request) -> dict:
    service, _runtime = _modules()
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "error": "JSON object required", "funds_moved": False}
    return service.quote_payment(body, _deps(), kind="quote")


@router.post("/invoice")
async def invoice(request: Request) -> dict:
    service, _runtime = _modules()
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "error": "JSON object required", "funds_moved": False}
    return service.create_invoice(body, _deps())


@router.post("/status")
async def status(request: Request) -> dict:
    service, _runtime = _modules()
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "error": "JSON object required", "funds_moved": False}
    return service.payment_status(body, _deps())


@router.post("/verify")
async def verify(request: Request) -> dict:
    service, _runtime = _modules()
    body = await request.json()
    if not isinstance(body, dict):
        return {"ok": False, "error": "JSON object required", "funds_moved": False}
    return service.verify_quote(body, _deps())
