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

Use `--output` to select a writable location outside the reviewed repository. Otherwise the portable default is `~/Documents/mandiff-reviews/<repository>/<digest>/` when Documents exists, or `~/mandiff-reviews/...`. If that default is denied, prepare falls back to an OS temporary directory; it does not override an explicitly requested location. Read the printed path.

For a provider-frozen patch, use `--provenance pull_request --selector-label ... --base ... --head ...`. `prepare` does not fetch provider data; the host adapter supplies the already frozen patch.

### 2. Establish the pre-change baseline

Before explaining any changed line, identify each main unit's original behavior from frozen source on the selector's pre-change side:

- commit or range: `base`;
- staged changes: `head` at `HEAD`;
- unstaged changes: `index` at `INDEX`;
- pull-request or standalone patch: a frozen `provider`, `base`, or `patch` excerpt that represents the pre-change side.

For each main unit, capture only the definitions, direct callers and callees, state owners, contracts, and relevant tests needed to explain:

1. where the behavior sits in the architecture;
2. what each relevant component is responsible for;
3. how control and data flowed before the change;
4. what data or state governed the result.

Write these facts into `baseline.architecture`, `baseline.responsibilities`, `baseline.flow_steps`, `baseline.data_and_state`, and `baseline.context_refs`. A main baseline needs a source-backed explanation of responsibility, original behavior, and relevant state. Schema 1.6 permits one truthful step; do not invent three. Do not use changed working-tree code or inferred intent as proof of original behavior.

Select complementary diagrams, tables, and representative scenarios using [presentation.md](presentation.md). Combine `baseline.views` with the graph/stack `baseline.guide` as needed. Control the scope and detail of each; do not replace useful diagrams and walkthroughs with a table merely to save generation time. `guide.views` selects the diagrams to display while reusing the same records. All displayed relationships still cite original source.

If one unit contains both staged and unstaged evidence, freeze both required predecessors: `HEAD` for the staged portion and `INDEX` for the unstaged portion. If those predecessors describe materially different behavior, split the unit instead of presenting one ambiguous baseline.

### 3. Edit semantic data once

Establish the changed system with the same structure in `post_change`: architecture, responsibilities, flow_steps, data_and_state, context_refs, and selected views/guide. For commit/range use snapshot `head` at the selected result SHA; staged uses `index` at `INDEX`; unstaged uses `working_tree` at `WORKTREE`. In a mixed unit, provide both result snapshots or separate the units. For standalone patch/provider excerpts, declare `side: before` / `side: after` and the correct version. Frozen Git context revisions must match the corresponding source artifact's base/head. Even unchanged code cited after the change must be acquired at the result version.

Add `comparison` rows for the same input before/after. See [presentation.md](presentation.md) for the fields and rules. A short `after` summary or mechanism list alone does not complete the post-change walkthrough.

Read `inventory.json`, `context-candidates.json`, and each selected hunk. Correct the proposed groups and edit only `analysis-draft.json`.

Determine the report language from the predominant language of the current conversation; an explicit user request overrides that default. Use it for all human-facing semantic prose. Write that prose in plain, precise, direct, and unambiguous language: prefer concrete subjects, actions, conditions, and results; keep sentences short where possible; use technical terms only when they add precision; explain each necessary term at first use; and never invent terminology or concepts. When the evidence is insufficient, say that the point is unknown or unverified. Do not infer the report language from the diff, repository, commit message, or English example. Keep code, symbols, paths, commands, source quotations, and fixed enum values unchanged where translation would reduce precision. Rewrite scaffold titles, labels, summaries, and placeholders that do not match the chosen language.

New drafts use `schema_version: "2.1"` and semantic keys instead of final report IDs. Use `tests/fixtures/paired-draft.json` for a simple before/after example, and `authoring-help.json` for enums and references. Completed 2.0 drafts retain the legacy 1.6 path; new drafts must not be downgraded to omit the changed-system explanation.

Agent-authored content is limited to:

- pre-change architecture, responsibilities, original flow, data/state ownership, and context selection;
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

Context can include an excerpt directly. Prefer supplying exact `revision`, `path`, one-based `start`, and `lines`; `finalize` freezes and fingerprints that range. Unredacted immutable Git ranges remain as declarations in `analysis-draft.json`, with the resolved revision pinned; the full excerpt lives in `analysis.json` and the report. Mutable, supplied, or redacted excerpts stay frozen in the draft to avoid changing evidence or exposing secrets on a retry. Edit the compact draft, not generated analysis. `INDEX` is accepted for an unstaged baseline. `WORKTREE` remains available for post-change context, but a main-unit baseline cannot cite it as the original behavior. Other values resolve to exact commits.

### 4. Finalize

```sh
python3 scripts/mandiff.py finalize <review-directory>
```

The command:

1. reacquires every mutable source and rejects drift;
2. freezes declared context ranges and validates main-unit pre-change baselines;
3. resolves semantic keys and assigns stable final IDs;
4. derives completeness and outcome aggregation;
5. expands the compact draft into `analysis.json` schema 1.0;
6. compiles and validates canonical `review.json` schema 1.7, including both versions' frozen context and matching comparison references; supplied graphs, scenarios and stacks are validated independently on each side;
7. renders `review.md` and self-contained `review.html`;
8. removes private redaction material after success.

Fix only the reported draft or validation error, then rerun `finalize`. Do not repeat evidence discovery.

Use `mandiff.py status <review-directory>` after source analysis and before finalization. The default target is 600 seconds from starting prepare to the first successful finalize. At eight minutes it reports `finalize_now`, at ten `over_target`; these are progress signals, not a process timeout. Reserve time for validation and delivery, keep useful paired views, and state any unresolved blocking question if the target cannot be met. Do not reset the work directory or timer to hide overruns.

`performance.json` records preparation and each finalize attempt, including failed attempts, and preserves the first successful finalize time across later edits. The prepare-to-first-finalize gap includes human/model work, permission waiting and idle time; it is not a precise attribution to any one cause. Work before prepare and handoff after finalize are outside the recorded interval. Script timings exclude the gap. Do not conflate fast compilation or a reused demonstration with a fresh end-to-end review under ten minutes.

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
