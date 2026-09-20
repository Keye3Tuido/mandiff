import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from context_guide import mermaid
from mandiff import _parser, prepare, finalize
from render_markdown import render_markdown
from render_review import render_html
from validate_review import validate_report

TEMPLATE = (ROOT / "assets" / "review-explorer-template.html").read_text()

class ContextGuideTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        output = Path(cls.directory.name) / "review"
        fixtures = ROOT / "tests" / "fixtures"
        prepare(_parser().parse_args(["prepare", "--patch", str(fixtures / "context-guide.diff"), "--output", str(output)]))
        shutil.copyfile(fixtures / "context-guide-draft.json", output / "analysis-draft.json")
        report_path, warnings = finalize(output)
        assert not warnings, warnings
        cls.report = json.loads(report_path.read_text())

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.report = copy.deepcopy(type(self).report)
        self.unit = self.report["units"][0]
        self.guide = self.unit["baseline"]["guide"]
        self.execution = self.guide["execution"]

    def rejects(self, fragment):
        self.assertTrue(any(fragment in error for error in validate_report(self.report)), validate_report(self.report))

    def test_end_to_end_offline_output_and_source_links(self):
        self.assertEqual(validate_report(self.report), [])
        md = render_markdown(self.report)
        html = render_html(self.report, TEMPLATE)
        self.assertEqual(md.count("```mermaid"), 3)
        self.assertIn("[`C01`]", md)
        self.assertIn("(#context-c01)", md)
        self.assertIn("service.py:1", md)
        self.assertIn("调用栈依据源码推导，未实际运行", md)
        self.assertIn("const renderContextGuide", html)
        self.assertNotIn("/*__MANDIFF_CONTEXT_GUIDE__*/", html)
        self.assertNotIn('<script src=', html)
        self.assertNotIn('fetch("http', html)
        for source in self.report["context_sources"]:
            expected = (ROOT / "tests" / "fixtures" / "context-system" / source["path"]).read_text()
            self.assertEqual(source["excerpt"], expected)

    def test_requires_guide_for_new_main_units_but_renders_legacy(self):
        self.report["schema_version"] = "1.5"
        del self.unit["baseline"]["guide"]
        self.rejects("architecture and execution guide required")
        for version in ("1.3", "1.4"):
            self.report["schema_version"] = version
            self.assertEqual(validate_report(self.report), [])
            self.assertIn("no structured pre-change diagrams", render_markdown(self.report))
            self.assertIn("older report", render_html(self.report, TEMPLATE))

    def test_selected_graphs_preserve_scenario_and_stack_evidence(self):
        self.guide["views"] = ["structure"]
        self.assertEqual(validate_report(self.report), [])
        md = render_markdown(self.report)
        self.assertEqual(md.count("```mermaid"), 1)
        self.assertIn("调用栈依据源码推导，未实际运行", md)
        for scenario in self.execution["scenarios"]:
            self.assertIn(scenario["title"], md)
        # Hiding a graph never exempts its call evidence from validation.
        self.execution["scenarios"][0]["walkthrough"][1]["stack"] = ["load"]
        self.rejects("silently replace the stack root")

    def test_rejects_empty_unknown_and_duplicate_view_selection(self):
        for views in ([], ["invented"], ["structure", "structure"]):
            with self.subTest(views=views):
                self.guide["views"] = views
                self.assertTrue(validate_report(self.report))

    def test_rejects_changed_evidence_or_post_change_source_in_graph(self):
        self.guide["relations"][0]["context_refs"] = ["F01-H01"]
        self.rejects("baseline.context_refs")

    def test_rejects_unknown_endpoint_and_duplicate_node(self):
        self.guide["relations"][0]["to"] = "missing"
        self.guide["nodes"].append(copy.deepcopy(self.guide["nodes"][0]))
        self.rejects("unknown endpoint")
        self.rejects("duplicate node")

    def test_rejects_unreachable_flow_and_unexplained_branch(self):
        self.execution["steps"].append({"id": "orphan", "node": "load", "action": "Orphan", "context_refs": ["C02"]})
        self.rejects("unreachable")
        self.execution["transitions"].append({"from": "lookup", "to": "orphan", "kind": "branch", "label": "Extra branch", "context_refs": ["C02"]})
        self.rejects("every flow step")

    def test_rejects_walkthrough_jump_or_wrong_stack(self):
        walk = self.execution["scenarios"][1]["walkthrough"]
        del walk[2]
        self.rejects("missing flow transition")
        walk[1]["stack"] = ["request"]
        self.rejects("stack top")

    def test_rejects_false_synchronous_call_and_fabricated_stack_root(self):
        self.guide["relations"] = [r for r in self.guide["relations"] if (r["from"], r["to"]) != ("request", "load")]
        self.rejects("synchronous calls relation")
        self.execution["scenarios"][0]["walkthrough"][1]["stack"] = ["load"]
        self.rejects("silently replace the stack root")

    def test_async_starts_a_new_stack(self):
        walk = self.execution["scenarios"][1]["walkthrough"]
        self.assertEqual(walk[5]["stack"], ["tick"])
        walk[5]["stack"] = ["request", "tick"]
        self.rejects("async continuation")

    def test_loop_and_recursive_call_remain_representable(self):
        self.guide["relations"].append({"from": "load", "to": "load", "kind": "calls", "label": "Recursive call fixture", "context_refs": ["C02"]})
        self.execution["transitions"].append({"from": "lookup", "to": "lookup", "kind": "loop", "label": "Repeat fixture", "context_refs": ["C02"]})
        walk = self.execution["scenarios"][0]["walkthrough"]
        recursive = copy.deepcopy(walk[1])
        recursive["stack"].append("load")
        walk.insert(2, recursive)
        self.assertEqual(validate_report(self.report), [])

    def test_async_can_enter_the_same_function_as_a_new_invocation(self):
        self.guide["execution"] = {
            "status": "available", "reason": "Repeated task fixture", "entry": "first",
            "steps": [
                {"id": key, "node": "request", "action": key, "context_refs": ["C01"]}
                for key in ("first", "later")
            ],
            "transitions": [{"from": "first", "to": "later", "kind": "async", "label": "Run again later", "context_refs": ["C01"]}],
            "scenarios": [{"title": "Repeated task", "summary": "Same function, new invocation", "walkthrough": [
                {"step": key, "stack": ["request"], "explanation": key, "context_refs": ["C01"]}
                for key in ("first", "later")
            ]}],
        }
        self.assertEqual(validate_report(self.report), [])

    def test_non_executable_and_unknown_have_honest_limits(self):
        self.guide["execution"] = {"status": "not_applicable", "reason": "Only declarations are under review."}
        self.assertEqual(validate_report(self.report), [])
        self.assertNotIn("Source-derived stack illustration", render_markdown(self.report))
        self.guide["execution"]["status"] = "unknown"
        self.rejects("unproven unit")
        self.unit["conclusion"]["status"] = "unproven"
        self.assertEqual(validate_report(self.report), [])
        self.guide["execution"]["steps"] = self.execution["steps"]
        self.rejects("fabricated flow or stack")

    def test_schema_rejects_empty_stack_and_missing_evidence(self):
        self.execution["scenarios"][0]["walkthrough"][0]["stack"] = []
        self.assertTrue(validate_report(self.report))
        self.guide["nodes"][0]["context_refs"] = []
        self.assertTrue(validate_report(self.report))

    def test_diagram_labels_cannot_inject_mermaid_syntax(self):
        output = "\n".join(mermaid([{"id": 'bad"]', "label": '</script>"\nclick n0 "https://evil"'}], []))
        self.assertNotIn('</script>', output)
        self.assertNotIn('\nclick', output)
        self.assertNotIn('bad"]', output)
        self.assertIn('n0["', output)


if __name__ == "__main__":
    unittest.main()
