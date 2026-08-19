#!/usr/bin/env python3
"""Render a validated ManDiff report as a portable Markdown audit record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_review import validate_report


def _cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return str(value if value not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def _bullets(items: list[Any], empty: str = "None.") -> list[str]:
    if not items:
        return [empty]
    result = []
    for item in items:
        if isinstance(item, dict):
            statement = item.get("statement", "")
            refs = item.get("refs", [])
            suffix = f" ({', '.join(refs)})" if refs else ""
            result.append(f"- {statement}{suffix}")
        else:
            result.append(f"- {item}")
    return result


def render_markdown(report: dict[str, Any]) -> str:
    errors = validate_report(report)
    if errors:
        raise ValueError("Invalid ManDiff report:\n- " + "\n- ".join(errors))

    lines: list[str] = ["# ManDiff Review", "", "## Review outcome", ""]
    outcome = report["outcome"]
    for title, key in (("Confirmed", "confirmed"), ("Defects", "defects"), ("Unproven", "unproven")):
        lines.extend([f"### {title}", "", *_bullets(outcome[key]), ""])
    recommendation = outcome["recommendation"]
    lines.extend(
        [
            "### Recommendation",
            "",
            f"**{recommendation['disposition']}**: {recommendation['reason']} "
            f"({', '.join(recommendation['refs'])})",
            "",
            "## Review target",
            "",
        ]
    )
    meta = report["report"]
    lines.extend(
        [
            f"- Selector: `{meta['selector']}`",
            f"- Repository: `{meta['repository']}`",
            f"- Aggregate base/head: `{meta.get('base', '-')}` / `{meta.get('head', '-')}`",
            f"- Source artifacts: {', '.join(meta['source_artifact_ids'])}",
            f"- Review digest: `{meta['diff_digest']}` ({meta['diff_bytes']} bytes)",
            f"- Mutable selector: {'yes' if meta['mutable'] else 'no'}",
            f"- Drift: `{meta['drift']}`",
            f"- Scope exclusions: {_cell(meta['scope_exclusions'])}",
            "",
            "| Source | Provenance | Selector | Acquisition | Base / head | Captured | Digest / bytes | Drift |",
            "|---|---|---|---|---|---|---|---|",
        ]
    )
    for source in report["source_artifacts"]:
        lines.append(
            "| "
            + " | ".join(
                _cell(value)
                for value in (
                    source["id"],
                    source["provenance"],
                    source["selector"],
                    source["acquisition"],
                    f"{source['base']} / {source['head']}",
                    source["captured_at"],
                    f"{source['diff_digest']} / {source['diff_bytes']}",
                    source["drift"],
                )
            )
            + " |"
        )

    summary = report["summary"]
    kind_counts: dict[str, int] = {}
    lane_counts: dict[str, int] = {}
    for item in report["evidence_ledger"]:
        kind_counts[item["kind"]] = kind_counts.get(item["kind"], 0) + 1
        lane_counts[item["lane"]] = lane_counts.get(item["lane"], 0) + 1
    lines.extend(
        [
            "",
            "## Overall change map",
            "",
            "### Purpose",
            "",
            *(
                _bullets(outcome["confirmed"], "No behavior is confirmed by the selected evidence.")
            ),
            "",
            "### Scale",
            "",
            "| Metric | Value |",
            "|---|---:|",
            f"| Files | {summary['files']} |",
            f"| Text hunks | {summary['hunks']} |",
            f"| Additions | {summary['additions']} |",
            f"| Deletions | {summary['deletions']} |",
            f"| Renames | {kind_counts.get('rename', 0)} |",
            f"| Binary entries | {kind_counts.get('binary', 0)} |",
            f"| Submodule entries | {kind_counts.get('submodule', 0)} |",
            f"| Main-path evidence | {lane_counts.get('main', 0)} |",
            f"| Supporting evidence | {lane_counts.get('supporting', 0)} |",
            "",
            "### Behavioral themes",
            "",
            *[f"- {unit['title']}" for unit in report["units"]],
            "",
            "### Dependency flow",
            "",
            *[
                f"- {unit['id']} depends on {_cell(unit['depends_on'])}."
                for unit in report["units"]
            ],
            "",
            "### Risk hotspots",
            "",
            *(
                [
                    f"- {item['unit_id']} / {item['id']} (`{item.get('severity', 'none')}`): "
                    f"{item['description']}"
                    for item in report["findings"]
                ]
                or ["None identified in the selected evidence."]
            ),
            "",
            "### Review plan",
            "",
            "| Step | Lane | Importance | Review unit | Evidence | Main question |",
            "|---:|---|---|---|---|---|",
        ]
    )
    for unit in report["units"]:
        lines.append(
            f"| {unit['order']} | {_cell(unit['lane'])} | {_cell(unit['importance'])} | "
            f"{_cell(unit['title'])} | {_cell(unit['evidence_ids'])} | {_cell(unit['question'])} |"
        )

    findings_by_unit: dict[str, list[dict[str, Any]]] = {}
    for finding in report["findings"]:
        findings_by_unit.setdefault(finding["unit_id"], []).append(finding)
    total_units = len(report["units"])
    for unit in report["units"]:
        lines.extend(
            [
                "",
                f"## Step {unit['order']}/{total_units}: {unit['title']}",
                "",
                f"**Review question:** {unit['question']}",
                "",
                f"**Behavior contract:** {unit['contract']}",
                "",
                f"**Background:** {unit['background']}",
                "",
                f"**Before:** {unit['before']}",
                "",
                f"**After:** {unit['after']}",
                "",
                "### Entry point and call path",
                "",
                f"- Entry points: {_cell(unit['entry_points'])}",
                f"- Call path: {' -> '.join(unit['call_path'])}",
                "",
                "### Affected surface",
                "",
                f"- Evidence: {_cell(unit['evidence_ids'])}",
                f"- Lane / importance: `{unit['lane']}` / `{unit['importance']}`",
                f"- Files: {_cell(unit['files'])}",
                f"- Symbols: {_cell(unit['symbols'])}",
                f"- Depends on: {_cell(unit['depends_on'])}",
                "",
                "### Hunk map",
                "",
                "| Evidence | Stable anchor | Role |",
                "|---|---|---|",
            ]
        )
        for anchor in unit["anchors"]:
            stable = f"{anchor['provenance']}, {anchor['path']}, {anchor['header'] or anchor['kind']}"
            lines.append(
                f"| {_cell(anchor['evidence_id'] + ' · ' + anchor['label'])} | "
                f"{_cell(stable)} | {_cell(anchor['summary'])} |"
            )
        lines.extend(["", "### Mechanism walkthrough", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(unit["mechanism_steps"], start=1))
        lines.extend(["", "### Invariants, consumers, and compatibility", ""])
        for invariant in unit["invariants"]:
            lines.append(
                f"- `{invariant['status']}` {invariant['statement']} ({_cell(invariant['evidence_refs'])})"
            )
        lines.extend(
            [
                f"- Consumers: {_cell(unit['consumers'])}",
                f"- Compatibility: {_cell(unit['compatibility'])}",
                "",
                "### Claims and evidence",
                "",
                "| Claim | Kind | Statement | Evidence | Confidence |",
                "|---|---|---|---|---|",
            ]
        )
        for claim in unit["claims"]:
            lines.append(
                f"| {_cell(claim['id'])} | {_cell(claim['kind'])} | {_cell(claim['statement'])} | "
                f"{_cell(claim['evidence_refs'])} | {_cell(claim['confidence'])} |"
            )
        lines.extend(["", "### Exact diff", ""])
        if unit["diff"]:
            lines.extend(["```diff", unit["diff"], "```"])
        else:
            lines.append("Typed non-text evidence: " + _cell(unit["evidence_ids"]) + ".")
        lines.extend(
            [
                "",
                "### Human review checks",
                "",
                "| Check | Setup | Action | Expected result | Claims |",
                "|---|---|---|---|---|",
            ]
        )
        for check in unit["checks"]:
            lines.append(
                f"| {_cell(check['id'] + ' · ' + check['label'])} | {_cell(check['setup'])} | "
                f"{_cell(check['action'])} | {_cell(check['expected'])} | {_cell(check['claim_ids'])} |"
            )
        lines.extend(["", "### Failure modes and unknowns", ""])
        for failure in unit["failure_modes"]:
            lines.append(
                f"- `{failure['id']}` {failure['trigger']} -> {failure['effect']} -> "
                f"{failure['detection_or_mitigation']} ({_cell(failure['evidence_refs'])})"
            )
        lines.extend(f"- Unknown: {item}" for item in unit["unknowns"])
        lines.extend(["", "### Findings", ""])
        for finding in findings_by_unit.get(unit["id"], []):
            lines.append(
                f"- `{finding['category']}` `{finding.get('severity', 'none')}` "
                f"{finding['id']}: {finding['description']}"
            )
        if not findings_by_unit.get(unit["id"]):
            lines.append("None.")
        conclusion = unit["conclusion"]
        lines.extend(
            [
                "",
                "### Unit conclusion",
                "",
                f"**{conclusion['status']}**: {conclusion['statement']} "
                f"({_cell(conclusion['evidence_refs'])})",
            ]
        )

    lines.extend(["", "## End-to-end synthesis", ""])
    lines.extend(
        f"- {unit['id']} {unit['title']}: {unit['conclusion']['statement']}"
        for unit in report["units"]
    )
    lines.extend(["", "## Findings and open questions", ""])
    if report["findings"]:
        for finding in report["findings"]:
            lines.append(
                f"- `{finding['category']}` `{finding.get('severity', 'none')}` "
                f"{finding['id']} / {finding['unit_id']}: {finding['description']}"
            )
    else:
        lines.append("None.")
    lines.extend(
        [
            "",
            "## Verification matrix",
            "",
            "| Behavior | Existing evidence | Setup / action / expected | Status |",
            "|---|---|---|---|",
        ]
    )
    for item in report["verification"]:
        check = f"{item['setup']} / {item['action']} / {item['expected']}"
        lines.append(
            f"| {_cell(item['behavior'])} | {_cell(item.get('existing_evidence', '-'))} | "
            f"{_cell(check)} | {_cell(item['status'])} |"
        )
    coverage = report["coverage"]
    lines.extend(
        [
            "",
            "## Coverage report",
            "",
            "| Coverage item | Count |",
            "|---|---:|",
            f"| Total evidence IDs | {coverage['total']} |",
            f"| Assigned exactly once | {coverage['assigned_once']} |",
            f"| Presented exactly once | {coverage['presented_once']} |",
            f"| Byte-validated | {coverage['validated']} |",
            f"| Explicitly redacted | {coverage['redacted']} |",
            f"| Missing | {coverage['missing']} |",
            f"| Duplicated | {coverage['duplicated']} |",
            f"| Unknown | {coverage['unknown']} |",
            "",
            f"Frozen diff digest: `{meta['diff_digest']}`. Drift check: `{meta['drift']}`.",
            "",
            "Evidence coverage does not imply human approval.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
        markdown = render_markdown(report)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(markdown, encoding="utf-8")


if __name__ == "__main__":
    main()
