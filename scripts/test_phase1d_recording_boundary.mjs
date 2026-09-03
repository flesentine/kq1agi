import assert from 'node:assert/strict';
import { snapshotReadyPlayJournal } from '../web/certification-phase1d.mjs';

function makeShared({ totalTicks = 0, inTick = 0 } = {}) {
  const sab = new SharedArrayBuffer(8353 * 4);
  const vars = new Int32Array(sab);
  Atomics.store(vars, 512, totalTicks);
  Atomics.store(vars, 517, inTick);
  return { sab, vars };
}

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
    overflowed: false,
  });
  assert.equal(result.ready, true);
  assert.equal(result.reason, 'complete');
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
  });
  assert.equal(result.ready, true);
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
  });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'no-cycle-release');
}

{
  const result = snapshotReadyPlayJournal({ rawEvents: released, variableSAB: null, lastCompletedTick: 1 });
  assert.equal(result.ready, false);
  assert.equal(result.reason, 'no-shared-state');
}

console.log('Phase -1D recording boundary tests: PASS');
