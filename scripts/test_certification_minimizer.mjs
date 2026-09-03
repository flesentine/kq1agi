import assert from 'node:assert/strict';
import { hashPlayRecordingV1 } from '../web/certification-recording.mjs';
import {
  buildRecordingPrefixV1,
  divergenceFingerprint,
  focusRecordingAroundTick,
  minimizeDivergentPrefix,
  sameDivergence,
} from '../web/certification-minimizer.mjs';

const recordingBase = {
  schema: 'kq1agi-play-recording-v1',
  completeFromStart: true,
  startTick: 1,
  finalTick: 100,
  gameHash: 'sha256:game',
  gameBytes: 1234,
  editConfigHash: 'sha256:edit',
  overflowed: false,
  releaseTicks: [1, 5, 20, 42, 45, 70, 100],
  events: [
    { tick: 2, seq: 1, phase: 'idle', type: 'key-state', keyCode: 1, pressed: true },
    { tick: 41, seq: 2, phase: 'busy', type: 'key-queue', encodedKey: 0x80041 },
    { tick: 44, seq: 3, phase: 'idle', type: 'mouse', x: 2, y: 3, button: 0 },
    { tick: 65, seq: 4, phase: 'idle', type: 'mouse', x: 3, y: 4, button: 1 },
  ],
  random: [
    { tick: 5, seq: 5, bound: 8, value: 3 },
    { tick: 42, seq: 6, bound: 9, value: 4 },
    { tick: 46, seq: 7, bound: 6, value: 1 },
    { tick: 80, seq: 8, bound: 10, value: 2 },
  ],
};
const recording = Object.freeze({ ...recordingBase, hash: await hashPlayRecordingV1(recordingBase) });

const prefix = await buildRecordingPrefixV1(recording, 42);
assert.equal(prefix.finalTick, 42);
assert.deepEqual(prefix.releaseTicks, [1, 5, 20, 42]);
assert.deepEqual(prefix.events.map(event => event.tick), [2, 41]);
assert.deepEqual(prefix.random.map(draw => draw.tick), [5, 42]);
assert.notEqual(prefix.hash, recording.hash);
assert.equal(prefix.hash, await hashPlayRecordingV1(prefix));
assert.equal(prefix.gameHash, recording.gameHash);
assert.equal(prefix.editConfigHash, recording.editConfigHash);
await assert.rejects(buildRecordingPrefixV1(recording, 0), /between 1 and 100/);
await assert.rejects(buildRecordingPrefixV1(recording, 101), /between 1 and 100/);

// Phase -1E must not turn a stale/tampered Phase -1D envelope into a fresh valid
// candidate merely by recomputing the candidate hash.
const tampered = {
  ...recording,
  events: recording.events.map((event, index) => index === 0 ? { ...event, keyCode: 99 } : { ...event }),
};
await assert.rejects(buildRecordingPrefixV1(tampered, 42), /source recording hash mismatch/);
let tamperedReplayCalls = 0;
await assert.rejects(minimizeDivergentPrefix(tampered, {
  status: 'DIVERGED', tick: 42, reason: 'semantic-digest', index: 2, truth: 100, edited: 101,
}, async () => {
  tamperedReplayCalls += 1;
  return { status: 'REPLAY_MATCH' };
}), /source recording hash mismatch/);
assert.equal(tamperedReplayCalls, 0);
await assert.rejects(buildRecordingPrefixV1({ ...recording, completeFromStart: false }, 42), /complete recording/);
await assert.rejects(buildRecordingPrefixV1({ ...recording, startTick: 2 }, 42), /complete recording/);
await assert.rejects(buildRecordingPrefixV1({ ...recording, overflowed: true }, 42), /overflowed/);

const target = {
  status: 'DIVERGED', tick: 42, cycle: 9, reason: 'semantic-digest', index: 2,
  truth: 100, edited: 101,
};
assert.ok(divergenceFingerprint(target));
assert.equal(sameDivergence({ ...target, cycle: 999 }, target), true);
assert.equal(sameDivergence({ ...target, index: 3 }, target), false);
assert.equal(sameDivergence({ ...target, tick: 43 }, target), false);

// External-event identity includes the complete stable detail payload, not merely
// the event category. Two different WAVs/flags must never collapse to one target.
const externalA = {
  status: 'DIVERGED', tick: 12, reason: 'external-event',
  detail: {
    type: 'sound-event',
    truth: { type: 'play', endFlag: 7, durationTicks: 10, wavHash: 0x1111 },
    edited: { type: 'play', endFlag: 7, durationTicks: 10, wavHash: 0x2222 },
  },
};
const externalReordered = {
  ...externalA,
  detail: {
    edited: { wavHash: 0x2222, durationTicks: 10, endFlag: 7, type: 'play' },
    type: 'sound-event',
    truth: { wavHash: 0x1111, durationTicks: 10, endFlag: 7, type: 'play' },
  },
};
assert.equal(sameDivergence(externalReordered, externalA), true);
assert.equal(sameDivergence({
  ...externalA,
  detail: { ...externalA.detail, edited: { ...externalA.detail.edited, wavHash: 0x3333 } },
}, externalA), false);
assert.equal(sameDivergence({
  ...externalA,
  detail: { ...externalA.detail, edited: { ...externalA.detail.edited, endFlag: 8 } },
}, externalA), false);

const quitState = {
  status: 'DIVERGED', tick: 91, cycle: 20, reason: 'quit-state',
  truthQuit: true, editedQuit: false, truthQuitMarked: true, editedQuitMarked: false,
};
assert.equal(sameDivergence({ ...quitState, cycle: 999 }, quitState), true);
assert.equal(sameDivergence({ ...quitState, editedQuitMarked: true }, quitState), false);
const quitHandshake = {
  status: 'DIVERGED', tick: 92, reason: 'quit-handshake', truthQuit: true, editedQuit: false,
};
assert.equal(sameDivergence({ ...quitHandshake, editedQuit: true }, quitHandshake), false);

const focus = focusRecordingAroundTick(recording, 42, 5);
assert.deepEqual([focus.startTick, focus.endTick], [37, 47]);
assert.deepEqual(focus.events.map(event => event.tick), [41, 44]);
assert.deepEqual(focus.random.map(draw => draw.tick), [42, 46]);
assert.deepEqual(focus.releaseTicks, [42, 45]);

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
// The authoritative replay prefix stops at 42, but the debugging focus deliberately
// retains the original post-divergence context through tick 47.
assert.deepEqual([direct.focus.startTick, direct.focus.endTick], [37, 47]);
assert.deepEqual(direct.focus.events.map(event => event.tick), [41, 44]);

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

// The source envelope is only top-level frozen. A replay callback must not be
// able to mutate nested source arrays after initial hash validation and thereby
// influence later candidates.
const mutableBase = {
  ...recordingBase,
  events: recordingBase.events.map(event => ({ ...event })),
  random: recordingBase.random.map(draw => ({ ...draw })),
  releaseTicks: [...recordingBase.releaseTicks],
};
const mutableRecording = {
  ...mutableBase,
  hash: await hashPlayRecordingV1(mutableBase),
};
let mutationAttempt = 0;
const mutationSafe = await minimizeDivergentPrefix(mutableRecording, target, async candidate => {
  mutationAttempt += 1;
  if (mutationAttempt === 1) {
    mutableRecording.events.length = 0;
    mutableRecording.random.length = 0;
    mutableRecording.releaseTicks.length = 0;
    return { status: 'REPLAY_MATCH' };
  }
  const retainedAuthenticatedSource = candidate.events.some(event => event.tick === 44)
    && candidate.random.some(draw => draw.tick === 42)
    && candidate.releaseTicks.includes(45);
  if (candidate.finalTick >= 45 && retainedAuthenticatedSource) {
    return { status: 'DIVERGED', firstDivergence: target, result: target };
  }
  return { status: 'REPLAY_MATCH' };
});
assert.equal(mutationSafe.status, 'MINIMIZED');
assert.equal(mutationSafe.minimizedFinalTick, 45);

const mismatch = await minimizeDivergentPrefix(recording, target, async () => ({
  status: 'DIVERGED',
  firstDivergence: { ...target, index: 3 },
  result: { ...target, index: 3 },
}));
assert.equal(mismatch.status, 'NOT_REPRODUCED');

// A stale diagnostic firstDivergence field on a non-divergent replay summary must
// never be accepted as proof that the candidate reproduced the target.
const staleDiagnostic = await minimizeDivergentPrefix(recording, target, async () => ({
  status: 'REPLAY_MATCH',
  firstDivergence: target,
  result: { status: 'MATCH', tick: 42 },
}));
assert.equal(staleDiagnostic.status, 'NOT_REPRODUCED');

let stop = false;
const attemptsSeen = [];
const stopped = await minimizeDivergentPrefix(recording, target, async () => {
  stop = true;
  return { status: 'REPLAY_MATCH' };
}, {
  shouldStop: () => stop,
  onAttempt: attempt => attemptsSeen.push(attempt.finalTick),
});
assert.equal(stopped.status, 'STOPPED');
assert.deepEqual(attemptsSeen, [42]);

console.log('certification minimizer tests: PASS');
