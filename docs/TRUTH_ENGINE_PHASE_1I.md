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
   - the frozen game/EditConfig identity fields; and
11. the checkpoint's authenticated truth/edited RNG draw counts agree, and the first N source/candidate RNG observations are exactly equal, where N is that consumed draw count.

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
- RNG compatibility is additionally bound to the checkpoint's authenticated consumed-draw count; changing any of the first N consumed draws is rejected even if tick metadata is misleading.
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


## Phase -1I.2 — shadow oracle-gated candidate replay

Phase -1I.2 adds a reusable shadow runner around the Phase -1I.1 compatibility/rebinding proof.

The full from-start replay remains authoritative in every case. The checkpoint path is experimental evidence only.

For each candidate:

1. run the candidate from logical tick 1 using the existing replay oracle, require its authenticated evidence context to name the candidate recording, and require replayStartTick = 0;
2. if that full replay does not end in a trusted terminal classification (`REPLAY_MATCH`, `DIVERGED`, or `COMPLETE`), return the full result without trying acceleration;
3. prove checkpoint/candidate compatibility with Phase -1I.1;
4. if incompatible, return the full result without trying acceleration;
5. re-authenticate the compatible checkpoint to the candidate recording/RNG identity;
6. run the candidate again from the rebound checkpoint, require its evidence context to name the same candidate recording, and require replayStartTick = checkpoint.logicalTick;
7. canonicalize both replay decisions while excluding non-semantic telemetry such as consumed-tick counts, replay-start tick, certified-barrier count, skipped-prefix count, and snapshot epoch;
8. require the canonical decisions to be exactly equal;
9. require exact terminal evidence equality for:
   - logical tick, cycle, and compared cycle,
   - ORIGINAL and EDITED diagnostic traces,
   - semantic-v1 digests including RNG draw position,
   - key queue, keys, old keys, and the complete shared variable transport,
   - framebuffer pixels,
   - exact per-lane KQ1H v2 serialized worker payloads, covering hidden reconstruction state such as current-picture drawing context,
   - quit/error state,
   - pending sound requests/completions, and
   - pending external divergence state; and
10. only then return `CHECKPOINT_ORACLE_EQUIVALENT`.

If the checkpoint path throws, omits evidence, disagrees on the replay decision, or differs in any terminal evidence field, the result is not trusted. The full replay classification remains authoritative and the runner reports either `CHECKPOINT_ORACLE_FULL_ONLY` or `CHECKPOINT_ORACLE_MISMATCH`.

The runner reports full and checkpoint consumed-tick telemetry plus `savedTicks`, but those values are explicitly excluded from semantic equivalence.

### Phase -1I.2 acceptance criteria

- Compatible full/checkpoint runs with the same semantic outcome and exact terminal evidence return `CHECKPOINT_ORACLE_EQUIVALENT`.
- Different replay-start tick, consumed ticks, certified-barrier count, skipped-prefix count, and snapshot epoch do not create false mismatches.
- Full evidence bound to the wrong recording or a full replay that did not start at tick 0 is rejected as an oracle wiring error.
- A checkpoint run bound to the wrong recording or starting anywhere except the proven checkpoint tick is never trusted.
- A decision mismatch is rejected even if terminal evidence is otherwise equal.
- An evidence mismatch is rejected even if the replay decision is equal.
- Missing or incomplete full evidence prevents any checkpoint attempt and returns the full result only.
- Missing or incomplete checkpoint evidence is rejected.
- Oracle evidence capture must include both exact worker payloads; if either lane cannot serialize hidden state, acceleration is not trusted.
- A checkpoint replay exception falls back to the full result.
- A Phase -1I.1-incompatible candidate never attempts checkpoint replay.
- Full `REPLAY_CONTRACT_MISS`, `REPLAY_TIMING_MISS`, or `STOPPED` results remain full-only.
- The full replay result remains the authoritative candidate classification in every branch.
- Phase -1E/-1F/-1G minimizer call sites remain unchanged in this slice.

The next slice may wire Phase -1E/-1F candidate execution through this shadow runner to collect real minimizer-level equivalence evidence. It must not skip the full replay until a later policy freeze explicitly permits that optimization.


## Phase -1I.3 — minimizer-level shadow evidence

Phase -1I.3 wires the recording-only Phase -1E and Phase -1F candidate call sites through the Phase -1I.2 oracle in **shadow mode**.

This is still not an acceleration-policy change. Every minimizer candidate runs from logical tick 1 first, and that full replay remains the only classification returned to the minimizer. A checkpoint replay may add evidence and telemetry, but it cannot make a candidate reproduce, fail to reproduce, or otherwise change the reduction decision.

### Checkpoint selection and capture

Each minimizer stage captures at most one experimental source checkpoint:

1. take the stage's immutable source recording and exact target divergence tick;
2. consider only recorded release ticks from 2 through the target tick;
3. translate each release tick `T` to the authoritative pre-release checkpoint at `T-1`;
4. choose the candidate closest to the midpoint of the target tick, preferring the later checkpoint on an exact tie;
5. replay the exact source from start and pause at that recorded boundary; and
6. capture a normal Phase -1H checkpoint only if the source lanes are exact there.

The midpoint choice is deterministic. It deliberately balances skipped-prefix evidence against Phase -1F eligibility: removing an input before the checkpoint must make that candidate incompatible, while suffix-only removals can still exercise the checkpoint path.

Checkpoint capture is best-effort. No usable recorded boundary, a pause/capture failure, or a user stop leaves the minimizer on its existing full-replay path.

### Candidate execution

When a source checkpoint is available, each Phase -1E/-1F candidate does the following:

1. run the complete candidate from logical tick 1 and capture Phase -1I.2 terminal evidence;
2. pass that full run to `runCheckpointCandidateOracleV1`;
3. if Phase -1I.1 says the candidate prefix is compatible, rebind and run the checkpoint suffix in a fresh replay host;
4. compare decision and terminal evidence exactly under the Phase -1I.2 rules; and
5. return **only `oracle.authoritativeSummary`** to the minimizer.

The UI reports aggregate shadow evidence after the reduction: equivalent, full-only, and mismatch counts; checkpoint attempts and trusted checkpoints; measured saved ticks; and reason counts.

A `CHECKPOINT_ORACLE_MISMATCH` is therefore scientific evidence against a future shortcut policy, not a minimizer failure and never a replacement for the full result.

### Scope boundary

Phase -1G remains intentionally unchanged and full-replay-only. Its candidates change the EditConfig hash, which can change execution from logical tick 1 and is outside the recording-only Phase -1I.1 rebinding proof.

### Phase -1I.3 acceptance criteria

- Phase -1E and Phase -1F each capture at most one deterministic checkpoint from their own immutable source recording.
- Checkpoints are captured only at a recorded pre-release boundary before or at the target divergence.
- Every candidate still runs the full from-start replay first.
- The minimizer receives the full replay's authoritative summary even when the checkpoint shadow disagrees.
- A compatible candidate reaches `CHECKPOINT_ORACLE_EQUIVALENT` only after exact Phase -1I.2 decision and terminal-evidence equality.
- Prefix-changing Phase -1F candidates remain full-only and do not attempt a checkpoint suffix.
- Missing terminal evidence or unavailable checkpoint capture falls back to the full result without blocking reduction.
- Shadow telemetry is reported but is not semantic input to the minimizer.
- Phase -1G has no checkpoint capture, rebinding, or shadow-run call site.
- No policy is allowed to skip the full replay in this slice.

## Next slice

Collect minimizer-level equivalence evidence across real divergent reproductions and freeze an explicit acceleration policy only after the observed compatible population is large enough to justify it. Until that policy is separately reviewed and frozen, full replay remains mandatory for every candidate.
