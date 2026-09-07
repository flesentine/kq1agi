import {
  hashCanonicalJsonV1,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  MinimizerCheckpointCorpusLayout,
  validateMinimizerCheckpointEvidenceCorpusV1,
} from './certification-minimizer-checkpoint-corpus.mjs';
import {
  createMinimizerCheckpointEvidenceCohortReviewV1,
} from './certification-minimizer-checkpoint-cohort-review.mjs';

const COVERAGE_SCHEMA = 'kq1agi-minimizer-checkpoint-evidence-coverage-profile-v1';
const POLICY = MinimizerCheckpointCorpusLayout.POLICY;

function lexicalCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

function numericCompare(left, right) {
  return Number(left) - Number(right);
}

function sortedUniqueStrings(values) {
  return Object.freeze(
    [...new Set(values.map(value => String(value)).filter(Boolean))].sort(lexicalCompare),
  );
}

function sortedUniqueIntegers(values) {
  return Object.freeze(
    [...new Set(
      values
        .filter(value => typeof value === 'number' && Number.isSafeInteger(value) && value >= 0),
    )].sort(numericCompare),
  );
}

function compactStage(stage) {
  const checkpoint = stage?.checkpoint ?? {};
  return Object.freeze({
    hash: String(stage?.hash ?? ''),
    stage: String(stage?.stage ?? ''),
    sourceRecordingHash: String(stage?.source?.recordingHash ?? ''),
    targetTick: Number(stage?.target?.tick),
    checkpointStatus: String(checkpoint.status ?? ''),
    checkpointReason: checkpoint.reason == null ? null : String(checkpoint.reason),
    checkpointTick: checkpoint.logicalTick == null ? null : Number(checkpoint.logicalTick),
    checkpointHash: checkpoint.hash == null ? null : String(checkpoint.hash),
    observationCount: Array.isArray(stage?.observations) ? stage.observations.length : 0,
    compactionFailures: Number(stage?.collection?.compactionFailures) || 0,
  });
}

function stageCounts(stages) {
  const counts = { 'phase-1e': 0, 'phase-1f': 0 };
  for (const stage of stages) {
    if (stage.stage === 'phase-1e' || stage.stage === 'phase-1f') counts[stage.stage] += 1;
  }
  return Object.freeze(counts);
}

function coverageFlags(profile) {
  return Object.freeze({
    missingPhase1E: profile.stageCounts['phase-1e'] === 0,
    missingPhase1F: profile.stageCounts['phase-1f'] === 0,
    singleStageRecord: profile.stageRecordCount === 1,
    singleSourceRecording: profile.sourceRecordingHashes.length === 1,
    singleTargetTick: profile.targetTicks.length === 1,
    noCapturedCheckpoint: profile.capturedCheckpointTicks.length === 0,
    singleCapturedCheckpointTick: profile.capturedCheckpointTicks.length === 1,
    hasUnavailableCheckpoint: profile.unavailableCheckpointReasons.length > 0,
  });
}

async function cohortKeyForStage(stage) {
  return hashCanonicalJsonV1({
    gameHash: String(stage?.source?.gameHash ?? ''),
    editConfigHash: String(stage?.source?.editConfigHash ?? ''),
  });
}

async function buildCoverageCohort(cohortReview, stages) {
  const compactStages = Object.freeze(
    stages.map(compactStage).sort((a, b) => lexicalCompare(a.hash, b.hash)),
  );
  const sourceRecordingHashes = sortedUniqueStrings(
    compactStages.map(stage => stage.sourceRecordingHash),
  );
  const targetTicks = sortedUniqueIntegers(compactStages.map(stage => stage.targetTick));
  const capturedCheckpointTicks = sortedUniqueIntegers(
    compactStages.map(stage => stage.checkpointTick),
  );
  const checkpointHashes = sortedUniqueStrings(
    compactStages.map(stage => stage.checkpointHash),
  );
  const unavailableCheckpointReasons = sortedUniqueStrings(
    compactStages
      .filter(stage => stage.checkpointHash == null)
      .map(stage => stage.checkpointReason),
  );
  const counts = stageCounts(compactStages);

  const base = {
    cohortKey: cohortReview.cohortKey,
    identity: cohortReview.identity,
    reviewHash: cohortReview.reviewHash,
    reviewStatus: cohortReview.reviewStatus,
    blockers: cohortReview.blockers,
    stageRecordCount: compactStages.length,
    observationCount: compactStages.reduce((sum, stage) => sum + stage.observationCount, 0),
    compactionFailures: compactStages.reduce((sum, stage) => sum + stage.compactionFailures, 0),
    stageCounts: counts,
    sourceRecordingHashes,
    targetTicks,
    capturedCheckpointTicks,
    checkpointHashes,
    unavailableCheckpointReasons,
    stages: compactStages,
  };

  return Object.freeze({
    ...base,
    coverageFlags: coverageFlags(base),
  });
}

/**
 * Describe the shape of one validated evidence corpus without making a sufficiency
 * or acceleration decision. Coverage is partitioned by the same exact GAMEFILES +
 * EditConfig identity used by Phase -1I.7 and linked back to each I.7 review.
 */
export async function createMinimizerCheckpointEvidenceCoverageProfileV1(corpus) {
  await validateMinimizerCheckpointEvidenceCorpusV1(corpus);
  const cohortBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(corpus);

  const stagesByCohort = new Map();
  for (const stage of corpus.stages ?? []) {
    const cohortKey = await cohortKeyForStage(stage);
    const stages = stagesByCohort.get(cohortKey) ?? [];
    stages.push(stage);
    stagesByCohort.set(cohortKey, stages);
  }

  const cohorts = [];
  for (const cohortReview of cohortBundle.cohorts) {
    const stages = stagesByCohort.get(cohortReview.cohortKey) ?? [];
    if (stages.length !== cohortReview.stageHashes.length) {
      throw new Error('Coverage profile cohort stage count disagrees with Phase -1I.7.');
    }
    const stageHashes = stages.map(stage => String(stage.hash)).sort(lexicalCompare);
    const expectedStageHashes = [...cohortReview.stageHashes].sort(lexicalCompare);
    if (stageHashes.some((hash, index) => hash !== expectedStageHashes[index])) {
      throw new Error('Coverage profile cohort stage identity disagrees with Phase -1I.7.');
    }
    cohorts.push(await buildCoverageCohort(cohortReview, stages));
  }
  cohorts.sort((a, b) => lexicalCompare(a.cohortKey, b.cohortKey));

  const flagCounts = {};
  for (const cohort of cohorts) {
    for (const [flag, enabled] of Object.entries(cohort.coverageFlags)) {
      if (enabled) flagCounts[flag] = (flagCounts[flag] ?? 0) + 1;
    }
  }
  const orderedFlagCounts = {};
  for (const key of Object.keys(flagCounts).sort(lexicalCompare)) {
    orderedFlagCounts[key] = flagCounts[key];
  }

  const unsigned = {
    schema: COVERAGE_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    coverageDecision: 'DESCRIPTIVE_ONLY',
    parentCorpusHash: String(corpus.hash),
    cohortReviewHash: String(cohortBundle.hash),
    cohortIdentity: cohortBundle.cohortIdentity,
    cohortCount: cohorts.length,
    flagCounts: Object.freeze(orderedFlagCounts),
    cohorts: Object.freeze(cohorts),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumUniqueCheckpointAttemptedSamples: null,
      minimumDistinctSourceRecordings: null,
      minimumTargetTickCoverage: null,
      minimumCheckpointTickCoverage: null,
      minimumSavedTickBenefit: null,
    }),
    caveats: Object.freeze([
      'COVERAGE_FLAGS_ARE_DESCRIPTIVE_NOT_BLOCKERS',
      'GLOBAL_AND_COHORT_REVIEWS_REMAIN_SEPARATE',
      'BYTE_IDENTICAL_STAGE_RECORDS_DEDUPED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointEvidenceCoverageProfileV1(profile) {
  if (profile?.schema !== COVERAGE_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(profile?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.8 coverage profile is required.');
  }
  return `${JSON.stringify(profile, null, 2)}\n`;
}

export const MinimizerCheckpointCoverageLayout = Object.freeze({
  COVERAGE_SCHEMA,
  POLICY,
});
