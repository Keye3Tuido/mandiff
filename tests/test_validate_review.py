import copy
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
sys.path.insert(0, str(ROOT / "scripts"))

from validate_review import review_digest, validate_report  # noqa: E402


FIXTURE = ROOT / "tests" / "fixtures" / "valid-review.json"


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.report = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_valid_fixture(self):
        self.assertEqual(validate_report(self.report), [])

    def test_missing_core_output_is_rejected(self):
        del self.report["outcome"]
        self.assertTrue(any("outcome" in error for error in validate_report(self.report)))

    def test_manifest_digest_mismatch_is_rejected(self):
        self.report["report"]["diff_digest"] = "0" * 64
        self.assertTrue(any("source manifest digest" in error for error in validate_report(self.report)))

    def test_manifest_digest_binds_source_order(self):
        first = {"id": "S01", "diff_digest": "a" * 64, "diff_bytes": 10}
        second = {"id": "S02", "diff_digest": "b" * 64, "diff_bytes": 20}
        self.assertNotEqual(review_digest([first, second]), review_digest([second, first]))

    def test_unknown_claim_reference_is_rejected(self):
        self.report["units"][0]["claims"][0]["evidence_refs"] = ["F99-H99"]
        self.assertTrue(any("unknown reference" in error for error in validate_report(self.report)))

    def test_tampered_displayed_diff_is_rejected(self):
        self.report["units"][0]["diff"] = self.report["units"][0]["diff"].replace("+new", "+tampered")
        errors = validate_report(self.report)
        self.assertTrue(any("exact evidence" in error or "not backed by frozen source" in error for error in errors))

    def test_reordered_diff_metadata_is_rejected(self):
        unit = self.report["units"][0]
        source = base64.b64decode(self.report["source_artifacts"][0]["diff_base64"])
        first = source.index(b"--- a/src/example.txt")
        second = source.index(b"+++ b/src/example.txt")
        hunk = source.index(b"@@ -1 +1 @@")
        unit["diff_segments"] = [
            {"source_artifact_id": "S01", "byte_start": 0, "byte_length": first},
            {"source_artifact_id": "S01", "byte_start": second, "byte_length": hunk - second},
            {"source_artifact_id": "S01", "byte_start": first, "byte_length": second - first},
            {"source_artifact_id": "S01", "byte_start": hunk, "byte_length": len(source) - hunk},
        ]
        unit["diff"] = b"".join(
            source[item["byte_start"]:item["byte_start"] + item["byte_length"]]
            for item in unit["diff_segments"]
        ).decode()
        self.assertTrue(any("source file metadata" in error for error in validate_report(self.report)))

    def test_coordinated_segments_cannot_omit_file_metadata(self):
        unit = self.report["units"][0]
        unit["diff_segments"] = [{"source_artifact_id": "S01", "byte_start": 91, "byte_length": 21}]
        unit["diff"] = "@@ -1 +1 @@\n-old\n+new"
        self.assertTrue(any("source file metadata" in error for error in validate_report(self.report)))

    def test_redacted_evidence_keeps_only_a_private_original_commitment(self):
        source = self.report["source_artifacts"][0]
        unit = self.report["units"][0]
        original_bytes = base64.b64decode(source["diff_base64"])
        original_hunk = original_bytes[91:112]
        private_key = b"fixture-only-private-key"
        safe_diff = unit["diff"].replace("+new", "+[REDACTED]")
        safe_bytes = safe_diff.encode()
        safe_hunk = b"@@ -1 +1 @@\n-old\n+[REDACTED]"
        source.update(
            {
                "diff_base64": base64.b64encode(safe_bytes).decode(),
                "diff_digest": hmac.new(private_key, original_bytes, hashlib.sha256).hexdigest(),
                "display_digest": hashlib.sha256(safe_bytes).hexdigest(),
                "display_bytes": len(safe_bytes),
                "redacted": True,
            }
        )
        unit["diff"] = safe_diff
        unit["diff_segments"][0]["byte_length"] = len(safe_bytes)
        anchor = unit["anchors"][0]
        anchor["byte_length"] = len(safe_hunk)
        anchor["fingerprint"] = hmac.new(private_key, original_hunk, hashlib.sha256).hexdigest()
        anchor["display_fingerprint"] = hashlib.sha256(safe_hunk).hexdigest()
        self.report["evidence_ledger"][0]["fingerprint"] = anchor["fingerprint"]
        self.report["evidence_ledger"][0]["byte_length"] = len(safe_hunk)
        self.report["evidence_ledger"][0]["display_fingerprint"] = anchor["display_fingerprint"]
        self.report["evidence_ledger"][0]["state"] = "redacted"
        self.report["report"]["diff_digest"] = review_digest(self.report["source_artifacts"])
        self.report["coverage"]["validated"] = 0
        self.report["coverage"]["redacted"] = 1
        self.assertNotIn(b"+new", base64.b64decode(source["diff_base64"]))
        self.assertNotEqual(source["diff_digest"], hashlib.sha256(original_bytes).hexdigest())
        self.assertEqual(validate_report(self.report), [])

    def test_anchor_cannot_validate_only_part_of_a_hunk(self):
        raw = base64.b64decode(self.report["source_artifacts"][0]["diff_base64"])
        anchor = self.report["units"][0]["anchors"][0]
        anchor["byte_length"] -= len("\n+new")
        partial = raw[anchor["byte_start"]:anchor["byte_start"] + anchor["byte_length"]]
        fingerprint = hashlib.sha256(partial).hexdigest()
        anchor["fingerprint"] = fingerprint
        self.report["evidence_ledger"][0]["fingerprint"] = fingerprint
        self.assertTrue(any("complete hunk body" in error for error in validate_report(self.report)))

    def test_malformed_capture_time_is_rejected(self):
        self.report["source_artifacts"][0]["captured_at"] = "not-a-date"
        self.assertTrue(any("RFC 3339" in error for error in validate_report(self.report)))

    def test_non_rfc3339_iso_variants_are_rejected(self):
        for value in ("2026-01-01T00:00:00+0000", "2026-W01-1T00:00:00+00:00"):
            with self.subTest(value=value):
                report = copy.deepcopy(self.report)
                report["source_artifacts"][0]["captured_at"] = value
                self.assertTrue(any("RFC 3339" in error for error in validate_report(report)))

    def test_mechanism_requires_three_steps(self):
        self.report["units"][0]["mechanism_steps"] = ["Only one step."]
        self.assertTrue(any("at least 3" in error for error in validate_report(self.report)))

    def test_supporting_context_unit_accepts_proportionate_analysis(self):
        unit = self.report["units"][0]
        unit["lane"] = "supporting"
        unit["importance"] = "context"
        unit["entry_points"] = []
        unit["call_path"] = []
        unit["mechanism_steps"] = ["Record the mechanical consequence of the selected hunk."]
        unit["invariants"] = []
        unit["consumers"] = []
        unit["compatibility"] = []
        unit["claims"] = []
        unit["failure_modes"] = []
        unit["unknowns"] = []
        unit["checks"] = []
        unit["finding_ids"] = []
        unit["verification_ids"] = []
        unit["completeness"] = {
            key: "complete" if key == "mechanism" else "not_applicable"
            for key in unit["completeness"]
        }
        for item in self.report["evidence_ledger"]:
            item["lane"] = "supporting"
            item["importance"] = "context"
        self.report["findings"] = []
        self.report["verification"] = []
        self.report["outcome"] = {
            "confirmed": [{"statement": "The mechanical change is present.", "refs": ["U01", "F01-H01"]}],
            "defects": [],
            "unproven": [],
            "recommendation": {"disposition": "accept", "reason": "No blocking issue found.", "refs": ["U01"]},
        }
        self.assertEqual(validate_report(self.report), [])
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            report_path = temporary / "supporting.json"
            report_path.write_text(json.dumps(self.report), encoding="utf-8")
            for renderer, suffix in (("render_markdown.py", ".md"), ("render_review.py", ".html")):
                output_path = temporary / f"supporting{suffix}"
                process = subprocess.run(
                    [sys.executable, str(ROOT / "scripts" / renderer), str(report_path), str(output_path)],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(process.returncode, 0, process.stderr)
                self.assertTrue(output_path.exists())

    def test_main_unit_still_requires_decision_grade_collections(self):
        self.report["units"][0]["claims"] = []
        self.assertTrue(any("U01.claims" in error for error in validate_report(self.report)))

    def test_discovered_evidence_may_remain_unassigned(self):
        self.report["units"] = []
        self.report["files"][0]["unit_ids"] = []
        self.report["findings"] = []
        self.report["verification"] = []
        self.report["outcome"] = {
            "confirmed": [],
            "defects": [],
            "unproven": [{"statement": "The evidence has not been assigned to a review unit.", "refs": ["F01-H01"]}],
            "recommendation": {"disposition": "expand_scope", "reason": "Complete evidence assignment.", "refs": ["F01-H01"]},
        }
        self.report["evidence_ledger"][0].update(
            {"unit_id": None, "lane": None, "importance": None, "state": "discovered"}
        )
        self.report["summary"]["evidence_validated"] = 0
        self.report["coverage"] = {
            "total": 1,
            "assigned_once": 0,
            "presented_once": 0,
            "validated": 0,
            "redacted": 0,
            "missing": 1,
            "duplicated": 0,
            "unknown": 0,
        }
        self.assertEqual(validate_report(self.report), [])

    def test_duplicate_evidence_owner_is_rejected(self):
        duplicate = copy.deepcopy(self.report["units"][0])
        duplicate["id"] = "U02"
        duplicate["order"] = 2
        duplicate["title"] = "Duplicate owner"
        duplicate["claims"][0]["id"] = "CL03"
        duplicate["claims"][1]["id"] = "CL04"
        duplicate["failure_modes"][0]["id"] = "FM02"
        duplicate["failure_modes"][0]["claim_ids"] = ["CL03", "CL04"]
        duplicate["checks"][0]["id"] = "C2"
        duplicate["checks"][0]["claim_ids"] = ["CL03", "CL04"]
        duplicate["finding_ids"] = []
        duplicate["verification_ids"] = []
        self.report["units"].append(duplicate)
        self.report["files"][0]["unit_ids"].append("U02")
        self.assertTrue(any("ownership" in error or "duplicate evidence anchor" in error for error in validate_report(self.report)))

    def test_renderer_validates_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            invalid_path = temporary / "invalid.json"
            output_path = temporary / "review.html"
            del self.report["requirements"]
            invalid_path.write_text(json.dumps(self.report), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "render_review.py"), str(invalid_path), str(output_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(process.returncode, 0)
            self.assertFalse(output_path.exists())
            self.assertIn("requirements", process.stderr)

    def test_renderer_embeds_a_valid_report(self):
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "nested" / "review.html"
            process = subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "render_review.py"), str(FIXTURE), str(output_path)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            rendered = output_path.read_text(encoding="utf-8")
            self.assertIn('"schema_version":"1.3"', rendered)
            self.assertNotIn('{"__replace_with_mandiff_report__":true}', rendered)

    def test_review_template_keeps_diff_as_the_primary_workspace(self):
        template = (ROOT / "assets" / "review-explorer-template.html").read_text(encoding="utf-8")
        self.assertIn("grid-template-columns: 280px minmax(0, 1fr)", template)
        self.assertIn('class="diff-panel"', template)
        self.assertIn('class="review-panel"', template)
        self.assertLess(template.index('class="diff-panel"'), template.index('class="review-panel"'))
        self.assertIn("max-height: min(72vh, 920px)", template)
        self.assertIn('data-line="${index + 1}"', template)
        self.assertIn("const LONG_LINE_LIMIT = 2000", template)
        self.assertIn('data-expand-line="${index}"', template)
        self.assertIn("if (renderKey === renderedDiffKey) return", template)
        self.assertIn('<summary>Report evidence map</summary>', template)
        self.assertNotIn("max-width: 1320px", template)
        self.assertNotIn('class="review-grid"', template)

    def test_review_template_highlights_code_without_external_dependencies(self):
        template = (ROOT / "assets" / "review-explorer-template.html").read_text(encoding="utf-8")
        self.assertIn("const EXTENSION_LANGUAGES", template)
        self.assertIn("const syntaxHighlight", template)
        self.assertIn("const narrativeHtml", template)
        self.assertIn("const unitSymbols", template)
        self.assertIn("tok-keyword", template)
        self.assertIn("tok-string", template)
        self.assertIn("tok-comment", template)
        self.assertNotIn("cdnjs.cloudflare.com", template)
        self.assertNotIn("unpkg.com", template)
        self.assertNotIn("cdn.jsdelivr.net", template)

    def test_review_template_decodes_and_navigates_evidence_references(self):
        template = (ROOT / "assets" / "review-explorer-template.html").read_text(encoding="utf-8")
        self.assertIn("const anchorLocation", template)
        self.assertIn('data-evidence-id="${escapeHtml(id)}"', template)
        self.assertIn("const selectEvidence", template)
        self.assertIn("entry.query || ''", template)


if __name__ == "__main__":
    unittest.main()
