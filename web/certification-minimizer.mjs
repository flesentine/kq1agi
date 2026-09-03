import { canonicalizePlayRecordingV1, hashPlayRecordingV1 } from './certification-recording.mjs';

const RECORDING_SCHEMA = 'kq1agi-play-recording-v1';

function asInt(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? (n | 0) : fallback;
}

function stableValue(value) {
  if (Array.isArray(value)) return value.map(stableValue);
  if (!value || typeof value !== 'object') return value;
  const out = {};
  for (const key of Object.keys(value).sort()) out[key] = stableValue(value[key]);
  return out;
}

function optionalBoolean(object, key) {
  return object && key in object ? !!object[key] : null;
}

function optionalValue(object, key) {
  return object && key in object ? stableValue(object[key]) : null;
}

/**
 * Phase -1E deliberately preserves the exact first semantic mismatch rather than
 * accepting any later/nearby divergence as a successful reduction. Cycle number is
 * intentionally excluded: the semantic authority is the logical tick plus the
 * reason-specific mismatch identity, not worker completion timing.
 */
export function divergenceFingerprint(result) {
  if (!result || result.status !== 'DIVERGED') return null;
  const reason = String(result.reason ?? 'unknown');
  const identity = {
    status: 'DIVERGED',
    tick: asInt(result.tick, -1),
    reason,
  };

  if (reason === 'trace' || reason === 'semantic-digest' || reason === 'random-stream') {
    identity.index = Number.isFinite(Number(result.index)) ? asInt(result.index) : null;
    identity.truth = optionalValue(result, 'truth');
    identity.edited = optionalValue(result, 'edited');
  } else if (reason === 'external-event') {
    // Sound mismatches, unpaired sound queues, and worker failures all carry their
    // semantic identity in detail. Matching only detail.type would allow a different
    // sound/hash/flag or worker failure to be mistaken for the original divergence.
    identity.detail = stableValue(result.detail ?? null);
  } else if (reason === 'quit-state') {
    identity.truthQuit = optionalBoolean(result, 'truthQuit');
    identity.editedQuit = optionalBoolean(result, 'editedQuit');
    identity.truthQuitMarked = optionalBoolean(result, 'truthQuitMarked');
    identity.editedQuitMarked = optionalBoolean(result, 'editedQuitMarked');
  } else if (reason === 'quit-handshake') {
    identity.truthQuit = optionalBoolean(result, 'truthQuit');
    identity.editedQuit = optionalBoolean(result, 'editedQuit');
  } else {
    // Preserve all commonly-used mismatch payload fields for future categories
    // without accidentally binding to non-authoritative cycle/snapshot telemetry.
    identity.index = Number.isFinite(Number(result.index)) ? asInt(result.index) : null;
    identity.truth = optionalValue(result, 'truth');
    identity.edited = optionalValue(result, 'edited');
    identity.detail = stableValue(result.detail ?? null);
  }

  return JSON.stringify(stableValue(identity));
}

export function sameDivergence(result, target) {
  const targetFingerprint = typeof target === 'string' ? target : divergenceFingerprint(target);
  return !!targetFingerprint && divergenceFingerprint(result) === targetFingerprint;
}

function snapshotSourceRecordingV1(recording) {
  if (!recording || typeof recording !== 'object') return null;
  // Capture every replay-authoritative field synchronously before any async digest
  // work. The Phase -1D envelope is top-level frozen but its nested arrays are not.
  // Canonicalize that private copy immediately so every minimization layer sees the
  // same representation that the recording hash and replay engine authenticate.
  const rawSnapshot = {
    schema: recording.schema,
    completeFromStart: recording.completeFromStart,
    startTick: recording.startTick,
    finalTick: recording.finalTick,
    gameHash: recording.gameHash,
    gameBytes: recording.gameBytes,
    editConfigHash: recording.editConfigHash,
    overflowed: recording.overflowed,
    releaseTicks: [...(recording.releaseTicks ?? [])],
    events: [...(recording.events ?? [])].map(event =>
      event && typeof event === 'object' ? { ...event } : event),
    random: [...(recording.random ?? [])].map(draw =>
      draw && typeof draw === 'object' ? { ...draw } : draw),
  };
  const canonical = canonicalizePlayRecordingV1(rawSnapshot);
  return Object.freeze({ ...canonical, hash: recording.hash });
}

export async function snapshotVerifiedRecordingV1(recording) {
  const source = snapshotSourceRecordingV1(recording);
  if (!source || source.schema !== RECORDING_SCHEMA) {
    throw new Error(`Phase -1E requires a ${RECORDING_SCHEMA} recording.`);
  }
  if (!source.completeFromStart || asInt(source.startTick) !== 1) {
    throw new Error('Phase -1E requires a complete recording starting at logical tick 1.');
  }
  if (source.overflowed) {
    throw new Error('Phase -1E refuses to minimize an overflowed PLAY recording.');
  }
  if (asInt(source.finalTick) < 1) {
    throw new Error('Phase -1E requires a recording with at least one logical tick.');
  }
  const expectedHash = String(source.hash ?? '');
  if (!expectedHash) {
    throw new Error('Phase -1E requires the frozen Phase -1D recording hash.');
  }
  const actualHash = await hashPlayRecordingV1(source);
  if (actualHash !== expectedHash) {
    throw new Error(`Phase -1E source recording hash mismatch: expected ${expectedHash}, got ${actualHash}.`);
  }
  return source;
}

async function buildRecordingPrefixUnchecked(recording, finalTick) {
  const tick = asInt(finalTick);
  if (tick < 1 || tick > asInt(recording.finalTick)) {
    throw new RangeError(`Prefix finalTick must be between 1 and ${recording.finalTick}.`);
  }

  const prefix = {
    schema: recording.schema,
    completeFromStart: true,
    startTick: 1,
    finalTick: tick,
    gameHash: String(recording.gameHash ?? ''),
    gameBytes: Math.max(0, asInt(recording.gameBytes)),
    editConfigHash: String(recording.editConfigHash ?? ''),
    overflowed: false,
    releaseTicks: [...(recording.releaseTicks ?? [])]
      .map(value => asInt(value))
      .filter(value => value <= tick),
    events: [...(recording.events ?? [])]
      .filter(event => asInt(event?.tick) <= tick)
      .map(event => ({ ...event })),
    random: [...(recording.random ?? [])]
      .filter(draw => asInt(draw?.tick) <= tick)
      .map(draw => ({ ...draw })),
  };
  const hash = await hashPlayRecordingV1(prefix);
  return Object.freeze({ ...prefix, hash });
}

/**
 * Build a replay-valid prefix without inventing a checkpoint. The frozen Phase -1D
 * source hash is verified before any candidate is derived, so minimization cannot
 * silently launder a mutated/stale recording into a new hash-valid prefix.
 */
export async function buildRecordingPrefixV1(recording, finalTick) {
  const source = await snapshotVerifiedRecordingV1(recording);
  return buildRecordingPrefixUnchecked(source, finalTick);
}

export function focusRecordingAroundTick(recording, tick, radius = 60) {
  const center = Math.max(0, asInt(tick));
  const span = Math.max(0, asInt(radius));
  const startTick = Math.max(0, center - span);
  const endTick = Math.min(asInt(recording?.finalTick), center + span);
  const events = [...(recording?.events ?? [])].filter(event => {
    const eventTick = asInt(event?.tick);
    return eventTick >= startTick && eventTick <= endTick;
  });
  const random = [...(recording?.random ?? [])].filter(draw => {
    const drawTick = asInt(draw?.tick);
    return drawTick >= startTick && drawTick <= endTick;
  });
  const releaseTicks = [...(recording?.releaseTicks ?? [])]
    .map(value => asInt(value))
    .filter(value => value >= startTick && value <= endTick);
  return Object.freeze({ centerTick: center, startTick, endTick, events, random, releaseTicks });
}

function divergenceFromSummary(summary) {
  // Only an authoritative DIVERGED replay may satisfy minimization. Do not accept
  // stale diagnostic fields such as firstDivergence attached to a MATCH/STOPPED
  // summary by a caller or future wrapper.
  if (summary?.status !== 'DIVERGED') return null;
  return summary.firstDivergence ?? (summary?.result?.status === 'DIVERGED' ? summary.result : null);
}

/**
 * Find the shortest prefix, still starting at logical tick 1, that reproduces the
 * exact first divergence. The common case is one replay at the divergence tick.
 * A binary-search fallback handles any future contract where a later final boundary
 * is required to expose the same divergence.
 */
export async function minimizeDivergentPrefix(recording, targetResult, replayCandidate, options = {}) {
  if (typeof replayCandidate !== 'function') throw new TypeError('replayCandidate must be a function.');
  const source = await snapshotVerifiedRecordingV1(recording);

  const targetFingerprint = divergenceFingerprint(targetResult);
  if (!targetFingerprint) throw new Error('Phase -1E minimization requires a DIVERGED target result.');
  const targetTick = asInt(targetResult.tick);
  const originalFinalTick = asInt(source.finalTick);
  if (targetTick < 1 || targetTick > originalFinalTick) {
    throw new Error('Target divergence tick is outside the recording.');
  }

  const shouldStop = options.shouldStop ?? (() => false);
  const onAttempt = options.onAttempt ?? (() => {});
  const attempts = [];
  const stopped = () => Object.freeze({
    status: 'STOPPED', targetFingerprint, originalFinalTick, targetTick,
    attempts: Object.freeze([...attempts]),
  });
  const tryTick = async finalTick => {
    if (shouldStop()) return { stopped: true };
    // The immutable source was verified once at minimization start. Candidate hashes
    // remain freshly computed by the same Phase -1D canonical hash function.
    const candidate = await buildRecordingPrefixUnchecked(source, finalTick);
    const summary = await replayCandidate(candidate);
    const divergence = divergenceFromSummary(summary);
    const reproduced = sameDivergence(divergence, targetFingerprint);
    const attempt = Object.freeze({ finalTick, status: summary?.status ?? 'unknown', reproduced });
    attempts.push(attempt);
    onAttempt(attempt);
    return { candidate, summary, divergence, reproduced, stopped: false };
  };

  let best = await tryTick(targetTick);
  if (best.stopped) return stopped();
  if (!best.reproduced) {
    let low = targetTick + 1;
    let high = originalFinalTick;
    let verified = null;
    while (low <= high) {
      if (shouldStop()) return stopped();
      const mid = Math.floor((low + high) / 2);
      const probe = await tryTick(mid);
      if (probe.stopped) return stopped();
      if (probe.reproduced) {
        verified = probe;
        best = probe;
        high = mid - 1;
      } else {
        low = mid + 1;
      }
    }
    if (!verified) {
      const fullAlreadyTried = attempts.some(attempt => attempt.finalTick === originalFinalTick);
      const full = fullAlreadyTried ? null : await tryTick(originalFinalTick);
      if (full?.stopped) return stopped();
      if (full?.reproduced) best = full;
      else {
        return Object.freeze({
          status: 'NOT_REPRODUCED',
          targetFingerprint,
          originalFinalTick,
          targetTick,
          attempts: Object.freeze([...attempts]),
        });
      }
    }
  }

  return Object.freeze({
    status: 'MINIMIZED',
    targetFingerprint,
    targetTick,
    originalFinalTick,
    minimizedFinalTick: best.candidate.finalTick,
    removedTicks: originalFinalTick - best.candidate.finalTick,
    recording: best.candidate,
    replaySummary: best.summary,
    attempts: Object.freeze([...attempts]),
    // Keep context after the divergence for debugging even though the authoritative
    // replay prefix stops at the minimized final boundary.
    focus: focusRecordingAroundTick(source, targetTick, options.focusRadius ?? 60),
  });
}
