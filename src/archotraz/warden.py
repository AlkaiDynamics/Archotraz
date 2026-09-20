from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, TypeVar

from .bopo import BopoControlPort, ControlResponse
from .evidence import EvidenceLedger


T = TypeVar("T")


class DryModeViolation(PermissionError):
    pass


@dataclass(slots=True)
class Warden:
    ledger: EvidenceLedger
    bopo: BopoControlPort
    dry_mode: bool = True

    def check_bopo_health(self) -> ControlResponse:
        return self._record_control_call("bopo.health", {}, self.bopo.health)

    def check_bopo_preflight(
        self,
        provider_type: str,
        runtime_config: dict[str, Any] | None = None,
    ) -> ControlResponse:
        inputs = {"provider_type": provider_type, "runtime_config": runtime_config or {}}
        return self._record_control_call(
            "bopo.preflight",
            inputs,
            lambda: self.bopo.preflight(provider_type, runtime_config),
        )

    def run_side_effecting(self, operation: str, action: Callable[[], T]) -> T:
        """Cross a side-effecting execution door only when Dry Mode is disabled."""
        if self.dry_mode:
            raise DryModeViolation(f"Dry Mode blocks side-effecting operation: {operation}")
        return action()

    def _record_control_call(
        self,
        kind: str,
        inputs: dict[str, Any],
        call: Callable[[], ControlResponse],
    ) -> ControlResponse:
        attempt_id = self.ledger.begin_attempt(kind, inputs)
        try:
            response = call()
        except Exception as exc:
            request_id = getattr(exc, "request_id", None)
            status_code = getattr(exc, "status_code", None)
            self.ledger.finish_attempt(
                attempt_id,
                status="failed",
                error_text=str(exc),
                request_id=request_id,
                external_ref=request_id,
            )
            failure = self.ledger.record_failure(kind, str(exc), attempt_id=attempt_id, payload=inputs)
            self.ledger.record_provenance(
                failure,
                source_type="bopo",
                source_ref=request_id or kind,
                metadata={"attempt_id": attempt_id, "http_status": status_code},
            )
            raise

        self.ledger.finish_attempt(
            attempt_id,
            status="succeeded",
            output=response.payload,
            request_id=response.request_id,
            external_ref=response.request_id,
        )
        observation = self.ledger.record_observation(
            kind,
            "bopo",
            response.payload,
            external_ref=response.request_id,
        )
        self.ledger.record_provenance(
            observation,
            source_type="bopo",
            source_ref=response.request_id,
            metadata={
                "attempt_id": attempt_id,
                "http_status": response.status_code,
                "control_kind": kind,
            },
        )
        return response
