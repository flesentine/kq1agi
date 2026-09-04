import { formatCertificationResult, readImportedGame } from './certification-panel.mjs';
import { captureEditConfigV1, createEditConfigApplicator, EditConfigLayout, hashEditConfigV1 } from './certification-edit-config.mjs';
import { minimizeDivergentPrefix } from './certification-minimizer.mjs';
import { groupReplayInputEventsV1, minimizeInputGroupsV1 } from './certification-input-minimizer.mjs';
import { groupEditConfigV1, minimizeEditConfigV1 } from './certification-edit-minimizer.mjs';
import { ReplayCertificationHost } from './certification-replay-host.mjs';
import {
  encodeRandomReplay,
  freezePlayRecordingV1,
  getPlayRecordingStats,
  hashArrayBufferV1,
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

function minimizationFocusText(focus) {
  if (!focus) return 'No focus data.';
  const eventTicks = (focus.events ?? []).map(event => `${event.tick}:${event.type}`).join(', ') || 'none';
  const randomTicks = (focus.random ?? []).map(draw => `${draw.tick}:${draw.bound}→${draw.value}`).join(', ') || 'none';
  const releaseTicks = (focus.releaseTicks ?? []).join(', ') || 'none';
  return [
    `focus ticks ${focus.startTick}–${focus.endTick}`,
    `transport: ${eventTicks}`,
    `RNG: ${randomTicks}`,
    `releases: ${releaseTicks}`,
  ].join('\n');
}

function inputGroupsText(groups, limit = 12) {
  if (!groups?.length) return 'remaining groups: none';
  const shown = groups.slice(0, limit).map(group =>
    `${group.id} ${group.kind} ticks ${group.startTick}–${group.endTick} seq ${group.startSeq}–${group.endSeq}`);
  if (groups.length > limit) shown.push(`… ${groups.length - limit} more group(s)`);
  return ['remaining groups:', ...shown].join('\n');
}

function editGroupsText(groups, limit = 12) {
  if (!groups?.length) return 'remaining edit groups: none';
  const shown = groups.slice(0, limit).map(group => {
    if (group.kind === 'room-config') {
      return `${group.id} room ${group.room} · ${group.maskLayers?.length ?? 0} configured mask layer(s)`;
    }
    return `${group.id} visual pins · ${group.count ?? 0} record(s)`;
  });
  if (groups.length > limit) shown.push(`… ${groups.length - limit} more group(s)`);
  return ['remaining edit groups:', ...shown].join('\n');
}

/**
 * Re-verify the immutable replay identities before Phase -1E derives candidates.
 * The recording hash protects the declared EditConfig hash, but EditConfig's nested
 * arrays are not deep-frozen; hashing the actual config again prevents a later
 * in-memory mutation from being replayed under the old recording identity.
 */
export async function validateFrozenReplayIdentityV1(recording, gameBuffer, editConfig) {
  if (!recording || typeof recording !== 'object') throw new TypeError('A frozen PLAY recording is required.');
  if (!(gameBuffer instanceof ArrayBuffer)) throw new TypeError('A GAMEFILES.DAT ArrayBuffer is required.');

  const expectedGameHash = String(recording.gameHash ?? '');
  const expectedGameBytes = Number(recording.gameBytes);
  const actualGameHash = await hashArrayBufferV1(gameBuffer);
  if (!expectedGameHash
      || !Number.isSafeInteger(expectedGameBytes)
      || expectedGameBytes < 0
      || actualGameHash !== expectedGameHash
      || gameBuffer.byteLength !== expectedGameBytes) {
    throw new Error(`The local GAMEFILES.DAT changed after the divergent replay (expected ${expectedGameHash || 'missing'}/${recording.gameBytes ?? 'missing'} bytes, got ${actualGameHash}/${gameBuffer.byteLength} bytes).`);
  }

  const expectedEditConfigHash = String(recording.editConfigHash ?? '');
  const declaredEditConfigHash = String(editConfig?.hash ?? '');
  const editConfigSchema = String(editConfig?.schema ?? '');
  const actualEditConfigHash = await hashEditConfigV1(editConfig);
  if (!expectedEditConfigHash
      || editConfigSchema !== EditConfigLayout.SCHEMA
      || declaredEditConfigHash !== expectedEditConfigHash
      || actualEditConfigHash !== expectedEditConfigHash) {
    throw new Error(`The frozen EditConfig changed after the divergent replay (recording ${expectedEditConfigHash || 'missing'}, declared ${declaredEditConfigHash || 'missing'}, actual ${actualEditConfigHash}).`);
  }

  return Object.freeze({ gameHash: actualGameHash, editConfigHash: actualEditConfigHash });
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
  } catch {
    return { ready: false, reason: 'no-shared-state', ...base };
  }

  let inTick;
  try {
    inTick = Atomics.load(vars, 517) | 0;
  } catch {
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

  let minimizeButton = document.getElementById('certify-minimize-button');
  if (!minimizeButton) {
    minimizeButton = document.createElement('button');
    minimizeButton.id = 'certify-minimize-button';
    minimizeButton.type = 'button';
    minimizeButton.textContent = 'MINIMIZE';
    minimizeButton.title = 'Shrink the last divergent PLAY replay to the shortest reproducing prefix';
    minimizeButton.disabled = true;
    replayButton.insertAdjacentElement('afterend', minimizeButton);
  }

  let reduceInputsButton = document.getElementById('certify-reduce-inputs-button');
  if (!reduceInputsButton) {
    reduceInputsButton = document.createElement('button');
    reduceInputsButton.id = 'certify-reduce-inputs-button';
    reduceInputsButton.type = 'button';
    reduceInputsButton.textContent = 'REDUCE INPUTS';
    reduceInputsButton.title = 'Remove dependency-safe keyboard/mouse groups while preserving the exact divergence';
    reduceInputsButton.disabled = true;
    minimizeButton.insertAdjacentElement('afterend', reduceInputsButton);
  }

  let reduceEditsButton = document.getElementById('certify-reduce-edits-button');
  if (!reduceEditsButton) {
    reduceEditsButton = document.createElement('button');
    reduceEditsButton.id = 'certify-reduce-edits-button';
    reduceEditsButton.type = 'button';
    reduceEditsButton.textContent = 'REDUCE EDITS';
    reduceEditsButton.title = 'Remove whole room EditConfig groups and visual pins while preserving the exact divergence';
    reduceEditsButton.disabled = true;
    reduceInputsButton.insertAdjacentElement('afterend', reduceEditsButton);
  }

  let replayHost = null;
  let replayRunning = false;
  let stopRequested = false;
  let lastDivergenceContext = null;
  let lastMinimizedContext = null;
  let lastInputReducedContext = null;

  const setStatus = (text, state) => {
    status.textContent = text;
    status.dataset.state = state;
  };

  const invalidateMinimization = () => {
    lastDivergenceContext = null;
    lastMinimizedContext = null;
    lastInputReducedContext = null;
    minimizeButton.disabled = true;
    reduceInputsButton.disabled = true;
    reduceEditsButton.disabled = true;
  };

  const setReplayRunning = value => {
    replayRunning = value;
    replayButton.disabled = value;
    minimizeButton.disabled = value || !lastDivergenceContext;
    reduceInputsButton.disabled = value || !lastMinimizedContext;
    reduceEditsButton.disabled = value || !lastInputReducedContext;
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

  async function runFrozenRecording(recording, gameBuffer, editConfig, options = {}) {
    const truthWorkerUrl = new URL('./truth-worker/worker.nocache.js', import.meta.url).href;
    const editedWorkerUrl = new URL('./edited-worker/worker.nocache.js', import.meta.url).href;
    replayHost?.terminate();
    replayHost = new ReplayCertificationHost({
      truthWorkerUrl,
      editedWorkerUrl,
      randomReplaySpec: encodeRandomReplay(recording),
      recordedExternalTiming: true,
    });
    try {
      await replayHost.start(gameBuffer);
      const applyEditConfig = createEditConfigApplicator(editConfig);
      applyEditConfig(replayHost);
      return await runCertificationReplaySession(replayHost, recording, {
        pulseIntervalMs: options.pulseIntervalMs ?? (1000 / 60),
        beforePulse: () => applyEditConfig(replayHost),
        shouldStop: () => stopRequested,
        onUpdate: options.onUpdate ?? (() => {}),
      });
    } finally {
      replayHost?.terminate();
      replayHost = null;
    }
  }

  async function startReplay() {
    if (replayRunning || runButton.disabled) return;
    invalidateMinimization();
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
      const gameBuffer = await readImportedGame(directoryName);
      const editConfig = await captureEditConfigV1();
      const recording = await freezePlayRecordingV1({ gameBuffer, editConfig, rawEvents, overflowed });

      setStatus('REPLAYING PLAY', 'BUSY');
      detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nORIGINAL receives the recorded PLAY transport unchanged. Frozen EditConfig applies only to EDITED.`;
      const summary = await runFrozenRecording(recording, gameBuffer, editConfig, {
        pulseIntervalMs: 1000 / 60,
        onUpdate: update => {
          progress.textContent = `replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${recording.finalTick} · ${update.certifiedBarriers} certified barrier(s)`;
          if (update.result?.status === 'MATCH' || update.result?.status === 'DIVERGED') {
            detail.textContent = `${formatCertificationResult(update.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
          }
        },
      });

      if (summary.status === 'REPLAY_MATCH') {
        setStatus(`REPLAY MATCH × ${summary.certifiedBarriers}`, 'MATCH');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe recorded PLAY window reached tick ${summary.finalTick}, settled its final in-flight cycle at that same logical tick, consumed the complete recorded RNG stream, and found no covered semantic divergence across ${summary.certifiedBarriers} shared barrier(s).`;
      } else if (summary.status === 'DIVERGED') {
        lastDivergenceContext = Object.freeze({ directoryName, recording, editConfig, firstDivergence: summary.firstDivergence });
        minimizeButton.disabled = false;
        setStatus(`DIVERGED @ ${summary.firstDivergence.tick}`, 'DIVERGED');
        detail.textContent = `${formatCertificationResult(summary.firstDivergence)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}\n\nThis is the first divergent shared barrier in the recorded PLAY window. MINIMIZE can now search for the shortest from-start prefix that reproduces this exact mismatch.`;
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
      invalidateMinimization();
      setStatus('REPLAY ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startMinimize() {
    if (replayRunning || !lastDivergenceContext) return;
    lastMinimizedContext = null;
    lastInputReducedContext = null;
    reduceInputsButton.disabled = true;
    reduceEditsButton.disabled = true;
    const context = lastDivergenceContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('MINIMIZE GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after the divergent replay. Replay the intended game again before minimizing.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    setStatus('MINIMIZING', 'BUSY');
    progress.textContent = `target divergence tick ${context.firstDivergence.tick}`;
    detail.textContent = `recording=${recordingIdentity(context.recording)}\neditConfig=${editConfigIdentity(context.editConfig)}\n\nSearching only hash-valid prefixes that start at logical tick 1 and reproduce the exact same first divergence.`;

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);

      const replayCandidate = async candidate => {
        attemptNumber += 1;
        return runFrozenRecording(candidate, gameBuffer, context.editConfig, {
          pulseIntervalMs: 0,
          onUpdate: update => {
            progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${candidate.finalTick} · replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}`;
          },
        });
      };

      const minimized = await minimizeDivergentPrefix(
        context.recording,
        context.firstDivergence,
        replayCandidate,
        {
          focusRadius: 60,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${attempt.finalTick} · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );

      if (minimized.status === 'MINIMIZED') {
        lastMinimizedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: minimized.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        reduceInputsButton.disabled = false;
        setStatus(`MINIMIZED TO ${minimized.minimizedFinalTick}`, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `recording=${recordingIdentity(context.recording)}`,
          `minimized=${recordingIdentity(minimized.recording)}`,
          `removedTicks=${minimized.removedTicks}`,
          `attempts=${minimized.attempts.length}`,
          '',
          minimizationFocusText(minimized.focus),
          '',
          'The focused window is diagnostic context only; authoritative replay still starts at logical tick 1.',
        ].join('\n');
      } else if (minimized.status === 'NOT_REPRODUCED') {
        setStatus('MINIMIZE NOT REPRODUCED', 'WAITING');
        detail.textContent = `The frozen source no longer reproduced the exact target divergence. No reduced recording was accepted.\nrecording=${recordingIdentity(context.recording)}\nattempts=${minimized.attempts.length}`;
      } else if (minimized.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(minimized.status, 'ERROR');
        detail.textContent = JSON.stringify(minimized, null, 2);
      }
    } catch (error) {
      setStatus('MINIMIZE ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startReduceInputs() {
    if (replayRunning || !lastMinimizedContext) return;
    lastInputReducedContext = null;
    reduceEditsButton.disabled = true;
    const context = lastMinimizedContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('INPUT GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after prefix minimization. Replay and minimize the intended game again before reducing inputs.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    const groups = groupReplayInputEventsV1(context.recording);
    setStatus('REDUCING INPUTS', 'BUSY');
    progress.textContent = `${groups.length} dependency-safe input group(s) · target tick ${context.firstDivergence.tick}`;
    detail.textContent = [
      `recording=${recordingIdentity(context.recording)}`,
      `editConfig=${editConfigIdentity(context.editConfig)}`,
      '',
      'Keeping release timing, RNG draws, sound completions, game identity, EditConfig identity, and final tick frozen while delta-debugging keyboard/mouse groups.',
    ].join('\n');

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);

      const replayCandidate = async candidate => {
        attemptNumber += 1;
        return runFrozenRecording(candidate, gameBuffer, context.editConfig, {
          pulseIntervalMs: 0,
          onUpdate: update => {
            progress.textContent = `input attempt ${attemptNumber} · replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidate.finalTick}`;
          },
        });
      };

      const reduced = await minimizeInputGroupsV1(
        context.recording,
        context.firstDivergence,
        replayCandidate,
        {
          maxAttempts: 256,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `input attempt ${attempt.number} · kept ${attempt.keptGroups}/${groups.length} group(s) · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );

      if (reduced.status === 'INPUTS_MINIMIZED' || reduced.status === 'INPUTS_ALREADY_MINIMAL') {
        const label = reduced.status === 'INPUTS_MINIMIZED'
          ? `INPUTS ${reduced.keptGroups.length}/${reduced.totalGroups}`
          : 'INPUTS ALREADY MINIMAL';
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        reduceEditsButton.disabled = false;
        setStatus(label, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `source=${recordingIdentity(context.recording)}`,
          `reduced=${recordingIdentity(reduced.recording)}`,
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `input events=${reduced.totalInputEvents} → ${reduced.keptInputEvents}`,
          `locked events retained=${reduced.lockedEvents}`,
          `attempts=${reduced.attempts.length}`,
          '',
          inputGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'NO_REMOVABLE_INPUTS') {
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        reduceEditsButton.disabled = false;
        setStatus('NO REMOVABLE INPUTS', 'MATCH');
        detail.textContent = `The minimized prefix contains no dependency-safe keyboard/mouse groups. ${reduced.lockedEvents} locked reproduction event(s) remain. REDUCE EDITS can now minimize the frozen EditConfig.`;
      } else if (reduced.status === 'NOT_REPRODUCED') {
        setStatus('INPUT TARGET NOT REPRODUCED', 'WAITING');
        detail.textContent = `The Phase -1E source no longer reproduced the exact target divergence. No input reduction was accepted.\nattempts=${reduced.attempts.length}`;
      } else if (reduced.status === 'PARTIAL') {
        setStatus(`INPUTS PARTIAL ${reduced.keptGroups.length}/${reduced.totalGroups}`, 'WAITING');
        detail.textContent = [
          'The input attempt budget ended before 1-minimality was proven.',
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `input events=${reduced.totalInputEvents} → ${reduced.keptInputEvents}`,
          `attempts=${reduced.attempts.length}`,
          '',
          inputGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(reduced.status, 'ERROR');
        detail.textContent = JSON.stringify(reduced, null, 2);
      }
    } catch (error) {
      setStatus('INPUT REDUCTION ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startReduceEdits() {
    if (replayRunning || !lastInputReducedContext) return;
    const context = lastInputReducedContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('EDIT GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after input minimization. Replay the intended game and repeat the reduction pipeline before reducing edits.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    let groups = [];
    setStatus('REDUCING EDITS', 'BUSY');
    progress.textContent = 'Verifying frozen EditConfig identity…';
    detail.textContent = [
      `recording=${recordingIdentity(context.recording)}`,
      `editConfig=${editConfigIdentity(context.editConfig)}`,
      '',
      'Keeping GAMEFILES.DAT, minimized ticks, input transport, RNG draws, sound completions, and exact divergence frozen while delta-debugging whole room configs and the visual-pin set.',
    ].join('\n');

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);
      groups = groupEditConfigV1(context.editConfig);
      progress.textContent = `${groups.length} dependency-safe EditConfig group(s) · target tick ${context.firstDivergence.tick}`;

      const replayCandidate = async (candidateRecording, candidateConfig) => {
        attemptNumber += 1;
        await validateFrozenReplayIdentityV1(candidateRecording, gameBuffer, candidateConfig);
        return runFrozenRecording(candidateRecording, gameBuffer, candidateConfig, {
          pulseIntervalMs: 0,
          onUpdate: update => {
            progress.textContent = `edit attempt ${attemptNumber} · replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidateRecording.finalTick}`;
          },
        });
      };

      const reduced = await minimizeEditConfigV1(
        context.recording,
        context.editConfig,
        context.firstDivergence,
        replayCandidate,
        {
          maxAttempts: 128,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `edit attempt ${attempt.number} · kept ${attempt.keptGroups}/${groups.length} group(s) · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );

      if (reduced.status === 'EDITS_MINIMIZED' || reduced.status === 'EDITS_ALREADY_MINIMAL') {
        const label = reduced.status === 'EDITS_MINIMIZED'
          ? `EDITS ${reduced.keptGroups.length}/${reduced.totalGroups}`
          : 'EDITS ALREADY MINIMAL';
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: reduced.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        setStatus(label, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `source recording=${recordingIdentity(context.recording)}`,
          `rebound recording=${recordingIdentity(reduced.recording)}`,
          `source EditConfig=${editConfigIdentity(context.editConfig)}`,
          `reduced EditConfig=${editConfigIdentity(reduced.editConfig)}`,
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `room configs=${reduced.totalRoomGroups} → ${reduced.keptRoomGroups}`,
          `visual pins=${reduced.totalVisualPins} → ${reduced.keptVisualPins}`,
          `attempts=${reduced.attempts.length}`,
          '',
          editGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'NO_REMOVABLE_EDITS') {
        setStatus('NO REMOVABLE EDITS', 'MATCH');
        detail.textContent = 'The current minimized reproduction has no configured rooms or visual pins to remove.';
      } else if (reduced.status === 'NOT_REPRODUCED') {
        setStatus('EDIT TARGET NOT REPRODUCED', 'WAITING');
        detail.textContent = `The Phase -1F source no longer reproduced the exact target divergence. No EditConfig reduction was accepted.\nattempts=${reduced.attempts.length}`;
      } else if (reduced.status === 'PARTIAL') {
        setStatus(`EDITS PARTIAL ${reduced.keptGroups.length}/${reduced.totalGroups}`, 'WAITING');
        detail.textContent = [
          'The EditConfig attempt budget ended before 1-minimality was proven.',
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `room configs=${reduced.totalRoomGroups} → ${reduced.keptRoomGroups}`,
          `visual pins=${reduced.totalVisualPins} → ${reduced.keptVisualPins}`,
          `attempts=${reduced.attempts.length}`,
          '',
          editGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(reduced.status, 'ERROR');
        detail.textContent = JSON.stringify(reduced, null, 2);
      }
    } catch (error) {
      setStatus('EDIT REDUCTION ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  replayButton.addEventListener('click', startReplay);
  minimizeButton.addEventListener('click', startMinimize);
  reduceInputsButton.addEventListener('click', startReduceInputs);
  reduceEditsButton.addEventListener('click', startReduceEdits);
  gameSelect.addEventListener('change', invalidateMinimization);
  runButton.addEventListener('click', invalidateMinimization, { capture: true });
  stopButton.addEventListener('click', () => {
    if (!replayRunning) return;
    stopRequested = true;
    setStatus('STOPPING…', 'BUSY');
  });
  window.addEventListener('beforeunload', () => replayHost?.terminate());
  setInterval(() => {
    if (!replayRunning && panel.getAttribute('aria-hidden') === 'false') refreshJournal();
  }, 1000);
  refreshJournal();
}

if (typeof document !== 'undefined') installPhase1D();
