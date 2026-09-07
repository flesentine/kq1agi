import {
  createMinimizerCheckpointEvidenceReportV1,
  hashCanonicalJsonV1,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointEvidenceCorpusV1,
  MinimizerCheckpointCorpusLayout,
  validateMinimizerCheckpointEvidenceCorpusV1,
} from './certification-minimizer-checkpoint-corpus.mjs';
import {
  createMinimizerCheckpointEvidenceReviewV1,
} from './certification-minimizer-checkpoint-review.mjs';

const COHORT_BUNDLE_SCHEMA = 'kq1agi-minimizer-checkpoint-evidence-cohort-review-v1';
const POLICY = MinimizerCheckpointCorpusLayout.POLICY;

function lexicalCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

async function cohortIdentity(stage) {
  const gameHash = String(stage?.source?.gameHash ?? '');
  const editConfigHash = String(stage?.source?.editConfigHash ?? '');
  if (!gameHash || !editConfigHash) throw new Error('Evidence stage is missing cohort identity.');
  const cohortKey = await hashCanonicalJsonV1({ gameHash, editConfigHash });
  return Object.freeze({ cohortKey, gameHash, editConfigHash });
}

async function buildCohortRecord(identity, stages) {
  const orderedStages = Object.freeze(
    [...stages].sort((a, b) => lexicalCompare(a.hash, b.hash)),
  );
  const report = await createMinimizerCheckpointEvidenceReportV1(orderedStages);
  const corpus = await createMinimizerCheckpointEvidenceCorpusV1([report]);
  const review = await createMinimizerCheckpointEvidenceReviewV1(corpus);

  if (review.identities.gameHashes.length !== 1
      || review.identities.gameHashes[0] !== identity.gameHash
      || review.identities.editConfigHashes.length !== 1
      || review.identities.editConfigHashes[0] !== identity.editConfigHash) {
    throw new Error('Identity-scoped review escaped its GAMEFILES/EditConfig cohort.');
  }

  return Object.freeze({
    cohortKey: identity.cohortKey,
    identity: Object.freeze({
      gameHash: identity.gameHash,
      editConfigHash: identity.editConfigHash,
    }),
    stageHashes: Object.freeze(orderedStages.map(stage => String(stage.hash))),
    corpusHash: corpus.hash,
    reviewHash: review.hash,
    reviewStatus: review.reviewStatus,
    blockers: review.blockers,
    sourceRecordingHashes: review.identities.sourceRecordingHashes,
    evidence: review.evidence,
    savedTicks: review.savedTicks,
    accelerationAllowed: false,
    thresholdPolicy: review.thresholdPolicy,
  });
}

/**
 * Partition one validated Phase -1I.5 corpus into deterministic GAMEFILES +
 * EditConfig cohorts and derive the already-qualified Phase -1I.6 review for each.
 *
 * The global corpus/review remain authoritative for global-policy discussion. This
 * bundle exists only to prevent mixed identities from hiding useful per-identity
 * evidence. It does not enable acceleration or define any threshold.
 */
export async function createMinimizerCheckpointEvidenceCohortReviewV1(corpus) {
  await validateMinimizerCheckpointEvidenceCorpusV1(corpus);
  const groups = new Map();

  for (const stage of corpus.stages ?? []) {
    const identity = await cohortIdentity(stage);
    let group = groups.get(identity.cohortKey);
    if (!group) {
      group = { identity, stages: [] };
      groups.set(identity.cohortKey, group);
    } else if (group.identity.gameHash !== identity.gameHash
        || group.identity.editConfigHash !== identity.editConfigHash) {
      throw new Error('Checkpoint evidence cohort hash collision.');
    }
    group.stages.push(stage);
  }

  const cohorts = [];
  for (const group of groups.values()) {
    cohorts.push(await buildCohortRecord(group.identity, group.stages));
  }
  cohorts.sort((a, b) => lexicalCompare(a.cohortKey, b.cohortKey));

  const statusCounts = {};
  for (const cohort of cohorts) {
    statusCounts[cohort.reviewStatus] = (statusCounts[cohort.reviewStatus] ?? 0) + 1;
  }
  const orderedStatusCounts = {};
  for (const key of Object.keys(statusCounts).sort(lexicalCompare)) {
    orderedStatusCounts[key] = statusCounts[key];
  }

  const unsigned = {
    schema: COHORT_BUNDLE_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    parentCorpusHash: String(corpus.hash),
    cohortIdentity: 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH',
    cohortCount: cohorts.length,
    statusCounts: Object.freeze(orderedStatusCounts),
    cohorts: Object.freeze(cohorts),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumUniqueCheckpointAttemptedSamples: null,
      minimumDistinctSourceRecordings: null,
      minimumSavedTickBenefit: null,
    }),
    caveats: Object.freeze([
      'GLOBAL_REVIEW_REMAINS_SEPARATE',
      'COHORTING_DOES_NOT_REMOVE_NON_IDENTITY_BLOCKERS',
      'BYTE_IDENTICAL_STAGE_RECORDS_DEDUPED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointEvidenceCohortReviewV1(bundle) {
  if (bundle?.schema !== COHORT_BUNDLE_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(bundle?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.7 cohort review bundle is required.');
  }
  return `${JSON.stringify(bundle, null, 2)}\n`;
}

export const MinimizerCheckpointCohortReviewLayout = Object.freeze({
  COHORT_BUNDLE_SCHEMA,
  POLICY,
});
