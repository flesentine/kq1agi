import assert from 'node:assert/strict';
import { hashPlayRecordingV1 } from '../web/certification-recording.mjs';
import {
  buildRecordingWithoutInputGroupsV1,
  groupReplayInputEventsV1,
  minimizeInputGroupsV1,
} from '../web/certification-input-minimizer.mjs';

const base = {
  schema: 'kq1agi-play-recording-v1',
  completeFromStart: true,
  startTick: 1,
  finalTick: 12,
  gameHash: 'sha256:game',
  gameBytes: 321,
  editConfigHash: 'sha256:edit',
  overflowed: false,
  releaseTicks: [1, 2, 4, 6, 8, 10, 12],
  events: [
    // A normal key gesture.
    { tick: 1, seq: 1, phase: 'idle', type: 'key-state', keyCode: 29, pressed: true },
    { tick: 1, seq: 2, phase: 'idle', type: 'key-queue', encodedKey: 0x80041 },
    { tick: 2, seq: 3, phase: 'idle', type: 'key-state', keyCode: 29, pressed: false },

    // Shift+B chord. The overlapping key intervals must form one atomic group.
    { tick: 3, seq: 4, phase: 'idle', type: 'key-state', keyCode: 59, pressed: true },
    { tick: 3, seq: 5, phase: 'idle', type: 'key-state', keyCode: 30, pressed: true },
    { tick: 3, seq: 6, phase: 'idle', type: 'key-queue', encodedKey: 0x80042 },
    { tick: 4, seq: 7, phase: 'idle', type: 'key-state', keyCode: 30, pressed: false },
    { tick: 4, seq: 8, phase: 'idle', type: 'key-state', keyCode: 59, pressed: false },

    // Queue-only event (e.g. a platform-specific typed/back action).
    { tick: 5, seq: 9, phase: 'idle', type: 'key-queue', encodedKey: 0x4001d },

    // Mouse press, drag, release. Each physical pointer update records a three-write
    // state batch, and the complete held-button interval must stay atomic.
    { tick: 6, seq: 10, phase: 'idle', type: 'mouse', x: 0, y: 0, button: 1 },
    { tick: 6, seq: 11, phase: 'idle', type: 'mouse', x: 10, y: 0, button: 1 },
    { tick: 6, seq: 12, phase: 'idle', type: 'mouse', x: 10, y: 20, button: 1 },
    { tick: 7, seq: 13, phase: 'idle', type: 'mouse', x: 10, y: 20, button: 1 },
    { tick: 7, seq: 14, phase: 'idle', type: 'mouse', x: 11, y: 20, button: 1 },
    { tick: 7, seq: 15, phase: 'idle', type: 'mouse', x: 11, y: 21, button: 1 },
    { tick: 8, seq: 16, phase: 'idle', type: 'mouse', x: 11, y: 21, button: 0 },
    { tick: 8, seq: 17, phase: 'idle', type: 'mouse', x: 12, y: 21, button: 0 },
    { tick: 8, seq: 18, phase: 'idle', type: 'mouse', x: 12, y: 22, button: 0 },

    // Plain mouse move is independently removable as one physical state batch.
    { tick: 9, seq: 19, phase: 'idle', type: 'mouse', x: 12, y: 22, button: 0 },
    { tick: 9, seq: 20, phase: 'idle', type: 'mouse', x: 13, y: 22, button: 0 },
    { tick: 9, seq: 21, phase: 'idle', type: 'mouse', x: 13, y: 23, button: 0 },

    // External completion timing is reproduction authority, never an input group.
    { tick: 10, seq: 22, phase: 'idle', type: 'sound-end', endFlag: 7 },
  ],
  random: [
    { tick: 2, seq: 30, bound: 9, value: 4 },
    { tick: 8, seq: 31, bound: 255, value: 17 },
  ],
};
const recording = Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });

const groups = groupReplayInputEventsV1(recording);
assert.deepEqual(groups.map(group => group.kind), [
  'keyboard-gesture',
  'keyboard-gesture',
  'keyboard-queue',
  'mouse-gesture',
  'mouse-move',
]);
assert.deepEqual(groups[0].eventSeqs, [1, 2, 3]);
assert.deepEqual(groups[1].eventSeqs, [4, 5, 6, 7, 8]);
assert.deepEqual(groups[2].eventSeqs, [9]);
assert.deepEqual(groups[3].eventSeqs, [10, 11, 12, 13, 14, 15, 16, 17, 18]);
assert.deepEqual(groups[4].eventSeqs, [19, 20, 21]);

assert.throws(() => groupReplayInputEventsV1({
  ...recording,
  events: [
    { tick: 1, seq: 1, phase: 'idle', type: 'key-queue', encodedKey: 1 },
    { tick: 1, seq: 1, phase: 'idle', type: 'sound-end', endFlag: 7 },
  ],
}), /unique positive canonical event seq/);
assert.throws(() => groupReplayInputEventsV1({
  ...recording,
  events: [{ tick: 1, seq: 0, phase: 'idle', type: 'key-queue', encodedKey: 1 }],
}), /unique positive canonical event seq/);

// Incomplete key-state fragments are intentionally locked: no synthetic one-sided
// key gesture is offered to delta debugging when the matching release is absent.
const incompleteBase = {
  ...base,
  events: [
    { tick: 1, seq: 1, phase: 'idle', type: 'key-state', keyCode: 29, pressed: true },
    { tick: 1, seq: 2, phase: 'idle', type: 'key-queue', encodedKey: 0x80041 },
    { tick: 2, seq: 3, phase: 'idle', type: 'sound-end', endFlag: 7 },
  ],
};
const incomplete = Object.freeze({ ...incompleteBase, hash: await hashPlayRecordingV1(incompleteBase) });
assert.deepEqual(groupReplayInputEventsV1(incomplete), []);

const reduced = await buildRecordingWithoutInputGroupsV1(recording, ['input-1', 'input-4']);
assert.equal(reduced.finalTick, recording.finalTick);
assert.deepEqual(reduced.releaseTicks, recording.releaseTicks);
assert.deepEqual(reduced.random, recording.random);
assert.ok(reduced.events.some(event => event.type === 'sound-end' && event.seq === 22));
assert.equal(reduced.events.some(event => event.seq === 1), false);
assert.equal(reduced.events.some(event => event.seq === 10), false);
assert.equal(reduced.events.some(event => event.seq === 4), true);
assert.equal(reduced.hash, await hashPlayRecordingV1(reduced));
await assert.rejects(
  buildRecordingWithoutInputGroupsV1(recording, ['input-999']),
  /Unknown Phase -1F input group/,
);

const target = {
  status: 'DIVERGED',
  tick: 10,
  reason: 'semantic-digest',
  index: 2,
  truth: 111,
  edited: 222,
};

const replay = async candidate => {
  const hasRequiredB = candidate.events.some(event =>
    event.type === 'key-queue' && event.encodedKey === 0x80042);
  if (hasRequiredB) {
    return { status: 'DIVERGED', firstDivergence: target, result: target };
  }
  // A different mismatch must never count as the target.
  const hasMouseMove = candidate.events.some(event => event.seq === 21);
  if (hasMouseMove) {
    const different = { ...target, index: 3, edited: 223 };
    return { status: 'DIVERGED', firstDivergence: different, result: different };
  }
  return { status: 'REPLAY_MATCH' };
};

const minimized = await minimizeInputGroupsV1(recording, target, replay);
assert.equal(minimized.status, 'INPUTS_MINIMIZED');
assert.equal(minimized.totalGroups, 5);
assert.equal(minimized.keptGroups.length, 1);
assert.equal(minimized.keptGroups[0].kind, 'keyboard-gesture');
assert.deepEqual(minimized.keptGroups[0].eventSeqs, [4, 5, 6, 7, 8]);
assert.equal(minimized.removedGroups.length, 4);
assert.equal(minimized.keptInputEvents, 5);
assert.equal(minimized.removedInputEvents, 16);
assert.equal(minimized.lockedEvents, 1);
assert.ok(minimized.recording.events.some(event => event.type === 'sound-end'));
assert.equal(minimized.recording.hash, await hashPlayRecordingV1(minimized.recording));
assert.equal(minimized.attempts[0].phase, 'baseline');
assert.equal(minimized.attempts[0].reproduced, true);

// If the exact source no longer reproduces the target, reduction must not begin.
const notReproduced = await minimizeInputGroupsV1(recording, target, async () => ({
  status: 'REPLAY_MATCH',
}));
assert.equal(notReproduced.status, 'NOT_REPRODUCED');
assert.equal(notReproduced.attempts.length, 1);

// Cancellation is honored between candidate runs.
let stop = false;
const stopped = await minimizeInputGroupsV1(recording, target, async candidate => {
  stop = true;
  return candidate.events.some(event => event.encodedKey === 0x80042)
    ? { status: 'DIVERGED', firstDivergence: target, result: target }
    : { status: 'REPLAY_MATCH' };
}, {
  shouldStop: () => stop,
});
assert.equal(stopped.status, 'STOPPED');
assert.equal(stopped.attempts.length, 1);

// Attempt budgets produce a truthful partial result instead of claiming minimality.
const partial = await minimizeInputGroupsV1(recording, target, replay, { maxAttempts: 1 });
assert.equal(partial.status, 'PARTIAL');
assert.equal(partial.reason, 'attempt-budget');
assert.equal(partial.attempts.length, 1);

// A recording with only locked external events has nothing dependency-safe to drop.
const lockedBase = {
  ...base,
  events: [{ tick: 10, seq: 22, phase: 'idle', type: 'sound-end', endFlag: 7 }],
};
const locked = Object.freeze({ ...lockedBase, hash: await hashPlayRecordingV1(lockedBase) });
const noInputs = await minimizeInputGroupsV1(locked, target, async () => ({
  status: 'DIVERGED', firstDivergence: target, result: target,
}));
assert.equal(noInputs.status, 'NO_REMOVABLE_INPUTS');
assert.equal(noInputs.totalGroups, 0);
assert.equal(noInputs.lockedEvents, 1);

console.log('certification input minimizer tests: PASS');
