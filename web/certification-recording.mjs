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
    overflowed: !!recording.overflowed,
    releaseTicks: [...(recording.releaseTicks ?? [])].map(value => Math.max(0, asInt(value))).sort((a, b) => a - b),
    events: [...(recording.events ?? [])].map(canonicalEvent).filter(Boolean).sort((a, b) => a.seq - b.seq),
    random: [...(recording.random ?? [])].map(canonicalRandom).filter(Boolean).sort((a, b) => a.seq - b.seq),
  };
}

export function canonicalizePlayRecordingV1(recording) {
  const canonical = canonicalRecording(recording ?? {});
  return Object.freeze({
    ...canonical,
    releaseTicks: Object.freeze([...canonical.releaseTicks]),
    events: Object.freeze(canonical.events.map(event => Object.freeze({ ...event }))),
    random: Object.freeze(canonical.random.map(draw => Object.freeze({ ...draw }))),
  });
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
    events.push(item);
  }

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
    overflowed: !!globalThis.__kq1agiPlayRecordingOverflow,
  };
}

export function clearPlayRecording() {
  if (Array.isArray(globalThis.__kq1agiPlayRecordingRaw)) globalThis.__kq1agiPlayRecordingRaw.length = 0;
  globalThis.__kq1agiPlayRecordingSeq = 0;
  globalThis.__kq1agiPlayRecordingOverflow = false;
}

export async function freezePlayRecordingV1(options = {}) {
  const gameBuffer = options.gameBuffer;
  if (!(gameBuffer instanceof ArrayBuffer)) throw new TypeError('freezePlayRecordingV1 requires gameBuffer.');
  const normalized = normalizePlayRecordingRaw(options.rawEvents ?? rawBuffer());
  const overflowed = options.overflowed ?? !!globalThis.__kq1agiPlayRecordingOverflow;
  if (overflowed) throw new Error('The PLAY journal reached its in-memory safety limit. Reload the page before reproducing the event again.');
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
    overflowed,
  });
  return Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });
}

export function encodeRandomReplay(recording) {
  if (!recording || recording.schema !== SCHEMA) throw new Error('Unknown PLAY recording schema.');
  // The recording hash is defined over canonical data. Replay must consume that
  // same canonical view so hash-equivalent representation changes (for example,
  // reordered-by-seq arrays or ignored malformed entries) cannot alter RNG behavior.
  const canonical = canonicalRecording(recording);
  const body = canonical.random.map(draw => `${draw.bound}:${draw.value}`).join(';');
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

function replayNow() {
  return globalThis.performance?.now?.() ?? Date.now();
}

function replaySleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function terminalReplaySummary(result, certifiedBarriers, consumedTicks) {
  if (result?.status === 'DIVERGED') {
    return {
      status: 'DIVERGED', certifiedBarriers, consumedTicks,
      result, firstDivergence: result,
    };
  }
  if (result?.status === 'COMPLETE') {
    return { status: 'COMPLETE', certifiedBarriers, consumedTicks, result };
  }
  if (result?.status === 'REPLAY_TIMING_MISS') {
    return { status: 'REPLAY_TIMING_MISS', certifiedBarriers, consumedTicks, result };
  }
  if (result?.status === 'REPLAY_CONTRACT_MISS') {
    return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result };
  }
  return null;
}

function buildTransportSchedule(events) {
  const byTick = new Map();
  let previousTick = -1;
  for (const event of events) {
    const tick = Math.max(0, asInt(event.tick));
    if (tick < previousTick) {
      return { error: { reason: 'transport-tick-order', previousTick, tick, seq: asInt(event.seq) } };
    }
    previousTick = tick;
    let bucket = byTick.get(tick);
    if (!bucket) {
      bucket = { busy: [], idle: [], sawIdle: false };
      byTick.set(tick, bucket);
    }
    if (event.phase === 'busy') {
      if (bucket.sawIdle) {
        return { error: { reason: 'transport-phase-order', tick, seq: asInt(event.seq) } };
      }
      bucket.busy.push(event);
    } else {
      bucket.sawIdle = true;
      bucket.idle.push(event);
    }
  }
  return { byTick };
}

function replayContractMiss(host, reason, extra = {}) {
  return {
    status: 'REPLAY_CONTRACT_MISS',
    reason,
    tick: host.logicalTick,
    cycle: host.cycle,
    ...extra,
  };
}

export async function runCertificationReplaySession(host, recording, options = {}) {
  if (!host || typeof host.pulse !== 'function') throw new TypeError('A CertificationHost is required.');
  if (!recording || recording.schema !== SCHEMA) throw new Error('Unknown PLAY recording schema.');
  if (!recording.completeFromStart || recording.startTick !== 1) throw new Error('PLAY recording is not complete from logical tick 1.');
  const expectedRecordingHash = String(recording.hash ?? '');
  const actualRecordingHash = await hashPlayRecordingV1(recording);
  if (!expectedRecordingHash || actualRecordingHash !== expectedRecordingHash) {
    const miss = replayContractMiss(host, 'recording-hash', {
      expectedRecordingHash,
      actualRecordingHash,
    });
    return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers: 0, consumedTicks: 0, result: miss };
  }

  // Execute exactly the same canonical representation that the hash authenticates.
  // This closes a subtle integrity gap where raw array ordering or malformed entries
  // could previously be hash-equivalent yet influence replay transport/RNG behavior.
  const replayRecording = canonicalRecording(recording);
  const shouldStop = options.shouldStop ?? (() => false);
  const onUpdate = options.onUpdate ?? (() => {});
  const beforePulse = options.beforePulse ?? (() => {});
  const pulseIntervalMs = Math.max(0, Number(options.pulseIntervalMs ?? (1000 / 60)) || 0);
  const events = [...replayRecording.events];
  const releaseSet = new Set(replayRecording.releaseTicks);
  const transport = buildTransportSchedule(events);
  let certifiedBarriers = 0;
  let consumedTicks = 0;
  let lastResult = null;
  let pacedTargetTick = 0;
  let nextPulseAt = replayNow();

  if (transport.error) {
    const miss = replayContractMiss(host, transport.error.reason, transport.error);
    return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result: miss };
  }
  const eventsByTick = transport.byTick;

  const processSettledResult = (result, targetTick, meta = {}) => {
    lastResult = result;
    if (result?.status === 'MATCH') certifiedBarriers += 1;
    const terminal = terminalReplaySummary(result, certifiedBarriers, consumedTicks);
    onUpdate({ certifiedBarriers, consumedTicks, targetTick, result, ...meta });
    return terminal;
  };

  const settleAtCurrentTick = async (reason, targetTick, meta = {}) => {
    if (typeof host.settleCurrentCycle !== 'function') {
      const miss = replayContractMiss(host, 'recorded-barrier-host', { reason, targetTick });
      return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result: miss };
    }
    const result = await host.settleCurrentCycle(reason);
    return processSettledResult(result, targetTick, { recordedBarrier: reason, ...meta });
  };

  const applyIdleEventsAt = async tick => {
    const bucket = eventsByTick.get(tick);
    if (!bucket?.idle.length) return null;

    // An idle-phase event proves normal PLAY's worker had completed at this logical
    // tick. Reproduce that semantic boundary by waiting at the same logical tick,
    // however long wall-clock execution takes, then apply the recorded transport.
    // Wall-clock speed is not allowed to turn into simulated game time.
    const settled = await settleAtCurrentTick('recorded-idle-event', tick, { transportPhase: 'idle' });
    if (settled) return settled;
    await beforePulse(host);
    for (const event of bucket.idle) applyEvent(host, event);
    bucket.idle.length = 0;
    onUpdate({
      certifiedBarriers, consumedTicks, targetTick: tick, result: lastResult,
      transportPhase: 'idle', transportApplied: true,
    });
    return null;
  };

  const initial = eventsByTick.get(host.logicalTick);
  if (initial?.busy.length) {
    const miss = replayContractMiss(host, 'transport-phase', {
      expectedPhase: 'busy', eventTick: host.logicalTick,
      detail: 'Busy transport cannot precede the first released interpreter cycle.',
    });
    return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result: miss };
  }
  const initialIdle = await applyIdleEventsAt(host.logicalTick);
  if (initialIdle) return initialIdle;

  while (host.logicalTick < replayRecording.finalTick) {
    if (shouldStop()) return { status: 'STOPPED', certifiedBarriers, consumedTicks, result: lastResult };

    const targetTick = host.logicalTick + 1;
    const releaseExpected = releaseSet.has(targetTick);

    // A recorded release at T means normal PLAY had observed the previous cycle as
    // complete before the T callback released the next one. If certification is
    // slower, wait here at T-1 and certify the completed cycle. Never advance the
    // logical clock merely because wall-clock time passed.
    if (releaseExpected) {
      const releaseBarrier = await settleAtCurrentTick('recorded-release', targetTick, { releaseExpected: true });
      if (releaseBarrier) return releaseBarrier;
      await beforePulse(host);
    }

    if (targetTick !== pacedTargetTick && pulseIntervalMs > 0) {
      if (pacedTargetTick !== 0) {
        nextPulseAt += pulseIntervalMs;
        const delayMs = nextPulseAt - replayNow();
        if (delayMs > 0) await replaySleep(delayMs);
        else nextPulseAt = replayNow();
      }
      pacedTargetTick = targetTick;
    }

    const beforeTick = host.logicalTick;
    const bucket = eventsByTick.get(targetTick);
    const busyEvents = bucket?.busy ?? [];
    const beforeCycle = host.cycle;
    const result = await host.pulse({
      allowCycleRelease: releaseExpected,
      afterClockAdvance: busyEvents.length ? phaseState => {
        // Busy is provenance, not a wall-clock deadline. Once replay releases the
        // recorded cycle (or carries forward an earlier in-flight cycle), inject
        // before yielding to either worker. This is the strongest deterministic
        // boundary available without claiming a Java instruction position.
        if (!releaseExpected && phaseState.truthIdle && phaseState.editedIdle) {
          return {
            status: 'REPLAY_CONTRACT_MISS',
            reason: 'transport-busy-without-cycle',
            tick: phaseState.tick,
            cycle: phaseState.cycle,
          };
        }
        for (const event of busyEvents) applyEvent(host, event);
        busyEvents.length = 0;
        return null;
      } : null,
    });
    lastResult = result;

    const terminal = terminalReplaySummary(result, certifiedBarriers, consumedTicks);
    if (terminal) {
      onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result });
      return terminal;
    }

    if (host.logicalTick === beforeTick) {
      // A Phase -1B barrier-only return consumes no recorded logical pulse.
      if (result.status === 'MATCH') certifiedBarriers += 1;
      onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result, barrierOnly: true });
      continue;
    }

    consumedTicks += 1;
    const released = host.cycle > beforeCycle;
    if (releaseExpected !== released) {
      const miss = {
        status: 'REPLAY_TIMING_MISS',
        reason: 'cycle-release',
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

    // Do not opportunistically count a barrier merely because a fast worker happened
    // to finish during pulse()'s one event-loop yield. Recorded release/idle markers
    // decide when a shared barrier is semantically required; the next settle call
    // publishes and compares that exact boundary independent of CPU speed.
    onUpdate({ certifiedBarriers, consumedTicks, targetTick, releaseExpected, result });
    const idleAfterPulse = await applyIdleEventsAt(targetTick);
    if (idleAfterPulse) return idleAfterPulse;
  }

  const finalIdle = await applyIdleEventsAt(replayRecording.finalTick);
  if (finalIdle) return finalIdle;
  const finalBucket = eventsByTick.get(replayRecording.finalTick);
  if (finalBucket?.busy.length) {
    const miss = replayContractMiss(host, 'transport-phase-unconsumed', {
      expectedPhase: 'busy', eventTick: replayRecording.finalTick, remainingEvents: finalBucket.busy.length,
    });
    return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result: miss };
  }

  // A recording is allowed to end while its final interpreter cycle is still busy.
  // Settle and compare that cycle at the same logical tick; never advance a made-up
  // extra pulse just to obtain a convenient barrier.
  if (typeof host.settleCurrentCycle === 'function') {
    const settleResult = await host.settleCurrentCycle();
    lastResult = settleResult;
    if (settleResult?.status === 'MATCH') certifiedBarriers += 1;
    const terminal = terminalReplaySummary(settleResult, certifiedBarriers, consumedTicks);
    if (terminal) {
      onUpdate({ certifiedBarriers, consumedTicks, targetTick: replayRecording.finalTick, result: settleResult, finalSettle: true });
      return terminal;
    }
    onUpdate({ certifiedBarriers, consumedTicks, targetTick: replayRecording.finalTick, result: settleResult, finalSettle: true });
  }

  // Both replay workers can agree with each other yet still have consumed only a
  // prefix of the recorded RNG stream. That is a reproduction-contract failure,
  // not an ORIGINAL-vs-EDITED semantic divergence.
  if (typeof host.getReplayRandomDrawCounts === 'function') {
    const counts = host.getReplayRandomDrawCounts();
    const expectedRandomDraws = replayRecording.random.length;
    if ((counts.truth >>> 0) !== expectedRandomDraws || (counts.edited >>> 0) !== expectedRandomDraws) {
      const miss = {
        status: 'REPLAY_CONTRACT_MISS',
        reason: 'random-stream-consumption',
        tick: host.logicalTick,
        cycle: host.cycle,
        expectedRandomDraws,
        truthRandomDraws: counts.truth >>> 0,
        editedRandomDraws: counts.edited >>> 0,
      };
      onUpdate({ certifiedBarriers, consumedTicks, targetTick: replayRecording.finalTick, result: miss, finalSettle: true });
      return { status: 'REPLAY_CONTRACT_MISS', certifiedBarriers, consumedTicks, result: miss };
    }
  }

  return {
    status: 'REPLAY_MATCH',
    certifiedBarriers,
    consumedTicks,
    result: lastResult,
    finalTick: host.logicalTick,
  };
}

export const PlayRecordingLayout = Object.freeze({ SCHEMA, VAR });
