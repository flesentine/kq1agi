import assert from 'node:assert/strict';
import { CertificationHost, createLaneBuffers, CertificationLayout } from '../web/certification-host.mjs';

class MockWorker {
  static instances = [];

  constructor(url) {
    this.url = url;
    this.onmessage = null;
    this.onerror = null;
    this.terminated = false;
    this.hold = false;
    MockWorker.instances.push(this);
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
        if (!this.hold && Atomics.load(this.vars, 517) === 1) {
          this.trace[0] = 2;
          this.trace[1] = this.vars[512];
          this.trace[2] = 1;
          this.trace[3] = 50;
          this.trace[4] = 100;
          this.trace[15] = ((this.vars[14] & 255) << 24)
            | ((this.vars[13] & 255) << 16)
            | ((this.vars[12] & 255) << 8)
            | (this.vars[11] & 255);
          this.digest[0] = 1;
          this.digest[1] = this.vars[512] ^ 0x1111;
          this.digest[2] = 0x2222;
          this.digest[3] = 0x3333;
          this.digest[4] = 0x4444;
          this.digest[5] = 0;
          Atomics.store(this.vars, 517, 0);
        }
      }, 0);
    }
  }

  terminate() {
    this.terminated = true;
    clearInterval(this.timer);
  }
}

{
  const lane = createLaneBuffers();
  assert.equal(lane.variableSAB.byteLength, 518 * 4);
  assert.equal(lane.keyPressQueueSAB.byteLength, 8 + 257 * 4);
  assert.equal(lane.certificationDigestSAB.byteLength, 8 * 4);
}

{
  MockWorker.instances.length = 0;
  const host = new CertificationHost({ WorkerCtor: MockWorker, barrierTimeoutMs: 500 });
  await host.start(new ArrayBuffer(16));

  host.setKey(19, true);
  assert.equal(Atomics.load(host.truth.keys, 19), 1);
  assert.equal(Atomics.load(host.edited.keys, 19), 1);

  host.enqueueKey(0x10041);
  assert.equal(Atomics.load(host.truth.queue, 0), 1);
  assert.equal(Atomics.load(host.edited.queue, 0), 1);

  host.setMouse(123, 77, 1);
  assert.equal(Atomics.load(host.truth.vars, 514), 123);
  assert.equal(Atomics.load(host.edited.vars, 515), 77);

  let result = await host.step();
  assert.equal(result.status, 'MATCH');

  // Time must continue while an aligned interpreter cycle is blocked. This mirrors
  // AgileRunner.tick(), which advances TOTAL_TICKS/game clock outside the worker.
  for (const worker of MockWorker.instances) worker.hold = true;
  result = await host.pulse();
  assert.equal(result.status, 'BUSY');
  const beforeBlockedTicks = host.logicalTick;
  await host.pulse();
  await host.pulse();
  assert.equal(host.logicalTick, beforeBlockedTicks + 2);
  assert.equal(Atomics.load(host.truth.vars, 512), host.logicalTick);
  assert.equal(Atomics.load(host.edited.vars, 512), host.logicalTick);
  for (const worker of MockWorker.instances) worker.hold = false;
  // A pulse lets the blocked cycle finish; the following step releases the next one.
  await host.pulse();
  result = await host.step();
  assert.equal(result.status, 'MATCH');

  while (host.logicalTick < 60) result = await host.step();
  assert.equal(Atomics.load(host.truth.vars, 512), host.logicalTick);
  assert.equal(Atomics.load(host.edited.vars, 512), host.logicalTick);
  assert.ok(host.logicalTick >= 60);
  assert.equal(Atomics.load(host.truth.vars, 11), 1);
  assert.equal(result.status, 'MATCH');

  host.edited.digest[2] ^= 1;
  result = host.compare();
  assert.equal(result.status, 'DIVERGED');
  assert.equal(result.reason, 'semantic-digest');

  host.terminate();
}

assert.equal(CertificationLayout.VAR.IN_TICK, 517);
console.log('certification host tests: PASS');
