import { formatCertificationResult, readImportedGame } from './certification-panel.mjs';
import { captureEditConfigV1, createEditConfigApplicator } from './certification-edit-config.mjs';
import { ReplayCertificationHost } from './certification-replay-host.mjs';
import {
  encodeRandomReplay,
  freezePlayRecordingV1,
  getPlayRecordingStats,
  runCertificationReplaySession,
} from './certification-recording.mjs';

function shortHash(value) {
  const hash = String(value ?? 'none');
  return hash.startsWith('sha256:') ? `sha256:${hash.slice(7, 19)}` : hash;
}

function editConfigIdentity(config) {
  return `${shortHash(config?.hash)} · ${config?.rooms?.length ?? 0} room(s) · ${config?.visualPins?.length ?? 0} visual pin(s)`;
}

function recordingIdentity(recording) {
  return `${shortHash(recording?.hash)} · ticks 1–${recording?.finalTick ?? 0} · ${recording?.events?.length ?? 0} transport event(s) · ${recording?.random?.length ?? 0} RNG draw(s)`;
}

/**
 * Freeze only at a normal-PLAY worker completion boundary. RecordingRandomDraw and
 * RecordingCycleComplete are FIFO messages from the same worker, so seeing the
 * completion marker for the most recent released cycle means every RNG observation
 * from that cycle has reached the UI journal before we copy it.
 */
export function snapshotReadyPlayJournal(options = {}) {
  const source = options.rawEvents ?? globalThis.__kq1agiPlayRecordingRaw;
  const variableSAB = options.variableSAB ?? globalThis.__kq1agiVariableSAB ?? null;
  const lastCompletedTick = Number(options.lastCompletedTick ?? globalThis.__kq1agiPlayLastCompletedTick ?? 0) | 0;
  const gameDirectory = String(options.gameDirectory ?? globalThis.__kq1agiPlayGameDirectory ?? '');
  const overflowed = options.overflowed ?? !!globalThis.__kq1agiPlayRecordingOverflow;
  const base = { gameDirectory, lastCompletedTick, lastReleaseTick: 0 };
  if (!Array.isArray(source)) return { ready: false, reason: 'no-journal', ...base };
  if (!variableSAB) return { ready: false, reason: 'no-shared-state', ...base };
  if (!gameDirectory) return { ready: false, reason: 'no-game-identity', ...base };

  let vars;
  try {
    vars = new Int32Array(variableSAB);
    if (vars.length <= 517) throw new Error('short shared variable buffer');
  } catch (error) {
    return { ready: false, reason: 'no-shared-state', ...base };
  }

  let inTick;
  try {
    inTick = Atomics.load(vars, 517) | 0;
  } catch (error) {
    return { ready: false, reason: 'no-shared-state', ...base };
  }

  let lastReleaseTick = 0;
  for (const event of source) {
    if (event?.type === 'pulse' && event.released) lastReleaseTick = Math.max(lastReleaseTick, Number(event.tick) | 0);
  }
  if (lastReleaseTick < 1) return { ready: false, reason: 'no-cycle-release', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  if (inTick !== 0) return { ready: false, reason: 'worker-busy', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  if (lastCompletedTick !== lastReleaseTick) {
    return { ready: false, reason: 'worker-events-pending', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  }
  return {
    ready: true,
    reason: 'complete',
    gameDirectory,
    inTick,
    lastCompletedTick,
    lastReleaseTick,
    overflowed: !!overflowed,
    rawEvents: source.map(event => ({ ...event })),
  };
}

function boundaryMessage(boundary) {
  if (boundary.reason === 'worker-busy') return 'Normal PLAY is still inside its current interpreter cycle. Try REPLAY PLAY again when the worker is idle.';
  if (boundary.reason === 'worker-events-pending') return `Normal PLAY finished its shared cycle, but its worker observations have not all reached the journal yet (last release ${boundary.lastReleaseTick}, confirmed complete ${boundary.lastCompletedTick}). Try REPLAY PLAY again.`;
  if (boundary.reason === 'no-cycle-release') return 'Normal PLAY has not completed its first interpreter cycle yet.';
  if (boundary.reason === 'no-game-identity') return 'Phase -1D could not identify the game currently running in normal PLAY. Reload before reproducing the event again.';
  return 'The normal PLAY shared state is not ready for an authoritative replay snapshot yet.';
}

function contractMissText(summary, recording, editConfig) {
  const result = summary.result ?? {};
  const identity = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}`;
  if (result.reason === 'random-stream-consumption') {
    return `${identity}\n\nThe replay did not consume the complete recorded RNG stream (expected ${result.expectedRandomDraws}, ORIGINAL ${result.truthRandomDraws}, EDITED ${result.editedRandomDraws}). This is a reproduction-contract failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
  }
  return `${identity}\n\nThe frozen PLAY transport contract could not be reproduced (${result.reason ?? 'unknown-contract'} at logical tick ${result.tick ?? '?'}). This is a reproduction-contract failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
}

function installPhase1D() {
  const panel = document.getElementById('certify-panel');
  const replayButton = document.getElementById('certify-replay-button');
  const recordingStatus = document.getElementById('certify-recording');
  const runButton = document.getElementById('certify-run-button');
  const refreshButton = document.getElementById('certify-refresh-button');
  const stopButton = document.getElementById('certify-stop-button');
  const gameSelect = document.getElementById('certify-game-select');
  const barrierInput = document.getElementById('certify-barrier-count');
  const status = document.getElementById('certify-status');
  const progress = document.getElementById('certify-progress');
  const detail = document.getElementById('certify-detail');
  if (!panel || !replayButton || !recordingStatus || !runButton || !stopButton || !gameSelect || !status || !progress || !detail) return;

  let replayHost = null;
  let replayRunning = false;
  let stopRequested = false;

  const setStatus = (text, state) => {
    status.textContent = text;
    status.dataset.state = state;
  };

  const setReplayRunning = value => {
    replayRunning = value;
    replayButton.disabled = value;
    runButton.disabled = value;
    if (refreshButton) refreshButton.disabled = value;
    gameSelect.disabled = value;
    if (barrierInput) barrierInput.disabled = value;
    stopButton.disabled = !value;
  };

  function refreshJournal() {
    const stats = getPlayRecordingStats();
    if (stats.overflowed) {
      recordingStatus.textContent = 'PLAY journal reached its safety limit · reload before reproducing again';
      return;
    }
    if (!stats.rawCount) {
      recordingStatus.textContent = 'PLAY journal: waiting for the first logical tick…';
      return;
    }
    if (!stats.completeFromStart) {
      recordingStatus.textContent = `PLAY journal started at tick ${stats.startTick || '?'} · reload required for replay from game start`;
      return;
    }
    const boundary = snapshotReadyPlayJournal();
    const game = boundary.gameDirectory ? ` · game ${boundary.gameDirectory}` : '';
    const suffix = boundary.ready ? ' · replay boundary ready' : ' · waiting for worker boundary';
    recordingStatus.textContent = `PLAY journal: ticks 1–${stats.finalTick} · ${stats.eventCount} transport event(s) · ${stats.randomCount} RNG draw(s) · ${stats.releaseCount} cycle release(s)${game}${suffix}`;
  }

  async function startReplay() {
    if (replayRunning || runButton.disabled) return;
    if (!window.crossOriginIsolated) {
      setStatus('NOT ISOLATED', 'ERROR');
      detail.textContent = 'REPLAY PLAY requires the same cross-origin isolation used by the AGILE SharedArrayBuffer runtime.';
      return;
    }
    const directoryName = gameSelect.value;
    if (!directoryName) {
      setStatus('NO LOCAL GAME', 'ERROR');
      return;
    }

    // This check and copy are synchronous. The browser cannot run the next normal
    // 60 Hz callback between the boundary validation and the raw journal snapshot.
    const boundary = snapshotReadyPlayJournal();
    if (!boundary.ready) {
      setStatus('WAIT FOR PLAY IDLE', 'WAITING');
      detail.textContent = boundaryMessage(boundary);
      refreshJournal();
      return;
    }
    if (boundary.gameDirectory !== directoryName) {
      setStatus('PLAY GAME MISMATCH', 'ERROR');
      detail.textContent = `The frozen PLAY journal belongs to local game "${boundary.gameDirectory}", but CERTIFY currently selects "${directoryName}". Select the same imported game before replaying.`;
      return;
    }
    const rawEvents = boundary.rawEvents;
    const overflowed = boundary.overflowed;

    stopRequested = false;
    setReplayRunning(true);
    setStatus('FREEZING PLAY WINDOW', 'BUSY');
    progress.textContent = 'Preparing Phase -1D replay…';
    detail.textContent = `Normal PLAY boundary confirmed for ${boundary.gameDirectory} at released cycle tick ${boundary.lastReleaseTick}. Hashing local GAMEFILES.DAT, frozen EditConfig v1, and the in-memory PLAY journal…`;

    try {
      replayHost?.terminate();
      replayHost = null;
      const gameBuffer = await readImportedGame(directoryName);
      const editConfig = await captureEditConfigV1();
      const recording = await freezePlayRecordingV1({ gameBuffer, editConfig, rawEvents, overflowed });
      const truthWorkerUrl = new URL('./truth-worker/worker.nocache.js', import.meta.url).href;
      const editedWorkerUrl = new URL('./edited-worker/worker.nocache.js', import.meta.url).href;
      replayHost = new ReplayCertificationHost({
        truthWorkerUrl,
        editedWorkerUrl,
        randomReplaySpec: encodeRandomReplay(recording),
        recordedExternalTiming: true,
      });
      await replayHost.start(gameBuffer);
      const applyEditConfig = createEditConfigApplicator(editConfig);
      applyEditConfig(replayHost);

      setStatus('REPLAYING PLAY', 'BUSY');
      detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nORIGINAL receives the recorded PLAY transport unchanged. Frozen EditConfig applies only to EDITED.`;
      const summary = await runCertificationReplaySession(replayHost, recording, {
        pulseIntervalMs: 1000 / 60,
        beforePulse: () => applyEditConfig(replayHost),
        shouldStop: () => stopRequested,
        onUpdate: update => {
          progress.textContent = `replay tick ${replayHost.logicalTick}/${recording.finalTick} · ${update.certifiedBarriers} certified barrier(s)`;
          if (update.result?.status === 'MATCH' || update.result?.status === 'DIVERGED') {
            detail.textContent = `${formatCertificationResult(update.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
          }
        },
      });

      if (summary.status === 'REPLAY_MATCH') {
        setStatus(`REPLAY MATCH × ${summary.certifiedBarriers}`, 'MATCH');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe recorded PLAY window reached tick ${summary.finalTick}, settled its final in-flight cycle at that same logical tick, consumed the complete recorded RNG stream, and found no covered semantic divergence across ${summary.certifiedBarriers} shared barrier(s).`;
      } else if (summary.status === 'DIVERGED') {
        setStatus(`DIVERGED @ ${summary.firstDivergence.tick}`, 'DIVERGED');
        detail.textContent = `${formatCertificationResult(summary.firstDivergence)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}\n\nThis is the first divergent shared barrier in the recorded PLAY window.`;
      } else if (summary.status === 'COMPLETE') {
        setStatus('REPLAY COMPLETE / MATCH', 'MATCH');
        detail.textContent = `${formatCertificationResult(summary.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
      } else if (summary.status === 'REPLAY_TIMING_MISS') {
        setStatus(`REPLAY TIMING MISS @ ${summary.result.tick}`, 'WAITING');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe certification workers could not reproduce recorded timing (${summary.result.reason ?? 'timing'} at tick ${summary.result.tick}). This is a reproduction failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
      } else if (summary.status === 'REPLAY_CONTRACT_MISS') {
        setStatus(`REPLAY CONTRACT MISS @ ${summary.result.tick}`, 'WAITING');
        detail.textContent = contractMissText(summary, recording, editConfig);
      } else if (summary.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(summary.status, 'ERROR');
        detail.textContent = `${formatCertificationResult(summary.result)}\nrecording=${recordingIdentity(recording)}`;
      }
    } catch (error) {
      setStatus('REPLAY ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  replayButton.addEventListener('click', startReplay);
  stopButton.addEventListener('click', () => {
    if (!replayRunning) return;
    stopRequested = true;
    setStatus('STOPPING REPLAY…', 'BUSY');
  });
  window.addEventListener('beforeunload', () => replayHost?.terminate());
  setInterval(() => {
    if (!replayRunning && panel.getAttribute('aria-hidden') === 'false') refreshJournal();
  }, 1000);
  refreshJournal();
}

if (typeof document !== 'undefined') installPhase1D();
