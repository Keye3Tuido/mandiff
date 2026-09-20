# Review Data Model

Use one canonical model for Markdown, HTML, and reviewer-state export. Field names are stable; human-facing labels may be localized.

When JSON Schema tooling is available, validate the immutable report against `../assets/review-model.schema.json`.

During normal authoring, use the compact `analysis-draft.json` schema 2.0 created by `mandiff.py prepare`. Semantic keys replace final IDs, and optional fields may be omitted. `mandiff.py finalize` freezes declared context, assigns IDs, derives completeness and outcome aggregation, and writes expanded `analysis.json` schema 1.0 before invoking the canonical compiler. Do not hand-author the source manifest or canonical report. The low-level manifest plus schema 1.0 analysis path remains available only for compatibility and diagnostics.

## Evidence classes

Keep provenance explicit. A source supports only the kind of conclusion it can establish:

| Class | ID form | Establishes | Does not establish |
|---|---|---|---|
| Changed evidence | `F01-H01`, `F02-SUBMODULE` | Exact selected change | Surrounding runtime behavior by itself |
| Context snapshot | `C01`, `C02` | Unchanged definition, caller, test, or contract at a frozen revision | Intent or behavior outside that snapshot |
| Change description | `M01` | What an author reported | Correctness or runtime behavior |
| Requirement | `RQ01` | Requested outcome | That the implementation satisfies it |

Record context sources at the top level with `id`, `kind`, `snapshot`, `revision`, `path`, `locator`, `summary`, and `fingerprint`; `excerpt` is required when a main-unit baseline cites the source. Every changed-evidence anchor carries its source artifact, typed kind, provenance, paths, ordinal, hunk span or typed-entry metadata, label, summary, and fingerprint. Human-facing renderers must show the ID with its location and meaning; the ID alone exists only for stable cross-reference. Context remains separate from changed-hunk coverage.

## Report

```json
{
  "schema_version": "1.6",
  "report": {
    "id": "stable-report-id",
    "repository": "repository identity",
    "selector": "requested selector",
    "source_artifact_ids": ["S01"],
    "base": "optional aggregate base identity",
    "head": "optional aggregate head identity",
    "diff_digest": "sha256 of the ordered artifact manifest",
    "diff_bytes": 0,
    "mutable": false,
    "drift": "immutable",
    "scope_exclusions": []
  },
  "source_artifacts": [
    {
      "id": "S01",
      "provenance": "commit",
      "selector": "exact source selector",
      "acquisition": "read-only acquisition operation",
      "captured_at": "ISO-8601 timestamp",
      "base": "source base identity",
      "head": "source head identity",
      "diff_base64": "base64 of safe display bytes",
      "diff_digest": "sha256, or keyed HMAC-SHA-256 when redacted",
      "diff_bytes": 0,
      "display_digest": "sha256 of decoded display bytes",
      "display_bytes": 0,
      "redacted": false,
      "mutable": false,
      "drift": "immutable"
    }
  ],
  "summary": {
    "files": 0,
    "hunks": 0,
    "additions": 0,
    "deletions": 0,
    "evidence_total": 0,
    "evidence_validated": 0
  },
  "outcome": {
    "confirmed": [],
    "defects": [],
    "unproven": [],
    "recommendation": {}
  },
  "context_sources": [],
  "requirements": [],
  "files": [],
  "units": [],
  "evidence_ledger": [],
  "findings": [],
  "verification": [],
  "coverage": {}
}
```

`source_artifacts` is the provenance boundary. Never use one digest field to represent staged and unstaged changes together. For ordinary evidence, `diff_base64` carries exact raw bytes and the original/display commitments are equal. For secret redaction, it carries only safe display bytes; the original digest and anchor fingerprint are HMAC-SHA-256 commitments made with an ephemeral key that is never embedded. Derive the report digest from the original commitments exactly as specified in `evidence-protocol.md`; `scripts/validate_review.py` enforces the portable display layer and commitment consistency.

## Review unit

Every unit keeps the same stable field names. In 1.6, a main critical/normal unit requires original context, a claim, a check, a conclusion, and at least one mechanism step. Include entry/call paths, invariants, consumers, compatibility, failure modes and unknowns when they affect the decision; empty collections are allowed without inventing filler. Supporting/context units can also omit irrelevant claims and checks. Evidence coverage and snapshot validation are never optional.

- Identity: `id`, `order`, `title`, `lane`, and `importance`.
- Decision frame: one `question` and one falsifiable `contract`.
- Decision output: one `conclusion` with status, statement, and evidence references.
- State delta: symmetrical `before` and `after` statements.
- Pre-change baseline: `architecture`, `responsibilities`, ordered `flow_steps`, `data_and_state`, `context_refs`. Main units require frozen excerpts from the original side. `views` supplies tables or interactions; `guide` supplies diagrams and scenario/stack navigation. Their schema optionality accommodates differing needs, not a default to omit them. Combine complementary forms and control their scope using [presentation.md](presentation.md). Optional `guide.views` selects graph types from `structure`, `calls`, `flow`; `guide.expanded` defaults to true, with false reserved for supplementary detail. `context_sources.start_line` optionally preserves the excerpt's one-based original line.
- Execution: include `entry_points` and `call_path` when useful; `mechanism_steps` needs at least one truthful explanation, with no arbitrary three-step minimum in 1.6.
- Constraints: `invariants`, `consumers`, and `compatibility`.
- Evidence: author `depends_on`, `symbols`, and the declarative evidence `id`/`label`/`summary`; let the compiler derive `files`, `evidence_ids`, exact `diff`, ordered `diff_segments`, and stable `anchors`. Segments locate bytes but do not define completeness: the compiler derives the canonical display independently as each source file's exact metadata followed by the unit's complete owned hunks, then requires both the segments and `diff` to reproduce it.
- Reasoning: atomic `claims`, concrete `failure_modes`, and explicit `unknowns`.
- Verification: structured `checks`, linked `finding_ids`, and linked `verification_ids`.

Reviewer decisions are not unit fields. Changed-evidence lifecycle state belongs only in the report-level ledger; mutable human decisions belong only in the reviewer-state overlay.

### Claims

Each claim contains:

- stable `id`;
- one falsifiable `statement`;
- `kind`: `observed`, `contextual`, `reported`, `inferred`, or `unknown`;
- `evidence_refs`: changed evidence, context, description, or requirement IDs;
- `confidence`: `high`, `medium`, or `low`.

An `observed` claim cites changed evidence. A `contextual` claim cites frozen context. A `reported` claim cites only author or requirement text. An `inferred` claim cites the facts used to derive it. An `unknown` claim explains the missing evidence and may have no reference.

Keep claims atomic. If one sentence contains two independently falsifiable clauses, split it.

### Checks

Each check contains `id`, a short `label`, `setup`, `action`, `expected`, and `claim_ids`. The expected result must be observable and specific enough for a reviewer to mark pass or fail. Checks such as "verify correctness" are invalid.

### Failure modes

Each failure mode contains `id`, `trigger`, `effect`, `detection_or_mitigation`, `evidence_refs`, and a `claim_ids` array, which may be empty when no claim establishes it. If a unit has no plausible failure mode within scope, store a single explicit `not_applicable` item with the reason rather than inventing generic risk.

### Completeness

Store a `completeness` object on every unit. For each required information category, use `complete`, `unknown`, or `not_applicable`. This is an audit of information availability, not a quality score.

## Finding

Use `defect`, `risk`, `design_question`, or `missing_context`. Include `unit_id`, related evidence IDs, an evidence-backed description, and at least one `claim_id` or `failure_mode_id`. Severity never replaces category.

## Review outcome

The report-level `outcome` is the human-facing product of the analysis, not another summary of changed files.

- `confirmed`: concrete conclusions established by selected evidence.
- `defects`: actionable defects linked to finding IDs.
- `unproven`: requested or implied behaviors that cannot be established from the selected scope.
- `recommendation`: `accept`, `request_changes`, or `expand_scope`, plus one concise reason.

Each item contains a statement and relevant unit, finding, claim, or evidence references. Keep these lists short and decision-relevant.

## Verification

Use `verified`, `static_only`, `not_run`, `missing`, `failed`, or `out_of_scope`. Include the claimed behavior, existing evidence, structured setup/action/expected fields, linked claim IDs, and owning units.

## Reviewer-state overlay

Keep mutable state in a separate `review-state.json`-style artifact. It is never embedded back into `review.json`:

```json
{
  "schema_version": "1.1",
  "report_id": "stable-report-id",
  "diff_digest": "sha256 hex",
  "saved_at": "ISO-8601 timestamp",
  "units": {
    "U01": {
      "decision": "pending",
      "check_results": {
        "C1": "unverified"
      },
      "finding_reviews": {
        "R01": {
          "decision": "pending",
          "rationale": ""
        }
      },
      "note": ""
    }
  }
}
```

Validate newly exported overlays against `../assets/review-state.schema.json`. The portable explorer may import legacy schema `1.0` state and upgrades it in memory, but every new export uses `1.1`.

Use `pending`, `accepted`, `changes_requested`, or `needs_evidence` for unit decisions. Use `unverified`, `passed`, `failed`, or `not_applicable` for check results. Use `pending`, `confirmed`, or `dismissed` for finding decisions. A dismissed finding requires a non-empty human rationale before the conclusion can be complete. These states produce a reusable human-review conclusion; they do not mutate immutable report evidence.

Reject unknown unit, check, or finding IDs during import. Warn and require explicit human confirmation before applying state with a mismatched digest; the safe default is rejection.

## Referential validation

Before rendering, validate both JSON shape and these cross-record rules. `scripts/validate_review.py` is the normative executable validator when Python is available:

1. Every claim reference resolves to changed evidence, context, description, or requirement.
2. Every check references existing claims in the same unit.
3. Every finding references an existing claim or failure mode.
4. Every verification record references existing claims and units.
5. Every changed evidence ID belongs to exactly one diff-bearing unit.
6. Context IDs never appear as changed-hunk owners or inflate diff coverage.
7. Source IDs and report digest bind the ordered artifact manifest; report bytes, mutability, and drift agree with its artifacts.
8. Every ledger item records the evidence kind, source, and original fingerprint. `discovered` items may retain null ownership until assigned; every later state has one matching anchor and unit with matching source, kind, fingerprint, lane, and importance. Every anchor display fingerprint must equal the SHA-256 of its byte span in the decoded display artifact; the original fingerprint must also match unless ledger state is `redacted`.
9. Summary and coverage counters are derived from files, anchors, ownership, and ledger state.
10. Outcome references resolve to units, findings, claims, changed/context/reported evidence, or verification records.
11. Every schema 1.4/1.5/1.6 main critical/normal unit has a complete baseline; its context references resolve only to frozen excerpts from a valid pre-change snapshot, and each excerpt matches its fingerprint. Version 1.6 allows one original step and does not require a guide.
12. Schema 1.5 main critical/normal units also have `baseline.guide`. Diagram IDs are unique within a unit; edges and steps resolve; every cited context belongs to that baseline. Execution steps are reachable from entry and covered by complete scenarios. Each illustrated stack ends at the current function and adjacent frames have synchronous call evidence. Asynchronous transitions begin at the new task's entry with a one-frame stack; synchronous transitions cannot silently replace the stack root. Unknown execution requires an unproven conclusion and `expand_scope`; unavailable execution must not include a fabricated walkthrough.

13. Optional `baseline.views` rows cite the owning baseline's context. Their kind is table, sequence, state, or relationships; columns map to from/label/to, never changed-hunk evidence. The expander resolves shared context refs to individual rows before validation.

Older schema 1.3/1.4/1.5 reports remain readable with their original constraints. Do not invent original diagrams or stacks from after-change prose. New compilations emit 1.6, where prose without a diagram is a valid deliberate choice. Optional supplied graphs retain all their structural checks.

The renderer must refuse invalid reports before creating output. A visually complete page is not evidence that its model is coherent.
