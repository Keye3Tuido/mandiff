---
name: mandiff
description: Turn a specified Git working-tree change, staged change, commit, commit range, patch, or pull request into a portable, visual-first, evidence-complete tutorial for human review. Use when any coding agent is asked to explain a large or cross-cutting diff step by step, split changes into logical review units, visualize dependencies and risks, prepare a change for manual audit, or make code review easier. Freeze the selected diff, build an ordered review path, emit an agent-neutral review model, provide a scannable change map, and present every original hunk exactly once with context and focused human checks. Operate read-only and never modify the reviewed source.
---

# ManDiff

Transform one explicitly selected change set into an ordered, visual-first tutorial for review. Keep the protocol and generated artifacts independent of any agent vendor or chat host. Help the human see the shape of the change, then understand and verify each unit; do not replace human judgment with a verdict.

## Non-negotiable rules

1. Treat the selected diff as immutable evidence.
2. Operate read-only. Do not edit, stage, commit, reset, checkout, rebase, format, or generate files inside the reviewed repository.
3. Review only the selector the user supplied. Never silently include adjacent commits, nested repositories, or unrelated working-tree changes.
4. Quote diff text from the source command or patch. Never reconstruct, normalize, shorten, or "clean up" a hunk.
5. Account for every file and every hunk exactly once. Every item must receive substantive explanation; never hide unexplained evidence in a generic remainder bucket.
6. Separate observed facts, contextual facts, reported intent, inferences, and unresolved unknowns. Every factual clause must cite its evidence source.
7. Explain enough context to audit the code, but avoid generic language tutorials and unrelated architecture tours.
8. Preserve secrets and sensitive values. If the diff contains credentials or personal data, redact the value, mark the redaction, and warn the reviewer.
9. Never truncate evidence supplied for analysis. Batch or divide the review when necessary, and state what remains unprocessed.
10. Treat "presented" as evidence coverage, not human approval. Only the reviewer can mark a change accepted.
11. Make the visual layer evidence-backed. Never invent architecture, flow, risk, or status merely to make the report look complete.
12. Keep the complete exact diff available at the point where each visual review unit is explained. Never default to a changed-lines-only or condensed diff view.
13. Keep the core output agent-neutral. Never require a vendor-specific API, global object, MCP server, UI directive, or proprietary message format.
14. Produce decision-grade conclusions, not only preparation material. Lead with what is confirmed, what is defective, what remains unproven, and the recommended review disposition.
15. Never show a bare evidence ID in human-facing output. Pair every ID with its source location and a one-line explanation; IDs are stable cross-references, not explanations.

## Resolve and freeze the review target

Confirm the repository and selector before analysis. If either is ambiguous and cannot be discovered safely, ask one concise question.

Support these selector types:

- Unstaged working tree: `git diff --no-ext-diff --binary`
- Staged changes: `git diff --cached --no-ext-diff --binary`
- All local uncommitted changes: collect staged and unstaged diffs separately; never merge their provenance
- One non-merge commit: compare `<commit>^` to `<commit>`
- Merge commit: ask which parent to review, or explicitly state that first-parent semantics are being used
- Commit range: compare the exact endpoints or range semantics requested by the user
- Pull request: freeze its base SHA and head SHA, then obtain the patch through the available provider tool
- Patch file or pasted patch: treat that artifact as the complete source of truth

Resolve symbolic refs to immutable object IDs before analysis. Capture the exact raw diff in a uniquely named temporary artifact outside the repository. Normally record its SHA-256 digest and byte count. If it contains a secret, generate an ephemeral private key outside every deliverable and use HMAC-SHA-256 for the original source and affected-anchor commitments; never publish the key or a plain hash that enables offline guessing. Store base64-encoded display bytes in the canonical source artifact: replace only the secret value before encoding, record separate display digest/byte fields, and set `redacted: true`. Never put raw secret bytes in `review.json`, Markdown, or HTML, and do not retain the sensitive temporary artifact or HMAC key after drift and validation finish. Use the frozen artifact, not a later command invocation, as the evidence source for all quoted hunks.

For staged plus unstaged changes, capture two artifacts and retain their provenance. Never collapse two versions of the same lines into one synthetic diff.

Record one `source_artifact` for each independently acquired diff, including selector, provenance, base/head identity, repository root, acquisition command, capture time, digest, byte count, mutability, and drift. Preserve source-artifact order. Bind the complete review to those artifacts with the aggregate digest defined in `references/evidence-protocol.md`. For a historical commit, read surrounding source from the base and head snapshots with `git show <revision>:<path>` rather than trusting a possibly different working tree.

For a submodule pointer change, explain the pointer update only. Inspect the nested repository diff only when the user explicitly includes it in scope.

## Build the evidence inventory

Read [references/evidence-protocol.md](references/evidence-protocol.md) and follow its snapshot, anchor, lane, coverage, and drift rules.

Collect, without mutation:

1. Raw unified diff with rename/copy and binary metadata preserved.
2. `--stat`, `--numstat`, and `--name-status` summaries when Git is the source.
3. Commit metadata and commit list when relevant.
4. Only the surrounding definitions, callers, tests, schemas, configuration, and documentation needed to understand changed behavior.

Do not accept a commit message, PR description, or conversation summary as proof of behavior. Use them only as orientation and verify claims against the frozen diff and surrounding code.

Assign stable evidence IDs:

- Files: `F01`, `F02`, ... in original diff order.
- Hunks: `F01-H01`, `F01-H02`, ... in original hunk order.
- Non-text entries: `F03-BINARY`, `F04-RENAME`, `F05-SUBMODULE`, as applicable.
- Context snapshots: `C01`, `C02`, ... for unchanged definitions, direct callers or callees, tests, schemas, configuration, or documentation.
- Reported intent: `M01`, `M02`, ... for commit or pull-request text, and `RQ01`, `RQ02`, ... for explicit requirements or issue statements.

For each entry, retain an anchor containing its source artifact, provenance, old and new paths, section kind, ordinal, exact hunk header or entry type, old and new line spans when available, byte start and length inside the decoded display artifact, a concise human label, a one-line explanation, and both original and display fingerprints. They are equal unless that evidence is redacted. Recompute the display fingerprint from the byte span. IDs are report-local labels; the commitments detect drift, tampering, or accidental rebinding. Render the ID together with that label and explanation everywhere a human sees it.

Create a canonical `evidence_ledger` entry for every changed evidence ID containing its source artifact, fingerprint, logical unit, review lane, importance, and state. Advance evidence only through `discovered -> assigned -> presented -> validated`; use `redacted` only for the explicit secret-redaction exception. Never call `presented` or `validated` evidence human-reviewed.

Context evidence does not count as changed-hunk coverage and must never own a diff hunk. Freeze each context source to the same immutable base or head snapshot, record its revision, path, symbol or line span, and fingerprint, and identify whether it describes the old state or the new state. Use only direct context that changes the reviewer’s ability to decide:

1. the changed symbol’s definition or data contract;
2. its direct callers, callees, readers, or writers;
3. the nearest tests or executable verification surface;
4. persistence, migration, configuration, or compatibility rules touched by the change;
5. documentation only when it states a contract or conflicts with the code.

Do not collect broad architecture tours. Commit messages, pull-request descriptions, issue text, and user requirements establish reported intent only; they never prove runtime behavior.

## Build the portable review model

Read [references/agent-portability.md](references/agent-portability.md) and [references/review-data-model.md](references/review-data-model.md). Construct the canonical review model before rendering Markdown or HTML.

When artifacts can be written outside the reviewed repository, emit:

- `review.json`: immutable, agent-neutral evidence and analysis;
- `review-state.json`: optional mutable reviewer decisions, exported separately and bound to the report digest;
- `review.md`: portable evidence-complete audit record;
- `review.html`: self-contained visual explorer with the report data embedded.

Prefer `assets/review-explorer-template.html` for consistent portable rendering. When Python is available, run `scripts/validate_review.py <review.json>` and then `scripts/render_review.py <review.json> <review.html>`; the renderer repeats validation before writing. Otherwise validate the schema and all semantic constraints in `references/review-data-model.md`, then replace the template's single embedded-data placeholder with the canonical report JSON using an equivalent safe structured operation.

When artifact output is unavailable, keep the same model internally and render the best available chat representation. The evidence IDs, unit order, findings, verification states, and coverage counts must agree across every representation.

The canonical model must include a report-level `outcome` with four concise parts: `confirmed`, `defects`, `unproven`, and `recommendation`. Every item must point to units, findings, claims, or evidence. State exactly which requested behavior the selected change cannot prove.

## Decompose into a narrative review path

Group evidence by behavior and dependency, not merely by filename. Prefer this order when it matches the change:

1. Contracts, schemas, types, and configuration
2. Core algorithms and state transitions
3. Integration, adapters, and persistence
4. User-facing or operational behavior
5. Tests, migrations, generated artifacts, and documentation

Keep a behavior change and its direct tests close together. A file may participate in several units, but each original hunk may appear in only one unit.

Build two ordered lanes:

- `Main path`: contracts, state transitions, runtime behavior, integration points, failure handling, and risk-bearing verification needed to understand the change.
- `Supporting path`: direct tests, documentation, generated output, repetitive wiring, fixtures, lockfiles, and mechanical consequences.

Use the supporting lane to improve reading order, not to reduce rigor. Every supporting item still requires the same context, exact diff, review checks, and conclusion as a main-path item. If a supposedly mechanical hunk changes behavior or risk, promote it to the main path.

Assign each unit an importance of `critical`, `normal`, or `context`. Use semantic titles that name the review idea, never a filename alone.

Aim for one coherent question per unit. As a guide, use 1-5 tightly related hunks or roughly 40-200 changed lines. Do not split an original hunk to hit a size target. If one hunk is large, present it intact and explain its internal phases before the code block.

If one hunk contains multiple concerns, place it in the unit that owns its primary behavior and cross-reference its evidence ID elsewhere without repeating the diff.

Order units so each one introduces concepts needed by later units. State the dependency when the order is not obvious.

## Build the visual review layer

Read [references/visual-review-format.md](references/visual-review-format.md) and follow it before writing the guide.

Make the first useful view the decision-grade review outcome, followed by the change map. It must show:

- ordered review units and their dependencies;
- main/supporting lane, importance, evidence count, and changed-line weight;
- affected files or components;
- concrete defects, risks, missing context, and verification status;
- progress from evidence discovery through byte validation.

When an interactive HTML surface is available, create a companion review explorer. Selecting a unit must reveal its before/after behavior, prerequisites, affected surface, exact diff, review checks, and findings. Preserve reviewer decisions, four-state check results, finding confirmations or dismissals, and notes locally; support importing and exporting that state without a backend. Generate a concrete human-review conclusion from that mutable state. Keep the full textual guide as the portable fallback and audit record.

When interactive output is unavailable, use the smallest useful static visuals: a dependency flow, a file-to-unit matrix, and a risk/verification table. Do not use decorative diagrams, oversized metric cards, or color without labels.

## Analyze each unit

Before showing its diff, build a minimum sufficient review packet:

1. State one behavior contract and one review question in plain language.
2. Describe previous and new behavior on the same concrete dimension. Do not compare implementation detail on one side with intended outcome on the other.
3. Name the entry point and direct call or data path. Use `unknown` when the available snapshots do not establish it.
4. Supply only required background: lifecycle, invariants, data shape, concurrency model, compatibility constraints, or framework semantics.
5. Identify affected files, symbols, evidence IDs, and the exact role of every hunk.
6. Walk through the mechanism in 3-7 ordered steps, including important state and failure transitions.
7. List invariants as added, preserved, removed, or unknown, with evidence references.
8. Identify direct consumers and compatibility or migration consequences.
9. Describe each plausible failure mode as `trigger -> observable effect -> detection or mitigation`. Do not use generic labels such as "may break behavior".
10. Express each important conclusion as a structured claim with one epistemic kind: `observed`, `contextual`, `reported`, `inferred`, or `unknown`; attach evidence references and `high`, `medium`, or `low` confidence.
11. State explicit unknowns and out-of-scope dependencies instead of completing the story by inference.
12. Finish with one unit conclusion classified as `confirmed`, `partially_confirmed`, `defect`, or `unproven`. State what the reviewer can decide now and what evidence blocks a stronger conclusion.

Then show the exact original hunks in a fenced `diff` block. Include the `diff --git`, file markers, and hunk headers needed to identify provenance. Never replace omitted lines with invented ellipses inside a hunk.

After the diff, provide focused human checks. Each check must state `setup -> action -> expected result`, name the claim it verifies, and be executable or directly observable. Avoid vague checks such as "verify correctness":

- Correctness and invariants
- Boundary and failure cases
- Compatibility and migration impact
- Concurrency, security, performance, or resource lifetime when relevant
- Test coverage and observable verification
- Concrete questions the reviewer must decide

Report a suspected defect only when evidence supports it. Distinguish defects from risks, design questions, and missing context.

## Run the precision pass

Before rendering any unit, edit its analysis for evidence density and precision:

1. Split compound claims when their clauses rely on different sources or confidence levels.
2. Remove claims that merely restate the title, diff, or another claim.
3. Replace intent verbs such as "ensures", "prevents", or "preserves" with observed mechanism unless end-to-end evidence proves the outcome.
4. Keep `before` and `after` concrete, symmetrical, and falsifiable.
5. Keep mechanism steps causal; do not narrate line order when it adds no understanding.
6. Anchor every risk to a trigger and observable failure. Remove generic risk boilerplate.
7. Use commit and requirement text only in `reported` claims. Never upgrade it to `observed` or `contextual` without code or test evidence.
8. Prefer a short explicit unknown over a confident extrapolation beyond the frozen snapshots.
9. Remove generic language, framework lessons, and architecture context that do not change a review decision.

Apply a completeness gate before producing output. Every `critical` and `normal` main-path unit must contain, or explicitly mark `not_applicable` or `unknown` for: contract, entry point, call path, mechanism, invariants, direct consumers, compatibility, failure modes, checks, and unknowns. Every claim must resolve to known evidence IDs; every check must reference claims; every finding must reference a claim or failure mode. Do not render an apparently complete unit that fails this gate.

## Produce the guide

Read [references/review-guide-format.md](references/review-guide-format.md) before writing the result and follow its structure.

Start with a concrete review outcome before metadata or the first unit:

- Confirmed behavior changes supported by selected evidence
- Defects that require a code, test, or documentation change
- Requested behaviors that the selected change cannot prove
- A recommended disposition: `accept`, `request_changes`, or `expand_scope`, with reasons

Then include:

- Review target, frozen identities, diff digest, and mutability
- Change size and file-type breakdown
- High-level behavior changes
- Dependency flow and ordered main/supporting review plan
- Risk hotspots and why they deserve attention
- Evidence coverage totals
- A visual review layer that satisfies `visual-review-format.md`

Then present all review units in order. Finish with:

- Cross-unit behavior and end-to-end flow
- Findings and unresolved questions
- Verification and test matrix
- Coverage report showing discovered, assigned, presented, validated, redacted, missing, duplicated, and unknown evidence
- Drift result for mutable selectors

Completion requires every item to be validated or explicitly redacted, with `missing = 0`, `duplicated = 0`, and `unknown = 0`.

## Handle very large diffs

Never truncate the raw evidence or silently reduce unprocessed hunks to supporting material. Patch excerpts may be used only as navigation aids after the complete hunk has been read; they are never substitutes for analysis.

If the full guide will not fit comfortably in one response:

1. Produce the complete overview and review-unit index first.
2. State the planned volume boundaries and evidence IDs in each volume.
3. Deliver volumes only at unit boundaries.
4. Carry the coverage ledger forward and show cumulative coverage after each volume.
5. Keep every unprocessed item in `discovered` or `assigned`; do not mark unseen evidence as presented or validated.
6. Preserve the same frozen diff digest and anchor inventory across every volume.

If the user requests a standalone report, ask for an output location or use an explicitly approved location outside the reviewed repository. The report must contain the same coverage ledger and exact diffs.

## Final validation

Before finishing:

1. Recount files and hunks from the frozen raw diff.
2. Compare additions/deletions and entry types with the collected summaries.
3. Verify every evidence ID is assigned once and appears in exactly one diff-bearing unit or appropriate non-text entry.
4. Verify each displayed diff block byte-for-byte against the frozen evidence, except explicitly marked secret redactions.
5. Verify all changed evidence reached `validated`, with zero missing, duplicated, unknown, or silently truncated entries. Contextual unknowns remain explicit review content and do not count as missing diff coverage.
6. For mutable selectors, reacquire the same selector and compare its digest with the frozen digest. If it changed, mark the guide stale and stop; never silently repair an anchor onto different code.
7. Verify conclusions do not rely on code outside the frozen base/head snapshots.
8. State any limitations, unavailable context, unrenderable binary changes, redactions, drift, or tests not run.
9. Verify portable HTML works without network access or vendor-specific globals, and that exported review state is bound to the frozen diff digest.
10. Verify every structured claim references existing evidence, every check references existing claims, and every finding references a claim or failure mode.
11. Run the completeness and precision gates; report any failed field as missing context instead of silently weakening the analysis.
12. Run `scripts/validate_review.py` when Python is available. Do not render or deliver a report with schema, cross-reference, aggregate digest, summary, or evidence-ledger errors.

## Validate this skill installation

The bundled scripts require Python 3.9 or newer and only the standard library. From the ManDiff skill directory (or using absolute paths), run this generic fixture, which contains no repository-specific information:

```sh
python3 scripts/validate_review.py tests/fixtures/valid-review.json
python3 scripts/render_review.py tests/fixtures/valid-review.json /tmp/mandiff-review.html
python3 -m unittest discover -s tests -v
```

The renderer creates the requested output directory when needed. These commands test installation only; they do not authorize reviewing or modifying the current repository.
