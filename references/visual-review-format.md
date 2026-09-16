# Visual Review Format

Use the visual layer to make review order, dependency, impact, and risk immediately scannable. Keep every mark tied to frozen evidence.

## Required views

### Review outcome

Lead with a short, decision-grade outcome: confirmed changes, actionable defects, important unproven behavior, and the recommended disposition. This replaces decorative summary metrics. Do not make the reviewer infer the result by reading every unit first.

### Scope bar

Keep the immutable selector, repository identity, frozen digest, drift state, and explicit exclusions accessible without letting metadata dominate the first screen. Use a compact disclosure or secondary bar.

### Review flow

Show all review units in dependency order. Each unit must expose:

- step number and semantic title;
- main or supporting lane;
- critical, normal, or context importance;
- evidence IDs and changed-line weight;
- dependency edges;
- defect, risk, design-question, or missing-context markers when present.

Do not infer dependency edges from file order alone. Use only relationships established by code, configuration, or the review explanation.

### Change surface

Show how files or components map to review units. A compact matrix, grouped strip, or bipartite view is preferable to a file tree when one file participates in several behaviors.

Encode additions and deletions as signed values or paired bars. Never let line count imply semantic importance: display importance separately.

### Verification state

Show which behavior is statically verified, tested, not run, missing, or outside scope. Keep human approval distinct from evidence validation.

### Findings queue

Show defects, risks, design questions, and missing context as a selectable queue. Selecting a finding must navigate to the owning review unit and evidence. Never flatten these categories into one severity score.

## Interactive explorer

When the host supports an inline interactive view, make review units selectable. The selected unit must show, in this order:

1. a visible pre-change baseline: architecture position, component responsibilities, original control/data flow, data/state ownership, and frozen context excerpts;
2. the review question;
3. the behavior contract and symmetrical before/after behavior;
4. entry point, direct call path, required context, and dependencies;
5. mechanism steps, invariants, consumers, and compatibility;
6. claims labeled as observed, contextual, reported, inferred, or unknown, with evidence references and confidence;
7. affected files, symbols, and evidence anchors;
8. complete exact original diff;
9. concrete failure modes and focused setup/action/expected checks;
10. findings, unresolved questions, evidence-validation state, and human-decision state.

Do not collapse the pre-change baseline by default. A reviewer must be able to understand the original path without opening the diff. Show the exact frozen context excerpts under the explanation so the reviewer can verify that the prose matches the original code.

Every visible reference must decode the stable ID inline: show the source path and line when available, followed by a one-line statement of what that reference establishes. A bare identifier is never sufficient UI copy. In interactive output, selecting changed evidence must open its owning review unit, show the complete exact diff, and locate the referenced hunk.

Support the complete reviewer loop:

- filter or search units only when the number of units makes direct selection impractical;
- search inside the selected diff without mutating its source text;
- classify each focused check as unverified, passed, failed, or unrelated to this change using a visible single-choice radio group; store the last state as `not_applicable` for compatibility, and do not hide these four states in a select menu;
- confirm or dismiss each AI finding so an AI hypothesis cannot silently become a human conclusion; require a reviewer rationale for dismissal;
- record a unit decision as pending, accepted, changes requested, or needing more evidence;
- show immediate visible feedback after a check or decision changes;
- attach reviewer notes to a unit;
- jump to the next unresolved unit;
- preserve local state across reloads when storage is available;
- export and import the separate reviewer-state overlay bound to the frozen diff digest;
- generate a concrete human-review conclusion that combines unit decisions, all four check states, confirmed findings, dismissed findings with rationale, and reviewer notes.

Human checks are executable observations, not acknowledgements that text was read. Findings are AI-proposed defects, risks, design questions, or missing context, not facts until the reviewer confirms them. `Accept` records that the unit is reviewable and acceptable under the completed checks; `Need evidence` keeps it unresolved; `Request changes` makes it an actionable blocker. `Next unresolved` navigates to any unit with an unresolved decision, check, finding, or unsupported dismissal. The durable payoff is the exported state and generated conclusion, both bound to the frozen diff digest.

Always show the complete exact hunk. Searching may highlight matching text but must not filter, condense, reorder, or hide diff lines.

Default to the first critical unit, otherwise the first main-path unit. Preserve the planned review order while allowing direct selection.

Use color only as a redundant cue:

- additions and deletions need `+` and `-` signs or labels;
- importance needs text labels;
- findings need category labels or icons;
- verification needs explicit status text.

In the review path, keep the grading copy stable and color the grade label, verification text, and human-decision text themselves according to state. Do not replace those words with colored dots or recolor the entire review-unit button.

Support keyboard selection and narrow layouts. Keep diff text readable without overlay, clipping, or forced horizontal page scrolling.

## Static fallback

When interactive output is unavailable, include:

1. a dependency flow diagram;
2. a file-to-unit matrix;
3. a risk and verification table.

Mermaid is suitable only when nodes and edges communicate the relationship clearly. Prefer tables for exact mappings and statuses.

## Anti-patterns

Do not:

- lead with commit hashes, capture metadata, or prose before showing change shape;
- render a dashboard of decorative counts with no review action;
- turn each file into a unit when behavior crosses files;
- hide exact hunks behind summaries;
- use a single giant diagram that mixes dependency, files, risks, and tests;
- show evidence validation as human approval;
- collapse unreviewed or out-of-scope behavior into a green success state.
- require authentication, a backend, network access, or a particular agent host for basic review.
