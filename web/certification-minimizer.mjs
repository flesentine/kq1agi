import { hashPlayRecordingV1 } from './certification-recording.mjs';

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

/**
 * Phase -1E deliberately preserves the exact first semantic mismatch rather than
 * accepting any later/nearby divergence as a successful reduction.
 */
export function divergenceFingerprint(result) {
  if (!result || result.status !== 'DIVERGED') return null;
  return JSON.stringify(stableValue({
    status: 'DIVERGED',
    tick: asInt(result.tick, -1),
    reason: String(result.reason ?? 'unknown'),
    index: Number.isFinite(Number(result.index)) ? asInt(result.index) : null,
    truth: 'truth' in result ? result.truth : null,
    edited: 'edited' in result ? result.edited : null,
    detailType: result.detail?.type ?? null,
  }));
}

export function sameDivergence(result, target) {
  const targetFingerprint = typeof target === 'string' ? target : divergenceFingerprint(target);
  return !!targetFingerprint && divergenceFingerprint(result) === targetFingerprint;
}

/**
 * Build a replay-valid prefix without inventing a checkpoint. All identity fields
 * remain bound to the same game/EditConfig, while schedule, transport, and RNG data
 * after finalTick are removed and the recording hash is recomputed.
 */
export async function buildRecordingPrefixV1(recording, finalTick) {
  if (!recording || recording.schema !== 'kq1agi-play-recording-v1') {
    throw new Error('Phase -1E requires a kq1agi-play-recording-v1 recording.');
  }
  const tick = asInt(finalTick);
  if (tick < 1 || tick > asInt(recording.finalTick)) {
    throw new RangeError(`Prefix finalTick must be between 1 and ${recording.finalTick}.`);
  }

  const prefix = {
    schema: recording.schema,
    completeFromStart: !!recording.completeFromStart,
    startTick: asInt(recording.startTick),
    finalTick: tick,
    gameHash: String(recording.gameHash ?? ''),
    gameBytes: Math.max(0, asInt(recording.gameBytes)),
    editConfigHash: String(recording.editConfigHash ?? ''),
    overflowed: !!recording.overflowed,
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
  return summary?.firstDivergence ?? (summary?.result?.status === 'DIVERGED' ? summary.result : null);
}

/**
 * Find the shortest prefix, still starting at logical tick 1, that reproduces the
 * exact first divergence. The common case is one replay at the divergence tick.
 * A binary-search fallback handles any future contract where a later final boundary
 * is required to expose the same divergence.
 */
export async function minimizeDivergentPrefix(recording, targetResult, replayCandidate, options = {}) {
  if (typeof replayCandidate !== 'function') throw new TypeError('replayCandidate must be a function.');
  const targetFingerprint = divergenceFingerprint(targetResult);
  if (!targetFingerprint) throw new Error('Phase -1E minimization requires a DIVERGED target result.');
  const targetTick = asInt(targetResult.tick);
  const originalFinalTick = asInt(recording?.finalTick);
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
    const candidate = await buildRecordingPrefixV1(recording, finalTick);
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
    focus: focusRecordingAroundTick(recording, targetTick, options.focusRadius ?? 60),
  });
}
