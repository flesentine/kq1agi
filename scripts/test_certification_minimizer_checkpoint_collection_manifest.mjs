import assert from 'node:assert/strict';

import {
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointCollectionEventV1,
  createMinimizerCheckpointCollectionProvenanceV1,
} from '../web/certification-minimizer-checkpoint-provenance.mjs';
import {
  createMinimizerCheckpointCollectionPackageV1,
} from '../web/certification-minimizer-checkpoint-collection-package.mjs';
import {
  createMinimizerCheckpointCollectionManifestV1,
  MinimizerCheckpointCollectionManifestLayout,
  serializeMinimizerCheckpointCollectionManifestV1,
  validateMinimizerCheckpointCollectionManifestV1,
} from '../web/certification-minimizer-checkpoint-collection-manifest.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const runA = `kq1agi-collection-run-v1:${'a'.repeat(32)}`;
const runB = `kq1agi-collection-run-v1:${'b'.repeat(32)}`;

function sourceRecording(hash, gameHash, editConfigHash) {
  return Object.freeze({
    hash,
    gameHash,
    gameBytes: 17295,
    editConfigHash,
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

async function makeStage({ stageName, sourceHash, gameHash, editConfigHash, targetTick, reason }) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: stageName,
    sourceRecording: sourceRecording(sourceHash, gameHash, editConfigHash),
    targetDivergence: { tick: targetTick },
    shadowState: unavailableShadowState(reason, targetTick),
    observations: [],
    collectionErrorCandidateHashes: [],
    outcome: { status: 'MINIMIZED', attempts: 0 },
  });
}

async function makePackage({ collectionRunId, stages }) {
  const evidenceReport = await createMinimizerCheckpointEvidenceReportV1(stages);
  const events = [];
  for (let ordinal = 0; ordinal < stages.length; ordinal += 1) {
    events.push(await createMinimizerCheckpointCollectionEventV1({
      collectionRunId,
      ordinal,
      stageHash: stages[ordinal].hash,
    }));
  }
  const provenance = await createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId,
    evidenceReport,
    events,
  });
  return createMinimizerCheckpointCollectionPackageV1({ evidenceReport, provenance });
}

const stage1 = await makeStage({
  stageName: 'phase-1e',
  sourceHash: sha('1'),
  gameHash: sha('2'),
  editConfigHash: sha('3'),
  targetTick: 12,
  reason: 'no-recorded-release',
});
const stage2 = await makeStage({
  stageName: 'phase-1f',
  sourceHash: sha('4'),
  gameHash: sha('2'),
  editConfigHash: sha('3'),
  targetTick: 20,
  reason: 'checkpoint-incompatible',
});

const packageA1 = await makePackage({ collectionRunId: runA, stages: [stage1] });
const packageA2 = await makePackage({ collectionRunId: runA, stages: [stage1, stage2] });
const packageB = await makePackage({ collectionRunId: runB, stages: [stage1] });

const manifest = await createMinimizerCheckpointCollectionManifestV1([
  packageB,
  packageA2,
  packageA1,
  packageB,
]);

assert.equal(manifest.schema, MinimizerCheckpointCollectionManifestLayout.MANIFEST_SCHEMA);
assert.equal(manifest.policy, 'full-replay-authoritative');
assert.equal(manifest.policyFrozen, false);
assert.equal(manifest.policyDecision, 'EVIDENCE_ONLY');
assert.equal(manifest.accelerationAllowed, false);
assert.equal(manifest.manifestDecision, 'COLLECTION_SET_ARCHIVE_ONLY');
assert.equal(manifest.packageCount, 3, 'Exact duplicate package hashes must collapse.');
assert.equal(manifest.collectionRunCount, 2);
assert.deepEqual(manifest.collectionRunIds, [runA, runB]);
assert.deepEqual(manifest.packageHashes, [...manifest.packageHashes].sort());
assert.equal(manifest.derived.uniqueCollectionRuns, 2);
assert.equal(manifest.derived.toolObservedCollectionEvents, 3,
  'I.10 must select the longest consistent run-A snapshot plus run B.');
assert.equal(manifest.derived.distinctStageHashes, 2);
assert.equal(manifest.derived.crossRunRepeatedStageHashes, 1);
assert.equal(manifest.derived.cohortCount, 1);
assert.equal(manifest.derived.multiIdentityCollectionRuns, 0);
assert.equal(manifest.derived.maxIdentitiesPerRun, 1);
assert.match(manifest.hash, /^sha256:[0-9a-f]{64}$/);

const reordered = await createMinimizerCheckpointCollectionManifestV1([
  packageA1,
  packageB,
  packageA2,
]);
assert.equal(reordered.hash, manifest.hash, 'Manifest hash must be package-order independent.');

const validated = await validateMinimizerCheckpointCollectionManifestV1(
  manifest,
  [packageA2, packageA1, packageB],
);
assert.equal(validated.valid, true);
assert.equal(validated.hash, manifest.hash);
assert.equal(validated.packageCount, 3);
assert.equal(validated.collectionRunCount, 2);
assert.equal(validated.provenanceCensusHash, manifest.derived.provenanceCensusHash);
assert.equal(validated.provenanceCoverageMatrixHash, manifest.derived.provenanceCoverageMatrixHash);
assert.equal(validated.provenanceSessionTopologyHash, manifest.derived.provenanceSessionTopologyHash);

const duplicateOnly = await createMinimizerCheckpointCollectionManifestV1([
  packageB,
  packageB,
]);
const single = await createMinimizerCheckpointCollectionManifestV1([packageB]);
assert.equal(duplicateOnly.hash, single.hash, 'Exact duplicate package imports must be idempotent.');

const serialized = serializeMinimizerCheckpointCollectionManifestV1(manifest);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"manifestDecision": "COLLECTION_SET_ARCHIVE_ONLY"'), true);
assert.equal(serialized.includes('"accelerationAllowed": false'), true);
assert.equal(serialized.includes('"workerPayload":'), false);

const tampered = structuredClone(manifest);
tampered.caveats[0] = 'TAMPERED';
await assert.rejects(
  validateMinimizerCheckpointCollectionManifestV1(
    tampered,
    [packageA1, packageA2, packageB],
  ),
  /hash mismatch/,
);

const wrongPopulation = await createMinimizerCheckpointCollectionManifestV1([packageB]);
await assert.rejects(
  validateMinimizerCheckpointCollectionManifestV1(
    wrongPopulation,
    [packageA1, packageA2, packageB],
  ),
  /population mismatch/,
);

const conflictingPackage = structuredClone(packageA2);
conflictingPackage.provenance.events[0].eventHash = sha('f');
await assert.rejects(
  createMinimizerCheckpointCollectionManifestV1([conflictingPackage]),
  /hash mismatch|provenance|validation/i,
);

await assert.rejects(
  createMinimizerCheckpointCollectionManifestV1([]),
  /at least one/,
);

console.log('minimizer checkpoint collection manifest tests: PASS');
