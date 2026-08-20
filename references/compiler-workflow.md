# Compiler Workflow

The Agent owns semantic analysis. `mandiff.py` owns acquisition, evidence mechanics, identifier expansion, drift, validation, and presentation.

## Primary workflow

### 1. Prepare

Run one selector command:

```sh
python3 scripts/mandiff.py prepare --repo /path/to/repo --unstaged
python3 scripts/mandiff.py prepare --repo /path/to/repo --staged
python3 scripts/mandiff.py prepare --repo /path/to/repo --uncommitted
python3 scripts/mandiff.py prepare --repo /path/to/repo --commit REVISION
python3 scripts/mandiff.py prepare --repo /path/to/repo --range BASE..HEAD
python3 scripts/mandiff.py prepare --patch /path/to/change.diff
```

The command prints the review directory and semantic draft path. It:

- discovers the repository root;
- resolves historical refs to immutable object IDs;
- rejects an ambiguous merge parent;
- captures staged and unstaged sources separately;
- writes exact diff bytes outside the reviewed repository;
- creates the source manifest and inventory;
- assigns evidence IDs and mechanical labels;
- proposes bounded main/supporting groups;
- emits changed locators and nearby test-name candidates;
- stores machine-readable acquisition operations for drift.

Use `--output` only for an explicitly requested location. Otherwise the portable default is `~/Documents/mandiff-reviews/<repository>/<digest>/` when Documents exists, or `~/mandiff-reviews/...`.

For a provider-frozen patch, use `--provenance pull_request --selector-label ... --base ... --head ...`. `prepare` does not fetch provider data; the host adapter supplies the already frozen patch.

### 2. Edit semantic data once

Read `inventory.json`, `context-candidates.json`, and each selected hunk. Correct the proposed groups and edit only `analysis-draft.json`.

The draft uses `schema_version: "2.0"` and semantic keys instead of final report IDs. Use `tests/fixtures/pipeline-draft.json` as the complete example.

Agent-authored content is limited to:

- review questions, contracts, before/after behavior, background, and causal mechanism;
- lane, importance, grouping, dependencies, and relevant symbols;
- context selection and summaries;
- atomic claims, failure modes, checks, findings, and verification;
- unit conclusions and final recommendation.

Do not author:

- source manifest or inventory fields;
- final `Uxx`, `CLxx`, `FMxx`, `Rxx`, `Vxx`, `Cxx`, or `RQxx` IDs;
- completeness tables;
- derived outcome lists unless the automatic aggregation needs a semantic override;
- files, changed-line counts, exact unit diffs, segments, anchors, ownership, ledger, summary, digest, or coverage;
- Markdown or HTML.

Optional context can include an excerpt directly. To let the script acquire it, supply exact `revision`, `path`, one-based `start`, and `lines`; `finalize` freezes and fingerprints that range. `WORKTREE` and `INDEX` are accepted revision tokens. Other values resolve to exact commits.

### 3. Finalize

```sh
python3 scripts/mandiff.py finalize <review-directory>
```

The command:

1. reacquires every mutable source and rejects drift;
2. freezes declared context ranges;
3. resolves semantic keys and assigns stable final IDs;
4. derives completeness and outcome aggregation;
5. expands the compact draft into `analysis.json` schema 1.0;
6. compiles and validates canonical `review.json`;
7. renders `review.md` and self-contained `review.html`;
8. removes private redaction material after success.

Fix only the reported draft or validation error, then rerun `finalize`. Do not repeat evidence discovery.

## Compact references

Keys are scoped as follows:

- unit, context, requirement, finding, and verification keys are report-wide;
- claim and failure keys are local to their unit;
- use `<unit-key>.<claim-key>` for a cross-unit claim;
- changed evidence keeps inventory IDs such as `F01-H01`;
- observed claims may omit evidence refs to inherit unit evidence;
- finding evidence and conclusion evidence also default to their unit evidence.

The expander rejects unknown keys, duplicate keys, unresolved scaffold placeholders, missing evidence ownership, and every canonical-model error.

## Redaction

Pass a private JSON value list to prepare:

```sh
python3 scripts/mandiff.py prepare --patch change.diff --redactions /private/redactions.json
```

The script replaces exact values only in display bytes, stores original bytes and a random HMAC key in an OS temporary directory, computes original/display commitments through the inventory compiler, and never embeds private bytes in report artifacts. Finalization applies the same replacement to semantic strings and context before rendering, then deletes script-owned private material.

If work is abandoned before successful finalization:

```sh
python3 scripts/mandiff.py cleanup <review-directory>
```

## Low-level compatibility path

The original declarative compiler remains available for existing integrations and diagnostics:

```sh
python3 scripts/compile_review.py inventory source-manifest.json inventory.json
python3 scripts/compile_review.py compile inventory.json analysis.json review.json
python3 scripts/render_markdown.py review.json review.md
python3 scripts/render_review.py review.json review.html
```

This path accepts full `analysis.json` schema 1.0 and does not provide selector capture, compact keys, automatic IDs/completeness/outcome, context acquisition, or drift orchestration. Do not choose it for a normal review.

If Python is unavailable, use the text-only fallback and state that deterministic packaging was unavailable. Never recreate the toolchain in another language during a review.
