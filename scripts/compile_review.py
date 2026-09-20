#!/usr/bin/env python3
"""Compile frozen diffs and declarative analysis into a ManDiff report."""

from __future__ import annotations

import argparse
import ast
import base64
import copy
import hashlib
import hmac
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from validate_review import review_digest, validate_report


DIFF_START = re.compile(rb"(?m)^diff --git ")
HUNK_START = re.compile(
    rb"(?m)^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@[^\r\n]*"
)
DERIVED_UNIT_FIELDS = {
    "anchors",
    "changed_lines",
    "diff",
    "diff_segments",
    "evidence_ids",
    "files",
    "finding_ids",
    "verification_ids",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read {path}: {error}") from error
    if not isinstance(value, dict):
        raise SystemExit(f"{path}: expected a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _decode_git_path(value: bytes, strip_prefix: bool = True) -> str:
    value = value.strip()
    if value == b"/dev/null":
        return ""
    if value.startswith(b'"'):
        try:
            decoded = ast.literal_eval(value.decode("ascii"))
            value = bytes(ord(char) for char in decoded)
        except (SyntaxError, ValueError, UnicodeEncodeError):
            pass
    text = value.decode("utf-8", "replace")
    return text[2:] if strip_prefix and text.startswith(("a/", "b/")) else text


def _marker_path(section: bytes, marker: bytes, strip_prefix: bool = True) -> Optional[str]:
    match = re.search(rb"(?m)^" + re.escape(marker) + rb" (.+)$", section)
    return _decode_git_path(match.group(1), strip_prefix) if match else None


def _fallback_paths(section: bytes) -> tuple[str, str]:
    first_line = section.splitlines()[0] if section else b""
    prefix = b"diff --git "
    if not first_line.startswith(prefix):
        return "", ""
    payload = first_line[len(prefix):]
    if payload.startswith(b'"'):
        match = re.fullmatch(rb'("(?:\\.|[^"\\])*") ("(?:\\.|[^"\\])*")', payload)
        if not match:
            return "", ""
        return _decode_git_path(match.group(1)), _decode_git_path(match.group(2))
    separator = payload.rfind(b" b/")
    if separator < 0:
        return "", ""
    return _decode_git_path(payload[:separator]), _decode_git_path(payload[separator + 1:])


def _hunk_line_counts(value: bytes) -> tuple[int, int]:
    additions = 0
    deletions = 0
    for line in value.splitlines()[1:]:
        if line.startswith(b"+"):
            additions += 1
        elif line.startswith(b"-"):
            deletions += 1
    return additions, deletions


def _typed_kind(section: bytes, status: str) -> str:
    if b" 160000" in section or b"Subproject commit " in section:
        return "submodule"
    if b"GIT binary patch" in section or re.search(rb"(?m)^Binary files .+ differ$", section):
        return "binary"
    if status == "renamed":
        return "rename"
    if status == "copied":
        return "copy"
    if b"new file mode" in section and not HUNK_START.search(section):
        return "empty_file"
    return "mode"


def _status(section: bytes) -> str:
    if re.search(rb"(?m)^new file mode ", section):
        return "added"
    if re.search(rb"(?m)^deleted file mode ", section):
        return "deleted"
    if re.search(rb"(?m)^rename from ", section):
        return "renamed"
    if re.search(rb"(?m)^copy from ", section):
        return "copied"
    return "modified"


def _typed_suffix(kind: str) -> str:
    return {
        "binary": "BINARY",
        "copy": "COPY",
        "empty_file": "EMPTY",
        "mode": "MODE",
        "rename": "RENAME",
        "submodule": "SUBMODULE",
    }[kind]


def _parse_source(
    source: dict[str, Any], raw: bytes, file_number: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    files: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    starts = [match.start() for match in DIFF_START.finditer(raw)]
    if raw and not starts:
        raise SystemExit(f"{source['id']}: diff has content but no 'diff --git' section")

    for position, section_start in enumerate(starts):
        section_end = starts[position + 1] if position + 1 < len(starts) else len(raw)
        section = raw[section_start:section_end]
        file_id = f"F{file_number:02d}"
        file_number += 1
        old_path = _marker_path(section, b"---")
        new_path = _marker_path(section, b"+++")
        fallback_old, fallback_new = _fallback_paths(section)
        if old_path is None:
            old_path = (
                _marker_path(section, b"rename from", False)
                or _marker_path(section, b"copy from", False)
                or fallback_old
            )
        if new_path is None:
            new_path = (
                _marker_path(section, b"rename to", False)
                or _marker_path(section, b"copy to", False)
                or fallback_new
            )
        path = new_path or old_path
        status = _status(section)
        hunk_matches = list(HUNK_START.finditer(section))
        is_submodule = _typed_kind(section, status) == "submodule"
        hunk_ranges = [
            (
                match.start(),
                hunk_matches[index + 1].start() if index + 1 < len(hunk_matches) else len(section),
            )
            for index, match in enumerate(hunk_matches)
        ]
        hunk_counts = [_hunk_line_counts(section[start:end]) for start, end in hunk_ranges]
        file_additions = sum(item[0] for item in hunk_counts)
        file_deletions = sum(item[1] for item in hunk_counts)
        files.append(
            {
                "id": file_id,
                "path": path,
                "status": status,
                "additions": file_additions,
                "deletions": file_deletions,
            }
        )

        if hunk_matches and not is_submodule:
            metadata_end = section_start + hunk_matches[0].start()
            for ordinal, match in enumerate(hunk_matches, start=1):
                byte_start = section_start + match.start()
                byte_end = (
                    section_start + hunk_matches[ordinal].start()
                    if ordinal < len(hunk_matches)
                    else section_end
                )
                evidence_bytes = raw[byte_start:byte_end]
                old_start = int(match.group(1))
                old_lines = int(match.group(2) or 1)
                new_start = int(match.group(3))
                new_lines = int(match.group(4) or 1)
                additions, deletions = _hunk_line_counts(evidence_bytes)
                evidence.append(
                    {
                        "evidence_id": f"{file_id}-H{ordinal:02d}",
                        "file_id": file_id,
                        "source_artifact_id": source["id"],
                        "kind": "text_hunk",
                        "provenance": source["provenance"],
                        "path": path,
                        "old_path": old_path,
                        "new_path": new_path,
                        "ordinal": ordinal,
                        "header": match.group(0).decode("utf-8", "replace"),
                        "old_start": old_start,
                        "old_lines": old_lines,
                        "new_start": new_start,
                        "new_lines": new_lines,
                        "byte_start": byte_start,
                        "byte_length": byte_end - byte_start,
                        "file_start": section_start,
                        "metadata_end": metadata_end,
                        "additions": additions,
                        "deletions": deletions,
                        "fingerprint": _sha256(evidence_bytes),
                        "display_fingerprint": _sha256(evidence_bytes),
                    }
                )
            continue

        kind = _typed_kind(section, status)
        evidence.append(
            {
                "evidence_id": f"{file_id}-{_typed_suffix(kind)}",
                "file_id": file_id,
                "source_artifact_id": source["id"],
                "kind": kind,
                "provenance": source["provenance"],
                "path": path,
                "old_path": old_path,
                "new_path": new_path,
                "ordinal": 1,
                "header": section.splitlines()[0].decode("utf-8", "replace"),
                "old_start": None,
                "old_lines": None,
                "new_start": None,
                "new_lines": None,
                "byte_start": section_start,
                "byte_length": section_end - section_start,
                "file_start": section_start,
                "metadata_end": section_end,
                "additions": file_additions,
                "deletions": file_deletions,
                "fingerprint": _sha256(section),
                "display_fingerprint": _sha256(section),
            }
        )
    return files, evidence, file_number


def create_inventory(manifest_path: Path) -> dict[str, Any]:
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != "1.0":
        raise SystemExit("source manifest: schema_version must be '1.0'")
    source_specs = manifest.get("sources")
    if not isinstance(source_specs, list) or not source_specs:
        raise SystemExit("source manifest: sources must be a non-empty array")

    captured_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    sources: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    file_number = 1
    for position, spec in enumerate(source_specs, start=1):
        source_id = f"S{position:02d}"
        try:
            diff_path = Path(spec["diff_path"])
            if not diff_path.is_absolute():
                diff_path = manifest_path.parent / diff_path
            raw = diff_path.read_bytes()
            provenance = spec["provenance"]
            selector = spec["selector"]
            acquisition = spec["acquisition"]
        except (KeyError, OSError) as error:
            raise SystemExit(f"source {source_id}: invalid source specification: {error}") from error
        mutable = bool(spec.get("mutable", False))
        redacted = bool(spec.get("redacted", False))
        display_digest = _sha256(raw)
        original = raw
        private_key = b""
        if redacted:
            try:
                original_path = Path(spec["original_diff_path"])
                key_path = Path(spec["hmac_key_path"])
                if not original_path.is_absolute():
                    original_path = manifest_path.parent / original_path
                if not key_path.is_absolute():
                    key_path = manifest_path.parent / key_path
                original = original_path.read_bytes()
                private_key = key_path.read_bytes()
            except (KeyError, OSError) as error:
                raise SystemExit(
                    f"source {source_id}: redaction requires original_diff_path and hmac_key_path"
                ) from error
            if not private_key:
                raise SystemExit(f"source {source_id}: HMAC key must not be empty")
        diff_digest = hmac.new(private_key, original, hashlib.sha256).hexdigest() if redacted else display_digest
        diff_bytes = len(original)
        source = {
            "id": source_id,
            "provenance": provenance,
            "selector": selector,
            "acquisition": acquisition,
            "captured_at": spec.get("captured_at", captured_at),
            "base": spec.get("base", ""),
            "head": spec.get("head", ""),
            "diff_path": str(diff_path.resolve()),
            "diff_digest": diff_digest,
            "diff_bytes": diff_bytes,
            "display_digest": display_digest,
            "display_bytes": len(raw),
            "redacted": redacted,
            "mutable": mutable,
            "drift": spec.get("drift", "unknown" if mutable else "immutable"),
        }
        sources.append(source)
        starting_file_number = file_number
        source_files, source_evidence, file_number = _parse_source(source, raw, file_number)
        if redacted:
            _, original_evidence, _ = _parse_source(source, original, starting_file_number)
            original_by_id = {item["evidence_id"]: item for item in original_evidence}
            if [(item["evidence_id"], item["kind"], item["header"]) for item in source_evidence] != [
                (item["evidence_id"], item["kind"], item["header"]) for item in original_evidence
            ]:
                raise SystemExit(
                    f"source {source_id}: redaction changed diff structure; only value replacement is allowed"
                )
            for item in source_evidence:
                original_item = original_by_id[item["evidence_id"]]
                start = original_item["byte_start"]
                original_bytes = original[start:start + original_item["byte_length"]]
                item["fingerprint"] = hmac.new(private_key, original_bytes, hashlib.sha256).hexdigest()
        files.extend(source_files)
        evidence.extend(source_evidence)

    return {
        "schema_version": "1.0",
        "report": manifest.get("report", {}),
        "sources": sources,
        "files": files,
        "evidence": evidence,
    }


def _read_frozen_sources(inventory: dict[str, Any]) -> tuple[dict[str, bytes], list[dict[str, Any]]]:
    raw_sources: dict[str, bytes] = {}
    report_sources: list[dict[str, Any]] = []
    for source in inventory.get("sources", []):
        raw = Path(source["diff_path"]).read_bytes()
        if _sha256(raw) != source["display_digest"] or len(raw) != source["display_bytes"]:
            raise SystemExit(f"{source['id']}: frozen display diff changed after inventory")
        raw_sources[source["id"]] = raw
        report_source = {key: value for key, value in source.items() if key != "diff_path"}
        report_source["diff_base64"] = base64.b64encode(raw).decode("ascii")
        report_sources.append(report_source)
    return raw_sources, report_sources


def _anchor(item: dict[str, Any], label: str, summary: str) -> dict[str, Any]:
    internal = {"file_id", "file_start", "metadata_end", "additions", "deletions"}
    result = {key: value for key, value in item.items() if key not in internal}
    result["label"] = label
    result["summary"] = summary
    return result


def _context_sources(items: Any) -> list[dict[str, Any]]:
    result = copy.deepcopy(items if isinstance(items, list) else [])
    for item in result:
        excerpt = item.get("excerpt")
        if isinstance(excerpt, str):
            item["fingerprint"] = _sha256(excerpt.encode("utf-8"))
        elif not item.get("fingerprint"):
            raise SystemExit(f"context source {item.get('id', '?')}: excerpt or fingerprint is required")
    return result


def compile_report(inventory_path: Path, analysis_path: Path) -> dict[str, Any]:
    inventory = _load_json(inventory_path)
    analysis = _load_json(analysis_path)
    if inventory.get("schema_version") != "1.0" or analysis.get("schema_version") != "1.0":
        raise SystemExit("inventory and analysis schema_version must both be '1.0'")
    raw_sources, source_artifacts = _read_frozen_sources(inventory)
    evidence_items = inventory.get("evidence", [])
    evidence_by_id = {item["evidence_id"]: item for item in evidence_items}
    file_by_id = {item["id"]: item for item in inventory.get("files", [])}
    findings = copy.deepcopy(analysis.get("findings", []))
    verifications = copy.deepcopy(analysis.get("verification", []))
    finding_ids_by_unit: dict[str, list[str]] = {}
    verification_ids_by_unit: dict[str, list[str]] = {}
    for finding in findings:
        finding_ids_by_unit.setdefault(finding.get("unit_id"), []).append(finding.get("id"))
    for verification in verifications:
        for unit_id in verification.get("unit_ids", []):
            verification_ids_by_unit.setdefault(unit_id, []).append(verification.get("id"))

    units: list[dict[str, Any]] = []
    ownership: Counter[str] = Counter()
    file_units: dict[str, list[str]] = {file_id: [] for file_id in file_by_id}
    evidence_labels: dict[str, tuple[str, str]] = {}
    for source_unit in analysis.get("units", []):
        forbidden = DERIVED_UNIT_FIELDS & set(source_unit)
        if forbidden:
            raise SystemExit(
                f"unit {source_unit.get('id', '?')}: derived fields are forbidden in analysis: "
                + ", ".join(sorted(forbidden))
            )
        unit = copy.deepcopy(source_unit)
        evidence_specs = unit.pop("evidence", None)
        if not isinstance(evidence_specs, list) or not evidence_specs:
            raise SystemExit(f"unit {unit.get('id', '?')}: evidence must be a non-empty array")
        selected: list[dict[str, Any]] = []
        for spec in evidence_specs:
            evidence_id = spec.get("id")
            item = evidence_by_id.get(evidence_id)
            if item is None:
                raise SystemExit(f"unit {unit.get('id', '?')}: unknown evidence {evidence_id!r}")
            label = spec.get("label", "").strip()
            summary = spec.get("summary", "").strip()
            if not label or not summary:
                raise SystemExit(f"unit {unit.get('id', '?')}: {evidence_id} requires label and summary")
            selected.append(item)
            ownership[evidence_id] += 1
            evidence_labels[evidence_id] = (label, summary)
        kinds = {item["kind"] for item in selected}
        if "text_hunk" in kinds and len(kinds) > 1:
            raise SystemExit(f"unit {unit.get('id', '?')}: text and typed evidence require separate units")

        unit_id = unit.get("id")
        anchors = [_anchor(item, *evidence_labels[item["evidence_id"]]) for item in selected]
        paths = list(dict.fromkeys(item["path"] for item in selected))
        for file_id in dict.fromkeys(item["file_id"] for item in selected):
            file_units[file_id].append(unit_id)
        segments: list[dict[str, Any]] = []
        diff_chunks: list[bytes] = []
        if kinds == {"text_hunk"}:
            grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for item in selected:
                grouped.setdefault((item["source_artifact_id"], item["file_id"]), []).append(item)
            for (source_id, _), group in grouped.items():
                group.sort(key=lambda item: item["byte_start"])
                metadata_start = group[0]["file_start"]
                metadata_end = group[0]["metadata_end"]
                segments.append(
                    {
                        "source_artifact_id": source_id,
                        "byte_start": metadata_start,
                        "byte_length": metadata_end - metadata_start,
                    }
                )
                diff_chunks.append(raw_sources[source_id][metadata_start:metadata_end])
                for item in group:
                    segments.append(
                        {
                            "source_artifact_id": source_id,
                            "byte_start": item["byte_start"],
                            "byte_length": item["byte_length"],
                        }
                    )
                    start = item["byte_start"]
                    diff_chunks.append(raw_sources[source_id][start:start + item["byte_length"]])
        unit["files"] = paths
        unit["evidence_ids"] = [item["evidence_id"] for item in selected]
        unit["changed_lines"] = sum(item["additions"] + item["deletions"] for item in selected)
        unit["diff"] = b"".join(diff_chunks).decode("utf-8")
        unit["diff_segments"] = segments
        unit["anchors"] = anchors
        unit["finding_ids"] = finding_ids_by_unit.get(unit_id, [])
        unit["verification_ids"] = verification_ids_by_unit.get(unit_id, [])
        units.append(unit)

    missing = [item["evidence_id"] for item in evidence_items if ownership[item["evidence_id"]] == 0]
    duplicated = [item for item, count in ownership.items() if count > 1]
    if missing or duplicated:
        details = []
        if missing:
            details.append("unassigned: " + ", ".join(missing))
        if duplicated:
            details.append("duplicated: " + ", ".join(duplicated))
        raise SystemExit("evidence ownership incomplete; " + "; ".join(details))

    files = []
    for item in inventory.get("files", []):
        file_item = copy.deepcopy(item)
        file_item["unit_ids"] = file_units[item["id"]]
        files.append(file_item)
    source_by_id = {item["id"]: item for item in source_artifacts}
    ledger = []
    for item in evidence_items:
        owner = next(unit for unit in units if item["evidence_id"] in unit["evidence_ids"])
        state = "redacted" if source_by_id[item["source_artifact_id"]]["redacted"] else "validated"
        ledger.append(
            {
                "evidence_id": item["evidence_id"],
                "source_artifact_id": item["source_artifact_id"],
                "kind": item["kind"],
                "byte_start": item["byte_start"],
                "byte_length": item["byte_length"],
                "unit_id": owner["id"],
                "lane": owner["lane"],
                "importance": owner["importance"],
                "state": state,
                "fingerprint": item["fingerprint"],
                "display_fingerprint": item["display_fingerprint"],
            }
        )

    state_counts = Counter(item["state"] for item in ledger)
    report_meta = copy.deepcopy(inventory.get("report", {}))
    report_meta["source_artifact_ids"] = [item["id"] for item in source_artifacts]
    report_meta["diff_digest"] = review_digest(source_artifacts)
    report_meta["diff_bytes"] = sum(item["diff_bytes"] for item in source_artifacts)
    report_meta["mutable"] = any(item["mutable"] for item in source_artifacts)
    report_meta["drift"] = (
        "stale" if any(item["drift"] == "stale" for item in source_artifacts)
        else "unknown" if any(item["drift"] == "unknown" for item in source_artifacts)
        else "unchanged" if report_meta["mutable"]
        else "immutable"
    )
    report = {
        "schema_version": "1.5",
        "report": report_meta,
        "source_artifacts": source_artifacts,
        "summary": {
            "files": len(files),
            "hunks": sum(item["kind"] == "text_hunk" for item in ledger),
            "additions": sum(item["additions"] for item in files),
            "deletions": sum(item["deletions"] for item in files),
            "evidence_total": len(ledger),
            "evidence_validated": state_counts["validated"] + state_counts["redacted"],
        },
        "outcome": copy.deepcopy(analysis.get("outcome", {})),
        "context_sources": _context_sources(analysis.get("context_sources", [])),
        "requirements": copy.deepcopy(analysis.get("requirements", [])),
        "files": files,
        "units": units,
        "evidence_ledger": ledger,
        "findings": findings,
        "verification": verifications,
        "coverage": {
            "total": len(ledger),
            "assigned_once": len(ledger),
            "presented_once": len(ledger),
            "validated": state_counts["validated"],
            "redacted": state_counts["redacted"],
            "missing": 0,
            "duplicated": 0,
            "unknown": 0,
        },
    }
    errors = validate_report(report)
    if errors:
        raise SystemExit("Invalid compiled ManDiff report:\n- " + "\n- ".join(errors))
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    inventory_parser = subparsers.add_parser("inventory", help="freeze and index diff sources")
    inventory_parser.add_argument("manifest", type=Path)
    inventory_parser.add_argument("output", type=Path)
    compile_parser = subparsers.add_parser("compile", help="compile declarative analysis")
    compile_parser.add_argument("inventory", type=Path)
    compile_parser.add_argument("analysis", type=Path)
    compile_parser.add_argument("output", type=Path)
    args = parser.parse_args()

    if args.command == "inventory":
        inventory = create_inventory(args.manifest)
        _write_json(args.output, inventory)
        print(
            f"Indexed {len(inventory['files'])} file(s) and "
            f"{len(inventory['evidence'])} evidence item(s): {args.output}"
        )
        return
    report = compile_report(args.inventory, args.analysis)
    _write_json(args.output, report)
    print(f"Compiled and validated ManDiff report: {args.output}")


if __name__ == "__main__":
    main()
