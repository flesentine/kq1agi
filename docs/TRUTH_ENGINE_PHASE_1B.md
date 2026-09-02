# Truth Engine — Phase -1B Deterministic Certification Core

Phase -1B turns the Phase -1A feasibility spike into an executable dual-engine certification core. It is deliberately **opt-in and separate from production PLAY**: the normal GitHub Pages game/editor does not load the certification host or either certification-instrumented worker.

## What is built

The certification artifact contains two independently compiled AGILE worker bundles and one host:

- **truth worker** — exact pinned upstream AGILE (`81c42ba63b3b7f5fb260d282592681c097d46da9`) plus only the read-only trace and deterministic certification instrumentation;
- **edited worker** — the current KQ1AGI AGILE patch chain plus the same certification instrumentation;
- **`certification-host.mjs`** — creates isolated memory for both lanes, supplies the same input/events/time, releases aligned interpreter cycles, and compares their state.

No KQ1 game resources are committed to the repository or uploaded by this workflow. The host accepts an already encoded AGI game-file `ArrayBuffer`; wiring that to the user's locally imported KQ1 data is the next browser-integration step.

## Deterministic clock

The certification host owns one logical 60 Hz clock. Every pulse advances `TOTAL_TICKS` in both variable stores. Every 60th pulse advances `SECONDS`, and carries through `MINUTES`, `HOURS`, and `DAYS` exactly like `AgileRunner.tick()`.

Critically, logical time continues advancing while an interpreter worker remains inside a blocking tick. AGILE normally advances its UI-side clock even when the worker is waiting in a menu, text window, input wait, or timeout. Freezing the certification clock until a worker returned would therefore be incorrect and could deadlock time-based waits.

A new interpreter cycle is released only when **both** lanes are idle. This keeps interpreter cycle boundaries aligned while still allowing time to move forward during a long/blocking cycle.

## Independent memory and mirrored input

Each lane receives its own:

- key-press queue SharedArrayBuffer;
- current/old key arrays;
- AGI variable/flag/mouse/tick storage;
- pixel buffer;
- trace buffer;
- semantic digest buffer.

Keyboard state, queued encoded key presses, and mouse state are mirrored into both lanes. A queued key is written only if **both** queues have capacity, so one lane cannot accept an event the other failed to receive.

## Deterministic random stream

Certification mode replaces `GameState.random` before the first interpreter tick with `CertificationRandom`, a seeded `java.util.Random` subclass. Both lanes receive the same seed.

The wrapper counts underlying PRNG draws. The comparator therefore catches not only different semantic state but also a different number of random draws, which is an early signal that the two execution paths have diverged even if later visible state happens to coincide temporarily.

Normal non-certification gameplay still uses AGILE's normal unseeded `Random`.

## Deterministic sound completion

The worker still produces the same `PlaySound` / `StopSound` requests. The certification host does **not** depend on real browser audio timing.

For matching `PlaySound` requests, it reads the generated WAV duration and schedules the AGI sound end flag on the same logical tick in both lanes. Starting a replacement sound or stopping sound cancels the previous scheduled completion, matching the browser runner's single-current-sound behavior.

If the two lanes request different sounds/end flags/durations or only one lane emits a sound event at a shared barrier, certification reports `DIVERGED`.

## Saved-game isolation

Certification workers use `CertificationSavedGameStore`, a session-local in-memory store. It supports deterministic save/restore behavior inside the certification session but never touches OPFS and therefore cannot read, overwrite, or race the player's real browser saves.

## Trace v2 and semantic digest v1

Trace v2 remains the human-readable diagnostic surface from Phase -1A: room, Graham position, direction, water/hitspec/edge state, view/loop/cel, priority, control mode, and AGI clock.

Semantic digest v1 adds four deterministic state partitions:

1. all 256 AGI variables, all 256 flags, controllers, core GameState scalar/input state;
2. semantic fields for every AnimatedObject;
3. scan starts, loaded resource state, inventory objects, and script-buffer contents;
4. AGI strings, recognised words, and controller-key mappings.

The digest also publishes the PRNG draw count.

The host compares the readable trace first, then semantic digest v1. Results are:

- **`DIVERGED`** — a trace, semantic digest, PRNG stream, external event, or quit-state mismatch is observed;
- **`MATCH` / `scope: semantic-v1`** — both lanes are at the same shared barrier and every field covered by trace v2 + semantic digest v1 + PRNG/event parity agrees;
- **`BUSY`** — one or both workers are still inside the aligned interpreter cycle while logical time continues;
- **`NOT_CERTIFIED`** — a worker has not yet published the semantic digest.

`MATCH` is intentionally scoped. Phase -1B does **not** claim framebuffer/pixel identity, browser rendering identity, or byte-for-byte equality of every Java object. Those can be added as additional certification scopes later without weakening the semantic runtime contract.

## Production safety

Phase -1B is built by a separate certification workflow. It does not patch the production Pages artifact and does not change the user's normal EDIT/PLAY behavior. This lets the certification engine mature behind CI before it is exposed in the editor UI.

## Next browser integration

Once this core is green, the next step is small and explicit:

1. reuse the user's locally imported KQ1 game data;
2. encode/copy it into the two certification workers without uploading it;
3. add an opt-in **CERTIFY** panel showing `MATCH`, `DIVERGED`, first divergent tick, trace details, and digest category;
4. later record/replay user input so a surprising PLAY event can be replayed through truth vs edited automatically.
