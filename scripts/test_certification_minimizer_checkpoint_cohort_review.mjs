import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
  hashMinimizerCheckpointObservationSemanticV1,
  MinimizerCheckpointEvidenceLayout,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointEvidenceCorpusV1,
} from '../web/certification-minimizer-checkpoint-corpus.mjs';
import {
  createMinimizerCheckpointEvidenceReviewV1,
} from '../web/certification-minimizer-checkpoint-review.mjs';
import {
  createMinimizerCheckpointEvidenceCohortReviewV1,
  MinimizerCheckpointCohortReviewLayout,
  serializeMinimizerCheckpointEvidenceCohortReviewV1,
} from '../web/certification-minimizer-checkpoint-cohort-review.mjs';

const sha = char => `sha256:${char.repeat(64)}`;

const identityA = Object.freeze({
  source: sha('1'),
  game: sha('2'),
  edit: sha('3'),
  checkpoint: sha('4'),
});
const identityB = Object.freeze({
  source: sha('5'),
  game: sha('6'),
  edit: sha('7'),
  checkpoint: sha('8'),
});
const identityASource2 = Object.freeze({
  source: sha('9'),
  game: identityA.game,
  edit: identityA.edit,
  checkpoint: sha('a'),
});
const sameGameDifferentEdit = Object.freeze({
  source: sha('b'),
  game: identityA.game,
  edit: sha('d'),
  checkpoint: sha('e'),
});
const differentGameSameEdit = Object.freeze({
  source: sha('f'),
  game: sha('0'),
  edit: identityA.edit,
  checkpoint: sha('1'),
});

async function observation({
  candidate,
  sourceHash,
  checkpointHash,
  status = 'CHECKPOINT_ORACLE_EQUIVALENT',
  savedTicks = 5,
  checkpointEvidenceHash = sha('b'),
} = {}) {
  const attempted = status !== 'CHECKPOINT_ORACLE_FULL_ONLY';
  const equivalent = status === 'CHECKPOINT_ORACLE_EQUIVALENT';
  const mismatch = status === 'CHECKPOINT_ORACLE_MISMATCH';
  const evidenceHash = sha('c');
  const decisionHash = sha('d');
  const core = {
    schema: MinimizerCheckpointEvidenceLayout.OBSERVATION_SCHEMA,
    candidateRecordingHash: candidate,
    status,
    reason: mismatch
      ? 'evidence'
      : status === 'CHECKPOINT_ORACLE_FULL_ONLY'
        ? 'checkpoint-incompatible'
        : status,
    checkpointAttempted: attempted,
    checkpointTrusted: equivalent,
    savedTicks: equivalent ? savedTicks : null,
    fullTelemetry: { consumedTicks: 12, replayStartTick: 0 },
    checkpointTelemetry: attempted ? { consumedTicks: 7, replayStartTick: 5 } : null,
    compatibility: {
      checkpointTick: 5,
      sourceRecordingHash: sourceHash,
      candidateRecordingHash: candidate,
      checkpointHash,
    },
    comparison: equivalent
      ? { category: 'exact', equivalent: true, differencePath: null, differenceReason: null }
      : mismatch
        ? {
          category: 'evidence',
          equivalent: false,
          differencePath: '$.evidence.edited.workerPayload[0]',
          differenceReason: 'value',
        }
        : null,
    authoritativeStatus: 'REPLAY_MATCH',
    authoritativeResultStatus: 'MATCH',
    authoritativeResultTick: 12,
    fullDecisionHash: decisionHash,
    checkpointDecisionHash: attempted ? decisionHash : null,
    fullEvidenceValidation: { valid: true, reason: 'complete' },
    checkpointEvidenceValidation: attempted ? { valid: true, reason: 'complete' } : null,
    fullEvidenceHash: evidenceHash,
    checkpointEvidenceHash: attempted
      ? (equivalent ? evidenceHash : checkpointEvidenceHash)
      : null,
  };
  return Object.freeze({
    ...core,
    semanticFingerprint: await hashMinimizerCheckpointObservationSemanticV1(core),
  });
}

function sourceRecording(identity) {
  return Object.freeze({
    hash: identity.source,
    gameHash: identity.game,
    gameBytes: 17295,
    editConfigHash: identity.edit,
    finalTick: 12,
    events: [{ tick: 2 }],
    random: [{ tick: 2 }],
    releaseTicks: [1, 3, 6, 8, 12],
  });
}

function shadowState(identity) {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
    selection: Object.freeze({
      desiredCheckpointTick: 6,
      pauseBeforeTick: 6,
      checkpointTick: 5,
    }),
    checkpoint: Object.freeze({
      hash: identity.checkpoint,
      logicalTick: 5,
    }),
  });
}

async function stage(identity, obs, {
  stageName = 'phase-1e',
  failures = [],
} = {}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording(identity),
    targetDivergence: { tick: 12 },
    shadowState: shadowState(identity),
    observations: [obs],
    collectionErrorCandidateHashes: failures,
    outcome: { status: 'MINIMIZED', attempts: 1 },
  });
}

async function corpusFromStages(stages) {
  const report = await createMinimizerCheckpointEvidenceReportV1(stages);
  return createMinimizerCheckpointEvidenceCorpusV1([report]);
}

const cleanA = await observation({
  candidate: sha('e'),
  sourceHash: identityA.source,
  checkpointHash: identityA.checkpoint,
  savedTicks: 5,
});
const cleanB = await observation({
  candidate: sha('f'),
  sourceHash: identityB.source,
  checkpointHash: identityB.checkpoint,
  savedTicks: 9,
});

const mixedCorpus = await corpusFromStages([
  await stage(identityA, cleanA),
  await stage(identityB, cleanB, { stageName: 'phase-1f' }),
]);
const globalMixedReview = await createMinimizerCheckpointEvidenceReviewV1(mixedCorpus);
assert.equal(globalMixedReview.reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.equal(globalMixedReview.blockers.includes('MIXED_GAME_IDENTITY'), true);
assert.equal(globalMixedReview.blockers.includes('MIXED_EDIT_CONFIG_IDENTITY'), true);

const mixedBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(mixedCorpus);
assert.equal(mixedBundle.schema, MinimizerCheckpointCohortReviewLayout.COHORT_BUNDLE_SCHEMA);
assert.equal(mixedBundle.policy, 'full-replay-authoritative');
assert.equal(mixedBundle.policyFrozen, false);
assert.equal(mixedBundle.policyDecision, 'EVIDENCE_ONLY');
assert.equal(mixedBundle.accelerationAllowed, false);
assert.equal(mixedBundle.parentCorpusHash, mixedCorpus.hash);
assert.equal(mixedBundle.cohortIdentity, 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH');
assert.equal(mixedBundle.cohortCount, 2);
assert.deepEqual(mixedBundle.statusCounts, { CLEAN_EVIDENCE_THRESHOLD_UNSET: 2 });
assert.equal(mixedBundle.thresholdPolicy.status, 'UNSET');
assert.equal(mixedBundle.thresholdPolicy.minimumUniqueCheckpointAttemptedSamples, null);
assert.equal(mixedBundle.thresholdPolicy.minimumDistinctSourceRecordings, null);
assert.equal(mixedBundle.thresholdPolicy.minimumSavedTickBenefit, null);

const byGame = new Map(mixedBundle.cohorts.map(cohort => [cohort.identity.gameHash, cohort]));
const cohortA = byGame.get(identityA.game);
const cohortB = byGame.get(identityB.game);
assert.ok(cohortA);
assert.ok(cohortB);
for (const cohort of [cohortA, cohortB]) {
  assert.equal(cohort.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');
  assert.deepEqual(cohort.blockers, []);
  assert.equal(cohort.accelerationAllowed, false);
  assert.equal(cohort.thresholdPolicy.status, 'UNSET');
  assert.equal(cohort.stageHashes.length, 1);
}
assert.equal(cohortA.identity.editConfigHash, identityA.edit);
assert.equal(cohortA.evidence.cleanEquivalentSamples, 1);
assert.equal(cohortA.savedTicks.min, 5);
assert.equal(cohortB.identity.editConfigHash, identityB.edit);
assert.equal(cohortB.evidence.cleanEquivalentSamples, 1);
assert.equal(cohortB.savedTicks.min, 9);

const allStageHashes = mixedBundle.cohorts.flatMap(cohort => cohort.stageHashes).sort();
const parentStageHashes = mixedCorpus.stages.map(stageRecord => stageRecord.hash).sort();
assert.deepEqual(allStageHashes, parentStageHashes, 'Every parent stage record must appear in exactly one identity cohort.');

const mixedBundleAgain = await createMinimizerCheckpointEvidenceCohortReviewV1(mixedCorpus);
assert.equal(mixedBundleAgain.hash, mixedBundle.hash, 'Cohort bundle must be deterministic.');

const sameIdentitySecondSourceObs = await observation({
  candidate: sha('0'),
  sourceHash: identityASource2.source,
  checkpointHash: identityASource2.checkpoint,
  savedTicks: 7,
});
const sameIdentityCorpus = await corpusFromStages([
  await stage(identityA, cleanA),
  await stage(identityASource2, sameIdentitySecondSourceObs, { stageName: 'phase-1f' }),
]);
const sameIdentityBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(sameIdentityCorpus);
assert.equal(sameIdentityBundle.cohortCount, 1, 'Different source recordings must stay in one GAMEFILES/EditConfig cohort.');
assert.equal(sameIdentityBundle.cohorts[0].evidence.distinctSourceRecordings, 2);
assert.deepEqual(
  sameIdentityBundle.cohorts[0].sourceRecordingHashes,
  [identityA.source, identityASource2.source].sort(),
);
assert.equal(sameIdentityBundle.cohorts[0].reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');

const sameGameDifferentEditObs = await observation({
  candidate: sha('4'),
  sourceHash: sameGameDifferentEdit.source,
  checkpointHash: sameGameDifferentEdit.checkpoint,
  savedTicks: 6,
});
const editSplitBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(
  await corpusFromStages([
    await stage(identityA, cleanA),
    await stage(sameGameDifferentEdit, sameGameDifferentEditObs, { stageName: 'phase-1f' }),
  ]),
);
assert.equal(editSplitBundle.cohortCount, 2, 'Changing only EditConfig identity must split cohorts.');

const differentGameSameEditObs = await observation({
  candidate: sha('5'),
  sourceHash: differentGameSameEdit.source,
  checkpointHash: differentGameSameEdit.checkpoint,
  savedTicks: 8,
});
const gameSplitBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(
  await corpusFromStages([
    await stage(identityA, cleanA),
    await stage(differentGameSameEdit, differentGameSameEditObs, { stageName: 'phase-1f' }),
  ]),
);
assert.equal(gameSplitBundle.cohortCount, 2, 'Changing only GAMEFILES identity must split cohorts.');

const mismatchA = await observation({
  candidate: sha('a'),
  sourceHash: identityA.source,
  checkpointHash: identityA.checkpoint,
  status: 'CHECKPOINT_ORACLE_MISMATCH',
  checkpointEvidenceHash: sha('1'),
});
const mismatchCorpus = await corpusFromStages([
  await stage(identityA, mismatchA),
  await stage(identityB, cleanB, { stageName: 'phase-1f' }),
]);
const mismatchBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(mismatchCorpus);
const mismatchCohort = mismatchBundle.cohorts.find(cohort => cohort.identity.gameHash === identityA.game);
const cleanCohort = mismatchBundle.cohorts.find(cohort => cohort.identity.gameHash === identityB.game);
assert.equal(mismatchCohort.reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.deepEqual(mismatchCohort.blockers, ['CHECKPOINT_MISMATCH']);
assert.equal(cleanCohort.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');
assert.deepEqual(cleanCohort.blockers, []);

const fullOnlyA = await observation({
  candidate: sha('2'),
  sourceHash: identityA.source,
  checkpointHash: identityA.checkpoint,
  status: 'CHECKPOINT_ORACLE_FULL_ONLY',
});
const noAttemptBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(
  await corpusFromStages([await stage(identityA, fullOnlyA)]),
);
assert.equal(noAttemptBundle.cohortCount, 1);
assert.equal(noAttemptBundle.cohorts[0].reviewStatus, 'NO_COMPATIBLE_SAMPLES');
assert.deepEqual(noAttemptBundle.cohorts[0].blockers, ['NO_CHECKPOINT_ATTEMPTS']);

const gapBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(
  await corpusFromStages([
    await stage(identityA, fullOnlyA, { failures: [sha('3')] }),
  ]),
);
assert.equal(gapBundle.cohorts[0].reviewStatus, 'NO_COMPATIBLE_SAMPLES');
assert.deepEqual(gapBundle.cohorts[0].blockers, ['NO_CHECKPOINT_ATTEMPTS', 'COLLECTION_GAP']);

const serialized = serializeMinimizerCheckpointEvidenceCohortReviewV1(mixedBundle);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload": ['), false);
assert.match(mixedBundle.hash, /^sha256:[0-9a-f]{64}$/);

const tamperedCorpus = structuredClone(mixedCorpus);
tamperedCorpus.summary.uniqueSamples = 999;
await assert.rejects(
  createMinimizerCheckpointEvidenceCohortReviewV1(tamperedCorpus),
  /summary mismatch|hash mismatch/,
);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-evidence-cohorts-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointEvidenceCohortReview'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointEvidenceCohortReviewV1'), true);
const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf("replayButton.addEventListener", editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointEvidenceCohortReviewV1'), false);
assert.equal(editSection.includes('refreshEvidenceCohortReview'), false);

console.log('minimizer checkpoint evidence cohort review tests: PASS');
