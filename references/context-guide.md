# Explain the original system with diagrams and a walkthrough

This is the authoring contract for `baseline.guide` in report schema 1.5. Read it before writing a main review unit. The compiler renders the same structured model in HTML and Markdown; do not author SVG, Mermaid, or a separate diagram description.

## Reader journey

1. Explain where the changed behavior lives. Map components, functions, data, and external boundaries to their responsibilities and original source locations.
2. Show architecture and dependencies, then calls. Every arrow has a direction, a concrete meaning, and evidence. Containment, dependency, reading/writing, a synchronous call, and scheduling work are different relations.
3. Start with a concrete trigger and input. Draw the original flow including relevant branches, loops, failure exits, and asynchronous continuations.
4. Walk through at least one complete scenario from entry to result. At each step explain the current function, its action/result, and the active stack from outermost caller to current function. Every drawn flow step must appear in a scenario; add scenarios for other branches. State concrete inputs and starting state. A repeated function call and a return should visibly push and remove frames; do not retain a returned function.
5. Connect the now-understood original behavior to the change, then show the exact diff.

Keep a diagram focused on the behavior being reviewed. Split a large unit by behavior or explain shared architecture in an earlier dependency unit. Do not replace a useful diagram with a directory tree or make one giant graph of unrelated modules.

## Data contract

`guide.nodes` contains `{id, label, kind, responsibility, context_refs}`. IDs are unit-local semantic keys, never visible titles. `kind` is `component`, `function`, `data`, or `external`. Labels name real components or symbols; responsibilities explain what they do. Context refs resolve to the owning baseline's frozen sources, including a path and source locator.

`guide.relations` contains `{from, to, kind, label, context_refs}`. Kinds are `contains`, `depends_on`, `calls`, `dispatches`, `reads`, and `writes`. The label describes the actual relationship in the report language. A `calls` arrow is caller to callee; `dispatches` schedules later work and must not imply a shared synchronous stack. Keep recursive and cyclic dependencies when the code establishes them.

`guide.execution` always has a `status` and `reason`. Use `available` for an explained execution, `not_applicable` with a concrete reason for purely declarative/non-executable changes, or `unknown` with the missing evidence. Do not invent calls to fill a template. An unknown execution keeps the unit `unproven` and the report recommendation `expand_scope`.

When available, also provide:

- `entry`: the first flow step's ID.
- `steps`: `{id, node, action, context_refs}`. `node` names the function executing the step; use a separate step when that function occurs again later. Describe the operation and state/result, not just a function name.
- `transitions`: `{from, to, kind, label, context_refs}` between step IDs. Kinds are `next`, `branch`, `loop`, and `async`. Label conditions explicitly; a loop points to an earlier step. After an asynchronous transition, show the new task's entry as a one-frame stack, then show any calls it makes in subsequent steps. The same function can be entered again in a new task; that does not preserve the earlier invocation.
- `scenarios`: `{title, summary, walkthrough}`. Each walkthrough entry is `{step, stack, explanation, context_refs}`. `stack` lists node IDs from outermost active caller to current function, and its last frame must be the step's node. Consecutive entries follow declared flow transitions; end at a terminal step. Explain selected branch results in the entry's prose.

All walkthroughs are **source-derived illustrations**, never captured runtime stacks. The report labels that limit explicitly. Actual stack traces or tests belong in verification with their real provenance. Do not append a callback to a stack whose initiating function has already returned.

## Evidence and limits

Every node, relation, flow step, transition, and walkthrough entry cites context refs. The pipeline verifies IDs, directed edges, graph reachability, scenario continuity, stack/call consistency, and excerpt hashes. It cannot prove that an AI interpretation follows from code: the semantic pass must check every arrow and described effect against its cited lines.

Use the pre-change revision for each selected source. Shared IDs do not allow mixing incompatible `HEAD` and index states in one narrative. Include only code needed to explain the behavior, preserving complete relevant function bodies and conditions. Never label modified code as the original system. Keep unresolved links visible as missing context instead of drawing guessed arrows.

## Presentation and compatibility

HTML shows separate architecture/dependency, call, and flow diagrams as native SVG with readable relationship lists. Selecting a node, arrow, or walkthrough step opens its source and meaning. Scenario navigation highlights the active flow step and stack. It works offline, by mouse and keyboard, and in a narrow viewport with scrolling inside diagrams only.

Markdown emits Mermaid from the same records and includes source-linked node/relationship tables and the full scenario/stack walkthrough, so hosts without Mermaid can still read it. Missing/irrelevant execution displays its stated reason. Older 1.3/1.4 reports remain renderable and explicitly say the diagram guide is unavailable; never infer diagrams or original stacks from old after-change mechanism prose.
