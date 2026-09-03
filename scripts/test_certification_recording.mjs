import assert from 'node:assert/strict';
import {
  PlayRecordingLayout,
  clearPlayRecording,
  encodeRandomReplay,
  freezePlayRecordingV1,
  getPlayRecordingStats,
  normalizePlayRecordingRaw,
  runCertificationReplaySession,
} from '../web/certification-recording.mjs';

const raw = [
  { type: 'pulse', tick: 1, seq: 1, released: true },
  { type: 'key-state', tick: 1, seq: 2, phase: 'busy', keyCode: 19, pressed: true },
  { type: 'key-queue', tick: 1, seq: 3, phase: 'busy', encodedKey: 0x80041 },
  { type: 'mouse', tick: 1, seq: 4, phase: 'busy', x: 10, y: 20, button: 0 },
  { type: 'mouse', tick: 1, seq: 5, phase: 'busy', x: 11, y: 21, button: 1 },
  { type: 'random', tick: 1, seq: 6, bound: 9, value: 4 },
  { type: 'pulse', tick: 2, seq: 7, released: false },
  { type: 'sound-end', tick: 2, seq: 8, phase: 'idle', endFlag: 7 },
  { type: 'pulse', tick: 3, seq: 9, released: true },
];
const normalized = normalizePlayRecordingRaw(raw);
assert.equal(normalized.completeFromStart, true);
assert.deepEqual(normalized.releaseTicks, [1, 3]);
assert.equal(normalized.events.filter(e => e.type === 'mouse').length, 2);
assert.equal(normalized.events.filter(e => e.type === 'mouse')[1].x, 11);
assert.deepEqual(normalized.random.map(({ bound, value }) => [bound, value]), [[9, 4]]);
assert.deepEqual(getPlayRecordingStats(raw), {
  completeFromStart: true, startTick: 1, finalTick: 3, releaseCount: 2,
  eventCount: 5, randomCount: 1, rawCount: 9, overflowed: false,
});

const frozen = await freezePlayRecordingV1({
  gameBuffer: new Uint8Array([1, 2, 3]).buffer,
  editConfigHash: 'sha256:edit',
  rawEvents: raw,
});
assert.equal(frozen.schema, PlayRecordingLayout.SCHEMA);
assert.equal(frozen.finalTick, 3);
assert.match(frozen.gameHash, /^(sha256|fnv1a32):/);
assert.match(frozen.hash, /^(sha256|fnv1a32):/);
assert.equal(encodeRandomReplay(frozen), 'v1|9:4');
await assert.rejects(freezePlayRecordingV1({
  gameBuffer: new ArrayBuffer(1), editConfigHash: 'x',
  rawEvents: [{ type: 'pulse', tick: 2, seq: 1, released: true }],
}), /did not start at logical tick 1/);
await assert.rejects(freezePlayRecordingV1({
  gameBuffer: new ArrayBuffer(1), editConfigHash: 'x', rawEvents: raw, overflowed: true,
}), /safety limit/);

class FakeHost {
  constructor() {
    this.logicalTick = 0;
    this.cycle = 0;
    this.keys = [];
    this.queue = [];
    this.mouse = [];
    this.soundEnds = [];
  }
  setKey(code, pressed) { this.keys.push([this.logicalTick, code, pressed]); }
  enqueueKey(value) { this.queue.push([this.logicalTick, value]); }
  setMouse(x, y, button) { this.mouse.push([this.logicalTick, x, y, button]); }
  injectSoundCompletion(flag) { this.soundEnds.push([this.logicalTick, flag]); }
  async pulse({ allowCycleRelease }) {
    this.logicalTick += 1;
    if (allowCycleRelease) this.cycle += 1;
    return allowCycleRelease
      ? { status: 'MATCH', tick: this.logicalTick, cycle: this.cycle }
      : { status: 'IDLE', tick: this.logicalTick, cycle: this.cycle };
  }
}
const host = new FakeHost();
const summary = await runCertificationReplaySession(host, frozen);
assert.equal(summary.status, 'REPLAY_MATCH');
assert.equal(summary.consumedTicks, 3);
assert.equal(summary.certifiedBarriers, 2);
assert.deepEqual(host.keys, [[1, 19, true]]);
assert.deepEqual(host.queue, [[1, 0x80041]]);
assert.deepEqual(host.mouse, [[1, 10, 20, 0], [1, 11, 21, 1]]);
assert.deepEqual(host.soundEnds, [[2, 7]]);

class BarrierOnlyHost extends FakeHost {
  constructor() {
    super();
    this.first = true;
  }
  async pulse({ allowCycleRelease }) {
    if (this.first) {
      this.first = false;
      return { status: 'MATCH', tick: 0, cycle: 0, replayBarrierOnly: true };
    }
    return super.pulse({ allowCycleRelease });
  }
}
const barrierOnly = await runCertificationReplaySession(new BarrierOnlyHost(), frozen);
assert.equal(barrierOnly.status, 'REPLAY_MATCH');
assert.equal(barrierOnly.consumedTicks, 3);

class MissHost extends FakeHost {
  async pulse() {
    this.logicalTick += 1;
    return { status: 'BUSY', tick: this.logicalTick, cycle: this.cycle, truthIdle: false, editedIdle: false };
  }
}
const miss = await runCertificationReplaySession(new MissHost(), frozen);
assert.equal(miss.status, 'REPLAY_TIMING_MISS');
assert.equal(miss.result.expectedRelease, true);

clearPlayRecording();
console.log('certification recording tests: PASS');
