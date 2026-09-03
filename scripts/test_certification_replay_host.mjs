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

result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'MATCH');
assert.equal(host.logicalTick, 2);
assert.equal(host.cycle, 1);

host.injectSoundCompletion(7);
assert.equal(Atomics.load(host.truth.vars, 256 + 7), 1);
assert.equal(Atomics.load(host.edited.vars, 256 + 7), 1);

const wav = new ArrayBuffer(48);
host._handleLaneMessage(host.truth, { name: 'PlaySound', object: { endFlag: 9 }, buffer: wav });
host._handleLaneMessage(host.edited, { name: 'PlaySound', object: { endFlag: 9 }, buffer: wav.slice(0) });
assert.equal(host.pendingExternalDivergence, null);
assert.equal(host.pendingSoundCompletions.length, 0);

// End a recording on a release whose interpreter cycle is still in flight.
// settleCurrentCycle must wait without incrementing logical time, then publish the
// common final barrier and expose the replay RNG draw counts from that snapshot.
const [truthWorker, editedWorker] = MockWorker.instances;
truthWorker.hold = true;
editedWorker.hold = true;
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'BUSY');
assert.equal(host.logicalTick, 3);
assert.equal(host.cycle, 2);
const finalTick = host.logicalTick;
truthWorker.randomDraws = 2;
editedWorker.randomDraws = 2;
truthWorker.hold = false;
editedWorker.hold = false;
result = await host.settleCurrentCycle();
assert.equal(result.status, 'MATCH');
assert.equal(result.replaySettled, true);
assert.equal(host.logicalTick, finalTick);
assert.deepEqual(host.getReplayRandomDrawCounts(), { truth: 2, edited: 2 });

// A semantic difference that becomes visible only when the final busy cycle ends
// must still be caught at the same final logical tick.
truthWorker.hold = true;
editedWorker.hold = true;
editedWorker.digestXor = 1;
result = await host.pulse({ allowCycleRelease: true });
assert.equal(result.status, 'BUSY');
const divergenceTick = host.logicalTick;
truthWorker.hold = false;
editedWorker.hold = false;
result = await host.settleCurrentCycle();
assert.equal(result.status, 'DIVERGED');
assert.equal(result.reason, 'semantic-digest');
assert.equal(host.logicalTick, divergenceTick);

host.terminate();
console.log('certification replay host tests: PASS');
