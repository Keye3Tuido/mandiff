#!/usr/bin/env python3
"""Prepare and finalize portable ManDiff reviews with minimal Agent-authored data."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Optional

from compile_review import compile_report, create_inventory
from context_guide import guide_records
from render_markdown import render_markdown
from render_review import render_html
from validate_review import SCHEMA_PATH


ROOT = Path(__file__).resolve().parent.parent
HTML_TEMPLATE = ROOT / "assets" / "review-explorer-template.html"
RESERVED_FILES = {
    "source-manifest.json",
    "inventory.json",
    "analysis-draft.json",
    "analysis.json",
    "prepare-state.json",
    "context-candidates.json",
    "review.json",
    "review.md",
    "review.html",
    "authoring-help.json",
    "performance.json",
}
PLACEHOLDERS = {
    "<state the decision this unit enables>",
    "<state the behavior contract>",
    "<state what the selected evidence proves or cannot prove>",
    "<describe the previous behavior>",
    "<describe the new behavior>",
    "<include only decision-relevant context>",
    "<state the evidence-backed review disposition>",
    "<explain where the original behavior sits in the system>",
}
HUNK_LOCATOR = re.compile(r"@@[^@]*@@\s*(.*)$")
GENERIC_PHRASES = ("verify correctness", "may break", "works as expected", "review changes")


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


def _git(repo: Path, args: list[str]) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if process.returncode:
        detail = process.stderr.decode("utf-8", "replace").strip()
        raise SystemExit(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def _git_text(repo: Path, args: list[str]) -> str:
    return _git(repo, args).decode("utf-8", "replace").strip()


def _repo_root(path: Path) -> Path:
    return Path(_git_text(path.resolve(), ["rev-parse", "--show-toplevel"]))


def _resolve_commit(repo: Path, revision: str) -> str:
    return _git_text(repo, ["rev-parse", "--verify", f"{revision}^{{commit}}"])


def _command_text(repo: Path, args: list[str]) -> str:
    quoted = " ".join(json.dumps(item) for item in ["git", "-C", str(repo), *args])
    return quoted


def _capture_git(repo: Path, args: list[str], **metadata: Any) -> dict[str, Any]:
    raw = _git(repo, args)
    return {
        "raw": raw,
        "capture_argv": args,
        "acquisition": _command_text(repo, args),
        **metadata,
    }


def _capture_sources(args: argparse.Namespace) -> tuple[Optional[Path], list[dict[str, Any]], dict[str, str]]:
    selector = ""
    aggregate = {"base": "", "head": ""}
    if args.patch:
        repo = _repo_root(args.repo) if args.repo else None
        patch = args.patch.resolve()
        try:
            raw = patch.read_bytes()
        except OSError as error:
            raise SystemExit(f"Cannot read patch {patch}: {error}") from error
        if not raw:
            raise SystemExit("The selected patch is empty")
        if args.provenance == "pull_request" and (not args.base or not args.head):
            raise SystemExit("pull_request patch capture requires --base and --head")
        selector = args.selector_label or str(patch)
        aggregate = {"base": args.base or "", "head": args.head or ""}
        return repo, [{
            "raw": raw,
            "capture_argv": None,
            "acquisition": f"read exact patch bytes from {patch}",
            "provenance": args.provenance,
            "selector": selector,
            "base": aggregate["base"],
            "head": aggregate["head"],
            "mutable": False,
        }], {"selector": selector, **aggregate}

    repo = _repo_root(args.repo or Path.cwd())
    head = _resolve_commit(repo, "HEAD")
    sources: list[dict[str, Any]] = []
    if args.unstaged:
        selector = "unstaged"
        sources.append(_capture_git(
            repo,
            ["diff", "--no-ext-diff", "--binary"],
            provenance="unstaged",
            selector=selector,
            base="INDEX",
            head="WORKTREE",
            mutable=True,
        ))
        aggregate = {"base": "INDEX", "head": "WORKTREE"}
    elif args.staged:
        selector = "staged"
        sources.append(_capture_git(
            repo,
            ["diff", "--cached", "--no-ext-diff", "--binary"],
            provenance="staged",
            selector=selector,
            base=head,
            head="INDEX",
            mutable=True,
        ))
        aggregate = {"base": head, "head": "INDEX"}
    elif args.uncommitted:
        selector = "uncommitted"
        sources.extend([
            _capture_git(
                repo,
                ["diff", "--cached", "--no-ext-diff", "--binary"],
                provenance="staged",
                selector="staged portion of uncommitted",
                base=head,
                head="INDEX",
                mutable=True,
            ),
            _capture_git(
                repo,
                ["diff", "--no-ext-diff", "--binary"],
                provenance="unstaged",
                selector="unstaged portion of uncommitted",
                base="INDEX",
                head="WORKTREE",
                mutable=True,
            ),
        ])
        aggregate = {"base": head, "head": "WORKTREE"}
    elif args.commit:
        resolved = _resolve_commit(repo, args.commit)
        parent_line = _git_text(repo, ["rev-list", "--parents", "-n", "1", resolved]).split()
        parents = parent_line[1:]
        if not parents:
            parent = _git_text(repo, ["hash-object", "-t", "tree", "/dev/null"])
        elif len(parents) == 1:
            parent = parents[0]
        else:
            if args.parent is None:
                raise SystemExit(f"Merge commit {resolved} requires --parent 1..{len(parents)}")
            if args.parent < 1 or args.parent > len(parents):
                raise SystemExit(f"--parent must be between 1 and {len(parents)}")
            parent = parents[args.parent - 1]
        selector = resolved
        sources.append(_capture_git(
            repo,
            ["diff", "--no-ext-diff", "--binary", parent, resolved],
            provenance="commit",
            selector=selector,
            base=parent,
            head=resolved,
            mutable=False,
        ))
        aggregate = {"base": parent, "head": resolved}
    elif args.range:
        match = re.fullmatch(r"(.+?)(\.\.\.?)(.+)", args.range)
        if not match:
            raise SystemExit("--range must use BASE..HEAD or BASE...HEAD syntax")
        left = _resolve_commit(repo, match.group(1))
        right = _resolve_commit(repo, match.group(3))
        separator = match.group(2)
        diff_selector = f"{left}{separator}{right}"
        base = _git_text(repo, ["merge-base", left, right]) if separator == "..." else left
        selector = diff_selector
        sources.append(_capture_git(
            repo,
            ["diff", "--no-ext-diff", "--binary", diff_selector],
            provenance="commit_range",
            selector=selector,
            base=base,
            head=right,
            mutable=False,
        ))
        aggregate = {"base": base, "head": right}
    else:
        raise SystemExit("No selector was supplied")

    if not any(source["raw"] for source in sources):
        raise SystemExit("The selected Git diff is empty")
    if not args.uncommitted:
        sources = [source for source in sources if source["raw"]]
    return repo, sources, {"selector": selector, **aggregate}


def _default_output(repo: Optional[Path], report_id: str) -> Path:
    documents = Path.home() / "Documents"
    root = documents if documents.is_dir() else Path.home()
    repository_name = repo.name if repo else "patch"
    base = root / "mandiff-reviews" / repository_name / report_id
    candidate = base
    suffix = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.name}-{suffix}")
        suffix += 1
    return candidate


def _repository_identity(repo: Optional[Path], fallback: Path) -> str:
    if not repo:
        return str(fallback)
    try:
        origin = _git_text(repo, ["remote", "get-url", "origin"])
    except SystemExit:
        origin = ""
    return origin or str(repo)


def _prepare_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    collisions = sorted(item for item in RESERVED_FILES if (path / item).exists())
    if collisions:
        raise SystemExit(f"Output directory already contains ManDiff artifacts: {', '.join(collisions)}")


def _require_output_outside_repo(output: Path, repo: Optional[Path]) -> None:
    if not repo:
        return
    try:
        output.resolve().relative_to(repo.resolve())
    except ValueError:
        return
    raise SystemExit(f"ManDiff output must be outside the reviewed repository: {repo}")


def _owned_private_dir(state: dict[str, Any]) -> Optional[Path]:
    private_value = state.get("private_dir")
    if not private_value:
        return None
    private_dir = Path(private_value).resolve()
    temporary_root = Path(tempfile.gettempdir()).resolve()
    if (
        private_dir.parent != temporary_root
        or not private_dir.name.startswith("mandiff-private-")
        or private_dir.is_symlink()
    ):
        raise SystemExit("Refusing to use an invalid ManDiff private directory")
    marker = private_dir / ".mandiff-owner"
    try:
        marker_value = marker.read_text(encoding="ascii")
    except OSError as error:
        raise SystemExit("ManDiff private directory ownership marker is missing") from error
    if not secrets.compare_digest(marker_value, state.get("private_token", "")):
        raise SystemExit("ManDiff private directory ownership marker does not match")
    return private_dir


def _support_category(path: str) -> Optional[str]:
    value = path.lower()
    padded = f"/{value}"
    name = Path(value).name
    if name.endswith((".lock", "-lock.json")) or name in {"package-lock.json", "pnpm-lock.yaml", "yarn.lock"}:
        return "lockfiles"
    if (
        any(token in padded for token in ("/test/", "/tests/", "/__tests__/", ".test.", ".spec."))
        or name.startswith("test_")
        or re.search(r"_test\.[^.]+$", name)
    ):
        return "tests"
    if any(token in padded for token in ("/fixture", "/snapshot", "/__snapshots__/")):
        return "fixtures"
    if name.endswith((".md", ".rst")) or "/docs/" in padded:
        return "documentation"
    if any(token in padded for token in ("/generated/", "/dist/", "/vendor/")):
        return "generated files"
    return None


def _locator(item: dict[str, Any]) -> str:
    match = HUNK_LOCATOR.search(item.get("header", ""))
    if match and match.group(1).strip():
        return match.group(1).strip()
    if item.get("new_start") is not None:
        return f"line {item['new_start']}"
    return item["kind"]


def _evidence_spec(item: dict[str, Any]) -> dict[str, str]:
    locator = _locator(item)
    label = f"{item['path']} · {locator}"
    if item["kind"] == "text_hunk":
        summary = (
            f"Changes {item['additions']} added and {item['deletions']} removed line(s) near {locator}."
        )
    else:
        summary = f"Records the selected {item['kind'].replace('_', ' ')} change for {item['path']}."
    return {"id": item["evidence_id"], "label": label, "summary": summary}


def _scaffold_units(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    group_index: dict[str, int] = {}
    for item in inventory["evidence"]:
        category = _support_category(item["path"])
        if item["kind"] != "text_hunk":
            key = f"typed:{item['evidence_id']}"
        elif category:
            key = f"supporting:{category}"
        else:
            key = f"main:{item['path']}"
        if key not in group_index:
            group_index[key] = len(groups)
            groups.append((key, []))
        groups[group_index[key]][1].append(item)

    units: list[dict[str, Any]] = []
    for _, group_items in groups:
        chunks: list[list[dict[str, Any]]] = []
        current: list[dict[str, Any]] = []
        changed_lines = 0
        for item in group_items:
            item_lines = item["additions"] + item["deletions"]
            if current and (len(current) >= 12 or changed_lines + item_lines > 600):
                chunks.append(current)
                current = []
                changed_lines = 0
            current.append(item)
            changed_lines += item_lines
        if current:
            chunks.append(current)
        for chunk_index, items in enumerate(chunks, start=1):
            category = _support_category(items[0]["path"])
            lane = "supporting" if category else "main"
            paths = list(dict.fromkeys(item["path"] for item in items))
            title = f"Review supporting {category}" if category else f"Review {paths[0]}"
            if len(chunks) > 1:
                title += f" (part {chunk_index})"
            units.append(
                {
                    "key": f"unit-{len(units) + 1}",
                    "title": title,
                    "lane": lane,
                    "importance": "context" if lane == "supporting" else "normal",
                    "question": "<state the decision this unit enables>",
                    "contract": "<state the behavior contract>",
                    "conclusion": {
                        "status": "unproven",
                        "statement": "<state what the selected evidence proves or cannot prove>",
                    },
                    "before": "<describe the previous behavior>",
                    "after": "<describe the new behavior>",
                    "background": "<include only decision-relevant context>",
                    "baseline": {
                        "architecture": "<explain where the original behavior sits in the system>",
                        "responsibilities": [],
                        "flow_steps": [],
                        "data_and_state": [],
                        "context_refs": [],
                    },
                    "mechanism_steps": [],
                    "evidence": [_evidence_spec(item) for item in items],
                }
            )
    return units


def _context_candidates(repo: Optional[Path], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tracked: list[str] = []
    if repo:
        tracked = _git(repo, ["ls-files", "-z"]).decode("utf-8", "replace").split("\0")
    test_files = [path for path in tracked if path and _support_category(path) == "tests"]
    result = []
    changed_paths = list(dict.fromkeys(item["path"] for item in evidence))
    for path in changed_paths:
        stem = re.sub(r"[^a-z0-9]", "", Path(path).stem.lower())
        suggestions = []
        if stem:
            suggestions = [candidate for candidate in test_files if stem in re.sub(r"[^a-z0-9]", "", candidate.lower())][:5]
        locators = list(dict.fromkeys(_locator(item) for item in evidence if item["path"] == path))
        result.append({"path": path, "locators": locators, "suggested_tests": suggestions})
    return result


def prepare(args: argparse.Namespace) -> Path:
    started = time.perf_counter()
    repo, sources, aggregate = _capture_sources(args)
    digest_input = b"\0".join(source["raw"] for source in sources)
    report_id = hashlib.sha256(digest_input).hexdigest()[:12]
    output = args.output.resolve() if args.output else _default_output(repo, report_id)
    _require_output_outside_repo(output, repo)
    try:
        _prepare_output(output)
    except PermissionError:
        if args.output:
            raise SystemExit(f"Cannot write requested output directory: {output}")
        output = Path(tempfile.mkdtemp(prefix=f"mandiff-{report_id}-"))
        _require_output_outside_repo(output, repo)
    source_dir = output / "sources"
    source_dir.mkdir(parents=True, exist_ok=True)

    redaction_values: list[bytes] = []
    private_dir: Optional[Path] = None
    private_key_path: Optional[Path] = None
    private_token: Optional[str] = None
    if args.redactions:
        redactions = _load_json(args.redactions.resolve())
        values = redactions.get("values")
        if not isinstance(values, list) or not values or not all(isinstance(value, str) and value for value in values):
            raise SystemExit("redactions file must contain a non-empty string array named 'values'")
        redaction_values = [value.encode("utf-8") for value in values]
        private_dir = Path(tempfile.mkdtemp(prefix=f"mandiff-private-{report_id}-"))
        private_token = secrets.token_hex(16)
        (private_dir / ".mandiff-owner").write_text(private_token, encoding="ascii")
        private_key_path = private_dir / "hmac.key"
        private_key_path.write_bytes(secrets.token_bytes(32))
        (private_dir / "redactions.json").write_text(
            json.dumps({"values": values}, ensure_ascii=False), encoding="utf-8"
        )

    manifest_sources = []
    capture_checks = []
    matched_redactions: set[bytes] = set()
    for index, source in enumerate(sources, start=1):
        diff_path = source_dir / f"source-{index:02d}.diff"
        display = source["raw"]
        for value in redaction_values:
            if value in display:
                matched_redactions.add(value)
                display = display.replace(value, b"[REDACTED]")
        diff_path.write_bytes(display)
        manifest_source = {
            "diff_path": str(diff_path),
            "provenance": source["provenance"],
            "selector": source["selector"],
            "acquisition": source["acquisition"],
            "base": source["base"],
            "head": source["head"],
            "mutable": source["mutable"],
            "drift": "unknown" if source["mutable"] else "immutable",
        }
        if display != source["raw"]:
            assert private_dir is not None and private_key_path is not None
            original_path = private_dir / f"source-{index:02d}.original.diff"
            original_path.write_bytes(source["raw"])
            manifest_source.update(
                {
                    "redacted": True,
                    "original_diff_path": str(original_path),
                    "hmac_key_path": str(private_key_path),
                }
            )
        manifest_sources.append(manifest_source)
        if source["capture_argv"] is not None:
            capture_checks.append(
                {
                    "source_id": f"S{index:02d}",
                    "argv": source["capture_argv"],
                    "digest": hashlib.sha256(source["raw"]).hexdigest(),
                }
            )

    unmatched = [value.decode("utf-8", "replace") for value in redaction_values if value not in matched_redactions]
    if unmatched:
        if private_dir:
            shutil.rmtree(private_dir)
        raise SystemExit(f"{len(unmatched)} redaction value(s) were not present in the selected diff")

    repository = args.repository or _repository_identity(repo, args.patch or repo)
    manifest = {
        "schema_version": "1.0",
        "report": {
            "id": report_id,
            "repository": repository,
            "selector": aggregate["selector"],
            "base": aggregate["base"],
            "head": aggregate["head"],
            "scope_exclusions": args.scope_exclusion or [],
        },
        "sources": manifest_sources,
    }
    manifest_path = output / "source-manifest.json"
    _write_json(manifest_path, manifest)
    try:
        inventory = create_inventory(manifest_path)
    except BaseException:
        if private_dir and private_dir.exists():
            shutil.rmtree(private_dir)
        raise
    _write_json(output / "inventory.json", inventory)
    draft = {
        "schema_version": "2.0",
        "recommendation": {
            "disposition": "expand_scope",
            "reason": "<state the evidence-backed review disposition>",
        },
        "context_sources": [],
        "requirements": [],
        "units": _scaffold_units(inventory),
        "findings": [],
        "verification": [],
    }
    _write_json(output / "analysis-draft.json", draft)
    _write_json(
        output / "context-candidates.json",
        {"schema_version": "1.0", "files": _context_candidates(repo, inventory["evidence"])},
    )
    _write_json(
        output / "prepare-state.json",
        {
            "schema_version": "1.0",
            "repository_root": str(repo) if repo else None,
            "capture_checks": capture_checks,
            "private_dir": str(private_dir) if private_dir else None,
            "private_token": private_token,
        },
    )
    _write_json(output / "authoring-help.json", {
        "enums": _authoring_enums(),
        "references": {"claim_refs": "local claim key or unit-key.claim-key", "failure_refs": "local failure key or owning-unit.failure-key", "context_refs": "context source keys", "evidence": "inventory evidence IDs"},
        "optional_views": "Combine baseline.views (table, sequence, state, relationships) with baseline.guide (diagrams and scenario/stack navigation) as needed. Select guide.views from structure, calls, flow. Core guides are expanded; use guide.expanded=false only for supplementary detail.",
        "view_rows": "from, label, to, context_refs; columns label those three values in that order. View-level context_refs may supply a shared default.",
        "depth": "Choose the number, scope and detail of diagrams/scenarios by comprehension needs, uncertainty and consequence. Save time through shared evidence and fewer retries; do not drop useful views merely for speed or small line count.",
    })
    _write_json(output / "performance.json", {"prepared_at": time.time(), "prepare_seconds": round(time.perf_counter() - started, 6), "finalize_attempts": []})
    return output


def _authoring_enums() -> dict[str, list[str]]:
    definitions = _load_json(SCHEMA_PATH)["$defs"]
    result = {}
    for name in ("context_source", "claim", "invariant", "verification", "finding", "unit", "context_view"):
        for field, rule in definitions[name]["properties"].items():
            if "enum" in rule:
                result[f"{name}.{field}"] = rule["enum"]
    return result


def _draft_enum_errors(draft: dict[str, Any]) -> list[str]:
    errors = []
    enums = _authoring_enums()
    def check(kind, values, path):
        for index, value in enumerate(values):
            for key, allowed in enums.items():
                name, field = key.split(".")
                if name == kind and field in value and value[field] not in allowed:
                    errors.append(f"{path}[{index}].{field}: {value[field]!r}; allowed: {', '.join(allowed)}")
    check("context_source", draft.get("context_sources", []), "context_sources")
    check("verification", draft.get("verification", []), "verification")
    check("finding", draft.get("findings", []), "findings")
    check("unit", draft.get("units", []), "units")
    for index, unit in enumerate(draft.get("units", [])):
        check("claim", unit.get("claims", []), f"units[{index}].claims")
        check("invariant", unit.get("invariants", []), f"units[{index}].invariants")
        check("context_view", unit.get("baseline", {}).get("views", []), f"units[{index}].baseline.views")
    return errors


def _placeholder_errors(value: Any, path: str = "$") -> list[str]:
    errors = []
    if isinstance(value, str) and value.strip() in PLACEHOLDERS:
        errors.append(f"{path}: unresolved placeholder {value!r}")
    elif isinstance(value, dict):
        for key, item in value.items():
            errors.extend(_placeholder_errors(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(_placeholder_errors(item, f"{path}[{index}]"))
    return errors


def _context_bytes(repo: Path, source: dict[str, Any]) -> tuple[bytes, str]:
    path = source["path"]
    revision = source.get("revision", "")
    if revision == "WORKTREE":
        candidate = (repo / path).resolve()
        try:
            candidate.relative_to(repo.resolve())
        except ValueError as error:
            raise SystemExit(f"context path escapes repository: {path}") from error
        try:
            return candidate.read_bytes(), revision
        except OSError as error:
            raise SystemExit(f"Cannot read context path {path}: {error}") from error
    if revision == "INDEX":
        return _git(repo, ["show", f":{path}"]), revision
    resolved = _resolve_commit(repo, revision)
    return _git(repo, ["show", f"{resolved}:{path}"]), resolved


def _freeze_context_sources(draft: dict[str, Any], state: dict[str, Any]) -> None:
    repo_value = state.get("repository_root")
    for index, source in enumerate(draft.get("context_sources", []), start=1):
        if "excerpt" in source:
            continue
        if not repo_value:
            raise SystemExit(f"context source {index}: excerpt is required when no Git repository was captured")
        start = source.pop("start", None)
        line_count = source.pop("lines", None)
        if not isinstance(start, int) or start < 1 or not isinstance(line_count, int) or line_count < 1:
            raise SystemExit(f"context source {index}: start and lines must be positive integers")
        raw, revision = _context_bytes(Path(repo_value), source)
        selected = b"".join(raw.splitlines(keepends=True)[start - 1:start - 1 + line_count])
        if not selected:
            raise SystemExit(f"context source {index}: selected line range is empty")
        source["revision"] = revision
        source["start_line"] = start
        source["excerpt"] = selected.decode("utf-8", "replace")


def _redaction_values(state: dict[str, Any]) -> list[str]:
    private_dir = _owned_private_dir(state)
    if not private_dir:
        return []
    values_path = private_dir / "redactions.json"
    redactions = _load_json(values_path)
    return redactions.get("values", [])


def _redact_strings(value: Any, redactions: list[str]) -> Any:
    if isinstance(value, str):
        for secret in redactions:
            value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, list):
        return [_redact_strings(item, redactions) for item in value]
    if isinstance(value, dict):
        return {key: _redact_strings(item, redactions) for key, item in value.items()}
    return value


def _unique_key(item: dict[str, Any], fallback: str, seen: set[str], label: str) -> str:
    key = item.get("key", fallback)
    if not isinstance(key, str) or not key:
        raise SystemExit(f"{label}: key must be a non-empty string")
    if key in seen:
        raise SystemExit(f"{label}: duplicate key {key!r}")
    seen.add(key)
    return key


def _resolve_refs(refs: Any, local: dict[str, str], global_refs: dict[str, str], label: str) -> list[str]:
    result = []
    for ref in refs or []:
        resolved = local.get(ref, global_refs.get(ref, ref if isinstance(ref, str) and re.match(r"^(F\d|C\d|RQ\d|M\d|U\d|CL\d|FM\d|R\d|V\d)", ref) else None))
        if not resolved:
            raise SystemExit(f"{label}: unknown reference {ref!r}")
        if resolved not in result:
            result.append(resolved)
    return result


def _completeness(unit: dict[str, Any]) -> dict[str, str]:
    support = unit["lane"] == "supporting" or unit["importance"] == "context"
    mapping = {
        "baseline": "baseline",
        "contract": "contract",
        "entry_points": "entry_points",
        "call_path": "call_path",
        "mechanism": "mechanism_steps",
        "invariants": "invariants",
        "consumers": "consumers",
        "compatibility": "compatibility",
        "failure_modes": "failure_modes",
        "checks": "checks",
        "unknowns": "unknowns",
    }
    overrides = unit.pop("field_states", {})
    result = {}
    for output_key, field in mapping.items():
        if output_key in overrides:
            result[output_key] = overrides[output_key]
        elif output_key == "baseline":
            baseline = unit.get("baseline", {})
            complete = (
                baseline.get("architecture")
                and baseline.get("responsibilities")
                and baseline.get("flow_steps")
                and baseline.get("data_and_state")
                and baseline.get("context_refs")
            )
            result[output_key] = "complete" if complete else ("not_applicable" if support else "unknown")
        elif unit.get(field):
            result[output_key] = "complete"
        else:
            result[output_key] = "not_applicable" if support or output_key == "unknowns" else "unknown"
    return result


def _expand_draft(draft: dict[str, Any], inventory: dict[str, Any]) -> dict[str, Any]:
    if draft.get("schema_version") == "1.0":
        return copy.deepcopy(draft)
    if draft.get("schema_version") != "2.0":
        raise SystemExit("analysis-draft.json: schema_version must be '2.0'")
    placeholders = _placeholder_errors(draft)
    if placeholders:
        raise SystemExit("Unresolved analysis placeholders:\n- " + "\n- ".join(placeholders))

    evidence_items = {item["evidence_id"]: item for item in inventory["evidence"]}
    global_refs = {evidence_id: evidence_id for evidence_id in evidence_items}
    seen: set[str] = set(evidence_items)
    contexts = []
    for index, source in enumerate(draft.get("context_sources", []), start=1):
        item = copy.deepcopy(source)
        key = _unique_key(item, f"context-{index}", seen, "context source")
        item.pop("key", None)
        item["id"] = f"C{index:02d}"
        contexts.append(item)
        global_refs[key] = item["id"]
    requirements = []
    message_number = 1
    requirement_number = 1
    for index, source in enumerate(draft.get("requirements", []), start=1):
        item = copy.deepcopy(source)
        key = _unique_key(item, f"requirement-{index}", seen, "reported source")
        item.pop("key", None)
        if item.get("kind") == "requirement":
            item["id"] = f"RQ{requirement_number:02d}"
            requirement_number += 1
        else:
            item["id"] = f"M{message_number:02d}"
            message_number += 1
        requirements.append(item)
        global_refs[key] = item["id"]

    unit_keys: dict[str, str] = {}
    source_units = draft.get("units", [])
    if not source_units:
        raise SystemExit("analysis-draft.json: units must not be empty")
    for index, source in enumerate(source_units, start=1):
        key = _unique_key(source, f"unit-{index}", seen, "review unit")
        unit_keys[key] = f"U{index:02d}"
        global_refs[key] = unit_keys[key]

    claim_number = 1
    failure_number = 1
    check_number = 1
    units = []
    unit_locals: dict[str, dict[str, str]] = {}
    unit_failures: dict[str, dict[str, str]] = {}
    for index, source in enumerate(source_units, start=1):
        item = copy.deepcopy(source)
        key = item.pop("key", f"unit-{index}")
        unit_id = unit_keys[key]
        evidence_specs = []
        for spec in item.pop("evidence", []):
            spec = {"id": spec} if isinstance(spec, str) else copy.deepcopy(spec)
            evidence_id = spec.get("id")
            original = evidence_items.get(evidence_id)
            if original is None:
                raise SystemExit(f"{key}: unknown evidence {evidence_id!r}")
            defaults = _evidence_spec(original)
            evidence_specs.append(
                {
                    "id": evidence_id,
                    "label": spec.get("label") or defaults["label"],
                    "summary": spec.get("summary") or defaults["summary"],
                }
            )
        if not evidence_specs:
            raise SystemExit(f"{key}: evidence must not be empty")
        item.update(
            {
                "id": unit_id,
                "order": index,
                "entry_points": item.get("entry_points", []),
                "call_path": item.get("call_path", []),
                "mechanism_steps": item.get("mechanism_steps", []),
                "invariants": item.get("invariants", []),
                "consumers": item.get("consumers", []),
                "compatibility": item.get("compatibility", []),
                "unknowns": item.get("unknowns", []),
                "symbols": item.get("symbols", []),
                "evidence": evidence_specs,
            }
        )
        baseline = item.get("baseline", {})
        if baseline:
            baseline["context_refs"] = _resolve_refs(
                baseline.get("context_refs", []), {}, global_refs, f"{key}.baseline.context_refs"
            )
            for record in guide_records(baseline.get("guide", {})):
                record["context_refs"] = _resolve_refs(
                    record.get("context_refs", []), {}, global_refs, f"{key}.baseline.guide"
                )
            for view in baseline.get("views", []):
                default_refs = view.pop("context_refs", [])
                for row in view.get("rows", []):
                    row["context_refs"] = _resolve_refs(row.get("context_refs", default_refs), {}, global_refs, f"{key}.baseline.views")
            item["baseline"] = baseline
        item["depends_on"] = [unit_keys.get(value, value) for value in item.get("depends_on", [])]
        local_refs: dict[str, str] = {}
        claims = []
        for claim_index, source_claim in enumerate(item.get("claims", []), start=1):
            claim = copy.deepcopy(source_claim)
            claim_key = claim.pop("key", f"claim-{claim_index}")
            if claim_key in local_refs or claim_key in global_refs:
                raise SystemExit(f"{key}: duplicate claim key {claim_key!r}")
            claim_id = f"CL{claim_number:02d}"
            claim_number += 1
            local_refs[claim_key] = claim_id
            global_refs[f"{key}.{claim_key}"] = claim_id
            claim["id"] = claim_id
            default_refs = [spec["id"] for spec in evidence_specs] if claim.get("kind") == "observed" else []
            claim["evidence_refs"] = _resolve_refs(
                claim.get("evidence_refs", default_refs), local_refs, global_refs, f"{key}.{claim_key}"
            )
            claims.append(claim)
        item["claims"] = claims
        unit_locals[key] = local_refs

        failures = []
        local_failures: dict[str, str] = {}
        for failure_index, source_failure in enumerate(item.get("failure_modes", []), start=1):
            failure = copy.deepcopy(source_failure)
            failure_key = failure.pop("key", f"failure-{failure_index}")
            if failure_key in local_failures:
                raise SystemExit(f"{key}: duplicate failure key {failure_key!r}")
            failure_id = f"FM{failure_number:02d}"
            failure_number += 1
            local_failures[failure_key] = failure_id
            failure["id"] = failure_id
            failure["evidence_refs"] = _resolve_refs(
                failure.get("evidence_refs", []), local_refs, global_refs, f"{key}.{failure_key}"
            )
            failure["claim_ids"] = _resolve_refs(
                failure.pop("claim_refs", []), local_refs, global_refs, f"{key}.{failure_key}.claim_refs"
            )
            failures.append(failure)
        item["failure_modes"] = failures
        unit_failures[key] = local_failures

        checks = []
        for check_index, source_check in enumerate(item.get("checks", []), start=1):
            check = copy.deepcopy(source_check)
            check.pop("key", None)
            check["id"] = f"CK{check_number:02d}"
            check_number += 1
            check["claim_ids"] = _resolve_refs(
                check.pop("claim_refs", []), local_refs, global_refs, f"{key}.check-{check_index}.claim_refs"
            )
            checks.append(check)
        item["checks"] = checks
        for invariant in item["invariants"]:
            invariant["evidence_refs"] = _resolve_refs(
                invariant.get("evidence_refs", []), local_refs, global_refs, f"{key}.invariant"
            )
        conclusion = item["conclusion"]
        conclusion["evidence_refs"] = _resolve_refs(
            conclusion.get("evidence_refs", [spec["id"] for spec in evidence_specs]),
            local_refs,
            global_refs,
            f"{key}.conclusion",
        )
        item["completeness"] = _completeness(item)
        units.append(item)

    findings = []
    finding_keys: dict[str, str] = {}
    for index, source in enumerate(draft.get("findings", []), start=1):
        item = copy.deepcopy(source)
        key = _unique_key(item, f"finding-{index}", seen, "finding")
        item.pop("key", None)
        item["id"] = f"R{index:02d}"
        finding_keys[key] = item["id"]
        global_refs[key] = item["id"]
        unit_key = item.pop("unit")
        item["unit_id"] = unit_keys.get(unit_key, unit_key)
        local = unit_locals.get(unit_key, {})
        failures = dict(unit_failures.get(unit_key, {}))
        failures.update({f"{unit_key}.{key}": value for key, value in list(failures.items())})
        owner = next(unit for unit in units if unit["id"] == item["unit_id"])
        item["evidence_ids"] = _resolve_refs(
            item.pop("evidence_refs", owner["evidence"] and [spec["id"] for spec in owner["evidence"]]),
            local,
            global_refs,
            f"finding {key}.evidence_refs",
        )
        item["claim_ids"] = _resolve_refs(item.pop("claim_refs", []), local, global_refs, f"finding {key}.claim_refs")
        item["failure_mode_ids"] = _resolve_refs(
            item.pop("failure_refs", []), failures, global_refs, f"finding {key}.failure_refs"
        )
        findings.append(item)

    verifications = []
    for index, source in enumerate(draft.get("verification", []), start=1):
        item = copy.deepcopy(source)
        key = _unique_key(item, f"verification-{index}", seen, "verification")
        item.pop("key", None)
        item["id"] = f"V{index:02d}"
        global_refs[key] = item["id"]
        source_unit_refs = item.pop("unit_refs", [])
        item["unit_ids"] = [unit_keys.get(value, value) for value in source_unit_refs]
        local = unit_locals.get(source_unit_refs[0], {}) if len(source_unit_refs) == 1 else {}
        item["claim_ids"] = _resolve_refs(
            item.pop("claim_refs", []), local, global_refs, f"verification {key}.claim_refs"
        )
        item.setdefault("existing_evidence", "")
        verifications.append(item)

    custom_outcome = draft.get("outcome", {})
    if custom_outcome:
        outcome = {
            key: [
                {
                    "statement": entry["statement"],
                    "refs": _resolve_refs(entry.get("refs", []), {}, global_refs, f"outcome.{key}"),
                }
                for entry in custom_outcome.get(key, [])
            ]
            for key in ("confirmed", "defects", "unproven")
        }
    else:
        defect_units_with_findings = {
            item["unit_id"] for item in findings if item["category"] == "defect"
        }
        outcome = {
            "confirmed": [
                {"statement": unit["conclusion"]["statement"], "refs": [unit["id"]]}
                for unit in units
                if unit["conclusion"]["status"] == "confirmed"
            ],
            "defects": [
                {"statement": item["description"], "refs": [item["id"], item["unit_id"]]}
                for item in findings
                if item["category"] == "defect"
            ] + [
                {"statement": unit["conclusion"]["statement"], "refs": [unit["id"]]}
                for unit in units
                if unit["conclusion"]["status"] == "defect"
                and unit["id"] not in defect_units_with_findings
            ],
            "unproven": [
                {"statement": unit["conclusion"]["statement"], "refs": [unit["id"]]}
                for unit in units
                if unit["conclusion"]["status"] in {"partially_confirmed", "unproven"}
            ],
        }
    recommendation = copy.deepcopy(draft.get("recommendation", {}))
    default_refs = []
    if recommendation.get("disposition") == "request_changes":
        default_refs = [ref for item in outcome["defects"] for ref in item["refs"]]
    elif recommendation.get("disposition") == "expand_scope":
        default_refs = [ref for item in outcome["unproven"] for ref in item["refs"]]
    recommendation["refs"] = _resolve_refs(
        recommendation.get("refs", default_refs or [units[0]["id"]]), {}, global_refs, "recommendation.refs"
    )
    outcome["recommendation"] = recommendation
    return {
        "schema_version": "1.0",
        "outcome": outcome,
        "context_sources": contexts,
        "requirements": requirements,
        "units": units,
        "findings": findings,
        "verification": verifications,
    }


def _lint_warnings(draft: dict[str, Any]) -> list[str]:
    warnings = []
    statements: dict[str, str] = {}
    for index, unit in enumerate(draft.get("units", []), start=1):
        key = unit.get("key", f"unit-{index}")
        for field in ("title", "question", "contract", "before", "after", "background"):
            value = unit.get(field, "")
            lowered = value.lower() if isinstance(value, str) else ""
            if any(phrase in lowered for phrase in GENERIC_PHRASES):
                warnings.append(f"{key}.{field}: generic wording may not support a review decision")
            if value and value in statements:
                warnings.append(f"{key}.{field}: duplicates {statements[value]}")
            elif value:
                statements[value] = f"{key}.{field}"
    return warnings


def _check_drift(workdir: Path, inventory: dict[str, Any]) -> None:
    state = _load_json(workdir / "prepare-state.json")
    repo_value = state.get("repository_root")
    if not repo_value:
        return
    repo = Path(repo_value)
    stale = []
    source_by_id = {item["id"]: item for item in inventory["sources"]}
    for check in state.get("capture_checks", []):
        raw = _git(repo, check["argv"])
        digest = hashlib.sha256(raw).hexdigest()
        source = source_by_id.get(check["source_id"])
        if digest != check["digest"]:
            stale.append(check["source_id"])
            if source:
                source["drift"] = "stale"
        elif source and source["mutable"]:
            source["drift"] = "unchanged"
    _write_json(workdir / "inventory.json", inventory)
    if stale:
        raise SystemExit("Review source changed after prepare: " + ", ".join(stale))


def finalize(workdir: Path) -> tuple[Path, list[str]]:
    started = time.perf_counter()
    metrics_path = workdir / "performance.json"
    metrics = _load_json(metrics_path) if metrics_path.exists() else {"finalize_attempts": []}
    attempt = {"status": "failed", "stages_seconds": {}}
    if metrics.get("prepared_at") and not metrics["finalize_attempts"]:
        metrics["prepare_to_first_finalize_seconds"] = round(time.time() - metrics["prepared_at"], 3)
    try:
        result = _finalize(workdir, attempt["stages_seconds"])
        attempt["status"] = "success"
        return result
    finally:
        attempt["total_seconds"] = round(time.perf_counter() - started, 6)
        metrics["finalize_attempts"].append(attempt)
        if workdir.is_dir():
            _write_json(metrics_path, metrics)


def _finalize(workdir: Path, stages: dict[str, float]) -> tuple[Path, list[str]]:
    previous = time.perf_counter()
    def mark(label):
        nonlocal previous
        now = time.perf_counter()
        stages[label] = round(now - previous, 6)
        previous = now
    workdir = workdir.resolve()
    inventory_path = workdir / "inventory.json"
    draft_path = workdir / "analysis-draft.json"
    inventory = _load_json(inventory_path)
    draft = _load_json(draft_path)
    state = _load_json(workdir / "prepare-state.json")
    _check_drift(workdir, inventory)
    mark("read_and_drift")
    errors = _draft_enum_errors(draft)
    if errors:
        raise SystemExit("Draft errors (see authoring-help.json):\n- " + "\n- ".join(errors))
    placeholders = _placeholder_errors(draft)
    if placeholders:
        raise SystemExit("Unresolved analysis placeholders:\n- " + "\n- ".join(placeholders))
    _freeze_context_sources(draft, state)
    draft = _redact_strings(draft, _redaction_values(state))
    mark("context_and_redaction")
    _write_json(draft_path, draft)
    analysis = _expand_draft(draft, inventory)
    analysis_path = workdir / "analysis.json"
    _write_json(analysis_path, analysis)
    report = compile_report(inventory_path, analysis_path)
    mark("expand_compile_validate")
    report_path = workdir / "review.json"
    _write_json(report_path, report)
    (workdir / "review.md").write_text(render_markdown(report), encoding="utf-8")
    template = HTML_TEMPLATE.read_text(encoding="utf-8")
    (workdir / "review.html").write_text(render_html(report, template), encoding="utf-8")
    mark("render_and_write")
    private_dir = _owned_private_dir(state)
    if private_dir:
        shutil.rmtree(private_dir)
        state["private_dir"] = None
        state["private_token"] = None
        state["private_cleaned"] = True
        _write_json(workdir / "prepare-state.json", state)
    return report_path, _lint_warnings(draft)


def cleanup(workdir: Path) -> bool:
    state_path = workdir.resolve() / "prepare-state.json"
    state = _load_json(state_path)
    private_dir = _owned_private_dir(state)
    if not private_dir:
        return False
    if private_dir.exists():
        shutil.rmtree(private_dir)
    state["private_dir"] = None
    state["private_token"] = None
    state["private_cleaned"] = True
    state["abandoned"] = True
    _write_json(state_path, state)
    return True


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare_parser = commands.add_parser("prepare", help="freeze a selector and create a compact analysis draft")
    prepare_parser.add_argument("--repo", type=Path)
    prepare_parser.add_argument("--output", type=Path)
    prepare_parser.add_argument("--repository")
    prepare_parser.add_argument("--scope-exclusion", action="append")
    selectors = prepare_parser.add_mutually_exclusive_group(required=True)
    selectors.add_argument("--unstaged", action="store_true")
    selectors.add_argument("--staged", action="store_true")
    selectors.add_argument("--uncommitted", action="store_true")
    selectors.add_argument("--commit")
    selectors.add_argument("--range")
    selectors.add_argument("--patch", type=Path)
    prepare_parser.add_argument("--parent", type=int)
    prepare_parser.add_argument("--provenance", choices=("patch", "pull_request"), default="patch")
    prepare_parser.add_argument("--selector-label")
    prepare_parser.add_argument("--base")
    prepare_parser.add_argument("--head")
    prepare_parser.add_argument("--redactions", type=Path)
    finalize_parser = commands.add_parser("finalize", help="compile, drift-check, and render a completed draft")
    finalize_parser.add_argument("workdir", type=Path)
    cleanup_parser = commands.add_parser("cleanup", help="remove private redaction material from an abandoned review")
    cleanup_parser.add_argument("workdir", type=Path)
    return parser


def main() -> None:
    args = _parser().parse_args()
    if args.command == "prepare":
        output = prepare(args)
        print(f"Prepared ManDiff review: {output}")
        print(f"Edit semantic draft: {output / 'analysis-draft.json'}")
        return
    if args.command == "cleanup":
        removed = cleanup(args.workdir)
        print("Removed private ManDiff material." if removed else "No private ManDiff material was present.")
        return
    report, warnings = finalize(args.workdir)
    for warning in warnings:
        print(f"Warning: {warning}", file=sys.stderr)
    print(f"Finalized ManDiff review: {report.parent / 'review.html'}")


if __name__ == "__main__":
    main()
