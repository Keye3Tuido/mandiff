#!/usr/bin/env python3
"""Render a validated ManDiff report as a portable Markdown audit record."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from validate_review import validate_report
from context_guide import guide_markdown


def _cell(value: Any) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    return str(value if value not in (None, "") else "-").replace("|", "\\|").replace("\n", " ")


def _anchor_location(anchor: dict[str, Any]) -> str:
    path = anchor.get("path") or anchor.get("new_path") or anchor.get("old_path") or anchor.get("kind", "evidence")
    if anchor.get("kind") == "text_hunk":
        line = anchor.get("new_start")
        if line is None:
            line = anchor.get("old_start")
        if line is not None:
            return f"{path}:{line}"
    return str(path)


def _reference_catalog(report: dict[str, Any]) -> tuple[dict[str, str], set[str]]:
    catalog: dict[str, str] = {}
    changed_evidence: set[str] = set()
    for unit in report["units"]:
        catalog[unit["id"]] = unit["title"]
        for anchor in unit["anchors"]:
            evidence_id = anchor["evidence_id"]
            catalog[evidence_id] = f"{_anchor_location(anchor)} · {anchor['summary']}"
            changed_evidence.add(evidence_id)
        for claim in unit["claims"]:
            catalog[claim["id"]] = claim["statement"]
        for failure in unit["failure_modes"]:
            catalog[failure["id"]] = f"{failure['trigger']} -> {failure['effect']}"
        for check in unit["checks"]:
            catalog[check["id"]] = check["label"]
    for source in report["context_sources"]:
        path = source["path"] + (f":{source['start_line']}" if source.get("start_line") else "")
        parts = [path, source.get("locator"), source.get("summary")]
        catalog[source["id"]] = " · ".join(str(part) for part in parts if part)
    for requirement in report["requirements"]:
        catalog[requirement["id"]] = requirement["statement"]
    for finding in report["findings"]:
        catalog[finding["id"]] = finding["description"]
    for verification in report["verification"]:
        catalog[verification["id"]] = verification["behavior"]
    return catalog, changed_evidence


def _reference(identifier: str, catalog: dict[str, str], changed_evidence: set[str]) -> str:
    rendered_id = f"`{identifier}`"
    if identifier in changed_evidence:
        rendered_id = f"[{rendered_id}](#evidence-{identifier.lower()})"
    elif identifier.startswith("C") and identifier[1:].isdigit():
        rendered_id = f"[{rendered_id}](#context-{identifier.lower()})"
    description = catalog.get(identifier)
    return f"{rendered_id} · {description}" if description else rendered_id


def _references(identifiers: list[str], catalog: dict[str, str], changed_evidence: set[str]) -> str:
    if not identifiers:
        return "None"
    return "; ".join(_reference(identifier, catalog, changed_evidence) for identifier in identifiers)


def _bullets(items: list[Any], empty: str = "None.", format_refs=None) -> list[str]:
    if not items:
        return [empty]
    result = []
    for item in items:
        if isinstance(item, dict):
            statement = item.get("statement", "")
            refs = item.get("refs", [])
            rendered_refs = format_refs(refs) if format_refs else ", ".join(refs)
            suffix = f" ({rendered_refs})" if refs else ""
            result.append(f"- {statement}{suffix}")
        else:
            result.append(f"- {item}")
    return result


def _baseline(unit: dict[str, Any]) -> dict[str, Any]:
    if unit.get("baseline"):
        return unit["baseline"]
    contextual_refs = []
    for claim in unit.get("claims", []):
        contextual_refs.extend(ref for ref in claim.get("evidence_refs", []) if ref.startswith("C"))
    return {
        "architecture": unit.get("background", "Unknown"),
        "responsibilities": unit.get("consumers", []),
        "flow_steps": unit.get("call_path", []) or unit.get("mechanism_steps", []),
        "data_and_state": [item.get("statement", "") for item in unit.get("invariants", [])],
        "context_refs": list(dict.fromkeys(contextual_refs)),
    }


def _fenced(value: str) -> list[str]:
    fence = "```"
    while fence in value:
        fence += "`"
    return [fence, value.rstrip("\n"), fence]


def render_markdown(report: dict[str, Any]) -> str:
    errors = validate_report(report)
    if errors:
        raise ValueError("Invalid ManDiff report:\n- " + "\n- ".join(errors))

    reference_catalog, changed_evidence = _reference_catalog(report)
    format_refs = lambda refs: _references(refs, reference_catalog, changed_evidence)
    lines: list[str] = ["# ManDiff Review", "", "## Review outcome", ""]
    outcome = report["outcome"]
    for title, key in (("Confirmed", "confirmed"), ("Defects", "defects"), ("Unproven", "unproven")):
        lines.extend([f"### {title}", "", *_bullets(outcome[key], format_refs=format_refs), ""])
    recommendation = outcome["recommendation"]
    lines.extend(
        [
            "### Recommendation",
            "",
            f"**{recommendation['disposition']}**: {recommendation['reason']} "
            f"({format_refs(recommendation['refs'])})",
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
                _bullets(
                    outcome["confirmed"],
                    "No behavior is confirmed by the selected evidence.",
                    format_refs,
                )
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
                f"- {_reference(unit['id'], reference_catalog, changed_evidence)} depends on "
                f"{format_refs(unit['depends_on'])}."
                for unit in report["units"]
            ],
            "",
            "### Risk hotspots",
            "",
            *(
                [
                    f"- {_reference(item['unit_id'], reference_catalog, changed_evidence)} / "
                    f"{_reference(item['id'], reference_catalog, changed_evidence)} "
                    f"(`{item.get('severity', 'none')}`)"
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
            f"{_cell(unit['title'])} | {_cell(format_refs(unit['evidence_ids']))} | {_cell(unit['question'])} |"
        )

    findings_by_unit: dict[str, list[dict[str, Any]]] = {}
    for finding in report["findings"]:
        findings_by_unit.setdefault(finding["unit_id"], []).append(finding)
    total_units = len(report["units"])
    context_by_id = {item["id"]: item for item in report["context_sources"]}
    context_anchors = set()
    for unit in report["units"]:
        baseline = _baseline(unit)
        lines.extend(
            [
                "",
                f"## Step {unit['order']}/{total_units}: {unit['title']}",
                "",
                "### Original logic before this change",
                "",
                f"**Architecture:** {baseline['architecture']}",
                "",
                "**Responsibilities:**",
                "",
                *_bullets(baseline.get("responsibilities", [])),
                "",
                "**Original flow:**",
                "",
                *[
                    f"{index}. {step}"
                    for index, step in enumerate(baseline.get("flow_steps", []), start=1)
                ],
                "",
                "**Data and state:**",
                "",
                *_bullets(baseline.get("data_and_state", [])),
                "",
                f"**Frozen context:** {format_refs(baseline.get('context_refs', []))}",
                "",
            ]
        )
        if baseline.get("guide"):
            lines.extend(guide_markdown(baseline["guide"], format_refs, _cell))
        else:
            lines.extend(["This report has no structured pre-change diagrams or source-derived stack walkthrough.", ""])
        for context_id in baseline.get("context_refs", []):
            source = context_by_id.get(context_id)
            if not source or not source.get("excerpt"):
                continue
            lines.extend(
                [
                    f'<a id="context-{context_id.lower()}"></a>' if context_id not in context_anchors else "",
                    f"#### {_reference(context_id, reference_catalog, changed_evidence)}",
                    "",
                    f"Snapshot: `{source['snapshot']}` at `{source['revision']}`",
                    "",
                    *_fenced(source["excerpt"]),
                    "",
                ]
            )
            context_anchors.add(context_id)
        lines.extend(
            [
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
                f"- Evidence: {format_refs(unit['evidence_ids'])}",
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
            evidence_anchor = f'<a id="evidence-{anchor["evidence_id"].lower()}"></a>'
            lines.append(
                f"| {evidence_anchor}`{_cell(anchor['evidence_id'])}` · {_cell(anchor['label'])} | "
                f"{_cell(stable)} | {_cell(anchor['summary'])} |"
            )
        lines.extend(["", "### Mechanism walkthrough", ""])
        lines.extend(f"{index}. {step}" for index, step in enumerate(unit["mechanism_steps"], start=1))
        lines.extend(["", "### Invariants, consumers, and compatibility", ""])
        for invariant in unit["invariants"]:
            lines.append(
                f"- `{invariant['status']}` {invariant['statement']} "
                f"({format_refs(invariant['evidence_refs'])})"
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
                f"{_cell(format_refs(claim['evidence_refs']))} | {_cell(claim['confidence'])} |"
            )
        lines.extend(["", "### Exact diff", ""])
        if unit["diff"]:
            lines.extend(["```diff", unit["diff"], "```"])
        else:
            lines.append("Typed non-text evidence: " + format_refs(unit["evidence_ids"]) + ".")
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
                f"{_cell(check['action'])} | {_cell(check['expected'])} | "
                f"{_cell(format_refs(check['claim_ids']))} |"
            )
        lines.extend(["", "### Failure modes and unknowns", ""])
        for failure in unit["failure_modes"]:
            lines.append(
                f"- `{failure['id']}` {failure['trigger']} -> {failure['effect']} -> "
                f"{failure['detection_or_mitigation']} ({format_refs(failure['evidence_refs'])})"
            )
        lines.extend(f"- Unknown: {item}" for item in unit["unknowns"])
        lines.extend(["", "### Findings", ""])
        for finding in findings_by_unit.get(unit["id"], []):
            lines.append(
                f"- `{finding['category']}` `{finding.get('severity', 'none')}` "
                f"{finding['id']}: {finding['description']} ({format_refs(finding['evidence_ids'])})"
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
                f"({format_refs(conclusion['evidence_refs'])})",
            ]
        )

    lines.extend(["", "## End-to-end synthesis", ""])
    lines.extend(
        f"- {unit['title']}: {unit['conclusion']['statement']}"
        for unit in report["units"]
    )
    lines.extend(["", "## Findings and open questions", ""])
    if report["findings"]:
        for finding in report["findings"]:
            lines.append(
                f"- `{finding['category']}` `{finding.get('severity', 'none')}` "
                f"{finding['id']} / {finding['unit_id']}: {finding['description']} "
                f"({format_refs(finding['evidence_ids'])})"
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
