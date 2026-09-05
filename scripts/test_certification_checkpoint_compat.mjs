import assert from 'node:assert/strict';

import {
  canonicalizePlayRecordingV1,
  encodeRandomReplay,
  hashPlayRecordingV1,
} from '../web/certification-recording.mjs';
import { hashCertificationCheckpointV1 } from '../web/certification-host.mjs';
import {
  proveCheckpointCandidateCompatibilityV1,
  rebindCheckpointForRecordingCandidateV1,
} from '../web/certification-checkpoint-compat.mjs';

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
    releaseTicks: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12],
    events: [
      { tick: 2, seq: 1, phase: 'idle', type: 'key-state', keyCode: 65, pressed: true },
      { tick: 3, seq: 2, phase: 'idle', type: 'key-state', keyCode: 65, pressed: false },
      { tick: 8, seq: 3, phase: 'idle', type: 'mouse', x: 10, y: 20, button: 0 },
    ],
    random: [
      { tick: 2, seq: 4, bound: 255, value: 7 },
      { tick: 9, seq: 5, bound: 255, value: 11 },
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
    truthTrace: [1, 2, 3],
    editedTrace: [1, 2, 3],
    truthDigest: [1, 2, 3, 4],
    editedDigest: [1, 2, 3, 4],
    truthTransport: {
      queue: [1, 2],
      keys: [0, 1],
      oldKeys: [0, 0],
      vars: [1, 2, 3],
      pixels: [4, 5, 6],
    },
    editedTransport: {
      queue: [1, 2],
      keys: [0, 1],
      oldKeys: [0, 0],
      vars: [1, 2, 3],
      pixels: [4, 5, 6],
    },
    truthWorkerPayload: [1, 2, 3, 4],
    editedWorkerPayload: [5, 6, 7, 8],
    pendingSoundCompletions: [{ dueTick: 8, endFlag: 12 }],
  };
  return Object.freeze({ ...base, hash: await hashCertificationCheckpointV1(base) });
}

const source = await freezeRecording();
const checkpoint = await makeCheckpoint(source);

const suffixInput = await freezeRecording({
  events: source.events.filter(event => event.seq !== 3),
});
const suffixProof = await proveCheckpointCandidateCompatibilityV1(checkpoint, source, suffixInput);
assert.equal(suffixProof.status, 'CHECKPOINT_CANDIDATE_COMPATIBLE');
assert.equal(suffixProof.checkpointTick, 6);
assert.equal(suffixProof.resumeBeforeTick, 7);
assert.equal(suffixProof.candidateRecordingHash, suffixInput.hash);
assert.ok(suffixProof.compatibilityKey.includes(suffixInput.hash));
assert.ok(suffixProof.compatibilityKey.endsWith('|6'));

const suffixRandom = await freezeRecording({
  random: [
    source.random[0],
    { ...source.random[1], value: 12 },
  ],
});
const randomProof = await proveCheckpointCandidateCompatibilityV1(checkpoint, source, suffixRandom);
assert.equal(randomProof.status, 'CHECKPOINT_CANDIDATE_COMPATIBLE');
assert.notEqual(randomProof.candidateRandomReplaySpec, randomProof.sourceRandomReplaySpec);

const reboundResult = await rebindCheckpointForRecordingCandidateV1(
  checkpoint,
  source,
  suffixRandom,
);
assert.equal(reboundResult.status, 'CHECKPOINT_CANDIDATE_REBOUND');
const rebound = reboundResult.checkpoint;
assert.equal(rebound.context.recordingHash, suffixRandom.hash);
assert.equal(rebound.context.randomReplaySpec, encodeRandomReplay(suffixRandom));
assert.equal(rebound.context.seed, checkpoint.context.seed);
assert.equal(rebound.context.gameHash, checkpoint.context.gameHash);
assert.equal(rebound.context.gameBytes, checkpoint.context.gameBytes);
assert.equal(rebound.context.editConfigHash, checkpoint.context.editConfigHash);
assert.equal(rebound.context.recordedExternalTiming, true);
assert.notEqual(rebound.hash, checkpoint.hash);
assert.equal(rebound.hash, await hashCertificationCheckpointV1(rebound));

const prefixInput = await freezeRecording({
  events: source.events.filter(event => event.seq !== 1),
});
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, prefixInput)).reason,
  'prefix-authority',
);

const prefixRandom = await freezeRecording({
  random: [
    { ...source.random[0], value: 8 },
    source.random[1],
  ],
});
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, prefixRandom)).reason,
  'prefix-authority',
);

const missingBoundary = await freezeRecording({
  releaseTicks: source.releaseTicks.filter(tick => tick !== 7),
});
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, missingBoundary)).reason,
  'resume-boundary',
);

const tooShort = await freezeRecording({
  finalTick: 6,
  releaseTicks: source.releaseTicks.filter(tick => tick <= 6),
  events: source.events.filter(event => event.tick <= 6),
  random: source.random.filter(draw => draw.tick <= 6),
});
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, tooShort)).reason,
  'candidate-before-checkpoint',
);

const editChanged = await freezeRecording({ editConfigHash: 'sha256:other-edit' });
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, editChanged)).reason,
  'edit-config-identity',
);

const gameChanged = await freezeRecording({ gameHash: 'sha256:other-game' });
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(checkpoint, source, gameChanged)).reason,
  'game-identity',
);

const tamperedCheckpoint = Object.freeze({ ...checkpoint, cycle: checkpoint.cycle + 1 });
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(tamperedCheckpoint, source, suffixInput)).reason,
  'checkpoint-hash',
);

const wrongContextBase = {
  ...checkpoint,
  context: Object.freeze({ ...checkpoint.context, recordingHash: 'sha256:not-source' }),
};
const wrongContext = Object.freeze({
  ...wrongContextBase,
  hash: await hashCertificationCheckpointV1(wrongContextBase),
});
assert.equal(
  (await proveCheckpointCandidateCompatibilityV1(wrongContext, source, suffixInput)).reason,
  'checkpoint-source-recording',
);

console.log('checkpoint candidate compatibility tests: PASS');
