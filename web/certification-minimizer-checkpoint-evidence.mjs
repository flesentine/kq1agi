import {
  canonicalReplayOracleDecisionV1,
  validateCheckpointOracleEvidenceV1,
} from './certification-checkpoint-oracle.mjs';
import { summarizeMinimizerCheckpointShadowV1 } from './certification-minimizer-checkpoint-shadow.mjs';

const OBSERVATION_SCHEMA = 'kq1agi-minimizer-checkpoint-observation-v1';
const STAGE_SCHEMA = 'kq1agi-minimizer-checkpoint-stage-evidence-v1';
const REPORT_SCHEMA = 'kq1agi-minimizer-checkpoint-evidence-report-v1';
const POLICY = 'full-replay-authoritative';

function canonicalValue(value) {
  if (Array.isArray(value)) return value.map(canonicalValue);
  if (!value || typeof value !== 'object') {
    if (typeof value === 'number' && !Number.isFinite(value)) return null;
    return value;
  }
  const out = {};
  for (const key of Object.keys(value).sort()) {
    const item = value[key];
    if (item === undefined) continue;
    out[key] = canonicalValue(item);
  }
  return out;
}

function hex(bytes) {
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}

export async function hashCanonicalJsonV1(value) {
  if (!globalThis.crypto?.subtle) throw new Error('SubtleCrypto is required for checkpoint evidence hashing.');
  const canonical = JSON.stringify(canonicalValue(value));
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(canonical));
  return `sha256:${hex(new Uint8Array(digest))}`;
}

function compactTelemetry(value) {
  const consumedTicks = Number(value?.consumedTicks);
  const replayStartTick = Number(value?.replayStartTick);
  return Object.freeze({
    consumedTicks: Number.isSafeInteger(consumedTicks) && consumedTicks >= 0 ? consumedTicks : null,
    replayStartTick: Number.isSafeInteger(replayStartTick) && replayStartTick >= 0 ? replayStartTick : null,
  });
}

function compactComparison(comparison) {
  if (!comparison || typeof comparison !== 'object') return null;
  return Object.freeze({
    category: String(comparison.category ?? 'unknown'),
    equivalent: comparison.equivalent === true,
    differencePath: comparison.difference?.path == null ? null : String(comparison.difference.path),
    differenceReason: comparison.difference?.reason == null ? null : String(comparison.difference.reason),
  });
}

function compactCompatibility(compatibility) {
  if (!compatibility || typeof compatibility !== 'object') return null;
  const checkpointTick = Number(compatibility.checkpointTick);
  return Object.freeze({
    checkpointTick: Number.isSafeInteger(checkpointTick) && checkpointTick >= 0 ? checkpointTick : null,
    sourceRecordingHash: compatibility.sourceRecordingHash == null ? null : String(compatibility.sourceRecordingHash),
    candidateRecordingHash: compatibility.candidateRecordingHash == null ? null : String(compatibility.candidateRecordingHash),
    checkpointHash: compatibility.checkpointHash == null ? null : String(compatibility.checkpointHash),
  });
}

function validationSummary(evidence) {
  const validation = validateCheckpointOracleEvidenceV1(evidence);
  return Object.freeze({ valid: validation.valid === true, reason: String(validation.reason ?? 'unknown') });
}

async function optionalHash(value) {
  return value == null ? null : hashCanonicalJsonV1(value);
}

/**
 * Convert one full Phase -1I.2 oracle result into a compact, cryptographically
 * fingerprinted observation. The giant terminal evidence payloads are hashed and
 * then intentionally omitted so a long minimizer run does not retain one copy of
 * both worker states for every candidate.
 */
export async function compactMinimizerCheckpointObservationV1(shadow, candidateRecordingHash) {
  const oracle = shadow?.oracle;
  if (!oracle || typeof oracle !== 'object') throw new TypeError('A minimizer shadow oracle result is required.');

  const candidateHash = String(candidateRecordingHash ?? oracle.fullRun?.evidence?.context?.recordingHash ?? '');
  if (!candidateHash) throw new Error('A candidate recording hash is required for checkpoint evidence.');

  const fullDecision = canonicalReplayOracleDecisionV1(oracle.authoritativeSummary);
  const acceleratedSummary = oracle.acceleratedRun?.summary ?? null;
  const acceleratedDecision = acceleratedSummary == null
    ? null
    : canonicalReplayOracleDecisionV1(acceleratedSummary);
  const fullEvidence = oracle.fullRun?.evidence ?? null;
  const acceleratedEvidence = oracle.acceleratedRun?.evidence ?? null;

  const [
    fullDecisionHash,
    checkpointDecisionHash,
    fullEvidenceHash,
    checkpointEvidenceHash,
  ] = await Promise.all([
    hashCanonicalJsonV1(fullDecision),
    optionalHash(acceleratedDecision),
    optionalHash(fullEvidence),
    optionalHash(acceleratedEvidence),
  ]);

  const status = String(oracle.status ?? 'UNKNOWN');
  const reason = String(oracle.reason ?? status);
  const comparison = compactComparison(oracle.comparison);
  const compatibility = compactCompatibility(oracle.compatibility);
  const savedTicks = Number(oracle.savedTicks);
  const observationCore = {
    schema: OBSERVATION_SCHEMA,
    candidateRecordingHash: candidateHash,
    status,
    reason,
    checkpointAttempted: oracle.checkpointAttempted === true,
    checkpointTrusted: oracle.checkpointTrusted === true,
    savedTicks: Number.isSafeInteger(savedTicks) && savedTicks >= 0 ? savedTicks : null,
    fullTelemetry: compactTelemetry(oracle.fullTelemetry ?? oracle.authoritativeSummary),
    checkpointTelemetry: oracle.checkpointTelemetry == null
      ? null
      : compactTelemetry(oracle.checkpointTelemetry),
    compatibility,
    comparison,
    authoritativeStatus: String(oracle.authoritativeSummary?.status ?? 'UNKNOWN'),
    authoritativeResultStatus: oracle.authoritativeSummary?.result?.status == null
      ? null
      : String(oracle.authoritativeSummary.result.status),
    authoritativeResultTick: Number.isSafeInteger(Number(oracle.authoritativeSummary?.result?.tick))
      ? Number(oracle.authoritativeSummary.result.tick)
      : null,
    fullDecisionHash,
    checkpointDecisionHash,
    fullEvidenceValidation: validationSummary(fullEvidence),
    checkpointEvidenceValidation: acceleratedEvidence == null ? null : validationSummary(acceleratedEvidence),
    fullEvidenceHash,
    checkpointEvidenceHash,
  };

  const semanticFingerprint = await hashCanonicalJsonV1({
    candidateRecordingHash: observationCore.candidateRecordingHash,
    status: observationCore.status,
    reason: observationCore.reason,
    checkpointAttempted: observationCore.checkpointAttempted,
    checkpointTrusted: observationCore.checkpointTrusted,
    savedTicks: observationCore.savedTicks,
    compatibility: observationCore.compatibility,
    comparison: observationCore.comparison,
    authoritativeStatus: observationCore.authoritativeStatus,
    authoritativeResultStatus: observationCore.authoritativeResultStatus,
    authoritativeResultTick: observationCore.authoritativeResultTick,
    fullDecisionHash,
    checkpointDecisionHash,
    fullEvidenceHash,
    checkpointEvidenceHash,
  });

  return Object.freeze({ ...observationCore, semanticFingerprint });
}

function sourceIdentity(recording) {
  return Object.freeze({
    recordingHash: String(recording?.hash ?? ''),
    gameHash: String(recording?.gameHash ?? ''),
    gameBytes: Number(recording?.gameBytes) || 0,
    editConfigHash: String(recording?.editConfigHash ?? ''),
    finalTick: Number(recording?.finalTick) || 0,
    eventCount: recording?.events?.length ?? 0,
    randomCount: recording?.random?.length ?? 0,
    releaseCount: recording?.releaseTicks?.length ?? 0,
  });
}

function checkpointIdentity(shadowState) {
  const selection = shadowState?.selection ?? null;
  const checkpoint = shadowState?.checkpoint ?? null;
  return Object.freeze({
    status: String(shadowState?.status ?? (checkpoint ? 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED' : 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE')),
    reason: checkpoint ? null : String(shadowState?.reason ?? selection?.reason ?? 'checkpoint-unavailable'),
    hash: checkpoint?.hash == null ? null : String(checkpoint.hash),
    logicalTick: Number.isSafeInteger(Number(checkpoint?.logicalTick)) ? Number(checkpoint.logicalTick) : null,
    pauseBeforeTick: Number.isSafeInteger(Number(selection?.pauseBeforeTick)) ? Number(selection.pauseBeforeTick) : null,
    desiredCheckpointTick: Number.isSafeInteger(Number(selection?.desiredCheckpointTick)) ? Number(selection.desiredCheckpointTick) : null,
  });
}

function compactOutcome(outcome) {
  return Object.freeze({
    status: String(outcome?.status ?? 'UNKNOWN'),
    attempts: Number.isSafeInteger(Number(outcome?.attempts)) && Number(outcome.attempts) >= 0
      ? Number(outcome.attempts)
      : 0,
  });
}

export async function createMinimizerCheckpointStageEvidenceV1(options = {}) {
  const stage = String(options.stage ?? '');
  if (!['phase-1e', 'phase-1f'].includes(stage)) throw new Error(`Unsupported minimizer evidence stage: ${stage || 'missing'}`);
  const source = sourceIdentity(options.sourceRecording);
  if (!source.recordingHash) throw new Error('Stage evidence requires a source recording hash.');
  const targetTick = Number(options.targetDivergence?.tick ?? options.targetTick);
  if (!Number.isSafeInteger(targetTick) || targetTick < 0) throw new Error('Stage evidence requires a target divergence tick.');
  const observations = Object.freeze([...(options.observations ?? [])]);
  const collectionErrorCandidateHashes = Object.freeze(
    [...new Set((options.collectionErrorCandidateHashes ?? []).map(value => String(value)).filter(Boolean))].sort(),
  );
  const checkpoint = checkpointIdentity(options.shadowState);
  const summary = summarizeMinimizerCheckpointShadowV1(observations);
  const collection = Object.freeze({
    compactedObservations: observations.length,
    compactionFailures: collectionErrorCandidateHashes.length,
    failedCandidateHashes: collectionErrorCandidateHashes,
  });
  const stageKey = await hashCanonicalJsonV1({
    stage,
    sourceRecordingHash: source.recordingHash,
    targetTick,
    checkpointHash: checkpoint.hash,
    checkpointTick: checkpoint.logicalTick,
  });

  const unsigned = {
    schema: STAGE_SCHEMA,
    policy: POLICY,
    stage,
    stageKey,
    source,
    target: Object.freeze({ tick: targetTick }),
    checkpoint,
    outcome: compactOutcome(options.outcome),
    collection,
    summary,
    observations,
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

function populationSummary(stages) {
  const all = [];
  const samples = new Map();
  for (const stage of stages) {
    for (const observation of stage.observations ?? []) {
      all.push(observation);
      const sampleKey = `${stage.stageKey}|${observation.candidateRecordingHash}`;
      let sample = samples.get(sampleKey);
      if (!sample) {
        sample = { count: 0, fingerprints: new Set() };
        samples.set(sampleKey, sample);
      }
      sample.count += 1;
      sample.fingerprints.add(String(observation.semanticFingerprint ?? 'missing'));
    }
  }

  const aggregate = summarizeMinimizerCheckpointShadowV1(all);
  const compactionFailures = stages.reduce(
    (total, stage) => total + (Number(stage?.collection?.compactionFailures) || 0),
    0,
  );
  let repeatedSamples = 0;
  let inconsistentSamples = 0;
  for (const sample of samples.values()) {
    if (sample.count > 1) repeatedSamples += 1;
    if (sample.fingerprints.size > 1) inconsistentSamples += 1;
  }
  const uniqueSamples = samples.size;
  const totalObservations = all.length;
  return Object.freeze({
    stageExecutions: stages.length,
    totalObservations,
    compactionFailures,
    uniqueSamples,
    duplicateObservations: Math.max(0, totalObservations - uniqueSamples),
    repeatedSamples,
    inconsistentSamples,
    equivalent: aggregate.equivalent,
    fullOnly: aggregate.fullOnly,
    mismatch: aggregate.mismatch,
    checkpointAttempts: aggregate.checkpointAttempts,
    trustedCheckpoints: aggregate.trustedCheckpoints,
    totalSavedTicks: aggregate.totalSavedTicks,
    averageSavedTicks: aggregate.averageSavedTicks,
    equivalentRateAmongAttempts: aggregate.checkpointAttempts
      ? aggregate.equivalent / aggregate.checkpointAttempts
      : null,
    mismatchRateAmongAttempts: aggregate.checkpointAttempts
      ? aggregate.mismatch / aggregate.checkpointAttempts
      : null,
    reasons: aggregate.reasons,
  });
}

export async function createMinimizerCheckpointEvidenceReportV1(stageEvidence = []) {
  const stages = Object.freeze([...(stageEvidence ?? [])]);
  const population = populationSummary(stages);
  const unsigned = {
    schema: REPORT_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    stages,
    population,
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointEvidenceReportV1(report) {
  if (report?.schema !== REPORT_SCHEMA || !String(report?.hash ?? '')) {
    throw new TypeError('A complete Phase -1I.4 evidence report is required.');
  }
  return `${JSON.stringify(report, null, 2)}\n`;
}

export const MinimizerCheckpointEvidenceLayout = Object.freeze({
  OBSERVATION_SCHEMA,
  STAGE_SCHEMA,
  REPORT_SCHEMA,
  POLICY,
});
