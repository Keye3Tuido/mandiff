---
name: mandiff
description: Explain and audit a selected Git change with source-backed before-and-after system walkthroughs, diagrams, tables, and same-input scenario comparisons. Select scope and detail to balance understanding and generation time. Produce an offline guide with exact evidence without modifying the reviewed source.
---

# ManDiff

Help a reviewer unfamiliar with the code understand both the original and changed system, compare their behavior, then judge the exact diff. Balance generation time with comprehension by selecting what to explain and how deeply. Preserve useful diagrams, tables, scenarios, and call stacks; fewer representations or fewer words are not success criteria.

## Non-negotiable evidence and language

- Keep the reviewed repository read-only. Freeze only the requested selector; do not silently include other commits, submodules, or working-tree changes.
- Present every selected evidence item exactly once with complete original bytes. Never truncate a remainder to save time.
- Separate source facts, reported intent, inference, and unverified behavior. A build is not evidence of runtime behavior.
- Explain original behavior from the pre-change version. Commit/range: base; staged: HEAD; unstaged: INDEX. Mixed staged/unstaged units need both predecessors, or separate units if their behavior differs.
- Explain changed behavior from the selected result: commit/range HEAD, staged INDEX, unstaged WORKTREE. A standalone patch/provider excerpt must state `side: before` or `side: after`. Do not use the original version as evidence of the changed system, including for apparently unchanged functions.
- Use the predominant conversation language unless requested otherwise. Write precise, direct prose with concrete subjects, actions, conditions, and results. Avoid unnecessary terms and invented concepts. Preserve code, identifiers, paths, commands, and source quotations.
- Every human-facing reference needs a readable location and meaning. IDs alone do not explain evidence.

## Default workflow

Use the bundled commands; do not build a custom report generator or hand-author hashes, exact diff spans, final IDs, ledgers, Markdown, or HTML.

```sh
python3 scripts/mandiff.py prepare --repo <repo> --unstaged
# Read the frozen diff, inventory.json, and authoring-help.json.
# Establish both versions and matching scenarios, then edit analysis-draft.json.
python3 scripts/mandiff.py finalize <review-directory>
```

Other selectors: `--staged`, `--uncommitted`, `--commit REV`, `--range BASE..HEAD`, or `--patch FILE`. A merge needs `--parent N`. Ask only when the intended selector is genuinely unclear. A submodule pointer is not authorization to review its nested diff.

Choose a writable output directory outside the reviewed repository using `--output` when useful. If the default Documents destination is denied, the script falls back to an OS temporary directory and prints its location. Avoid repeated permission requests merely to write generated artifacts; respect an explicitly requested destination.

Read [compiler-workflow.md](references/compiler-workflow.md) only for selector, redaction, or authoring details not covered here. `prepare` supplies valid enum values and reference rules in `authoring-help.json`; read it before guessing field names or opening implementation files.

## Decide what the reader needs to understand

Start with the review question. Explain the relevant system boundary, the changed component's responsibility, its input/state and consumers, and a trigger-to-result example in each version. Use the same business scenario, input, starting state, and observation points to compare the two. Explain changed responsibilities, data sources, execution order, conditions, outputs, and failure paths. A before/after summary sentence is not a substitute for the changed system walkthrough.

Choose a complementary set of representations using [presentation.md](references/presentation.md). Decide what each shows and how far it follows the code:

- System organization and shared dependencies: a focused relationship diagram showing the affected component in its surroundings.
- Repeated fields, responsibilities, producers/consumers: a table showing the details needed to judge impact.
- Original behavior: a representative trigger-to-result scenario; include another when a branch materially changes the outcome.
- Order, initialization, callbacks, or state changes: a sequence, flow, or state view showing relevant conditions and transitions.
- Nested execution, return, or asynchronous boundaries: a source-backed call walkthrough and stack at the steps that explain the behavior.

Choose the number of views, nodes, relationships, scenarios, and steps to preserve understanding. A relationship graph and a parameter table can complement each other; do not treat either as a replacement for the other. Keep the overview and representative behavior visible; collapse secondary detail and source excerpts. Use prose alone only when the reader can already locate the behavior and follow its consequences without reconstructing omitted relationships. A small diff is not by itself a reason to omit context.

Use `baseline.views` for tables or interaction steps and `baseline.guide` for diagrams and scenario/stack navigation; see [context-guide.md](references/context-guide.md). They may be used together. `guide.views` selects which diagrams are drawn from shared evidence; there is no need to draw all graph types. Source-derived stacks are illustrations, not captured runtime traces. Stop at a named, evidenced boundary rather than inventing a complete call chain.

Apply the same structure to `post_change.views` and `post_change.guide`. Keep corresponding names, abstraction levels, and scenario inputs aligned. Reuse verified unchanged relationships when authoring, resolving their evidence to the result version. Show a complete changed path through the affected behavior and state which parts remain the same. If a new interface or prerequisite is introduced, compare the old input first, then explain the new prerequisite as an additional scenario; do not silently assume it is already satisfied.

Use matching section order, diagram types and boundaries, table columns and row subjects, and scenario names where they describe the same question. Use neutral labels such as "读取规则及用途" on both sides, not "原来的规则" in the after view. Different node/step counts are legitimate when behavior changes; explain necessary presentation differences in the caption. Do not satisfy symmetry by removing useful detail from the original explanation. Include concrete relevant input/state/output values, and types, defaults or units when they affect the result. Clearly label constructed examples; never present them as captured runtime data.

## Keep generation bounded

Aim to deliver a normal review within **10 minutes**, including analysis, drafting, validation and handoff. Start `prepare` promptly after resolving the selector, so its timer covers the work. Check `mandiff.py status <review-directory>` after source analysis and before finalization. Use these checkpoints as a working budget, not a promise or a reason to hide evidence:

- By minute 4: freeze the diff, establish the relevant path in both versions, and choose matching views and representative scenarios.
- By minute 8: finish one semantic draft. Stop unrelated exploration and equivalent examples; reserve the remaining two minutes for fixing concrete validation errors and delivery.
- At minute 10: deliver the valid report if ready. Otherwise tell the user the specific unresolved question or error and what remains. Mark unknowns and use `expand_scope` when warranted; never claim completion or silently discard required evidence to meet the clock.

Use uncertainty and consequence, not just line count, to decide depth. A one-line authorization or concurrency change may need broad evidence; a large mechanical edit may not.

Save time first by reusing verified source and relationships, acquiring ranges automatically, and avoiding duplicate authoring and validation retries. Then reduce unrelated breadth or repetitive detail. Do not remove an explanatory form that materially helps the reader merely because it takes effort to author. Choose representative cases that cover different outcomes; do not enumerate equivalent paths or trace every getter separately.

- Start with the changed function, its direct caller/consumer, and state owner. Read other code only to resolve a specific open question.
- Reuse context already established in this task after checking revision and scope. Use one context source for multiple relevant references.
- Prefer `revision/path/start/lines` for Git context: the script acquires the excerpt. Do not spend model output reproducing source already on disk.
- Immutable unredacted Git ranges remain compact in the authoring draft after finalize; full excerpts are in `analysis.json` and the final report. Mutable or redacted sources stay frozen. Edit only affected semantic sections; do not re-read or rewrite expanded output as the next draft.
- Read independent files together. Write one semantic draft and do one precision pass; repair reported errors locally rather than restarting discovery.
- Do not compile the project, run application tests, browse the web, or perform browser QA solely to generate a review. Record relevant existing verification; run additional checks only when needed for the decision or requested.
- Do not open the large generic graph example for a simple change. Use the small example below first.
- If analysis expands unexpectedly, tell the user which concrete question needs more evidence. Deliver a valid review with explicit unknowns when necessary; never invent completeness to meet a time target.

`performance.json` records prepare start, the 600-second target, time before the first finalize attempt, attempt count, script stages, and first successful finalize. `status` reports time remaining and whether that first success met the target; later edits do not reset it. Measurements exclude work before prepare and delivery after finalize, and include approval/idle time in between. State these limits; do not claim script timing is total review latency or that a reused demonstration proves a fresh review fits ten minutes.

## Author semantic content

New drafts use `schema_version: "2.1"`; the compiler produces report schema 1.7. Main critical/normal units require `baseline`, `post_change`, and `comparison`, as well as a claim, actionable check, and conclusion. Each side uses the same context structure; simple behavior can use one truthful step. Keep meaningful risks and unknowns. Completed 2.0 drafts remain readable through the legacy path; do not downgrade a new draft to evade the post-change requirement.

Both `baseline` and `post_change` contain `architecture`, `responsibilities`, `flow_steps`, `data_and_state`, and `context_refs`. Their optional `views` and `guide` support tables, diagrams and stacks on both sides. A `comparison` row has `scenario`, shared `input`, `before`, `after`, `impact`, `before_context_refs`, and `after_context_refs`. References belong to the matching side. See [presentation.md](references/presentation.md) for the comparison contract.

Use semantic keys; `finalize` assigns IDs. Claims/checks use local claim keys; findings use a unit key and local or owning-unit-qualified failure keys. Cross-unit claims use `unit-key.claim-key`. Changed evidence uses inventory IDs. Observed claims and conclusions inherit the owning unit's changed evidence unless narrowed explicitly.

Use [tests/fixtures/paired-draft.json](tests/fixtures/paired-draft.json) for a small complete draft with both versions. Use [review-data-model.md](references/review-data-model.md) only for a field not covered by the example or help file. Main units describe behavior; supporting units cover genuinely mechanical tests/docs/fixtures. Do not relabel a risky change as supporting to bypass requirements.

A frozen context source can be declared as:
```json
{"key":"reader","kind":"caller","snapshot":"base","revision":"<pre-change SHA>","path":"src/reader.ext","start":20,"lines":30,"locator":"read_value","summary":"Calls the changed reader and uses its result."}
```
A standalone patch needs supplied original excerpts with explicit provenance. Context records remain separate from changed-evidence coverage.

For secret redaction, supply a private JSON file `{"values":["sensitive literal"]}` through `prepare --redactions FILE`. Never put the secret on the command line. Read [evidence-protocol.md](references/evidence-protocol.md) for special evidence cases; `finalize` handles redaction and deletes its private temporary material after success. On abandonment use `mandiff.py cleanup <review-directory>`.

## Finish

Before finalize, remove duplicate descriptions, unsupported intent, generic risks, vague checks, and prose in the wrong language. Check selected relationships against cited code; schema validation cannot prove an explanation true.

Completion means an unfamiliar reader can locate the changed part, follow the same representative operation before and after, explain where the results diverge or stay the same, and trace both explanations to their source versions. Check that useful relationships have not been compressed into unexplained prose. Preserve exact evidence coverage, explicit risks/unknowns, verification status, and a recommendation. Diagram counts vary with these needs. A missing prerequisite can justify `expand_scope` rather than a speculative conclusion.

Deliver the HTML/Markdown link with what changed and what remains unverified. Read [agent-portability.md](references/agent-portability.md) only for host-specific delivery or text-only fallback. Python 3.9+ and Git are sufficient; the runtime uses the standard library.
