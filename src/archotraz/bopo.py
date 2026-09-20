from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Protocol
from urllib import error, request
from uuid import uuid4


class BopoError(RuntimeError):
    pass


class BopoConfigurationError(BopoError):
    pass


class BopoTransportError(BopoError):
    def __init__(
        self,
        message: str,
        *,
        request_id: str,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.request_id = request_id
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True, slots=True)
class ControlResponse:
    status_code: int
    payload: Any
    request_id: str


class BopoControlPort(Protocol):
    def health(self) -> ControlResponse: ...

    def preflight(self, provider_type: str, runtime_config: dict[str, Any] | None = None) -> ControlResponse: ...


@dataclass(slots=True)
class BopoHttpControlPort:
    base_url: str = "http://localhost:4020"
    company_id: str | None = None
    timeout_seconds: float = 10.0

    def __post_init__(self) -> None:
        self.base_url = self.base_url.rstrip("/")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")

    def health(self) -> ControlResponse:
        return self._request("GET", "/health")

    def preflight(self, provider_type: str, runtime_config: dict[str, Any] | None = None) -> ControlResponse:
        if not self.company_id:
            raise BopoConfigurationError("Bopo runtime preflight requires a company id")
        body: dict[str, Any] = {"providerType": provider_type}
        if runtime_config:
            body["runtimeConfig"] = runtime_config
        return self._request("POST", "/agents/runtime-preflight", body, company_scoped=True)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        company_scoped: bool = False,
    ) -> ControlResponse:
        request_id = f"archotraz-{uuid4().hex}"
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {"accept": "application/json", "x-request-id": request_id}
        if body is not None:
            headers["content-type"] = "application/json"
        if company_scoped:
            if not self.company_id:
                raise BopoConfigurationError("company-scoped Bopo request requires a company id")
            headers["x-company-id"] = self.company_id

        req = request.Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                raw = response.read()
                response_request_id = response.headers.get("x-request-id") or request_id
                decoded = self._decode_json(raw)
                return ControlResponse(int(response.status), decoded, response_request_id)
        except error.HTTPError as exc:
            raw = exc.read()
            decoded = self._decode_json(raw)
            response_request_id = exc.headers.get("x-request-id") or request_id
            raise BopoTransportError(
                f"Bopo {method} {path} returned HTTP {exc.code}: {decoded!r}",
                request_id=response_request_id,
                status_code=int(exc.code),
                payload=decoded,
            ) from exc
        except error.URLError as exc:
            raise BopoTransportError(
                f"Bopo {method} {path} failed: {exc.reason}",
                request_id=request_id,
            ) from exc

    @staticmethod
    def _decode_json(raw: bytes) -> Any:
        if not raw:
            return None
        text = raw.decode("utf-8", errors="replace")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}
