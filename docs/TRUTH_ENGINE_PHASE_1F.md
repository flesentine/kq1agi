# Truth Engine — Phase -1F Dependency-Safe Input Minimization

Phase -1F builds on merged Phase -1E prefix minimization. Phase -1E answers **how early can the replay stop?** Phase -1F answers **which user-input actions inside that minimized prefix are actually required to reproduce the exact same first semantic divergence?**

The authoritative replay still starts at logical tick 1. Phase -1F does not introduce arbitrary checkpoints.

## Scope

Phase -1F minimizes only canonical **user-input transport groups**:

- keyboard state/queue gestures; and
- mouse/touch state gestures.

It deliberately does **not** remove:

- interpreter release ticks;
- recorded RNG draws;
- sound-completion events;
- GAMEFILES.DAT identity;
- EditConfig identity; or
- the Phase -1E minimized final tick.

Those remain reproduction authority. If removing an input group changes RNG consumption, scheduling semantics, sound behavior, or the first divergence, that candidate is rejected.

## Dependency-safe keyboard groups

Removing isolated key events can create synthetic states, especially a key-down without its recorded key-up.

Phase -1F therefore pairs canonical \`key-state\` down/up transitions for each key. Overlapping key intervals are merged so modifier/chord sessions are atomic. Canonical \`key-queue\` events inside a matched interval remain in that same group.

Examples:

- \`A down → queue A → A up\` is one group.
- \`SHIFT down → B down → queue B → B up → SHIFT up\` is one group.
- A queue-only action with no matching state interval is independently removable.
- An unmatched key-state fragment at the recording boundary is **locked**, because the frozen prefix does not contain a dependency-safe closing boundary.

This is intentionally conservative. A later phase may record explicit browser-input transaction IDs if finer physical-key attribution becomes valuable.

## Dependency-safe mouse groups

Normal AGILE mouse/touch processing updates button, X, and Y as separate shared-memory writes. The Phase -1D journal therefore contains multiple canonical mouse snapshots for one physical pointer update.

Phase -1F first groups consecutive same-tick/same-phase mouse writes into a physical state batch. It then keeps a held-button interval atomic:

\`press batch → zero or more drag/move batches → release batch\`

A plain mouse move while no button is held is independently removable as one state batch.

This prevents minimization from keeping a press while deleting its release or from retaining only a partial X/Y/button update.

## Exact divergence authority

Every candidate must still reproduce the exact Phase -1E divergence fingerprint. A different \`DIVERGED\` result does not count.

The source recording is re-verified with the Phase -1E authenticated snapshot contract before grouping. Every accepted candidate receives a fresh canonical Phase -1D recording hash.

Only an authoritative replay summary with status \`DIVERGED\` can satisfy a candidate.

## Delta-debug search

Phase -1F uses dependency-safe delta debugging over the derived input groups.

1. Replay the exact Phase -1E source once to prove the target still reproduces.
2. Start with all input groups kept.
3. Try removing large chunks of groups.
4. If the exact divergence remains, keep that reduction and continue.
5. Increase search granularity until no remaining single dependency-safe group can be removed.

The completed result is therefore **1-minimal with respect to the Phase -1F groups**: no one remaining group can be deleted while preserving the same target divergence under this grouping policy.

A default attempt budget prevents an unexpectedly large recording from launching an unbounded number of full replays. Hitting that limit returns \`PARTIAL\`; it never claims minimality.

The STOP control is honored between candidate runs.

## Result meanings

- \`INPUTS_MINIMIZED\` — at least one dependency-safe input group was removed and the final set is 1-minimal.
- \`INPUTS_ALREADY_MINIMAL\` — the source reproduces, but no dependency-safe group can be removed.
- \`NO_REMOVABLE_INPUTS\` — the replay contains no keyboard/mouse groups; only locked reproduction events remain.
- \`NOT_REPRODUCED\` — the exact source no longer reproduces the target; no input reduction is accepted.
- \`PARTIAL\` — useful reductions may have been found, but the attempt budget ended before minimality was proven.
- \`STOPPED\` — the user stopped the search between candidates.

## What Phase -1F does not remove

Phase -1F does not minimize RNG draws or sound-end events. Those are observed consequences/external completions needed to reproduce the recorded run, not interchangeable user actions.

It also does not rewrite release timing after input deletion. The recorded logical schedule remains fixed; a candidate that cannot honor it is rejected by the existing Phase -1D replay contract.

## Acceptance criteria

- Phase -1E remains the authority for the minimized final tick and exact divergence fingerprint.
- Input grouping is derived from the authenticated canonical recording representation.
- Keyboard down/up dependencies are atomic; overlapping modifier/chord intervals merge.
- Mouse button gestures and their three-write state batches are atomic.
- Queue-only keyboard actions and button-up mouse moves can be independently removable; unmatched keyboard state fragments stay locked.
- Sound completions, RNG draws, release ticks, game identity, EditConfig identity, and final tick are never removed.
- Every candidate has a fresh canonical recording hash.
- The unchanged source must reproduce the exact target immediately before reduction starts.
- A different semantic divergence is never accepted.
- Completed delta-debugging results are 1-minimal with respect to the dependency-safe groups.
- Attempt-budget exhaustion is reported as \`PARTIAL\`, not minimal.
- Cancellation is honored between candidate replays.

## Browser integration target

After Phase -1E reports \`MINIMIZED TO T\`, CERTIFY should enable **REDUCE INPUTS**. The UI will reuse the same frozen GAMEFILES.DAT/EditConfig identity, run each candidate through fresh ORIGINAL/EDITED workers, and report:

- input groups before/after;
- canonical input events before/after;
- locked reproduction events retained;
- candidate replay attempts; and
- a concise description of the remaining dependency-safe groups.

Exact compiled Chromium validation should include a recording with at least one irrelevant keyboard gesture, one required keyboard gesture, and an irrelevant mouse gesture, plus a changed-divergence negative control.
