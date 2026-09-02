# Truth Engine Spike — Phase -1A

This spike answers three questions before the editor adds any more behavioral overlays:

1. Can a pristine AGILE reference lane exist independently from the edited KQ1AGI runtime?
2. Can both lanes receive the same deterministic input/tick stream?
3. Can the pristine lane publish a useful semantic trace without participating in game decisions?

The reference source is pinned to the same upstream AGILE commit already used by KQ1AGI:

`81c42ba63b3b7f5fb260d282592681c097d46da9`

## What the spike builds

`.github/workflows/truth-engine-spike.yml` checks out a second pristine AGILE tree, applies only `scripts/instrument_truth_worker.py`, and compiles its normal GWT worker bundle.

The observer patch is intentionally limited to two files:

- `Interpreter.java` — exposes a read-only 16-slot diagnostic snapshot.
- `AgileWebWorker.java` — optionally writes that snapshot to a dedicated SharedArrayBuffer after each completed tick.

The workflow fails if any additional upstream file is changed by the observer patch. It also verifies the generated worker bundle contains the optional diagnostic transport, rather than checking source markers alone.

The compiled truth worker is uploaded as a CI artifact. It is **not** loaded by the production game yet.

## Trace v2

| Slot | Meaning |
| ---: | --- |
| 0 | schema version (`2`) |
| 1 | total ticks |
| 2 | current room |
| 3 | ego X |
| 4 | ego Y / baseline |
| 5 | ego direction |
| 6 | `ONWATER` |
| 7 | `HITSPEC` |
| 8 | `EGOEDGE` |
| 9 | ego view |
| 10 | ego loop |
| 11 | ego cel |
| 12 | ego priority |
| 13 | user-control state |
| 14 | hold-key mode |
| 15 | packed AGI game clock: `DAYS:HOURS:MINUTES:SECONDS` |

The optional trace SharedArrayBuffer must be at least 64 bytes (16 Uint32 slots) **and its byte length must be divisible by 4**. Shorter or misaligned buffers are ignored rather than being allowed to crash the truth worker.

This trace is deliberately a **diagnostic observation surface**, not a complete parity proof. It is excellent for saying where an observed room/ego/hazard/clock divergence first became visible. It cannot prove that every piece of AGI state is identical, because it does not yet include every variable, flag, animated object, inventory/resource state, scan start, script state, and other interpreter state.

A future UI may say **DIVERGED** as soon as trace v2 (or the full digest) differs. It must not say full runtime **MATCH** based on trace v2 alone.

## Feasibility findings

### Independent runtime state — feasible

GWT AGILE already allocates keyboard queues, key-state arrays, AGI variable/flag storage, and pixel storage through SharedArrayBuffers supplied to a worker during `Initialise`. A second set of those objects therefore creates an independent runtime-memory lane.

The truth lane must **not** share its `GwtUserInput`, `GwtVariableData`, or `GwtPixelData` instances with the edited lane.

Persistent browser services are a separate concern. In particular, the truth lane must namespace or suppress saved-game writes during certification.

### Same keyboard and mouse input — feasible

All keyboard state and encoded key presses funnel through `UserInput.setKey(...)` and the key-press queue. The GWT implementation backs both with shared memory. A certification host can mirror each input event into two independent input buffers before either worker consumes it.

Mouse state is also mirrorable because X/Y/button state is carried in `VariableData` shared slots.

### Worker tick barrier — feasible

The UI releases an interpreter tick by setting `IN_TICK`; the worker clears it after completing the tick. A dual-runner host can use this as a barrier: release the next interpreter tick only when **both** workers report idle.

That is only the worker half of determinism, however. The normal `AgileRunner.tick()` uses `TimeUtils.nanoTime()` on the UI thread to decide when to increment `TOTAL_TICKS`, update the AGI `DAYS/HOURS/MINUTES/SECONDS` clock, and release animation ticks. Two independent normal runner clocks could therefore advance differently even if both workers use a perfect barrier.

Certification must use **one logical 60 Hz clock** for both lanes. That clock advances total ticks and the AGI game clock identically in both variable stores, then releases both workers, then waits for both to finish.

### Read-only semantic state — feasible

The spike observer compiles against pristine AGILE and publishes state only after `Interpreter.animationTick()` returns. It does not replace movement, collision, logic execution, flags, random calls, input consumption, drawing, or the normal runner clock.

## Important blockers found

The spike found several reasons why simply mirroring keyboard events would produce false parity failures.

### 1. The UI wall clock must be centralized

`AgileRunner.tick()` is driven by `TimeUtils.nanoTime()`. It increments `TOTAL_TICKS` and updates the AGI game clock outside the worker.

Certification must not run two independent `AgileRunner.tick()` clocks. One deterministic certification clock must advance both lanes identically before releasing the two-worker barrier.

### 2. PRNG state must be shared/replayed

`GameState` creates `java.util.Random` with no common seed. Two independent workers can therefore take different random branches even when every user input is identical.

Certification needs an explicit deterministic random contract. Normal gameplay should remain unaffected when certification is off.

For debugging, the first random-call divergence should eventually be observable too: once two runs consume a different number of random values, later random outcomes are no longer directly comparable without a checkpoint/replay boundary.

### 3. Sound-completion events are external

On the browser platform, sound completion is observed on the UI thread and the AGI end flag is then written into shared variable data. Two workers cannot be assumed to receive that event at exactly the same logical tick.

Certification must record/replay the completion event or feed the same logical completion tick to both lanes.

### 4. Saved-game storage must be isolated

A pristine worker constructs the normal browser saved-game store. A reference worker must never overwrite or compete with the user's real saves during certification.

### 5. Trace v2 is not a complete state oracle

Two runs can have identical room, Graham position, `ONWATER`, `HITSPEC`, and clock values while already differing somewhere else—for example an arbitrary AGI flag, score, inventory, another animated object, a scan start, loaded resource state, or script state.

Before the editor can claim full runtime **MATCH**, Phase -1B needs a deterministic semantic state digest (or equivalent complete state comparison) in addition to trace v2. The trace remains valuable because it is human-readable and can explain where common gameplay divergences become visible.

## Verdict

**The dual-engine architecture is feasible, but full runtime parity is not safe to enable yet.**

The correct next implementation is the deterministic certification host:

1. create two independent SAB sets;
2. mirror keyboard + mouse input;
3. use one logical 60 Hz certification clock to advance `TOTAL_TICKS` and `DAYS/HOURS/MINUTES/SECONDS` identically;
4. release both workers together and wait on the two-worker `IN_TICK` barrier;
5. give both lanes the same deterministic PRNG contract;
6. replay external events such as sound completion at the same logical tick;
7. isolate truth-lane persistence;
8. add a deterministic full semantic state digest;
9. compare trace v2 for readable diagnostics and the state digest for full parity.

Only then should the editor use **ORIGINAL RUNTIME**, **EDITED RUNTIME**, **DIVERGED**, and full runtime **MATCH** as authoritative labels.

The existing SIERRA control-map comparison remains useful, but it should be understood as **original control geometry**, not as independent proof of original runtime behavior.
