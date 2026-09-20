---
name: mandiff
description: Explain and audit a selected Git change with source-backed system context, diagrams, tables, scenarios, and call walkthroughs. Select their scope and detail to balance understanding and generation time. Produce an offline review guide with exact evidence without modifying the reviewed source.
---

# ManDiff

Help a reviewer unfamiliar with the code understand the original system, then judge the selected change. Balance generation time with comprehension by selecting what to explain and how deeply. Preserve useful diagrams, tables, scenarios, and call stacks; fewer representations or fewer words are not success criteria.

## Non-negotiable evidence and language

- Keep the reviewed repository read-only. Freeze only the requested selector; do not silently include other commits, submodules, or working-tree changes.
- Present every selected evidence item exactly once with complete original bytes. Never truncate a remainder to save time.
- Separate source facts, reported intent, inference, and unverified behavior. A build is not evidence of runtime behavior.
- Explain original behavior from the pre-change version. Commit/range: base; staged: HEAD; unstaged: INDEX. Mixed staged/unstaged units need both predecessors, or separate units if their behavior differs.
- Use the predominant conversation language unless requested otherwise. Write precise, direct prose with concrete subjects, actions, conditions, and results. Avoid unnecessary terms and invented concepts. Preserve code, identifiers, paths, commands, and source quotations.
- Every human-facing reference needs a readable location and meaning. IDs alone do not explain evidence.

## Default workflow

Use the bundled commands; do not build a custom report generator or hand-author hashes, exact diff spans, final IDs, ledgers, Markdown, or HTML.

```sh
python3 scripts/mandiff.py prepare --repo <repo> --unstaged
# Read the frozen diff, inventory.json, and authoring-help.json.
# Establish context, then edit analysis-draft.json.
python3 scripts/mandiff.py finalize <review-directory>
```

Other selectors: `--staged`, `--uncommitted`, `--commit REV`, `--range BASE..HEAD`, or `--patch FILE`. A merge needs `--parent N`. Ask only when the intended selector is genuinely unclear. A submodule pointer is not authorization to review its nested diff.

Choose a writable output directory outside the reviewed repository using `--output` when useful. If the default Documents destination is denied, the script falls back to an OS temporary directory and prints its location. Avoid repeated permission requests merely to write generated artifacts; respect an explicitly requested destination.

Read [compiler-workflow.md](references/compiler-workflow.md) only for selector, redaction, or authoring details not covered here. `prepare` supplies valid enum values and reference rules in `authoring-help.json`; read it before guessing field names or opening implementation files.

## Decide what the reader needs to understand

Start with the review question. Explain the relevant system boundary, the changed component's responsibility, its input/state and consumers, and an original trigger-to-result example. Give enough surrounding context to place the code, without tracing unrelated subsystems.

Choose a complementary set of representations using [presentation.md](references/presentation.md). Decide what each shows and how far it follows the code:

- System organization and shared dependencies: a focused relationship diagram showing the affected component in its surroundings.
- Repeated fields, responsibilities, producers/consumers: a table showing the details needed to judge impact.
- Original behavior: a representative trigger-to-result scenario; include another when a branch materially changes the outcome.
- Order, initialization, callbacks, or state changes: a sequence, flow, or state view showing relevant conditions and transitions.
- Nested execution, return, or asynchronous boundaries: a source-backed call walkthrough and stack at the steps that explain the behavior.

Choose the number of views, nodes, relationships, scenarios, and steps to preserve understanding. A relationship graph and a parameter table can complement each other; do not treat either as a replacement for the other. Keep the overview and representative behavior visible; collapse secondary detail and source excerpts. Use prose alone only when the reader can already locate the behavior and follow its consequences without reconstructing omitted relationships. A small diff is not by itself a reason to omit context.

Use `baseline.views` for tables or interaction steps and `baseline.guide` for diagrams and scenario/stack navigation; see [context-guide.md](references/context-guide.md). They may be used together. `guide.views` selects which diagrams are drawn from shared evidence; there is no need to draw all graph types. Source-derived stacks are illustrations, not captured runtime traces. Stop at a named, evidenced boundary rather than inventing a complete call chain.

## Keep generation bounded

Use uncertainty and consequence, not just line count, to decide depth. A one-line authorization or concurrency change may need broad evidence; a large mechanical edit may not.

Save time first by reusing verified source and relationships, acquiring ranges automatically, and avoiding duplicate authoring and validation retries. Then reduce unrelated breadth or repetitive detail. Do not remove an explanatory form that materially helps the reader merely because it takes effort to author. Choose representative cases that cover different outcomes; do not enumerate equivalent paths or trace every getter separately.

- Start with the changed function, its direct caller/consumer, and state owner. Read other code only to resolve a specific open question.
- Reuse context already established in this task after checking revision and scope. Use one context source for multiple relevant references.
- Prefer `revision/path/start/lines` for Git context: the script acquires the excerpt. Do not spend model output reproducing source already on disk.
- Read independent files together. Write one semantic draft and do one precision pass; repair reported errors locally rather than restarting discovery.
- Do not compile the project, run application tests, browse the web, or perform browser QA solely to generate a review. Record relevant existing verification; run additional checks only when needed for the decision or requested.
- Do not open the large generic graph example for a simple change. Use the small example below first.
- If analysis expands unexpectedly, tell the user which concrete question needs more evidence. Deliver a valid review with explicit unknowns when necessary; never invent completeness to meet a time target.

`performance.json` records prepare time, time before the first finalize attempt, attempt count, and script stages. The gap includes reading, writing, approval, and idle time; it is not model-only timing. Use these measurements when diagnosing slowness. Do not claim script timing is total review latency.

## Author semantic content

Keep the draft `schema_version: "2.0"`; the compiler produces report schema 1.6. Main units still need an evidence-backed baseline, a claim, an actionable check, and a conclusion. A single truthful original step and change explanation are enough when the behavior is simple. Empty ancillary collections are allowed; include real risks and unknowns rather than filler.

`baseline` contains `architecture`, `responsibilities`, `flow_steps`, `data_and_state`, and `context_refs`. The schema permits optional `views` and `guide` because needs vary; this is not a default instruction to omit them. Use both when they explain different aspects. The compiler accepts older completed drafts and renders old reports.

Use semantic keys; `finalize` assigns IDs. Claims/checks use local claim keys; findings use a unit key and local or owning-unit-qualified failure keys. Cross-unit claims use `unit-key.claim-key`. Changed evidence uses inventory IDs. Observed claims and conclusions inherit the owning unit's changed evidence unless narrowed explicitly.

Use [tests/fixtures/concise-draft.json](tests/fixtures/concise-draft.json) for a small complete draft. Use [review-data-model.md](references/review-data-model.md) only for a field not covered by the example or help file. Main units describe behavior; supporting units cover genuinely mechanical tests/docs/fixtures. Do not relabel a risky change as supporting to bypass requirements.

A frozen context source can be declared as:
```json
{"key":"reader","kind":"caller","snapshot":"base","revision":"<pre-change SHA>","path":"src/reader.ext","start":20,"lines":30,"locator":"read_value","summary":"Calls the changed reader and uses its result."}
```
A standalone patch needs supplied original excerpts with explicit provenance. Context records remain separate from changed-evidence coverage.

For secret redaction, supply a private JSON file `{"values":["sensitive literal"]}` through `prepare --redactions FILE`. Never put the secret on the command line. Read [evidence-protocol.md](references/evidence-protocol.md) for special evidence cases; `finalize` handles redaction and deletes its private temporary material after success. On abandonment use `mandiff.py cleanup <review-directory>`.

## Finish

Before finalize, remove duplicate descriptions, unsupported intent, generic risks, vague checks, and prose in the wrong language. Check selected relationships against cited code; schema validation cannot prove an explanation true.

Completion means an unfamiliar reader can locate the changed part, follow a representative original operation, understand the important state and conditions, and trace each explanation to source. Check that useful relationships have not been compressed into unexplained prose. Preserve exact evidence coverage, explicit risks/unknowns, verification status, and a recommendation. Diagram counts vary with these needs. A missing prerequisite can justify `expand_scope` rather than a speculative conclusion.

Deliver the HTML/Markdown link with what changed and what remains unverified. Read [agent-portability.md](references/agent-portability.md) only for host-specific delivery or text-only fallback. Python 3.9+ and Git are sufficient; the runtime uses the standard library.
