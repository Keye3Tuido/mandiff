# Evidence Protocol

Use this protocol to keep a narrative review bound to the exact change it explains.

## Snapshot manifest

Record these fields for each independently acquired source artifact before analysis:

| Field | Meaning |
|---|---|
| Selector | The exact user-selected working tree, commit, range, PR, or patch |
| Repository | Canonical repository root or provider identity |
| Base / head | Immutable object IDs when Git objects exist |
| Provenance | Staged, unstaged, commit parent, range semantics, provider patch, or patch artifact |
| Acquisition | Exact read-only command or provider operation |
| Captured at | Timestamp for mutable targets |
| Display diff bytes | Base64-encoded source bytes; redacted before encoding when required |
| Diff digest / bytes | SHA-256 for ordinary evidence; private keyed HMAC commitment for redacted evidence |
| Display digest / bytes | Recomputable commitment to the portable display artifact |
| Redacted | Whether display bytes differ from the private raw artifact |
| Mutable | Whether the selector can change during authoring |

Store raw diff artifacts only in a unique temporary location outside the reviewed repository. Do not place review state in the source tree.

Assign source IDs `S01`, `S02`, ... in acquisition order. Keep staged and unstaged changes as separate artifacts even when they touch the same path. The report-level `source_artifact_ids` must reproduce that order and `diff_bytes` must equal the sum of artifact byte counts.

Bind the report to the ordered artifact manifest, not to one arbitrarily chosen diff. Compute the report digest as:

```text
payload = concat(source_id + TAB + source_diff_digest + TAB + decimal_diff_bytes + LF)
report.diff_digest = SHA256(UTF-8(payload))
```

For example, two artifacts produce two newline-terminated manifest records. This aggregate digest detects missing, reordered, or substituted sources while retaining each artifact's own raw-byte digest.

## Stable evidence anchors

Give each file and hunk a readable report-local ID, but do not rely on the ID alone. Retain this anchor data:

- provenance or section kind;
- source artifact ID;
- old path and new path;
- hunk ordinal within that provenance;
- exact hunk header and old/new line spans;
- zero-based byte start and byte length inside the decoded source artifact;
- a concise label naming the changed location and a one-line explanation of what the evidence establishes;
- SHA-256 fingerprint of the original hunk or non-text entry bytes.

Recompute the display digest and byte count from decoded `diff_base64`. Then slice each anchor's byte span and recompute its `display_fingerprint`. For unredacted evidence, the original and display commitments must match. Use that binding to detect tampering, accidental duplication, or rebinding. Line numbers and paths are navigation hints and may drift; a matching-looking location is not proof that the evidence is unchanged.

For a text review unit, derive its displayed diff independently from the source artifact: include the exact `diff --git` and file metadata for each participating file, followed by only that unit's complete owned hunk spans in anchor order. `diff_segments` must locate bytes that concatenate to this canonical display. Do not let agent-authored segments redefine, omit, or reorder required metadata.

The identifier is navigation syntax, not reviewer-facing meaning. Render `F01-H02` as, for example, `F01-H02 · src/parser.ts, parseConfig · adds the fallback branch`, never as a bare code alone. Apply the same rule to context, requirement, claim, finding, and verification IDs.

For rename, copy, binary, mode-only, empty-file, or submodule changes, create a typed non-text entry and fingerprint the relevant raw metadata. Do not invent a text hunk.

## Review lanes

Assign every evidence item to exactly one ordered lane:

- `Main path`: behavior, contracts, state, integration, failure handling, and high-value tests.
- `Supporting path`: direct tests, docs, generated output, fixtures, repetitive wiring, lockfiles, and mechanical effects.

The lane controls reading order and analysis depth, never exact-evidence coverage. Supporting evidence must still receive:

- relevant background and before/after behavior;
- a mechanism explanation proportional to its role;
- its exact diff or typed non-text description;
- focused human review checks only when a check can change the review decision;
- a step conclusion.

Do not research main-path context for a mechanical supporting item. Use explicit `not_applicable` or `unknown` values where the canonical model requires fields. Do not use labels such as "other changes" when a more specific role can be established.

## Coverage state machine

Store every item in the report-level `evidence_ledger` and track it through these states:

1. `discovered`: present in the frozen diff inventory.
2. `assigned`: owned by exactly one review unit and lane.
3. `presented`: its explanation and exact evidence appear in the guide.
4. `validated`: its displayed evidence matches the frozen source and appears once.

Use `redacted` instead of `validated` only when a sensitive value was deliberately replaced under the redaction rule below. Every ledger record includes evidence kind, source artifact, and fingerprint. A `discovered` item may keep null unit, lane, and importance fields; after assignment those fields and its source, kind, and fingerprint must match the owning unit and anchor. Derive coverage counters from this ledger; never hand-author counters independently.

Reject these invalid conditions:

- an unknown ID appears in a unit;
- an item belongs to zero or multiple units;
- two units overlap on any hunk;
- an item is described but its evidence is omitted;
- evidence is displayed without context and counted as complete;
- a generated or repetitive item is silently hidden;
- `presented` is reported as if the human accepted the code.

## Drift handling

Historical Git objects are stable after their base and head object IDs are resolved. Working trees, staged sets, moving branch names, and provider PR heads are mutable.

For a mutable selector, reacquire it immediately before completing the guide and compare its SHA-256 digest with the frozen digest.

- If the digest matches, record `Drift check: unchanged`.
- If it differs, record `Drift check: stale`, do not complete the coverage claim, and restart from the new snapshot or ask the user which snapshot to review.

Never repair an old anchor by attaching it to nearby or similar-looking code. Regenerate from the changed evidence.

## Exactness and redaction

Quote original diff bytes without normalization, reconstructed context, reordered lines inside a hunk, or invented ellipses. Reorder whole hunks only through review-unit ordering.

Secret redaction is the sole exception. Before hashing original secret-bearing bytes, generate an ephemeral private key and compute HMAC-SHA-256 source and anchor commitments. Keep the key only outside deliverables for the duration of drift and validation; never publish it or a plain hash that enables offline guessing. Replace only the sensitive value in the display artifact, and replace the same value anywhere it would appear in summaries, claims, context excerpts, findings, or notes. Recompute the ordinary SHA-256 display digest and anchor display fingerprint, set the source `redacted` flag and ledger state, and validate the displayed hunk byte-for-byte against those safe display bytes. Retain the item in coverage totals as `redacted`, not `validated`, then discard the sensitive temporary artifact and private key.
