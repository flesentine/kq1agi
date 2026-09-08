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
  createMinimizerCheckpointProvenanceSessionTopologyV1,
  MinimizerCheckpointProvenanceSessionTopologyLayout,
  serializeMinimizerCheckpointProvenanceSessionTopologyV1,
} from '../web/certification-minimizer-checkpoint-provenance-session-topology.mjs';

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

async function stage({
  stageName,
  identity,
  sourceHash,
  targetTick,
  reason,
}) {
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
  reason: 'no-recorded-release',
});
const stageA2 = await stage({
  stageName: 'phase-1f',
  identity: identityA,
  sourceHash: sha('6'),
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});
const stageB1 = await stage({
  stageName: 'phase-1e',
  identity: identityB,
  sourceHash: sha('7'),
  targetTick: 14,
  reason: 'pause-unavailable',
});

const packageRunA = await packageFor(runA, [stageA1, stageB1]);
const packageRunB = await packageFor(runB, [stageA1, stageA2]);

const topology = await createMinimizerCheckpointProvenanceSessionTopologyV1([
  packageRunA,
  packageRunB,
]);

assert.equal(topology.schema, MinimizerCheckpointProvenanceSessionTopologyLayout.TOPOLOGY_SCHEMA);
assert.equal(topology.policy, 'full-replay-authoritative');
assert.equal(topology.policyFrozen, false);
assert.equal(topology.policyDecision, 'EVIDENCE_ONLY');
assert.equal(topology.accelerationAllowed, false);
assert.equal(topology.topologyDecision, 'DESCRIPTIVE_ONLY');
assert.equal(topology.provenanceDecision, 'COLLECTION_IDENTITY_ONLY');
assert.equal(topology.cohortIdentity, 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH');
assert.equal(topology.uniqueCollectionRuns, 2);
assert.equal(topology.toolObservedCollectionEvents, 4);
assert.equal(topology.multiIdentityCollectionRuns, 1);
assert.deepEqual(topology.multiIdentityCollectionRunIds, [runA]);
assert.equal(topology.maxIdentitiesPerRun, 2);
assert.equal(topology.thresholdPolicy.status, 'UNSET');
assert.equal(topology.thresholdPolicy.maximumIdentitiesPerRun, null);
assert.equal(topology.thresholdPolicy.maximumMultiIdentityCollectionRuns, null);
assert.match(topology.provenanceCensusHash, /^sha256:[0-9a-f]{64}$/);
assert.match(topology.provenanceCoverageMatrixHash, /^sha256:[0-9a-f]{64}$/);

const byRun = new Map(topology.runs.map(run => [run.collectionRunId, run]));
const a = byRun.get(runA);
const b = byRun.get(runB);
assert.ok(a);
assert.ok(b);

assert.equal(a.eventCount, 2);
assert.equal(a.distinctStageHashes, 2);
assert.equal(a.identityCount, 2);
assert.equal(a.multiIdentity, true);
assert.equal(a.identities.length, 2);
assert.equal(a.identityCohortKeys.length, 2);
assert.equal(
  a.identities.reduce((sum, item) => sum + item.toolObservedCollectionEvents, 0),
  a.eventCount,
);

const aByGame = new Map(a.identities.map(item => [item.identity.gameHash, item]));
const aIdentityA = aByGame.get(identityA.game);
const aIdentityB = aByGame.get(identityB.game);
assert.ok(aIdentityA);
assert.ok(aIdentityB);
assert.equal(aIdentityA.identity.editConfigHash, identityA.edit);
assert.equal(aIdentityA.toolObservedCollectionEvents, 1);
assert.equal(aIdentityA.distinctStageHashes, 1);
assert.deepEqual(aIdentityA.eventStageCounts, { 'phase-1e': 1 });
assert.deepEqual(aIdentityA.sourceRecordingHashes, [sha('5')]);
assert.deepEqual(aIdentityA.targetTicks, [12]);
assert.deepEqual(aIdentityA.stageHashes, [stageA1.hash]);
assert.equal(aIdentityA.eventHashes.length, 1);

assert.equal(aIdentityB.identity.editConfigHash, identityB.edit);
assert.equal(aIdentityB.toolObservedCollectionEvents, 1);
assert.equal(aIdentityB.distinctStageHashes, 1);
assert.deepEqual(aIdentityB.eventStageCounts, { 'phase-1e': 1 });
assert.deepEqual(aIdentityB.sourceRecordingHashes, [sha('7')]);
assert.deepEqual(aIdentityB.targetTicks, [14]);
assert.deepEqual(aIdentityB.stageHashes, [stageB1.hash]);

assert.equal(b.eventCount, 2);
assert.equal(b.distinctStageHashes, 2);
assert.equal(b.identityCount, 1);
assert.equal(b.multiIdentity, false);
assert.equal(b.identities.length, 1);
assert.equal(b.identities[0].identity.gameHash, identityA.game);
assert.equal(b.identities[0].identity.editConfigHash, identityA.edit);
assert.equal(b.identities[0].toolObservedCollectionEvents, 2);
assert.equal(b.identities[0].distinctStageHashes, 2);
assert.deepEqual(b.identities[0].eventStageCounts, { 'phase-1e': 1, 'phase-1f': 1 });
assert.deepEqual(b.identities[0].sourceRecordingHashes, [sha('5'), sha('6')].sort());
assert.deepEqual(b.identities[0].targetTicks, [12, 20]);
assert.deepEqual(b.identities[0].stageHashes, [stageA1.hash, stageA2.hash].sort());

const duplicate = await createMinimizerCheckpointProvenanceSessionTopologyV1([
  packageRunA,
  packageRunB,
  packageRunB,
]);
assert.equal(duplicate.hash, topology.hash, 'Exact duplicate provenance packages must be topology-idempotent.');

const reverse = await createMinimizerCheckpointProvenanceSessionTopologyV1([
  packageRunB,
  packageRunA,
]);
assert.equal(reverse.hash, topology.hash, 'Package order must not change topology hash.');

const packageRunAPrefix = await packageFor(runA, [stageA1]);
const prefix = await createMinimizerCheckpointProvenanceSessionTopologyV1([
  packageRunAPrefix,
  packageRunA,
  packageRunB,
]);
assert.equal(prefix.uniqueCollectionRuns, topology.uniqueCollectionRuns);
assert.equal(prefix.toolObservedCollectionEvents, topology.toolObservedCollectionEvents);
assert.equal(prefix.multiIdentityCollectionRuns, topology.multiIdentityCollectionRuns);
assert.deepEqual(prefix.multiIdentityCollectionRunIds, topology.multiIdentityCollectionRunIds);
assert.notEqual(prefix.provenanceCensusHash, topology.provenanceCensusHash);
assert.notEqual(prefix.hash, topology.hash, 'Topology binds to exact I.10/I.11 canonical snapshot history.');

const conflict = await packageFor(runA, [stageA2, stageB1]);
await assert.rejects(
  createMinimizerCheckpointProvenanceSessionTopologyV1([
    packageRunA,
    conflict,
  ]),
  /Conflicting provenance snapshots share collection run|Conflicting provenance history/,
);

const serialized = serializeMinimizerCheckpointProvenanceSessionTopologyV1(topology);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"topologyDecision": "DESCRIPTIVE_ONLY"'), true);
assert.equal(serialized.includes('"status": "UNSET"'), true);
assert.equal(serialized.includes('"workerPayload":'), false);
assert.match(topology.hash, /^sha256:[0-9a-f]{64}$/);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-provenance-topology-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointProvenanceSessionTopology'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointProvenanceSessionTopologyV1'), true);

const provenanceImportStart = phase1dSource.indexOf('async function importProvenanceFiles()');
const provenanceImportEnd = phase1dSource.indexOf('async function importEvidenceFiles()', provenanceImportStart);
const provenanceImportSection = phase1dSource.slice(provenanceImportStart, provenanceImportEnd);
assert.equal(provenanceImportSection.includes('importedEvidenceArtifacts'), false);
assert.equal(provenanceImportSection.includes('createMinimizerCheckpointEvidenceCorpusV1'), false);
const censusIndex = provenanceImportSection.indexOf('await createMinimizerCheckpointProvenanceCensusV1(candidatePackages)');
const matrixIndex = provenanceImportSection.indexOf('await createMinimizerCheckpointProvenanceCoverageMatrixV1(candidatePackages)');
const topologyIndex = provenanceImportSection.indexOf('await createMinimizerCheckpointProvenanceSessionTopologyV1(candidatePackages)');
const commitIndex = provenanceImportSection.indexOf('importedProvenancePackages.push(...committedBatch)');
assert.ok(
  censusIndex >= 0 && matrixIndex > censusIndex && topologyIndex > matrixIndex && commitIndex > topologyIndex,
  'Provenance import must validate I.10, I.11, and I.12 before committing the batch.',
);

const evidenceImportStart = phase1dSource.indexOf('async function importEvidenceFiles()');
const evidenceImportEnd = phase1dSource.indexOf('function refreshJournal()', evidenceImportStart);
const evidenceImportSection = phase1dSource.slice(evidenceImportStart, evidenceImportEnd);
assert.equal(evidenceImportSection.includes('createMinimizerCheckpointProvenanceSessionTopologyV1'), false);

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointProvenanceSessionTopologyV1'), false);
assert.equal(editSection.includes('refreshProvenanceSessionTopology'), false);

console.log('minimizer checkpoint provenance session topology tests: PASS');
