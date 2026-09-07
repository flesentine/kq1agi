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
  createMinimizerCheckpointProvenanceCohortCoverageV1,
  MinimizerCheckpointProvenanceCohortCoverageLayout,
  serializeMinimizerCheckpointProvenanceCohortCoverageV1,
} from '../web/certification-minimizer-checkpoint-provenance-cohort-coverage.mjs';

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

function unavailableShadowState(reason) {
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

async function stage({
  stageName,
  sourceHash,
  identity,
  targetTick,
  reason,
}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording({ hash: sourceHash, identity }),
    targetDivergence: { tick: targetTick },
    shadowState: unavailableShadowState(reason),
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

const stageA = await stage({
  stageName: 'phase-1e',
  sourceHash: sha('5'),
  identity: identityA,
  targetTick: 12,
  reason: 'no-recorded-release',
});
const stageB = await stage({
  stageName: 'phase-1f',
  sourceHash: sha('6'),
  identity: identityA,
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});
const stageC = await stage({
  stageName: 'phase-1e',
  sourceHash: sha('7'),
  identity: identityB,
  targetTick: 18,
  reason: 'pause-unavailable',
});

const packageAFull = await packageFor(runA, [stageA, stageB, stageC]);
const packageBRepeatA = await packageFor(runB, [stageA]);

const mixed = await createMinimizerCheckpointProvenanceCohortCoverageV1([
  packageAFull,
  packageBRepeatA,
]);

assert.equal(mixed.schema, MinimizerCheckpointProvenanceCohortCoverageLayout.COVERAGE_SCHEMA);
assert.equal(mixed.policy, 'full-replay-authoritative');
assert.equal(mixed.policyFrozen, false);
assert.equal(mixed.policyDecision, 'EVIDENCE_ONLY');
assert.equal(mixed.accelerationAllowed, false);
assert.equal(mixed.coverageDecision, 'DESCRIPTIVE_ONLY');
assert.equal(mixed.provenanceDecision, 'COLLECTION_IDENTITY_ONLY');
assert.equal(mixed.cohortIdentity, 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH');
assert.equal(mixed.cohortCount, 2);
assert.equal(mixed.uniqueCollectionRuns, 2);
assert.equal(mixed.toolObservedCollectionEvents, 4);
assert.equal(mixed.distinctStageHashes, 3);
assert.equal(mixed.crossRunRepeatedStageHashes, 1);
assert.equal(mixed.crossIdentityCollectionRuns, 1);
assert.deepEqual(mixed.crossIdentityCollectionRunIds, [runA]);
assert.equal(mixed.thresholdPolicy.status, 'UNSET');
assert.equal(mixed.thresholdPolicy.minimumCollectionRunsPerCohort, null);
assert.equal(mixed.thresholdPolicy.minimumCollectionEventsPerCohort, null);
assert.equal(mixed.thresholdPolicy.minimumCrossRunStageRepetitionsPerCohort, null);
assert.equal(mixed.thresholdPolicy.minimumDistinctSourceRecordingsPerCohort, null);
assert.equal(mixed.thresholdPolicy.minimumTargetTickCoveragePerCohort, null);

const byGame = new Map(mixed.cohorts.map(cohort => [cohort.identity.gameHash, cohort]));
const cohortA = byGame.get(identityA.game);
const cohortB = byGame.get(identityB.game);
assert.ok(cohortA);
assert.ok(cohortB);

assert.equal(cohortA.identity.editConfigHash, identityA.edit);
assert.equal(cohortA.collectionRunCount, 2);
assert.deepEqual(cohortA.collectionRunIds, [runA, runB]);
assert.equal(cohortA.toolObservedCollectionEvents, 3);
assert.equal(cohortA.distinctStageHashes, 2);
assert.equal(cohortA.crossRunRepeatedStageHashes, 1);
assert.equal(cohortA.maxCollectionRunsPerStage, 2);
assert.deepEqual(cohortA.phaseEventCounts, { 'phase-1e': 2, 'phase-1f': 1 });
assert.deepEqual(cohortA.phaseDeterministicStageCounts, { 'phase-1e': 1, 'phase-1f': 1 });
assert.deepEqual(cohortA.sourceRecordingHashes, [sha('5'), sha('6')].sort());
assert.deepEqual(cohortA.targetTicks, [12, 20]);
assert.deepEqual(cohortA.capturedCheckpointTicks, []);
assert.deepEqual(cohortA.checkpointHashes, []);
assert.deepEqual(
  cohortA.unavailableCheckpointReasons,
  ['checkpoint-incompatible', 'no-recorded-release'].sort(),
);
assert.deepEqual(cohortA.coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: false,
  singleCollectionRun: false,
  singleDeterministicStage: false,
  noCrossRunStageRepeat: false,
  singleSourceRecording: false,
  singleTargetTick: false,
});

const stageAPopulation = cohortA.stages.find(item => item.stageHash === stageA.hash);
assert.ok(stageAPopulation);
assert.equal(stageAPopulation.stage, 'phase-1e');
assert.equal(stageAPopulation.toolObservedEvents, 2);
assert.equal(stageAPopulation.collectionRunCount, 2);
assert.deepEqual(stageAPopulation.collectionRunIds, [runA, runB]);

const stageBPopulation = cohortA.stages.find(item => item.stageHash === stageB.hash);
assert.ok(stageBPopulation);
assert.equal(stageBPopulation.toolObservedEvents, 1);
assert.equal(stageBPopulation.collectionRunCount, 1);
assert.deepEqual(stageBPopulation.collectionRunIds, [runA]);

assert.equal(cohortB.identity.editConfigHash, identityB.edit);
assert.equal(cohortB.collectionRunCount, 1);
assert.deepEqual(cohortB.collectionRunIds, [runA]);
assert.equal(cohortB.toolObservedCollectionEvents, 1);
assert.equal(cohortB.distinctStageHashes, 1);
assert.equal(cohortB.crossRunRepeatedStageHashes, 0);
assert.deepEqual(cohortB.phaseEventCounts, { 'phase-1e': 1, 'phase-1f': 0 });
assert.deepEqual(cohortB.phaseDeterministicStageCounts, { 'phase-1e': 1, 'phase-1f': 0 });
assert.deepEqual(cohortB.sourceRecordingHashes, [sha('7')]);
assert.deepEqual(cohortB.targetTicks, [18]);
assert.deepEqual(cohortB.coverageFlags, {
  missingPhase1E: false,
  missingPhase1F: true,
  singleCollectionRun: true,
  singleDeterministicStage: true,
  noCrossRunStageRepeat: true,
  singleSourceRecording: true,
  singleTargetTick: true,
});

const duplicate = await createMinimizerCheckpointProvenanceCohortCoverageV1([
  packageAFull,
  packageBRepeatA,
  packageBRepeatA,
]);
assert.equal(duplicate.hash, mixed.hash, 'Exact duplicate provenance package import must be coverage-idempotent.');

const reverse = await createMinimizerCheckpointProvenanceCohortCoverageV1([
  packageBRepeatA,
  packageAFull,
]);
assert.equal(reverse.hash, mixed.hash, 'Package order must not change provenance cohort coverage.');

const packageA1 = await packageFor(runA, [stageA]);
const prefix = await createMinimizerCheckpointProvenanceCohortCoverageV1([
  packageA1,
  packageAFull,
  packageBRepeatA,
]);
assert.equal(prefix.toolObservedCollectionEvents, mixed.toolObservedCollectionEvents);
assert.equal(prefix.distinctStageHashes, mixed.distinctStageHashes);
assert.equal(prefix.cohortCount, mixed.cohortCount);
assert.notEqual(prefix.provenanceCensusHash, mixed.provenanceCensusHash, 'Census preserves superseded snapshot history.');
assert.notEqual(prefix.hash, mixed.hash, 'Coverage is bound to its exact canonical census.');

const conflictingA = await packageFor(runA, [stageC]);
await assert.rejects(
  createMinimizerCheckpointProvenanceCohortCoverageV1([
    packageA1,
    conflictingA,
  ]),
  /Conflicting provenance snapshots share collection run/,
);

const serialized = serializeMinimizerCheckpointProvenanceCohortCoverageV1(mixed);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"coverageDecision": "DESCRIPTIVE_ONLY"'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload":'), false);
assert.match(mixed.hash, /^sha256:[0-9a-f]{64}$/);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-provenance-coverage-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointProvenanceCohortCoverage'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointProvenanceCohortCoverageV1'), true);

const provenanceImportStart = phase1dSource.indexOf('async function importProvenanceFiles()');
const provenanceImportEnd = phase1dSource.indexOf('async function importEvidenceFiles()', provenanceImportStart);
const provenanceImportSection = phase1dSource.slice(provenanceImportStart, provenanceImportEnd);
assert.equal(provenanceImportSection.includes('importedEvidenceArtifacts'), false);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointEvidenceCorpusV1'), false);

const evidenceImportStart = phase1dSource.indexOf('async function importEvidenceFiles()');
const evidenceImportEnd = phase1dSource.indexOf('function refreshJournal()', evidenceImportStart);
const evidenceImportSection = phase1dSource.slice(evidenceImportStart, evidenceImportEnd);
assert.equal(evidenceImportSection.includes('createMinimizerCheckpointProvenanceCohortCoverageV1'), false);

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointProvenanceCohortCoverageV1'), false);
assert.equal(editSection.includes('refreshProvenanceCohortCoverage'), false);

console.log('minimizer checkpoint provenance cohort coverage tests: PASS');
