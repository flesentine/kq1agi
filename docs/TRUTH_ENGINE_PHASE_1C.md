# Truth Engine — Phase -1C Browser Certification Bridge

Phase -1C connects the deterministic dual-worker core from Phase -1B to the real browser build without changing normal PLAY or EDIT behavior unless the user explicitly opens **CERTIFY**.

## Scope

Phase -1C does four things:

1. reads the user's already-imported AGI game data from AGILE's same-origin Origin Private File System (OPFS), specifically `Game Files/<game>/GAMEFILES.DAT`;
2. copies that already-encoded buffer into the independent pristine truth worker and current edited worker from Phase -1B;
3. freezes the current browser editor state as **EditConfig v1** and applies it only to the edited certification lane; and
4. exposes an opt-in **CERTIFY** panel that reports shared-barrier `MATCH`, first `DIVERGED` tick/category, terminal `COMPLETE`, trace/digest details, and the EditConfig identity used by the run.

The commercial King's Quest data remains local to the browser. The browser bridge does not `fetch`, POST, upload, commit, or package `GAMEFILES.DAT`.

## Browser packaging

The normal Pages build remains the playable edited runtime. In addition, the Pages artifact contains a separate `certification/` directory:

- `certification/truth-worker/` — pinned pristine AGILE plus certification instrumentation;
- `certification/edited-worker/` — current KQ1AGI runtime plus the same certification instrumentation;
- `certification/opfs-saved-games.js` — worker bootstrap dependency;
- `certification/certification-host.mjs` — Phase -1B deterministic host;
- `certification/certification-panel.mjs` — Phase -1C local OPFS/UI bridge;
- `certification/certification-edit-config.mjs` — EditConfig v1 capture/hash/apply bridge.

The page loads only the lightweight certification JavaScript up front. The heavy certification workers and their compiled GWT payloads are not started until the user presses **RUN**.

## Local game discovery

The panel enumerates the browser origin's `Game Files` OPFS directory and lists only subdirectories containing a non-empty `GAMEFILES.DAT`. If more than one AGI game is present, the user can choose which local import to certify.

`GAMEFILES.DAT` is already the `GameFileMapEncoder` representation expected by the certification host, so Phase -1C does not unzip or re-encode commercial data. `CertificationHost.start()` clones the `ArrayBuffer` and transfers one copy to each worker.

## EditConfig v1

The standalone edited certification worker does not share the production PLAY worker's browser editor memory. Phase -1C therefore freezes the editor configuration at the start of every certification run.

EditConfig v1 collects persisted scene-editor state from the browser's `agi-scene-mask-editor-v3` preferences and overlays the live current-room `__kq1agiVariableSAB` snapshot so unsaved current edits are included. The frozen configuration contains the six current scene planes (front/occluder, collision, behind, water, fall, and scripted-fall), room enable/water/fall authority state, control/script seed state, and persisted visual sprite offsets.

The configuration is canonicalized and identified by a deterministic hash. The CERTIFY panel displays that identity with the run. The configuration is never written to the pristine truth lane: it is copied only into the edited lane after worker bootstrap and again when that lane enters a different room, before its next host pulse. Rooms absent from the frozen configuration run with editor ownership disabled.

This keeps the comparison meaningful: **truth = pristine Sierra behavior; edited = the exact frozen browser edit configuration being tested**.

## Initial run mode

Phase -1C intentionally begins with a deterministic **no-input smoke run**. The panel advances the two certification lanes through a requested number of shared barriers (60 by default) and stops on the first covered divergence.

The browser runner paces `CertificationHost.pulse()` against a monotonic 60 Hz schedule because one host pulse is one logical 1/60-second game pulse. It deliberately does **not** spin pulses as fast as the browser event loop can run them; otherwise worker CPU scheduling would become simulated game time. If the browser misses a pulse deadline, the schedule re-anchors instead of issuing a burst of catch-up pulses.

If the game enters a long blocking input wait, the panel reports **WAITING FOR INPUT** after a bounded number of logical pulses instead of treating the wait as a mismatch. Automatic capture/replay of the user's real PLAY input is explicitly deferred to Phase -1D.

## Results

The panel uses the Phase -1B result contract unchanged:

- `MATCH / semantic-v1` — trace v2, semantic digest v1, random stream, sound events, and terminal parity all agree at the shared barrier;
- `DIVERGED` — the panel stops at the first divergent shared barrier and names the trace slot, digest category, external-event category, or terminal-state mismatch;
- `COMPLETE / semantic-v1` — both workers reached a synchronized terminal barrier and the final semantic state matched;
- `BUSY` — internal running state while one or both workers are still inside the aligned interpreter cycle;
- `NOT_CERTIFIED` — a worker has not produced the required digest.

The panel does not expand Phase -1B's authority claim: framebuffer/pixel identity and byte-for-byte JVM object-graph identity are still outside `semantic-v1`.

## Production safety

Normal PLAY continues to use its existing worker, OPFS game import, OPFS player saves, editor state, sound, and rendering. Certification gets independent SharedArrayBuffers and session-local certification saves. EditConfig capture is read-only against production browser state. Each completed/stopped certification run terminates only its two certification workers; normal PLAY remains untouched.

## Phase -1C acceptance criteria

- Pages contains both independently compiled certification workers plus the host, panel, and EditConfig bridge.
- The panel reads an existing local `GAMEFILES.DAT` without asking for another upload.
- EditConfig v1 includes persisted editor state plus unsaved live current-room state, has a deterministic identity, and is applied only to the edited lane.
- No King's Quest resources are present in the repository or CI artifact.
- A requested no-input run reports progress by shared barrier and stops at the first divergence.
- Browser certification pulses are paced at logical 60 Hz rather than tied to event-loop spin speed.
- A divergence identifies its first observed tick and trace/digest/event category.
- A blocking input wait is reported as waiting, not divergence.
- Normal production PLAY/EDIT continues to build and run when CERTIFY is never opened.
- Node browser-bridge/EditConfig tests and the existing Phase -1B host/core tests are green before Chromium verification.

## Next phase — Phase -1D

Record the canonical PLAY session needed to reproduce a real run: AGI-level input transitions/queue entries, logical timing and interpreter cycle releases, relevant external completions, and the production random stream. Bind that journal to the exact `GAMEFILES.DAT` and EditConfig v1 identities, then replay it through the truth and edited lanes so a surprising gameplay event can be reproduced automatically and stopped at the first certified divergence.
