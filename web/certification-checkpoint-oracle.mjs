import { CertificationLayout } from './certification-host.mjs';
import { rebindCheckpointForRecordingCandidateV1 } from './certification-checkpoint-compat.mjs';

const EVIDENCE_SCHEMA = 'kq1agi-checkpoint-oracle-evidence-v1';
const TRUSTED_TERMINAL = new Set(['REPLAY_MATCH', 'DIVERGED', 'COMPLETE']);
const TELEMETRY_KEYS = new Set([
  'certifiedBarriers',
  'consumedTicks',
  'replayStartTick',
  'skippedPrefixTicks',
  'snapshotEpoch',
]);

function copyU32(view) {
  return Array.from(view, value => Number(value) >>> 0);
}

function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (!value || typeof value !== 'object') return value;
  const out = {};
  for (const key of Object.keys(value).sort()) {
    if (TELEMETRY_KEYS.has(key)) continue;
    out[key] = canonicalValue(value[key]);
  }
  return out;
}

function firstDifference(expected, actual, path = '$') {
  if (Object.is(expected, actual)) return null;
  if (Array.isArray(expected) || Array.isArray(actual)) {
    if (!Array.isArray(expected) || !Array.isArray(actual)) {
      return { path, expected, actual, reason: 'type' };
    }
    if (expected.length !== actual.length) {
      return { path: path + '.length', expected: expected.length, actual: actual.length, reason: 'length' };
    }
    for (let i = 0; i < expected.length; i += 1) {
      const diff = firstDifference(expected[i], actual[i], path + '[' + i + ']');
      if (diff) return diff;
    }
    return null;
  }
  const expectedObject = expected && typeof expected === 'object';
  const actualObject = actual && typeof actual === 'object';
  if (expectedObject || actualObject) {
    if (!expectedObject || !actualObject) {
      return { path, expected, actual, reason: 'type' };
    }
    const expectedKeys = Object.keys(expected).sort();
    const actualKeys = Object.keys(actual).sort();
    const keyDiff = firstDifference(expectedKeys, actualKeys, path + '.__keys');
    if (keyDiff) return keyDiff;
    for (const key of expectedKeys) {
      const diff = firstDifference(expected[key], actual[key], path + '.' + key);
      if (diff) return diff;
    }
    return null;
  }
  return { path, expected, actual, reason: 'value' };
}

function laneEvidence(lane) {
  const semanticSlots = CertificationLayout.DIGEST.SEMANTIC_SLOTS;
  return Object.freeze({
    trace: Object.freeze(copyU32(lane.trace)),
    digest: Object.freeze(copyU32(lane.digest.slice(0, semanticSlots))),
    queue: Object.freeze(copyU32(lane.queue)),
    keys: Object.freeze(copyU32(lane.keys)),
    oldKeys: Object.freeze(copyU32(lane.oldKeys)),
    vars: Object.freeze(copyU32(lane.vars)),
    pixels: Object.freeze(copyU32(new Uint32Array(lane.pixelDataSAB))),
    quit: lane.quit === true,
    error: lane.error == null ? null : String(lane.error?.message ?? lane.error),
    soundRequests: Object.freeze((lane.soundRequests ?? []).map(request => Object.freeze(canonicalValue(request)))),
  });
}

/**
 * Capture the terminal state used by the Phase -1I.2 oracle.
 *
 * Call only after runCertificationReplaySession() returns. That runner has already
 * synchronized every trusted MATCH/DIVERGENCE/COMPLETE decision at an authoritative
 * replay barrier. This function is intentionally observational: it does not pulse,
 * snapshot, checkpoint, or otherwise mutate the host.
 */
export function captureCheckpointOracleEvidenceV1(host) {
  if (!host?.started || !host?.truth?.ready || !host?.edited?.ready) {
    throw new Error('Checkpoint oracle evidence requires a started replay host.');
  }
  return Object.freeze({
    schema: EVIDENCE_SCHEMA,
    logicalTick: Number(host.logicalTick) >>> 0,
    cycle: Number(host.cycle) >>> 0,
    comparedCycle: Number(host.comparedCycle) >>> 0,
    truth: laneEvidence(host.truth),
    edited: laneEvidence(host.edited),
    pendingSoundCompletions: Object.freeze((host.pendingSoundCompletions ?? []).map(event => Object.freeze({
      dueTick: Number(event?.dueTick) >>> 0,
      endFlag: Number(event?.endFlag) & 0xff,
    }))),
    pendingExternalDivergence: host.pendingExternalDivergence == null
      ? null : Object.freeze(canonicalValue(host.pendingExternalDivergence)),
  });
}

export function canonicalReplayOracleDecisionV1(summary) {
  if (!summary || typeof summary !== 'object') {
    return { status: 'INVALID_REPLAY_SUMMARY' };
  }
  return canonicalValue(summary);
}

export function compareCheckpointOracleRunsV1(fullRun, acceleratedRun) {
  if (!fullRun?.summary || !acceleratedRun?.summary) {
    return Object.freeze({
      equivalent: false,
      category: 'missing-summary',
      difference: { path: '$.summary', expected: !!fullRun?.summary, actual: !!acceleratedRun?.summary },
    });
  }
  if (!fullRun?.evidence || !acceleratedRun?.evidence) {
    return Object.freeze({
      equivalent: false,
      category: 'missing-evidence',
      difference: { path: '$.evidence', expected: !!fullRun?.evidence, actual: !!acceleratedRun?.evidence },
    });
  }

  const fullDecision = canonicalReplayOracleDecisionV1(fullRun.summary);
  const acceleratedDecision = canonicalReplayOracleDecisionV1(acceleratedRun.summary);
  const decisionDifference = firstDifference(fullDecision, acceleratedDecision, '$.decision');
  if (decisionDifference) {
    return Object.freeze({
      equivalent: false,
      category: 'decision',
      difference: Object.freeze(decisionDifference),
      fullDecision: Object.freeze(fullDecision),
      acceleratedDecision: Object.freeze(acceleratedDecision),
    });
  }

  const fullEvidence = canonicalValue(fullRun.evidence);
  const acceleratedEvidence = canonicalValue(acceleratedRun.evidence);
  const evidenceDifference = firstDifference(fullEvidence, acceleratedEvidence, '$.evidence');
  if (evidenceDifference) {
    return Object.freeze({
      equivalent: false,
      category: 'evidence',
      difference: Object.freeze(evidenceDifference),
    });
  }

  return Object.freeze({
    equivalent: true,
    category: 'exact',
    fullDecision: Object.freeze(fullDecision),
    acceleratedDecision: Object.freeze(acceleratedDecision),
  });
}

function telemetry(summary) {
  const consumedTicks = Number(summary?.consumedTicks);
  const replayStartTick = Number(summary?.replayStartTick);
  return Object.freeze({
    consumedTicks: Number.isSafeInteger(consumedTicks) && consumedTicks >= 0 ? consumedTicks : null,
    replayStartTick: Number.isSafeInteger(replayStartTick) && replayStartTick >= 0 ? replayStartTick : null,
  });
}

/**
 * Phase -1I.2 shadow/oracle runner.
 *
 * The full from-start replay always runs first and remains authoritative. A compatible
 * checkpoint path is then executed in shadow mode. Only exact decision + terminal
 * evidence equivalence earns CHECKPOINT_ORACLE_EQUIVALENT. Any incompatibility,
 * exception, unsupported terminal result, or mismatch falls back to the full result.
 */
export async function runCheckpointCandidateOracleV1(options = {}) {
  const {
    checkpoint,
    sourceRecording,
    candidateRecording,
    runFullReplay,
    runCheckpointReplay,
  } = options;

  if (typeof runFullReplay !== 'function') throw new TypeError('runFullReplay callback is required.');
  if (typeof runCheckpointReplay !== 'function') throw new TypeError('runCheckpointReplay callback is required.');

  const fullRun = await runFullReplay(candidateRecording);
  if (!fullRun?.summary) throw new Error('Full replay callback must return {summary, evidence}.');

  const authoritativeSummary = fullRun.summary;
  if (!TRUSTED_TERMINAL.has(String(authoritativeSummary.status ?? ''))) {
    return Object.freeze({
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'unsupported-full-status',
      authoritativeSummary,
      fullRun,
      fullTelemetry: telemetry(authoritativeSummary),
      checkpointAttempted: false,
    });
  }

  const rebound = await rebindCheckpointForRecordingCandidateV1(
    checkpoint,
    sourceRecording,
    candidateRecording,
  );
  if (rebound.status !== 'CHECKPOINT_CANDIDATE_REBOUND') {
    return Object.freeze({
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'checkpoint-incompatible',
      compatibility: rebound,
      authoritativeSummary,
      fullRun,
      fullTelemetry: telemetry(authoritativeSummary),
      checkpointAttempted: false,
    });
  }

  let acceleratedRun;
  try {
    acceleratedRun = await runCheckpointReplay(candidateRecording, rebound.checkpoint, rebound.proof);
  } catch (error) {
    return Object.freeze({
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'checkpoint-exception',
      compatibility: rebound.proof,
      authoritativeSummary,
      fullRun,
      fullTelemetry: telemetry(authoritativeSummary),
      checkpointAttempted: true,
      checkpointError: String(error?.stack ?? error),
    });
  }

  if (!acceleratedRun?.summary) {
    return Object.freeze({
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'checkpoint-missing-summary',
      compatibility: rebound.proof,
      authoritativeSummary,
      fullRun,
      acceleratedRun: acceleratedRun ?? null,
      fullTelemetry: telemetry(authoritativeSummary),
      checkpointAttempted: true,
    });
  }

  const comparison = compareCheckpointOracleRunsV1(fullRun, acceleratedRun);
  if (!comparison.equivalent) {
    return Object.freeze({
      status: 'CHECKPOINT_ORACLE_MISMATCH',
      reason: comparison.category,
      compatibility: rebound.proof,
      comparison,
      authoritativeSummary,
      fullRun,
      acceleratedRun,
      fullTelemetry: telemetry(authoritativeSummary),
      checkpointTelemetry: telemetry(acceleratedRun.summary),
      checkpointAttempted: true,
      checkpointTrusted: false,
    });
  }

  const fullTelemetry = telemetry(authoritativeSummary);
  const checkpointTelemetry = telemetry(acceleratedRun.summary);
  const savedTicks = fullTelemetry.consumedTicks != null && checkpointTelemetry.consumedTicks != null
    ? Math.max(0, fullTelemetry.consumedTicks - checkpointTelemetry.consumedTicks)
    : null;

  return Object.freeze({
    status: 'CHECKPOINT_ORACLE_EQUIVALENT',
    compatibility: rebound.proof,
    comparison,
    authoritativeSummary,
    fullRun,
    acceleratedRun,
    fullTelemetry,
    checkpointTelemetry,
    savedTicks,
    checkpointAttempted: true,
    checkpointTrusted: true,
  });
}

export const CheckpointOracleLayout = Object.freeze({
  EVIDENCE_SCHEMA,
  TRUSTED_TERMINAL: Object.freeze([...TRUSTED_TERMINAL]),
});
