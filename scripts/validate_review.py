#!/usr/bin/env python3
"""Validate a ManDiff report's shape, references, and evidence accounting."""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_PATH = Path(__file__).resolve().parent.parent / "assets" / "review-model.schema.json"
HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
RFC3339 = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$")


def review_digest(source_artifacts: list[dict[str, Any]]) -> str:
    """Bind an ordered set of independently frozen diff artifacts to one report."""
    payload = "".join(
        f"{item.get('id', '')}\t{item.get('diff_digest', '')}\t{item.get('diff_bytes', '')}\n"
        for item in source_artifacts
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _json_type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return True


def _shape_errors(
    value: Any,
    rule: dict[str, Any],
    root: dict[str, Any],
    path: str = "$",
) -> list[str]:
    errors: list[str] = []
    if "$ref" in rule:
        target: Any = root
        for part in rule["$ref"].removeprefix("#/").split("/"):
            target = target[part.replace("~1", "/").replace("~0", "~")]
        return _shape_errors(value, target, root, path)

    expected = rule.get("type")
    if expected:
        candidates = expected if isinstance(expected, list) else [expected]
        if not any(_json_type_matches(value, item) for item in candidates):
            return [f"{path}: expected {' or '.join(candidates)}"]

    if "const" in rule and value != rule["const"]:
        errors.append(f"{path}: expected constant {rule['const']!r}")
    if "enum" in rule and value not in rule["enum"]:
        errors.append(f"{path}: value {value!r} is not allowed")

    if isinstance(value, dict):
        for key in rule.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required field {key!r}")
        properties = rule.get("properties", {})
        for key, item in value.items():
            child_path = f"{path}.{key}"
            if key in properties:
                errors.extend(_shape_errors(item, properties[key], root, child_path))
            elif rule.get("additionalProperties") is False:
                errors.append(f"{child_path}: unexpected field")
            elif isinstance(rule.get("additionalProperties"), dict):
                errors.extend(_shape_errors(item, rule["additionalProperties"], root, child_path))

    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            errors.append(f"{path}: requires at least {rule['minItems']} item(s)")
        if "maxItems" in rule and len(value) > rule["maxItems"]:
            errors.append(f"{path}: allows at most {rule['maxItems']} item(s)")
        if rule.get("uniqueItems"):
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in value]
            if len(encoded) != len(set(encoded)):
                errors.append(f"{path}: items must be unique")
        item_rule = rule.get("items")
        if item_rule:
            for index, item in enumerate(value):
                errors.extend(_shape_errors(item, item_rule, root, f"{path}[{index}]"))

    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            errors.append(f"{path}: string is too short")
        if "pattern" in rule and re.fullmatch(rule["pattern"], value) is None:
            errors.append(f"{path}: does not match {rule['pattern']!r}")
        if rule.get("format") == "date-time":
            try:
                if RFC3339.fullmatch(value) is None:
                    raise ValueError
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError
            except ValueError:
                errors.append(f"{path}: expected an RFC 3339 date-time with timezone")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            errors.append(f"{path}: must be at least {rule['minimum']}")
    return errors


def _index(items: list[dict[str, Any]], key: str, label: str, errors: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for position, item in enumerate(items):
        identifier = item.get(key)
        if not isinstance(identifier, str):
            continue
        if identifier in result:
            errors.append(f"{label}: duplicate ID {identifier!r} at item {position + 1}")
        result[identifier] = item
    return result


def _check_refs(refs: list[Any], known: set[str], location: str, errors: list[str]) -> None:
    for ref in refs:
        if ref not in known:
            errors.append(f"{location}: unknown reference {ref!r}")


def _check_text_hunk(anchor: dict[str, Any], text: str, location: str, errors: list[str]) -> None:
    lines = text.splitlines()
    if not lines or lines[0] != anchor.get("header"):
        errors.append(f"{location}: byte span must begin with the exact hunk header")
        return
    match = HUNK_HEADER.match(lines[0])
    if not match:
        errors.append(f"{location}: invalid unified-diff hunk header")
        return
    old_start, old_lines, new_start, new_lines = (
        int(match.group(1)),
        int(match.group(2) or 1),
        int(match.group(3)),
        int(match.group(4) or 1),
    )
    declared = (anchor.get("old_start"), anchor.get("old_lines"), anchor.get("new_start"), anchor.get("new_lines"))
    if declared != (old_start, old_lines, new_start, new_lines):
        errors.append(f"{location}: line spans do not match the hunk header")
    body = [line for line in lines[1:] if not line.startswith("\\ No newline at end of file")]
    actual_old = sum(1 for line in body if not line.startswith("+"))
    actual_new = sum(1 for line in body if not line.startswith("-"))
    if (actual_old, actual_new) != (old_lines, new_lines):
        errors.append(f"{location}: byte span does not contain the complete hunk body")


def _detect_dependency_cycles(units: dict[str, dict[str, Any]], errors: list[str]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(unit_id: str, trail: list[str]) -> None:
        if unit_id in visiting:
            start = trail.index(unit_id)
            errors.append(f"units: dependency cycle {' -> '.join(trail[start:] + [unit_id])}")
            return
        if unit_id in visited:
            return
        visiting.add(unit_id)
        for dependency in units[unit_id].get("depends_on", []):
            if dependency in units:
                visit(dependency, trail + [unit_id])
        visiting.remove(unit_id)
        visited.add(unit_id)

    for identifier in units:
        visit(identifier, [])


def validate_report(report: Any, schema_path: Path = SCHEMA_PATH) -> list[str]:
    """Return deterministic validation errors; an empty list means renderable."""
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = _shape_errors(report, schema, schema)
    if not isinstance(report, dict) or errors:
        return errors

    source_artifacts = report.get("source_artifacts", [])
    units_list = report.get("units", [])
    files_list = report.get("files", [])
    context_list = report.get("context_sources", [])
    requirement_list = report.get("requirements", [])
    ledger_list = report.get("evidence_ledger", [])
    findings_list = report.get("findings", [])
    verification_list = report.get("verification", [])

    sources = _index(source_artifacts, "id", "source_artifacts", errors)
    units = _index(units_list, "id", "units", errors)
    files = _index(files_list, "id", "files", errors)
    contexts = _index(context_list, "id", "context_sources", errors)
    requirements = _index(requirement_list, "id", "requirements", errors)
    ledger = _index(ledger_list, "evidence_id", "evidence_ledger", errors)
    findings = _index(findings_list, "id", "findings", errors)
    verifications = _index(verification_list, "id", "verification", errors)

    source_bytes: dict[str, bytes] = {}
    for source_id, source in sources.items():
        try:
            raw = base64.b64decode(source.get("diff_base64", ""), validate=True)
        except (binascii.Error, ValueError):
            errors.append(f"source artifact {source_id}: diff_base64 is not valid base64")
            continue
        source_bytes[source_id] = raw
        display_digest = hashlib.sha256(raw).hexdigest()
        if source.get("display_digest") != display_digest:
            errors.append(f"source artifact {source_id}: display digest expected {display_digest}")
        if source.get("display_bytes") != len(raw):
            errors.append(f"source artifact {source_id}: display byte count expected {len(raw)}")
        if not source.get("redacted"):
            if source.get("diff_digest") != display_digest:
                errors.append(f"source artifact {source_id}: unredacted raw digest must match display digest")
            if source.get("diff_bytes") != len(raw):
                errors.append(f"source artifact {source_id}: unredacted raw byte count must match display bytes")

    meta = report["report"]
    ordered_source_ids = [item.get("id") for item in source_artifacts]
    if meta.get("source_artifact_ids") != ordered_source_ids:
        errors.append("report.source_artifact_ids: must match source_artifacts order exactly")
    expected_digest = review_digest(source_artifacts)
    if meta.get("diff_digest") != expected_digest:
        errors.append(f"report.diff_digest: expected ordered source manifest digest {expected_digest}")
    expected_bytes = sum(item.get("diff_bytes", 0) for item in source_artifacts)
    if meta.get("diff_bytes") != expected_bytes:
        errors.append(f"report.diff_bytes: expected source artifact total {expected_bytes}")
    expected_mutable = any(item.get("mutable") for item in source_artifacts)
    if meta.get("mutable") != expected_mutable:
        errors.append(f"report.mutable: expected {expected_mutable}")
    artifact_drifts = [item.get("drift") for item in source_artifacts]
    expected_drift = (
        "stale" if "stale" in artifact_drifts else
        "unknown" if "unknown" in artifact_drifts else
        "unchanged" if expected_mutable else
        "immutable"
    )
    if meta.get("drift") != expected_drift:
        errors.append(f"report.drift: expected {expected_drift!r} from source artifacts")

    unit_orders = [item.get("order") for item in units_list]
    if len(unit_orders) != len(set(unit_orders)):
        errors.append("units.order: values must be unique")
    if unit_orders != sorted(unit_orders):
        errors.append("units: items must appear in ascending order")

    claim_owner: dict[str, str] = {}
    claims: dict[str, dict[str, Any]] = {}
    failure_owner: dict[str, str] = {}
    failures: dict[str, dict[str, Any]] = {}
    anchors: dict[str, dict[str, Any]] = {}
    unit_diff_segments: dict[str, list[tuple[str, int, int]]] = {}
    evidence_owners: Counter[str] = Counter()

    changed_ids = set(ledger)
    context_ids = set(contexts)
    requirement_ids = set(requirements)
    reported_ids = {identifier for identifier in requirement_ids if identifier.startswith("M")}
    requirement_only_ids = {identifier for identifier in requirement_ids if identifier.startswith("RQ")}

    for unit in units_list:
        unit_id = unit["id"]
        _check_refs(unit.get("depends_on", []), set(units), f"{unit_id}.depends_on", errors)
        if unit_id in unit.get("depends_on", []):
            errors.append(f"{unit_id}.depends_on: unit cannot depend on itself")
        _check_refs(unit.get("files", []), {item.get("path") for item in files_list}, f"{unit_id}.files", errors)
        _check_refs(unit.get("finding_ids", []), set(findings), f"{unit_id}.finding_ids", errors)
        _check_refs(unit.get("verification_ids", []), set(verifications), f"{unit_id}.verification_ids", errors)

        unit_segments: list[tuple[str, int, int]] = []
        displayed_chunks: list[bytes] = []
        for index, segment in enumerate(unit.get("diff_segments", []), start=1):
            source_id = segment.get("source_artifact_id")
            raw = source_bytes.get(source_id)
            if source_id not in sources:
                errors.append(f"{unit_id}.diff_segments[{index}]: unknown source artifact {source_id!r}")
                continue
            if raw is None:
                continue
            start = segment.get("byte_start", 0)
            end = start + segment.get("byte_length", 0)
            if end > len(raw):
                errors.append(f"{unit_id}.diff_segments[{index}]: byte span exceeds source artifact")
                continue
            unit_segments.append((source_id, start, end))
            displayed_chunks.append(raw[start:end])
        try:
            expected_diff = b"".join(displayed_chunks).decode("utf-8")
        except UnicodeDecodeError:
            errors.append(f"{unit_id}.diff_segments: text display bytes must be UTF-8")
        else:
            if unit.get("diff", "") != expected_diff:
                errors.append(f"{unit_id}.diff: must exactly equal the ordered frozen display segments")
        unit_diff_segments[unit_id] = unit_segments

        evidence_ids = unit.get("evidence_ids", [])
        evidence_owners.update(evidence_ids)
        unit_anchor_ids: list[str] = []
        for anchor in unit.get("anchors", []):
            evidence_id = anchor.get("evidence_id")
            unit_anchor_ids.append(evidence_id)
            if evidence_id in anchors:
                errors.append(f"anchors: duplicate evidence anchor {evidence_id!r}")
            anchors[evidence_id] = anchor
            if anchor.get("source_artifact_id") not in sources:
                errors.append(f"{unit_id}.anchors[{evidence_id}]: unknown source artifact")
            elif anchor.get("provenance") != sources[anchor["source_artifact_id"]].get("provenance"):
                errors.append(f"{unit_id}.anchors[{evidence_id}]: provenance differs from source artifact")
            raw = source_bytes.get(anchor.get("source_artifact_id"))
            if raw is not None:
                start = anchor.get("byte_start", 0)
                end = start + anchor.get("byte_length", 0)
                if end > len(raw):
                    errors.append(f"{unit_id}.anchors[{evidence_id}]: byte span exceeds source artifact")
                else:
                    evidence_bytes = raw[start:end]
                    display_fingerprint = hashlib.sha256(evidence_bytes).hexdigest()
                    if anchor.get("display_fingerprint") != display_fingerprint:
                        errors.append(f"{unit_id}.anchors[{evidence_id}]: display fingerprint expected {display_fingerprint}")
                    ledger_item = ledger.get(evidence_id, {})
                    if ledger_item.get("state") != "redacted" and anchor.get("fingerprint") != display_fingerprint:
                        errors.append(f"{unit_id}.anchors[{evidence_id}]: unredacted fingerprint must match display bytes")
                    if ledger_item.get("state") == "redacted" and not sources[anchor["source_artifact_id"]].get("redacted"):
                        errors.append(f"{unit_id}.anchors[{evidence_id}]: redacted evidence requires a redacted source artifact")
                    if anchor.get("kind") == "text_hunk":
                        try:
                            evidence_text = evidence_bytes.decode("utf-8")
                        except UnicodeDecodeError:
                            errors.append(f"{unit_id}.anchors[{evidence_id}]: text hunk is not UTF-8")
                        else:
                            _check_text_hunk(anchor, evidence_text, f"{unit_id}.anchors[{evidence_id}]", errors)
                            if unit.get("diff", "").count(evidence_text) != 1:
                                errors.append(f"{unit_id}.diff: exact evidence {evidence_id} must appear once")
                            if not any(source_id == anchor.get("source_artifact_id") and segment_start <= start and end <= segment_end for source_id, segment_start, segment_end in unit_segments):
                                errors.append(f"{unit_id}.anchors[{evidence_id}]: text hunk is not covered by a display segment")
            if anchor.get("path") not in unit.get("files", []):
                errors.append(f"{unit_id}.anchors[{evidence_id}]: path is not listed by the unit")
        if evidence_ids != unit_anchor_ids:
            errors.append(f"{unit_id}: evidence_ids must match anchor order exactly")
        _check_refs(evidence_ids, changed_ids, f"{unit_id}.evidence_ids", errors)

        anchor_kinds = {anchor.get("kind") for anchor in unit.get("anchors", [])}
        if "text_hunk" in anchor_kinds and len(anchor_kinds) > 1:
            errors.append(f"{unit_id}: text hunks and typed non-text evidence require separate units")
        if anchor_kinds == {"text_hunk"}:
            grouped: dict[tuple[str, int], list[dict[str, Any]]] = {}
            for anchor in unit.get("anchors", []):
                source_id = anchor.get("source_artifact_id")
                raw = source_bytes.get(source_id)
                if raw is None:
                    continue
                start = anchor.get("byte_start", 0)
                file_start = raw.rfind(b"diff --git ", 0, start + 1)
                if file_start < 0:
                    errors.append(f"{unit_id}.anchors[{anchor.get('evidence_id')}]: cannot locate source file header")
                    continue
                grouped.setdefault((source_id, file_start), []).append(anchor)
            expected_chunks: list[bytes] = []
            for (source_id, file_start), group in grouped.items():
                raw = source_bytes[source_id]
                first_hunk_marker = raw.find(b"\n@@ ", file_start)
                if first_hunk_marker < 0:
                    errors.append(f"{unit_id}.diff: cannot locate the first hunk after source file metadata")
                    continue
                metadata_end = first_hunk_marker + 1
                expected_chunks.append(raw[file_start:metadata_end])
                for anchor in group:
                    start = anchor.get("byte_start", 0)
                    expected_chunks.append(raw[start:start + anchor.get("byte_length", 0)])
            try:
                canonical_diff = b"".join(expected_chunks).decode("utf-8")
            except UnicodeDecodeError:
                errors.append(f"{unit_id}.diff: canonical text evidence is not UTF-8")
            else:
                if unit.get("diff", "") != canonical_diff:
                    errors.append(f"{unit_id}.diff: must contain exact source file metadata followed by owned hunks")
        elif unit.get("diff") or unit.get("diff_segments"):
            errors.append(f"{unit_id}: typed non-text evidence must use an empty text diff and no diff segments")

        local_claims: set[str] = set()
        for claim in unit.get("claims", []):
            claim_id = claim.get("id")
            if claim_id in claims:
                errors.append(f"claims: duplicate ID {claim_id!r}")
            claims[claim_id] = claim
            claim_owner[claim_id] = unit_id
            local_claims.add(claim_id)
        local_failures: set[str] = set()
        for failure in unit.get("failure_modes", []):
            failure_id = failure.get("id")
            if failure_id in failures:
                errors.append(f"failure_modes: duplicate ID {failure_id!r}")
            failures[failure_id] = failure
            failure_owner[failure_id] = unit_id
            local_failures.add(failure_id)
        for check in unit.get("checks", []):
            _check_refs(check.get("claim_ids", []), local_claims, f"{unit_id}.check[{check.get('id')}].claim_ids", errors)

        if unit.get("lane") == "main" and unit.get("importance") in {"critical", "normal"}:
            required_collections = (
                "entry_points",
                "call_path",
                "invariants",
                "consumers",
                "compatibility",
                "claims",
                "failure_modes",
                "unknowns",
                "checks",
            )
            for field in required_collections:
                if not unit.get(field):
                    errors.append(f"{unit_id}.{field}: main critical/normal units require at least one item")
            if len(unit.get("mechanism_steps", [])) < 3:
                errors.append(f"{unit_id}.mechanism_steps: main critical/normal units require at least 3 steps")


    _detect_dependency_cycles(units, errors)

    for unit_id, segments in unit_diff_segments.items():
        for source_id, segment_start, segment_end in segments:
            for evidence_id, item in ledger.items():
                if item.get("source_artifact_id") != source_id or item.get("unit_id") == unit_id:
                    continue
                evidence_start = item.get("byte_start", 0)
                evidence_end = evidence_start + item.get("byte_length", 0)
                if max(segment_start, evidence_start) < min(segment_end, evidence_end):
                    errors.append(f"{unit_id}.diff_segments: overlaps evidence {evidence_id} owned outside this unit")

    for file_item in files_list:
        file_id = file_item["id"]
        _check_refs(file_item.get("unit_ids", []), set(units), f"file {file_id}.unit_ids", errors)
        for unit_id in file_item.get("unit_ids", []):
            if unit_id in units and file_item.get("path") not in units[unit_id].get("files", []):
                errors.append(f"file {file_id}: unit {unit_id} does not link back to path {file_item.get('path')!r}")

    all_fact_refs = changed_ids | context_ids | requirement_ids | set(claims)
    for claim_id, claim in claims.items():
        refs = claim.get("evidence_refs", [])
        _check_refs(refs, all_fact_refs - {claim_id}, f"claim {claim_id}.evidence_refs", errors)
        kind = claim.get("kind")
        if kind == "observed" and not (set(refs) & changed_ids):
            errors.append(f"claim {claim_id}: observed claims must cite changed evidence")
        if kind == "contextual" and not (set(refs) & context_ids):
            errors.append(f"claim {claim_id}: contextual claims must cite context evidence")
        if kind == "reported" and not refs:
            errors.append(f"claim {claim_id}: reported claims must cite reported intent or a requirement")
        if kind == "reported" and not set(refs).issubset(reported_ids | requirement_only_ids):
            errors.append(f"claim {claim_id}: reported claims may cite only Mxx or RQxx evidence")
        if kind == "inferred" and not refs:
            errors.append(f"claim {claim_id}: inferred claims must cite their premises")

    for failure_id, failure in failures.items():
        refs = failure.get("evidence_refs", [])
        _check_refs(refs, all_fact_refs, f"failure mode {failure_id}.evidence_refs", errors)
        owner = failure_owner[failure_id]
        local_claims = {identifier for identifier, unit_id in claim_owner.items() if unit_id == owner}
        _check_refs(failure.get("claim_ids", []), local_claims, f"failure mode {failure_id}.claim_ids", errors)

    for evidence_id, item in ledger.items():
        source_id = item.get("source_artifact_id")
        raw = source_bytes.get(source_id)
        if source_id not in sources:
            errors.append(f"evidence_ledger[{evidence_id}]: unknown source artifact {source_id!r}")
        elif raw is not None:
            start = item.get("byte_start", 0)
            end = start + item.get("byte_length", 0)
            if end > len(raw):
                errors.append(f"evidence_ledger[{evidence_id}]: byte span exceeds source artifact")
            else:
                display_fingerprint = hashlib.sha256(raw[start:end]).hexdigest()
                if item.get("display_fingerprint") != display_fingerprint:
                    errors.append(f"evidence_ledger[{evidence_id}]: display fingerprint expected {display_fingerprint}")
                if item.get("state") != "redacted" and item.get("fingerprint") != display_fingerprint:
                    errors.append(f"evidence_ledger[{evidence_id}]: unredacted fingerprint must match display bytes")
        anchor = anchors.get(evidence_id)
        if not anchor:
            if item.get("state") != "discovered":
                errors.append(f"evidence_ledger[{evidence_id}]: no matching unit anchor")
            if item.get("unit_id") is not None or item.get("lane") is not None or item.get("importance") is not None:
                errors.append(f"evidence_ledger[{evidence_id}]: discovered unassigned evidence must use null ownership fields")
            continue
        if item.get("source_artifact_id") != anchor.get("source_artifact_id"):
            errors.append(f"evidence_ledger[{evidence_id}]: source artifact differs from anchor")
        if item.get("fingerprint") != anchor.get("fingerprint"):
            errors.append(f"evidence_ledger[{evidence_id}]: fingerprint differs from anchor")
        if item.get("display_fingerprint") != anchor.get("display_fingerprint"):
            errors.append(f"evidence_ledger[{evidence_id}]: display fingerprint differs from anchor")
        if item.get("byte_start") != anchor.get("byte_start") or item.get("byte_length") != anchor.get("byte_length"):
            errors.append(f"evidence_ledger[{evidence_id}]: byte span differs from anchor")
        if item.get("kind") != anchor.get("kind"):
            errors.append(f"evidence_ledger[{evidence_id}]: kind differs from anchor")
        owner = item.get("unit_id")
        if owner not in units:
            errors.append(f"evidence_ledger[{evidence_id}]: unknown unit {owner!r}")
            continue
        if evidence_owners[evidence_id] != 1 or evidence_id not in units[owner].get("evidence_ids", []):
            errors.append(f"evidence_ledger[{evidence_id}]: unit ownership does not match exactly once")
        if item.get("lane") != units[owner].get("lane"):
            errors.append(f"evidence_ledger[{evidence_id}]: lane differs from owning unit")
        if item.get("importance") != units[owner].get("importance"):
            errors.append(f"evidence_ledger[{evidence_id}]: importance differs from owning unit")
    for evidence_id in anchors:
        if evidence_id not in ledger:
            errors.append(f"anchor {evidence_id}: missing from evidence ledger")
    ledger_sources = Counter(item.get("source_artifact_id") for item in ledger.values())
    for source_id, source in sources.items():
        if source.get("diff_bytes", 0) > 0 and ledger_sources[source_id] == 0:
            errors.append(f"source artifact {source_id}: non-empty diff has no evidence inventory")
        has_redacted_evidence = any(item.get("source_artifact_id") == source_id and item.get("state") == "redacted" for item in ledger.values())
        if source.get("redacted") != has_redacted_evidence:
            errors.append(f"source artifact {source_id}: redacted flag must match its ledger evidence")

    for finding in findings_list:
        finding_id = finding["id"]
        owner = finding.get("unit_id")
        if owner not in units:
            errors.append(f"finding {finding_id}: unknown unit {owner!r}")
            continue
        allowed_finding_evidence = set(units[owner].get("evidence_ids", [])) | context_ids | requirement_ids
        _check_refs(finding.get("evidence_ids", []), allowed_finding_evidence, f"finding {finding_id}.evidence_ids", errors)
        local_claims = {identifier for identifier, unit_id in claim_owner.items() if unit_id == owner}
        local_failures = {identifier for identifier, unit_id in failure_owner.items() if unit_id == owner}
        _check_refs(finding.get("claim_ids", []), local_claims, f"finding {finding_id}.claim_ids", errors)
        _check_refs(finding.get("failure_mode_ids", []), local_failures, f"finding {finding_id}.failure_mode_ids", errors)
        if not finding.get("claim_ids") and not finding.get("failure_mode_ids"):
            errors.append(f"finding {finding_id}: requires at least one claim or failure mode")
        if finding_id not in units[owner].get("finding_ids", []):
            errors.append(f"finding {finding_id}: owning unit does not link back to it")
    for unit in units_list:
        for finding_id in unit.get("finding_ids", []):
            if finding_id in findings and findings[finding_id].get("unit_id") != unit["id"]:
                errors.append(f"{unit['id']}.finding_ids: finding {finding_id} belongs to another unit")

    for verification in verification_list:
        verification_id = verification["id"]
        _check_refs(verification.get("unit_ids", []), set(units), f"verification {verification_id}.unit_ids", errors)
        _check_refs(verification.get("claim_ids", []), set(claims), f"verification {verification_id}.claim_ids", errors)
        for unit_id in verification.get("unit_ids", []):
            if unit_id in units and verification_id not in units[unit_id].get("verification_ids", []):
                errors.append(f"verification {verification_id}: unit {unit_id} does not link back to it")
    for unit in units_list:
        for verification_id in unit.get("verification_ids", []):
            if verification_id in verifications and unit["id"] not in verifications[verification_id].get("unit_ids", []):
                errors.append(f"{unit['id']}.verification_ids: verification {verification_id} does not link back")

    conclusion_refs: list[tuple[str, list[Any]]] = []
    for unit in units_list:
        conclusion_refs.append((f"{unit['id']}.conclusion", unit.get("conclusion", {}).get("evidence_refs", [])))
        for index, invariant in enumerate(unit.get("invariants", []), start=1):
            conclusion_refs.append((f"{unit['id']}.invariant[{index}]", invariant.get("evidence_refs", [])))
    for location, refs in conclusion_refs:
        _check_refs(refs, all_fact_refs, f"{location}.evidence_refs", errors)

    outcome_refs = set(units) | set(findings) | set(claims) | changed_ids | context_ids | requirement_ids | set(verifications)
    outcome = report.get("outcome", {})
    for group in ("confirmed", "defects", "unproven"):
        for index, item in enumerate(outcome.get(group, []), start=1):
            _check_refs(item.get("refs", []), outcome_refs, f"outcome.{group}[{index}].refs", errors)
    _check_refs(outcome.get("recommendation", {}).get("refs", []), outcome_refs, "outcome.recommendation.refs", errors)

    state_counts = Counter(item.get("state") for item in ledger_list)
    ownership_counts = Counter(evidence_id for unit in units_list for evidence_id in unit.get("evidence_ids", []))
    assigned_once = sum(1 for evidence_id in ledger if ownership_counts[evidence_id] == 1)
    expected_coverage = {
        "total": len(ledger),
        "assigned_once": assigned_once,
        "presented_once": sum(1 for item in ledger_list if ownership_counts[item["evidence_id"]] == 1 and item.get("state") in {"presented", "validated", "redacted"}),
        "validated": state_counts["validated"],
        "redacted": state_counts["redacted"],
        "missing": sum(1 for evidence_id in ledger if ownership_counts[evidence_id] == 0),
        "duplicated": sum(max(0, count - 1) for count in ownership_counts.values()),
        "unknown": sum(1 for evidence_id in ownership_counts if evidence_id not in ledger),
    }
    for key, expected in expected_coverage.items():
        if report.get("coverage", {}).get(key) != expected:
            errors.append(f"coverage.{key}: expected {expected}")

    expected_summary = {
        "files": len(files),
        "hunks": sum(1 for item in ledger_list if item.get("kind") == "text_hunk"),
        "additions": sum(item.get("additions", 0) for item in files_list),
        "deletions": sum(item.get("deletions", 0) for item in files_list),
        "evidence_total": len(ledger),
        "evidence_validated": state_counts["validated"] + state_counts["redacted"],
    }
    for key, expected in expected_summary.items():
        if report.get("summary", {}).get(key) != expected:
            errors.append(f"summary.{key}: expected {expected}")
    return errors


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--schema", type=Path, default=SCHEMA_PATH)
    args = parser.parse_args()
    try:
        report = json.loads(args.report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read report: {error}") from error
    errors = validate_report(report, args.schema)
    if errors:
        raise SystemExit("Invalid ManDiff report:\n- " + "\n- ".join(errors))
    print(f"Valid ManDiff {report['schema_version']} report: {report['report']['id']}")


if __name__ == "__main__":
    main()
