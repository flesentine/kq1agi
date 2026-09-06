import {
  hashCanonicalJsonV1,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  MinimizerCheckpointCorpusLayout,
  validateMinimizerCheckpointEvidenceCorpusV1,
} from './certification-minimizer-checkpoint-corpus.mjs';

const REVIEW_SCHEMA = 'kq1agi-minimizer-checkpoint-evidence-review-v1';
const POLICY = MinimizerCheckpointCorpusLayout.POLICY;

const BLOCKER_ORDER = Object.freeze([
  'NO_CHECKPOINT_ATTEMPTS',
  'CHECKPOINT_MISMATCH',
  'INCONSISTENT_REPEAT',
  'COLLECTION_GAP',
  'MIXED_GAME_IDENTITY',
  'MIXED_EDIT_CONFIG_IDENTITY',
]);

function sortedUnique(values) {
  return Object.freeze(
    [...new Set(values.map(value => String(value)).filter(Boolean))]
      .sort((a, b) => (a < b ? -1 : a > b ? 1 : 0)),
  );
}

function evidenceBlockers(summary) {
  const blockers = [];
  if ((Number(summary.uniqueCheckpointAttemptedSamples) || 0) === 0) {
    blockers.push('NO_CHECKPOINT_ATTEMPTS');
  }
  if ((Number(summary.mismatchSamples) || 0) > 0) {
    blockers.push('CHECKPOINT_MISMATCH');
  }
  if ((Number(summary.inconsistentSamples) || 0) > 0) {
    blockers.push('INCONSISTENT_REPEAT');
  }
  if ((Number(summary.compactionFailures) || 0) > 0) {
    blockers.push('COLLECTION_GAP');
  }
  if ((Number(summary.distinctGameHashes) || 0) > 1) {
    blockers.push('MIXED_GAME_IDENTITY');
  }
  if ((Number(summary.distinctEditConfigHashes) || 0) > 1) {
    blockers.push('MIXED_EDIT_CONFIG_IDENTITY');
  }
  return Object.freeze(BLOCKER_ORDER.filter(code => blockers.includes(code)));
}

function reviewStatus(blockers) {
  if (blockers.includes('NO_CHECKPOINT_ATTEMPTS')) return 'NO_COMPATIBLE_SAMPLES';
  if (blockers.length) return 'BLOCKED_BY_EVIDENCE';
  return 'CLEAN_EVIDENCE_THRESHOLD_UNSET';
}

function evidenceCounts(summary) {
  return Object.freeze({
    uniqueStageRecords: Number(summary.uniqueStageRecords) || 0,
    totalObservations: Number(summary.totalObservations) || 0,
    uniqueSamples: Number(summary.uniqueSamples) || 0,
    duplicateObservations: Number(summary.duplicateObservations) || 0,
    repeatedSamples: Number(summary.repeatedSamples) || 0,
    inconsistentSamples: Number(summary.inconsistentSamples) || 0,
    compactionFailures: Number(summary.compactionFailures) || 0,
    uniqueCheckpointAttemptedSamples: Number(summary.uniqueCheckpointAttemptedSamples) || 0,
    cleanEquivalentSamples: Number(summary.cleanEquivalentSamples) || 0,
    mismatchSamples: Number(summary.mismatchSamples) || 0,
    fullOnlySamples: Number(summary.fullOnlySamples) || 0,
    distinctGameHashes: Number(summary.distinctGameHashes) || 0,
    distinctEditConfigHashes: Number(summary.distinctEditConfigHashes) || 0,
    distinctSourceRecordings: Number(summary.distinctSourceRecordings) || 0,
  });
}

function identitySummary(corpus) {
  const gameHashes = [];
  const editConfigHashes = [];
  const sourceRecordingHashes = [];
  for (const stage of corpus.stages ?? []) {
    gameHashes.push(stage?.source?.gameHash);
    editConfigHashes.push(stage?.source?.editConfigHash);
    sourceRecordingHashes.push(stage?.source?.recordingHash);
  }
  return Object.freeze({
    gameHashes: sortedUnique(gameHashes),
    editConfigHashes: sortedUnique(editConfigHashes),
    sourceRecordingHashes: sortedUnique(sourceRecordingHashes),
  });
}

/**
 * Derive a deterministic review record from one hash-valid Phase -1I.5 corpus.
 *
 * This is deliberately not an acceleration policy. It can identify evidence that
 * blocks policy review, but it never defines a minimum population or permits any
 * candidate to skip its mandatory full replay.
 */
export async function createMinimizerCheckpointEvidenceReviewV1(corpus) {
  await validateMinimizerCheckpointEvidenceCorpusV1(corpus);

  const counts = evidenceCounts(corpus.summary ?? {});
  const blockers = evidenceBlockers(counts);
  const identities = identitySummary(corpus);
  const status = reviewStatus(blockers);
  const unsigned = {
    schema: REVIEW_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    corpusHash: String(corpus.hash),
    corpusSchema: String(corpus.schema),
    reviewStatus: status,
    blockers,
    evidence: counts,
    identities,
    savedTicks: Object.freeze({ ...(corpus.summary?.savedTicks ?? {}) }),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumUniqueCheckpointAttemptedSamples: null,
      minimumDistinctSourceRecordings: null,
      minimumSavedTickBenefit: null,
    }),
    caveats: Object.freeze([
      'BYTE_IDENTICAL_STAGE_RECORDS_DEDUPED',
      'NO_EXECUTION_NONCE_IN_PHASE_1I4',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointEvidenceReviewV1(review) {
  if (review?.schema !== REVIEW_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(review?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.6 evidence review is required.');
  }
  return `${JSON.stringify(review, null, 2)}\n`;
}

export const MinimizerCheckpointReviewLayout = Object.freeze({
  REVIEW_SCHEMA,
  POLICY,
  BLOCKER_ORDER,
});
