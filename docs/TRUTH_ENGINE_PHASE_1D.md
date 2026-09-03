# Truth Engine — Phase -1D PLAY Record/Replay

Phase -1D extends the merged Phase -1C browser certification bridge with a local, in-memory recording of the **normal PLAY transport** and deterministic replay of that recording through the independent pristine ORIGINAL and current EDITED certification workers.

Phase -1D does not replace `semantic-v1`. It adds a reproducibility contract around the already-frozen comparator so an interactive gameplay window can be rerun rather than stopping at `WAITING FOR INPUT`.

## Recording authority

The recording begins when the page starts, before AGILE launches. It records values **after AGILE has already translated browser input into the transport seen by the normal worker**, rather than trying to reconstruct that translation later from DOM events.

PLAY recording v1 contains:

- the exact key-state writes made to the normal `keysSAB` transport;
- the exact encoded AGI key values added to the normal key-press queue;
- mouse X/Y/button values written into the normal shared variable transport;
- every normal 60 Hz logical pulse and whether that pulse released a new interpreter cycle;
- actual bounded AGI random results as `(bound, value)` pairs in draw order; and
- actual sound end-flag completion events at the logical tick observed by normal PLAY.

The journal is kept only in browser memory. It is not written to OPFS, localStorage, CI, the repository, or a network endpoint. A safety cap prevents an unbounded browser-memory journal; if that cap is reached, replay is refused rather than silently truncating the recording.

## Frozen replay identity

When **REPLAY PLAY** is pressed, the current journal is copied synchronously before any asynchronous hashing or OPFS work. The replay is then bound to:

1. the SHA-256 identity of the selected local `GAMEFILES.DAT` buffer;
2. the frozen Phase -1C `EditConfig v1` hash; and
3. the canonical `kq1agi-play-recording-v1` hash.

The recording must start at logical tick 1. If the page was modified or the journal started late, Phase -1D asks for a reload and a fresh reproduction rather than pretending it can reconstruct the missing prefix.

## Replay semantics

The certification replay host is a Phase -1D subclass of the frozen Phase -1B host. The base host and `semantic-v1` comparator remain unchanged.

For each recorded logical tick, replay:

1. applies all recorded transport events whose logical tick is now visible;
2. applies the frozen EditConfig only to EDITED, and only while both certification lanes are idle;
3. advances the shared AGI clock at a paced logical 60 Hz;
4. releases a new interpreter cycle only when normal PLAY recorded a release at that tick;
5. feeds both certification workers the exact recorded bounded RNG stream; and
6. injects recorded sound completion flags rather than deriving completion timing from WAV duration.

ORIGINAL receives the same recorded gameplay transport but never receives EditConfig. EDITED receives the same gameplay transport plus the frozen EditConfig.

A completed shared barrier is still compared with the Phase -1B trace/digest/event/terminal contract. The first covered semantic mismatch remains `DIVERGED` with the existing category reporting.

## Replay timing miss

Worker scheduling is not silently converted into a gameplay mismatch. If the certification workers cannot reproduce a recorded cycle-release decision at the required logical tick, Phase -1D reports:

`REPLAY_TIMING_MISS`

This means the recorded browser execution schedule was not reproduced closely enough to make the next semantic comparison authoritative. It is **not** reported as an ORIGINAL-vs-EDITED divergence.

Replay ticks are paced at logical 60 Hz for the same reason as the Phase -1C smoke runner: running pulses as fast as the event loop allows would turn worker CPU scheduling into simulated game time.

## Random stream

Normal PLAY still uses the existing `java.util.Random` implementation. Phase -1D adds an observer around the three bounded AGI runtime random call sites; with no observer, the helper delegates directly to the existing `Random.nextInt(bound)`.

During replay, both certification lanes use `CertificationReplayRandom`, which returns the captured `(bound, value)` sequence exactly. Stream exhaustion or a bound mismatch is a replay-contract failure; the runtime does not invent a replacement random value.

The Phase -1C no-input smoke path remains available and continues to use the deterministic seeded `CertificationRandom` path when no replay stream is supplied.

## EditConfig constraint

Phase -1D v1 assumes the editor configuration is stable during the gameplay window being reproduced. The frozen EditConfig is the configuration present when REPLAY PLAY is pressed. Phase -1D v1 does **not** journal historical scene-mask or sprite-pin authoring mutations that happened earlier in that same PLAY window.

For a clean reproduction, finish editing first, reload the page, reproduce the gameplay event without changing editor configuration, and then run REPLAY PLAY.

## Result meanings

- `REPLAY MATCH × N` — the recorded logical window was consumed with the recorded release schedule and no covered semantic divergence across `N` shared barriers.
- `DIVERGED @ tick` — the first covered ORIGINAL-vs-EDITED semantic divergence in the recorded window.
- `REPLAY COMPLETE / MATCH` — both lanes reached the synchronized terminal contract and the final semantic state matched.
- `REPLAY TIMING MISS @ tick` — the recorded cycle-release schedule could not be reproduced; this is not a semantic divergence.
- `REPLAY ERROR` — the recording contract, local data binding, worker bootstrap, or replay runtime failed.

`REPLAY MATCH` is scoped to the shared barriers actually observed inside the frozen recording window. It is not a claim of framebuffer/pixel identity, JVM object-graph identity, or behavior after the recording ends.

## Phase -1D acceptance criteria

- Normal PLAY builds with the recording observer enabled but retains the same underlying input, random, sound, and worker transports.
- The journal starts before the first normal logical tick and remains local/in-memory only.
- The frozen recording binds `GAMEFILES.DAT`, EditConfig v1, and the canonical recording hash.
- Exact encoded AGI key queue values are replayed; DOM keyboard mapping is not reimplemented by certification.
- Exact captured bounded RNG values are supplied to both certification lanes with bound validation.
- Recorded sound completion flags are replayed at recorded logical ticks.
- Recorded interpreter cycle-release decisions are followed at paced logical 60 Hz.
- A reproduction schedule failure is `REPLAY_TIMING_MISS`, not `DIVERGED`.
- EditConfig still mutates only EDITED and only at a common idle boundary.
- The existing Phase -1C no-input smoke run still works when no replay stream is supplied.
- No `GAMEFILES.DAT` or PLAY journal is committed, uploaded by CI, or packaged in the Pages artifact.

## Next step

After Phase -1D is validated in Chromium, the next truth-engine step should use the replay journal as the basis for **automatic minimization and event-focused reproduction**: trim a long PLAY recording to the smallest prefix/window that still reproduces the first divergence while preserving the frozen data/config identities.
