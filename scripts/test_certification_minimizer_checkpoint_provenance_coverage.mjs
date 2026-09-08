import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointCollectionEventV1,
  createMinimizerCheckpointCollectionProvenanceV1,
} from '../web/certification-minimizer-checkpoint-provenance.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
} from '../web/certification-minimizer-checkpoint-provenance-census.mjs';
import {
  createMinimizerCheckpointProvenanceCoverageMatrixV1,
  MinimizerCheckpointProvenanceCoverageLayout,
  serializeMinimizerCheckpointProvenanceCoverageMatrixV1,
} from '../web/certification-minimizer-checkpoint-provenance-coverage.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const runA = `kq1agi-collection-run-v1:${'a'.repeat(32)}`;
const runB = `kq1agi-collection-run-v1:${'b'.repeat(32)}`;
const identityA = Object.freeze({ game: sha('1'), edit: sha('2') });
const identityB = Object.freeze({ game: sha('3'), edit: sha('4') });

function sourceRecording({ hash, identity }) {
  return Object.freeze({
    hash,
    gameHash: identity.game,
    gameBytes: 17295,
    editConfigHash: identity.edit,
    finalTick: 24,
    events: [],
    random: [],
    releaseTicks: [],
  });
}

function unavailableShadowState(reason, targetTick) {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
    reason,
    selection: Object.freeze({
      status: 'MINIMIZER_SHADOW_NO_BOUNDARY',
      reason,
      targetTick,
    }),
  });
}

function capturedShadowState(checkpointHash, checkpointTick) {
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

async function stage({
  stageName,
  identity,
  sourceHash,
  targetTick,
  checkpointHash = null,
  checkpointTick = null,
  unavailableReason = null,
}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording({ hash: sourceHash, identity }),
    targetDivergence: { tick: targetTick },
    shadowState: unavailableReason
      ? unavailableShadowState(unavailableReason, targetTick)
      : capturedShadowState(checkpointHash, checkpointTick),
    observations: [],
    collectionErrorCandidateHashes: [],
    outcome: { status: 'MINIMIZED', attempts: 0 },
  });
}

async function packageFor(runId, stages) {
  const evidenceReport = await createMinimizerCheckpointEvidenceReportV1(stages);
  const events = [];
  for (let ordinal = 0; ordinal < stages.length; ordinal += 1) {
    events.push(await createMinimizerCheckpointCollectionEventV1({
      collectionRunId: runId,
      ordinal,
      stageHash: stages[ordinal].hash,
    }));
  }
  const provenance = await createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: runId,
    evidenceReport,
    events,
  });
  return Object.freeze({ evidenceReport, provenance });
}

const stageA1 = await stage({
  stageName: 'phase-1e',
  identity: identityA,
  sourceHash: sha('5'),
  targetTick: 12,
  checkpointHash: sha('6'),
  checkpointTick: 5,
});
const stageA2 = await stage({
  stageName: 'phase-1f',
  identity: identityA,
  sourceHash: sha('7'),
  targetTick: 20,
  unavailableReason: 'checkpoint-incompatible',
});
const stageB1 = await stage({
  stageName: 'phase-1e',
  identity: identityB,
  sourceHash: sha('8'),
  targetTick: 14,
  checkpointHash: sha('9'),
  checkpointTick: 6,
});

const packageA1 = await packageFor(runA, [stageA1]);
const packageA2 = await packageFor(runA, [stageA1, stageA2]);
const packageBRepeatA1 = await packageFor(runB, [stageA1]);

const matrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA2,
  packageBRepeatA1,
]);
assert.equal(matrix.schema, MinimizerCheckpointProvenanceCoverageLayout.MATRIX_SCHEMA);
assert.equal(matrix.policy, 'full-replay-authoritative');
assert.equal(matrix.policyFrozen, false);
assert.equal(matrix.policyDecision, 'EVIDENCE_ONLY');
assert.equal(matrix.accelerationAllowed, false);
assert.equal(matrix.matrixDecision, 'DESCRIPTIVE_ONLY');
assert.equal(matrix.provenanceDecision, 'COLLECTION_IDENTITY_ONLY');
assert.equal(matrix.cohortIdentity, 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH');
assert.equal(matrix.cohortCount, 1);
assert.equal(matrix.uniqueCollectionRuns, 2);
assert.equal(matrix.toolObservedCollectionEvents, 3);
assert.equal(matrix.distinctStageHashes, 2);
assert.equal(matrix.crossRunRepeatedStageHashes, 1);
assert.equal(matrix.thresholdPolicy.status, 'UNSET');
assert.equal(matrix.thresholdPolicy.minimumCollectionRunsPerCohort, null);
assert.equal(matrix.thresholdPolicy.minimumPhase1EEvents, null);
assert.equal(matrix.thresholdPolicy.minimumPhase1FEvents, null);
assert.equal(matrix.thresholdPolicy.minimumDistinctSourceRecordings, null);
assert.equal(matrix.thresholdPolicy.minimumTargetTickCoverage, null);
assert.equal(matrix.thresholdPolicy.minimumCrossRunStageRepetitions, null);

const census = await createMinimizerCheckpointProvenanceCensusV1([
  packageA2,
  packageBRepeatA1,
]);
assert.equal(matrix.provenanceCensusHash, census.hash);

const cohortA = matrix.cohorts[0];
assert.equal(cohortA.identity.gameHash, identityA.game);
assert.equal(cohortA.identity.editConfigHash, identityA.edit);
assert.deepEqual(cohortA.collectionRunIds, [runA, runB]);
assert.equal(cohortA.toolObservedCollectionEvents, 3);
assert.equal(cohortA.distinctEventHashes, 3);
assert.equal(cohortA.distinctStageHashes, 2);
assert.deepEqual(cohortA.eventStageCounts, { 'phase-1e': 2, 'phase-1f': 1 });
assert.deepEqual(cohortA.deterministicStageCounts, { 'phase-1e': 1, 'phase-1f': 1 });
assert.deepEqual(cohortA.sourceRecordingHashes, [sha('5'), sha('7')].sort());
assert.deepEqual(cohortA.targetTicks, [12, 20]);
assert.deepEqual(cohortA.capturedCheckpointTicks, [5]);
assert.deepEqual(cohortA.checkpointHashes, [sha('6')]);
assert.deepEqual(cohortA.unavailableCheckpointReasons, ['checkpoint-incompatible']);
assert.deepEqual(cohortA.crossRunRepeatedStageHashes, [stageA1.hash]);
assert.deepEqual(cohortA.coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: false,
  singleCollectionRun: false,
  singleSourceRecording: false,
  singleTargetTick: false,
  noCapturedCheckpoint: false,
  singleCapturedCheckpointTick: true,
  noCrossRunRepeatedStage: false,
});

const stageA1Summary = cohortA.stages.find(item => item.stageHash === stageA1.hash);
const stageA2Summary = cohortA.stages.find(item => item.stageHash === stageA2.hash);
assert.ok(stageA1Summary);
assert.ok(stageA2Summary);
assert.equal(stageA1Summary.eventCount, 2);
assert.equal(stageA1Summary.collectionRunCount, 2);
assert.deepEqual(stageA1Summary.collectionRunIds, [runA, runB]);
assert.equal(stageA1Summary.stage, 'phase-1e');
assert.equal(stageA1Summary.targetTick, 12);
assert.equal(stageA1Summary.checkpointTick, 5);
assert.equal(stageA1Summary.checkpointHash, sha('6'));
assert.equal(stageA2Summary.eventCount, 1);
assert.equal(stageA2Summary.collectionRunCount, 1);
assert.deepEqual(stageA2Summary.collectionRunIds, [runA]);
assert.equal(stageA2Summary.stage, 'phase-1f');
assert.equal(stageA2Summary.checkpointHash, null);
assert.equal(stageA2Summary.checkpointReason, 'checkpoint-incompatible');

const prefixMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA1,
  packageA2,
]);
assert.equal(prefixMatrix.uniqueCollectionRuns, 1);
assert.equal(prefixMatrix.toolObservedCollectionEvents, 2);
assert.equal(prefixMatrix.distinctStageHashes, 2);
assert.deepEqual(prefixMatrix.cohorts[0].eventStageCounts, {
  'phase-1e': 1,
  'phase-1f': 1,
});
assert.equal(prefixMatrix.cohorts[0].collectionRunIds.length, 1);

const duplicateMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA2,
  packageA2,
]);
const singleMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA2,
]);
assert.equal(
  duplicateMatrix.hash,
  singleMatrix.hash,
  'Exact duplicate provenance package must not alter the coverage matrix hash.',
);

const mixedIdentityMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA2,
  await packageFor(runB, [stageB1]),
]);
assert.equal(mixedIdentityMatrix.cohortCount, 2);
const identities = mixedIdentityMatrix.cohorts.map(item => item.identity.gameHash).sort();
assert.deepEqual(identities, [identityA.game, identityB.game].sort());

const concentratedMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageA1,
]);
assert.equal(concentratedMatrix.cohortCount, 1);
assert.deepEqual(concentratedMatrix.cohorts[0].coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: true,
  singleCollectionRun: true,
  singleSourceRecording: true,
  singleTargetTick: true,
  noCapturedCheckpoint: false,
  singleCapturedCheckpointTick: true,
  noCrossRunRepeatedStage: true,
});
assert.equal(concentratedMatrix.flagCounts.missingPhase1F, 1);
assert.equal(concentratedMatrix.flagCounts.singleCollectionRun, 1);

const sameSetReverse = await createMinimizerCheckpointProvenanceCoverageMatrixV1([
  packageBRepeatA1,
  packageA2,
]);
assert.equal(
  sameSetReverse.hash,
  matrix.hash,
  'Provenance coverage matrix must be deterministic independent of package order.',
);

const serialized = serializeMinimizerCheckpointProvenanceCoverageMatrixV1(matrix);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"matrixDecision": "DESCRIPTIVE_ONLY"'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload":'), false);
assert.match(matrix.hash, /^sha256:[0-9a-f]{64}$/);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-provenance-coverage-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointProvenanceCoverageMatrix'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointProvenanceCoverageMatrixV1'), true);
assert.equal(phase1dSource.includes('Phase -1I.10/−1I.11'), false);

const provenanceImportStart = phase1dSource.indexOf('async function importProvenanceFiles()');
const provenanceImportEnd = phase1dSource.indexOf('async function importEvidenceFiles()', provenanceImportStart);
const provenanceImportSection = phase1dSource.slice(provenanceImportStart, provenanceImportEnd);
const matrixIndex = provenanceImportSection.indexOf('await createMinimizerCheckpointProvenanceCoverageMatrixV1(candidatePackages)');
const commitIndex = provenanceImportSection.indexOf('importedProvenancePackages.push(...committedBatch)');
assert.ok(matrixIndex >= 0 && commitIndex > matrixIndex, 'Provenance coverage matrix must validate before provenance batch commit.');
assert.equal(provenanceImportSection.includes('importedEvidenceArtifacts'), false);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointEvidenceCorpusV1'), false);

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointProvenanceCoverageMatrixV1'), false);
assert.equal(editSection.includes('refreshProvenanceCoverageMatrix'), false);

console.log('minimizer checkpoint provenance coverage matrix tests: PASS');
