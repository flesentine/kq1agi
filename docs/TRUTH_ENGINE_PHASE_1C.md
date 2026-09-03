# Truth Engine — Phase -1C Browser Certification Bridge

Phase -1C connects the deterministic dual-worker core from Phase -1B to the real browser build without changing normal PLAY or EDIT behavior unless the user explicitly opens **CERTIFY**.

## Scope

Phase -1C does three things:

1. reads the user's already-imported AGI game data from AGILE's same-origin Origin Private File System (OPFS), specifically `Game Files/<game>/GAMEFILES.DAT`;
2. copies that already-encoded buffer into the independent pristine truth worker and current edited worker from Phase -1B; and
3. exposes an opt-in **CERTIFY** panel that reports shared-barrier `MATCH`, first `DIVERGED` tick/category, terminal `COMPLETE`, and trace/digest details.

The commercial King's Quest data remains local to the browser. The browser bridge does not `fetch`, POST, upload, commit, or package `GAMEFILES.DAT`.

## Browser packaging

The normal Pages build remains the playable edited runtime. In addition, the Pages artifact contains a separate `certification/` directory:

- `certification/truth-worker/` — pinned pristine AGILE plus certification instrumentation;
- `certification/edited-worker/` — current KQ1AGI runtime plus the same certification instrumentation;
- `certification/opfs-saved-games.js` — worker bootstrap dependency;
- `certification/certification-host.mjs` — Phase -1B deterministic host;
- `certification/certification-panel.mjs` — Phase -1C local OPFS/UI bridge.

The page loads only the lightweight certification panel/host JavaScript up front. The heavy certification workers and their compiled GWT payloads are not started until the user presses **RUN**.

## Local game discovery

The panel enumerates the browser origin's `Game Files` OPFS directory and lists only subdirectories containing a non-empty `GAMEFILES.DAT`. If more than one AGI game is present, the user can choose which local import to certify.

`GAMEFILES.DAT` is already the `GameFileMapEncoder` representation expected by the certification host, so Phase -1C does not unzip or re-encode commercial data. `CertificationHost.start()` clones the `ArrayBuffer` and transfers one copy to each worker.

## Initial run mode

Phase -1C intentionally begins with a deterministic **no-input smoke run**. The panel advances the two certification lanes through a requested number of shared barriers (60 by default) and stops on the first covered divergence.

The browser runner paces `CertificationHost.pulse()` against a monotonic 60 Hz schedule because one host pulse is one logical 1/60-second game pulse. It deliberately does **not** spin pulses as fast as the browser event loop can run them; otherwise worker CPU scheduling would become simulated game time. If the browser misses a pulse deadline, the schedule re-anchors instead of issuing a burst of catch-up pulses.

If the game enters a long blocking input wait, the panel reports **WAITING FOR INPUT** after a bounded number of logical pulses instead of treating the wait as a mismatch. Automatic capture/replay of the user's real PLAY input is explicitly deferred to the later record/replay phase.

## Results

The panel uses the Phase -1B result contract unchanged:

- `MATCH / semantic-v1` — trace v2, semantic digest v1, random stream, sound events, and terminal parity all agree at the shared barrier;
- `DIVERGED` — the panel stops at the first divergent shared barrier and names the trace slot, digest category, external-event category, or terminal-state mismatch;
- `COMPLETE / semantic-v1` — both workers reached a synchronized terminal barrier and the final semantic state matched;
- `BUSY` — internal running state while one or both workers are still inside the aligned interpreter cycle;
- `NOT_CERTIFIED` — a worker has not produced the required digest.

The panel does not expand Phase -1B's authority claim: framebuffer/pixel identity and byte-for-byte JVM object-graph identity are still outside `semantic-v1`.

## Production safety

Normal PLAY continues to use its existing worker, OPFS game import, OPFS player saves, editor state, sound, and rendering. Certification gets independent SharedArrayBuffers and session-local certification saves. Each completed/stopped certification run terminates only its two certification workers; normal PLAY remains untouched.

## Phase -1C acceptance criteria

- Pages contains both independently compiled certification workers plus the host and panel bridge.
- The panel reads an existing local `GAMEFILES.DAT` without asking for another upload.
- No King's Quest resources are present in the repository or CI artifact.
- A requested no-input run reports progress by shared barrier and stops at the first divergence.
- Browser certification pulses are paced at logical 60 Hz rather than tied to event-loop spin speed.
- A divergence identifies its first observed tick and trace/digest/event category.
- A blocking input wait is reported as waiting, not divergence.
- Normal production PLAY/EDIT continues to build and run when CERTIFY is never opened.
- Node browser-bridge tests and the existing Phase -1B host/core tests are green before Chromium verification.

## Next phase

Record the user's real PLAY keyboard/mouse/event stream with logical timing, then replay that recording through the truth and edited lanes so a surprising gameplay event can be reproduced automatically under certification.
