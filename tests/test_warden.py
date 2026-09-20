from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from archotraz.bopo import BopoTransportError, ControlResponse
from archotraz.evidence import EvidenceLedger
from archotraz.warden import DryModeViolation, Warden


class FakeBopo:
    def __init__(self, *, fail_health: bool = False) -> None:
        self.fail_health = fail_health
        self.preflight_calls: list[tuple[str, dict[str, Any] | None]] = []

    def health(self) -> ControlResponse:
        if self.fail_health:
            raise BopoTransportError("offline", request_id="req-failed")
        return ControlResponse(200, {"ok": True, "db": {"ready": True}}, "req-health")

    def preflight(self, provider_type: str, runtime_config: dict[str, Any] | None = None) -> ControlResponse:
        self.preflight_calls.append((provider_type, runtime_config))
        return ControlResponse(200, {"status": "pass", "checks": []}, "req-preflight")


class WardenTests(unittest.TestCase):
    def make_warden(self, root: str, bopo: FakeBopo, *, dry_mode: bool = True) -> tuple[Warden, EvidenceLedger]:
        ledger = EvidenceLedger(Path(root) / "ledger.db")
        ledger.initialize()
        return Warden(ledger=ledger, bopo=bopo, dry_mode=dry_mode), ledger

    def test_health_is_recorded_as_attempt_observation_and_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warden, ledger = self.make_warden(tmp, FakeBopo())
            response = warden.check_bopo_health()
            self.assertTrue(response.payload["ok"])
            self.assertEqual(ledger.rows("attempts")[0]["kind"], "bopo.health")
            self.assertEqual(ledger.rows("observations")[0]["source"], "bopo")
            self.assertEqual(ledger.rows("provenance")[0]["source_ref"], "req-health")

    def test_preflight_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake = FakeBopo()
            warden, ledger = self.make_warden(tmp, fake)
            response = warden.check_bopo_preflight("shell", {"runtimeCommand": "echo"})
            self.assertEqual(response.payload["status"], "pass")
            self.assertEqual(fake.preflight_calls, [("shell", {"runtimeCommand": "echo"})])
            self.assertEqual(ledger.rows("attempts")[0]["kind"], "bopo.preflight")

    def test_failed_control_call_records_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warden, ledger = self.make_warden(tmp, FakeBopo(fail_health=True))
            with self.assertRaises(BopoTransportError):
                warden.check_bopo_health()
            self.assertEqual(ledger.rows("attempts")[0]["status"], "failed")
            self.assertEqual(ledger.rows("failures")[0]["kind"], "bopo.health")
            self.assertEqual(ledger.rows("attempts")[0]["request_id"], "req-failed")
            self.assertEqual(ledger.rows("provenance")[0]["source_ref"], "req-failed")

    def test_dry_mode_blocks_side_effect_before_action_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warden, _ = self.make_warden(tmp, FakeBopo(), dry_mode=True)
            called = False

            def action() -> str:
                nonlocal called
                called = True
                return "ran"

            with self.assertRaises(DryModeViolation):
                warden.run_side_effecting("heartbeat.run", action)
            self.assertFalse(called)

    def test_side_effect_can_run_when_dry_mode_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            warden, _ = self.make_warden(tmp, FakeBopo(), dry_mode=False)
            self.assertEqual(warden.run_side_effecting("test.operation", lambda: "ran"), "ran")


if __name__ == "__main__":
    unittest.main()
