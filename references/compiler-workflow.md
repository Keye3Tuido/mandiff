# Compiler Workflow

Use this pipeline to keep review generation fast and deterministic. The Agent owns semantic analysis; bundled tools own evidence mechanics and presentation duplication.

## 1. Write the source manifest

Write UTF-8 JSON directly with the host's structured file tool. Keep it outside the reviewed repository:

```json
{
  "schema_version": "1.0",
  "report": {
    "id": "stable-report-id",
    "repository": "repository identity",
    "selector": "exact selected change",
    "base": "optional aggregate base",
    "head": "optional aggregate head",
    "scope_exclusions": []
  },
  "sources": [
    {
      "diff_path": "/absolute/path/to/frozen.diff",
      "provenance": "commit",
      "selector": "base..head",
      "acquisition": "exact read-only command",
      "captured_at": "optional RFC 3339 timestamp",
      "base": "base identity",
      "head": "head identity",
      "mutable": false,
      "drift": "immutable"
    }
  ]
}
```

Keep staged and unstaged sources separate. Use only the provenance values accepted by the final model.

For a redacted source, set `diff_path` to the safe display diff and add `redacted: true`, `original_diff_path`, and `hmac_key_path`. The inventory command computes private original commitments and safe display anchors, then omits the original path and key from its output. Retain the private files only until drift and final validation finish, then delete them.

## 2. Generate the compact inventory

```sh
python3 scripts/compile_review.py inventory source-manifest.json inventory.json
```

The command parses all Git diff sections, assigns source/file/evidence IDs, detects text and typed entries, records byte spans and fingerprints, and checks that frozen paths still match. `inventory.json` does not embed the raw diff bytes, so it remains compact enough for Agent use.

Read the inventory for navigation and read the frozen diff for substantive review. Never calculate or rewrite its mechanical fields.

## 3. Write declarative analysis

Use `tests/fixtures/pipeline-analysis.json` as the complete generic example. Write `analysis.json` directly as UTF-8 JSON; do not generate it with executable code.

Include:

- `schema_version: "1.0"`;
- report outcome, context sources, reported requirements, findings, and verification;
- ordered semantic review units;
- an `evidence` array per unit containing only `id`, human-readable `label`, and decision-relevant `summary`.

Do not include these compiler-derived unit fields:

- `files`, `evidence_ids`, `changed_lines`;
- `diff`, `diff_segments`, `anchors`;
- `finding_ids`, `verification_ids`.

The compiler derives context fingerprints from `excerpt` when present. Otherwise provide a precomputed frozen-context fingerprint.

## 4. Compile once and render twice

```sh
python3 scripts/compile_review.py compile inventory.json analysis.json review.json
python3 scripts/render_markdown.py review.json review.md
python3 scripts/render_review.py review.json review.html
```

Compilation derives exact unit diffs, anchors, source embedding, file/unit links, evidence ledger, summary, digest, drift, and coverage. It rejects unassigned or duplicate evidence, mixed text/non-text units, agent-authored derived fields, changed frozen artifacts, and every final-model validation error.

Both renderers consume the same validated model. Never write a second narrative for Markdown or HTML, and never create `build_review.py`, `build_review_utf8.py`, encoding repair scripts, custom renderers, or equivalent one-off tooling.

If the current host cannot run Python, produce the text-only fallback and state that the portable bundle was unavailable. Do not spend review time reimplementing the toolchain.
