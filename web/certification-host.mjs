const VAR = Object.freeze({
  SECONDS: 11,
  MINUTES: 12,
  HOURS: 13,
  DAYS: 14,
  TOTAL_TICKS: 512,
  MOUSE_BUTTON: 513,
  MOUSE_X: 514,
  MOUSE_Y: 515,
  OLD_MOUSE_BUTTON: 516,
  IN_TICK: 517,
  FLAGS_OFFSET: 256,
  // Pristine AGILE owns slots 0..517. The edited runtime extends the same shared
  // transport through slot 8352: editable/debug state plus the read-only Sierra
  // original-control snapshot used by ORIGINAL-vs-EDITED comparison.
  CORE_VARIABLE_SLOTS: 518,
  VARIABLE_SLOTS: 8353,
});

const DIGEST = Object.freeze({
  SCHEMA: 0,
  STATE0: 1,
  STATE1: 2,
  STATE2: 3,
  STATE3: 4,
  RANDOM_DRAWS: 5,
  ROOM: 6,
  QUIT: 7,
  SNAPSHOT_REQUEST: 8,
  SNAPSHOT_ACK: 9,
  CHECKPOINT_REQUEST: 10,
  CHECKPOINT_ACK: 11,
  CHECKPOINT_STATUS: 12,
  SEMANTIC_SLOTS: 8,
});

const DEFAULTS = Object.freeze({
  width: 320,
  height: 200,
  keyCapacity: 256,
  traceSlots: 16,
  digestSlots: 13,
  checkpointSlots: 32768,
  variableSlots: VAR.VARIABLE_SLOTS,
  seed: 0x4b513142,
  barrierTimeoutMs: 3000,
  maxBarrierPulses: 3600,
});

function assertSharedArrayBuffer() {
  if (typeof SharedArrayBuffer === 'undefined' || typeof Atomics === 'undefined') {
    throw new Error('Certification requires SharedArrayBuffer + Atomics (cross-origin isolation in browsers).');
  }
}

export function createLaneBuffers(options = {}) {
  assertSharedArrayBuffer();
  const width = options.width ?? DEFAULTS.width;
  const height = options.height ?? DEFAULTS.height;
  const keyCapacity = options.keyCapacity ?? DEFAULTS.keyCapacity;
  const traceSlots = options.traceSlots ?? DEFAULTS.traceSlots;
  const digestSlots = options.digestSlots ?? DEFAULTS.digestSlots;
  const checkpointSlots = options.checkpointSlots ?? DEFAULTS.checkpointSlots;
  const variableSlots = options.variableSlots ?? DEFAULTS.variableSlots;
  if (digestSlots < 13) throw new Error('Certification digest needs at least 13 Uint32 slots.');
  if (checkpointSlots < 4096) throw new Error('Certification checkpoint transport needs at least 4096 Uint32 slots.');
  if (variableSlots < VAR.VARIABLE_SLOTS) {
    throw new Error(`Certification shared state needs at least ${VAR.VARIABLE_SLOTS} Int32 slots.`);
  }
  const queueSlots = keyCapacity + 1;
  const keyPressQueueSAB = new SharedArrayBuffer(8 + queueSlots * 4);
  const keysSAB = new SharedArrayBuffer(256 * 4);
  const oldKeysSAB = new SharedArrayBuffer(256 * 4);
  const variableSAB = new SharedArrayBuffer(variableSlots * 4);
  const pixelDataSAB = new SharedArrayBuffer(width * height * 4);
  const diagnosticTraceSAB = new SharedArrayBuffer(traceSlots * 4);
  const certificationDigestSAB = new SharedArrayBuffer(digestSlots * 4);
  const certificationCheckpointSAB = new SharedArrayBuffer(checkpointSlots * 4);
  return {
    keyCapacity, width, height, variableSlots, checkpointSlots,
    keyPressQueueSAB, keysSAB, oldKeysSAB, variableSAB, pixelDataSAB,
    diagnosticTraceSAB, certificationDigestSAB, certificationCheckpointSAB,
    queue: new Uint32Array(keyPressQueueSAB),
    keys: new Uint32Array(keysSAB),
    oldKeys: new Uint32Array(oldKeysSAB),
    vars: new Uint32Array(variableSAB),
    trace: new Uint32Array(diagnosticTraceSAB),
    digest: new Uint32Array(certificationDigestSAB),
    checkpointData: new Uint32Array(certificationCheckpointSAB),
  };
}

function queueCanPush(lane) {
  const storageCapacity = lane.keyCapacity + 1;
  const wr = Atomics.load(lane.queue, 0);
  const rd = Atomics.load(lane.queue, 1);
  return ((wr + 1) % storageCapacity) !== rd;
}

function queuePush(lane, value) {
  const storageCapacity = lane.keyCapacity + 1;
  const wr = Atomics.load(lane.queue, 0);
  lane.queue[2 + wr] = value >>> 0;
  Atomics.store(lane.queue, 0, (wr + 1) % storageCapacity);
}

function u8Set(vars, index, value) {
  Atomics.store(vars, index, value & 0xff);
}

function u8Get(vars, index) {
  return Atomics.load(vars, index) & 0xff;
}

function incU8(vars, index) {
  const next = (u8Get(vars, index) + 1) & 0xff;
  u8Set(vars, index, next);
  return next;
}

function advanceGameClock(vars) {
  if (incU8(vars, VAR.SECONDS) >= 60) {
    u8Set(vars, VAR.SECONDS, 0);
    if (incU8(vars, VAR.MINUTES) >= 60) {
      u8Set(vars, VAR.MINUTES, 0);
      if (incU8(vars, VAR.HOURS) >= 24) {
        u8Set(vars, VAR.HOURS, 0);
        incU8(vars, VAR.DAYS);
      }
    }
  }
}

function readTrace(lane) {
  return Array.from(lane.trace, value => value >>> 0);
}

function readSemanticDigest(lane) {
  return Array.from(lane.digest.slice(0, DIGEST.SEMANTIC_SLOTS), value => value >>> 0);
}

function copyU32(view) {
  return Array.from(view, value => value >>> 0);
}

function restoreU32(view, values) {
  if (!Array.isArray(values) || values.length !== view.length) {
    throw new Error('Checkpoint transport length mismatch: expected ' + view.length + ', got ' + (values?.length ?? 'missing') + '.');
  }
  for (let i = 0; i < view.length; i += 1) Atomics.store(view, i, Number(values[i]) >>> 0);
}

function snapshotLaneTransport(lane) {
  return Object.freeze({
    queue: Object.freeze(copyU32(lane.queue)),
    keys: Object.freeze(copyU32(lane.keys)),
    oldKeys: Object.freeze(copyU32(lane.oldKeys)),
    vars: Object.freeze(copyU32(lane.vars)),
    pixels: Object.freeze(copyU32(new Uint32Array(lane.pixelDataSAB))),
  });
}

function restoreLaneTransport(lane, snapshot) {
  restoreU32(lane.queue, snapshot?.queue);
  restoreU32(lane.keys, snapshot?.keys);
  restoreU32(lane.oldKeys, snapshot?.oldKeys);
  restoreU32(lane.vars, snapshot?.vars);
  restoreU32(new Uint32Array(lane.pixelDataSAB), snapshot?.pixels);
}

function readWorkerCheckpointPayload(lane) {
  const length = Atomics.load(lane.checkpointData, 0) >>> 0;
  if (length < 1 || length + 1 > lane.checkpointData.length) {
    throw new Error('Worker checkpoint payload length is invalid for ' + lane.name + '.');
  }
  return Object.freeze(Array.from(lane.checkpointData.slice(1, length + 1), value => value & 0xff));
}

function writeWorkerCheckpointPayload(lane, payload) {
  if (!Array.isArray(payload) || payload.length < 1 || payload.length + 1 > lane.checkpointData.length) {
    throw new Error('Checkpoint payload does not fit ' + lane.name + ' checkpoint transport.');
  }
  Atomics.store(lane.checkpointData, 0, payload.length >>> 0);
  for (let i = 0; i < payload.length; i += 1) {
    Atomics.store(lane.checkpointData, i + 1, Number(payload[i]) & 0xff);
  }
}

function fallbackCheckpointHash(bytes) {
  let hash = 0x811c9dc5;
  for (const byte of bytes) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
  return 'fnv1a32:' + hash.toString(16).padStart(8, '0');
}

function canonicalCheckpointTransport(snapshot) {
  return {
    queue: [...(snapshot?.queue ?? [])].map(value => Number(value) >>> 0),
    keys: [...(snapshot?.keys ?? [])].map(value => Number(value) >>> 0),
    oldKeys: [...(snapshot?.oldKeys ?? [])].map(value => Number(value) >>> 0),
    vars: [...(snapshot?.vars ?? [])].map(value => Number(value) >>> 0),
    pixels: [...(snapshot?.pixels ?? [])].map(value => Number(value) >>> 0),
  };
}

function canonicalCheckpointForHash(checkpoint) {
  return {
    schema: 'kq1agi-certification-checkpoint-v1',
    logicalTick: Number(checkpoint?.logicalTick) >>> 0,
    cycle: Number(checkpoint?.cycle) >>> 0,
    comparedCycle: Number(checkpoint?.comparedCycle) >>> 0,
    truthTrace: [...(checkpoint?.truthTrace ?? [])].map(value => Number(value) >>> 0),
    editedTrace: [...(checkpoint?.editedTrace ?? [])].map(value => Number(value) >>> 0),
    truthDigest: [...(checkpoint?.truthDigest ?? [])].map(value => Number(value) >>> 0),
    editedDigest: [...(checkpoint?.editedDigest ?? [])].map(value => Number(value) >>> 0),
    truthTransport: canonicalCheckpointTransport(checkpoint?.truthTransport),
    editedTransport: canonicalCheckpointTransport(checkpoint?.editedTransport),
    truthWorkerPayload: [...(checkpoint?.truthWorkerPayload ?? [])].map(value => Number(value) & 0xff),
    editedWorkerPayload: [...(checkpoint?.editedWorkerPayload ?? [])].map(value => Number(value) & 0xff),
    pendingSoundCompletions: [...(checkpoint?.pendingSoundCompletions ?? [])].map(event => ({
      dueTick: Number(event?.dueTick) >>> 0,
      endFlag: Number(event?.endFlag) & 0xff,
    })),
  };
}

export async function hashCertificationCheckpointV1(checkpoint) {
  const bytes = new TextEncoder().encode(JSON.stringify(canonicalCheckpointForHash(checkpoint)));
  if (globalThis.crypto?.subtle?.digest) {
    const digest = new Uint8Array(await globalThis.crypto.subtle.digest('SHA-256', bytes));
    return 'sha256:' + Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('');
  }
  return fallbackCheckpointHash(bytes);
}
function firstDifference(a, b) {
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i += 1) {
    if ((a[i] ?? null) !== (b[i] ?? null)) return i;
  }
  return -1;
}

function hashArrayBuffer(buffer) {
  if (!(buffer instanceof ArrayBuffer)) return 0;
  const bytes = new Uint8Array(buffer);
  let hash = 0x811c9dc5;
  for (let i = 0; i < bytes.length; i += 1) {
    hash = Math.imul(hash ^ bytes[i], 0x01000193) >>> 0;
  }
  return hash >>> 0;
}

function parseWavDurationTicks(buffer) {
  try {
    const view = new DataView(buffer);
    if (view.byteLength < 44) return 1;
    const fourCC = offset => String.fromCharCode(
      view.getUint8(offset), view.getUint8(offset + 1), view.getUint8(offset + 2), view.getUint8(offset + 3)
    );
    if (fourCC(0) !== 'RIFF' || fourCC(8) !== 'WAVE') return 1;
    let offset = 12;
    let byteRate = 0;
    let dataBytes = 0;
    while (offset + 8 <= view.byteLength) {
      const id = fourCC(offset);
      const size = view.getUint32(offset + 4, true);
      const payload = offset + 8;
      if (id === 'fmt ' && size >= 16 && payload + 12 <= view.byteLength) {
        byteRate = view.getUint32(payload + 8, true);
      } else if (id === 'data') {
        dataBytes = Math.min(size, Math.max(0, view.byteLength - payload));
        break;
      }
      offset = payload + size + (size & 1);
    }
    if (!byteRate || !dataBytes) return 1;
    return Math.max(1, Math.ceil((dataBytes / byteRate) * 60));
  } catch {
    return 1;
  }
}

function makeLane(name, WorkerCtor, workerUrl, options) {
  const buffers = createLaneBuffers(options);
  return {
    name,
    worker: new WorkerCtor(workerUrl),
    ...buffers,
    ready: false,
    quit: false,
    error: null,
    soundRequests: [],
    snapshotAck: 0,
  };
}

function cloneArrayBuffer(buffer) {
  if (!(buffer instanceof ArrayBuffer)) throw new TypeError('encodedGameFileBuffer must be an ArrayBuffer');
  return buffer.slice(0);
}

function isIdle(lane) {
  return Atomics.load(lane.vars, VAR.IN_TICK) === 0;
}

function isQuitMarked(lane) {
  return Atomics.load(lane.digest, DIGEST.QUIT) === 1;
}

export class CertificationHost {
  constructor(options = {}) {
    assertSharedArrayBuffer();
    const WorkerCtor = options.WorkerCtor ?? globalThis.Worker;
    if (!WorkerCtor) throw new Error('CertificationHost requires a Worker constructor.');
    this.seed = (options.seed ?? DEFAULTS.seed) | 0;
    this.barrierTimeoutMs = options.barrierTimeoutMs ?? DEFAULTS.barrierTimeoutMs;
    this.maxBarrierPulses = options.maxBarrierPulses ?? DEFAULTS.maxBarrierPulses;
    this.truth = makeLane('truth', WorkerCtor, options.truthWorkerUrl ?? '/truth-worker/worker.nocache.js', options);
    this.edited = makeLane('edited', WorkerCtor, options.editedWorkerUrl ?? '/edited-worker/worker.nocache.js', options);
    this.logicalTick = 0;
    this.cycle = 0;
    // Highest interpreter cycle whose shared idle barrier has been certified.
    // A worker can finish after pulse() returns BUSY but before the next pulse;
    // this prevents that completed barrier from being skipped by releasing a new cycle.
    this.comparedCycle = 0;
    this.snapshotEpoch = 0;
    this.checkpointEpoch = 0;
    this.pendingSoundCompletions = [];
    this.pendingExternalDivergence = null;
    this.started = false;
    this._readyResolvers = [];
    this._installLaneHandler(this.truth);
    this._installLaneHandler(this.edited);
  }

  _installLaneHandler(lane) {
    lane.worker.onmessage = event => this._handleLaneMessage(lane, event.data);
    lane.worker.onerror = error => {
      lane.error = error;
      this.pendingExternalDivergence ??= { type: 'worker-error', lane: lane.name, message: String(error?.message ?? error) };
    };
  }

  _handleLaneMessage(lane, data) {
    const name = data?.name;
    if (name === 'CertificationReady') {
      lane.ready = true;
      this._flushReadyResolvers();
      return;
    }
    if (name === 'CertificationSnapshotReady') {
      lane.snapshotAck = Number(data?.object?.epoch ?? 0) >>> 0;
      return;
    }
    if (name === 'QuitGame') {
      lane.quit = true;
      return;
    }
    if (name === 'PlaySound') {
      const buffer = data?.buffer;
      lane.soundRequests.push({
        type: 'play',
        endFlag: Number(data?.object?.endFlag ?? 0) & 0xff,
        durationTicks: buffer instanceof ArrayBuffer ? parseWavDurationTicks(buffer) : 1,
        wavHash: hashArrayBuffer(buffer),
      });
      this._pairSoundRequests();
      return;
    }
    if (name === 'StopSound') {
      lane.soundRequests.push({ type: 'stop' });
      this._pairSoundRequests();
    }
  }

  _pairSoundRequests() {
    while (this.truth.soundRequests.length && this.edited.soundRequests.length && !this.pendingExternalDivergence) {
      const truth = this.truth.soundRequests.shift();
      const edited = this.edited.soundRequests.shift();
      const same = truth.type === edited.type
        && truth.endFlag === edited.endFlag
        && truth.durationTicks === edited.durationTicks
        && truth.wavHash === edited.wavHash;
      if (!same) {
        this.pendingExternalDivergence = { type: 'sound-event', truth, edited };
        return;
      }
      // AGILE has one current sound. Stop or replacement cancels the old completion.
      this.pendingSoundCompletions.length = 0;
      if (truth.type === 'play') {
        this.pendingSoundCompletions.push({
          dueTick: this.logicalTick + Math.max(1, truth.durationTicks),
          endFlag: truth.endFlag,
        });
      }
    }
  }

  _flushReadyResolvers() {
    if (!this.truth.ready || !this.edited.ready) return;
    const pending = this._readyResolvers.splice(0);
    for (const resolve of pending) resolve();
  }

  async start(encodedGameFileBuffer) {
    if (this.started) throw new Error('CertificationHost.start() may only be called once.');
    this.started = true;
    const truthGame = cloneArrayBuffer(encodedGameFileBuffer);
    const editedGame = cloneArrayBuffer(encodedGameFileBuffer);
    for (const lane of [this.truth, this.edited]) {
      lane.worker.postMessage({
        name: 'Initialise',
        object: {
          keyPressQueueSAB: lane.keyPressQueueSAB,
          keysSAB: lane.keysSAB,
          oldKeysSAB: lane.oldKeysSAB,
          variableSAB: lane.variableSAB,
          pixelDataSAB: lane.pixelDataSAB,
          diagnosticTraceSAB: lane.diagnosticTraceSAB,
          certificationDigestSAB: lane.certificationDigestSAB,
          certificationCheckpointSAB: lane.certificationCheckpointSAB,
          certificationMode: true,
          certificationSeed: this.seed,
        },
      });
    }
    this.truth.worker.postMessage({ name: 'Start', buffer: truthGame }, [truthGame]);
    this.edited.worker.postMessage({ name: 'Start', buffer: editedGame }, [editedGame]);
    await this._waitReady();
  }

  _waitReady() {
    if (this.truth.ready && this.edited.ready) return Promise.resolve();
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => reject(new Error('Timed out waiting for both certification workers to become ready.')), this.barrierTimeoutMs);
      this._readyResolvers.push(() => { clearTimeout(timer); resolve(); });
    });
  }

  setKey(keyCode, pressed) {
    const value = pressed ? 1 : 0;
    for (const lane of [this.truth, this.edited]) Atomics.store(lane.keys, keyCode & 0xff, value);
  }

  enqueueKey(encodedKey) {
    if (!queueCanPush(this.truth) || !queueCanPush(this.edited)) {
      throw new Error('Certification key queue is full; refusing to desynchronise the two lanes.');
    }
    queuePush(this.truth, encodedKey);
    queuePush(this.edited, encodedKey);
  }

  setMouse(x, y, button) {
    for (const lane of [this.truth, this.edited]) {
      Atomics.store(lane.vars, VAR.MOUSE_X, x | 0);
      Atomics.store(lane.vars, VAR.MOUSE_Y, y | 0);
      Atomics.store(lane.vars, VAR.MOUSE_BUTTON, button | 0);
    }
  }

  _applyExternalEvents(nextTick) {
    const due = [];
    const later = [];
    for (const event of this.pendingSoundCompletions) (event.dueTick <= nextTick ? due : later).push(event);
    this.pendingSoundCompletions = later;
    for (const event of due) {
      for (const lane of [this.truth, this.edited]) {
        Atomics.store(lane.vars, VAR.FLAGS_OFFSET + event.endFlag, 1);
      }
    }
  }

  _advanceLogicalClock(lane) {
    const total = (Atomics.load(lane.vars, VAR.TOTAL_TICKS) + 1) >>> 0;
    Atomics.store(lane.vars, VAR.TOTAL_TICKS, total);
    if ((total % 60) === 0) advanceGameClock(lane.vars);
  }

  async _synchronizeBarrierSnapshot() {
    if (!isIdle(this.truth) || !isIdle(this.edited)) throw new Error('Cannot snapshot while a certification lane is busy.');
    const epoch = (++this.snapshotEpoch) >>> 0 || (++this.snapshotEpoch) >>> 0;
    for (const lane of [this.truth, this.edited]) {
      Atomics.store(lane.digest, DIGEST.SNAPSHOT_REQUEST, epoch);
    }
    const deadline = Date.now() + this.barrierTimeoutMs;
    while (this.truth.snapshotAck !== epoch || this.edited.snapshotAck !== epoch) {
      if (this.truth.error || this.edited.error) throw new Error('Certification worker failed during snapshot synchronization.');
      if (Date.now() > deadline) throw new Error(`Timed out synchronizing certification snapshot ${epoch}.`);
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    // Each worker posts SnapshotReady only after publishing its snapshot. Messages
    // posted earlier by that same worker (including sound events) are ordered before it.
    this._pairSoundRequests();
    if (this.truth.soundRequests.length || this.edited.soundRequests.length) {
      this.pendingExternalDivergence ??= {
        type: 'unpaired-sound-event',
        truth: [...this.truth.soundRequests],
        edited: [...this.edited.soundRequests],
      };
    }
    return epoch;
  }

  async _requestCheckpointProbe(action) {
    if (!this.started || !this.truth.ready || !this.edited.ready) {
      throw new Error('CertificationHost is not ready for checkpoint probing.');
    }
    if (!isIdle(this.truth) || !isIdle(this.edited)) {
      throw new Error('Checkpoint probing requires both certification lanes to be idle.');
    }
    const actionCode = action === 'capture' ? 1 : action === 'restore' ? 2 : 0;
    if (!actionCode) throw new Error('Unknown checkpoint probe action: ' + action);
    const epoch = (++this.checkpointEpoch) >>> 0 || (++this.checkpointEpoch) >>> 0;
    const request = ((epoch << 2) | actionCode) >>> 0;
    for (const lane of [this.truth, this.edited]) {
      Atomics.store(lane.digest, DIGEST.CHECKPOINT_STATUS, 0);
      Atomics.store(lane.digest, DIGEST.CHECKPOINT_REQUEST, request);
    }
    const deadline = Date.now() + this.barrierTimeoutMs;
    while (Atomics.load(this.truth.digest, DIGEST.CHECKPOINT_ACK) !== request
        || Atomics.load(this.edited.digest, DIGEST.CHECKPOINT_ACK) !== request) {
      if (this.truth.error || this.edited.error) throw new Error('Certification worker failed during checkpoint probe.');
      if (Date.now() > deadline) throw new Error('Timed out waiting for checkpoint ' + action + ' acknowledgement.');
      await new Promise(resolve => setTimeout(resolve, 0));
    }
    return {
      request,
      truthStatus: Atomics.load(this.truth.digest, DIGEST.CHECKPOINT_STATUS) >>> 0,
      editedStatus: Atomics.load(this.edited.digest, DIGEST.CHECKPOINT_STATUS) >>> 0,
    };
  }

  async captureCheckpointProbe() {
    if (!isIdle(this.truth) || !isIdle(this.edited)) {
      throw new Error('Checkpoint capture requires both certification lanes to be idle.');
    }
    const snapshotEpoch = await this._synchronizeBarrierSnapshot();
    const baseline = this.compare(snapshotEpoch);
    if (baseline.status !== 'MATCH') {
      return { status: 'CHECKPOINT_BASELINE_REJECTED', baseline };
    }
    const capture = await this._requestCheckpointProbe('capture');
    if (capture.truthStatus === 4 || capture.editedStatus === 4) {
      return {
        status: 'CHECKPOINT_CAPTURE_UNAVAILABLE',
        reason: 'no-reconstructable-picture',
        baseline,
        capture,
      };
    }
    if (capture.truthStatus !== 1 || capture.editedStatus !== 1) {
      return { status: 'CHECKPOINT_CAPTURE_ERROR', baseline, capture };
    }
    const checkpoint = {
      status: 'CHECKPOINT_CAPTURED',
      schema: 'kq1agi-certification-checkpoint-v1',
      logicalTick: this.logicalTick,
      cycle: this.cycle,
      comparedCycle: this.comparedCycle,
      baseline,
      truthTrace: Object.freeze(readTrace(this.truth)),
      editedTrace: Object.freeze(readTrace(this.edited)),
      truthDigest: Object.freeze(readSemanticDigest(this.truth)),
      editedDigest: Object.freeze(readSemanticDigest(this.edited)),
      truthTransport: snapshotLaneTransport(this.truth),
      editedTransport: snapshotLaneTransport(this.edited),
      truthWorkerPayload: readWorkerCheckpointPayload(this.truth),
      editedWorkerPayload: readWorkerCheckpointPayload(this.edited),
      pendingSoundCompletions: Object.freeze(this.pendingSoundCompletions.map(event => Object.freeze({ ...event }))),
    };
    return Object.freeze({ ...checkpoint, hash: await hashCertificationCheckpointV1(checkpoint) });
  }

  async restoreCheckpointProbe(checkpoint) {
    if (!checkpoint || checkpoint.schema !== 'kq1agi-certification-checkpoint-v1') {
      throw new Error('Unknown Phase -1H checkpoint schema.');
    }
    const expectedHash = String(checkpoint.hash ?? '');
    const actualHash = await hashCertificationCheckpointV1(checkpoint);
    if (!expectedHash || expectedHash !== actualHash) {
      return { status: 'CHECKPOINT_HASH_MISMATCH', expectedHash, actualHash };
    }
    if (!isIdle(this.truth) || !isIdle(this.edited)) {
      throw new Error('Checkpoint restore requires both certification lanes to be idle.');
    }
    writeWorkerCheckpointPayload(this.truth, checkpoint.truthWorkerPayload);
    writeWorkerCheckpointPayload(this.edited, checkpoint.editedWorkerPayload);
    const restore = await this._requestCheckpointProbe('restore');
    if (restore.truthStatus !== 2 || restore.editedStatus !== 2) {
      return { status: 'CHECKPOINT_RESTORE_ERROR', restore };
    }

    restoreLaneTransport(this.truth, checkpoint.truthTransport);
    restoreLaneTransport(this.edited, checkpoint.editedTransport);
    this.logicalTick = Number(checkpoint.logicalTick) >>> 0;
    this.cycle = Number(checkpoint.cycle) >>> 0;
    this.comparedCycle = Number(checkpoint.comparedCycle) >>> 0;
    this.pendingSoundCompletions = (checkpoint.pendingSoundCompletions ?? []).map(event => ({ ...event }));
    this.pendingExternalDivergence = null;
    this.truth.soundRequests.length = 0;
    this.edited.soundRequests.length = 0;

    const snapshotEpoch = await this._synchronizeBarrierSnapshot();
    const actualTruthTrace = readTrace(this.truth);
    const actualEditedTrace = readTrace(this.edited);
    const actualTruthDigest = readSemanticDigest(this.truth);
    const actualEditedDigest = readSemanticDigest(this.edited);

    const lanes = [
      ['truth', checkpoint.truthTrace, actualTruthTrace, checkpoint.truthDigest, actualTruthDigest],
      ['edited', checkpoint.editedTrace, actualEditedTrace, checkpoint.editedDigest, actualEditedDigest],
    ];
    for (const lane of lanes) {
      const laneName = lane[0];
      const expectedTrace = lane[1];
      const actualTrace = lane[2];
      const expectedDigest = lane[3];
      const actualDigest = lane[4];
      const traceIndex = firstDifference(expectedTrace, actualTrace);
      if (traceIndex >= 0) {
        return {
          status: 'CHECKPOINT_NOT_EXACT', lane: laneName, category: 'trace', index: traceIndex,
          expected: expectedTrace[traceIndex], actual: actualTrace[traceIndex], expectedTrace, actualTrace,
        };
      }
      const digestIndex = firstDifference(expectedDigest, actualDigest);
      if (digestIndex >= 0) {
        return {
          status: 'CHECKPOINT_NOT_EXACT', lane: laneName,
          category: digestIndex === DIGEST.RANDOM_DRAWS ? 'random-stream' : 'semantic-digest',
          index: digestIndex, expected: expectedDigest[digestIndex], actual: actualDigest[digestIndex],
          expectedDigest, actualDigest,
        };
      }
    }

    const pair = this.compare(snapshotEpoch);
    if (pair.status !== 'MATCH') return { status: 'CHECKPOINT_NOT_EXACT', category: 'lane-pair', pair };
    return {
      status: 'CHECKPOINT_ROUNDTRIP_MATCH', scope: 'semantic-v1',
      tick: this.logicalTick, cycle: this.cycle, snapshotEpoch, pair,
    };
  }
  async _resolveQuitIfObserved() {
    const truthMarked = isQuitMarked(this.truth);
    const editedMarked = isQuitMarked(this.edited);
    if (!truthMarked && !editedMarked && !this.truth.quit && !this.edited.quit) return null;

    // QuitGame itself travels through independent postMessage queues, but the worker
    // first raises a shared quit marker. Freeze the logical clock as soon as either
    // marker is visible, then wait for the other lane to reach the same terminal
    // state instead of comparing message-arrival timing.
    const deadline = Date.now() + this.barrierTimeoutMs;
    while (!isQuitMarked(this.truth) || !isQuitMarked(this.edited)) {
      if (this.pendingExternalDivergence) {
        return { status: 'DIVERGED', tick: this.logicalTick, reason: 'external-event', detail: this.pendingExternalDivergence };
      }
      if (Date.now() > deadline) {
        return {
          status: 'DIVERGED', tick: this.logicalTick, cycle: this.cycle, reason: 'quit-state',
          truthQuit: this.truth.quit, editedQuit: this.edited.quit,
          truthQuitMarked: isQuitMarked(this.truth), editedQuitMarked: isQuitMarked(this.edited),
        };
      }
      await new Promise(resolve => setTimeout(resolve, 0));
    }

    // After setting QUIT and clearing IN_TICK, certification workers remain available
    // long enough to service one final barrier-snapshot request. This captures both
    // semantic states at the same frozen logical tick. Each worker posts QuitGame
    // before the SnapshotReady acknowledgement, so postMessage ordering also drains
    // all earlier sound events before this final comparison.
    const snapshotEpoch = await this._synchronizeBarrierSnapshot();
    if (!this.truth.quit || !this.edited.quit) {
      return {
        status: 'DIVERGED', tick: this.logicalTick, cycle: this.cycle, reason: 'quit-handshake',
        truthQuit: this.truth.quit, editedQuit: this.edited.quit,
      };
    }
    const finalResult = this.compare(snapshotEpoch);
    if (finalResult.status !== 'MATCH') return finalResult;
    this.comparedCycle = this.cycle;
    return {
      status: 'COMPLETE', scope: finalResult.scope, tick: this.logicalTick, cycle: this.cycle,
      snapshotEpoch, finalMatch: finalResult,
    };
  }

  /**
   * Advance one logical 1/60-second pulse. Time keeps moving while an interpreter
   * cycle is blocked; a new cycle is released only when both lanes are idle.
   */
  async pulse() {
    if (!this.started || !this.truth.ready || !this.edited.ready) throw new Error('CertificationHost is not ready.');
    const quitBefore = await this._resolveQuitIfObserved();
    if (quitBefore) return quitBefore;
    const bothIdleBefore = isIdle(this.truth) && isIdle(this.edited);
    // A worker sets the shared QUIT marker before clearing IN_TICK. If quit happened
    // between the first marker check and these idle loads, re-check now so a terminal
    // cycle cannot be mistaken for an ordinary barrier snapshot.
    const quitAtBarrier = await this._resolveQuitIfObserved();
    if (quitAtBarrier) return quitAtBarrier;
    // If the previous interpreter cycle completed between host pulses, certify that
    // exact shared barrier before time advances or another cycle is released. Without
    // this gate, a fast between-pulse completion could be skipped entirely.
    if (bothIdleBefore && this.cycle > this.comparedCycle) {
      const snapshotEpoch = await this._synchronizeBarrierSnapshot();
      const result = this.compare(snapshotEpoch);
      this.comparedCycle = this.cycle;
      return result;
    }
    const nextTick = this.logicalTick + 1;
    this._applyExternalEvents(nextTick);
    this._advanceLogicalClock(this.truth);
    this._advanceLogicalClock(this.edited);
    this.logicalTick = nextTick;

    if (bothIdleBefore) {
      Atomics.store(this.truth.vars, VAR.IN_TICK, 1);
      Atomics.store(this.edited.vars, VAR.IN_TICK, 1);
      this.cycle += 1;
    }

    await new Promise(resolve => setTimeout(resolve, 0));
    const quitAfter = await this._resolveQuitIfObserved();
    if (quitAfter) return quitAfter;
    const truthIdle = isIdle(this.truth);
    const editedIdle = isIdle(this.edited);
    if (!truthIdle || !editedIdle) {
      return { status: 'BUSY', tick: this.logicalTick, cycle: this.cycle, truthIdle, editedIdle };
    }

    const snapshotEpoch = await this._synchronizeBarrierSnapshot();
    const result = this.compare(snapshotEpoch);
    this.comparedCycle = this.cycle;
    return result;
  }

  async step(options = {}) {
    const maxPulses = options.maxPulses ?? this.maxBarrierPulses;
    for (let pulses = 1; pulses <= maxPulses; pulses += 1) {
      const result = await this.pulse();
      if (result.status === 'DIVERGED' || result.status === 'COMPLETE') return result;
      // Any non-BUSY result is a certified shared barrier. This also handles a
      // cycle that completed between an external pulse() and this step() call.
      if (result.status !== 'BUSY') return result;
    }
    if (this.truth.soundRequests.length || this.edited.soundRequests.length) {
      return {
        status: 'DIVERGED', tick: this.logicalTick, reason: 'external-event',
        detail: { type: 'sound-pair-timeout', truth: [...this.truth.soundRequests], edited: [...this.edited.soundRequests] },
      };
    }
    throw new Error(`Certification cycle did not reach a shared barrier after ${maxPulses} logical clock pulses.`);
  }

  compare(snapshotEpoch = this.snapshotEpoch) {
    if (this.pendingExternalDivergence) {
      return { status: 'DIVERGED', tick: this.logicalTick, reason: 'external-event', detail: this.pendingExternalDivergence };
    }
    if (!isIdle(this.truth) || !isIdle(this.edited)) {
      return { status: 'BUSY', tick: this.logicalTick, cycle: this.cycle, truthIdle: isIdle(this.truth), editedIdle: isIdle(this.edited) };
    }
    const truthTrace = readTrace(this.truth);
    const editedTrace = readTrace(this.edited);
    const traceIndex = firstDifference(truthTrace, editedTrace);
    if (traceIndex >= 0) {
      return {
        status: 'DIVERGED', tick: this.logicalTick, reason: 'trace', index: traceIndex,
        truth: truthTrace[traceIndex], edited: editedTrace[traceIndex], truthTrace, editedTrace,
      };
    }
    const truthDigest = readSemanticDigest(this.truth);
    const editedDigest = readSemanticDigest(this.edited);
    if (truthDigest[DIGEST.SCHEMA] !== 1 || editedDigest[DIGEST.SCHEMA] !== 1) {
      return { status: 'NOT_CERTIFIED', tick: this.logicalTick, reason: 'digest-not-ready', truthDigest, editedDigest };
    }
    const digestIndex = firstDifference(truthDigest, editedDigest);
    if (digestIndex >= 0) {
      return {
        status: 'DIVERGED', tick: this.logicalTick,
        reason: digestIndex === DIGEST.RANDOM_DRAWS ? 'random-stream' : 'semantic-digest',
        index: digestIndex, truth: truthDigest[digestIndex], edited: editedDigest[digestIndex], truthDigest, editedDigest,
      };
    }
    return {
      status: 'MATCH', scope: 'semantic-v1', tick: this.logicalTick, cycle: this.cycle, snapshotEpoch,
      room: truthTrace[2], x: truthTrace[3], y: truthTrace[4],
      randomDraws: truthDigest[DIGEST.RANDOM_DRAWS], digest: truthDigest.slice(1, 5),
    };
  }

  terminate() {
    for (const lane of [this.truth, this.edited]) lane.worker.terminate?.();
  }
}

export const CertificationLayout = Object.freeze({ VAR, DIGEST, DEFAULTS });
