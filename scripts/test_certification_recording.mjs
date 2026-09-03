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
    this.comparedCycle = 0;
    this.keys = [];
    this.queue = [];
    this.mouse = [];
    this.soundEnds = [];
    this.settles = [];
  }
  setKey(code, pressed) { this.keys.push([this.logicalTick, code, pressed]); }
  enqueueKey(value) { this.queue.push([this.logicalTick, value]); }
  setMouse(x, y, button) { this.mouse.push([this.logicalTick, x, y, button]); }
  injectSoundCompletion(flag) { this.soundEnds.push([this.logicalTick, flag]); }
  async settleCurrentCycle(reason = 'final-cycle') {
    this.settles.push([this.logicalTick, reason, this.cycle, this.comparedCycle]);
    if (this.cycle > this.comparedCycle) {
      this.comparedCycle = this.cycle;
      return { status: 'MATCH', tick: this.logicalTick, cycle: this.cycle };
    }
    return { status: 'IDLE', tick: this.logicalTick, cycle: this.cycle, truthIdle: true, editedIdle: true };
  }
  async pulse({ allowCycleRelease, afterClockAdvance } = {}) {
    this.logicalTick += 1;
    let releasedCycle = false;
    if (allowCycleRelease) {
      this.cycle += 1;
      releasedCycle = true;
    }
    afterClockAdvance?.({
      tick: this.logicalTick,
      cycle: this.cycle,
      truthIdle: true,
      editedIdle: true,
      releasedCycle,
    });
    return {
      status: 'IDLE', tick: this.logicalTick, cycle: this.cycle,
      truthIdle: true, editedIdle: true, releasedCycle,
    };
  }
  getReplayRandomDrawCounts() { return { truth: 1, edited: 1 }; }
}

const host = new FakeHost();
const summary = await runCertificationReplaySession(host, frozen, { pulseIntervalMs: 0 });
assert.equal(summary.status, 'REPLAY_MATCH');
assert.equal(summary.consumedTicks, 3);
assert.equal(summary.certifiedBarriers, 2);
assert.deepEqual(host.keys, [[1, 19, true]]);
assert.deepEqual(host.queue, [[1, 0x80041]]);
assert.deepEqual(host.mouse, [[1, 10, 20, 0], [1, 11, 21, 1]]);
assert.deepEqual(host.soundEnds, [[2, 7]]);
assert.deepEqual(host.settles.map(item => item.slice(0, 2)), [
  [0, 'recorded-release'],
  [2, 'recorded-idle-event'],
  [2, 'recorded-release'],
  [3, 'final-cycle'],
]);

// Busy provenance is not a wall-clock deadline. If this machine has already
// finished the replay cycle by the deterministic tick boundary, inject the recorded
// transport there instead of turning CPU speed into REPLAY_TIMING_MISS.
const fast = new FakeHost();
const fastSummary = await runCertificationReplaySession(fast, frozen, { pulseIntervalMs: 0 });
assert.equal(fastSummary.status, 'REPLAY_MATCH');
assert.deepEqual(fast.keys, [[1, 19, true]]);

// A replay cycle may take longer than one 60 Hz interval in wall-clock time. A
// recorded release means hold logical time at the preceding tick until that cycle
// settles, then release on the recorded logical tick.
class SlowHost extends FakeHost {
  constructor() {
    super();
    this.inFlight = false;
    this.waitedLongerThanFrame = false;
  }
  async pulse({ allowCycleRelease, afterClockAdvance } = {}) {
    this.logicalTick += 1;
    let releasedCycle = false;
    if (allowCycleRelease) {
      this.cycle += 1;
      releasedCycle = true;
      this.inFlight = true;
    }
    afterClockAdvance?.({
      tick: this.logicalTick,
      cycle: this.cycle,
      truthIdle: !this.inFlight,
      editedIdle: !this.inFlight,
      releasedCycle,
    });
    return {
      status: this.inFlight ? 'BUSY' : 'IDLE',
      tick: this.logicalTick,
      cycle: this.cycle,
      truthIdle: !this.inFlight,
      editedIdle: !this.inFlight,
      releasedCycle,
    };
  }
  async settleCurrentCycle(reason = 'final-cycle') {
    this.settles.push([this.logicalTick, reason, this.cycle, this.comparedCycle]);
    if (this.inFlight) {
      await new Promise(resolve => setTimeout(resolve, 35));
      this.waitedLongerThanFrame = true;
      this.inFlight = false;
    }
    if (this.cycle > this.comparedCycle) {
      this.comparedCycle = this.cycle;
      return { status: 'MATCH', tick: this.logicalTick, cycle: this.cycle };
    }
    return { status: 'IDLE', tick: this.logicalTick, cycle: this.cycle, truthIdle: true, editedIdle: true };
  }
}
const slow = new SlowHost();
const slowSummary = await runCertificationReplaySession(slow, frozen, { pulseIntervalMs: 0 });
assert.equal(slowSummary.status, 'REPLAY_MATCH');
assert.equal(slow.waitedLongerThanFrame, true);
assert.equal(slowSummary.finalTick, 3);

// If the replay host still cannot perform the recorded release after the driver has
// settled the preceding boundary, that remains a reproduction timing failure.
class ReleaseMissHost extends FakeHost {
  async pulse({ afterClockAdvance } = {}) {
    this.logicalTick += 1;
    afterClockAdvance?.({
      tick: this.logicalTick,
      cycle: this.cycle,
      truthIdle: true,
      editedIdle: true,
      releasedCycle: false,
    });
    return {
      status: 'IDLE', tick: this.logicalTick, cycle: this.cycle,
      truthIdle: true, editedIdle: true, releasedCycle: false,
    };
  }
}
const miss = await runCertificationReplaySession(new ReleaseMissHost(), frozen, { pulseIntervalMs: 0 });
assert.equal(miss.status, 'REPLAY_TIMING_MISS');
assert.equal(miss.result.reason, 'cycle-release');
assert.equal(miss.result.expectedRelease, true);

// Within one logical tick normal PLAY cannot transition from an idle transport
// write back to a busy transport write without another pulse. Refuse such a journal.
const badPhaseRaw = [
  { type: 'pulse', tick: 1, seq: 1, released: true },
  { type: 'sound-end', tick: 1, seq: 2, phase: 'idle', endFlag: 7 },
  { type: 'key-state', tick: 1, seq: 3, phase: 'busy', keyCode: 19, pressed: true },
];
const badPhase = await freezePlayRecordingV1({
  gameBuffer: new Uint8Array([1]).buffer,
  editConfigHash: 'sha256:edit',
  rawEvents: badPhaseRaw,
});
const badPhaseSummary = await runCertificationReplaySession(new FakeHost(), badPhase, { pulseIntervalMs: 0 });
assert.equal(badPhaseSummary.status, 'REPLAY_CONTRACT_MISS');
assert.equal(badPhaseSummary.result.reason, 'transport-phase-order');

// A semantic difference that becomes visible only at the frozen final boundary is
// still a real divergence at the same final logical tick.
class FinalDivergenceHost extends FakeHost {
  async settleCurrentCycle(reason = 'final-cycle') {
    if (reason === 'final-cycle') {
      return { status: 'DIVERGED', tick: this.logicalTick, cycle: this.cycle, reason: 'semantic-digest', index: 1 };
    }
    return super.settleCurrentCycle(reason);
  }
}
const finalDivergence = await runCertificationReplaySession(new FinalDivergenceHost(), frozen, { pulseIntervalMs: 0 });
assert.equal(finalDivergence.status, 'DIVERGED');
assert.equal(finalDivergence.firstDivergence.tick, 3);

class RandomMissHost extends FakeHost {
  getReplayRandomDrawCounts() { return { truth: 0, edited: 0 }; }
}
const randomMiss = await runCertificationReplaySession(new RandomMissHost(), frozen, { pulseIntervalMs: 0 });
assert.equal(randomMiss.status, 'REPLAY_CONTRACT_MISS');
assert.equal(randomMiss.result.reason, 'random-stream-consumption');
assert.equal(randomMiss.result.expectedRandomDraws, 1);
assert.equal(randomMiss.result.truthRandomDraws, 0);
assert.equal(randomMiss.result.editedRandomDraws, 0);

clearPlayRecording();
console.log('certification recording tests: PASS');
