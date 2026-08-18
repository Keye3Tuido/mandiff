# Agent Portability

ManDiff is a review protocol, not a dependency on one agent product. No single installation format is automatically discovered by every agent, so keep the core protocol portable and treat product integration as a thin adapter.

## Portable core

Require only capabilities that can be replaced:

- read repository or patch content;
- run read-only Git commands when Git is available;
- compute SHA-256 by any standard implementation;
- write Markdown, JSON, and optionally self-contained HTML outside the reviewed repository.

Never make correctness depend on:

- a named agent, model, provider, IDE, or chat client;
- a proprietary tool-call syntax or global JavaScript object;
- remote services, package installation, or network access;
- a specific filesystem layout for skills.

## Delivery levels

Choose the highest level the current agent can support:

1. **Portable bundle**: immutable `review.json`, optional mutable `review-state.json`, `review.md`, and self-contained `review.html`.
2. **Interactive chat**: host-native HTML or UI backed by the same review model, plus portable Markdown when possible.
3. **Text-only**: Mermaid dependency flow, exact diff blocks, mapping tables, findings, verification, and coverage.

The level may change presentation, never evidence coverage or conclusions.

## Adapter boundary

Allow an adapter to choose commands, temporary paths, UI directives, or artifact attachment mechanics. Keep these details out of the report model and core reasoning instructions.

If a host-specific enhancement is used, make it optional and preserve a vendor-neutral fallback. Do not place host callbacks in portable HTML.

## Reviewer state

Store reviewer decisions separately from immutable report evidence. Bind imported state to `report.diff_digest`; reject or warn on a mismatch. Use only:

- `pending`, `accepted`, `changes_requested`, or `needs_evidence` per unit;
- `unverified`, `passed`, `failed`, or `not_applicable` per check ID;
- `pending`, `confirmed`, or `dismissed` per finding ID;
- reviewer notes;
- a reviewer rationale for every dismissed finding;
- optional reviewer identity and timestamp supplied by the human.

Never encode evidence validation as reviewer acceptance.

The generated human conclusion must preserve all four check results: passed, failed, unrelated to this change, and unverified. It must also preserve confirmed findings and dismissed findings with their rationale. Otherwise exported state has no useful audit trail.
