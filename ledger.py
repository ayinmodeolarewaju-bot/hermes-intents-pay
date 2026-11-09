"""Profile-scoped invoice ledger.

Runtime state lives outside the plugin install tree so ``hermes plugins update``
does not delete it. Hermes' ``plugin_data_dir`` is used when the host provides
it. Tests pass an explicit path or an in-memory ledger.
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Callable

_LOCK = threading.Lock()
_EMPTY: dict[str, Any] = {"invoices": [], "pending": {}}
_MAX_INVOICES = 50


def hermes_ledger_path() -> Path | None:
    """Return the durable ledger path, or None when no home can be resolved."""
    try:
        from plugins.plugin_storage import plugin_data_dir

        directory = Path(plugin_data_dir("intents-pay"))
        directory.mkdir(parents=True, exist_ok=True)
        return directory / "ledger.json"
    except Exception:
        return None


class Ledger:
    """JSON ledger. ``path=None`` keeps the book in memory for tests."""

    def __init__(self, path: Path | None = None, *, memory: bool = False) -> None:
        self.path = None if memory else path
        self._memory: dict[str, Any] | None = {"invoices": [], "pending": {}} if self.path is None else None

    def read(self) -> dict[str, Any]:
        with _LOCK:
            return self._read_unlocked()

    def update(self, mutator: Callable[[dict[str, Any]], Any]) -> Any:
        with _LOCK:
            data = self._read_unlocked()
            result = mutator(data)
            invoices = data.get("invoices")
            if isinstance(invoices, list) and len(invoices) > _MAX_INVOICES:
                data["invoices"] = invoices[-_MAX_INVOICES :]
            self._write_unlocked(data)
            return result

    def _read_unlocked(self) -> dict[str, Any]:
        if self._memory is not None:
            return json.loads(json.dumps(self._memory))
        assert self.path is not None
        if not self.path.exists():
            return {"invoices": [], "pending": {}}
        try:
            loaded = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"invoices": [], "pending": {}}
        if not isinstance(loaded, dict):
            return {"invoices": [], "pending": {}}
        loaded.setdefault("invoices", [])
        loaded.setdefault("pending", {})
        return loaded

    def _write_unlocked(self, data: dict[str, Any]) -> None:
        if self._memory is not None:
            self._memory = json.loads(json.dumps(data))
            return
        assert self.path is not None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        os.replace(temporary, self.path)
