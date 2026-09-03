import { hashPlayRecordingV1 } from './certification-recording.mjs';
import {
  divergenceFingerprint,
  sameDivergence,
  snapshotVerifiedRecordingV1,
} from './certification-minimizer.mjs';

const REMOVABLE_INPUT_TYPES = new Set(['key-state', 'key-queue', 'mouse']);

function asInt(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? (n | 0) : fallback;
}

function eventSeq(event) {
  return Math.max(0, asInt(event?.seq));
}

function eventTick(event) {
  return Math.max(0, asInt(event?.tick));
}

function sortedEvents(recording) {
  return [...(recording?.events ?? [])].sort((a, b) => eventSeq(a) - eventSeq(b));
}

function makeGroup(kind, members) {
  const events = [...members].sort((a, b) => eventSeq(a) - eventSeq(b));
  if (!events.length) return null;
  return {
    kind,
    startSeq: eventSeq(events[0]),
    endSeq: eventSeq(events[events.length - 1]),
    startTick: Math.min(...events.map(eventTick)),
    endTick: Math.max(...events.map(eventTick)),
    eventSeqs: events.map(eventSeq),
    eventTypes: [...new Set(events.map(event => String(event.type ?? '')))].sort(),
  };
}

function mergeIntervals(intervals) {
  const ordered = [...intervals].sort((a, b) => a.startSeq - b.startSeq || a.endSeq - b.endSeq);
  const out = [];
  for (const interval of ordered) {
    const last = out[out.length - 1];
    if (!last || interval.startSeq > last.endSeq) {
      out.push({ ...interval });
    } else {
      last.endSeq = Math.max(last.endSeq, interval.endSeq);
    }
  }
  return out;
}

function keyboardGroups(events) {
  const keyboard = events.filter(event => event.type === 'key-state' || event.type === 'key-queue');
  if (!keyboard.length) return [];

  // A physical key gesture is dependency-sensitive: deleting only its release can
  // synthesize a stuck key. Pair down->up for each key and merge overlapping
  // intervals so modifiers/chords become one atomic keyboard gesture.
  const open = new Map();
  const intervals = [];
  for (const event of keyboard) {
    if (event.type !== 'key-state') continue;
    const keyCode = asInt(event.keyCode) & 0xff;
    if (event.pressed) {
      if (!open.has(keyCode)) open.set(keyCode, eventSeq(event));
    } else if (open.has(keyCode)) {
      intervals.push({ startSeq: open.get(keyCode), endSeq: eventSeq(event) });
      open.delete(keyCode);
    }
  }

  const assigned = new Set();
  const groups = [];
  for (const interval of mergeIntervals(intervals)) {
    const members = keyboard.filter(event => {
      const seq = eventSeq(event);
      return seq >= interval.startSeq && seq <= interval.endSeq;
    });
    for (const event of members) assigned.add(eventSeq(event));
    const group = makeGroup('keyboard-gesture', members);
    if (group) groups.push(group);
  }

  // Queue-only events outside matched gestures are still removable as their original
  // synchronous-looking batch. Unmatched state fragments remain locked because the
  // frozen prefix does not contain enough information to prove a safe pair.
  let batch = [];
  const flush = () => {
    if (!batch.length) return;
    // An unmatched key-state fragment has no dependency-safe closing boundary in
    // this frozen prefix. Keep that fragment locked rather than pretending we can
    // remove only one side of an incomplete physical key gesture.
    if (!batch.some(event => event.type === 'key-state')) {
      const group = makeGroup('keyboard-queue', batch);
      if (group) groups.push(group);
    }
    batch = [];
  };
  for (const event of keyboard) {
    if (assigned.has(eventSeq(event))) continue;
    const prev = batch[batch.length - 1];
    const sameBatch = prev
      && eventSeq(event) === eventSeq(prev) + 1
      && eventTick(event) === eventTick(prev)
      && event.phase === prev.phase;
    if (!sameBatch) flush();
    batch.push(event);
  }
  flush();
  return groups;
}

function mouseBatches(events) {
  const mouse = events.filter(event => event.type === 'mouse');
  const batches = [];
  let batch = [];
  const flush = () => {
    if (batch.length) batches.push(batch);
    batch = [];
  };
  for (const event of mouse) {
    const prev = batch[batch.length - 1];
    const sameBatch = prev
      && eventSeq(event) === eventSeq(prev) + 1
      && eventTick(event) === eventTick(prev)
      && event.phase === prev.phase;
    if (!sameBatch) flush();
    batch.push(event);
  }
  flush();
  return batches;
}

function mouseGroups(events) {
  const batches = mouseBatches(events);
  const groups = [];
  let gesture = [];
  let button = 0;

  const flushGesture = () => {
    if (!gesture.length) return;
    const group = makeGroup('mouse-gesture', gesture.flat());
    if (group) groups.push(group);
    gesture = [];
  };

  for (const batch of batches) {
    const finalButton = asInt(batch[batch.length - 1]?.button);
    if (gesture.length) {
      gesture.push(batch);
      button = finalButton;
      if (button === 0) flushGesture();
      continue;
    }

    if (button === 0 && finalButton !== 0) {
      gesture = [batch];
      button = finalButton;
      continue;
    }

    if (button !== 0) {
      gesture = [batch];
      button = finalButton;
      if (button === 0) flushGesture();
      continue;
    }

    const group = makeGroup('mouse-move', batch);
    if (group) groups.push(group);
    button = finalButton;
  }
  flushGesture();
  return groups;
}

function finalizeGroups(groups) {
  return Object.freeze(
    [...groups]
      .sort((a, b) => a.startSeq - b.startSeq || a.endSeq - b.endSeq)
      .map((group, index) => Object.freeze({
        id: `input-${index + 1}`,
        ...group,
        eventSeqs: Object.freeze([...group.eventSeqs]),
        eventTypes: Object.freeze([...group.eventTypes]),
      })),
  );
}

/**
 * Dependency-safe Phase -1F grouping. Only user-input transport is removable.
 * Sound completions, RNG observations, and interpreter release timing remain frozen
 * reproduction authority.
 */
export function groupReplayInputEventsV1(recording) {
  const events = sortedEvents(recording);
  return finalizeGroups([
    ...keyboardGroups(events),
    ...mouseGroups(events),
  ]);
}

async function buildCandidateUnchecked(source, groups, keptGroupIds) {
  const keep = new Set(keptGroupIds);
  const removableSeqs = new Set();
  const keptSeqs = new Set();
  for (const group of groups) {
    for (const seq of group.eventSeqs) {
      removableSeqs.add(seq);
      if (keep.has(group.id)) keptSeqs.add(seq);
    }
  }

  const base = {
    schema: source.schema,
    completeFromStart: source.completeFromStart,
    startTick: source.startTick,
    finalTick: source.finalTick,
    gameHash: source.gameHash,
    gameBytes: source.gameBytes,
    editConfigHash: source.editConfigHash,
    overflowed: source.overflowed,
    releaseTicks: [...source.releaseTicks],
    events: source.events
      .filter(event => !removableSeqs.has(eventSeq(event)) || keptSeqs.has(eventSeq(event)))
      .map(event => ({ ...event })),
    random: source.random.map(draw => ({ ...draw })),
  };
  return Object.freeze({ ...base, hash: await hashPlayRecordingV1(base) });
}

export async function buildRecordingWithoutInputGroupsV1(recording, groupIdsToRemove = []) {
  const source = await snapshotVerifiedRecordingV1(recording);
  const groups = groupReplayInputEventsV1(source);
  const known = new Set(groups.map(group => group.id));
  const remove = new Set(groupIdsToRemove);
  for (const id of remove) {
    if (!known.has(id)) throw new Error(`Unknown Phase -1F input group: ${id}`);
  }
  const kept = groups.filter(group => !remove.has(group.id)).map(group => group.id);
  return buildCandidateUnchecked(source, groups, kept);
}

function divergenceFromSummary(summary) {
  if (summary?.status !== 'DIVERGED') return null;
  return summary.firstDivergence ?? (summary?.result?.status === 'DIVERGED' ? summary.result : null);
}

function partition(items, count) {
  if (!items.length) return [];
  const n = Math.max(1, Math.min(items.length, asInt(count, 1)));
  const chunks = [];
  let offset = 0;
  for (let i = 0; i < n; i += 1) {
    const remaining = items.length - offset;
    const slots = n - i;
    const size = Math.ceil(remaining / slots);
    chunks.push(items.slice(offset, offset + size));
    offset += size;
  }
  return chunks.filter(chunk => chunk.length);
}

function summaryStats(source, groups, keptIds, attempts, recording) {
  const kept = new Set(keptIds);
  const keptGroups = groups.filter(group => kept.has(group.id));
  const removedGroups = groups.filter(group => !kept.has(group.id));
  const inputSeqs = new Set(groups.flatMap(group => group.eventSeqs));
  const keptInputSeqs = new Set(keptGroups.flatMap(group => group.eventSeqs));
  return {
    recording,
    totalGroups: groups.length,
    keptGroups: Object.freeze(keptGroups),
    removedGroups: Object.freeze(removedGroups),
    totalInputEvents: inputSeqs.size,
    keptInputEvents: keptInputSeqs.size,
    removedInputEvents: inputSeqs.size - keptInputSeqs.size,
    lockedEvents: source.events.length - inputSeqs.size,
    attempts: Object.freeze([...attempts]),
  };
}

/**
 * Delta-debug dependency-safe user-input groups while preserving the exact Phase -1E
 * target divergence. The logical clock/release schedule, RNG stream, sound completion
 * timing, game identity, EditConfig identity, and final prefix boundary never move.
 */
export async function minimizeInputGroupsV1(recording, targetResult, replayCandidate, options = {}) {
  if (typeof replayCandidate !== 'function') throw new TypeError('replayCandidate must be a function.');
  const source = await snapshotVerifiedRecordingV1(recording);
  const targetFingerprint = divergenceFingerprint(targetResult);
  if (!targetFingerprint) throw new Error('Phase -1F requires a DIVERGED target result.');

  const groups = groupReplayInputEventsV1(source);
  const shouldStop = options.shouldStop ?? (() => false);
  const onAttempt = options.onAttempt ?? (() => {});
  const maxAttempts = Math.max(1, asInt(options.maxAttempts, 256));
  const attempts = [];
  const allIds = groups.map(group => group.id);
  let keptIds = [...allIds];
  let bestRecording = source;
  let budgetExhausted = false;

  const stopped = () => Object.freeze({
    status: 'STOPPED',
    targetFingerprint,
    ...summaryStats(source, groups, keptIds, attempts, bestRecording),
  });

  const runCandidate = async (candidateKeptIds, phase) => {
    if (shouldStop()) return { stopped: true };
    if (attempts.length >= maxAttempts) {
      budgetExhausted = true;
      return { budget: true };
    }
    const candidate = candidateKeptIds.length === groups.length
      ? source
      : await buildCandidateUnchecked(source, groups, candidateKeptIds);
    const summary = await replayCandidate(candidate);
    const divergence = divergenceFromSummary(summary);
    const reproduced = sameDivergence(divergence, targetFingerprint);
    const attempt = Object.freeze({
      number: attempts.length + 1,
      phase,
      keptGroups: candidateKeptIds.length,
      removedGroups: groups.length - candidateKeptIds.length,
      status: summary?.status ?? 'unknown',
      reproduced,
      recordingHash: candidate.hash,
    });
    attempts.push(attempt);
    onAttempt(attempt);
    return { candidate, summary, reproduced, stopped: false, budget: false };
  };

  // Re-establish the target on the exact source immediately before reduction. A stale
  // or no-longer-reproducing prefix is never used as the baseline for delta debugging.
  const baseline = await runCandidate(keptIds, 'baseline');
  if (baseline.stopped) return stopped();
  if (baseline.budget) {
    return Object.freeze({
      status: 'PARTIAL',
      reason: 'attempt-budget',
      targetFingerprint,
      ...summaryStats(source, groups, keptIds, attempts, bestRecording),
    });
  }
  if (!baseline.reproduced) {
    return Object.freeze({
      status: 'NOT_REPRODUCED',
      targetFingerprint,
      ...summaryStats(source, groups, keptIds, attempts, bestRecording),
    });
  }

  if (!groups.length) {
    return Object.freeze({
      status: 'NO_REMOVABLE_INPUTS',
      targetFingerprint,
      ...summaryStats(source, groups, keptIds, attempts, bestRecording),
    });
  }

  let granularity = Math.min(2, keptIds.length);
  while (keptIds.length > 0) {
    if (shouldStop()) return stopped();
    const chunks = partition(keptIds, granularity);
    let reduced = false;

    for (const chunk of chunks) {
      if (shouldStop()) return stopped();
      const removed = new Set(chunk);
      const candidateKept = keptIds.filter(id => !removed.has(id));
      const probe = await runCandidate(candidateKept, 'ddmin');
      if (probe.stopped) return stopped();
      if (probe.budget) {
        budgetExhausted = true;
        break;
      }
      if (probe.reproduced) {
        keptIds = candidateKept;
        bestRecording = probe.candidate;
        granularity = Math.max(2, granularity - 1);
        reduced = true;
        break;
      }
    }

    if (budgetExhausted) break;
    if (reduced) {
      if (!keptIds.length) break;
      granularity = Math.min(granularity, keptIds.length);
      continue;
    }
    if (granularity >= keptIds.length) break;
    granularity = Math.min(keptIds.length, granularity * 2);
  }

  const stats = summaryStats(source, groups, keptIds, attempts, bestRecording);
  if (budgetExhausted) {
    return Object.freeze({
      status: 'PARTIAL',
      reason: 'attempt-budget',
      targetFingerprint,
      ...stats,
    });
  }
  return Object.freeze({
    status: stats.removedGroups.length ? 'INPUTS_MINIMIZED' : 'INPUTS_ALREADY_MINIMAL',
    targetFingerprint,
    ...stats,
  });
}

export const InputMinimizerLayout = Object.freeze({
  REMOVABLE_INPUT_TYPES: Object.freeze([...REMOVABLE_INPUT_TYPES]),
});
