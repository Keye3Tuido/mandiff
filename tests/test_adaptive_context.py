import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import mandiff
from render_markdown import render_markdown
from render_review import render_html
from validate_review import validate_report

FIXTURES = ROOT / "tests" / "fixtures"


class AdaptiveContextTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name) / "review"
        mandiff.prepare(mandiff._parser().parse_args([
            "prepare", "--patch", str(FIXTURES / "pipeline.diff"), "--output", str(self.output)
        ]))
        self.draft = json.loads((FIXTURES / "concise-draft.json").read_text())

    def finish(self):
        (self.output / "analysis-draft.json").write_text(json.dumps(self.draft))
        result, _ = mandiff.finalize(self.output)
        return json.loads(result.read_text())

    def test_concise_main_unit_preserves_context_and_exact_diff(self):
        report = self.finish()
        self.assertEqual(report["schema_version"], "1.6")
        self.assertEqual(validate_report(report), [])
        self.assertEqual(report["units"][0]["diff"], (FIXTURES / "pipeline.diff").read_text())
        self.assertEqual(report["coverage"]["missing"], 0)
        self.assertNotIn("guide", report["units"][0]["baseline"])
        self.assertNotIn("```mermaid", render_markdown(report))
        self.assertNotIn("no structured pre-change diagrams", render_markdown(report))
        self.assertTrue(report["units"][0]["checks"])
        self.assertTrue(report["context_sources"][0]["excerpt"])

    def test_views_expand_shared_evidence_and_preserve_state_and_sequence(self):
        self.draft["units"][0]["baseline"]["views"] = [
            {"kind": kind, "title": kind, "reason": "Answers this question", "context_refs": ["reader"],
             "rows": [{"from": "startup", "to": "read_value", "label": "Calls the reader"}]}
            for kind in ("table", "sequence", "state", "relationships")
        ]
        report = self.finish()
        for view in report["units"][0]["baseline"]["views"]:
            self.assertNotIn("context_refs", view)
            self.assertEqual(view["rows"][0]["context_refs"], ["C01"])
        self.assertIn("1. startup → read_value", render_markdown(report))
        self.assertIn("Before state", render_markdown(report))
        report["units"][0]["baseline"]["views"][0]["rows"][0]["context_refs"] = ["F01-H01"]
        self.assertTrue(any("baseline.context_refs" in error for error in validate_report(report)))

    def test_cannot_replace_frozen_context_with_a_view(self):
        report = self.finish()
        report["units"][0]["baseline"]["context_refs"] = []
        self.assertTrue(validate_report(report))
        with self.assertRaises(ValueError):
            render_markdown(report)

    def test_missing_claim_or_check_still_rejected(self):
        report = self.finish()
        report["units"][0]["checks"] = []
        self.assertTrue(any("checks" in error for error in validate_report(report)))

    def test_prepare_emits_help_without_mandatory_graph(self):
        scaffold = json.loads((self.output / "analysis-draft.json").read_text())
        self.assertNotIn("guide", scaffold["units"][0]["baseline"])
        help_data = json.loads((self.output / "authoring-help.json").read_text())
        self.assertIn("not_run", help_data["enums"]["verification.status"])
        self.assertIn("callee", help_data["enums"]["context_source.kind"])

    def test_reports_enum_errors_together_without_rewriting_draft(self):
        self.draft["context_sources"][0]["kind"] = "consumer"
        self.draft["units"][0]["invariants"] = [{"status": "unchanged", "statement": "x", "evidence_refs": []}]
        with self.assertRaises(SystemExit) as caught:
            self.finish()
        self.assertIn("context_sources[0].kind", str(caught.exception))
        self.assertIn("units[0].invariants[0].status", str(caught.exception))
        self.assertIn("preserved", str(caught.exception))
        self.assertEqual(json.loads((self.output / "analysis-draft.json").read_text()), self.draft)
        metrics = json.loads((self.output / "performance.json").read_text())
        self.assertEqual(metrics["finalize_attempts"][0]["status"], "failed")
        self.draft = json.loads((FIXTURES / "concise-draft.json").read_text())
        self.finish()
        metrics = json.loads((self.output / "performance.json").read_text())
        self.assertEqual([a["status"] for a in metrics["finalize_attempts"]], ["failed", "success"])
        self.assertGreaterEqual(metrics["prepare_to_first_finalize_seconds"], 0)
        self.assertIn("render_and_write", metrics["finalize_attempts"][-1]["stages_seconds"])

    def test_qualified_failure_reference_resolves_without_manual_repair(self):
        self.draft = json.loads((FIXTURES / "pipeline-draft.json").read_text())
        self.draft["findings"][0]["failure_refs"] = ["value-change.consumer-expectation"]
        report = self.finish()
        self.assertEqual(report["findings"][0]["failure_mode_ids"], ["FM01"])

    def test_unwritable_default_falls_back_but_explicit_path_is_respected(self):
        args = mandiff._parser().parse_args(["prepare", "--patch", str(FIXTURES / "pipeline.diff")])
        with patch.object(mandiff, "_prepare_output", side_effect=PermissionError):
            output = mandiff.prepare(args)
            self.addCleanup(shutil.rmtree, output)
            self.assertTrue((output / "analysis-draft.json").exists())
            args.output = self.output / "explicit"
            with self.assertRaisesRegex(SystemExit, "requested output"):
                mandiff.prepare(args)


if __name__ == "__main__":
    unittest.main()
