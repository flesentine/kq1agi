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
} from '../web/certification-minimizer-checkpoint-provenance-coverage.mjs';
import {
  createMinimizerCheckpointProvenanceSessionTopologyV1,
} from '../web/certification-minimizer-checkpoint-provenance-session-topology.mjs';
import {
  createMinimizerCheckpointCollectionPackageV1,
  extractMinimizerCheckpointCollectionPackageV1,
  MinimizerCheckpointCollectionPackageLayout,
  serializeMinimizerCheckpointCollectionPackageV1,
  validateMinimizerCheckpointCollectionPackageV1,
} from '../web/certification-minimizer-checkpoint-collection-package.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const runId = `kq1agi-collection-run-v1:${'a'.repeat(32)}`;

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

async function stage({ stageName, sourceHash, identity, targetTick, reason }) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording({ hash: sourceHash, identity }),
    targetDivergence: { tick: targetTick },
    shadowState: unavailableShadowState(reason, targetTick),
    observations: [],
    collectionErrorCandidateHashes: [],
    outcome: { status: 'MINIMIZED', attempts: 0 },
  });
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
  identity: identityB,
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});

const evidenceReport = await createMinimizerCheckpointEvidenceReportV1([stageA, stageB]);
const events = [
  await createMinimizerCheckpointCollectionEventV1({
    collectionRunId: runId,
    ordinal: 0,
    stageHash: stageA.hash,
  }),
  await createMinimizerCheckpointCollectionEventV1({
    collectionRunId: runId,
    ordinal: 1,
    stageHash: stageB.hash,
  }),
];
const provenance = await createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId: runId,
  evidenceReport,
  events,
});

const collectionPackage = await createMinimizerCheckpointCollectionPackageV1({
  evidenceReport,
  provenance,
});

assert.equal(collectionPackage.schema, MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA);
assert.equal(collectionPackage.policy, 'full-replay-authoritative');
assert.equal(collectionPackage.policyFrozen, false);
assert.equal(collectionPackage.policyDecision, 'EVIDENCE_ONLY');
assert.equal(collectionPackage.accelerationAllowed, false);
assert.equal(collectionPackage.packageDecision, 'COLLECTION_ARCHIVE_ONLY');
assert.equal(collectionPackage.collectionRunId, runId);
assert.equal(collectionPackage.evidenceReportHash, evidenceReport.hash);
assert.equal(collectionPackage.provenanceHash, provenance.hash);
assert.equal(collectionPackage.eventCount, 2);
assert.deepEqual(collectionPackage.distinctStageHashes, provenance.distinctStageHashes);
assert.equal(collectionPackage.evidenceReport, evidenceReport);
assert.equal(collectionPackage.provenance, provenance);
assert.match(collectionPackage.hash, /^sha256:[0-9a-f]{64}$/);

const pair = [{ evidenceReport, provenance }];
const [census, matrix, topology] = await Promise.all([
  createMinimizerCheckpointProvenanceCensusV1(pair),
  createMinimizerCheckpointProvenanceCoverageMatrixV1(pair),
  createMinimizerCheckpointProvenanceSessionTopologyV1(pair),
]);
assert.equal(collectionPackage.derived.provenanceCensusHash, census.hash);
assert.equal(collectionPackage.derived.provenanceCoverageMatrixHash, matrix.hash);
assert.equal(collectionPackage.derived.provenanceSessionTopologyHash, topology.hash);
assert.equal(collectionPackage.derived.cohortCount, matrix.cohortCount);
assert.equal(collectionPackage.derived.multiIdentity, true);
assert.equal(collectionPackage.derived.identityCount, 2);
assert.deepEqual(
  collectionPackage.derived.identityCohortKeys,
  topology.runs[0].identityCohortKeys,
);

const validated = await validateMinimizerCheckpointCollectionPackageV1(collectionPackage);
assert.deepEqual(validated, {
  valid: true,
  hash: collectionPackage.hash,
  collectionRunId: runId,
  evidenceReportHash: evidenceReport.hash,
  provenanceHash: provenance.hash,
  eventCount: 2,
});

const extracted = await extractMinimizerCheckpointCollectionPackageV1(collectionPackage);
assert.equal(extracted.evidenceReport.hash, evidenceReport.hash);
assert.equal(extracted.provenance.hash, provenance.hash);
assert.equal(extracted.provenance.collectionRunId, runId);
assert.equal(extracted.provenance.events[0].eventHash, events[0].eventHash);
assert.equal(extracted.provenance.events[1].eventHash, events[1].eventHash);

const again = await createMinimizerCheckpointCollectionPackageV1({
  evidenceReport,
  provenance,
});
assert.equal(again.hash, collectionPackage.hash, 'Re-export of one live snapshot must be deterministic.');

const serialized = serializeMinimizerCheckpointCollectionPackageV1(collectionPackage);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"packageDecision": "COLLECTION_ARCHIVE_ONLY"'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"workerPayload":'), false);

const tamperedDerived = structuredClone(collectionPackage);
tamperedDerived.derived.provenanceCensusHash = sha('f');
await assert.rejects(
  validateMinimizerCheckpointCollectionPackageV1(tamperedDerived),
  /validation mismatch/,
);

const tamperedProvenance = structuredClone(collectionPackage);
tamperedProvenance.provenance.eventCount = 999;
await assert.rejects(
  validateMinimizerCheckpointCollectionPackageV1(tamperedProvenance),
  /event count mismatch|hash mismatch|validation mismatch/,
);

const tamperedReport = structuredClone(collectionPackage);
tamperedReport.evidenceReport.population.totalObservations = 999;
await assert.rejects(
  validateMinimizerCheckpointCollectionPackageV1(tamperedReport),
  /summary mismatch|hash mismatch|validation mismatch/,
);

const forbidden = structuredClone(collectionPackage);
forbidden.workerPayload = [1, 2, 3];
await assert.rejects(
  validateMinimizerCheckpointCollectionPackageV1(forbidden),
  /forbidden raw oracle field/,
);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-collection-package-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointCollectionPackage'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointCollectionPackageV1'), true);
assert.equal(phase1dSource.includes('MinimizerCheckpointCollectionPackageLayout'), true);
assert.equal(phase1dSource.includes('extractMinimizerCheckpointCollectionPackageV1'), true);

const provenanceImportStart = phase1dSource.indexOf('async function importProvenanceFiles()');
const provenanceImportEnd = phase1dSource.indexOf('async function importEvidenceFiles()', provenanceImportStart);
assert.ok(provenanceImportStart >= 0 && provenanceImportEnd > provenanceImportStart);
const provenanceImportSection = phase1dSource.slice(provenanceImportStart, provenanceImportEnd);
assert.equal(provenanceImportSection.includes('MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA'), true);
assert.equal(provenanceImportSection.includes('extractMinimizerCheckpointCollectionPackageV1(parsed)'), true);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointCollectionRunIdV1'), false);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointCollectionEventV1'), false);
assert.equal(provenanceImportSection.includes('recordLiveCollectionProvenance'), false);
assert.equal(provenanceImportSection.includes('collectionProvenanceEvents.push'), false);

const recordStart = phase1dSource.indexOf('async function recordLiveCollectionProvenance(');
const recordEnd = phase1dSource.indexOf('async function refreshProvenanceCensus()', recordStart);
assert.ok(recordStart >= 0 && recordEnd > recordStart);
const recordSection = phase1dSource.slice(recordStart, recordEnd);
assert.equal(recordSection.includes('createMinimizerCheckpointCollectionPackageV1'), true);
assert.equal(recordSection.includes('__kq1agiCheckpointCollectionPackage'), true);

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointCollectionPackageV1'), false);
assert.equal(editSection.includes('refreshCollectionPackage'), false);

console.log('minimizer checkpoint collection package tests: PASS');
