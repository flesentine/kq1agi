import assert from 'node:assert/strict';
import { canonicalizeEditConfigV1, hashEditConfigV1 } from '../web/certification-edit-config.mjs';
import { hashPlayRecordingV1 } from '../web/certification-recording.mjs';
import {
  buildEditConfigWithoutGroupsV1,
  groupEditConfigV1,
  minimizeEditConfigV1,
} from '../web/certification-edit-minimizer.mjs';

async function freezeConfig(base) {
  const canonical = canonicalizeEditConfigV1(base);
  return Object.freeze({ ...canonical, hash: await hashEditConfigV1(canonical) });
}

async function freezeRecording(editConfigHash) {
  const base = {
    schema: 'kq1agi-play-recording-v1',
    completeFromStart: true,
    startTick: 1,
    finalTick: 3,
    gameHash: 'sha256:game',
    gameBytes: 321,
    editConfigHash,
    overflowed: false,
    releaseTicks: [1, 2, 3],
    events: [
      { tick: 2, seq: 1, phase: 'idle', type: 'key-state', keyCode: 30, pressed: true },
      { tick: 2, seq: 2, phase: 'idle', type: 'key-queue', encodedKey: 0x80042 },
      { tick: 2, seq: 3, phase: 'idle', type: 'key-state', keyCode: 30, pressed: false },
    ],
    random: [],
  };
  return Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });
}

const room = number => ({
  room: number,
  enabled: true,
  waterActive: false,
  fallActive: false,
  controlSeedState: number + 1,
  scriptDangerSeedState: number + 1,
  masks: ['', '', '', '', '', ''],
});

const config = await freezeConfig({
  schema: 'kq1agi-edit-config-v1',
  rooms: [room(1), room(2)],
  visualPins: [[1, 7, 8, 9, 10]],
});
const recording = await freezeRecording(config.hash);

const duplicateConfig = await freezeConfig({
  schema: 'kq1agi-edit-config-v1',
  rooms: [room(1), room(257)],
  visualPins: [],
});
assert.throws(() => groupEditConfigV1(duplicateConfig), /duplicate room 1/);

const groups = groupEditConfigV1(config);
assert.deepEqual(groups.map(group => group.id), ['edit-room-1', 'edit-room-2', 'edit-visual-pins']);
assert.deepEqual(groups.map(group => group.kind), ['room-config', 'room-config', 'visual-pins']);

const withoutRoom2 = await buildEditConfigWithoutGroupsV1(recording, config, ['edit-room-2']);
assert.deepEqual(withoutRoom2.editConfig.rooms.map(entry => entry.room), [1]);
assert.equal(withoutRoom2.editConfig.visualPins.length, 1);
assert.equal(withoutRoom2.recording.editConfigHash, withoutRoom2.editConfig.hash);
assert.equal(withoutRoom2.recording.hash, await hashPlayRecordingV1(withoutRoom2.recording));
assert.notEqual(withoutRoom2.recording.hash, recording.hash);
assert.equal(withoutRoom2.recording.finalTick, recording.finalTick);
assert.equal(withoutRoom2.recording.gameHash, recording.gameHash);
assert.equal(withoutRoom2.recording.gameBytes, recording.gameBytes);
assert.deepEqual(withoutRoom2.recording.releaseTicks, recording.releaseTicks);
assert.deepEqual(withoutRoom2.recording.events, recording.events);
assert.deepEqual(withoutRoom2.recording.random, recording.random);
assert.deepEqual(config.rooms.map(entry => entry.room), [1, 2]);
assert.equal(config.visualPins.length, 1);
await assert.rejects(
  buildEditConfigWithoutGroupsV1(recording, config, ['edit-room-999']),
  /Unknown Phase -1G edit group/,
);

const target = {
  status: 'DIVERGED',
  tick: 3,
  reason: 'semantic-digest',
  index: 1,
  truth: 111,
  edited: 222,
};

const replay = async (candidateRecording, candidateConfig) => {
  assert.equal(candidateRecording.editConfigHash, candidateConfig.hash);
  assert.equal(candidateRecording.hash, await hashPlayRecordingV1(candidateRecording));
  const hasRequiredRoom = candidateConfig.rooms.some(entry => entry.room === 1);
  if (hasRequiredRoom) {
    return { status: 'DIVERGED', firstDivergence: target, result: target };
  }
  const hasRoom2 = candidateConfig.rooms.some(entry => entry.room === 2);
  if (hasRoom2) {
    const different = { ...target, edited: 223 };
    return { status: 'DIVERGED', firstDivergence: different, result: different };
  }
  return { status: 'REPLAY_MATCH' };
};

const minimized = await minimizeEditConfigV1(recording, config, target, replay);
assert.equal(minimized.status, 'EDITS_MINIMIZED');
assert.equal(minimized.totalGroups, 3);
assert.equal(minimized.keptGroups.length, 1);
assert.equal(minimized.keptGroups[0].id, 'edit-room-1');
assert.deepEqual(minimized.editConfig.rooms.map(entry => entry.room), [1]);
assert.equal(minimized.editConfig.visualPins.length, 0);
assert.equal(minimized.recording.editConfigHash, minimized.editConfig.hash);
assert.equal(minimized.recording.hash, await hashPlayRecordingV1(minimized.recording));
assert.equal(minimized.attempts[0].phase, 'baseline');
assert.equal(minimized.attempts[0].reproduced, true);

const wrongConfig = Object.freeze({ ...config, hash: 'sha256:wrong' });
await assert.rejects(
  minimizeEditConfigV1(recording, wrongConfig, target, replay),
  /EditConfig hash mismatch/,
);

const notReproduced = await minimizeEditConfigV1(recording, config, target, async () => ({
  status: 'DIVERGED',
  firstDivergence: { ...target, edited: 223 },
  result: { ...target, edited: 223 },
}));
assert.equal(notReproduced.status, 'NOT_REPRODUCED');
assert.equal(notReproduced.attempts.length, 1);

let stop = false;
const stopped = await minimizeEditConfigV1(recording, config, target, async (...args) => {
  stop = true;
  return replay(...args);
}, {
  shouldStop: () => stop,
});
assert.equal(stopped.status, 'STOPPED');
assert.equal(stopped.attempts.length, 1);

const partial = await minimizeEditConfigV1(recording, config, target, replay, { maxAttempts: 1 });
assert.equal(partial.status, 'PARTIAL');
assert.equal(partial.reason, 'attempt-budget');
assert.equal(partial.attempts.length, 1);

const emptyConfig = await freezeConfig({
  schema: 'kq1agi-edit-config-v1',
  rooms: [],
  visualPins: [],
});
const emptyRecording = await freezeRecording(emptyConfig.hash);
const noEdits = await minimizeEditConfigV1(emptyRecording, emptyConfig, target, async () => ({
  status: 'DIVERGED', firstDivergence: target, result: target,
}));
assert.equal(noEdits.status, 'NO_REMOVABLE_EDITS');
assert.equal(noEdits.totalGroups, 0);

console.log('certification edit minimizer tests: PASS');
