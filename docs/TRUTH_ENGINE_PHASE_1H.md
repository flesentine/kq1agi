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

Each worker separately captures a certification-only, noninteractive AGI save/restore reconstruction payload. This uses a temporary in-memory SavedGameStore and never touches OPFS or the player's certification-session saved games.

The real compiled-worker qualification exposed the first expected gap in that reconstruction: AGILE's Sierra save payload restored semantic digest partitions 1–3 exactly but changed partition 0. Phase -1H therefore layers a worker-local transient overlay over the save backbone. The overlay captures the digest-visible core GameState fields that Sierra persistence intentionally normalizes or omits, including controllers, input/menu/picture scalars, animation phase, text colours/attributes, current input text, and related control state.

## Serialized checkpoint and round-trip verification

The initial probe kept the reconstruction payload worker-local until real compiled-worker qualification proved the reconstruction exact. The next Phase -1H slice now serializes the Sierra reconstruction bytes and transient/RNG overlay into one deterministic `KQ1H` v1 binary envelope.

Each lane exports that envelope through a dedicated SharedArrayBuffer. The host copies both lane payloads into the checkpoint object, snapshots the host/shared transports, and computes an authenticated checkpoint identity over the canonical content. Restore verifies that identity before making any worker or shared-memory mutation.

Because restore imports the worker envelope from the host-owned checkpoint transport, it no longer depends on a payload left behind in the worker that created the checkpoint. A JSON-serialized checkpoint can therefore be imported into newly started ORIGINAL and EDITED workers.

On restore:

1. the host verifies the checkpoint content hash and writes each serialized worker envelope into the fresh worker's checkpoint transport;
2. the certification wrapper runs the same post-restore reconstruction as AGILE's normal `restore.game` command: sound reset, menu enable, script-event replay, picture rebuild/show, and status-line update;
3. the worker reapplies the transient checkpoint overlay and rewinds the certification random source to its captured draw position;
4. the host restores the exact shared transport buffers and host logical metadata;
5. the host requests a fresh common-barrier snapshot;
6. each restored lane is compared against **its own captured trace and semantic digest**; and
7. only after both per-lane comparisons pass does ORIGINAL-vs-EDITED MATCH count.

Comparing only the two restored lanes would be unsafe because both lanes could restore to the same wrong state.

Fresh-worker restore is held to the same per-lane exactness rule as same-worker restore. A new worker pair must reproduce each lane's captured trace/digest before suffix replay can rely on the checkpoint.

## Result meanings

- `CHECKPOINT_CAPTURED` — a probe payload and host transport snapshot were captured at an authoritative MATCH barrier.
- `CHECKPOINT_BASELINE_REJECTED` — the capture point was not an authoritative MATCH barrier.
- `CHECKPOINT_CAPTURE_UNAVAILABLE` — the barrier is valid but the save-game reconstruction backbone cannot represent it yet (v1: no current Picture before the first `draw.pic`).
- `CHECKPOINT_CAPTURE_ERROR` — one or both workers threw while creating the reconstruction payload.
- `CHECKPOINT_RESTORE_ERROR` — one or both workers could not restore the payload.
- `CHECKPOINT_HASH_MISMATCH` — checkpoint content no longer matches its authenticated identity; restore is rejected before mutation.
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

Action 1 captures and exports the serialized reconstruction envelope. Action 2 imports the host-supplied envelope and restores it. A separate bounded checkpoint SharedArrayBuffer carries the payload bytes. The worker services these requests from the same idle busy-wait path used by the existing certification snapshot barrier, so correctness does not depend on postMessage callbacks that cannot run while AGILE is waiting on `IN_TICK`.

## Production safety

The checkpoint store and worker hooks are installed only in the opt-in certification workers. Normal PLAY and EDIT are unchanged.

No game resources or checkpoint payloads are committed or uploaded.

## Acceptance criteria for this slice

- Certification host unit tests cover exact and deliberately inexact checkpoint round trips, hash-tamper rejection, JSON serialization, and fresh-worker import.
- Both pristine ORIGINAL and current EDITED certification workers compile with the checkpoint probe.
- The runtime contract checker verifies the checkpoint store, worker shared-memory handshake and host per-lane exactness gate.
- Browser certification packaging includes the Phase -1H documentation and probe-instrumented workers.
- No arbitrary-start replay UI is enabled yet.
- Real compiled-worker Chromium qualification must pass after restoring both the Sierra reconstruction payload and the transient/RNG overlay.

## Next implementation step

Compile and qualify the serialized checkpoint against the exact browser artifact. The required proof is: capture on one worker pair, JSON-serialize the authenticated checkpoint, terminate that pair, start fresh ORIGINAL/EDITED workers with the same frozen game/EditConfig/replay identity, import the checkpoint, and reproduce the same deterministic suffix. Only after that passes should Phase -1H expose checkpoint-started replay to the minimizers.
