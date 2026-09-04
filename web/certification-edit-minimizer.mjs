import { canonicalizeEditConfigV1, EditConfigLayout, hashEditConfigV1 } from './certification-edit-config.mjs';
import { canonicalizePlayRecordingV1, hashPlayRecordingV1 } from './certification-recording.mjs';
import {
  divergenceFingerprint,
  sameDivergence,
  snapshotVerifiedRecordingV1,
} from './certification-minimizer.mjs';

function asInt(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? (n | 0) : fallback;
}

export async function snapshotVerifiedEditConfigV1(config, expectedHash = null) {
  if (!config || typeof config !== 'object' || String(config.schema ?? '') !== EditConfigLayout.SCHEMA) {
    throw new Error('Phase -1G requires a ' + EditConfigLayout.SCHEMA + ' EditConfig.');
  }
  const declaredHash = String(config.hash ?? '');
  const expected = String(expectedHash ?? declaredHash);
  if (!declaredHash || !expected) {
    throw new Error('Phase -1G requires the frozen EditConfig hash.');
  }
  const canonical = canonicalizeEditConfigV1(config);
  const actualHash = await hashEditConfigV1(canonical);
  if (declaredHash !== expected || actualHash !== expected) {
    throw new Error(
      'Phase -1G EditConfig hash mismatch: recording ' + expected
      + ', declared ' + declaredHash + ', actual ' + actualHash + '.',
    );
  }
  return Object.freeze({ ...canonical, hash: actualHash });
}

function freezeGroup(group) {
  return Object.freeze({
    ...group,
    maskLayers: group.maskLayers ? Object.freeze([...group.maskLayers]) : undefined,
  });
}

export function groupEditConfigV1(config) {
  if (!config || typeof config !== 'object' || String(config.schema ?? '') !== EditConfigLayout.SCHEMA) {
    throw new Error('Phase -1G requires a ' + EditConfigLayout.SCHEMA + ' EditConfig.');
  }
  const canonical = canonicalizeEditConfigV1(config);
  const groups = [];
  const seenRooms = new Set();

  for (const room of canonical.rooms) {
    const roomNumber = asInt(room.room) & 0xff;
    if (seenRooms.has(roomNumber)) {
      throw new Error('Phase -1G requires unique canonical room entries; duplicate room ' + roomNumber + '.');
    }
    seenRooms.add(roomNumber);
    groups.push(freezeGroup({
      id: 'edit-room-' + roomNumber,
      kind: 'room-config',
      room: roomNumber,
      maskLayers: room.masks
        .map((mask, index) => String(mask ?? '').length ? index : null)
        .filter(index => index != null),
    }));
  }

  if (canonical.visualPins.length) {
    groups.push(freezeGroup({
      id: 'edit-visual-pins',
      kind: 'visual-pins',
      count: canonical.visualPins.length,
    }));
  }

  return Object.freeze(groups);
}

async function buildCandidateUnchecked(sourceRecording, sourceConfig, groups, keptGroupIds) {
  const keep = new Set(keptGroupIds);
  const roomIds = new Map(
    groups
      .filter(group => group.kind === 'room-config')
      .map(group => [group.room, group.id]),
  );
  const pinsGroup = groups.find(group => group.kind === 'visual-pins');

  const configBase = canonicalizeEditConfigV1({
    schema: EditConfigLayout.SCHEMA,
    rooms: sourceConfig.rooms.filter(room => keep.has(roomIds.get(asInt(room.room) & 0xff))),
    visualPins: pinsGroup && keep.has(pinsGroup.id) ? sourceConfig.visualPins : [],
  });
  const candidateConfig = Object.freeze({
    ...configBase,
    hash: await hashEditConfigV1(configBase),
  });

  const recordingBase = canonicalizePlayRecordingV1({
    ...sourceRecording,
    editConfigHash: candidateConfig.hash,
  });
  const candidateRecording = Object.freeze({
    ...recordingBase,
    hash: await hashPlayRecordingV1(recordingBase),
  });

  return Object.freeze({ recording: candidateRecording, editConfig: candidateConfig });
}

export async function buildEditConfigWithoutGroupsV1(recording, editConfig, groupIdsToRemove = []) {
  const sourceRecording = await snapshotVerifiedRecordingV1(recording);
  const sourceConfig = await snapshotVerifiedEditConfigV1(editConfig, sourceRecording.editConfigHash);
  const groups = groupEditConfigV1(sourceConfig);
  const known = new Set(groups.map(group => group.id));
  const remove = new Set(groupIdsToRemove);
  for (const id of remove) {
    if (!known.has(id)) throw new Error('Unknown Phase -1G edit group: ' + id);
  }
  const kept = groups.filter(group => !remove.has(group.id)).map(group => group.id);
  return buildCandidateUnchecked(sourceRecording, sourceConfig, groups, kept);
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

function summaryStats(sourceConfig, groups, keptIds, attempts, pair) {
  const kept = new Set(keptIds);
  const keptGroups = groups.filter(group => kept.has(group.id));
  const removedGroups = groups.filter(group => !kept.has(group.id));
  const totalRoomGroups = groups.filter(group => group.kind === 'room-config').length;
  const keptRoomGroups = keptGroups.filter(group => group.kind === 'room-config').length;
  return {
    recording: pair.recording,
    editConfig: pair.editConfig,
    totalGroups: groups.length,
    keptGroups: Object.freeze(keptGroups),
    removedGroups: Object.freeze(removedGroups),
    totalRoomGroups,
    keptRoomGroups,
    removedRoomGroups: totalRoomGroups - keptRoomGroups,
    totalVisualPins: sourceConfig.visualPins.length,
    keptVisualPins: pair.editConfig.visualPins.length,
    attempts: Object.freeze([...attempts]),
  };
}

export async function minimizeEditConfigV1(recording, editConfig, targetResult, replayCandidate, options = {}) {
  if (typeof replayCandidate !== 'function') throw new TypeError('replayCandidate must be a function.');
  const sourceRecording = await snapshotVerifiedRecordingV1(recording);
  const sourceConfig = await snapshotVerifiedEditConfigV1(editConfig, sourceRecording.editConfigHash);
  const targetFingerprint = divergenceFingerprint(targetResult);
  if (!targetFingerprint) throw new Error('Phase -1G requires a DIVERGED target result.');

  const groups = groupEditConfigV1(sourceConfig);
  const shouldStop = options.shouldStop ?? (() => false);
  const onAttempt = options.onAttempt ?? (() => {});
  const maxAttempts = Math.max(1, asInt(options.maxAttempts, 128));
  const attempts = [];
  const allIds = groups.map(group => group.id);
  let keptIds = [...allIds];
  let bestPair = Object.freeze({ recording: sourceRecording, editConfig: sourceConfig });
  let budgetExhausted = false;

  const stopped = () => Object.freeze({
    status: 'STOPPED',
    targetFingerprint,
    ...summaryStats(sourceConfig, groups, keptIds, attempts, bestPair),
  });

  const runCandidate = async (candidateKeptIds, phase) => {
    if (shouldStop()) return { stopped: true };
    if (attempts.length >= maxAttempts) {
      budgetExhausted = true;
      return { budget: true };
    }
    const pair = candidateKeptIds.length === groups.length
      ? bestPair
      : await buildCandidateUnchecked(sourceRecording, sourceConfig, groups, candidateKeptIds);
    const summary = await replayCandidate(pair.recording, pair.editConfig);
    const divergence = divergenceFromSummary(summary);
    const reproduced = sameDivergence(divergence, targetFingerprint);
    const attempt = Object.freeze({
      number: attempts.length + 1,
      phase,
      keptGroups: candidateKeptIds.length,
      removedGroups: groups.length - candidateKeptIds.length,
      status: summary?.status ?? 'unknown',
      reproduced,
      editConfigHash: pair.editConfig.hash,
      recordingHash: pair.recording.hash,
    });
    attempts.push(attempt);
    onAttempt(attempt);
    return { pair, summary, reproduced, stopped: false, budget: false };
  };

  const baseline = await runCandidate(keptIds, 'baseline');
  if (baseline.stopped) return stopped();
  if (baseline.budget) {
    return Object.freeze({
      status: 'PARTIAL',
      reason: 'attempt-budget',
      targetFingerprint,
      ...summaryStats(sourceConfig, groups, keptIds, attempts, bestPair),
    });
  }
  if (!baseline.reproduced) {
    return Object.freeze({
      status: 'NOT_REPRODUCED',
      targetFingerprint,
      ...summaryStats(sourceConfig, groups, keptIds, attempts, bestPair),
    });
  }

  if (!groups.length) {
    return Object.freeze({
      status: 'NO_REMOVABLE_EDITS',
      targetFingerprint,
      ...summaryStats(sourceConfig, groups, keptIds, attempts, bestPair),
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
        bestPair = probe.pair;
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

  const stats = summaryStats(sourceConfig, groups, keptIds, attempts, bestPair);
  if (budgetExhausted) {
    return Object.freeze({
      status: 'PARTIAL',
      reason: 'attempt-budget',
      targetFingerprint,
      ...stats,
    });
  }
  return Object.freeze({
    status: stats.removedGroups.length ? 'EDITS_MINIMIZED' : 'EDITS_ALREADY_MINIMAL',
    targetFingerprint,
    ...stats,
  });
}
