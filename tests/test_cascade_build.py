from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "cascade_build.py"
spec = importlib.util.spec_from_file_location("cascade_build", SCRIPT)
assert spec and spec.loader
cascade = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cascade)


class CascadeBuildTests(unittest.TestCase):
    def test_default_plan_claims_ready_only_for_implemented_stages(self) -> None:
        stages = cascade.load_stages(None)
        self.assertTrue(cascade.ready(stages[0]))
        self.assertTrue(cascade.ready(stages[1]))
        self.assertTrue(all(not cascade.ready(stage) for stage in stages[2:]))

    def test_independent_tracks_can_be_selected_without_running_unrelated_gate(self) -> None:
        stages = [
            {"id": "foundation", "requires": [], "files": ["pyproject.toml"], "build": [],
             "checks": [["{python}", "-c", "print('ok')"]]},
            {"id": "case", "requires": ["foundation"], "files": [], "build": [], "checks": []},
            {"id": "identity", "requires": ["foundation"], "files": ["pyproject.toml"], "build": [],
             "checks": [["{python}", "-c", "print('identity')"]]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.assertEqual(cascade.run(stages, path, None, "identity"), 0)
            receipts = cascade.read_state(path)["receipts"]
            self.assertEqual(set(receipts), {"foundation", "identity"})
            self.assertEqual(cascade.run(stages, path, None, "identity"), 0)

    def test_missing_stage_blocks_without_fabricating_receipt(self) -> None:
        stages = [{"id": "future", "requires": [], "files": [], "build": [], "checks": [], "gate": "not built"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.assertEqual(cascade.run(stages, path, None, None), 2)
            self.assertFalse(path.exists())

    def test_failed_check_records_failure_and_prevents_dependent_stage(self) -> None:
        stages = [
            {"id": "failing", "requires": [], "files": ["pyproject.toml"], "build": [],
             "checks": [["{python}", "-c", "raise SystemExit(3)"]]},
            {"id": "next", "requires": ["failing"], "files": ["pyproject.toml"], "build": [],
             "checks": [["{python}", "-c", "print('must not run')"]]},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            self.assertEqual(cascade.run(stages, path, None, None), 1)
            receipts = cascade.read_state(path)["receipts"]
            self.assertEqual(receipts["failing"]["status"], "failed")
            self.assertNotIn("next", receipts)

    def test_recipe_rejects_unsafe_ambiguous_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Path(tmp) / "recipe.json"
            recipe.write_text(json.dumps({"stages": [{"id": "x", "requires": [], "files": ["pyproject.toml"],
                           "build": [["{python}", "-c", "pass"]], "checks": [["{python}", "-c", "pass"]]}]}))
            with self.assertRaisesRegex(ValueError, "idempotent_build"):
                cascade.load_stages(recipe)


if __name__ == "__main__":
    unittest.main()
