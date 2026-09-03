import assert from 'node:assert/strict';
import {
  freezePlayRecordingV1,
  runCertificationReplaySession,
} from '../web/certification-recording.mjs';

const recording = await freezePlayRecordingV1({
  gameBuffer: new Uint8Array([1, 2, 3, 4]).buffer,
  editConfigHash: 'sha256:test-edit',
  rawEvents: [
    { type: 'pulse', tick: 1, seq: 1, released: true },
    { type: 'random', tick: 1, seq: 2, bound: 255, value: 17 },
  ],
});

// Object.freeze() intentionally protects only the recording envelope. Verify that
// an accidental or malicious nested mutation cannot retain the old identity and
// proceed into ORIGINAL/EDITED execution.
recording.random[0].value = 18;

const host = {
  logicalTick: 0,
  cycle: 0,
  async pulse() {
    throw new Error('hash-mismatched recording must be rejected before replay starts');
  },
};

const result = await runCertificationReplaySession(host, recording, { pulseIntervalMs: 0 });
assert.equal(result.status, 'REPLAY_CONTRACT_MISS');
assert.equal(result.result.reason, 'recording-hash');
assert.equal(result.certifiedBarriers, 0);
assert.equal(result.consumedTicks, 0);
assert.notEqual(result.result.expectedRecordingHash, result.result.actualRecordingHash);

console.log('certification recording hash test: PASS');
