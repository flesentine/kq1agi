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
  VARIABLE_SLOTS: 518,
});

const DEFAULTS = Object.freeze({
  width: 320,
  height: 200,
  keyCapacity: 256,
  traceSlots: 16,
  digestSlots: 8,
  seed: 0x4b513142,
  barrierTimeoutMs: 3000,
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
  const queueSlots = keyCapacity + 1;
  const keyPressQueueSAB = new SharedArrayBuffer(8 + queueSlots * 4);
  const keysSAB = new SharedArrayBuffer(256 * 4);
  const oldKeysSAB = new SharedArrayBuffer(256 * 4);
  const variableSAB = new SharedArrayBuffer(VAR.VARIABLE_SLOTS * 4);
  const pixelDataSAB = new SharedArrayBuffer(width * height * 4);
  const diagnosticTraceSAB = new SharedArrayBuffer(traceSlots * 4);
  const certificationDigestSAB = new SharedArrayBuffer(digestSlots * 4);
  return {
    keyCapacity,
    width,
    height,
    keyPressQueueSAB,
    keysSAB,
    oldKeysSAB,
    variableSAB,
    pixelDataSAB,
    diagnosticTraceSAB,
    certificationDigestSAB,
    queue: new Uint32Array(keyPressQueueSAB),
    keys: new Uint32Array(keysSAB),
    oldKeys: new Uint32Array(oldKeysSAB),
    vars: new Uint32Array(variableSAB),
    trace: new Uint32Array(diagnosticTraceSAB),
    digest: new Uint32Array(certificationDigestSAB),
  };
}

function queueCanPush(lane) {
  const q = lane.queue;
  const storageCapacity = lane.keyCapacity + 1;
  const wr = Atomics.load(q, 0);
  const rd = Atomics.load(q, 1);
  return ((wr + 1) % storageCapacity) !== rd;
}

function queuePush(lane, value) {
  const q = lane.queue;
  const storageCapacity = lane.keyCapacity + 1;
  const wr = Atomics.load(q, 0);
  q[2 + wr] = value >>> 0;
  Atomics.store(q, 0, (wr + 1) % storageCapacity);
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

function readDigest(lane) {
  return Array.from(lane.digest, value => value >>> 0);
}

function firstDifference(a, b) {
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i += 1) {
    if ((a[i] ?? null) !== (b[i] ?? null)) return i;
  }
  return -1;
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
  const worker = new WorkerCtor(workerUrl);
  return {
    name,
    worker,
    ...buffers,
    ready: false,
    quit: false,
    error: null,
    soundRequest: null,
  };
}

function cloneArrayBuffer(buffer) {
  if (!(buffer instanceof ArrayBuffer)) throw new TypeError('encodedGameFileBuffer must be an ArrayBuffer');
  return buffer.slice(0);
}

export class CertificationHost {
  constructor(options = {}) {
    assertSharedArrayBuffer();
    const WorkerCtor = options.WorkerCtor ?? globalThis.Worker;
    if (!WorkerCtor) throw new Error('CertificationHost requires a Worker constructor.');
    this.seed = (options.seed ?? DEFAULTS.seed) | 0;
    this.barrierTimeoutMs = options.barrierTimeoutMs ?? DEFAULTS.barrierTimeoutMs;
    this.truth = makeLane('truth', WorkerCtor, options.truthWorkerUrl ?? '/truth-worker/worker.nocache.js', options);
    this.edited = makeLane('edited', WorkerCtor, options.editedWorkerUrl ?? '/worker/worker.nocache.js', options);
    this.logicalTick = 0;
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
    if (name === 'QuitGame') {
      lane.quit = true;
      return;
    }
    if (name === 'PlaySound') {
      const endFlag = data?.object?.endFlag;
      const durationTicks = data?.buffer instanceof ArrayBuffer ? parseWavDurationTicks(data.buffer) : 1;
      lane.soundRequest = { tick: this.logicalTick, endFlag, durationTicks };
      this._pairSoundRequests();
      return;
    }
    if (name === 'StopSound') {
      lane.soundRequest = { tick: this.logicalTick, stop: true };
      this._pairSoundRequests();
    }
  }

  _pairSoundRequests() {
    const a = this.truth.soundRequest;
    const b = this.edited.soundRequest;
    if (!a || !b) return;
    this.truth.soundRequest = null;
    this.edited.soundRequest = null;
    if (Boolean(a.stop) !== Boolean(b.stop) || a.endFlag !== b.endFlag || a.durationTicks !== b.durationTicks) {
      this.pendingExternalDivergence ??= { type: 'sound-event', truth: a, edited: b };
      return;
    }
    if (a.stop) {
      this.pendingSoundCompletions.length = 0;
      return;
    }
    this.pendingSoundCompletions.push({
      dueTick: this.logicalTick + Math.max(1, a.durationTicks),
      endFlag: a.endFlag & 0xff,
    });
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

  async step() {
    if (!this.started || !this.truth.ready || !this.edited.ready) throw new Error('CertificationHost is not ready.');
    if (this.truth.quit !== this.edited.quit) {
      return { status: 'DIVERGED', tick: this.logicalTick, reason: 'quit-state', truthQuit: this.truth.quit, editedQuit: this.edited.quit };
    }
    if (this.truth.quit && this.edited.quit) return { status: 'COMPLETE', tick: this.logicalTick };
    await this._waitForIdle();
    const nextTick = this.logicalTick + 1;
    this._applyExternalEvents(nextTick);
    this._advanceLogicalClock(this.truth);
    this._advanceLogicalClock(this.edited);
    Atomics.store(this.truth.vars, VAR.IN_TICK, 1);
    Atomics.store(this.edited.vars, VAR.IN_TICK, 1);
    await this._waitForIdle();
    this.logicalTick = nextTick;
    await new Promise(resolve => setTimeout(resolve, 0));
    return this.compare();
  }

  async _waitForIdle() {
    const deadline = Date.now() + this.barrierTimeoutMs;
    while (Atomics.load(this.truth.vars, VAR.IN_TICK) !== 0 || Atomics.load(this.edited.vars, VAR.IN_TICK) !== 0) {
      if (Date.now() > deadline) {
        throw new Error(`Certification barrier timed out at logical tick ${this.logicalTick}.`);
      }
      await new Promise(resolve => setTimeout(resolve, 0));
    }
  }

  compare() {
    if (this.pendingExternalDivergence) {
      return { status: 'DIVERGED', tick: this.logicalTick, reason: 'external-event', detail: this.pendingExternalDivergence };
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
    const truthDigest = readDigest(this.truth);
    const editedDigest = readDigest(this.edited);
    if (truthDigest[0] !== 1 || editedDigest[0] !== 1) {
      return { status: 'NOT_CERTIFIED', tick: this.logicalTick, reason: 'digest-not-ready', truthDigest, editedDigest };
    }
    const digestIndex = firstDifference(truthDigest, editedDigest);
    if (digestIndex >= 0) {
      return {
        status: 'DIVERGED', tick: this.logicalTick, reason: digestIndex === 5 ? 'random-stream' : 'semantic-digest', index: digestIndex,
        truth: truthDigest[digestIndex], edited: editedDigest[digestIndex], truthDigest, editedDigest,
      };
    }
    return {
      status: 'MATCH', scope: 'semantic-v1', tick: this.logicalTick,
      room: truthTrace[2], x: truthTrace[3], y: truthTrace[4], randomDraws: truthDigest[5], digest: truthDigest.slice(1, 5),
    };
  }

  terminate() {
    for (const lane of [this.truth, this.edited]) lane.worker.terminate?.();
  }
}

export const CertificationLayout = Object.freeze({ VAR, DEFAULTS });
