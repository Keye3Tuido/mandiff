import base64
import hashlib
import hmac
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compile_review.py"
FIXTURES = ROOT / "tests" / "fixtures"


class ReviewCompilerTests(unittest.TestCase):
    def run_command(self, *args):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *map(str, args)],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_inventory_compile_and_render_pipeline(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            inventory_path = output / "inventory.json"
            report_path = output / "review.json"
            html_path = output / "review.html"
            markdown_path = output / "review.md"

            inventory = self.run_command(
                "inventory", FIXTURES / "pipeline-manifest.json", inventory_path
            )
            self.assertEqual(inventory.returncode, 0, inventory.stderr)
            inventory_data = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(inventory_data["evidence"][0]["evidence_id"], "F01-H01")
            self.assertNotIn("diff_base64", inventory_data["sources"][0])

            compile_result = self.run_command(
                "compile", inventory_path, FIXTURES / "pipeline-analysis.json", report_path
            )
            self.assertEqual(compile_result.returncode, 0, compile_result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["units"][0]["title"], "更新存储值")
            self.assertEqual(report["units"][0]["diff"], (FIXTURES / "pipeline.diff").read_text())
            self.assertEqual(report["coverage"]["validated"], 1)

            rendered = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_review.py"),
                    str(report_path),
                    str(html_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            self.assertIn("更新存储值", html_path.read_text(encoding="utf-8"))
            markdown = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_markdown.py"),
                    str(report_path),
                    str(markdown_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(markdown.returncode, 0, markdown.stderr)
            markdown_text = markdown_path.read_text(encoding="utf-8")
            self.assertIn("更新存储值", markdown_text)
            self.assertIn("```diff", markdown_text)

    def test_compile_rejects_agent_authored_derived_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            inventory_path = output / "inventory.json"
            analysis_path = output / "analysis.json"
            self.assertEqual(
                self.run_command(
                    "inventory", FIXTURES / "pipeline-manifest.json", inventory_path
                ).returncode,
                0,
            )
            analysis = json.loads((FIXTURES / "pipeline-analysis.json").read_text())
            analysis["units"][0]["diff"] = "agent-authored"
            analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
            result = self.run_command("compile", inventory_path, analysis_path, output / "review.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("derived fields are forbidden", result.stderr)

    def test_compile_rejects_unassigned_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            inventory_path = output / "inventory.json"
            analysis_path = output / "analysis.json"
            self.assertEqual(
                self.run_command(
                    "inventory", FIXTURES / "pipeline-manifest.json", inventory_path
                ).returncode,
                0,
            )
            analysis = json.loads((FIXTURES / "pipeline-analysis.json").read_text())
            analysis["units"] = []
            analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
            result = self.run_command("compile", inventory_path, analysis_path, output / "review.json")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unassigned: F01-H01", result.stderr)

    def test_redacted_pipeline_keeps_original_hmac_and_safe_display(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            original_path = output / "original.diff"
            display_path = output / "display.diff"
            key_path = output / "review.key"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            report_path = output / "review.json"
            original = (FIXTURES / "pipeline.diff").read_bytes().replace(b"+new", b"+secret-value")
            display = original.replace(b"+secret-value", b"+[REDACTED]")
            private_key = b"fixture-private-key"
            original_path.write_bytes(original)
            display_path.write_bytes(display)
            key_path.write_bytes(private_key)
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0].update(
                {
                    "diff_path": str(display_path),
                    "redacted": True,
                    "original_diff_path": str(original_path),
                    "hmac_key_path": str(key_path),
                }
            )
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            self.assertEqual(
                self.run_command("inventory", manifest_path, inventory_path).returncode,
                0,
            )
            result = self.run_command(
                "compile", inventory_path, FIXTURES / "pipeline-analysis.json", report_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            embedded = report["source_artifacts"][0]["diff_base64"]
            self.assertNotIn("secret-value", base64.b64decode(embedded).decode())
            self.assertEqual(
                report["source_artifacts"][0]["diff_digest"],
                hmac.new(private_key, original, hashlib.sha256).hexdigest(),
            )
            self.assertEqual(report["evidence_ledger"][0]["state"], "redacted")

    def test_submodule_pointer_is_compiled_as_typed_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_path = output / "submodule.diff"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            analysis_path = output / "analysis.json"
            report_path = output / "review.json"
            diff_path.write_text(
                "diff --git a/vendor/library b/vendor/library\n"
                "index 1111111..2222222 160000\n"
                "--- a/vendor/library\n"
                "+++ b/vendor/library\n"
                "@@ -1 +1 @@\n"
                "-Subproject commit 1111111111111111111111111111111111111111\n"
                "+Subproject commit 2222222222222222222222222222222222222222\n",
                encoding="utf-8",
            )
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0]["diff_path"] = str(diff_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            analysis_text = (FIXTURES / "pipeline-analysis.json").read_text().replace(
                "F01-H01", "F01-SUBMODULE"
            )
            analysis_path.write_text(analysis_text, encoding="utf-8")

            self.assertEqual(
                self.run_command("inventory", manifest_path, inventory_path).returncode,
                0,
            )
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(inventory["evidence"][0]["kind"], "submodule")
            result = self.run_command("compile", inventory_path, analysis_path, report_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["units"][0]["diff"], "")
            self.assertEqual(report["units"][0]["diff_segments"], [])

    def test_inventory_counts_content_that_resembles_diff_markers(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_path = output / "operators.diff"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            diff_path.write_text(
                "diff --git a/src/operators.txt b/src/operators.txt\n"
                "--- a/src/operators.txt\n"
                "+++ b/src/operators.txt\n"
                "@@ -1 +1 @@\n"
                "---old-content\n"
                "+++new-content\n",
                encoding="utf-8",
            )
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0]["diff_path"] = str(diff_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_command("inventory", manifest_path, inventory_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(inventory["files"][0]["additions"], 1)
            self.assertEqual(inventory["files"][0]["deletions"], 1)

    def test_compile_rejects_a_changed_frozen_diff(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_path = output / "frozen.diff"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            diff_path.write_bytes((FIXTURES / "pipeline.diff").read_bytes())
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0]["diff_path"] = str(diff_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertEqual(
                self.run_command("inventory", manifest_path, inventory_path).returncode,
                0,
            )
            diff_path.write_bytes(diff_path.read_bytes().replace(b"+new", b"+changed"))
            result = self.run_command(
                "compile", inventory_path, FIXTURES / "pipeline-analysis.json", output / "review.json"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("frozen display diff changed", result.stderr)

    def test_inventory_preserves_dev_null_for_deleted_files(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_path = output / "deleted.diff"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            diff_path.write_text(
                "diff --git a/src/removed.txt b/src/removed.txt\n"
                "deleted file mode 100644\n"
                "--- a/src/removed.txt\n"
                "+++ /dev/null\n"
                "@@ -1 +0,0 @@\n"
                "-old\n",
                encoding="utf-8",
            )
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0]["diff_path"] = str(diff_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_command("inventory", manifest_path, inventory_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(inventory["files"][0]["path"], "src/removed.txt")
            self.assertEqual(inventory["files"][0]["status"], "deleted")
            self.assertEqual(inventory["evidence"][0]["new_path"], "")

    def test_inventory_uses_rename_metadata_for_paths_with_spaces(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            diff_path = output / "rename.diff"
            manifest_path = output / "manifest.json"
            inventory_path = output / "inventory.json"
            diff_path.write_text(
                'diff --git "a/old name.txt" "b/new name.txt"\n'
                "similarity index 100%\n"
                "rename from old name.txt\n"
                "rename to new name.txt\n",
                encoding="utf-8",
            )
            manifest = json.loads((FIXTURES / "pipeline-manifest.json").read_text())
            manifest["sources"][0]["diff_path"] = str(diff_path)
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            result = self.run_command("inventory", manifest_path, inventory_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            evidence = inventory["evidence"][0]
            self.assertEqual(evidence["kind"], "rename")
            self.assertEqual(evidence["old_path"], "old name.txt")
            self.assertEqual(evidence["new_path"], "new name.txt")


if __name__ == "__main__":
    unittest.main()
