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
  createMinimizerCheckpointEvidenceCohortReviewV1,
} from '../web/certification-minimizer-checkpoint-cohort-review.mjs';
import {
  createMinimizerCheckpointEvidenceCoverageProfileV1,
  MinimizerCheckpointCoverageLayout,
  serializeMinimizerCheckpointEvidenceCoverageProfileV1,
} from '../web/certification-minimizer-checkpoint-coverage.mjs';

const sha = char => `sha256:${char.repeat(64)}`;

const identityA = Object.freeze({ game: sha('1'), edit: sha('2') });
const identityB = Object.freeze({ game: sha('3'), edit: sha('4') });

function sourceRecording({ sourceHash, identity, finalTick = 24 }) {
  return Object.freeze({
    hash: sourceHash,
    gameHash: identity.game,
    gameBytes: 17295,
    editConfigHash: identity.edit,
    finalTick,
    events: [{ tick: 2 }],
    random: [{ tick: 2 }],
    releaseTicks: [1, 3, 6, 8, 12, 16, 20, 24],
  });
}

function capturedShadowState({ checkpointHash, checkpointTick }) {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
    selection: Object.freeze({
      desiredCheckpointTick: checkpointTick + 1,
      pauseBeforeTick: checkpointTick + 1,
      checkpointTick,
    }),
    checkpoint: Object.freeze({
      hash: checkpointHash,
      logicalTick: checkpointTick,
    }),
  });
}

function unavailableShadowState(reason = 'no-recorded-release') {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
    reason,
    selection: Object.freeze({
      status: 'MINIMIZER_SHADOW_NO_BOUNDARY',
      reason,
      targetTick: 12,
    }),
  });
}

async function observation({
  candidate,
  sourceHash,
  checkpointHash,
  checkpointTick,
  status = 'CHECKPOINT_ORACLE_EQUIVALENT',
  savedTicks = 5,
} = {}) {
  const attempted = status !== 'CHECKPOINT_ORACLE_FULL_ONLY';
  const equivalent = status === 'CHECKPOINT_ORACLE_EQUIVALENT';
  const mismatch = status === 'CHECKPOINT_ORACLE_MISMATCH';
  const evidenceHash = sha('a');
  const checkpointEvidenceHash = mismatch ? sha('b') : evidenceHash;
  const decisionHash = sha('c');
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
    fullTelemetry: { consumedTicks: 24, replayStartTick: 0 },
    checkpointTelemetry: attempted ? { consumedTicks: 12, replayStartTick: checkpointTick ?? 0 } : null,
    compatibility: attempted ? {
      checkpointTick,
      sourceRecordingHash: sourceHash,
      candidateRecordingHash: candidate,
      checkpointHash,
    } : null,
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
    authoritativeResultTick: 24,
    fullDecisionHash: decisionHash,
    checkpointDecisionHash: attempted ? decisionHash : null,
    fullEvidenceValidation: { valid: true, reason: 'complete' },
    checkpointEvidenceValidation: attempted ? { valid: true, reason: 'complete' } : null,
    fullEvidenceHash: evidenceHash,
    checkpointEvidenceHash: attempted ? checkpointEvidenceHash : null,
  };
  return Object.freeze({
    ...core,
    semanticFingerprint: await hashMinimizerCheckpointObservationSemanticV1(core),
  });
}

async function stage({
  stageName,
  identity,
  sourceHash,
  targetTick,
  checkpointHash,
  checkpointTick,
  observationRecord,
  unavailableReason = null,
  failures = [],
}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording({ sourceHash, identity }),
    targetDivergence: { tick: targetTick },
    shadowState: unavailableReason
      ? unavailableShadowState(unavailableReason)
      : capturedShadowState({ checkpointHash, checkpointTick }),
    observations: observationRecord ? [observationRecord] : [],
    collectionErrorCandidateHashes: failures,
    outcome: { status: 'MINIMIZED', attempts: 1 },
  });
}

async function corpusFromStages(stages) {
  const report = await createMinimizerCheckpointEvidenceReportV1(stages);
  return createMinimizerCheckpointEvidenceCorpusV1([report]);
}

const sourceA1 = sha('5');
const sourceA2 = sha('6');
const cpA1 = sha('7');
const cpA2 = sha('8');

const obsA1 = await observation({
  candidate: sha('d'),
  sourceHash: sourceA1,
  checkpointHash: cpA1,
  checkpointTick: 5,
  savedTicks: 5,
});
const obsA2 = await observation({
  candidate: sha('e'),
  sourceHash: sourceA2,
  checkpointHash: cpA2,
  checkpointTick: 10,
  savedTicks: 9,
});

const diverseCorpus = await corpusFromStages([
  await stage({
    stageName: 'phase-1e',
    identity: identityA,
    sourceHash: sourceA1,
    targetTick: 12,
    checkpointHash: cpA1,
    checkpointTick: 5,
    observationRecord: obsA1,
  }),
  await stage({
    stageName: 'phase-1f',
    identity: identityA,
    sourceHash: sourceA2,
    targetTick: 20,
    checkpointHash: cpA2,
    checkpointTick: 10,
    observationRecord: obsA2,
  }),
]);

const diverseProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(diverseCorpus);
assert.equal(diverseProfile.schema, MinimizerCheckpointCoverageLayout.COVERAGE_SCHEMA);
assert.equal(diverseProfile.policy, 'full-replay-authoritative');
assert.equal(diverseProfile.policyFrozen, false);
assert.equal(diverseProfile.policyDecision, 'EVIDENCE_ONLY');
assert.equal(diverseProfile.accelerationAllowed, false);
assert.equal(diverseProfile.coverageDecision, 'DESCRIPTIVE_ONLY');
assert.equal(diverseProfile.parentCorpusHash, diverseCorpus.hash);
assert.equal(diverseProfile.cohortCount, 1);
assert.equal(diverseProfile.thresholdPolicy.status, 'UNSET');
assert.equal(diverseProfile.thresholdPolicy.minimumUniqueCheckpointAttemptedSamples, null);
assert.equal(diverseProfile.thresholdPolicy.minimumDistinctSourceRecordings, null);
assert.equal(diverseProfile.thresholdPolicy.minimumTargetTickCoverage, null);
assert.equal(diverseProfile.thresholdPolicy.minimumCheckpointTickCoverage, null);
assert.equal(diverseProfile.thresholdPolicy.minimumSavedTickBenefit, null);

const diverse = diverseProfile.cohorts[0];
assert.deepEqual(diverse.stageCounts, { 'phase-1e': 1, 'phase-1f': 1 });
assert.deepEqual(diverse.sourceRecordingHashes, [sourceA1, sourceA2].sort());
assert.deepEqual(diverse.targetTicks, [12, 20]);
assert.deepEqual(diverse.capturedCheckpointTicks, [5, 10]);
assert.deepEqual(diverse.checkpointHashes, [cpA1, cpA2].sort());
assert.deepEqual(diverse.unavailableCheckpointReasons, []);
assert.equal(diverse.stageRecordCount, 2);
assert.equal(diverse.observationCount, 2);
assert.equal(diverse.compactionFailures, 0);
assert.deepEqual(diverse.coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: false,
  singleStageRecord: false,
  singleSourceRecording: false,
  singleTargetTick: false,
  noCapturedCheckpoint: false,
  singleCapturedCheckpointTick: false,
  hasUnavailableCheckpoint: false,
});
assert.equal(diverse.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');
assert.deepEqual(diverse.blockers, []);

const cohortBundle = await createMinimizerCheckpointEvidenceCohortReviewV1(diverseCorpus);
assert.equal(diverseProfile.cohortReviewHash, cohortBundle.hash);
assert.equal(diverse.reviewHash, cohortBundle.cohorts[0].reviewHash);

const concentratedCorpus = await corpusFromStages([
  await stage({
    stageName: 'phase-1e',
    identity: identityA,
    sourceHash: sourceA1,
    targetTick: 12,
    checkpointHash: cpA1,
    checkpointTick: 5,
    observationRecord: obsA1,
  }),
]);
const concentratedProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(concentratedCorpus);
const concentrated = concentratedProfile.cohorts[0];
assert.deepEqual(concentrated.coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: true,
  singleStageRecord: true,
  singleSourceRecording: true,
  singleTargetTick: true,
  noCapturedCheckpoint: false,
  singleCapturedCheckpointTick: true,
  hasUnavailableCheckpoint: false,
});
assert.equal(concentratedProfile.flagCounts.missingPhase1F, 1);
assert.equal(concentratedProfile.flagCounts.singleSourceRecording, 1);
assert.equal(concentrated.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');

const unavailableCorpus = await corpusFromStages([
  await stage({
    stageName: 'phase-1f',
    identity: identityA,
    sourceHash: sourceA1,
    targetTick: 12,
    unavailableReason: 'no-recorded-release',
    observationRecord: null,
  }),
]);
const unavailableProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(unavailableCorpus);
const unavailable = unavailableProfile.cohorts[0];
assert.deepEqual(unavailable.capturedCheckpointTicks, []);
assert.deepEqual(unavailable.checkpointHashes, []);
assert.deepEqual(unavailable.unavailableCheckpointReasons, ['no-recorded-release']);
assert.equal(unavailable.coverageFlags.noCapturedCheckpoint, true);
assert.equal(unavailable.coverageFlags.hasUnavailableCheckpoint, true);
assert.equal(unavailable.coverageFlags.missingPhase1E, true);
assert.equal(unavailable.coverageFlags.missingPhase1F, false);
assert.equal(unavailable.reviewStatus, 'NO_COMPATIBLE_SAMPLES');

const sourceB = sha('9');
const cpB = sha('f');
const obsB = await observation({
  candidate: sha('0'),
  sourceHash: sourceB,
  checkpointHash: cpB,
  checkpointTick: 6,
  savedTicks: 6,
});
const mixedCorpus = await corpusFromStages([
  ...diverseCorpus.stages,
  await stage({
    stageName: 'phase-1e',
    identity: identityB,
    sourceHash: sourceB,
    targetTick: 14,
    checkpointHash: cpB,
    checkpointTick: 6,
    observationRecord: obsB,
  }),
]);
const mixedProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(mixedCorpus);
assert.equal(mixedProfile.cohortCount, 2);
assert.equal(mixedProfile.cohorts.every(cohort => cohort.identity.gameHash && cohort.identity.editConfigHash), true);

const mismatchObs = await observation({
  candidate: sha('b'),
  sourceHash: sourceA1,
  checkpointHash: cpA1,
  checkpointTick: 5,
  status: 'CHECKPOINT_ORACLE_MISMATCH',
});
const mismatchProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(
  await corpusFromStages([
    await stage({
      stageName: 'phase-1e',
      identity: identityA,
      sourceHash: sourceA1,
      targetTick: 12,
      checkpointHash: cpA1,
      checkpointTick: 5,
      observationRecord: mismatchObs,
    }),
  ]),
);
assert.equal(mismatchProfile.coverageDecision, 'DESCRIPTIVE_ONLY');
assert.equal(mismatchProfile.cohorts[0].reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.deepEqual(mismatchProfile.cohorts[0].blockers, ['CHECKPOINT_MISMATCH']);
assert.equal(mismatchProfile.accelerationAllowed, false);

const profileAgain = await createMinimizerCheckpointEvidenceCoverageProfileV1(diverseCorpus);
assert.equal(profileAgain.hash, diverseProfile.hash, 'Coverage profile must be deterministic.');

const serialized = serializeMinimizerCheckpointEvidenceCoverageProfileV1(diverseProfile);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"coverageDecision": "DESCRIPTIVE_ONLY"'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"workerPayload": ['), false);
assert.match(diverseProfile.hash, /^sha256:[0-9a-f]{64}$/);

const tamperedCorpus = structuredClone(diverseCorpus);
tamperedCorpus.summary.uniqueSamples = 999;
await assert.rejects(
  createMinimizerCheckpointEvidenceCoverageProfileV1(tamperedCorpus),
  /summary mismatch|hash mismatch/,
);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-evidence-coverage-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointEvidenceCoverageProfile'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointEvidenceCoverageProfileV1'), true);
const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf("replayButton.addEventListener", editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointEvidenceCoverageProfileV1'), false);
assert.equal(editSection.includes('refreshEvidenceCoverageProfile'), false);

console.log('minimizer checkpoint evidence coverage profile tests: PASS');
