---
name: mandiff
description: Create a portable, evidence-complete review guide for a selected Git diff, commit, range, patch, or pull request. Explain the original system with source-backed architecture, dependency, call and flow diagrams, then walk through concrete scenarios and source-derived stacks before presenting the diff. Use when a large or cross-cutting change needs behavioral explanation, risk review, or manual audit. Freeze exact evidence and keep the reviewed source read-only.
---

# ManDiff

Turn one selected change set into a decision-grade tutorial for human review. Preserve exact evidence while spending Agent time only on semantic judgment.

## Core contract

1. Treat the selected diff as immutable evidence and the reviewed repository as read-only.
2. Review only the requested selector. Never include adjacent commits, nested repositories, or unrelated changes silently.
3. Account for every selected evidence item exactly once; never hide a remainder bucket.
4. Separate observed facts, frozen context, reported intent, inference, and unknowns.
5. Keep the complete exact diff beside each review unit. Evidence coverage is not human approval.
6. Before showing or explaining a diff, establish how the affected behavior worked before the change. Use source-backed diagrams for architecture, dependencies, calls, and execution; then walk through concrete inputs, actions, state changes, and results with an illustrated active stack. Cite frozen pre-change code for every relationship and step. Label source-derived stacks as illustrations, never runtime captures.
7. Never show a bare evidence ID in human-facing output. Render every reference as the stable ID plus its file and line when available, a plain-language statement of what it proves, and a direct jump to the owning unit and exact diff in interactive output.
8. Produce confirmed behavior, defects, unproven behavior, and a recommended disposition.
9. Keep the canonical output agent-neutral, offline, and independent of a proprietary UI.
10. Write report prose in the predominant language of the current conversation unless the user explicitly requests another language.
11. Write human-facing descriptions in plain, precise, direct, and unambiguous language. Prefer concrete words and short sentences. Use technical terms only when necessary; explain a term at first use, never invent terminology, and state uncertainty plainly when the evidence is insufficient.
12. Use the bundled workflow script. Never create build, encoding, hashing, diff, or rendering helpers.

## Default workflow

Read [references/compiler-workflow.md](references/compiler-workflow.md), then use only two normal commands:

```sh
python3 scripts/mandiff.py prepare <selector arguments>
# Edit only analysis-draft.json in the printed review directory.
python3 scripts/mandiff.py finalize <review-directory>
```

`prepare` owns repository discovery, immutable ref resolution, diff capture, report directory, source manifest, inventory, evidence IDs, default labels, bounded grouping scaffolds, and context/test candidates.

The Agent then reads each hunk once, corrects the proposed behavioral groups, and writes only semantic content in `analysis-draft.json`. Do not write final IDs, completeness tables, hashes, byte spans, ledgers, coverage, outcome aggregation, Markdown, or HTML.

`finalize` owns context freezing, local-key resolution, all final IDs, completeness, outcome aggregation, drift, exact evidence compilation, validation, Markdown, HTML, and private redaction cleanup. Fix only errors it reports; do not restart the review.

## Select the target

Use one selector:

```sh
python3 scripts/mandiff.py prepare --repo <repo> --unstaged
python3 scripts/mandiff.py prepare --repo <repo> --staged
python3 scripts/mandiff.py prepare --repo <repo> --uncommitted
python3 scripts/mandiff.py prepare --repo <repo> --commit <revision>
python3 scripts/mandiff.py prepare --repo <repo> --commit <merge> --parent <n>
python3 scripts/mandiff.py prepare --repo <repo> --range <base..head>
python3 scripts/mandiff.py prepare --patch <patch-file>
```

Use `--output <directory>` only when the user requested a location; otherwise accept the portable default outside the reviewed repository. Use `--repository`, `--selector-label`, `--base`, `--head`, and `--provenance pull_request` to describe a provider-frozen patch. A pull-request patch requires frozen base and head identities.

If repository or selector intent is ambiguous, ask one concise question. Merge commits require an explicit parent. Submodule evidence covers only the pointer unless nested changes are explicitly selected.

## Review the prepared evidence

The prepared directory contains:

- `inventory.json`: compact exact evidence index;
- `analysis-draft.json`: Agent-editable semantic model;
- `context-candidates.json`: changed locators and nearby test-name candidates;
- `sources/`: frozen safe display diffs;
- `prepare-state.json`: machine-owned acquisition and drift state.

Read the inventory and each frozen hunk once. Treat proposed units and lane classifications as scaffolding, not conclusions. Group by behavior and dependency rather than filename. Keep contracts and core behavior before integration, user-facing effects, tests, and mechanical consequences.

Before analyzing what changed, build the pre-change baseline for each main unit. Read the minimum frozen definitions, direct callers and callees, state owners, and contracts needed to answer four questions: where this behavior sits, what the relevant parts are responsible for, how control and data moved before the change, and which data or state governed the result. Use the selector's pre-change side, not the changed worktree. If the available source cannot establish the baseline, mark the unit as missing context and expand scope; do not compensate with assumptions.

Read [references/context-guide.md](references/context-guide.md) before authoring that baseline. Build `baseline.guide` from the same frozen code: named components and responsibilities, directed relations with precise meanings, execution steps and conditions, and complete scenarios showing the active stack. Follow calls across files; distinguish synchronous calls from queued work. Cover every drawn step in a scenario, including affected branches, returns, loops, and asynchronous boundaries. Explain a non-executable change with an explicit reason instead of inventing a stack. The compiler generates diagrams; do not write Mermaid or SVG yourself.

Before editing, determine the report language from the conversation as a whole, not from the language of source code, commit messages, or the bundled example. An explicit user language request wins. Use that language consistently for every human-facing semantic field, including titles, questions, contracts, conclusions, evidence labels and summaries, context summaries, findings, checks, verification, and the final recommendation. Write these fields so a person can understand them without decoding agent jargon: prefer concrete subjects, actions, conditions, and results; use a technical term only when it adds precision; explain it at first use; and do not create names for concepts that the source does not name. If the evidence does not establish a point, say that it is unknown or unverified instead of implying certainty. Preserve source quotations, code, identifiers, paths, commands, and model enum values exactly when translation would change their meaning. Rewrite scaffold text that is in another language; do not produce a mixed-language report merely because the example or diff uses English.

Use:

- `main`: contracts, runtime behavior, state transitions, integration, failure handling, and risk-bearing verification;
- `supporting`: tests, docs, generated output, fixtures, lockfiles, repetitive wiring, and mechanical consequences.

Promote a supposedly mechanical item if it changes behavior or risk. Prefer 1-8 units. The scaffold caps a proposed unit at 12 evidence items or 600 changed lines, but the Agent may merge or split units without duplicating evidence.

## Edit the compact semantic draft

Use stable human keys such as `parser-contract` or `startup-check`; `finalize` assigns `Uxx`, `CLxx`, `FMxx`, `Rxx`, and `Vxx` IDs.

For every unit, provide:

- `key`, semantic `title`, `lane`, and `importance`;
- one `question` and falsifiable `contract`;
- symmetrical `before` and `after` behavior;
- a `baseline` with `architecture`, `responsibilities`, `flow_steps`, `data_and_state`, `context_refs`, and the structured `guide` for main critical/normal units;
- concise `background` and causal `mechanism_steps`;
- one `conclusion` with status and statement;
- exact selected `evidence` IDs, rewriting their labels and summaries in the report language when needed.

For each `critical` or `normal` main unit, the baseline must have at least one responsibility, three original-flow steps, one data/state statement, and one frozen pre-change context reference. Also provide entry points, direct call/data path, invariants, consumers, compatibility, atomic claims, concrete failure modes, explicit unknowns, and executable checks. Main units normally need 3-7 mechanism steps, 1-4 claims, and 1-3 checks.

For supporting or `context` units, omit irrelevant collections. One causal mechanism step is enough for a purely mechanical consequence. `finalize` derives honest `not_applicable` completeness states instead of requiring filler.

References in the compact draft use keys:

- claim `evidence_refs`: changed evidence IDs or context/requirement keys;
- failure/check `claim_refs`: claim keys in the same unit;
- unit `depends_on`: unit keys;
- finding `unit`, `claim_refs`, and `failure_refs`: semantic keys;
- verification `unit_refs` and `claim_refs`: semantic keys;
- cross-unit claim references: `<unit-key>.<claim-key>`.

Observed claims default to the owning unit's changed evidence when `evidence_refs` is omitted. Findings default to the owning unit's evidence. Conclusion references default to the unit evidence. Use explicit references when a statement depends on a narrower or contextual source.

`finalize` derives confirmed, defect, and unproven outcome lists from conclusions and findings. The Agent still writes the recommendation disposition and evidence-backed reason, and may supply explicit outcome entries when the derived summary is insufficient.

Use `tests/fixtures/pipeline-draft.json` as the complete generic compact example. Read [references/review-data-model.md](references/review-data-model.md) only when that example is insufficient or validation fails.

Use `tests/fixtures/context-guide-draft.json` for a complete cross-file example with branching and a queued callback. Its original source files are in `tests/fixtures/context-system/`. Diagram labels, relation explanations, scenario inputs, step actions, and stack explanations follow the same report-language and plain-language rules as the rest of the report.

## Add frozen pre-change context

Context selection remains semantic; acquisition is mechanical. A context source may contain a direct `excerpt`, or declare:

```json
{
  "key": "reader",
  "kind": "caller",
  "snapshot": "base",
  "revision": "<exact-pre-change-commit-or-HEAD-INDEX>",
  "path": "src/reader.ext",
  "start": 20,
  "lines": 30,
  "locator": "read_value",
  "summary": "Why this context changes the review decision."
}
```

`finalize` reads the exact snapshot, resolves commit refs, slices the declared lines, and fingerprints the excerpt. For a commit or range use `base`; for staged changes use `head` at `HEAD`; for unstaged changes use `index` at `INDEX`; for provider-frozen or standalone patches use `provider`, `base`, or `patch` as appropriate. A main-unit baseline may not cite the changed working tree as its original logic. Add only definitions, direct callers or callees, state owners, contracts, and tests needed to make the original behavior understandable. Stop when the original flow and review decision are both clear; record missing context instead of touring adjacent architecture.

Commit messages, pull-request descriptions, issues, and requirements establish reported intent only. They never prove runtime behavior.

## Redaction

The Agent identifies sensitive values; the script performs every cryptographic and byte-handling step. Put values in a private JSON file, never on the command line:

```json
{"values": ["sensitive literal"]}
```

Pass `--redactions <private-json>` to `prepare`. It creates safe display diffs, keyed original commitments, and temporary private material outside the report. `finalize` redacts matching semantic/context strings and deletes its private material after successful validation. If abandoning the review, run:

```sh
python3 scripts/mandiff.py cleanup <review-directory>
```

Read [references/evidence-protocol.md](references/evidence-protocol.md) only for redaction failures, mixed mutable sources, binary/submodule evidence, or evidence-binding diagnostics.

## Precision and completion

Before finalizing, do one semantic precision pass without rereading every hunk: remove title/diff restatements, unsupported intent verbs, generic risks, vague checks, extrapolation beyond frozen evidence, and human-facing prose left in a different language. Report defect, risk, design question, and missing context separately.

Completion requires `finalize` to succeed with every main unit backed by a complete pre-change baseline and source-backed diagram guide, every evidence item assigned and byte-validated once, zero missing/duplicate/unknown changed evidence, resolved semantic references, valid main-path completeness, and explicit limitations or tests not run. Check each graph arrow against its cited code; structural validation cannot establish that an interpretation is true. When execution is available, verify the scenario follows the declared flow and synchronous stacks, including returns and asynchronous boundaries.

For oversized output, keep one prepared inventory and split only at unit boundaries; never truncate evidence. For host-specific delivery or text-only fallback, read [references/agent-portability.md](references/agent-portability.md). Read visual or Markdown format references only when changing a renderer.

The scripts require Python 3.9+ and Git for repository selectors, use only the standard library, and never modify the reviewed repository.
