import assert from 'node:assert/strict';

import {
  canonicalizePlayRecordingV1,
  encodeRandomReplay,
  hashPlayRecordingV1,
} from '../web/certification-recording.mjs';
import { hashCertificationCheckpointV1 } from '../web/certification-host.mjs';
import {
  canonicalReplayOracleDecisionV1,
  compareCheckpointOracleRunsV1,
  runCheckpointCandidateOracleV1,
} from '../web/certification-checkpoint-oracle.mjs';

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
    logicalTick: 6,
    cycle: 6,
    comparedCycle: 6,
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

function evidence(overrides = {}) {
  const lane = {
    trace: [1,2,3,4],
    digest: [1,2,3,4,5,1,2,0],
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
    logicalTick: 12,
    cycle: 12,
    comparedCycle: 12,
    truth: structuredClone(lane),
    edited: structuredClone(lane),
    pendingSoundCompletions: [],
    pendingExternalDivergence: null,
    ...overrides,
  };
}

function divergentSummary(overrides = {}) {
  return {
    status: 'DIVERGED',
    certifiedBarriers: 12,
    consumedTicks: 12,
    replayStartTick: 0,
    skippedPrefixTicks: 0,
    result: {
      status: 'DIVERGED',
      tick: 12,
      cycle: 12,
      reason: 'semantic-digest',
      index: 3,
      truth: 10,
      edited: 11,
      snapshotEpoch: 77,
    },
    firstDivergence: {
      status: 'DIVERGED',
      tick: 12,
      cycle: 12,
      reason: 'semantic-digest',
      index: 3,
      truth: 10,
      edited: 11,
      snapshotEpoch: 77,
    },
    ...overrides,
  };
}

const source = await freezeRecording();
const candidate = await freezeRecording({
  events: source.events.filter(event => event.tick <= 6),
});
const checkpoint = await makeCheckpoint(source);

const fullRun = {
  summary: divergentSummary(),
  evidence: evidence(),
};
const acceleratedRun = {
  summary: divergentSummary({
    certifiedBarriers: 6,
    consumedTicks: 6,
    replayStartTick: 6,
    skippedPrefixTicks: 6,
    result: {
      ...divergentSummary().result,
      snapshotEpoch: 2,
    },
    firstDivergence: {
      ...divergentSummary().firstDivergence,
      snapshotEpoch: 2,
    },
  }),
  evidence: evidence(),
};

const canonical = canonicalReplayOracleDecisionV1(acceleratedRun.summary);
assert.equal(canonical.consumedTicks, undefined);
assert.equal(canonical.replayStartTick, undefined);
assert.equal(canonical.result.snapshotEpoch, undefined);

const direct = compareCheckpointOracleRunsV1(fullRun, acceleratedRun);
assert.equal(direct.equivalent, true);
assert.equal(direct.category, 'exact');

let fullCalls = 0;
let checkpointCalls = 0;
const equivalent = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async recording => {
    fullCalls += 1;
    assert.equal(recording.hash, candidate.hash);
    return fullRun;
  },
  runCheckpointReplay: async (recording, reboundCheckpoint, proof) => {
    checkpointCalls += 1;
    assert.equal(recording.hash, candidate.hash);
    assert.equal(reboundCheckpoint.context.recordingHash, candidate.hash);
    assert.equal(proof.checkpointTick, 6);
    return acceleratedRun;
  },
});
assert.equal(equivalent.status, 'CHECKPOINT_ORACLE_EQUIVALENT');
assert.equal(equivalent.checkpointTrusted, true);
assert.equal(equivalent.authoritativeSummary, fullRun.summary);
assert.equal(equivalent.savedTicks, 6);
assert.equal(fullCalls, 1);
assert.equal(checkpointCalls, 1);

// Decision disagreement never replaces the full result.
const decisionMismatch = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => ({
    ...acceleratedRun,
    summary: divergentSummary({
      consumedTicks: 6,
      replayStartTick: 6,
      firstDivergence: {
        ...divergentSummary().firstDivergence,
        tick: 11,
      },
    }),
  }),
});
assert.equal(decisionMismatch.status, 'CHECKPOINT_ORACLE_MISMATCH');
assert.equal(decisionMismatch.reason, 'decision');
assert.equal(decisionMismatch.checkpointTrusted, false);
assert.equal(decisionMismatch.authoritativeSummary, fullRun.summary);

// Exact decision but changed terminal state is still a mismatch.
const evidenceMismatchRun = structuredClone(acceleratedRun);
evidenceMismatchRun.evidence.edited.transport.pixels[1] = 99;
const evidenceMismatch = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => evidenceMismatchRun,
});
assert.equal(evidenceMismatch.status, 'CHECKPOINT_ORACLE_MISMATCH');
assert.equal(evidenceMismatch.reason, 'evidence');
assert.match(evidenceMismatch.comparison.difference.path, /^\$\.evidence/);

// Prefix-incompatible candidates run only the full oracle.
const prefixChanged = await freezeRecording({
  events: source.events.filter(event => event.seq !== 1),
});
let incompatibleCheckpointCalls = 0;
const incompatible = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: prefixChanged,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => {
    incompatibleCheckpointCalls += 1;
    return acceleratedRun;
  },
});
assert.equal(incompatible.status, 'CHECKPOINT_ORACLE_FULL_ONLY');
assert.equal(incompatible.reason, 'checkpoint-incompatible');
assert.equal(incompatible.checkpointAttempted, false);
assert.equal(incompatibleCheckpointCalls, 0);
assert.equal(incompatible.authoritativeSummary, fullRun.summary);

// Timing/contract failures from the full oracle do not attempt acceleration.
let unsupportedCheckpointCalls = 0;
const unsupportedSummary = {
  status: 'REPLAY_CONTRACT_MISS',
  consumedTicks: 4,
  result: { status: 'REPLAY_CONTRACT_MISS', tick: 4, reason: 'transport-phase' },
};
const unsupported = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => ({ summary: unsupportedSummary, evidence: evidence() }),
  runCheckpointReplay: async () => {
    unsupportedCheckpointCalls += 1;
    return acceleratedRun;
  },
});
assert.equal(unsupported.status, 'CHECKPOINT_ORACLE_FULL_ONLY');
assert.equal(unsupported.reason, 'unsupported-full-status');
assert.equal(unsupportedCheckpointCalls, 0);
assert.equal(unsupported.authoritativeSummary, unsupportedSummary);

// Acceleration exceptions fall back to the full result.
const thrown = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => {
    throw new Error('synthetic checkpoint failure');
  },
});
assert.equal(thrown.status, 'CHECKPOINT_ORACLE_FULL_ONLY');
assert.equal(thrown.reason, 'checkpoint-exception');
assert.match(thrown.checkpointError, /synthetic checkpoint failure/);
assert.equal(thrown.authoritativeSummary, fullRun.summary);

// Two equally incomplete evidence objects must not be considered equivalent.
const incompleteEvidence = evidence();
delete incompleteEvidence.truth.workerPayload;
const invalidEvidenceComparison = compareCheckpointOracleRunsV1(
  { summary: fullRun.summary, evidence: incompleteEvidence },
  { summary: acceleratedRun.summary, evidence: structuredClone(incompleteEvidence) },
);
assert.equal(invalidEvidenceComparison.equivalent, false);
assert.equal(invalidEvidenceComparison.category, 'invalid-evidence');
assert.equal(invalidEvidenceComparison.fullEvidenceValidation.reason, 'truth-worker-payload');

// Missing evidence can never be trusted.
const missingEvidence = await runCheckpointCandidateOracleV1({
  checkpoint,
  sourceRecording: source,
  candidateRecording: candidate,
  runFullReplay: async () => fullRun,
  runCheckpointReplay: async () => ({ summary: acceleratedRun.summary }),
});
assert.equal(missingEvidence.status, 'CHECKPOINT_ORACLE_MISMATCH');
assert.equal(missingEvidence.reason, 'missing-evidence');
assert.equal(missingEvidence.checkpointTrusted, false);

console.log('checkpoint oracle runner tests: PASS');
