# Truth Engine — Phase -1H Exact Checkpoint/Restore Probe

Phase -1H begins the checkpoint/restore work that was deliberately deferred through Phases -1D through -1G.

The long-term goal is arbitrary-start certification replay near a minimized divergence instead of replaying every candidate from logical tick 1. This first slice does **not** enable arbitrary-start replay yet. It establishes the safety gate that must pass before such replay can be trusted.

## Why ordinary AGI saves are not checkpoints

AGILE already has mature save/restore logic, but a Sierra-compatible saved game is a gameplay persistence format, not an exact interpreter snapshot. It intentionally normalizes or omits state that semantic certification can observe, including exact 60 Hz tick position and other transient interpreter fields.

Phase -1H therefore uses AGILE save/restore only as a reconstruction backbone. It never assumes that restoring those bytes recreates the exact certification state.

## Phase -1H probe contract

A checkpoint probe may be captured only when:

- both certification workers are ready and idle;
- the host has synchronized a fresh common-barrier snapshot; and
- ORIGINAL and EDITED currently report semantic-v1 MATCH.

At that barrier the host captures losslessly:

- the complete key ring buffer including read/write positions;
- current and old key arrays;
- all 8,353 shared variable/editor slots for each lane;
- the full shared pixel buffer for each lane;
- logical tick, interpreter cycle and compared-cycle counters; and
- pending deterministic sound-completion timing.

Each worker separately captures a certification-only, noninteractive AGI save/restore reconstruction payload into worker-local memory. This uses a temporary in-memory SavedGameStore and never touches OPFS or the player's certification-session saved games.

## Destructive round-trip verification

The first implementation keeps the worker checkpoint payload inside the worker. This is intentional: before defining a cross-worker serialized checkpoint format, the project must prove that the reconstruction is exact enough to restore the same certification state at all.

On restore:

1. each worker restores its worker-local reconstruction payload while idle;
2. the certification wrapper runs the same post-restore reconstruction as AGILE's normal `restore.game` command: sound reset, menu enable, script-event replay, picture rebuild/show, and status-line update;
3. the host restores the exact shared transport buffers and host logical metadata;
4. the host requests a fresh common-barrier snapshot;
5. each restored lane is compared against **its own captured trace and semantic digest**; and
6. only after both per-lane comparisons pass does ORIGINAL-vs-EDITED MATCH count.

Comparing only the two restored lanes would be unsafe because both lanes could restore to the same wrong state.

## Result meanings

- `CHECKPOINT_CAPTURED` — a probe payload and host transport snapshot were captured at an authoritative MATCH barrier.
- `CHECKPOINT_BASELINE_REJECTED` — the capture point was not an authoritative MATCH barrier.
- `CHECKPOINT_CAPTURE_UNAVAILABLE` — the barrier is valid but the save-game reconstruction backbone cannot represent it yet (v1: no current Picture before the first `draw.pic`).
- `CHECKPOINT_CAPTURE_ERROR` — one or both workers threw while creating the reconstruction payload.
- `CHECKPOINT_RESTORE_ERROR` — one or both workers could not restore the payload.
- `CHECKPOINT_NOT_EXACT` — restore completed, but at least one lane's trace/digest differs from its captured barrier.
- `CHECKPOINT_ROUNDTRIP_MATCH` — both lanes individually restored to their captured semantic-v1 state and still match each other.

A `CHECKPOINT_NOT_EXACT` result is expected to identify the next missing state that must be added to the checkpoint format. It is not treated as a semantic ORIGINAL-vs-EDITED bug.

## Worker transport

The semantic digest SharedArrayBuffer grows from 10 to 13 Uint32 slots:

- slot 8: existing snapshot request epoch;
- slot 9: existing snapshot acknowledgement;
- slot 10: checkpoint request, packed as `(epoch << 2) | action`;
- slot 11: checkpoint acknowledgement; and
- slot 12: checkpoint status.

Action 1 captures the worker-local reconstruction payload. Action 2 restores it. The worker services these requests from the same idle busy-wait path used by the existing certification snapshot barrier, so correctness does not depend on postMessage callbacks that cannot run while AGILE is waiting on `IN_TICK`.

## Production safety

The checkpoint store and worker hooks are installed only in the opt-in certification workers. Normal PLAY and EDIT are unchanged.

No game resources or checkpoint payloads are committed or uploaded.

## Acceptance criteria for this slice

- Certification host unit tests cover exact and deliberately inexact checkpoint round trips.
- Both pristine ORIGINAL and current EDITED certification workers compile with the checkpoint probe.
- The runtime contract checker verifies the checkpoint store, worker shared-memory handshake and host per-lane exactness gate.
- Browser certification packaging includes the Phase -1H documentation and probe-instrumented workers.
- No arbitrary-start replay UI is enabled yet.
- A later Chromium run must identify whether a real compiled-worker round trip is already exact or which semantic partition still needs supplemental checkpoint state.

## Next implementation step

Run the probe against the exact compiled workers with the public qualification game. For every `CHECKPOINT_NOT_EXACT` result, add only the missing state required to make the same barrier round-trip exact. Once real checkpoints reliably return `CHECKPOINT_ROUNDTRIP_MATCH`, define an authenticated cross-worker checkpoint serialization and allow replay to begin from that checkpoint.
