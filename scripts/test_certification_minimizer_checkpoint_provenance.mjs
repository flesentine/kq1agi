import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointCollectionEventV1,
  createMinimizerCheckpointCollectionProvenanceV1,
  createMinimizerCheckpointCollectionRunIdV1,
  MinimizerCheckpointProvenanceLayout,
  serializeMinimizerCheckpointCollectionProvenanceV1,
  validateMinimizerCheckpointCollectionProvenanceV1,
} from '../web/certification-minimizer-checkpoint-provenance.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const runA = `kq1agi-collection-run-v1:${'a'.repeat(32)}`;
const runB = `kq1agi-collection-run-v1:${'b'.repeat(32)}`;

function sourceRecording(hash = sha('1')) {
  return Object.freeze({
    hash,
    gameHash: sha('2'),
    gameBytes: 17295,
    editConfigHash: sha('3'),
    finalTick: 12,
    events: [],
    random: [],
    releaseTicks: [],
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

async function stage({
  stageName = 'phase-1e',
  sourceHash = sha('1'),
  targetTick = 12,
  reason = 'no-recorded-release',
} = {}) {
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

const generatedRunId = createMinimizerCheckpointCollectionRunIdV1();
assert.match(generatedRunId, /^kq1agi-collection-run-v1:[0-9a-f]{32}$/);

const stageA = await stage();
const reportA = await createMinimizerCheckpointEvidenceReportV1([stageA]);

const eventA0 = await createMinimizerCheckpointCollectionEventV1({
  collectionRunId: runA,
  ordinal: 0,
  stageHash: stageA.hash,
});
assert.equal(eventA0.schema, MinimizerCheckpointProvenanceLayout.EVENT_SCHEMA);
assert.equal(eventA0.collectionRunId, runA);
assert.equal(eventA0.ordinal, 0);
assert.equal(eventA0.stageHash, stageA.hash);
assert.match(eventA0.eventHash, /^sha256:[0-9a-f]{64}$/);

const eventA0Again = await createMinimizerCheckpointCollectionEventV1({
  collectionRunId: runA,
  ordinal: 0,
  stageHash: stageA.hash,
});
assert.equal(eventA0Again.eventHash, eventA0.eventHash, 'Event hash must be deterministic.');

const eventB0 = await createMinimizerCheckpointCollectionEventV1({
  collectionRunId: runB,
  ordinal: 0,
  stageHash: stageA.hash,
});
assert.notEqual(
  eventB0.eventHash,
  eventA0.eventHash,
  'The same deterministic stage collected in a different live run must get a distinct event identity.',
);

const provenanceA = await createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId: runA,
  evidenceReport: reportA,
  events: [eventA0],
});
assert.equal(provenanceA.schema, MinimizerCheckpointProvenanceLayout.PROVENANCE_SCHEMA);
assert.equal(provenanceA.policy, 'full-replay-authoritative');
assert.equal(provenanceA.policyFrozen, false);
assert.equal(provenanceA.policyDecision, 'EVIDENCE_ONLY');
assert.equal(provenanceA.accelerationAllowed, false);
assert.equal(provenanceA.provenanceDecision, 'COLLECTION_IDENTITY_ONLY');
assert.equal(provenanceA.collectionRunId, runA);
assert.equal(provenanceA.evidenceReportHash, reportA.hash);
assert.equal(provenanceA.eventCount, 1);
assert.deepEqual(provenanceA.distinctStageHashes, [stageA.hash]);
assert.equal(provenanceA.events[0].eventHash, eventA0.eventHash);
assert.match(provenanceA.hash, /^sha256:[0-9a-f]{64}$/);

const validatedA = await validateMinimizerCheckpointCollectionProvenanceV1(provenanceA, reportA);
assert.equal(validatedA.valid, true);
assert.equal(validatedA.hash, provenanceA.hash);
assert.equal(validatedA.collectionRunId, runA);
assert.equal(validatedA.eventCount, 1);

const provenanceAAgain = await createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId: runA,
  evidenceReport: reportA,
  events: [eventA0],
});
assert.equal(provenanceAAgain.hash, provenanceA.hash, 'Same live run + report + events must re-export deterministically.');

const provenanceB = await createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId: runB,
  evidenceReport: reportA,
  events: [eventB0],
});
assert.notEqual(
  provenanceB.hash,
  provenanceA.hash,
  'Different live collection runs must remain distinguishable even when stage evidence bytes are identical.',
);

const duplicateReport = await createMinimizerCheckpointEvidenceReportV1([stageA, stageA]);
const eventA1 = await createMinimizerCheckpointCollectionEventV1({
  collectionRunId: runA,
  ordinal: 1,
  stageHash: stageA.hash,
});
const repeatedLiveCollection = await createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId: runA,
  evidenceReport: duplicateReport,
  events: [eventA0, eventA1],
});
assert.equal(repeatedLiveCollection.eventCount, 2);
assert.deepEqual(repeatedLiveCollection.distinctStageHashes, [stageA.hash]);
assert.notEqual(eventA0.eventHash, eventA1.eventHash, 'Distinct live events in one run must have distinct event hashes.');

await assert.rejects(
  createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: runA,
    evidenceReport: reportA,
    events: [eventA1],
  }),
  /ordinal sequence mismatch/,
);

const foreignEvent = await createMinimizerCheckpointCollectionEventV1({
  collectionRunId: runA,
  ordinal: 0,
  stageHash: sha('f'),
});
await assert.rejects(
  createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: runA,
    evidenceReport: reportA,
    events: [foreignEvent],
  }),
  /outside its evidence report/,
);

const stageB = await stage({
  stageName: 'phase-1f',
  sourceHash: sha('4'),
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});
const reportAB = await createMinimizerCheckpointEvidenceReportV1([stageA, stageB]);
await assert.rejects(
  validateMinimizerCheckpointCollectionProvenanceV1(provenanceA, reportAB),
  /evidence report hash mismatch/,
);

const tamperedEvent = { ...eventA0, eventHash: sha('e') };
await assert.rejects(
  createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: runA,
    evidenceReport: reportA,
    events: [tamperedEvent],
  }),
  /event hash mismatch/,
);

const forbiddenEvent = { ...eventA0, workerPayload: [1, 2, 3] };
await assert.rejects(
  createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: runA,
    evidenceReport: reportA,
    events: [forbiddenEvent],
  }),
  /forbidden raw oracle field/,
);

await assert.rejects(
  createMinimizerCheckpointCollectionEventV1({
    collectionRunId: 'bad-run-id',
    ordinal: 0,
    stageHash: stageA.hash,
  }),
  /run ID is invalid/,
);

const serialized = serializeMinimizerCheckpointCollectionProvenanceV1(provenanceA);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"provenanceDecision": "COLLECTION_IDENTITY_ONLY"'), true);
assert.equal(serialized.includes('"workerPayload":'), false);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-export-collection-provenance-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointCollectionRunId'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointCollectionProvenance'), true);
assert.equal(phase1dSource.includes('createMinimizerCheckpointCollectionEventV1'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointCollectionProvenanceV1'), true);

const recordStart = phase1dSource.indexOf('async function recordShadowEvidenceStage(');
const recordEnd = phase1dSource.indexOf('function exportShadowEvidence()', recordStart);
assert.ok(recordStart >= 0 && recordEnd > recordStart);
const recordSection = phase1dSource.slice(recordStart, recordEnd);
assert.equal(recordSection.includes('await recordLiveCollectionProvenance(stageEvidence)'), true);

const importStart = phase1dSource.indexOf('async function importEvidenceFiles()');
const importEnd = phase1dSource.indexOf('function refreshJournal()', importStart);
assert.ok(importStart >= 0 && importEnd > importStart);
const importSection = phase1dSource.slice(importStart, importEnd);
assert.equal(importSection.includes('createMinimizerCheckpointCollectionEventV1'), false);
assert.equal(importSection.includes('recordLiveCollectionProvenance'), false);
assert.equal(importSection.includes('collectionProvenanceEvents.push'), false);

const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf('replayButton.addEventListener', editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('recordLiveCollectionProvenance'), false);
assert.equal(editSection.includes('createMinimizerCheckpointCollectionEventV1'), false);
assert.equal(editSection.includes('createMinimizerCheckpointCollectionProvenanceV1'), false);

console.log('minimizer checkpoint collection provenance tests: PASS');
