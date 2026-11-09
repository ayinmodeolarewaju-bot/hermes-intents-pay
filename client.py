"""HTTP client for the public NEAR Intents 1-Click API.

Reads quotes, token lists, and swap status. It never submits a deposit and
never signs a transfer. An optional partner key is sent only as ``X-API-Key``
when the caller already resolved it through Hermes' secret scope.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Callable

from .tokens import API_BASE

Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, Any]]

_TOKEN_CACHE: dict[str, tuple[float, list[dict[str, Any]]]] = {}
_TOKEN_TTL_SECONDS = 300
_USER_AGENT = "hermes-intents-pay/1.0.0"


class OneClickError(Exception):
    """The 1-Click API rejected a call or could not be reached."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OneClickClient:
    def __init__(
        self,
        base_url: str = API_BASE,
        api_key: str | None = None,
        timeout: float = 25,
        transport: Transport | None = None,
    ) -> None:
        self.base_url = (base_url or API_BASE).rstrip("/")
        self.api_key = api_key or None
        self.timeout = timeout
        self._transport = transport

    def get_tokens(self, *, force: bool = False) -> list[dict[str, Any]]:
        now = time.time()
        cached = _TOKEN_CACHE.get(self.base_url)
        if not force and cached and now - cached[0] < _TOKEN_TTL_SECONDS:
            return cached[1]
        payload = self._request("GET", "/v0/tokens", None)
        if not isinstance(payload, list):
            raise OneClickError("1-Click token list was not a list")
        tokens = [row for row in payload if isinstance(row, dict)]
        _TOKEN_CACHE[self.base_url] = (now, tokens)
        return tokens

    def request_quote(self, body: dict[str, Any]) -> dict[str, Any]:
        payload = self._request("POST", "/v0/quote", body)
        if not isinstance(payload, dict) or not isinstance(payload.get("quote"), dict):
            raise OneClickError("1-Click quote response was missing a quote")
        return payload

    def get_status(self, deposit_address: str, deposit_memo: str | None = None) -> dict[str, Any]:
        from urllib.parse import urlencode

        query = {"depositAddress": deposit_address}
        if deposit_memo:
            query["depositMemo"] = deposit_memo
        payload = self._request("GET", "/v0/status?" + urlencode(query), None)
        if not isinstance(payload, dict):
            raise OneClickError("1-Click status response was not an object")
        return payload

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        }
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def _request(self, method: str, path: str, body: dict[str, Any] | None) -> Any:
        raw = None if body is None else json.dumps(body).encode("utf-8")
        url = self.base_url + path
        headers = self._headers()
        if self._transport is not None:
            status, payload = self._transport(method, url, headers, raw)
            return self._interpret(status, payload)
        request = urllib.request.Request(url, data=raw, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                text = response.read().decode("utf-8")
                status = response.status
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            try:
                payload = json.loads(text) if text else {}
            except json.JSONDecodeError:
                payload = {"message": text[:300] or exc.reason}
            return self._interpret(exc.code, payload)
        except urllib.error.URLError as exc:
            raise OneClickError(f"Could not reach the 1-Click API: {exc.reason}") from exc
        try:
            payload = json.loads(text) if text else {}
        except json.JSONDecodeError as exc:
            raise OneClickError("1-Click returned a response that was not JSON") from exc
        return self._interpret(status, payload)

    @staticmethod
    def _interpret(status: int, payload: Any) -> Any:
        if status >= 400:
            message = None
            if isinstance(payload, dict):
                message = payload.get("message") or payload.get("error")
            raise OneClickError(str(message or f"1-Click HTTP {status}"), status_code=status)
        return payload


def clear_token_cache() -> None:
    _TOKEN_CACHE.clear()
