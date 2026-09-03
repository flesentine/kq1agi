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
    recordingStatus.textContent = `PLAY journal: ticks 1–${stats.finalTick} · ${stats.eventCount} transport event(s) · ${stats.randomCount} RNG draw(s) · ${stats.releaseCount} cycle release(s)`;
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

    // Freeze before any awaits so normal PLAY can continue without changing this window.
    const rawEvents = Array.isArray(globalThis.__kq1agiPlayRecordingRaw)
      ? globalThis.__kq1agiPlayRecordingRaw.map(event => ({ ...event })) : [];
    const overflowed = !!globalThis.__kq1agiPlayRecordingOverflow;

    stopRequested = false;
    setReplayRunning(true);
    setStatus('FREEZING PLAY WINDOW', 'BUSY');
    progress.textContent = 'Preparing Phase -1D replay…';
    detail.textContent = 'Hashing local GAMEFILES.DAT, frozen EditConfig v1, and the in-memory PLAY journal…';

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
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe recorded PLAY window reached tick ${summary.finalTick} with the recorded 60 Hz cycle-release schedule and no covered semantic divergence across ${summary.certifiedBarriers} shared barrier(s).`;
      } else if (summary.status === 'DIVERGED') {
        setStatus(`DIVERGED @ ${summary.firstDivergence.tick}`, 'DIVERGED');
        detail.textContent = `${formatCertificationResult(summary.firstDivergence)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}\n\nThis is the first divergent shared barrier in the recorded PLAY window.`;
      } else if (summary.status === 'COMPLETE') {
        setStatus('REPLAY COMPLETE / MATCH', 'MATCH');
        detail.textContent = `${formatCertificationResult(summary.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
      } else if (summary.status === 'REPLAY_TIMING_MISS') {
        setStatus(`REPLAY TIMING MISS @ ${summary.result.tick}`, 'WAITING');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe certification workers could not reproduce the recorded cycle-release decision at tick ${summary.result.tick}. This is a reproduction/timing failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
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
