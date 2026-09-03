# Truth Engine — Phase -1E Replay Minimization

Phase -1E builds on merged Phase -1D deterministic PLAY record/replay. Its first goal is to turn a long reproducing run into the shortest **from-game-start prefix** that still produces the exact same first semantic divergence.

## Why prefix first

Phase -1D restarts ORIGINAL and EDITED from the same `GAMEFILES.DAT` plus frozen EditConfig and replays the recorded transport from logical tick 1. It does **not** yet provide arbitrary interpreter checkpoints.

Because of that, Phase -1E must not claim that it can simply throw away the first ten minutes of a recording and begin from a later tick. Dropping the prefix would also drop the AGI state created by that prefix.

The authoritative first reduction is therefore:

`tick 1 ... original end` → `tick 1 ... smallest final boundary that still reproduces the same first divergence`

A later checkpoint phase can make true arbitrary-window replay possible.

## Source recording authority

Phase -1E derives candidates only from an intact frozen Phase -1D recording. Before any candidate is created, it requires:

- schema `kq1agi-play-recording-v1`;
- `completeFromStart=true` and `startTick=1`;
- a non-overflowed recording with at least one logical tick; and
- a canonical recording hash that exactly matches the frozen `recording.hash`.

A stale or mutated source recording is rejected before any candidate replay. Phase -1E must never "repair" an altered source merely by recomputing a fresh candidate hash, because that would weaken the Phase -1D recording-integrity contract.

Before browser minimization begins, the selected local `GAMEFILES.DAT` is re-hashed and byte-count checked against the divergent recording. The actual frozen EditConfig object is also re-hashed and must match both its declared hash and the recording's `editConfigHash`. This matters because the EditConfig envelope is top-level frozen but contains nested arrays/objects; a later in-memory mutation must not be replayed under the old identity.

## Exact divergence target

A candidate is accepted only when it reproduces the same first divergence fingerprint. The fingerprint deliberately excludes worker `cycle` and snapshot timing, but preserves the reason-specific semantic identity:

- `trace`, `semantic-digest`, and `random-stream`: same logical tick, reason, slot, ORIGINAL value, and EDITED value;
- `external-event`: same logical tick, reason, and complete stable external-event detail payload, including sound hashes/flags or worker-error identity;
- `quit-state`: same logical tick, quit booleans, and shared quit-marker state;
- `quit-handshake`: same logical tick and lane quit booleans; and
- future/unknown categories: the available slot/value/detail payload without binding to non-authoritative cycle telemetry.

A different semantic mismatch is not accepted merely because it is also `DIVERGED` or belongs to the same broad external-event category.

## Candidate construction

A prefix candidate keeps the original:

- recording schema;
- game identity/hash and byte count;
- EditConfig hash;
- complete-from-start contract; and
- tick-1 start.

It removes only data after the candidate final tick:

- later logical release ticks;
- later canonical transport events; and
- later recorded RNG draws.

The candidate receives a newly computed canonical recording hash. The Phase -1D replay hash verification remains authoritative for every replay candidate.

## Search policy

The first candidate ends exactly at the original first-divergence tick. In the normal case this requires a single additional replay.

If a future replay contract needs a slightly later final settlement boundary to expose that same divergence, Phase -1E performs a binary search between the divergence tick and the original recording end to find the smallest reproducing final boundary.

If even the full recording no longer reproduces the exact target divergence, minimization reports `NOT_REPRODUCED` and does not invent a result.

Minimization is cancellable between candidate runs. A stopped search returns `STOPPED` with the attempts completed so far.

## Event focus

Alongside the minimized prefix, Phase -1E extracts a small focus view around the divergence tick containing:

- canonical transport events;
- recorded RNG draws; and
- recorded interpreter release ticks.

The focus view is taken from the original frozen recording, so it can retain useful post-divergence context even when the authoritative minimized replay ends exactly at the divergence. This is a debugging/reporting view, not an arbitrary-start replay window. The complete prefix is still required to reconstruct game state.

## What Phase -1E does not do yet

The initial Phase -1E implementation does not delete individual input events or RNG observations. Removing an isolated key-up, sound completion, or random draw can create a synthetic execution that no longer corresponds to the recorded run.

Event-level delta debugging should be added only with explicit grouping rules and the same exact-divergence acceptance test.

Phase -1E also does not claim framebuffer identity, JVM object-graph identity, or a checkpoint at the focused window start.

## Acceptance criteria

- The source Phase -1D recording hash is verified before any candidate is derived.
- A mutated, stale, incomplete, or overflowed source is rejected rather than rehashed into a new authoritative candidate.
- Prefix candidates always start at logical tick 1.
- Game and EditConfig identity are preserved exactly.
- The selected local `GAMEFILES.DAT` and the actual frozen EditConfig object are re-verified before minimization starts.
- Data after the candidate final tick is removed and the recording hash is recomputed.
- A reduction is accepted only for the exact same first divergence fingerprint.
- External-event and terminal mismatch payload identity is preserved, not merely their broad reason/type.
- Worker cycle/snapshot timing is not treated as part of semantic divergence identity.
- The direct divergence-tick candidate is tried first.
- A bounded binary-search fallback finds the smallest later final boundary when needed.
- A non-reproducing recording returns `NOT_REPRODUCED` rather than a false minimization.
- The search can be stopped between candidate runs.
- The result includes an event/RNG/release focus view around the divergence, including original post-divergence context when available.
- Phase -1D replay and hash validation remain unchanged and authoritative.

## Browser integration status

The CERTIFY panel now enables **MINIMIZE** only after an authoritative divergent `REPLAY PLAY` result. Each candidate runs in fresh ORIGINAL/EDITED replay workers using the frozen game and EditConfig identities. The panel reports the original and minimized span plus the focused transport/RNG/release context.

Exact compiled Chromium coverage includes a positive divergence fixture and a changed-divergence negative control. The negative control must return `NOT_REPRODUCED`, proving that a different mismatch is not accepted as the original target.

## Next step

After final review and merge, the next useful reduction layer is event-group minimization with explicit dependency-safe grouping rules. Arbitrary-start window replay should remain deferred until a real interpreter checkpoint/restore contract exists.
