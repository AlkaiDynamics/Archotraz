from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
import tempfile
import unittest
from pathlib import Path

from archotraz.cli import main


class CliTests(unittest.TestCase):
    def test_init_starts_archotraz_and_initializes_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "state" / "archotraz.db"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["init", "--db", str(db)])
            self.assertEqual(code, 0)
            payload = json.loads(stdout.getvalue())
            self.assertTrue(payload["ok"])
            self.assertTrue(payload["dry_mode"])
            self.assertTrue(db.exists())

    def test_repo_add_cli_creates_then_deduplicates_repo_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "archotraz.db"

            first_stdout = io.StringIO()
            with redirect_stdout(first_stdout):
                first_code = main(
                    [
                        "repo",
                        "add",
                        "https://github.com/AlkaiDynamics/Archotraz",
                        "--db",
                        str(db),
                        "--priority",
                        "7",
                        "--tag",
                        "core",
                        "--note",
                        "manual intake",
                    ]
                )

            second_stdout = io.StringIO()
            with redirect_stdout(second_stdout):
                second_code = main(
                    [
                        "repo",
                        "add",
                        "https://github.com/alkaidynamics/archotraz.git",
                        "--db",
                        str(db),
                    ]
                )

            first = json.loads(first_stdout.getvalue())
            second = json.loads(second_stdout.getvalue())

            self.assertEqual(first_code, 0)
            self.assertEqual(second_code, 0)
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            self.assertEqual(first["repo"]["repo_id"], second["repo"]["repo_id"])
            self.assertEqual(first["repo"]["canonical_url"], "https://github.com/AlkaiDynamics/Archotraz")
            self.assertEqual(first["repo"]["priority"], 7)
            self.assertEqual(first["repo"]["tags"], ["core"])
            self.assertEqual(first["repo"]["notes"], "manual intake")

    def test_profile_cli_preserves_missingness_without_detective_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "archotraz.db"

            add_stdout = io.StringIO()
            with redirect_stdout(add_stdout):
                main(
                    [
                        "repo",
                        "add",
                        "https://github.com/AlkaiDynamics/Archotraz",
                        "--db",
                        str(db),
                    ]
                )
            repo_id = json.loads(add_stdout.getvalue())["repo"]["repo_id"]

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                code = main(["profile", repo_id, "--db", str(db)])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(code, 0)
            self.assertEqual(payload["repo_id"], repo_id)
            self.assertIsNone(payload["language"])
            self.assertIn("language", payload["missing_fields"])

    def test_cell_cli_assigns_explicit_block_and_shows_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "archotraz.db"

            add_stdout = io.StringIO()
            with redirect_stdout(add_stdout):
                main(
                    [
                        "repo",
                        "add",
                        "https://github.com/AlkaiDynamics/Archotraz",
                        "--db",
                        str(db),
                    ]
                )
            repo_id = json.loads(add_stdout.getvalue())["repo"]["repo_id"]

            assign_stdout = io.StringIO()
            with redirect_stdout(assign_stdout):
                assign_code = main(
                    [
                        "cell",
                        "assign",
                        repo_id,
                        "--block",
                        "GEN_POP",
                        "--reason",
                        "initial explicit placement",
                        "--db",
                        str(db),
                    ]
                )

            show_stdout = io.StringIO()
            with redirect_stdout(show_stdout):
                show_code = main(["cell", "show", repo_id, "--db", str(db)])

            assigned = json.loads(assign_stdout.getvalue())
            shown = json.loads(show_stdout.getvalue())

            self.assertEqual(assign_code, 0)
            self.assertEqual(show_code, 0)
            self.assertEqual(assigned["block"], "GEN_POP")
            self.assertEqual(shown["current"]["block"], "GEN_POP")
            self.assertEqual(len(shown["history"]), 1)
            self.assertEqual(shown["history"][0]["reason"], "initial explicit placement")

    def test_pairs_and_pair_eligibility_guard_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "archotraz.db"
            repo_ids: list[str] = []

            for url in (
                "https://github.com/AlkaiDynamics/Archotraz",
                "https://github.com/openai/openai-python",
            ):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    main(["repo", "add", url, "--db", str(db)])
                repo_ids.append(json.loads(stdout.getvalue())["repo"]["repo_id"])

            pairs_stdout = io.StringIO()
            with redirect_stdout(pairs_stdout):
                pairs_code = main(["pairs", "--db", str(db)])
            pairs_payload = json.loads(pairs_stdout.getvalue())

            self.assertEqual(pairs_code, 0)
            self.assertEqual(pairs_payload["count"], 1)
            self.assertEqual(
                set(
                    (
                        pairs_payload["pairs"][0]["repo_a_id"],
                        pairs_payload["pairs"][0]["repo_b_id"],
                    )
                ),
                set(repo_ids),
            )

            unknown_stdout = io.StringIO()
            with redirect_stdout(unknown_stdout):
                unknown_code = main(
                    [
                        "guard",
                        "pair-eligibility",
                        repo_ids[0],
                        repo_ids[1],
                        "--db",
                        str(db),
                    ]
                )
            unknown = json.loads(unknown_stdout.getvalue())
            self.assertEqual(unknown_code, 0)
            self.assertEqual(unknown["result"]["status"], "UNKNOWN")

            for repo_id, block in zip(repo_ids, ("GEN_POP", "B"), strict=True):
                with redirect_stdout(io.StringIO()):
                    main(
                        [
                            "cell",
                            "assign",
                            repo_id,
                            "--block",
                            block,
                            "--reason",
                            "guard CLI test",
                            "--db",
                            str(db),
                        ]
                    )

            pass_stdout = io.StringIO()
            with redirect_stdout(pass_stdout):
                pass_code = main(
                    [
                        "guard",
                        "pair-eligibility",
                        repo_ids[0],
                        repo_ids[1],
                        "--db",
                        str(db),
                    ]
                )
            passed = json.loads(pass_stdout.getvalue())

            self.assertEqual(pass_code, 0)
            self.assertEqual(passed["result"]["status"], "PASS")
            self.assertTrue(passed["contract"]["deterministic"])
            self.assertEqual(passed["contract"]["name"], "pair.cell-readiness")


if __name__ == "__main__":
    unittest.main()
