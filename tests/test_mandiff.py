import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from mandiff import _parser, _scaffold_units, _support_category, cleanup, finalize, prepare  # noqa: E402


PIPELINE_DIFF = ROOT / "tests" / "fixtures" / "pipeline.diff"
PIPELINE_DRAFT = ROOT / "tests" / "fixtures" / "pipeline-draft.json"


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


class ManDiffWorkflowTests(unittest.TestCase):
    def _prepare_patch(self, output: Path) -> Path:
        args = _parser().parse_args(
            ["prepare", "--patch", str(PIPELINE_DIFF), "--output", str(output), "--repository", "fixture"]
        )
        return prepare(args)

    def _git_repo(self, root: Path) -> Path:
        repo = root / "repo"
        repo.mkdir()
        run(["git", "init"], repo)
        run(["git", "config", "user.name", "Fixture"], repo)
        run(["git", "config", "user.email", "fixture@example.com"], repo)
        (repo / "value.txt").write_text("old\n", encoding="utf-8")
        run(["git", "add", "value.txt"], repo)
        run(["git", "commit", "-m", "initial"], repo)
        return repo

    def test_prepare_patch_creates_inventory_draft_and_context_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            self.assertEqual(self._prepare_patch(output), output.resolve())
            for name in (
                "source-manifest.json",
                "inventory.json",
                "analysis-draft.json",
                "context-candidates.json",
                "prepare-state.json",
            ):
                self.assertTrue((output / name).exists())
            inventory = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
            draft = json.loads((output / "analysis-draft.json").read_text(encoding="utf-8"))
            self.assertEqual([item["evidence_id"] for item in inventory["evidence"]], ["F01-H01"])
            self.assertEqual(draft["schema_version"], "2.0")
            self.assertEqual(draft["units"][0]["evidence"][0]["id"], "F01-H01")

    def test_prepare_refuses_output_inside_reviewed_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--unstaged", "--output", str(repo / "review")]
            )
            with self.assertRaisesRegex(SystemExit, "outside the reviewed repository"):
                prepare(args)

    def test_supporting_classification_covers_root_level_paths(self):
        self.assertEqual(_support_category("tests/test_reader.py"), "tests")
        self.assertEqual(_support_category("test_reader.py"), "tests")
        self.assertEqual(_support_category("docs/guide.md"), "documentation")
        self.assertEqual(_support_category("generated/client.py"), "generated files")

    def test_scaffold_caps_automatic_group_size(self):
        evidence = []
        for index in range(13):
            evidence.append(
                {
                    "evidence_id": f"F01-H{index + 1:02d}",
                    "path": "tests/test_reader.py",
                    "kind": "text_hunk",
                    "header": f"@@ -{index + 1} +{index + 1} @@ test_case_{index + 1}",
                    "new_start": index + 1,
                    "additions": 1,
                    "deletions": 1,
                }
            )
        units = _scaffold_units({"evidence": evidence})
        self.assertEqual([len(unit["evidence"]) for unit in units], [12, 1])
        self.assertTrue(all(unit["lane"] == "supporting" for unit in units))

    def test_finalize_expands_compact_ids_and_renders_both_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            self._prepare_patch(output)
            shutil.copyfile(PIPELINE_DRAFT, output / "analysis-draft.json")
            report_path, warnings = finalize(output)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(warnings, [])
            self.assertEqual(report["units"][0]["id"], "U01")
            self.assertEqual([item["id"] for item in report["units"][0]["claims"]], ["CL01", "CL02"])
            self.assertEqual(report["units"][0]["checks"][0]["id"], "CK01")
            self.assertEqual(report["context_sources"][0]["id"], "C01")
            self.assertEqual(report["requirements"][0]["id"], "RQ01")
            self.assertEqual(report["outcome"]["unproven"][0]["refs"], ["U01"])
            self.assertEqual(report["outcome"]["recommendation"]["refs"], ["U01", "V01"])
            self.assertTrue((output / "review.md").exists())
            self.assertTrue((output / "review.html").exists())

    def test_outcome_derives_a_defect_from_unit_conclusion_without_finding(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            self._prepare_patch(output)
            draft = json.loads(PIPELINE_DRAFT.read_text(encoding="utf-8"))
            draft["units"][0]["conclusion"] = {
                "status": "defect",
                "statement": "The selected behavior violates its contract.",
            }
            draft["findings"] = []
            draft["recommendation"] = {
                "disposition": "request_changes",
                "reason": "The contract violation must be corrected.",
            }
            (output / "analysis-draft.json").write_text(json.dumps(draft), encoding="utf-8")
            report_path, _ = finalize(output)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["outcome"]["defects"], [
                {"statement": "The selected behavior violates its contract.", "refs": ["U01"]}
            ])
            self.assertEqual(report["outcome"]["recommendation"]["refs"], ["U01"])

    def test_prepare_commit_resolves_immutable_base_and_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            run(["git", "commit", "-am", "change"], repo)
            head = run(["git", "rev-parse", "HEAD"], repo)
            parent = run(["git", "rev-parse", "HEAD^"], repo)
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--commit", "HEAD", "--output", str(output)]
            )
            prepare(args)
            manifest = json.loads((output / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["report"]["base"], parent)
            self.assertEqual(manifest["report"]["head"], head)
            self.assertFalse(manifest["sources"][0]["mutable"])

    def test_prepare_root_commit_uses_the_empty_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--commit", "HEAD", "--output", str(output)]
            )
            prepare(args)
            inventory = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(inventory["files"][0]["status"], "added")

    def test_prepare_range_freezes_both_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            base = run(["git", "rev-parse", "HEAD"], repo)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            run(["git", "commit", "-am", "change"], repo)
            head = run(["git", "rev-parse", "HEAD"], repo)
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--range", f"{base}..{head}", "--output", str(output)]
            )
            prepare(args)
            manifest = json.loads((output / "source-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["report"]["base"], base)
            self.assertEqual(manifest["report"]["head"], head)
            self.assertEqual(manifest["sources"][0]["selector"], f"{base}..{head}")

    def test_pull_request_patch_requires_frozen_endpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            args = _parser().parse_args(
                [
                    "prepare",
                    "--patch",
                    str(PIPELINE_DIFF),
                    "--provenance",
                    "pull_request",
                    "--output",
                    str(output),
                ]
            )
            with self.assertRaisesRegex(SystemExit, "requires --base and --head"):
                prepare(args)

    def test_finalize_freezes_declared_context_from_exact_revision(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            run(["git", "commit", "-am", "change"], repo)
            base = run(["git", "rev-parse", "HEAD^"], repo)
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--commit", "HEAD", "--output", str(output)]
            )
            prepare(args)
            draft = json.loads(PIPELINE_DRAFT.read_text(encoding="utf-8"))
            draft["context_sources"][0].pop("excerpt")
            draft["context_sources"][0].update(
                {"snapshot": "base", "revision": base, "path": "value.txt", "start": 1, "lines": 1}
            )
            (output / "analysis-draft.json").write_text(json.dumps(draft), encoding="utf-8")
            report_path, _ = finalize(output)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["context_sources"][0]["revision"], base)
            self.assertEqual(report["context_sources"][0]["excerpt"], "old\n")
            self.assertEqual(report["context_sources"][0]["start_line"], 1)

    def test_redaction_hides_values_and_cleans_private_material_after_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patch = root / "secret.diff"
            secret = "fixture-secret-value"
            patch.write_text(
                "diff --git a/src/example.txt b/src/example.txt\n"
                "index 3367afd..3e75765 100644\n"
                "--- a/src/example.txt\n"
                "+++ b/src/example.txt\n"
                "@@ -1 +1 @@\n"
                "-old\n"
                f"+{secret}\n",
                encoding="utf-8",
            )
            redactions = root / "redactions.json"
            redactions.write_text(json.dumps({"values": [secret]}), encoding="utf-8")
            output = root / "review"
            args = _parser().parse_args(
                [
                    "prepare",
                    "--patch",
                    str(patch),
                    "--output",
                    str(output),
                    "--repository",
                    "fixture",
                    "--redactions",
                    str(redactions),
                ]
            )
            prepare(args)
            state = json.loads((output / "prepare-state.json").read_text(encoding="utf-8"))
            private_dir = Path(state["private_dir"])
            self.assertTrue(private_dir.exists())
            self.assertNotIn(secret, (output / "sources" / "source-01.diff").read_text(encoding="utf-8"))
            shutil.copyfile(PIPELINE_DRAFT, output / "analysis-draft.json")
            report_path, _ = finalize(output)
            report_text = report_path.read_text(encoding="utf-8")
            self.assertNotIn(secret, report_text)
            report = json.loads(report_text)
            self.assertEqual(report["coverage"]["redacted"], 1)
            self.assertFalse(private_dir.exists())
            final_state = json.loads((output / "prepare-state.json").read_text(encoding="utf-8"))
            self.assertTrue(final_state["private_cleaned"])

    def test_cleanup_removes_private_material_for_abandoned_review(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            patch = root / "secret.diff"
            patch.write_bytes(PIPELINE_DIFF.read_bytes().replace(b"+new", b"+fixture-secret"))
            redactions = root / "redactions.json"
            redactions.write_text(json.dumps({"values": ["fixture-secret"]}), encoding="utf-8")
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--patch", str(patch), "--output", str(output), "--redactions", str(redactions)]
            )
            prepare(args)
            state = json.loads((output / "prepare-state.json").read_text(encoding="utf-8"))
            private_dir = Path(state["private_dir"])
            self.assertTrue(cleanup(output))
            self.assertFalse(private_dir.exists())
            self.assertFalse(cleanup(output))

    def test_cleanup_refuses_unowned_directory_from_tampered_state(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "review"
            self._prepare_patch(output)
            target = root / "mandiff-private-target"
            target.mkdir()
            (target / ".mandiff-owner").write_text("forged", encoding="ascii")
            state_path = output / "prepare-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state.update({"private_dir": str(target), "private_token": "forged"})
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "invalid ManDiff private directory"):
                cleanup(output)
            self.assertTrue(target.exists())

    def test_semantic_key_cannot_shadow_evidence_id(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            self._prepare_patch(output)
            draft = json.loads(PIPELINE_DRAFT.read_text(encoding="utf-8"))
            draft["context_sources"][0]["key"] = "F01-H01"
            (output / "analysis-draft.json").write_text(json.dumps(draft), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "duplicate key"):
                finalize(output)

    def test_finalize_rejects_mutable_selector_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--unstaged", "--output", str(output)]
            )
            prepare(args)
            (repo / "value.txt").write_text("newer\n", encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "changed after prepare"):
                finalize(output)

    def test_uncommitted_tracks_an_initially_empty_staged_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--uncommitted", "--output", str(output)]
            )
            prepare(args)
            inventory = json.loads((output / "inventory.json").read_text(encoding="utf-8"))
            self.assertEqual(len(inventory["sources"]), 2)
            self.assertEqual(inventory["sources"][0]["display_bytes"], 0)
            run(["git", "add", "value.txt"], repo)
            with self.assertRaisesRegex(SystemExit, "changed after prepare"):
                finalize(output)

    def test_unchanged_uncommitted_selector_with_empty_source_can_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = self._git_repo(root)
            (repo / "value.txt").write_text("new\n", encoding="utf-8")
            output = root / "review"
            args = _parser().parse_args(
                ["prepare", "--repo", str(repo), "--uncommitted", "--output", str(output)]
            )
            prepare(args)
            draft = json.loads(PIPELINE_DRAFT.read_text(encoding="utf-8"))
            draft["context_sources"][0].update({"snapshot": "index", "revision": "INDEX"})
            (output / "analysis-draft.json").write_text(json.dumps(draft), encoding="utf-8")
            report_path, _ = finalize(output)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(len(report["source_artifacts"]), 2)
            self.assertEqual([item["drift"] for item in report["source_artifacts"]], ["unchanged", "unchanged"])

    def test_finalize_rejects_unresolved_scaffold(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            self._prepare_patch(output)
            with self.assertRaisesRegex(SystemExit, "Unresolved analysis placeholders"):
                finalize(output)

    def test_cli_prepare_and_finalize(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "review"
            prepare_process = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "mandiff.py"),
                    "prepare",
                    "--patch",
                    str(PIPELINE_DIFF),
                    "--output",
                    str(output),
                    "--repository",
                    "fixture",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(prepare_process.returncode, 0, prepare_process.stderr)
            shutil.copyfile(PIPELINE_DRAFT, output / "analysis-draft.json")
            finalize_process = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "mandiff.py"), "finalize", str(output)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(finalize_process.returncode, 0, finalize_process.stderr)
            self.assertIn("Finalized ManDiff review", finalize_process.stdout)


if __name__ == "__main__":
    unittest.main()
