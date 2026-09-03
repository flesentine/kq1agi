import assert from 'node:assert/strict';
import { hashEditConfigV1 } from '../web/certification-edit-config.mjs';
import { hashArrayBufferV1 } from '../web/certification-recording.mjs';
import { snapshotReadyPlayJournal, validateFrozenReplayIdentityV1 } from '../web/certification-phase1d.mjs';

function makeShared({ totalTicks = 0, inTick = 0 } = {}) {
  const sab = new SharedArrayBuffer(8353 * 4);
  const vars = new Int32Array(sab);
  Atomics.store(vars, 512, totalTicks);
  Atomics.store(vars, 517, inTick);
  return { sab, vars };
}

const GAME = 'demo1-local';
const released = [
  { type: 'pulse', tick: 1, seq: 1, released: true },
  { type: 'random', tick: 1, seq: 2, bound: 9, value: 4 },
];

{
  const { sab } = makeShared({ totalTicks: 1, inTick: 0 });
  const result = snapshotReadyPlayJournal({
    rawEvents: released,
    variableSAB: sab,
    lastCompletedTick: 1,
    gameDirectory: GAME,
    overflowed: false,
  });
  assert.equal(result.ready, true);
  assert.equal(result.reason, 'complete');
  assert.equal(result.gameDirectory, GAME);
  assert.equal(result.lastReleaseTick, 1);
  assert.equal(result.lastCompletedTick, 1);
  assert.deepEqual(result.rawEvents, released);
  assert.notEqual(result.rawEvents, released);
  assert.notEqual(result.rawEvents[0], released[0]);

  released[0].released = false;
  assert.equal(result.rawEvents[0].released, true);
  released[0].released = true;
}

{
  const { sab } = makeShared({ totalTicks: 1, inTick: 1 });
  const result = snapshotReadyPlayJournal({
    rawEvents: released,
    variableSAB: sab,
    lastCompletedTick: 1,
    gameDirectory: GAME,
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'worker-busy');
}

{
  const { sab } = makeShared({ totalTicks: 1, inTick: 0 });
  const result = snapshotReadyPlayJournal({
    rawEvents: released,
    variableSAB: sab,
    lastCompletedTick: 0,
    gameDirectory: GAME,
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'worker-events-pending');
  assert.equal(result.lastReleaseTick, 1);
}

// A long worker cycle can be released at tick 1 while the normal 60 Hz clock moves
// through ticks 2 and 3. Once that cycle is idle and its FIFO completion marker for
// release tick 1 has arrived, the journal is safe to freeze at logical tick 3.
{
  const longCycle = [
    { type: 'pulse', tick: 1, seq: 1, released: true },
    { type: 'pulse', tick: 2, seq: 2, released: false },
    { type: 'pulse', tick: 3, seq: 3, released: false },
    { type: 'random', tick: 1, seq: 4, bound: 8, value: 3 },
  ];
  const { sab } = makeShared({ totalTicks: 3, inTick: 0 });
  const result = snapshotReadyPlayJournal({
    rawEvents: longCycle,
    variableSAB: sab,
    lastCompletedTick: 1,
    gameDirectory: GAME,
  });
  assert.equal(result.ready, true);
  assert.equal(result.gameDirectory, GAME);
  assert.equal(result.lastReleaseTick, 1);
  assert.equal(result.lastCompletedTick, 1);
}

{
  const { sab } = makeShared({ totalTicks: 2, inTick: 0 });
  const result = snapshotReadyPlayJournal({
    rawEvents: [
      { type: 'pulse', tick: 1, seq: 1, released: false },
      { type: 'pulse', tick: 2, seq: 2, released: false },
    ],
    variableSAB: sab,
    lastCompletedTick: 0,
    gameDirectory: GAME,
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'no-cycle-release');
}

{
  const { sab } = makeShared({ totalTicks: 1, inTick: 0 });
  const result = snapshotReadyPlayJournal({
    rawEvents: released,
    variableSAB: sab,
    lastCompletedTick: 1,
    gameDirectory: '',
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'no-game-identity');
}

{
  const result = snapshotReadyPlayJournal({
    rawEvents: released,
    variableSAB: null,
    lastCompletedTick: 1,
    gameDirectory: GAME,
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'no-shared-state');
}

// Phase -1E reuses the exact frozen EditConfig from the divergent replay. The
// top-level object is frozen, but nested arrays are not necessarily deep-frozen, so
// minimization must re-hash the actual config rather than trusting its declared hash.
{
  const gameBuffer = new Uint8Array([1, 2, 3, 4]).buffer;
  const editConfigBase = { schema: 'kq1agi-edit-config-v1', rooms: [], visualPins: [] };
  const editConfig = {
    ...editConfigBase,
    hash: await hashEditConfigV1(editConfigBase),
  };
  const recording = {
    gameHash: await hashArrayBufferV1(gameBuffer),
    gameBytes: gameBuffer.byteLength,
    editConfigHash: editConfig.hash,
  };

  const identity = await validateFrozenReplayIdentityV1(recording, gameBuffer, editConfig);
  assert.equal(identity.gameHash, recording.gameHash);
  assert.equal(identity.editConfigHash, recording.editConfigHash);

  await assert.rejects(
    validateFrozenReplayIdentityV1(recording, new Uint8Array([1, 2, 3, 5]).buffer, editConfig),
    /GAMEFILES\.DAT changed/,
  );

  const mutatedNestedConfig = {
    ...editConfig,
    visualPins: [[1, 2, 3, 4, 5]],
  };
  await assert.rejects(
    validateFrozenReplayIdentityV1(recording, gameBuffer, mutatedNestedConfig),
    /frozen EditConfig changed/,
  );

  const wrongDeclaredHash = { ...editConfig, hash: 'sha256:stale' };
  await assert.rejects(
    validateFrozenReplayIdentityV1(recording, gameBuffer, wrongDeclaredHash),
    /frozen EditConfig changed/,
  );

  // hashEditConfigV1 intentionally canonicalizes to the v1 schema, so the replay
  // identity guard must also reject a raw schema mutation explicitly; otherwise the
  // applicator would skip the config while the hash still appeared unchanged.
  const wrongSchema = { ...editConfig, schema: 'kq1agi-edit-config-v0' };
  await assert.rejects(
    validateFrozenReplayIdentityV1(recording, gameBuffer, wrongSchema),
    /frozen EditConfig changed/,
  );
}

console.log('Phase -1D recording boundary tests: PASS');
