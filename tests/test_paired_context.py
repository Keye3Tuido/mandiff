import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from mandiff import _parser, prepare, finalize, _lint_warnings
from render_markdown import render_markdown
from validate_review import validate_report


class PairedContextTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.output = Path(self.directory.name) / "review"
        prepare(_parser().parse_args(["prepare", "--patch", str(ROOT / "tests/fixtures/pipeline.diff"), "--output", str(self.output)]))
        self.draft = json.loads((ROOT / "tests/fixtures/paired-draft.json").read_text())

    def finish(self):
        (self.output / "analysis-draft.json").write_text(json.dumps(self.draft))
        report_path, _ = finalize(self.output)
        return json.loads(report_path.read_text())

    def test_both_sides_and_same_input_comparison_precede_exact_diff(self):
        report = self.finish()
        self.assertEqual(report["schema_version"], "1.7")
        self.assertEqual(validate_report(report), [])
        self.assertEqual(report["units"][0]["post_change"]["context_refs"], ["C02"])
        self.assertEqual(report["units"][0]["comparison"][0]["after_context_refs"], ["C02"])
        md = render_markdown(report)
        self.assertLess(md.index("### Original logic"), md.index("### System after"))
        self.assertLess(md.index("### System after"), md.index("### Same-input comparison"))
        self.assertEqual(report["units"][0]["diff"], (ROOT / "tests/fixtures/pipeline.diff").read_text())

    def test_new_draft_cannot_fall_back_to_after_summary(self):
        del self.draft["units"][0]["post_change"]
        del self.draft["units"][0]["comparison"]
        with self.assertRaisesRegex(SystemExit, "post_change"):
            self.finish()

    def test_supporting_unit_can_supply_only_the_relevant_context_side(self):
        for side in ("baseline", "post_change"):
            with self.subTest(side=side):
                report = self.finish()
                unit = report["units"][0]
                unit["lane"] = "supporting"
                report["evidence_ledger"][0]["lane"] = "supporting"
                del unit["post_change" if side == "baseline" else "baseline"]
                del unit["comparison"]
                self.assertEqual(validate_report(report), [])
                # Optional context must still cite the correct version.
                source_id = unit[side]["context_refs"][0]
                source = next(item for item in report["context_sources"] if item["id"] == source_id)
                source["side"] = "after" if side == "baseline" else "before"
                self.assertTrue(any("snapshot and revision" in error for error in validate_report(report)))

    def test_comparison_must_have_inputs_and_both_evidence_sets(self):
        report = self.finish()
        del report["units"][0]["comparison"][0]["input"]
        self.assertTrue(validate_report(report))
        report = self.finish()
        report["units"][0]["comparison"][0]["after_context_refs"] = ["C01"]
        self.assertTrue(any("comparison.after_context_refs" in e for e in validate_report(report)))

    def test_cannot_relabel_before_excerpt_as_after_or_tamper_with_it(self):
        report = self.finish()
        report["context_sources"][1]["side"] = "before"
        self.assertTrue(any("after snapshot" in e for e in validate_report(report)))
        report = self.finish()
        report["context_sources"][1]["excerpt"] += "tampered"
        self.assertTrue(any("post_change" in e and "fingerprint" in e for e in validate_report(report)))

    def test_git_context_matches_each_selected_revision_and_snapshot(self):
        for provenance, before_snapshot, after_snapshot, base, head in (
            ("commit", "base", "head", "a" * 40, "b" * 40),
            ("staged", "head", "index", "a" * 40, "INDEX"),
            ("unstaged", "index", "working_tree", "INDEX", "WORKTREE"),
        ):
            with self.subTest(provenance=provenance):
                report = self.finish()
                report["source_artifacts"][0].update(provenance=provenance, base=base, head=head)
                report["units"][0]["anchors"][0]["provenance"] = provenance
                for source, snapshot, revision in zip(report["context_sources"], (before_snapshot, after_snapshot), (base, head)):
                    source.update(snapshot=snapshot, revision=revision)
                errors = validate_report(report)
                self.assertFalse(any("snapshot and revision" in e or "context for" in e for e in errors), errors)
                report["context_sources"][1]["revision"] = "wrong-version"
                self.assertTrue(any("post_change" in e and "revision" in e for e in validate_report(report)))

    def test_post_change_views_use_only_post_change_evidence(self):
        self.draft["units"][0]["post_change"]["views"] = [{
            "kind": "sequence", "title": "改动后的读取", "reason": "跟随同一个输入。",
            "context_refs": ["reader-after"],
            "rows": [{"from": "startup", "to": "read_value", "label": "返回新文本"}],
        }]
        report = self.finish()
        self.assertEqual(validate_report(report), [])
        report["units"][0]["post_change"]["views"][0]["rows"][0]["context_refs"] = ["C01"]
        self.assertTrue(any("post_change.views" in e for e in validate_report(report)))

    def test_missing_after_representation_is_reported_without_forcing_quotas(self):
        unit = self.draft["units"][0]
        unit["baseline"]["views"] = [{"kind": "table"}]
        self.assertTrue(any("original forms absent" in warning for warning in _lint_warnings(self.draft)))
        unit["post_change"]["views"] = [{"kind": "table"}, {"kind": "sequence"}]
        self.assertFalse(any("original forms absent" in warning for warning in _lint_warnings(self.draft)))

    def test_post_change_graph_retains_stack_validation(self):
        self.draft = json.loads((ROOT / "tests/fixtures/context-guide-draft.json").read_text())
        self.draft["schema_version"] = "2.1"
        self.output = Path(self.directory.name) / "guide"
        prepare(_parser().parse_args(["prepare", "--patch", str(ROOT / "tests/fixtures/context-guide.diff"), "--output", str(self.output)]))
        for source in self.draft["context_sources"]:
            source["side"] = "before"
        after = copy.deepcopy(self.draft["context_sources"])
        for source in after:
            source["key"] += "-after"
            source["side"] = "after"
            source["revision"] = "changed-fixture"
        self.draft["context_sources"].extend(after)
        unit = self.draft["units"][0]
        # Rename references in a copied guide without duplicating the walkthrough contract.
        def refs(value):
            if isinstance(value, dict):
                return {k: [v + "-after" for v in items] if k == "context_refs" else refs(items) for k, items in value.items()}
            if isinstance(value, list):
                return [refs(item) for item in value]
            return value
        unit["post_change"] = refs(unit["baseline"])
        unit["comparison"] = [{"scenario": "fixture", "input": "same request", "before": "original", "after": "changed", "impact": "fixture only", "before_context_refs": ["app"], "after_context_refs": ["app-after"]}]
        report = self.finish()
        self.assertEqual(validate_report(report), [])
        report["units"][0]["post_change"]["guide"]["execution"]["scenarios"][0]["walkthrough"][1]["stack"] = ["request"]
        self.assertTrue(any("post_change.guide" in e and "stack top" in e for e in validate_report(report)))


if __name__ == "__main__":
    unittest.main()
