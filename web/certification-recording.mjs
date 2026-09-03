const SCHEMA = 'kq1agi-play-recording-v1';
const VAR = Object.freeze({ TOTAL_TICKS: 512, IN_TICK: 517 });
const MAX_MOUSE_X = 0x7fffffff;
const MAX_MOUSE_Y = 0x7fffffff;

function rawBuffer() {
  const value = globalThis.__kq1agiPlayRecordingRaw;
  return Array.isArray(value) ? value : [];
}

function asInt(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? (n | 0) : fallback;
}

function asUint(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? (n >>> 0) : (fallback >>> 0);
}

function canonicalEvent(event) {
  const base = {
    tick: Math.max(0, asInt(event.tick)),
    seq: Math.max(0, asInt(event.seq)),
    phase: event.phase === 'busy' ? 'busy' : 'idle',
    type: String(event.type ?? ''),
  };
  if (base.type === 'key-state') {
    return { ...base, keyCode: asInt(event.keyCode) & 0xff, pressed: !!event.pressed };
  }
  if (base.type === 'key-queue') {
    return { ...base, encodedKey: asUint(event.encodedKey) };
  }
  if (base.type === 'mouse') {
    return {
      ...base,
      x: Math.max(-MAX_MOUSE_X, Math.min(MAX_MOUSE_X, asInt(event.x))),
      y: Math.max(-MAX_MOUSE_Y, Math.min(MAX_MOUSE_Y, asInt(event.y))),
      button: asInt(event.button),
    };
  }
  if (base.type === 'sound-end') {
    return { ...base, endFlag: asInt(event.endFlag) & 0xff };
  }
  return null;
}

function canonicalRandom(event) {
  const bound = asInt(event.bound);
  const value = asInt(event.value);
  if (bound <= 0 || value < 0 || value >= bound) return null;
  return {
    tick: Math.max(0, asInt(event.tick)),
    seq: Math.max(0, asInt(event.seq)),
    bound,
    value,
  };
}

function canonicalRecording(recording) {
  return {
    schema: SCHEMA,
    completeFromStart: !!recording.completeFromStart,
    startTick: Math.max(0, asInt(recording.startTick)),
    finalTick: Math.max(0, asInt(recording.finalTick)),
    gameHash: String(recording.gameHash ?? ''),
    gameBytes: Math.max(0, asInt(recording.gameBytes)),
    editConfigHash: String(recording.editConfigHash ?? ''),
    releaseTicks: [...(recording.releaseTicks ?? [])].map(value => Math.max(0, asInt(value))).sort((a, b) => a - b),
    events: [...(recording.events ?? [])].map(canonicalEvent).filter(Boolean).sort((a, b) => a.seq - b.seq),
    random: [...(recording.random ?? [])].map(canonicalRandom).filter(Boolean).sort((a, b) => a.seq - b.seq),
  };
}

function fallbackHash(bytes) {
  let hash = 0x811c9dc5;
  for (const byte of bytes) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
  return `fnv1a32:${hash.toString(16).padStart(8, '0')}`;
}

async function hashBytes(bytes) {
  const cryptoObject = globalThis.crypto;
  if (cryptoObject?.subtle?.digest) {
    const digest = new Uint8Array(await cryptoObject.subtle.digest('SHA-256', bytes));
    return `sha256:${Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('')}`;
  }
  return fallbackHash(bytes);
}

export async function hashArrayBufferV1(buffer) {
  if (!(buffer instanceof ArrayBuffer)) throw new TypeError('hashArrayBufferV1 requires an ArrayBuffer.');
  return hashBytes(new Uint8Array(buffer));
}

export async function hashPlayRecordingV1(recording) {
  const canonical = JSON.stringify(canonicalRecording(recording));
  return hashBytes(new TextEncoder().encode(canonical));
}

export function normalizePlayRecordingRaw(rawEvents = rawBuffer()) {
  const sorted = [...rawEvents]
    .filter(event => event && typeof event === 'object')
    .sort((a, b) => asInt(a.seq) - asInt(b.seq));
  const releaseTicks = [];
  const events = [];
  const random = [];
  const mouseByTick = new Map();
  let startTick = 0;
  let finalTick = 0;
  let firstPulse = null;

  for (const raw of sorted) {
    const type = String(raw.type ?? '');
    const tick = Math.max(0, asInt(raw.tick));
    finalTick = Math.max(finalTick, tick);
    if (type === 'pulse') {
      if (firstPulse == null) firstPulse = tick;
      if (raw.released) releaseTicks.push(tick);
      continue;
    }
    if (type === 'random') {
      const item = canonicalRandom(raw);
      if (item) random.push(item);
      continue;
    }
    const item = canonicalEvent(raw);
    if (!item) continue;
    if (item.type === 'mouse') {
      mouseByTick.set(item.tick, item);
    } else {
      events.push(item);
    }
  }

  events.push(...mouseByTick.values());
  events.sort((a, b) => a.seq - b.seq);
  random.sort((a, b) => a.seq - b.seq);
  releaseTicks.sort((a, b) => a - b);
  if (firstPulse != null) startTick = firstPulse;

  return {
    completeFromStart: firstPulse === 1,
    startTick,
    finalTick,
    releaseTicks,
    events,
    random,
  };
}

export function getPlayRecordingStats(rawEvents = rawBuffer()) {
  const normalized = normalizePlayRecordingRaw(rawEvents);
  return {
    completeFromStart: normalized.completeFromStart,
    startTick: normalized.startTick,
    finalTick: normalized.finalTick,
    releaseCount: normalized.releaseTicks.length,
    eventCount: normalized.events.length,
    randomCount: normalized.random.length,
    rawCount: Array.isArray(rawEvents) ? rawEvents.length : 0,
  };
}

export function clearPlayRecording() {
  if (Array.isArray(globalThis.__kq1agiPlayRecordingRaw)) globalThis.__kq1agiPlayRecordingRaw.length = 0;
  globalThis.__kq1agiPlayRecordingSeq = 0;
}

export async function freezePlayRecordingV1(options = {}) {
  const gameBuffer = options.gameBuffer;
  if (!(gameBuffer instanceof ArrayBuffer)) throw new TypeError('freezePlayRecordingV1 requires gameBuffer.');
  const normalized = normalizePlayRecordingRaw(options.rawEvents ?? rawBuffer());
  if (!normalized.completeFromStart) {
    throw new Error('The PLAY journal did not start at logical tick 1. Reload the page before reproducing the event so Phase -1D can replay from game start.');
  }
  if (normalized.finalTick < 1) throw new Error('No PLAY pulses have been recorded yet.');
  const editConfigHash = String(options.editConfig?.hash ?? options.editConfigHash ?? '');
  if (!editConfigHash) throw new Error('Phase -1D requires a frozen EditConfig v1 hash.');
  const base = canonicalRecording({
    ...normalized,
    gameHash: await hashArrayBufferV1(gameBuffer),
    gameBytes: gameBuffer.byteLength,
    editConfigHash,
  });
  return Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });
}

export function encodeRandomReplay(recording) {
  if (!recording || recording.schema !== SCHEMA) throw new Error('Unknown PLAY recording schema.');
  const body = (recording.random ?? []).map(draw => `${asInt(draw.bound)}:${asInt(draw.value)}`).join(';');
  return `v1|${body}`;
}

function applyEvent(host, event) {
  if (event.type === 'key-state') {
    host.setKey(event.keyCode, event.pressed);
    return;
  }
  if (event.type === 'key-queue') {
    host.enqueueKey(event.encodedKey);
    return;
  }
  if (event.type === 'mouse') {
    host.setMouse(event.x, event.y, event.button);
    return;
  }
  if (event.type === 'sound-end') {
    if (typeof host.injectSoundCompletion !== 'function') {
      throw new Error('CertificationHost does not support recorded sound completion timing.');
    }
    host.injectSoundCompletion(event.endFlag);
  }
}

export async function runCertificationReplaySession(host, recording, options = {}) {
  if (!host || typeof host.pulse !== 'function') throw new TypeError('A CertificationHost is required.');
  if (!recording || recording.schema !== SCHEMA) throw new Error('Unknown PLAY recording schema.');
  if (!recording.completeFromStart || recording.startTick !== 1) throw new Error('PLAY recording is not complete from logical tick 1.');
  const shouldStop = options.shouldStop ?? (() => false);
  const onUpdate = options.onUpdate ?? (() => {});
  const beforePulse = options.beforePulse ?? (() => {});
  const events = [...(recording.events ?? [])].sort((a, b) => a.seq - b.seq);
  const releaseSet = new Set((recording.releaseTicks ?? []).map(value => asInt(value)));
  let eventIndex = 0;
  let certifiedBarriers = 0;
  let consumedTicks = 0;
  let lastResult = null;

  const applyEventsThrough = tick => {
    while (eventIndex < events.length && asInt(events[eventIndex].tick) <= tick) {
      applyEvent(host, events[eventIndex]);
      eventIndex += 1;
    }
  };

  while (host.logicalTick < recording.finalTick) {
    if (shouldStop()) return { status: 'STOPPED', certifiedBarriers, consumedTicks, result: lastResult };
    applyEventsThrough(host.logicalTick);
    await beforePulse(host);

    const targetTick = host.logicalTick + 1;
    const releaseExpected = releaseSet.has(targetTick);
    const beforeTick = host.logicalTick;
    const beforeCycle = host.cycle;
    const result = await host.pulse({ allowCycleRelease: releaseExpected });
    lastResult = result;

    if (result.status === 'DIVERGED' || result.status === 'COMPLETE') {
      onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result });
      return { status: result.status, certifiedBarriers, consumedTicks, result, firstDivergence: result.status === 'DIVERGED' ? result : null };
    }

    if (result.status === 'MATCH') certifiedBarriers += 1;

    if (host.logicalTick === beforeTick) {
      onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result, barrierOnly: true });
      continue;
    }

    consumedTicks += 1;
    const released = host.cycle > beforeCycle;
    if (releaseExpected !== released) {
      const miss = {
        status: 'REPLAY_TIMING_MISS',
        tick: host.logicalTick,
        cycle: host.cycle,
        expectedRelease: releaseExpected,
        released,
        truthIdle: result.truthIdle,
        editedIdle: result.editedIdle,
      };
      onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result: miss });
      return { status: 'REPLAY_TIMING_MISS', certifiedBarriers, consumedTicks, result: miss };
    }

    onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result });
  }

  applyEventsThrough(recording.finalTick);
  return {
    status: 'REPLAY_MATCH',
    certifiedBarriers,
    consumedTicks,
    result: lastResult,
    finalTick: host.logicalTick,
  };
}

export const PlayRecordingLayout = Object.freeze({ SCHEMA, VAR });
