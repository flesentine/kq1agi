# Truth Engine — Phase -1E Replay Minimization

Phase -1E builds on merged Phase -1D deterministic PLAY record/replay. Its first goal is to turn a long reproducing run into the shortest **from-game-start prefix** that still produces the exact same first semantic divergence.

## Why prefix first

Phase -1D restarts ORIGINAL and EDITED from the same `GAMEFILES.DAT` plus frozen EditConfig and replays the recorded transport from logical tick 1. It does **not** yet provide arbitrary interpreter checkpoints.

Because of that, Phase -1E must not claim that it can simply throw away the first ten minutes of a recording and begin from a later tick. Dropping the prefix would also drop the AGI state created by that prefix.

The authoritative first reduction is therefore:

`tick 1 ... original end` → `tick 1 ... smallest final boundary that still reproduces the same first divergence`

A later checkpoint phase can make true arbitrary-window replay possible.

## Exact divergence target

A candidate is accepted only when it reproduces the same first divergence fingerprint:

- same logical divergence tick;
- same divergence reason;
- same trace/digest slot when present;
- same ORIGINAL and EDITED values when present; and
- same external-event type when relevant.

A different semantic mismatch is not accepted merely because it is also `DIVERGED`.

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

The candidate receives a newly computed canonical recording hash. The Phase -1D replay hash verification remains authoritative.

## Search policy

The first candidate ends exactly at the original first-divergence tick. In the normal case this requires a single additional replay.

If a future replay contract needs a slightly later final settlement boundary to expose that same divergence, Phase -1E performs a binary search between the divergence tick and the original recording end to find the smallest reproducing final boundary.

If even the full recording no longer reproduces the exact target divergence, minimization reports `NOT_REPRODUCED` and does not invent a result.

## Event focus

Alongside the minimized prefix, Phase -1E extracts a small focus view around the divergence tick containing:

- canonical transport events;
- recorded RNG draws; and
- recorded interpreter release ticks.

This is a debugging view, not an arbitrary-start replay window. The complete prefix is still required to reconstruct game state.

## What Phase -1E does not do yet

The initial Phase -1E implementation does not delete individual input events or RNG observations. Removing an isolated key-up, sound completion, or random draw can create a synthetic execution that no longer corresponds to the recorded run.

Event-level delta debugging should be added only with explicit grouping rules and the same exact-divergence acceptance test.

Phase -1E also does not claim framebuffer identity, JVM object-graph identity, or a checkpoint at the focused window start.

## Acceptance criteria

- Prefix candidates always start at logical tick 1.
- Game and EditConfig identity are preserved exactly.
- Data after the candidate final tick is removed and the recording hash is recomputed.
- A reduction is accepted only for the exact same first divergence fingerprint.
- The direct divergence-tick candidate is tried first.
- A bounded binary-search fallback finds the smallest later final boundary when needed.
- A non-reproducing recording returns `NOT_REPRODUCED` rather than a false minimization.
- The result includes an event/RNG/release focus view around the divergence.
- Phase -1D replay and hash validation remain unchanged and authoritative.

## Next implementation step

Wire the minimizer into the CERTIFY browser panel after a `DIVERGED` replay, show the original versus minimized tick span and focused events, then run the minimization path against an exact compiled Chromium artifact with both a positive divergence fixture and a changed-divergence negative control.
