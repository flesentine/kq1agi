import assert from 'node:assert/strict';
import {
  buildRecordingPrefixV1,
  divergenceFingerprint,
  focusRecordingAroundTick,
  minimizeDivergentPrefix,
  sameDivergence,
} from '../web/certification-minimizer.mjs';

const recording = Object.freeze({
  schema: 'kq1agi-play-recording-v1',
  completeFromStart: true,
  startTick: 1,
  finalTick: 100,
  gameHash: 'sha256:game',
  gameBytes: 1234,
  editConfigHash: 'sha256:edit',
  overflowed: false,
  releaseTicks: [1, 5, 20, 42, 70, 100],
  events: [
    { tick: 2, seq: 1, phase: 'idle', type: 'key-state', keyCode: 1, pressed: true },
    { tick: 41, seq: 2, phase: 'busy', type: 'key-queue', encodedKey: 0x80041 },
    { tick: 65, seq: 3, phase: 'idle', type: 'mouse', x: 3, y: 4, button: 1 },
  ],
  random: [
    { tick: 5, seq: 4, bound: 8, value: 3 },
    { tick: 42, seq: 5, bound: 9, value: 4 },
    { tick: 80, seq: 6, bound: 10, value: 2 },
  ],
  hash: 'sha256:old',
});

const prefix = await buildRecordingPrefixV1(recording, 42);
assert.equal(prefix.finalTick, 42);
assert.deepEqual(prefix.releaseTicks, [1, 5, 20, 42]);
assert.deepEqual(prefix.events.map(event => event.tick), [2, 41]);
assert.deepEqual(prefix.random.map(draw => draw.tick), [5, 42]);
assert.notEqual(prefix.hash, recording.hash);
assert.equal(prefix.gameHash, recording.gameHash);
assert.equal(prefix.editConfigHash, recording.editConfigHash);
await assert.rejects(buildRecordingPrefixV1(recording, 0), /between 1 and 100/);
await assert.rejects(buildRecordingPrefixV1(recording, 101), /between 1 and 100/);

const target = {
  status: 'DIVERGED', tick: 42, cycle: 9, reason: 'semantic-digest', index: 2,
  truth: 100, edited: 101,
};
assert.ok(divergenceFingerprint(target));
assert.equal(sameDivergence({ ...target, cycle: 999 }, target), true);
assert.equal(sameDivergence({ ...target, index: 3 }, target), false);
assert.equal(sameDivergence({ ...target, tick: 43 }, target), false);

const focus = focusRecordingAroundTick(recording, 42, 5);
assert.deepEqual([focus.startTick, focus.endTick], [37, 47]);
assert.deepEqual(focus.events.map(event => event.tick), [41]);
assert.deepEqual(focus.random.map(draw => draw.tick), [42]);
assert.deepEqual(focus.releaseTicks, [42]);

const directAttempts = [];
const direct = await minimizeDivergentPrefix(recording, target, async candidate => {
  directAttempts.push(candidate.finalTick);
  if (candidate.finalTick >= 42) {
    return { status: 'DIVERGED', result: target, firstDivergence: target };
  }
  return { status: 'REPLAY_MATCH' };
}, { focusRadius: 5 });
assert.equal(direct.status, 'MINIMIZED');
assert.equal(direct.minimizedFinalTick, 42);
assert.equal(direct.removedTicks, 58);
assert.deepEqual(directAttempts, [42]);
assert.deepEqual([direct.focus.startTick, direct.focus.endTick], [37, 42]);

// Exercise the fallback: imagine a future transport contract where the same
// divergence at tick 42 is not exposed until a final boundary at tick 45.
const fallbackAttempts = [];
const fallback = await minimizeDivergentPrefix(recording, target, async candidate => {
  fallbackAttempts.push(candidate.finalTick);
  if (candidate.finalTick >= 45) {
    return { status: 'DIVERGED', firstDivergence: target, result: target };
  }
  return { status: 'REPLAY_MATCH' };
});
assert.equal(fallback.status, 'MINIMIZED');
assert.equal(fallback.minimizedFinalTick, 45);
assert.ok(fallbackAttempts.length < 10);
assert.equal(fallbackAttempts[0], 42);

const mismatch = await minimizeDivergentPrefix(recording, target, async candidate => ({
  status: 'DIVERGED',
  firstDivergence: { ...target, index: 3 },
  result: { ...target, index: 3 },
}));
assert.equal(mismatch.status, 'NOT_REPRODUCED');

console.log('certification minimizer tests: PASS');
