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

  publishSnapshot() {
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
    this.digest[6] = 1;
    this.digest[7] = 0;
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
          // Finish the interpreter cycle. The certification snapshot is deliberately
          // NOT captured here; the host will request it only after both lanes are idle.
          Atomics.store(this.vars, 517, 0);
        }

        if (Atomics.load(this.vars, 517) === 0) {
          const request = Atomics.load(this.digest, 8) >>> 0;
          const acknowledgement = Atomics.load(this.digest, 9) >>> 0;
          if (request !== 0 && request !== acknowledgement) {
            this.publishSnapshot();
            Atomics.store(this.digest, 9, request);
            queueMicrotask(() => this.onmessage?.({
              data: { name: 'CertificationSnapshotReady', object: { epoch: request } },
            }));
          }
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
  assert.equal(lane.variableSAB.byteLength, 8353 * 4);
  assert.equal(lane.variableSlots, 8353);
  assert.equal(lane.keyPressQueueSAB.byteLength, 8 + 257 * 4);
  assert.equal(lane.certificationDigestSAB.byteLength, 10 * 4);
  assert.throws(() => createLaneBuffers({ digestSlots: 9 }), /at least 10/);
  assert.throws(() => createLaneBuffers({ variableSlots: 8352 }), /at least 8353/);
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
  assert.equal(result.snapshotEpoch, 1);

  // Critical race test: truth finishes first, edited remains blocked, and logical
  // time continues. When edited finally returns, both lanes must republish at the
  // common barrier tick rather than comparing stale per-worker completion snapshots.
  const [truthWorker, editedWorker] = MockWorker.instances;
  editedWorker.hold = true;
  result = await host.pulse();
  assert.equal(result.status, 'BUSY');
  const blockedStartTick = host.logicalTick;
  await host.pulse();
  await host.pulse();
  assert.equal(host.logicalTick, blockedStartTick + 2);
  assert.equal(Atomics.load(host.truth.vars, 512), host.logicalTick);
  assert.equal(Atomics.load(host.edited.vars, 512), host.logicalTick);
  assert.equal(Atomics.load(host.truth.vars, 517), 0);
  assert.equal(Atomics.load(host.edited.vars, 517), 1);

  editedWorker.hold = false;
  result = await host.pulse();
  assert.equal(result.status, 'MATCH');
  assert.equal(host.truth.trace[1], host.logicalTick);
  assert.equal(host.edited.trace[1], host.logicalTick);
  assert.equal(host.truth.digest[9], result.snapshotEpoch);
  assert.equal(host.edited.digest[9], result.snapshotEpoch);

  // Time keeps AGILE's external one-second clock semantics.
  while (host.logicalTick < 60) result = await host.step();
  assert.equal(Atomics.load(host.truth.vars, 512), host.logicalTick);
  assert.equal(Atomics.load(host.edited.vars, 512), host.logicalTick);
  assert.ok(host.logicalTick >= 60);
  assert.equal(Atomics.load(host.truth.vars, 11), 1);
  assert.equal(result.status, 'MATCH');

  // Comparator still catches semantic drift at an already-synchronized barrier.
  host.edited.digest[2] ^= 1;
  result = host.compare();
  assert.equal(result.status, 'DIVERGED');
  assert.equal(result.reason, 'semantic-digest');

  // Ordered sound-event queues accept identical payloads and reject equal-duration
  // but byte-different WAVs.
  const wavA = new ArrayBuffer(48);
  const wavB = wavA.slice(0);
  new Uint8Array(wavB)[47] = 1;
  host.pendingExternalDivergence = null;
  host._handleLaneMessage(host.truth, { name: 'PlaySound', object: { endFlag: 7 }, buffer: wavA });
  host._handleLaneMessage(host.edited, { name: 'PlaySound', object: { endFlag: 7 }, buffer: wavA.slice(0) });
  assert.equal(host.pendingExternalDivergence, null);
  host._handleLaneMessage(host.truth, { name: 'PlaySound', object: { endFlag: 7 }, buffer: wavA });
  host._handleLaneMessage(host.edited, { name: 'PlaySound', object: { endFlag: 7 }, buffer: wavB });
  assert.equal(host.pendingExternalDivergence?.type, 'sound-event');

  truthWorker.hold = false;
  host.terminate();
}

assert.equal(CertificationLayout.VAR.CORE_VARIABLE_SLOTS, 518);
assert.equal(CertificationLayout.VAR.VARIABLE_SLOTS, 8353);
assert.equal(CertificationLayout.VAR.IN_TICK, 517);
assert.equal(CertificationLayout.DIGEST.SNAPSHOT_REQUEST, 8);
assert.equal(CertificationLayout.DIGEST.SNAPSHOT_ACK, 9);
console.log('certification host tests: PASS');