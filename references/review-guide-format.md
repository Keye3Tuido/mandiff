# Review Guide Format

Use this template as a contract. Omit a subsection only when it is genuinely irrelevant; do not omit evidence or coverage fields.

## 1. Visual review layer

Lead with the visual review map defined in [visual-review-format.md](visual-review-format.md). It is the primary navigation surface; the sections below remain the exact, portable audit record.

## 2. Review target

- Selector: `<selector>`
- Repository: `<repository identity or path>`
- Aggregate base/head: `<identities when meaningful across all sources>`
- Source artifacts: `<ordered Sxx IDs>`
- Review digest: `<SHA-256 of ordered source manifest, aggregate byte count>`
- Mutable selector: `<yes/no>`
- Scope exclusions: `<explicit exclusions>`

| Source | Provenance | Selector and acquisition | Base / head | Captured | Raw digest / bytes | Drift |
|---|---|---|---|---|---|---|
| `S01` | `<staged/unstaged/commit/range/PR/patch>` | `<exact selector and read-only operation>` | `<identities>` | `<timestamp>` | `<SHA-256 / bytes>` | `<state>` |

## 3. Review outcome

### Confirmed

List only conclusions established by selected evidence.

### Defects

List actionable defects and their owning findings.

### Unproven

Name the requested behaviors the current scope cannot establish.

### Recommendation

State `accept`, `request changes`, or `expand scope`, with one concise reason.

## 4. Overall change map

### Purpose

Summarize the observable change in a short paragraph. Separate confirmed behavior from inferred intent.

### Scale

| Metric | Value |
|---|---:|
| Files | `<count>` |
| Text hunks | `<count>` |
| Additions | `<count>` |
| Deletions | `<count>` |
| Renames | `<count>` |
| Binary entries | `<count>` |
| Submodule entries | `<count>` |
| Main-path evidence | `<count>` |
| Supporting evidence | `<count>` |

### Behavioral themes

List a small number of concrete themes. Avoid repeating filenames as themes.

### Dependency flow

Describe the order in which contracts, implementation, integration, and verification depend on one another.

### Risk hotspots

Identify the highest-risk units and explain the failure mode each could introduce.

## 5. Review plan

| Step | Lane | Importance | Review unit | Evidence IDs | Main question |
|---:|---|---|---|---|---|
| 1 | `<main/supporting>` | `<critical/normal/context>` | `<title>` | `<linked ID · path:line · meaning>` | `<question>` |

## 6. Step `<n>/<total>`: `<review unit title>`

### Original logic before this change

This section must appear before the review question, before/after summary, and exact diff. Explain the minimum complete pre-change model:

- **Architecture:** where this behavior sits and which boundary it crosses.
- **Responsibilities:** what each relevant component does; do not list names without duties.
- **Original flow:** the trigger, direct calls or reads/writes, state transition, and returned or visible result in order.
- **Data and state:** who owns the relevant data, where it is read or written, and which conditions govern the result.
- **Frozen context:** cite and show the exact pre-change excerpts that establish the explanation.

Use `baseline.guide` and [context-guide.md](context-guide.md) to render architecture/dependency, call, and flow diagrams from structured evidence. Follow with complete scenarios showing concrete inputs, each action/result, and the active stack. Every node and arrow has a source reference. Markdown includes Mermaid plus readable tables and step/stack text; HTML provides node/arrow/step selection and frozen-source navigation. Stacks are explicitly source-derived illustrations. If execution is irrelevant or unknown, state why instead of fabricating a flow.

For main `critical` or `normal` units, never substitute the changed hunk, commit message, or inferred intent for pre-change source. If the original flow cannot be established, classify it as missing context and recommend expanding scope before presenting the diff as reviewable.

### Goal

Explain what behavior this unit changes and why it exists.

### Behavior contract

State the concrete input/state, operation, and externally observable result. Cite the claims and evidence that establish each part.

### Background and prerequisites

Provide only additional lifecycle, invariant, framework, or compatibility knowledge not already covered by the original-logic section.

### Entry point and call path

Name the direct entry point and show only the caller/callee or reader/writer chain needed to audit this unit. Mark missing links as `Unknown`.

### Before and after

State previous behavior and new behavior. Mark inferred intent as `Inference:`.

### Affected surface

- Evidence: `<linked ID · path:line · meaning>`
- Lane: `<main/supporting>`
- Importance: `<critical/normal/context>`
- Files: `<paths>`
- Symbols: `<functions, classes, keys, or interfaces>`
- Depends on: `<earlier units or external contracts>`

### Hunk map

| Evidence | Stable anchor | Role in this unit |
|---|---|---|
| `<linked ID plus concise label>` | `<provenance, path, hunk header or entry type>` | `<what this evidence establishes and why it belongs here>` |

Never print a changed-evidence ID such as `F01-H01` by itself. Every occurrence must include a readable file-and-line locator when available and what the evidence establishes; link it to this hunk-map entry in Markdown and to the owning exact diff in interactive output.

### Mechanism walkthrough

Walk through control flow, data flow, state transitions, and error paths in 3-7 causal steps.

### Invariants, consumers, and compatibility

List added, preserved, removed, or unknown invariants; direct consumers; and persistence, migration, or compatibility effects. Cite evidence for each factual statement.

### Claims and evidence

| Claim | Kind | Statement | Evidence | Confidence |
|---|---|---|---|---|
| `<ID>` | `<observed/contextual/reported/inferred/unknown>` | `<one falsifiable statement>` | `<evidence IDs>` | `<high/medium/low>` |

### Exact diff

```diff
<verbatim original diff entries and complete hunks>
```

### Human review checks

| Check | Setup | Action | Expected result | Claims |
|---|---|---|---|---|
| `<ID>` | `<precondition>` | `<observable operation>` | `<specific pass condition>` | `<claim IDs>` |

### Failure modes and unknowns

For each risk, state `trigger -> observable effect -> detection or mitigation` and link it to evidence or an explicit inference. List remaining unknowns separately; do not silently fill them from commit or requirement text.

### Reviewer notes

Classify evidence-backed observations as one of:

- `Defect:` behavior is demonstrably wrong or unsafe.
- `Risk:` behavior may fail under a concrete condition that needs verification.
- `Design question:` the code is coherent but a product or architectural decision remains.
- `Missing context:` the available evidence cannot establish the answer.

Do not manufacture an item for every category.

### Unit conclusion

Classify the result as `confirmed`, `partially confirmed`, `defect`, or `unproven`. State the decision available now and the exact evidence preventing a stronger result.

### Step conclusion

State what the reviewer can now accept, reject, or carry forward. Report immutable evidence status here. If a separate reviewer-state overlay exists, summarize its human decision without writing that decision into the report model.

## 6. End-to-end synthesis

Explain how the units combine into the complete runtime, build, migration, or user-visible behavior. Call out contracts that span multiple units.

## 7. Findings and open questions

Order concrete findings by severity. Keep design questions separate from defects.

## 8. Verification matrix

| Behavior or invariant | Existing evidence | Recommended check | Status |
|---|---|---|---|
| `<item>` | `<test, code path, or none>` | `<command or manual scenario>` | `<verified/not run/missing>` |

## 9. Coverage report

| Coverage item | Count |
|---|---:|
| Total evidence IDs | `<count>` |
| Assigned exactly once | `<count>` |
| Presented exactly once | `<count>` |
| Byte-validated | `<count>` |
| Explicitly redacted | `<count>` |
| Missing | `0` |
| Duplicated | `0` |
| Unknown | `0` |

List non-text entries and any redactions explicitly. Report the frozen diff digest and `Drift check: unchanged/immutable/stale`. Completion requires every item to be validated or explicitly redacted, with zero missing, duplicated, and unknown evidence IDs. This reports presentation coverage only; it does not imply human approval.

For multi-volume output, append:

- This volume: `<evidence IDs>`
- Cumulative: `<presented>/<total>`
- Remaining: `<evidence IDs>`
