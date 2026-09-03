import assert from 'node:assert/strict';
import {
  encodeRandomReplay,
  freezePlayRecordingV1,
  hashPlayRecordingV1,
  runCertificationReplaySession,
} from '../web/certification-recording.mjs';

const recording = await freezePlayRecordingV1({
  gameBuffer: new Uint8Array([1, 2, 3, 4]).buffer,
  editConfigHash: 'sha256:test-edit',
  rawEvents: [
    { type: 'pulse', tick: 1, seq: 1, released: true },
    { type: 'random', tick: 1, seq: 2, bound: 255, value: 17 },
    { type: 'random', tick: 1, seq: 3, bound: 9, value: 4 },
  ],
});

// Hash-equivalent representation changes must also be replay-equivalent. The
// canonical recording hash sorts RNG by seq and ignores malformed draws, so the RNG
// replay encoder must consume that same canonical view rather than raw array order.
const originalHash = recording.hash;
recording.random.reverse();
recording.random.push({ tick: 1, seq: 999, bound: 0, value: 999 });
assert.equal(await hashPlayRecordingV1(recording), originalHash);
assert.equal(encodeRandomReplay(recording), 'v1|255:17;9:4');
recording.random.splice(0, recording.random.length,
  { tick: 1, seq: 2, bound: 255, value: 17 },
  { tick: 1, seq: 3, bound: 9, value: 4 },
);

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
