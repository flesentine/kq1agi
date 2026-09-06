import {
  createMinimizerCheckpointEvidenceReportV1,
  hashCanonicalJsonV1,
  hashMinimizerCheckpointObservationSemanticV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import { summarizeMinimizerCheckpointShadowV1 } from './certification-minimizer-checkpoint-shadow.mjs';

const CORPUS_SCHEMA = 'kq1agi-minimizer-checkpoint-evidence-corpus-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;
const MAX_STAGES = 2048;
const MAX_OBSERVATIONS = 20000;
const ORACLE_STATUSES = new Set([
  'CHECKPOINT_ORACLE_EQUIVALENT',
  'CHECKPOINT_ORACLE_FULL_ONLY',
  'CHECKPOINT_ORACLE_MISMATCH',
]);
const FORBIDDEN_EVIDENCE_KEYS = new Set([
  'workerPayload',
  'truthWorkerPayload',
  'editedWorkerPayload',
  'fullRun',
  'acceleratedRun',
]);

function rejectForbiddenEvidenceKeys(value, path = '$') {
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i += 1) rejectForbiddenEvidenceKeys(value[i], `${path}[${i}]`);
    return;
  }
  if (!isObject(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (FORBIDDEN_EVIDENCE_KEYS.has(key)) {
      throw new Error(`Checkpoint evidence contains forbidden raw oracle field at ${path}.${key}.`);
    }
    rejectForbiddenEvidenceKeys(item, `${path}.${key}`);
  }
}

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isSha256(value) {
  return /^sha256:[0-9a-f]{64}$/.test(String(value ?? ''));
}

function asNonNegativeInteger(value) {
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 0 ? n : null;
}

async function sameCanonicalValue(a, b) {
  return (await hashCanonicalJsonV1(a)) === (await hashCanonicalJsonV1(b));
}

function assertPolicy(value, label) {
  if (value?.policy !== POLICY
      || value?.policyFrozen !== false
      || value?.policyDecision !== 'EVIDENCE_ONLY') {
    throw new Error(`${label} changes the Phase -1I evidence-only replay policy.`);
  }
}

async function validateObservationV1(observation) {
  if (!isObject(observation)) throw new Error('Evidence observation must be an object.');
  if (observation.schema !== MinimizerCheckpointEvidenceLayout.OBSERVATION_SCHEMA) {
    throw new Error('Evidence observation schema mismatch.');
  }
  if (!isSha256(observation.candidateRecordingHash)) {
    throw new Error('Evidence observation candidate recording hash is invalid.');
  }
  if (!ORACLE_STATUSES.has(String(observation.status ?? ''))) {
    throw new Error('Evidence observation oracle status is invalid.');
  }
  if (!isSha256(observation.semanticFingerprint)) {
    throw new Error('Evidence observation semantic fingerprint is invalid.');
  }
  if (!isSha256(observation.fullDecisionHash)) {
    throw new Error('Evidence observation full decision hash is invalid.');
  }
  if (observation.fullEvidenceHash != null && !isSha256(observation.fullEvidenceHash)) {
    throw new Error('Evidence observation full evidence hash is invalid.');
  }
  if (observation.checkpointDecisionHash != null && !isSha256(observation.checkpointDecisionHash)) {
    throw new Error('Evidence observation checkpoint decision hash is invalid.');
  }
  if (observation.checkpointEvidenceHash != null && !isSha256(observation.checkpointEvidenceHash)) {
    throw new Error('Evidence observation checkpoint evidence hash is invalid.');
  }

  const status = String(observation.status);
  if (status === 'CHECKPOINT_ORACLE_EQUIVALENT') {
    if (observation.checkpointAttempted !== true || observation.checkpointTrusted !== true) {
      throw new Error('Equivalent evidence must be attempted and trusted.');
    }
    if (!isSha256(observation.checkpointDecisionHash) || !isSha256(observation.checkpointEvidenceHash)) {
      throw new Error('Equivalent evidence requires checkpoint fingerprints.');
    }
    if (observation.fullDecisionHash !== observation.checkpointDecisionHash
        || observation.fullEvidenceHash !== observation.checkpointEvidenceHash) {
      throw new Error('Equivalent evidence fingerprints disagree.');
    }
  } else if (status === 'CHECKPOINT_ORACLE_MISMATCH') {
    if (observation.checkpointAttempted !== true || observation.checkpointTrusted === true) {
      throw new Error('Mismatch evidence must be attempted and untrusted.');
    }
    if (!isObject(observation.comparison) || observation.comparison.equivalent !== false) {
      throw new Error('Mismatch evidence must retain a failed comparison.');
    }
  } else if (observation.checkpointTrusted === true) {
    throw new Error('Full-only evidence cannot be checkpoint-trusted.');
  }

  const savedTicks = observation.savedTicks;
  if (savedTicks != null && asNonNegativeInteger(savedTicks) == null) {
    throw new Error('Evidence observation savedTicks is invalid.');
  }
  if (!isObject(observation.fullEvidenceValidation)
      || typeof observation.fullEvidenceValidation.valid !== 'boolean') {
    throw new Error('Evidence observation full evidence validation is missing.');
  }
  if (observation.checkpointEvidenceValidation != null
      && (!isObject(observation.checkpointEvidenceValidation)
          || typeof observation.checkpointEvidenceValidation.valid !== 'boolean')) {
    throw new Error('Evidence observation checkpoint evidence validation is invalid.');
  }

  const fingerprint = await hashMinimizerCheckpointObservationSemanticV1(observation);
  if (fingerprint !== observation.semanticFingerprint) {
    throw new Error('Evidence observation semantic fingerprint mismatch.');
  }
  return observation;
}

async function validateStageV1(stage) {
  if (!isObject(stage)) throw new Error('Evidence stage must be an object.');
  if (stage.schema !== MinimizerCheckpointEvidenceLayout.STAGE_SCHEMA) {
    throw new Error('Evidence stage schema mismatch.');
  }
  if (stage.policy !== POLICY) throw new Error('Evidence stage policy mismatch.');
  if (!['phase-1e', 'phase-1f'].includes(String(stage.stage ?? ''))) {
    throw new Error('Evidence stage name is invalid.');
  }
  if (!isSha256(stage.stageKey) || !isSha256(stage.hash)) {
    throw new Error('Evidence stage integrity hash is invalid.');
  }
  if (!isObject(stage.source)
      || !isSha256(stage.source.recordingHash)
      || !isSha256(stage.source.gameHash)
      || !isSha256(stage.source.editConfigHash)) {
    throw new Error('Evidence stage source identity is invalid.');
  }
  if (!isObject(stage.target) || asNonNegativeInteger(stage.target.tick) == null) {
    throw new Error('Evidence stage target is invalid.');
  }
  if (!isObject(stage.checkpoint)) throw new Error('Evidence stage checkpoint identity is missing.');
  if (stage.checkpoint.hash != null && !isSha256(stage.checkpoint.hash)) {
    throw new Error('Evidence stage checkpoint hash is invalid.');
  }
  for (const key of ['logicalTick', 'pauseBeforeTick', 'desiredCheckpointTick']) {
    if (stage.checkpoint[key] != null && asNonNegativeInteger(stage.checkpoint[key]) == null) {
      throw new Error(`Evidence stage checkpoint ${key} is invalid.`);
    }
  }
  for (const key of ['gameBytes', 'finalTick', 'eventCount', 'randomCount', 'releaseCount']) {
    if (asNonNegativeInteger(stage.source[key]) == null) {
      throw new Error(`Evidence stage source ${key} is invalid.`);
    }
  }
  if (!Array.isArray(stage.observations)) throw new Error('Evidence stage observations are missing.');
  if (stage.observations.length > MAX_OBSERVATIONS) throw new Error('Evidence stage exceeds the observation safety limit.');

  for (const observation of stage.observations) {
    await validateObservationV1(observation);
    const compatibility = observation.compatibility;
    if (compatibility) {
      if (compatibility.candidateRecordingHash != null
          && compatibility.candidateRecordingHash !== observation.candidateRecordingHash) {
        throw new Error('Evidence observation compatibility candidate identity mismatch.');
      }
      if (compatibility.sourceRecordingHash != null
          && compatibility.sourceRecordingHash !== stage.source.recordingHash) {
        throw new Error('Evidence observation compatibility source identity mismatch.');
      }
      if (compatibility.checkpointHash != null
          && compatibility.checkpointHash !== stage.checkpoint.hash) {
        throw new Error('Evidence observation compatibility checkpoint hash mismatch.');
      }
      if (compatibility.checkpointTick != null
          && Number(compatibility.checkpointTick) !== Number(stage.checkpoint.logicalTick)) {
        throw new Error('Evidence observation compatibility checkpoint tick mismatch.');
      }
    }
  }

  if (!isObject(stage.collection)) throw new Error('Evidence stage collection metadata is missing.');
  const failures = Array.isArray(stage.collection.failedCandidateHashes)
    ? stage.collection.failedCandidateHashes
    : null;
  if (!failures
      || asNonNegativeInteger(stage.collection.compactedObservations) !== stage.observations.length
      || asNonNegativeInteger(stage.collection.compactionFailures) !== failures.length) {
    throw new Error('Evidence stage collection counts are inconsistent.');
  }
  if (new Set(failures).size !== failures.length || failures.some(hash => !isSha256(hash))) {
    throw new Error('Evidence stage collection failure identities are invalid.');
  }

  const expectedSummary = summarizeMinimizerCheckpointShadowV1(stage.observations);
  if (!(await sameCanonicalValue(expectedSummary, stage.summary))) {
    throw new Error('Evidence stage aggregate summary mismatch.');
  }

  const expectedStageKey = await hashCanonicalJsonV1({
    stage: stage.stage,
    sourceRecordingHash: stage.source.recordingHash,
    targetTick: stage.target.tick,
    checkpointHash: stage.checkpoint.hash ?? null,
    checkpointTick: stage.checkpoint.logicalTick ?? null,
  });
  if (expectedStageKey !== stage.stageKey) throw new Error('Evidence stage key mismatch.');

  const { hash, ...unsigned } = stage;
  const expectedHash = await hashCanonicalJsonV1(unsigned);
  if (expectedHash !== hash) throw new Error('Evidence stage hash mismatch.');
  return stage;
}

export async function validateMinimizerCheckpointEvidenceReportV1(report) {
  if (!isObject(report)) throw new Error('Checkpoint evidence report must be an object.');
  rejectForbiddenEvidenceKeys(report);
  if (report.schema !== MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
    throw new Error('Checkpoint evidence report schema mismatch.');
  }
  assertPolicy(report, 'Checkpoint evidence report');
  if (!Array.isArray(report.stages)) throw new Error('Checkpoint evidence report stages are missing.');
  if (report.stages.length > MAX_STAGES) throw new Error('Checkpoint evidence report exceeds the stage safety limit.');
  let observations = 0;
  for (const stage of report.stages) {
    observations += stage?.observations?.length ?? 0;
    if (observations > MAX_OBSERVATIONS) throw new Error('Checkpoint evidence report exceeds the observation safety limit.');
    await validateStageV1(stage);
  }

  const expected = await createMinimizerCheckpointEvidenceReportV1(report.stages);
  if (!(await sameCanonicalValue(expected.population, report.population))) {
    throw new Error('Checkpoint evidence report population mismatch.');
  }
  if (expected.hash !== report.hash) throw new Error('Checkpoint evidence report hash mismatch.');
  return Object.freeze({ valid: true, kind: 'report', hash: report.hash, stages: report.stages });
}

function percentile(sorted, fraction) {
  if (!sorted.length) return null;
  const index = Math.max(0, Math.ceil(sorted.length * fraction) - 1);
  return sorted[Math.min(sorted.length - 1, index)];
}

function savedTickDistribution(samples) {
  const values = samples
    .map(sample => sample.savedTicks)
    .filter(value => asNonNegativeInteger(value) != null)
    .map(Number)
    .sort((a, b) => a - b);
  if (!values.length) {
    return Object.freeze({ count: 0, min: null, median: null, p90: null, max: null, average: null });
  }
  const total = values.reduce((sum, value) => sum + value, 0);
  const middle = Math.floor(values.length / 2);
  const median = values.length % 2
    ? values[middle]
    : (values[middle - 1] + values[middle]) / 2;
  return Object.freeze({
    count: values.length,
    min: values[0],
    median,
    p90: percentile(values, 0.9),
    max: values[values.length - 1],
    average: total / values.length,
  });
}

function corpusSummary(stages) {
  const samples = new Map();
  const gameHashes = new Set();
  const editConfigHashes = new Set();
  const sourceRecordingHashes = new Set();
  let totalObservations = 0;
  let compactionFailures = 0;

  for (const stage of stages) {
    gameHashes.add(String(stage.source.gameHash));
    editConfigHashes.add(String(stage.source.editConfigHash));
    sourceRecordingHashes.add(String(stage.source.recordingHash));
    compactionFailures += Number(stage.collection?.compactionFailures) || 0;
    for (const observation of stage.observations) {
      totalObservations += 1;
      const key = `${stage.stageKey}|${observation.candidateRecordingHash}`;
      let sample = samples.get(key);
      if (!sample) {
        sample = {
          key,
          count: 0,
          fingerprints: new Set(),
          statuses: new Set(),
          checkpointAttempted: false,
          savedTicks: null,
        };
        samples.set(key, sample);
      }
      sample.count += 1;
      sample.fingerprints.add(String(observation.semanticFingerprint));
      sample.statuses.add(String(observation.status));
      sample.checkpointAttempted ||= observation.checkpointAttempted === true;
      if (observation.savedTicks != null) sample.savedTicks = Number(observation.savedTicks);
    }
  }

  let repeatedSamples = 0;
  let inconsistentSamples = 0;
  let uniqueCheckpointAttemptedSamples = 0;
  let cleanEquivalentSamples = 0;
  let mismatchSamples = 0;
  let fullOnlySamples = 0;
  const cleanEquivalent = [];

  for (const sample of samples.values()) {
    const inconsistent = sample.fingerprints.size > 1;
    if (sample.count > 1) repeatedSamples += 1;
    if (inconsistent) inconsistentSamples += 1;
    if (sample.checkpointAttempted) uniqueCheckpointAttemptedSamples += 1;
    if (sample.statuses.has('CHECKPOINT_ORACLE_MISMATCH')) mismatchSamples += 1;
    if (sample.statuses.size === 1 && sample.statuses.has('CHECKPOINT_ORACLE_FULL_ONLY')) fullOnlySamples += 1;
    if (!inconsistent
        && sample.statuses.size === 1
        && sample.statuses.has('CHECKPOINT_ORACLE_EQUIVALENT')) {
      cleanEquivalentSamples += 1;
      cleanEquivalent.push(sample);
    }
  }

  const uniqueSamples = samples.size;
  return Object.freeze({
    uniqueStageExecutions: stages.length,
    totalObservations,
    uniqueSamples,
    duplicateObservations: Math.max(0, totalObservations - uniqueSamples),
    repeatedSamples,
    inconsistentSamples,
    compactionFailures,
    uniqueCheckpointAttemptedSamples,
    cleanEquivalentSamples,
    mismatchSamples,
    fullOnlySamples,
    distinctGameHashes: gameHashes.size,
    distinctEditConfigHashes: editConfigHashes.size,
    distinctSourceRecordings: sourceRecordingHashes.size,
    savedTicks: savedTickDistribution(cleanEquivalent),
    reviewFlags: Object.freeze({
      hasMismatch: mismatchSamples > 0,
      hasInconsistentSamples: inconsistentSamples > 0,
      hasCollectionGaps: compactionFailures > 0,
      mixedGameIdentity: gameHashes.size > 1,
      mixedEditConfigIdentity: editConfigHashes.size > 1,
    }),
  });
}

async function createCorpusFromStagesV1(stages) {
  const unique = new Map();
  for (const stage of stages) {
    if (!unique.has(stage.hash)) unique.set(stage.hash, stage);
  }
  const dedupedStages = Object.freeze(
    [...unique.values()].sort((a, b) => {
      const left = String(a.hash);
      const right = String(b.hash);
      return left < right ? -1 : left > right ? 1 : 0;
    }),
  );
  if (dedupedStages.length > MAX_STAGES) {
    throw new Error('Checkpoint evidence corpus exceeds the post-dedup stage safety limit.');
  }
  const observationCount = dedupedStages.reduce(
    (total, stage) => total + (stage.observations?.length ?? 0),
    0,
  );
  if (observationCount > MAX_OBSERVATIONS) {
    throw new Error('Checkpoint evidence corpus exceeds the post-dedup observation safety limit.');
  }
  const unsigned = {
    schema: CORPUS_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    stages: dedupedStages,
    summary: corpusSummary(dedupedStages),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export async function validateMinimizerCheckpointEvidenceCorpusV1(corpus) {
  if (!isObject(corpus)) throw new Error('Checkpoint evidence corpus must be an object.');
  rejectForbiddenEvidenceKeys(corpus);
  if (corpus.schema !== CORPUS_SCHEMA) throw new Error('Checkpoint evidence corpus schema mismatch.');
  assertPolicy(corpus, 'Checkpoint evidence corpus');
  if (!Array.isArray(corpus.stages)) throw new Error('Checkpoint evidence corpus stages are missing.');
  if (corpus.stages.length > MAX_STAGES) throw new Error('Checkpoint evidence corpus exceeds the stage safety limit.');
  let observations = 0;
  for (const stage of corpus.stages) {
    observations += stage?.observations?.length ?? 0;
    if (observations > MAX_OBSERVATIONS) throw new Error('Checkpoint evidence corpus exceeds the observation safety limit.');
    await validateStageV1(stage);
  }

  const expected = await createCorpusFromStagesV1(corpus.stages);
  if (!(await sameCanonicalValue(expected.summary, corpus.summary))) {
    throw new Error('Checkpoint evidence corpus summary mismatch.');
  }
  if (expected.hash !== corpus.hash) throw new Error('Checkpoint evidence corpus hash mismatch.');
  return Object.freeze({ valid: true, kind: 'corpus', hash: corpus.hash, stages: corpus.stages });
}

export async function validateMinimizerCheckpointEvidenceArtifactV1(artifact) {
  if (artifact?.schema === MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
    return validateMinimizerCheckpointEvidenceReportV1(artifact);
  }
  if (artifact?.schema === CORPUS_SCHEMA) {
    return validateMinimizerCheckpointEvidenceCorpusV1(artifact);
  }
  throw new Error('Unsupported checkpoint evidence artifact schema.');
}

/**
 * Combine one or more hash-valid Phase -1I.4 reports / Phase -1I.5 corpora.
 *
 * Stage executions are deduplicated by their complete stage hash before population
 * statistics are calculated. Repeated executions that share a stageKey but have a
 * different stage hash remain independent observations, allowing contradictory
 * repeats to surface rather than disappear.
 */
export async function createMinimizerCheckpointEvidenceCorpusV1(artifacts = []) {
  if (!Array.isArray(artifacts) || !artifacts.length) {
    throw new Error('At least one checkpoint evidence report or corpus is required.');
  }
  const stages = [];
  for (const artifact of artifacts) {
    const validated = await validateMinimizerCheckpointEvidenceArtifactV1(artifact);
    stages.push(...validated.stages);
    if (stages.length > MAX_STAGES * 2) {
      throw new Error('Combined checkpoint evidence exceeds the import safety limit.');
    }
    const observationCount = stages.reduce((total, stage) => total + (stage.observations?.length ?? 0), 0);
    if (observationCount > MAX_OBSERVATIONS * 2) {
      throw new Error('Combined checkpoint evidence exceeds the observation import safety limit.');
    }
  }
  return createCorpusFromStagesV1(stages);
}

export function serializeMinimizerCheckpointEvidenceCorpusV1(corpus) {
  if (corpus?.schema !== CORPUS_SCHEMA || !isSha256(corpus?.hash)) {
    throw new TypeError('A complete Phase -1I.5 evidence corpus is required.');
  }
  return `${JSON.stringify(corpus, null, 2)}\n`;
}

export const MinimizerCheckpointCorpusLayout = Object.freeze({
  CORPUS_SCHEMA,
  POLICY,
  MAX_STAGES,
  MAX_OBSERVATIONS,
});
