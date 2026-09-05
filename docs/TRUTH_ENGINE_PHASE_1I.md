# Truth Engine — Phase -1I Checkpoint-Started Replay

Phase -1I begins consuming the exact fresh-worker checkpoint/restore substrate merged in Phase -1H.

This first slice is deliberately narrow. It does **not** accelerate Phase -1E/-1F/-1G minimization yet. It adds a replay-session cursor that can pause at an authoritative recorded boundary, capture a Phase -1H checkpoint, restore that checkpoint into fresh workers, and consume only the remaining authenticated suffix.

## Safety boundary

A Phase -1H checkpoint is exact interpreter state, but exact state alone does not prove where a replay driver may resume its transport schedule.

Phase -1I.0 therefore permits checkpoint capture only immediately **before a recorded cycle-release tick**:

1. the frozen Phase -1D recording says the previous interpreter cycle completed before release tick `T`;
2. replay settles and compares that completed cycle at logical tick `T-1`;
3. no release or transport for tick `T` has been applied yet;
4. the replay returns `REPLAY_PAUSED`; and
5. the caller may invoke `captureCheckpointProbe()` at that exact state.

A restored checkpoint is accepted as a replay cursor only when `checkpoint.logicalTick + 1` is a recorded release tick in the same authenticated recording.

A second cold-browser review exposed an additional hidden-state requirement: after a valid Phase -1H restore, AGILE could leave `currentPicture` absent even though semantic-v1 and the visible framebuffer were exact. That made the resumed worker unable to capture a second checkpoint. The Phase -1I hardening therefore upgrades the worker payload to KQ1H v2 and preserves the exact current-picture visual/priority drawing context and pen/colour state. Restored replay sessions must remain checkpointable again.

This avoids inventing an arbitrary idle state, avoids replaying same-tick transport twice, and preserves checkpoint chaining.

## Replay API

`runCertificationReplaySession(host, recording, options)` remains from-start by default.

Phase -1I.0 adds two opt-in options:

- `pauseBeforeTick`: pause only before a recorded release tick after the prior cycle has been authoritatively settled;
- `checkpoint`: restore a Phase -1H checkpoint first, verify `CHECKPOINT_ROUNDTRIP_MATCH`, verify the replay cursor boundary, and then consume only ticks after `checkpoint.logicalTick`.

A successful suffix replay reports:

- `replayStartTick`;
- `skippedPrefixTicks`; and
- `consumedTicks` for work actually executed after restore.

From-start callers continue to report a replay start tick of zero.

## Phase -1H remains authoritative

Phase -1I does not bypass or weaken Phase -1H authentication.

Before any suffix pulse:

- the full Phase -1D recording hash is verified;
- the ReplayCertificationHost still binds the actual GAMEFILES identity, EditConfig hash, recording hash, exact RNG replay spec, and recorded-external-timing mode;
- `restoreCheckpointProbe()` verifies the checkpoint SHA-256 and frozen context;
- restore must return `CHECKPOINT_ROUNDTRIP_MATCH`; and
- the restored logical tick must equal the checkpoint tick.

Hash mismatch, context mismatch, inexact restore, invalid checkpoint tick, or invalid resume boundary returns `REPLAY_CONTRACT_MISS` before the suffix is consumed.

## Why minimizers are not wired yet

Phase -1E prefix candidates and Phase -1F input candidates receive new recording hashes. Phase -1G candidates also receive new EditConfig hashes.

A checkpoint captured under the original replay context is therefore **supposed** to reject those candidates today.

The next Phase -1I slice must define a dependency-safe checkpoint rebinding rule. It may only rebind a checkpoint to a candidate after proving that every candidate-visible change occurs strictly after the checkpoint and therefore cannot alter the captured prefix state. Phase -1G requires additional care because an EditConfig change can affect execution from game start.

Until that proof exists, minimizer candidate runners stay on the full replay oracle.

## Acceptance criteria

- Existing from-start replay behavior remains the default.
- Pause is accepted only before a recorded release tick.
- The pause happens after the prior cycle is settled and before the target tick release/transport is applied.
- A restored checkpoint must pass the complete Phase -1H hash/context/exactness gate.
- A restored checkpoint must resume immediately before a recorded release tick.
- Events at `checkpoint.logicalTick` are not applied again.
- Rejected checkpoint restore or cursor validation consumes zero suffix pulses.
- A checkpoint-started replay reaches the same final state/result as the equivalent full replay.
- A resumed replay can pause at a later recorded release boundary, capture a second checkpoint, restore that second checkpoint into fresh workers, and still reproduce the same final state.
- Replay summaries expose skipped-prefix and consumed-suffix tick counts.
- Phase -1E/-1F/-1G candidate execution remains unchanged in this slice.

## Next slice

Add an explicit candidate/checkpoint compatibility proof and authenticated checkpoint-context rebinding for recording-only changes that are provably after the checkpoint. Gate every accelerated candidate against the existing full-from-start replay oracle before allowing minimizers to use the shortcut by default.


## Phase -1I.1 — candidate compatibility and authenticated rebinding

Phase -1I.1 adds the proof layer required before minimizers may reuse a checkpoint captured under another recording hash.

A checkpoint is eligible for a recording-only candidate only when all of the following hold:

1. the source checkpoint SHA-256 is valid;
2. the source and candidate Phase -1D recording hashes are independently valid;
3. the checkpoint context names the exact source recording and source RNG replay specification;
4. GAMEFILES hash/byte length are unchanged;
5. EditConfig hash is unchanged;
6. both recordings still begin at logical tick 1 and are not overflowed;
7. the checkpoint was captured under recorded-external-timing mode;
8. both source and candidate continue past the checkpoint;
9. `checkpoint.logicalTick + 1` remains a recorded cycle-release boundary; and
10. the canonical replay authority through `checkpoint.logicalTick` is exactly equal:
   - all release ticks through the checkpoint,
   - all transport events through the checkpoint, including seq/tick/phase/payload,
   - all RNG observations through the checkpoint, and
   - the frozen game/EditConfig identity fields.

Only after that proof may the checkpoint context be rebound. Rebinding is deliberately narrow:

- `recordingHash` changes to the candidate recording hash;
- `randomReplaySpec` changes to the candidate's full authenticated RNG stream;
- seed, GAMEFILES identity, EditConfig identity, and recorded-external-timing mode remain exactly frozen; and
- the complete checkpoint is SHA-256 authenticated again after the context change.

This permits suffix-only recording changes, including a shorter Phase -1E prefix or Phase -1F input removal after the checkpoint, while refusing any change that could have affected the captured state.

Phase -1G is still ineligible. A different EditConfig hash can alter execution from tick 1, so Phase -1I.1 never rebinds EditConfig identity.

The compatibility proof also emits a deterministic `compatibilityKey` containing the original checkpoint hash, candidate recording hash, and checkpoint tick. This is the minimum identity future accelerated-candidate caches must include.

### Phase -1I.1 acceptance criteria

- A suffix-only input change after the checkpoint is compatible.
- A suffix-only RNG-stream change after the checkpoint is compatible and rebinds the full candidate RNG replay specification.
- Any transport or RNG change through the checkpoint is rejected.
- Removing the checkpoint's next release boundary is rejected.
- A source or candidate ending at or before the checkpoint is rejected.
- A checkpoint not captured under recorded-external-timing mode is rejected.
- GAMEFILES changes are rejected.
- EditConfig changes are rejected.
- A tampered checkpoint is rejected before compatibility reasoning.
- A checkpoint whose context does not name the exact source recording/RNG stream is rejected.
- Successful rebinding changes only recording/RNG identity and produces a new valid checkpoint SHA-256.

Minimizer execution remains on the from-start oracle until the next slice adds candidate-level equivalence gating around this proof.
