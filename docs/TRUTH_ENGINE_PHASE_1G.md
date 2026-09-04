# Truth Engine — Phase -1G Dependency-Safe EditConfig Minimization

Phase -1G builds on the merged Phase -1F pipeline. Phase -1E minimizes how long the reproduction must run. Phase -1F minimizes which user actions are necessary. Phase -1G asks which editor configuration changes are actually necessary to cause the exact same first semantic divergence.

The replay still starts at logical tick 1. Phase -1G does not add arbitrary interpreter checkpoints.

## Scope

Phase -1G minimizes only frozen EditConfig v1 groups:

- each configured room is one atomic room-config group; and
- the complete visual-pin set is one atomic visual-pins group.

The first implementation is deliberately conservative. It does not delete individual mask pixels, split control-seed fields from their room, or reorder visual-pin records. Finer-grained mask or pin minimization can be added later after explicit dependency rules exist.

## Identity contract

Changing EditConfig changes replay identity. Therefore every candidate gets two fresh authenticated identities:

1. a new EditConfig hash for the candidate configuration; and
2. a new PLAY recording hash whose editConfigHash is rebound to that candidate.

GAMEFILES.DAT identity, the minimized final tick, release timing, user-input recording, RNG observations, sound-completion events, and the exact target divergence remain frozen.

The original Phase -1F recording and EditConfig are re-verified before the search starts. A stale or mutated source is rejected rather than silently re-hashed.

## Exact divergence authority

A candidate is accepted only when a fresh ORIGINAL/EDITED replay reproduces the exact same Phase -1E divergence fingerprint. A different DIVERGED result does not count.

## Search

Phase -1G uses bounded delta debugging over the EditConfig groups:

1. replay the unchanged source pair to prove the target still reproduces;
2. try removing groups in chunks;
3. keep a reduction only when the exact target still reproduces;
4. increase granularity until no remaining single group can be removed.

A completed result is 1-minimal with respect to the Phase -1G grouping policy. Attempt-budget exhaustion returns PARTIAL and never claims minimality. STOP is honored between candidate runs.

## Result meanings

- EDITS_MINIMIZED — one or more EditConfig groups were removed and the result is 1-minimal.
- EDITS_ALREADY_MINIMAL — the source reproduces but no EditConfig group can be removed.
- NO_REMOVABLE_EDITS — the frozen EditConfig contains no room entries or visual pins.
- NOT_REPRODUCED — the unchanged source no longer reproduces the exact target.
- PARTIAL — useful reductions may exist, but the attempt budget ended before minimality was proven.
- STOPPED — the user stopped between candidate replays.

## Browser integration

After Phase -1F completes, CERTIFY enables REDUCE EDITS. The UI reports:

- EditConfig groups before and after;
- configured rooms before and after;
- visual pins before and after;
- the reduced EditConfig identity;
- the rebound recording identity; and
- the remaining atomic edit groups.

Phase -1G also carries forward the Phase -1F reduced recording when REDUCE INPUTS succeeds, so repeating a reduction does not accidentally restart from the older unreduced input source.

## Acceptance criteria

- Source recording hash and source EditConfig hash are re-verified before candidate derivation.
- Canonical room entries must have unique room numbers.
- Room configurations are atomic groups.
- Visual pins are one atomic group in v1.
- Every candidate receives a fresh EditConfig hash and a freshly rebound recording hash.
- GAMEFILES.DAT, final tick, releases, inputs, RNG draws, sound completions, and target divergence stay frozen.
- Different divergences are rejected.
- Completed searches are 1-minimal with respect to the Phase -1G groups.
- Budget exhaustion reports PARTIAL.
- Cancellation is honored between candidate replays.
- Browser CI packages and tests the new minimizer without adding game data.

## Next step

After Phase -1G is validated and merged, the next major truth-engine capability should be a real checkpoint/restore contract so a minimized reproduction can begin near the divergent window instead of replaying from logical tick 1.
