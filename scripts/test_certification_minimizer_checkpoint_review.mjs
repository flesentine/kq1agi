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
  MinimizerCheckpointReviewLayout,
  serializeMinimizerCheckpointEvidenceReviewV1,
} from '../web/certification-minimizer-checkpoint-review.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const base = Object.freeze({
  source: sha('1'),
  game: sha('2'),
  edit: sha('3'),
  checkpoint: sha('4'),
  decision: sha('5'),
  evidence: sha('6'),
});

async function observation({
  candidate,
  status = 'CHECKPOINT_ORACLE_EQUIVALENT',
  sourceHash = base.source,
  checkpointHash = base.checkpoint,
  evidenceHash = base.evidence,
  checkpointEvidenceHash = evidenceHash,
  savedTicks = 5,
} = {}) {
  const attempted = status !== 'CHECKPOINT_ORACLE_FULL_ONLY';
  const equivalent = status === 'CHECKPOINT_ORACLE_EQUIVALENT';
  const mismatch = status === 'CHECKPOINT_ORACLE_MISMATCH';
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
    fullDecisionHash: base.decision,
    checkpointDecisionHash: attempted ? base.decision : null,
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

function sourceRecording({
  hash = base.source,
  gameHash = base.game,
  editConfigHash = base.edit,
} = {}) {
  return Object.freeze({
    hash,
    gameHash,
    gameBytes: 17295,
    editConfigHash,
    finalTick: 12,
    events: [{ tick: 2 }],
    random: [{ tick: 2 }],
    releaseTicks: [1, 3, 6, 8, 12],
  });
}

function capturedShadowState(checkpointHash = base.checkpoint) {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
    selection: Object.freeze({
      desiredCheckpointTick: 6,
      pauseBeforeTick: 6,
      checkpointTick: 5,
    }),
    checkpoint: Object.freeze({
      hash: checkpointHash,
      logicalTick: 5,
    }),
  });
}

async function stage(obs, {
  stageName = 'phase-1e',
  source = sourceRecording(),
  failures = [],
} = {}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: source,
    targetDivergence: { tick: 12 },
    shadowState: capturedShadowState(),
    observations: [obs],
    collectionErrorCandidateHashes: failures,
    outcome: { status: 'MINIMIZED', attempts: 1 },
  });
}

async function corpusFromStages(stages) {
  const report = await createMinimizerCheckpointEvidenceReportV1(stages);
  return createMinimizerCheckpointEvidenceCorpusV1([report]);
}

const cleanA = await observation({ candidate: sha('a'), savedTicks: 5 });
const cleanB = await observation({ candidate: sha('b'), savedTicks: 9 });
const cleanCorpus = await corpusFromStages([
  await stage(cleanA),
  await stage(cleanB, { stageName: 'phase-1f' }),
]);
const cleanReview = await createMinimizerCheckpointEvidenceReviewV1(cleanCorpus);

assert.equal(cleanReview.schema, MinimizerCheckpointReviewLayout.REVIEW_SCHEMA);
assert.equal(cleanReview.policy, 'full-replay-authoritative');
assert.equal(cleanReview.policyFrozen, false);
assert.equal(cleanReview.policyDecision, 'EVIDENCE_ONLY');
assert.equal(cleanReview.accelerationAllowed, false);
assert.equal(cleanReview.corpusHash, cleanCorpus.hash);
assert.equal(cleanReview.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');
assert.deepEqual(cleanReview.blockers, []);
assert.equal(cleanReview.evidence.uniqueCheckpointAttemptedSamples, 2);
assert.equal(cleanReview.evidence.cleanEquivalentSamples, 2);
assert.equal(cleanReview.evidence.mismatchSamples, 0);
assert.equal(cleanReview.thresholdPolicy.status, 'UNSET');
assert.equal(cleanReview.thresholdPolicy.minimumUniqueCheckpointAttemptedSamples, null);
assert.equal(cleanReview.thresholdPolicy.minimumDistinctSourceRecordings, null);
assert.equal(cleanReview.thresholdPolicy.minimumSavedTickBenefit, null);
assert.deepEqual(cleanReview.identities.gameHashes, [base.game]);
assert.deepEqual(cleanReview.identities.editConfigHashes, [base.edit]);
assert.deepEqual(cleanReview.identities.sourceRecordingHashes, [base.source]);
assert.equal(cleanReview.savedTicks.count, 2);
assert.equal(cleanReview.savedTicks.min, 5);
assert.equal(cleanReview.savedTicks.max, 9);
assert.match(cleanReview.hash, /^sha256:[0-9a-f]{64}$/);

const cleanReviewAgain = await createMinimizerCheckpointEvidenceReviewV1(cleanCorpus);
assert.equal(cleanReviewAgain.hash, cleanReview.hash, 'Review record must be deterministic.');

const mismatch = await observation({
  candidate: sha('c'),
  status: 'CHECKPOINT_ORACLE_MISMATCH',
  checkpointEvidenceHash: sha('7'),
});
const mismatchReview = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([await stage(mismatch)]),
);
assert.equal(mismatchReview.reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.deepEqual(mismatchReview.blockers, ['CHECKPOINT_MISMATCH']);
assert.equal(mismatchReview.accelerationAllowed, false);

const inconsistentEquivalent = await observation({ candidate: sha('d'), savedTicks: 5 });
const inconsistentMismatch = await observation({
  candidate: sha('d'),
  status: 'CHECKPOINT_ORACLE_MISMATCH',
  checkpointEvidenceHash: sha('8'),
});
const inconsistentReview = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([
    await stage(inconsistentEquivalent),
    await stage(inconsistentMismatch),
  ]),
);
assert.equal(inconsistentReview.reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.equal(inconsistentReview.blockers.includes('CHECKPOINT_MISMATCH'), true);
assert.equal(inconsistentReview.blockers.includes('INCONSISTENT_REPEAT'), true);

const gapObs = await observation({
  candidate: sha('e'),
  status: 'CHECKPOINT_ORACLE_FULL_ONLY',
});
const gapReview = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([
    await stage(gapObs, { failures: [sha('f')] }),
  ]),
);
assert.equal(gapReview.reviewStatus, 'NO_COMPATIBLE_SAMPLES');
assert.deepEqual(gapReview.blockers, ['NO_CHECKPOINT_ATTEMPTS', 'COLLECTION_GAP']);

const mixedSource = sourceRecording({
  hash: sha('9'),
  gameHash: sha('0'),
  editConfigHash: sha('a'),
});
const mixedObs = await observation({
  candidate: sha('9'),
  sourceHash: mixedSource.hash,
});
const mixedReview = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([
    await stage(cleanA),
    await stage(mixedObs, { source: mixedSource, stageName: 'phase-1f' }),
  ]),
);
assert.equal(mixedReview.reviewStatus, 'BLOCKED_BY_EVIDENCE');
assert.deepEqual(
  mixedReview.blockers,
  ['MIXED_GAME_IDENTITY', 'MIXED_EDIT_CONFIG_IDENTITY'],
);
assert.equal(mixedReview.identities.gameHashes.length, 2);
assert.equal(mixedReview.identities.editConfigHashes.length, 2);
assert.equal(mixedReview.identities.sourceRecordingHashes.length, 2);

const fullOnly = await observation({
  candidate: sha('f'),
  status: 'CHECKPOINT_ORACLE_FULL_ONLY',
});
const emptyReview = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([await stage(fullOnly)]),
);
assert.equal(emptyReview.reviewStatus, 'NO_COMPATIBLE_SAMPLES');
assert.deepEqual(emptyReview.blockers, ['NO_CHECKPOINT_ATTEMPTS']);
assert.equal(emptyReview.evidence.fullOnlySamples, 1);
assert.equal(emptyReview.accelerationAllowed, false);

const cleanWithFullOnly = await createMinimizerCheckpointEvidenceReviewV1(
  await corpusFromStages([
    await stage(cleanA),
    await stage(fullOnly, { stageName: 'phase-1f' }),
  ]),
);
assert.equal(cleanWithFullOnly.reviewStatus, 'CLEAN_EVIDENCE_THRESHOLD_UNSET');
assert.deepEqual(cleanWithFullOnly.blockers, []);
assert.equal(cleanWithFullOnly.evidence.fullOnlySamples, 1);
assert.equal(cleanWithFullOnly.evidence.cleanEquivalentSamples, 1);

const serialized = serializeMinimizerCheckpointEvidenceReviewV1(cleanReview);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload": ['), false);

const tamperedCorpus = structuredClone(cleanCorpus);
tamperedCorpus.summary.cleanEquivalentSamples = 999;
await assert.rejects(
  createMinimizerCheckpointEvidenceReviewV1(tamperedCorpus),
  /summary mismatch|hash mismatch/,
);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-evidence-review-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointEvidenceReview'), true);
assert.equal(phase1dSource.includes('accelerationAllowed=false'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointEvidenceReviewV1'), true);
const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf("replayButton.addEventListener", editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointEvidenceReviewV1'), false);
assert.equal(editSection.includes('refreshEvidenceReview'), false);

console.log('minimizer checkpoint evidence review tests: PASS');
