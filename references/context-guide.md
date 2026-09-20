# Explain the original system with diagrams and a walkthrough

This is the `baseline.guide` contract for diagrams and scenario/stack navigation. Use [presentation.md](presentation.md) to decide which relationships, scenarios, and details the reader needs. Combine the guide with parameter or responsibility tables where they complement it. Schema 1.6 permits omission for self-contained explanations; this is not a default instruction to omit graphs for speed. The compiler renders HTML and Markdown; do not author SVG or Mermaid yourself.

## Reader journey

1. Explain where the changed behavior lives. Map components, functions, data, and external boundaries to their responsibilities and original source locations.
2. Select diagrams for architecture/dependencies, calls, or flow. Every arrow has a direction, a concrete meaning, and evidence. Containment, dependency, reading/writing, a synchronous call, and scheduling work are different relations. A stack walkthrough may already explain a simple call chain without another call diagram.
3. Start with a concrete trigger and input. Explain the original flow including branches, loops, failure exits, and asynchronous continuations that affect the review. Draw them when a flow diagram adds understanding.
4. Walk through at least one complete scenario from entry to result. At each step explain the current function, its action/result, and the active stack from outermost caller to current function. Every drawn flow step must appear in a scenario; add scenarios for other branches. State concrete inputs and starting state. A repeated function call and a return should visibly push and remove frames; do not retain a returned function.
5. Connect the now-understood original behavior to the change, then show the exact diff.

Keep a diagram focused on the behavior being reviewed. Split a large unit by behavior or explain shared architecture in an earlier dependency unit. Do not replace a useful diagram with a directory tree or make one giant graph of unrelated modules.

## Data contract

`guide.views` optionally selects and orders diagrams: `structure`, `calls`, `flow`; for example `["structure", "flow"]` draws an overview and a flow without a redundant call graph. Omitting it preserves the three-view renderer used by existing reports. The selected scenario and its stack remain available even when its flow diagram is not selected. All supplied nodes, relations, and execution records are validated, including records not drawn in a selected view.

The guide is expanded by default so its core explanation is visible. Use `guide.expanded: false` only for supplementary detail when another visible view already establishes the needed context. This controls initial HTML display; it does not remove content from either format.

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

HTML draws only the selected graph types as native SVG with relationship lists, filtering each graph to its participating nodes. It displays the core guide before detailed tables. Supplementary guides explicitly marked `expanded: false` render when opened. Selecting a node, arrow, or walkthrough step opens its source and meaning. Scenario navigation updates the step and stack; it switches to a flow diagram only if that view was selected. The guide is offline and keyboard-operable, with internal diagram scrolling.

Markdown emits Mermaid from the same records and includes source-linked node/relationship tables and the full scenario/stack walkthrough, so hosts without Mermaid can still read it. Missing/irrelevant execution displays its stated reason. Older 1.3/1.4 reports remain renderable and explicitly say the diagram guide is unavailable; never infer diagrams or original stacks from old after-change mechanism prose.
