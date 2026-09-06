import assert from 'node:assert/strict';

import {
  canonicalizePlayRecordingV1,
  encodeRandomReplay,
  hashPlayRecordingV1,
} from '../web/certification-recording.mjs';
import { hashCertificationCheckpointV1 } from '../web/certification-host.mjs';
import {
  runMinimizerCheckpointShadowV1,
  selectMinimizerShadowCheckpointBoundaryV1,
  summarizeMinimizerCheckpointShadowV1,
} from '../web/certification-minimizer-checkpoint-shadow.mjs';

async function freezeRecording(overrides = {}) {
  const base = canonicalizePlayRecordingV1({
    schema: 'kq1agi-play-recording-v1',
    completeFromStart: true,
    startTick: 1,
    finalTick: 12,
    gameHash: 'sha256:game',
    gameBytes: 17295,
    editConfigHash: 'sha256:edit',
    overflowed: false,
    releaseTicks: [1,2,3,4,5,6,7,8,9,10,11,12],
    events: [
      { tick: 2, seq: 1, phase: 'idle', type: 'key-state', keyCode: 65, pressed: true },
      { tick: 8, seq: 2, phase: 'idle', type: 'mouse', x: 10, y: 20, button: 0 },
    ],
    random: [
      { tick: 2, seq: 3, bound: 255, value: 7 },
      { tick: 9, seq: 4, bound: 255, value: 11 },
    ],
    ...overrides,
  });
  return Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });
}

async function makeCheckpoint(source) {
  const base = {
    status: 'CHECKPOINT_CAPTURED',
    schema: 'kq1agi-certification-checkpoint-v1',
    context: Object.freeze({
      seed: 1234,
      gameHash: source.gameHash,
      gameBytes: source.gameBytes,
      editConfigHash: source.editConfigHash,
      recordingHash: source.hash,
      randomReplaySpec: encodeRandomReplay(source),
      recordedExternalTiming: true,
    }),
    logicalTick: 5,
    cycle: 5,
    comparedCycle: 5,
    truthTrace: [1,2,3,4],
    editedTrace: [1,2,3,4],
    truthDigest: [1,2,3,4,5,1,2,0],
    editedDigest: [1,2,3,4,5,1,2,0],
    truthTransport: { queue:[0], keys:[0], oldKeys:[0], vars:[1], pixels:[2] },
    editedTransport: { queue:[0], keys:[0], oldKeys:[0], vars:[1], pixels:[2] },
    truthWorkerPayload: [1,2,3],
    editedWorkerPayload: [4,5,6],
    pendingSoundCompletions: [],
  };
  return Object.freeze({ ...base, hash: await hashCertificationCheckpointV1(base) });
}

function evidence(recordingHash) {
  const lane = {
    trace: [1,2,3,4],
    digest: [1,2,3,4,5,2,2,0],
    transport: {
      queue: [0,1],
      keys: [0,1],
      oldKeys: [0,0],
      vars: [1,2,3],
      pixels: [4,5,6],
    },
    workerPayload: [1,2,3,4],
    quit: false,
    error: null,
    soundRequests: [],
  };
  return {
    schema: 'kq1agi-checkpoint-oracle-evidence-v1',
    context: {
      seed: 1234,
      gameHash: 'sha256:game',
      gameBytes: 17295,
      editConfigHash: 'sha256:edit',
      recordingHash,
      randomReplaySpec: 'fixture',
      recordedExternalTiming: true,
    },
    logicalTick: 12,
    cycle: 12,
    comparedCycle: 12,
    truth: structuredClone(lane),
    edited: structuredClone(lane),
    pendingSoundCompletions: [],
    pendingExternalDivergence: null,
  };
}

function matchSummary(overrides = {}) {
  return {
    status: 'REPLAY_MATCH',
    certifiedBarriers: 12,
    consumedTicks: 12,
    replayStartTick: 0,
    skippedPrefixTicks: 0,
    finalTick: 12,
    result: {
      status: 'MATCH',
      tick: 12,
      cycle: 12,
      snapshotEpoch: 99,
    },
    ...overrides,
  };
}

const selection = selectMinimizerShadowCheckpointBoundaryV1({
  releaseTicks: [1, 3, 6, 8, 12],
}, 12);
assert.deepEqual(selection, {
  status: 'MINIMIZER_SHADOW_BOUNDARY_SELECTED',
  targetTick: 12,
  desiredCheckpointTick: 6,
  pauseBeforeTick: 6,
  checkpointTick: 5,
  recordedReleaseCount: 4,
});

assert.equal(
  selectMinimizerShadowCheckpointBoundaryV1({ releaseTicks: [1] }, 1).status,
  'MINIMIZER_SHADOW_NO_BOUNDARY',
);
assert.equal(
  selectMinimizerShadowCheckpointBoundaryV1({ releaseTicks: [1] }, 8).reason,
  'no-recorded-release',
);

const source = await freezeRecording();
const candidate = await freezeRecording({
  events: source.events.filter(event => event.tick <= 5),
});
const checkpoint = await makeCheckpoint(source);

const fullRun = {
  summary: matchSummary(),
  evidence: evidence(candidate.hash),
};
const checkpointRun = {
  summary: matchSummary({
    certifiedBarriers: 7,
    consumedTicks: 7,
    replayStartTick: 5,
    skippedPrefixTicks: 5,
    result: {
      ...matchSummary().result,
      snapshotEpoch: 2,
    },
  }),
  evidence: evidence(candidate.hash),
};

const equivalent = await runMinimizerCheckpointShadowV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async recording => {
    assert.equal(recording.hash, candidate.hash);
    return fullRun;
  },
  runCheckpointReplay: async (recording, reboundCheckpoint, proof) => {
    assert.equal(recording.hash, candidate.hash);
    assert.equal(reboundCheckpoint.context.recordingHash, candidate.hash);
    assert.equal(proof.checkpointTick, 5);
    return checkpointRun;
  },
});
assert.equal(equivalent.oracle.status, 'CHECKPOINT_ORACLE_EQUIVALENT');
assert.equal(equivalent.oracle.savedTicks, 5);
assert.equal(equivalent.summary, fullRun.summary);

const mismatchRun = structuredClone(checkpointRun);
mismatchRun.summary.result.tick = 11;
const mismatch = await runMinimizerCheckpointShadowV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => mismatchRun,
});
assert.equal(mismatch.oracle.status, 'CHECKPOINT_ORACLE_MISMATCH');
assert.equal(mismatch.oracle.reason, 'decision');
assert.equal(mismatch.summary, fullRun.summary);
assert.equal(mismatch.summary.result.tick, 12);

const summary = summarizeMinimizerCheckpointShadowV1([
  equivalent,
  mismatch,
  {
    oracle: {
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'checkpoint-incompatible',
      checkpointAttempted: false,
    },
  },
]);
assert.equal(summary.totalCandidates, 3);
assert.equal(summary.equivalent, 1);
assert.equal(summary.mismatch, 1);
assert.equal(summary.fullOnly, 1);
assert.equal(summary.checkpointAttempts, 2);
assert.equal(summary.trustedCheckpoints, 1);
assert.equal(summary.totalSavedTicks, 5);
assert.equal(summary.averageSavedTicks, 5);
assert.deepEqual(summary.reasons, [
  { reason: 'CHECKPOINT_ORACLE_EQUIVALENT', count: 1 },
  { reason: 'checkpoint-incompatible', count: 1 },
  { reason: 'decision', count: 1 },
]);

console.log('minimizer checkpoint shadow tests: PASS');
