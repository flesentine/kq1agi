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

The workflow fails if any additional upstream file is changed by the observer patch.

The compiled truth worker is uploaded as a CI artifact. It is **not** loaded by the production game yet.

## Trace v1

| Slot | Meaning |
| ---: | --- |
| 0 | schema version |
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
| 15 | reserved |

This is deliberately state observation, not an explanation layer yet.

## Feasibility findings

### Independent runtime state — feasible

GWT AGILE already allocates keyboard queues, key-state arrays, AGI variable/flag storage, and pixel storage through SharedArrayBuffers supplied to a worker during `Initialise`. A second set of those objects therefore creates an independent runtime-memory lane.

The truth lane must **not** share its `GwtUserInput`, `GwtVariableData`, or `GwtPixelData` instances with the edited lane.

Persistent browser services are a separate concern. In particular, the truth lane must namespace or suppress saved-game writes during certification.

### Same keyboard input — feasible

All keyboard state and encoded key presses funnel through `UserInput.setKey(...)` and the key-press queue. The GWT implementation backs both with shared memory. A certification host can mirror each input event into two independent input buffers before either worker consumes it.

Mouse state is also mirrorable because X/Y/button state is carried in `VariableData` shared slots.

### Same tick cadence — feasible

The UI releases an interpreter tick by setting `IN_TICK`; the worker clears it after completing the tick. A dual-runner host can use a barrier: release the next tick only when **both** lanes report idle.

This avoids comparing two workers that silently ran different numbers of ticks.

### Read-only semantic state — feasible

The spike observer compiles against pristine AGILE and publishes state only after `Interpreter.animationTick()` returns. It does not replace movement, collision, logic execution, flags, random calls, input consumption, or drawing.

## Important blockers found

The spike also found why simply mirroring keyboard events would produce false parity failures.

### 1. PRNG state must be shared/replayed

`GameState` creates `java.util.Random` with no common seed. Two independent workers can therefore take different random branches even when every user input is identical.

Certification needs an explicit deterministic random contract. Normal gameplay should remain unaffected when certification is off.

### 2. Sound-completion events are external

On the browser platform, sound completion is observed on the UI thread and the AGI end flag is then written into shared variable data. Two workers cannot be assumed to receive that event at exactly the same logical tick.

Certification must record/replay the completion event or otherwise feed the same logical completion tick to both lanes.

### 3. Saved-game storage must be isolated

A pristine worker constructs the normal browser saved-game store. A reference worker must never overwrite or compete with the user's real saves during certification.

## Verdict

**The dual-engine architecture is feasible, but bit-exact parity is not safe to enable yet.**

The correct next implementation is not a visible editor feature. It is the deterministic certification host:

1. create two independent SAB sets;
2. mirror keyboard + mouse input;
3. synchronize ticks with a two-worker barrier;
4. give both lanes the same deterministic PRNG event stream;
5. replay external events such as sound completion;
6. isolate truth-lane persistence;
7. compare trace-v1 state only when both lanes have completed the same tick.

Only after that should the editor label a result as **ORIGINAL RUNTIME**, **EDITED RUNTIME**, or **DIVERGED**.

The existing SIERRA control-map comparison remains useful, but it should be understood as **original control geometry**, not as an independent proof of original runtime behavior.
