---
name: mandiff
description: Turn a specified Git working-tree change, staged change, commit, commit range, patch, or pull request into a portable, visual-first, evidence-complete tutorial for human review. Use when any coding agent is asked to explain a large or cross-cutting diff step by step, split changes into logical review units, visualize dependencies and risks, prepare a change for manual audit, or make code review easier. Freeze the selected diff, build an ordered review path, emit an agent-neutral review model, and present every original hunk exactly once with context and focused human checks. Operate read-only and never modify the reviewed source.
---

# ManDiff

Turn one explicitly selected change set into a decision-grade tutorial for human review. Preserve exact evidence while spending analysis time in proportion to behavioral risk. The output helps a reviewer decide; it does not replace human approval.

## Core contract

1. Treat the selected diff as immutable evidence and the reviewed repository as read-only.
2. Review only the requested selector. Never silently include adjacent commits, nested repositories, or unrelated working-tree changes.
3. Freeze exact raw diff bytes outside the reviewed repository. Never reconstruct, normalize, shorten, or clean up hunks.
4. Account for every file and evidence item exactly once. Never hide unexplained evidence in a remainder bucket.
5. Separate observed facts, frozen context, reported intent, inference, and unknowns. Cite the evidence supporting each decision-relevant claim.
6. Keep the complete exact diff beside each review unit. Evidence coverage does not mean human approval.
7. Never show a bare evidence ID to the reviewer; pair it with its source location and meaning.
8. Produce concrete confirmed behavior, defects, unproven behavior, and a recommended disposition.
9. Keep the canonical output agent-neutral and offline. Do not depend on a vendor API, MCP server, proprietary global, or chat directive.
10. Use the bundled compiler and renderers. Do not create one-off build, encoding, hashing, diff, or rendering scripts.

## Fast default workflow

Read [references/compiler-workflow.md](references/compiler-workflow.md), then follow this loop exactly:

1. Resolve and freeze the selector once.
2. Run `compile_review.py inventory` once.
3. Read every changed hunk once and group related evidence into normally 1-8 behavioral units.
4. Perform one batched context lookup after grouping, limited to context needed for main-path decisions.
5. Write one declarative `analysis.json` using `tests/fixtures/pipeline-analysis.json` as the authoring contract.
6. Run `compile_review.py compile` once. Fix only reported validation errors; do not restart analysis.
7. Render Markdown and HTML once from the successful canonical model.
8. For a mutable selector, perform one final drift check.

Do not read the same diff separately for discovery, explanation, precision, and presentation. Do not write a second narrative for Markdown or HTML. The compiler owns evidence IDs, hashes, byte spans, exact unit diffs, ledgers, counters, and validation.

Load other references only when needed:

- [references/evidence-protocol.md](references/evidence-protocol.md): secret redaction, multiple mutable sources, drift, binary/submodule evidence, or evidence-binding failures.
- [references/review-data-model.md](references/review-data-model.md): the fixture is insufficient or schema validation fails.
- [references/agent-portability.md](references/agent-portability.md): a host adapter or text-only fallback is required.
- [references/visual-review-format.md](references/visual-review-format.md): changing or debugging the HTML renderer.
- [references/review-guide-format.md](references/review-guide-format.md): changing or debugging the Markdown renderer.

Do not load conditional references during a normal review.

## Freeze the target

Confirm the repository and selector. If either is ambiguous and cannot be discovered safely, ask one concise question.

Supported selectors include:

- unstaged changes: `git diff --no-ext-diff --binary`;
- staged changes: `git diff --cached --no-ext-diff --binary`;
- all uncommitted changes: separate staged and unstaged artifacts;
- one commit: `<commit>^..<commit>` for a non-merge commit;
- merge commit: the requested parent, or an explicitly stated first-parent comparison;
- exact commit range or endpoints requested by the user;
- pull request with frozen base and head SHAs;
- patch file or pasted patch as its own source of truth.

Resolve symbolic refs to object IDs. Store every independently acquired diff as a separate source artifact with provenance, selector, base/head, acquisition operation, digest, byte count, mutability, and drift state. Use historical base/head snapshots for surrounding code instead of a possibly different working tree.

For submodule pointers, review the pointer update only unless nested changes are explicitly in scope. For secrets or personal data, follow the redaction protocol before creating any deliverable.

## Inventory evidence

Write the source manifest outside the reviewed repository, then run:

```sh
python3 scripts/compile_review.py inventory source-manifest.json inventory.json
```

The inventory assigns stable file, hunk, and typed non-text IDs. Read it for navigation and the frozen diff for semantics. Never calculate or transcribe IDs, offsets, fingerprints, statistics, or commitments yourself.

Commit messages, PR descriptions, issues, and requirements prove reported intent only. Add frozen context only when it changes a review decision:

- the changed definition or contract;
- direct callers, callees, readers, or writers;
- the nearest relevant test or executable check;
- persistence, migration, configuration, or compatibility rules touched by the change.

Batch those lookups after unit grouping. Stop once the claim is decidable; record an explicit unknown instead of touring adjacent architecture.

## Build the review path

Group by behavior and dependency rather than filename. Prefer contracts, core behavior, integration, user-facing effects, then supporting tests or generated consequences. Keep a change close to its direct tests.

Use two lanes:

- `main`: contracts, runtime behavior, state transitions, integration, failure handling, and risk-bearing verification;
- `supporting`: direct tests, docs, generated output, fixtures, lockfiles, repetitive wiring, and mechanical consequences.

Lane controls analysis depth, never exact-evidence coverage. Promote a supposedly mechanical item when it changes behavior or risk.

Prefer fewer, broader units. Normally use 1-8 units, with about 3-12 related hunks or 100-600 changed lines per unit. Never split a hunk to meet a size target. If a hunk spans concerns, give it one owner and cross-reference its ID without duplicating the diff.

## Author proportionate analysis

For every unit, provide a semantic title, review question, contract, symmetrical before/after statements, concise background, conclusion, evidence labels/summaries, and at least one causal mechanism step.

For each `critical` or `normal` main unit, also provide:

- entry point and direct call/data path;
- 3-7 causal mechanism steps;
- invariants, direct consumers, and compatibility consequences;
- normally 1-4 atomic claims with epistemic kind, evidence, and confidence;
- concrete failure modes in `trigger -> effect -> detection/mitigation` form;
- explicit unknowns;
- normally 1-3 checks in `setup -> action -> expected` form linked to claims.

For supporting or `context` units, keep exact evidence, explanation, and conclusion, but omit irrelevant collections. Use empty arrays and `not_applicable` completeness states instead of inventing claims, risks, consumers, or checks. One short mechanism step is enough for a purely mechanical consequence.

Report a defect only when evidence supports it. Distinguish defect, risk, design question, and missing context. A unit conclusion must be `confirmed`, `partially_confirmed`, `defect`, or `unproven` and state what can be decided now.

Do one precision pass over `analysis.json`, without rereading every hunk:

- split claims that require different evidence or confidence;
- remove title/diff restatements and generic risks;
- replace intent verbs with observed mechanism unless end-to-end evidence proves the outcome;
- keep before/after concrete and mechanism steps causal;
- prefer a short unknown over unsupported extrapolation.

## Compile and render

Run only the bundled pipeline:

```sh
python3 scripts/compile_review.py compile inventory.json analysis.json review.json
python3 scripts/render_markdown.py review.json review.md
python3 scripts/render_review.py review.json review.html
```

The compiler derives and validates source embeddings, exact diffs, anchors, ownership, ledger, summary, coverage, and digest. Its successful result is authoritative; do not manually recount or re-slice evidence afterward. Both renderers consume the same model, so never hand-write a parallel guide.

The report outcome must lead with short lists of confirmed behavior, actionable defects, unproven requested behavior, and `accept`, `request_changes`, or `expand_scope` with evidence-backed reasons. The HTML explorer may store reviewer decisions separately, but mutable state must never alter `review.json`.

If Python or artifact output is unavailable, use the text fallback and state the limitation. Do not reimplement the toolchain in another language.

## Large and mutable reviews

Never truncate evidence. For an oversized guide, preserve one inventory and digest, publish an overview and unit index, then divide output only at unit boundaries. Keep unprocessed evidence in `discovered` or `assigned`, never `presented` or `validated`.

Immediately before completion of a mutable review, reacquire the same selector once. If its digest differs, mark the report stale and stop; never attach old anchors to nearby code.

## Completion gate

Finish only when:

- compile and both renderers succeed;
- every selected evidence item is assigned and validated exactly once, or explicitly redacted;
- coverage has zero missing, duplicated, and unknown changed evidence;
- all main critical/normal units pass the completeness gate;
- claims, checks, findings, and outcome references resolve;
- limitations, unavailable context, binaries, redactions, drift, and tests not run are stated.

The bundled scripts require Python 3.9 or newer and only the standard library. To validate an installation, run the generic fixture commands documented in [references/compiler-workflow.md](references/compiler-workflow.md); fixture validation does not authorize reviewing or modifying the current repository.
