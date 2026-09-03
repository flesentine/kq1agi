import assert from 'node:assert/strict';
import { ReplayCertificationHost } from '../web/certification-replay-host.mjs';

class MockWorker {
  static instances = [];
  constructor(url) {
    this.url = url;
    this.onmessage = null;
    this.onerror = null;
    this.init = null;
    this.hold = false;
    this.randomDraws = 0;
    this.digestXor = 0;
    MockWorker.instances.push(this);
  }
  publishSnapshot() {
    this.trace[0] = 2;
    this.trace[1] = this.vars[512];
    this.digest[0] = 1;
    this.digest[1] = this.vars[512] ^ 0x1111;
    this.digest[2] = 0x2222 ^ this.digestXor;
    this.digest[3] = 0x3333;
    this.digest[4] = 0x4444;
    this.digest[5] = this.randomDraws;
    this.digest[6] = 0;
  }
  postMessage(message) {
    if (message.name === 'Initialise') {
      this.init = message.object;
      this.vars = new Uint32Array(this.init.variableSAB);
      this.trace = new Uint32Array(this.init.diagnosticTraceSAB);
      this.digest = new Uint32Array(this.init.certificationDigestSAB);
    } else if (message.name === 'Start') {
      queueMicrotask(() => this.onmessage?.({ data: { name: 'CertificationReady', object: {} } }));
      this.timer = setInterval(() => {
        if (!this.hold && Atomics.load(this.vars, 517) === 1) Atomics.store(this.vars, 517, 0);
        if (Atomics.load(this.vars, 517) === 0) {
          const req = Atomics.load(this.digest, 8) >>> 0;
          const ack = Atomics.load(this.digest, 9) >>> 0;
          if (req && req !== ack) {
            this.publishSnapshot();
            Atomics.store(this.digest, 9, req);
            queueMicrotask(() => this.onmessage?.({ data: { name: 'CertificationSnapshotReady', object: { epoch: req } } }));
          }
        }
      }, 0);
    }
  }
  terminate() { clearInterval(this.timer); }
}

MockWorker.instances.length = 0;
const host = new ReplayCertificationHost({
  WorkerCtor: MockWorker,
  truthWorkerUrl: 'truth.js',
  editedWorkerUrl: 'edited.js',
  randomReplaySpec: 'v1|9:4;255:17',
  barrierTimeoutMs: 500,
});
await host.start(new ArrayBuffer(16));
assert.equal(MockWorker.instances.length, 2);
for (const worker of MockWorker.instances) {
  assert.equal(worker.init.certificationRandomReplay, 'v1|9:4;255:17');
}

let result = await host.pulse({ allowCycleRelease: false });
assert.equal(result.status, 'IDLE');
assert.equal(host.logicalTick, 1);
assert.equal(host.cycle, 0);

// A quickly completed replay cycle is deliberately left un-compared until a
// recorded semantic boundary is reached. CPU speed must not choose the barrier tick.
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'IDLE');
assert.equal(result.comparisonDeferred, true);
assert.equal(host.logicalTick, 2);
assert.equal(host.cycle, 1);
assert.equal(host.comparedCycle, 0);
result = await host.settleCurrentCycle('recorded-release');
assert.equal(result.status, 'MATCH');
assert.equal(result.settleReason, 'recorded-release');
assert.equal(host.comparedCycle, 1);
assert.equal(host.logicalTick, 2);

host.injectSoundCompletion(7);
assert.equal(Atomics.load(host.truth.vars, 256 + 7), 1);
assert.equal(Atomics.load(host.edited.vars, 256 + 7), 1);

const wav = new ArrayBuffer(48);
host._handleLaneMessage(host.truth, { name: 'PlaySound', object: { endFlag: 9 }, buffer: wav });
host._handleLaneMessage(host.edited, { name: 'PlaySound', object: { endFlag: 9 }, buffer: wav.slice(0) });
assert.equal(host.pendingExternalDivergence, null);
assert.equal(host.pendingSoundCompletions.length, 0);

// A recorded boundary may take longer than one wall-clock frame to reproduce. Hold
// logical time fixed until both lanes finish, then compare the same logical tick.
const [truthWorker, editedWorker] = MockWorker.instances;
truthWorker.hold = true;
editedWorker.hold = true;
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'BUSY');
assert.equal(host.logicalTick, 3);
assert.equal(host.cycle, 2);
const heldTick = host.logicalTick;
truthWorker.randomDraws = 2;
editedWorker.randomDraws = 2;
setTimeout(() => {
  truthWorker.hold = false;
  editedWorker.hold = false;
}, 35);
const waitStarted = Date.now();
result = await host.settleCurrentCycle('recorded-release');
assert.ok((Date.now() - waitStarted) >= 20);
assert.equal(result.status, 'MATCH');
assert.equal(result.replaySettled, true);
assert.equal(result.settleReason, 'recorded-release');
assert.equal(host.logicalTick, heldTick);
assert.deepEqual(host.getReplayRandomDrawCounts(), { truth: 2, edited: 2 });

// Completing early on a no-release tick must not publish an opportunistic barrier.
// The clock advances according to the recorded schedule and comparison stays deferred.
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'IDLE');
assert.equal(result.comparisonDeferred, true);
const deferredCycle = host.cycle;
const deferredTick = host.logicalTick;
assert.ok(deferredCycle > host.comparedCycle);
result = await host.pulse({ allowCycleRelease: false });
assert.equal(result.status, 'IDLE');
assert.equal(host.logicalTick, deferredTick + 1);
assert.equal(host.cycle, deferredCycle);
assert.ok(host.comparedCycle < deferredCycle);
result = await host.settleCurrentCycle('recorded-release');
assert.equal(result.status, 'MATCH');
assert.equal(host.comparedCycle, deferredCycle);

// A semantic difference that becomes visible at a recorded boundary remains a real
// divergence at that same logical tick.
truthWorker.hold = true;
editedWorker.hold = true;
editedWorker.digestXor = 1;
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'BUSY');
const divergenceTick = host.logicalTick;
truthWorker.hold = false;
editedWorker.hold = false;
result = await host.settleCurrentCycle('final-cycle');
assert.equal(result.status, 'DIVERGED');
assert.equal(result.reason, 'semantic-digest');
assert.equal(host.logicalTick, divergenceTick);
host.terminate();

// Busy-phase transport is injected synchronously after the logical clock/release
// writes and before the workers receive an event-loop turn. Idle preparation may
// wait longer than one frame while logical time remains fixed.
MockWorker.instances.length = 0;
const phaseHost = new ReplayCertificationHost({
  WorkerCtor: MockWorker,
  truthWorkerUrl: 'truth.js',
  editedWorkerUrl: 'edited.js',
  randomReplaySpec: 'v1|',
  barrierTimeoutMs: 500,
});
await phaseHost.start(new ArrayBuffer(16));
const [phaseTruth, phaseEdited] = MockWorker.instances;
phaseTruth.hold = true;
phaseEdited.hold = true;
let hookCalled = false;
result = await phaseHost.pulse({
  allowCycleRelease: true,
  afterClockAdvance: state => {
    hookCalled = true;
    assert.equal(state.tick, 1);
    assert.equal(state.cycle, 1);
    assert.equal(state.truthIdle, false);
    assert.equal(state.editedIdle, false);
    phaseHost.setKey(42, true);
    return null;
  },
});
assert.equal(hookCalled, true);
assert.equal(result.status, 'BUSY');
assert.equal(Atomics.load(phaseHost.truth.keys, 42), 1);
assert.equal(Atomics.load(phaseHost.edited.keys, 42), 1);
const phaseTick = phaseHost.logicalTick;

result = await phaseHost.prepareTransportPhase('busy');
assert.equal(result.status, 'BUSY');
assert.equal(result.transportPhase, 'busy');
assert.equal(phaseHost.logicalTick, phaseTick);

setTimeout(() => {
  phaseTruth.hold = false;
  phaseEdited.hold = false;
}, 35);
result = await phaseHost.prepareTransportPhase('idle');
assert.equal(result.status, 'MATCH');
assert.equal(result.replaySettled, true);
assert.equal(result.settleReason, 'transport-idle');
assert.equal(phaseHost.logicalTick, phaseTick);

result = await phaseHost.prepareTransportPhase('idle');
assert.equal(result.status, 'IDLE');
assert.equal(result.transportPhase, 'idle');
assert.equal(phaseHost.logicalTick, phaseTick);
phaseHost.terminate();

console.log('certification replay host tests: PASS');
