# Select the explanation, then its form

The reader needs to locate the changed behavior in the system, understand the original rule and its consequences, and verify the relevant source. Diagrams, tables, scenarios, and stacks are complementary tools for that understanding. Choose their number, content, and level of detail; do not optimize by eliminating these forms or minimizing word count. The report need not document unrelated parts of the architecture.

## Reading order

1. Orient: state the system boundary, purpose, affected component, inputs, state owner, and immediate consumers. Keep this at one consistent abstraction level.
2. Explain before and after: follow the same representative trigger, input and starting state to its result in each version. Use comparable diagrams, tables and stack walkthroughs to explain relevant responsibilities, state and calls on both sides. Connect technical names to what they do.
3. Compare: identify where the two paths diverge, why the outcome changes or stays the same, and which assumptions remain unverified. New prerequisites get a separate, clearly conditional scenario.
4. Inspect: open each side's frozen source, then compare the complete diff. Keep the selected overview and core walkthrough visible. Collapse supplementary detail, not the entire explanation.

Multiple views are useful when they resolve different questions. A source file tree seldom explains runtime responsibilities by itself. A call graph does not prove temporal order; a sequence does not prove a shared synchronous stack. Do not make the reader mentally rebuild an omitted graph from a dense list of names.

| Reader's question | Useful form | Avoid |
|---|---|---|
| Where does this local rule fit? | Boundary paragraph, original input/result example, source | Full-system graph for a local check |
| Who owns, produces, or consumes several fields? | Responsibility or producer/consumer table | Repeating each field as a node and scenario |
| What happens before/after a call or callback? | Numbered interactions; add a sequence view if useful | Implying callbacks share a stack |
| Which event changes an object's state? | Before-state / condition / after-state table | Linearizing mutually exclusive transitions |
| What depends on what across boundaries? | Focused relationship graph; table for field-level detail | Making a table replace a needed overview, or mixing abstraction levels |
| Why does nested execution or re-entry matter? | Evidenced scenario and stack at meaningful steps | A separate trace for every equivalent getter |

## Balance scope and detail

For each main behavior, decide what an unfamiliar reader must understand about organization, data/state, and execution. Select views and scenarios to cover those needs. Briefly explain each view's purpose in its caption or scenario summary; no separate planning document is needed.

Start the graph at the affected component and the boundaries that matter. Group equivalent consumers only if grouping preserves their relevant roles and differences. Extend the diagram when ownership, initialization order, or another dependency remains unclear. Include the normal scenario plus failure/alternate cases whose outcomes matter to the review; skip equivalent repetitions. Show the stack where entering, returning, re-entering, or dispatching changes understanding. The goal is enough context for the decision, not a fixed node or scenario quota.

For a shared configuration change, an appropriate set might be a relationship overview (who holds and uses values), a table (which fields serve which uses), and a short initialization walkthrough with a normal and missing-configuration case. The stack makes the synchronous load and return explicit. A separate call graph may duplicate that walkthrough, so it need not be drawn. This is an example, not a compulsory bundle for unrelated changes.

Save authoring time by sharing source records and relationships across these views, generating presentation mechanically, and catching draft errors together. Reduce unrelated scope and repetitive explanations before removing a representation that aids comprehension. A shorter payload alone does not demonstrate a better report or a faster complete review.

Before finishing, verify that the reader can identify the affected boundary, follow a concrete input to its result in both versions, explain the difference, understand important conditions/state and execution boundaries, and open the evidence. If any of these requires guessing omitted relationships, add the appropriate view or detail. Prose alone remains suitable for a truly self-contained rule, not the default for small diffs.

## Matched before/after explanations (schema 1.7)

Every main critical/normal unit supplies `baseline` and `post_change`, each with architecture, responsibilities, flow_steps, data_and_state, context_refs, and the appropriate views/guide. Explain the changed system to the same useful depth as the original; `after` and `mechanism_steps` remain summaries, not substitutes for it. Corresponding symbols and scenarios should stay easy to match. Shared code may be reused when authoring after verifying both versions; cite it separately at each version rather than letting old evidence stand in for the result.

Default to the same section order, diagram types and boundaries, table columns and row subjects, and scenario names. Use neutral labels valid on both sides. Changed responsibilities may require more or fewer nodes/steps, and a new prerequisite may need an extra scenario. Explain such differences in captions; do not add meaningless duplicates or remove useful original detail just to match counts. Check each original representation against its after counterpart before finalization.

For data-dependent behavior, show the fields that determine the result: representative input or starting state, its relevant format/type, default or unit when material, and the resulting value or state. A focused three-column `views` table can show input, rule, and output on each side; the `comparison` table then summarizes the difference under the same input. Examples derived from code must be labeled as constructed, not observed. Keep actual payloads, literals and source quotations unchanged. Do not reproduce whole configuration files when only a few fields matter.

Add `comparison` rows with `scenario`, one shared `input`, `before`, `after`, `impact`, `before_context_refs`, and `after_context_refs`. The two reference lists must belong to their respective contexts. The `input` states the common trigger, inputs, starting state and observation point; `before` and `after` explain the resulting paths/outcomes. Include unchanged outcomes when they are an important compatibility question. This comparison is prose derived from source unless separately verified by running the system.

If the change adds an API, configuration requirement or caller, first explain what the old calling conditions do under the changed code. Then add a separate scenario that states the new prerequisite. Never imply a real caller exists merely because a function or comment requires one. Mark missing integration or runtime evidence explicitly.

HTML switches the complete context panel between before and after and keeps the same-input results table visible. Markdown prints both in order. Both reuse the same graph, table and stack renderers; useful detail remains on both sides without creating another rendering pipeline. Older reports explicitly lack the post-change walkthrough rather than fabricating it from a short summary.

## Compact views (schema 1.6)

Use the same context structure on both sides: `baseline.views` / `post_change.views` for tables/steps, and `baseline.guide` / `post_change.guide` for diagrams and scenario/stack navigation. These can be combined. A compact table entry is:

```json
{
  "kind": "table",
  "title": "原配置由谁读取",
  "reason": "本次修改的是配置来源，按读取方列出用途更容易判断影响。",
  "columns": ["配置来源", "读取用途", "读取方"],
  "context_refs": ["original-reader"],
  "rows": [
    {"from": "levelsDir", "label": "选择关卡文件目录", "to": "parseLevelConfigData()"}
  ]
}
```

Rows have `from`, `label`, `to`, and `context_refs`. Explicit row refs override shared view refs; the compiler expands shared refs once. Use shared refs only when the same excerpt really supports every row. References must belong to the frozen sources of the matching side. `columns`, when present, names exactly those first three values, in that order.

Kinds: `table` for comparisons/responsibilities, `sequence` for ordered interactions, `state` for state/event/result mappings, and `relationships` for dependencies. Sequence rows become numbered interactions in both formats; the other kinds become readable tables. A relationships table is not a drawn graph. For diagrams and a source-backed scenario/stack, use `baseline.guide` described in [context-guide.md](context-guide.md). Set `guide.views`, for example `["structure", "flow"]`, to draw the selected graph types from shared records. Do not mechanically redraw every table, or use a table to avoid drawing a useful graph.

State rows are transitions, not a single execution. Sequence rows are chronological within the stated scenario; mark conditions and asynchronous boundaries in `label`. Stop at the evidenced boundary and state what is unknown. Do not add unproved interactions to make a story look complete.

## Basis for these choices

The following sources support choosing views by the reader's concerns and progressively revealing detail. They do not establish that any one representation is universally best, or prove a generation-time improvement for ManDiff.

- [C4 model: diagrams](https://c4model.com/diagrams) describes levels of abstraction and recommends using only levels that add value. [Dynamic diagrams](https://c4model.com/diagrams/dynamic) are for selected interactions, not mandatory for every feature.
- [Kruchten, Architectural Blueprints: The 4+1 View Model (1995)](https://arxiv.org/abs/2006.04975) separates architectural concerns across concurrent views and uses scenarios to connect them. Applying all five views to every diff would exceed this review task.
- [Clements et al., Documenting Software Architectures: Views and Beyond, second edition (2010)](https://www.sei.cmu.edu/library/documenting-software-architectures-views-and-beyond-second-edition/) explains how to choose architectural information and organize it into views before choosing notation. A review should select the views needed for its readers and decisions.
- [arc42: runtime view](https://docs.arc42.org/section-6/) permits natural-language steps, activity/sequence diagrams and state machines, and favors representative, architecturally relevant scenarios over exhaustive enumeration.
- [Shneiderman, The Eyes Have It (1996)](https://www.cs.umd.edu/~ben/papers/Shneiderman1996eyes.pdf) motivates overview, focused exploration and details on demand. The concrete ManDiff reading order and defaults above are our design choices based on that principle.

Consulted 2026-09-20. Routine report generation should use this guidance; it does not require repeating this literature search.
