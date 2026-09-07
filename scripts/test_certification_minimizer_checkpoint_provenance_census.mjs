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
  MinimizerCheckpointProvenanceCensusLayout,
  serializeMinimizerCheckpointProvenanceCensusV1,
} from '../web/certification-minimizer-checkpoint-provenance-census.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const runA = `kq1agi-collection-run-v1:${'a'.repeat(32)}`;
const runB = `kq1agi-collection-run-v1:${'b'.repeat(32)}`;

function sourceRecording(hash) {
  return Object.freeze({
    hash,
    gameHash: sha('1'),
    gameBytes: 17295,
    editConfigHash: sha('2'),
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
  targetTick,
  reason,
}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording(sourceHash),
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
  sourceHash: sha('3'),
  targetTick: 12,
  reason: 'no-recorded-release',
});
const stageB = await stage({
  stageName: 'phase-1f',
  sourceHash: sha('4'),
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});
const stageC = await stage({
  stageName: 'phase-1e',
  sourceHash: sha('5'),
  targetTick: 18,
  reason: 'pause-unavailable',
});

const packageA1 = await packageFor(runA, [stageA]);
const packageA2 = await packageFor(runA, [stageA, stageB]);

const single = await createMinimizerCheckpointProvenanceCensusV1([packageA1]);
assert.equal(single.schema, MinimizerCheckpointProvenanceCensusLayout.CENSUS_SCHEMA);
assert.equal(single.policy, 'full-replay-authoritative');
assert.equal(single.policyFrozen, false);
assert.equal(single.policyDecision, 'EVIDENCE_ONLY');
assert.equal(single.accelerationAllowed, false);
assert.equal(single.censusDecision, 'DESCRIPTIVE_ONLY');
assert.equal(single.provenanceDecision, 'COLLECTION_IDENTITY_ONLY');
assert.equal(single.uniqueProvenanceSnapshots, 1);
assert.equal(single.supersededSnapshots, 0);
assert.equal(single.uniqueCollectionRuns, 1);
assert.equal(single.toolObservedCollectionEvents, 1);
assert.equal(single.distinctEventHashes, 1);
assert.equal(single.distinctStageHashes, 1);
assert.equal(single.crossRunRepeatedStageHashes, 0);
assert.equal(single.maxCollectionRunsPerStage, 1);
assert.equal(single.runs[0].collectionRunId, runA);
assert.equal(single.runs[0].eventCount, 1);
assert.equal(single.runs[0].snapshotCount, 1);
assert.deepEqual(single.runs[0].distinctStageHashes, [stageA.hash]);
assert.equal(single.stagePopulations[0].stageHash, stageA.hash);
assert.equal(single.stagePopulations[0].eventCount, 1);
assert.equal(single.stagePopulations[0].collectionRunCount, 1);
assert.deepEqual(single.stagePopulations[0].collectionRunIds, [runA]);
assert.equal(single.thresholdPolicy.status, 'UNSET');
assert.equal(single.thresholdPolicy.minimumCollectionRuns, null);
assert.equal(single.thresholdPolicy.minimumCollectionEvents, null);
assert.equal(single.thresholdPolicy.minimumCrossRunStageRepetitions, null);

const duplicate = await createMinimizerCheckpointProvenanceCensusV1([
  packageA1,
  packageA1,
]);
assert.equal(duplicate.uniqueProvenanceSnapshots, 1);
assert.equal(duplicate.uniqueCollectionRuns, 1);
assert.equal(duplicate.toolObservedCollectionEvents, 1);
assert.equal(duplicate.hash, single.hash, 'Exact duplicate package re-import must be census-idempotent.');

const prefix = await createMinimizerCheckpointProvenanceCensusV1([
  packageA1,
  packageA2,
]);
assert.equal(prefix.uniqueProvenanceSnapshots, 2);
assert.equal(prefix.supersededSnapshots, 1);
assert.equal(prefix.uniqueCollectionRuns, 1);
assert.equal(prefix.toolObservedCollectionEvents, 2);
assert.equal(prefix.distinctEventHashes, 2);
assert.equal(prefix.distinctStageHashes, 2);
assert.equal(prefix.runs[0].eventCount, 2);
assert.equal(prefix.runs[0].snapshotCount, 2);
assert.equal(prefix.runs[0].selectedProvenanceHash, packageA2.provenance.hash);

const prefixReverse = await createMinimizerCheckpointProvenanceCensusV1([
  packageA2,
  packageA1,
]);
assert.equal(prefixReverse.hash, prefix.hash, 'Input order must not affect the census hash.');

const packageB1SameStage = await packageFor(runB, [stageA]);
const crossRunRepeat = await createMinimizerCheckpointProvenanceCensusV1([
  packageA1,
  packageB1SameStage,
]);
assert.equal(crossRunRepeat.uniqueCollectionRuns, 2);
assert.equal(crossRunRepeat.toolObservedCollectionEvents, 2);
assert.equal(crossRunRepeat.distinctEventHashes, 2);
assert.equal(crossRunRepeat.distinctStageHashes, 1);
assert.equal(crossRunRepeat.crossRunRepeatedStageHashes, 1);
assert.equal(crossRunRepeat.maxCollectionRunsPerStage, 2);
assert.equal(crossRunRepeat.stagePopulations.length, 1);
assert.equal(crossRunRepeat.stagePopulations[0].eventCount, 2);
assert.equal(crossRunRepeat.stagePopulations[0].collectionRunCount, 2);
assert.deepEqual(
  crossRunRepeat.stagePopulations[0].collectionRunIds,
  [runA, runB],
);
assert.notEqual(
  packageA1.provenance.events[0].eventHash,
  packageB1SameStage.provenance.events[0].eventHash,
);

const conflictingSameCount = await packageFor(runA, [stageC]);
await assert.rejects(
  createMinimizerCheckpointProvenanceCensusV1([
    packageA1,
    conflictingSameCount,
  ]),
  /Conflicting provenance snapshots share collection run/,
);

const conflictingLonger = await packageFor(runA, [stageC, stageB]);
await assert.rejects(
  createMinimizerCheckpointProvenanceCensusV1([
    packageA1,
    conflictingLonger,
  ]),
  /Conflicting provenance history/,
);

const wrongReportPackage = {
  evidenceReport: packageA2.evidenceReport,
  provenance: packageA1.provenance,
};
await assert.rejects(
  createMinimizerCheckpointProvenanceCensusV1([wrongReportPackage]),
  /evidence report hash mismatch/,
);

const tamperedProvenance = structuredClone(packageA1.provenance);
tamperedProvenance.eventCount = 999;
await assert.rejects(
  createMinimizerCheckpointProvenanceCensusV1([{
    evidenceReport: packageA1.evidenceReport,
    provenance: tamperedProvenance,
  }]),
  /event count mismatch|hash mismatch/,
);

const sameSetAgain = await createMinimizerCheckpointProvenanceCensusV1([
  packageB1SameStage,
  packageA1,
]);
assert.equal(
  sameSetAgain.hash,
  crossRunRepeat.hash,
  'Cross-run census must be deterministic independent of input order.',
);

const serialized = serializeMinimizerCheckpointProvenanceCensusV1(crossRunRepeat);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"censusDecision": "DESCRIPTIVE_ONLY"'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload":'), false);
assert.match(crossRunRepeat.hash, /^sha256:[0-9a-f]{64}$/);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-import-provenance-button'), true);
assert.equal(phase1dSource.includes('certify-export-provenance-census-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointProvenanceCensus'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointProvenanceCensusV1'), true);

const evidenceImportStart = phase1dSource.indexOf('async function importEvidenceFiles()');
const evidenceImportEnd = phase1dSource.indexOf('function refreshJournal()', evidenceImportStart);
const evidenceImportSection = phase1dSource.slice(evidenceImportStart, evidenceImportEnd);
assert.equal(evidenceImportSection.includes('importedProvenancePackages.push'), false);

const provenanceImportStart = phase1dSource.indexOf('async function importProvenanceFiles()');
const provenanceImportEnd = phase1dSource.indexOf('async function importEvidenceFiles()', provenanceImportStart);
assert.ok(provenanceImportStart >= 0 && provenanceImportEnd > provenanceImportStart);
const provenanceImportSection = phase1dSource.slice(provenanceImportStart, provenanceImportEnd);
assert.equal(provenanceImportSection.includes('importedEvidenceArtifacts'), false);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointEvidenceCorpusV1'), false);
assert.equal(provenanceImportSection.includes('knownProvenanceHashes'), true);
assert.equal(provenanceImportSection.includes('committedBatch.push(item)'), true);
const candidateIndex = provenanceImportSection.indexOf('const candidatePackages = [');
const censusIndex = provenanceImportSection.indexOf('await createMinimizerCheckpointProvenanceCensusV1(candidatePackages)');
const commitIndex = provenanceImportSection.indexOf('importedProvenancePackages.push(...committedBatch)');
assert.ok(candidateIndex >= 0 && censusIndex > candidateIndex && commitIndex > censusIndex, 'Provenance import must validate the candidate census before committing the deduplicated batch.');

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointProvenanceCensusV1'), false);
assert.equal(editSection.includes('refreshProvenanceCensus'), false);

console.log('minimizer checkpoint provenance census tests: PASS');
