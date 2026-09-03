# Truth Engine — Phase -1D PLAY Record/Replay

Phase -1D extends the merged Phase -1C browser certification bridge with a local, in-memory recording of the **normal PLAY transport** and deterministic replay of that recording through the independent pristine ORIGINAL and current EDITED certification workers.

Phase -1D does not replace `semantic-v1`. It adds a reproducibility contract around the already-frozen comparator so an interactive gameplay window can be rerun rather than stopping at `WAITING FOR INPUT`.

## Recording authority

The page installs the journal bootstrap before AGILE launches. The journal itself is reset and bound to one game when normal **PLAY starts**, before that game's worker begins its first logical tick. Starting another game in the same page clears the old journal so two PLAY sessions cannot be merged accidentally.

Phase -1D records values **after AGILE has already translated browser input into the transport seen by the normal worker**, rather than trying to reconstruct that translation later from DOM events.

PLAY recording v1 contains:

- the exact key-state writes made to the normal `keysSAB` transport;
- the exact encoded AGI key values added to the normal key-press queue;
- mouse X/Y/button values written into the normal shared variable transport;
- every normal 60 Hz logical pulse and whether that pulse released a new interpreter cycle;
- actual bounded AGI random results as `(bound, value)` pairs in draw order; and
- actual sound end-flag completion events at the logical tick observed by normal PLAY.

Each transport event also retains whether normal PLAY observed the worker as **idle** or **busy** when the write occurred. That phase is provenance, not a wall-clock deadline. Idle writes are replayed only after the corresponding cycle has settled at that same logical tick. Busy writes are injected at a deterministic logical-tick boundary before the replay workers get their next event-loop turn, but replay does not require a worker to still be busy on the current CPU. The authoritative replay clock is the logical 60 Hz tick; Phase -1D does not claim an exact Java instruction position for a browser write that happened part-way through a busy interpreter cycle.

The journal is kept only in browser memory. It is not written to OPFS, localStorage, CI, the repository, or a network endpoint. A safety cap prevents an unbounded browser-memory journal; if that cap is reached, replay is refused rather than silently truncating the recording.

## Frozen replay identity

For an imported game, AGILE's `AppConfigItem.filePath` is the directory name passed to `OPFSGameFiles` for `Game Files/<directory>/GAMEFILES.DAT`. Phase -1D records that directory at PLAY start. **REPLAY PLAY refuses to run if the CERTIFY selector points at a different local game.** This prevents a valid journal from game A being replayed against game B merely because game B was selected when certification began.

When **REPLAY PLAY** is pressed, the current journal is copied synchronously before any asynchronous hashing or OPFS work. The replay is then bound to:

1. the local game directory captured when PLAY started;
2. the SHA-256 identity of that selected local `GAMEFILES.DAT` buffer;
3. the frozen Phase -1C `EditConfig v1` hash; and
4. the canonical `kq1agi-play-recording-v1` hash.

The recording must start at logical tick 1. If the journal started late or cannot be tied to the current local game, Phase -1D refuses replay rather than pretending it can reconstruct the missing identity or prefix.

The recording hash authenticates a canonical representation: release ticks are normalized, transport events are canonicalized and ordered by sequence, and valid RNG draws are ordered by sequence. Replay now executes that **same canonical representation**. Hash-equivalent raw representation changes therefore cannot alter replay behavior; for example, reordering the raw RNG array or appending a malformed draw cannot change the RNG stream while retaining the same recording identity.

## Replay semantics

The certification replay host is a Phase -1D subclass of the frozen Phase -1B host. The base host and `semantic-v1` comparator remain unchanged.

For each recorded logical tick, replay:

1. applies recorded transport at its logical tick, settling idle-phase writes at that tick and injecting busy-phase writes at the deterministic tick boundary;
2. applies the frozen EditConfig only to EDITED, and only while both certification lanes are idle;
3. advances the shared AGI clock at a paced logical 60 Hz;
4. releases a new interpreter cycle only when normal PLAY recorded a release at that tick;
5. feeds both certification workers the exact recorded bounded RNG stream; and
6. injects recorded sound completion flags rather than deriving completion timing from WAV duration.

Busy-phase transport is injected synchronously after the replay clock/release writes and before either certification worker receives its next event-loop turn. Phase -1D does **not** fail merely because a faster replay worker has already completed by that boundary; the recorded busy flag cannot identify an exact Java instruction position.

A recorded release at logical tick `T` is authoritative: before advancing from `T-1` to `T`, replay holds logical time at `T-1` until both lanes finish the preceding cycle and that shared barrier is compared. Likewise, an idle-phase transport event stamped at `T` holds logical time at `T` until the in-flight cycle settles, then applies the event. Wall-clock playback may therefore be slower than 60 Hz while the simulated AGI clock remains exactly on the recorded tick schedule. Faster or slower worker execution by itself is not `REPLAY_TIMING_MISS`.

ORIGINAL receives the same recorded gameplay transport but never receives EditConfig. EDITED receives the same gameplay transport plus the frozen EditConfig.

A completed shared barrier is still compared with the Phase -1B trace/digest/event/terminal contract. The first covered semantic mismatch remains `DIVERGED` with the existing category reporting.

## Final recording boundary

`RecordingRandomDraw` and `RecordingCycleComplete` are FIFO messages from the same normal PLAY worker. `RecordingCycleComplete` is posted after the interpreter returns for the released cycle, so observing that marker also proves that every RNG observation posted earlier by that cycle has reached the UI message queue.

Phase -1D freezes a PLAY window only when the normal shared worker is idle and the most recent released cycle's completion marker has arrived. The synchronous boundary check and journal copy happen in one UI task, so another 60 Hz page callback cannot interleave between validation and the copy.

The last recorded 60 Hz pulse is not automatically a certification barrier. Phase -1D therefore settles any final in-flight certification cycle **without advancing logical time**, publishes the normal Phase -1B common-barrier snapshot at that same final tick, and compares it before `REPLAY MATCH` can be reported. A semantic difference that appears only when the final cycle completes is still reported as `DIVERGED` at the final recorded tick.

After that final barrier, Phase -1D also verifies that ORIGINAL and EDITED both consumed the complete recorded bounded-RNG stream. Two lanes agreeing with each other after consuming only a prefix of the recording is not accepted as a match.

## Replay timing and contract misses

Worker scheduling is not silently converted into a gameplay mismatch. A normal cycle taking longer than one browser frame is allowed: replay waits at the recorded logical boundary without advancing simulated time. If a worker does not settle within the certification safety timeout, or the host cannot perform a release after the preceding recorded barrier has been settled, Phase -1D reports:

`REPLAY_TIMING_MISS`

This means replay could not reach a required recorded logical boundary safely. It is **not** a penalty for ordinary CPU-speed variation and is **not** reported as an ORIGINAL-vs-EDITED divergence.

If the frozen recording itself cannot be honored — for example, its transport phase ordering is impossible, the replay host does not provide a required phase hook, or both lanes do not consume the complete recorded RNG stream — Phase -1D reports:

`REPLAY_CONTRACT_MISS`

That is also a reproduction failure rather than a semantic divergence.

Replay ticks are paced at logical 60 Hz for the same reason as the Phase -1C smoke runner: running pulses as fast as the event loop allows would turn worker CPU scheduling into simulated game time.

## Random stream

Normal PLAY still uses the existing `java.util.Random` implementation. Phase -1D adds an observer around **all five bounded AGI runtime random call sites in the pinned engine**: four `AnimatedObject` wander/follow draws and the AGI `random` command. A build-time coverage check fails if any direct `state.random.nextInt(...)` call remains in those runtime paths. With no observer, the helper delegates directly to the existing `Random.nextInt(bound)`.

During replay, both certification lanes use `CertificationReplayRandom`, which returns the captured `(bound, value)` sequence exactly. Stream exhaustion or a bound mismatch is a replay-contract failure; the runtime does not invent a replacement random value. At the final settled barrier, both lanes' consumed draw counts must also equal the frozen recording's total draw count.

The Phase -1C no-input smoke path remains available and continues to use the deterministic seeded `CertificationRandom` path when no replay stream is supplied.

## EditConfig constraint

Phase -1D v1 assumes the editor configuration is stable during the gameplay window being reproduced. The frozen EditConfig is the configuration present when REPLAY PLAY is pressed. Phase -1D v1 does **not** journal historical scene-mask or sprite-pin authoring mutations that happened earlier in that same PLAY window.

For a clean reproduction, finish editing first, start/reload the intended local game, reproduce the gameplay event without changing editor configuration, and then run REPLAY PLAY.

## Result meanings

- `REPLAY MATCH × N` — the recorded logical window and transport phases were consumed, the final in-flight cycle was settled at the same final tick, the complete recorded RNG stream was consumed, and no covered semantic divergence was found across `N` shared barriers.
- `DIVERGED @ tick` — the first covered ORIGINAL-vs-EDITED semantic divergence in the recorded window.
- `REPLAY COMPLETE / MATCH` — both lanes reached the synchronized terminal contract and the final semantic state matched.
- `REPLAY TIMING MISS @ tick` — the recorded release/transport/final-settle timing could not be reproduced; this is not a semantic divergence.
- `REPLAY CONTRACT MISS @ tick` — replay did not satisfy the frozen reproduction contract; this is not a semantic divergence.
- `REPLAY ERROR` — the recording contract, local data binding, worker bootstrap, or replay runtime failed.

`REPLAY MATCH` is scoped to the shared barriers actually observed inside the frozen recording window. It is not a claim of framebuffer/pixel identity, JVM object-graph identity, exact sub-cycle Java instruction timing, or behavior after the recording ends.

## Phase -1D acceptance criteria

- Normal PLAY builds with the recording observer enabled but retains the same underlying input, random, sound, and worker transports.
- A fresh journal is established before the selected game's first normal logical tick and remains local/in-memory only.
- The journal is reset when a new PLAY game starts so sessions cannot be mixed.
- The journal records the exact local game directory used by normal PLAY, and REPLAY PLAY refuses a different selected directory.
- The frozen recording binds `GAMEFILES.DAT`, EditConfig v1, and the canonical recording hash.
- Exact encoded AGI key queue values are replayed; DOM keyboard mapping is not reimplemented by certification.
- Recorded transport writes are replayed at their captured logical tick; idle writes require a settled same-tick boundary, while busy provenance is injected at a deterministic tick boundary without requiring the replay worker to remain busy in wall-clock time.
- All five pinned bounded AGI runtime RNG call sites are wrapped and build-time verified; exact captured values are supplied to both certification lanes with bound validation.
- Recorded sound completion flags are replayed at recorded logical ticks.
- Recorded interpreter cycle-release decisions are the authoritative logical schedule; before release tick `T`, the preceding cycle is settled and compared at `T-1` without advancing logical time.
- A recorded idle-phase event may wait in wall-clock time while logical time stays fixed at that recorded tick; ordinary worker-speed variation does not create a timing miss.
- The final released interpreter cycle is settled and compared without advancing past the recording's final logical tick.
- Both replay lanes must consume exactly the complete recorded RNG stream before `REPLAY MATCH`.
- A reproduction schedule failure is `REPLAY_TIMING_MISS`, not `DIVERGED`.
- A reproduction-contract failure is `REPLAY_CONTRACT_MISS`, not `DIVERGED`.
- EditConfig still mutates only EDITED and only at a common idle boundary.
- The existing Phase -1C no-input smoke run still works when no replay stream is supplied.
- No `GAMEFILES.DAT` or PLAY journal is committed, uploaded by CI, or packaged in the Pages artifact.

## Next step

After Phase -1D is validated in Chromium, the next truth-engine step should use the replay journal as the basis for **automatic minimization and event-focused reproduction**: trim a long PLAY recording to the smallest prefix/window that still reproduces the first divergence while preserving the frozen data/config identities.
