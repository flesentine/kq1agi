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
  createMinimizerCheckpointCollectionPackageV1,
} from '../web/certification-minimizer-checkpoint-collection-package.mjs';
import {
  MinimizerCheckpointCollectionManifestLayout,
} from '../web/certification-minimizer-checkpoint-collection-manifest.mjs';
import {
  MinimizerCheckpointCollectionWorkspaceLayout,
  updateMinimizerCheckpointCollectionWorkspaceV1,
} from '../web/certification-minimizer-checkpoint-collection-workspace.mjs';

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

async function makeStage({
  stageName,
  sourceHash,
  gameHash,
  editConfigHash,
  targetTick,
  reason,
}) {
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
const packageAConflict = await makePackage({ collectionRunId: runA, stages: [stage2] });
const packageB = await makePackage({ collectionRunId: runB, stages: [stage1] });

const first = await updateMinimizerCheckpointCollectionWorkspaceV1({
  incomingPackages: [packageB, packageA1, packageB],
});
assert.equal(first.packageCount, 2);
assert.deepEqual(first.packageHashes, [...first.packageHashes].sort());
assert.equal(first.manifest.packageCount, 2);
assert.equal(first.manifest.collectionRunCount, 2);
assert.equal(first.manifest.accelerationAllowed, false);
assert.equal(first.manifest.manifestDecision, 'COLLECTION_SET_ARCHIVE_ONLY');

const extended = await updateMinimizerCheckpointCollectionWorkspaceV1({
  currentPackages: first.packages,
  incomingPackages: [packageA2, packageB],
});
assert.equal(extended.packageCount, 3);
assert.equal(extended.manifest.packageCount, 3);
assert.equal(extended.manifest.collectionRunCount, 2);
assert.equal(extended.manifest.derived.toolObservedCollectionEvents, 3);
assert.equal(extended.manifest.derived.distinctStageHashes, 2);

const reordered = await updateMinimizerCheckpointCollectionWorkspaceV1({
  incomingPackages: [packageA2, packageA1, packageB],
});
assert.equal(reordered.manifest.hash, extended.manifest.hash);
assert.deepEqual(reordered.packageHashes, extended.packageHashes);

const beforeRejectedHash = extended.manifest.hash;
const beforeRejectedPackages = extended.packageHashes;
await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({
    currentPackages: extended.packages,
    incomingPackages: [packageAConflict],
  }),
  /Conflicting provenance snapshots share collection run/,
);
assert.equal(extended.manifest.hash, beforeRejectedHash);
assert.deepEqual(extended.packageHashes, beforeRejectedPackages);

const corrupted = structuredClone(packageB);
corrupted.caveats[0] = 'TAMPERED';
await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({
    currentPackages: extended.packages,
    incomingPackages: [corrupted],
  }),
  /hash mismatch/,
);

await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({
    incomingPackages: [{ schema: 'not-a-package' }],
  }),
  /Phase -1I\.13 packages only/,
);

await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({}),
  /at least one/,
);

assert.equal(
  MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES,
  MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES,
);
await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({
    incomingPackages: Array(
      MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES + 1,
    ).fill(packageB),
  }),
  /package safety limit/,
);

const phase1dSource = await readFile(
  new URL('../web/certification-phase1d.mjs', import.meta.url),
  'utf8',
);
assert.equal(
  phase1dSource.includes("from './certification-minimizer-checkpoint-collection-workspace.mjs'"),
  true,
);
assert.equal(phase1dSource.includes('certify-import-collection-packages-button'), true);
assert.equal(phase1dSource.includes('certify-export-collection-manifest-button'), true);
assert.equal(phase1dSource.includes('certify-import-collection-packages-input'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointCollectionManifest'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointCollectionManifestV1'), true);
assert.equal(phase1dSource.includes('updateMinimizerCheckpointCollectionWorkspaceV1'), true);

const workspaceImportStart = phase1dSource.indexOf('async function importCollectionPackageFiles()');
const workspaceImportEnd = phase1dSource.indexOf('function exportProvenanceCensus()', workspaceImportStart);
assert.ok(workspaceImportStart >= 0 && workspaceImportEnd > workspaceImportStart);
const workspaceImportSection = phase1dSource.slice(workspaceImportStart, workspaceImportEnd);
assert.equal(workspaceImportSection.includes('MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA'), true);
assert.equal(workspaceImportSection.includes('commitCollectionWorkspace(batch)'), true);
assert.equal(workspaceImportSection.includes('createMinimizerCheckpointCollectionRunIdV1'), false);
assert.equal(workspaceImportSection.includes('createMinimizerCheckpointCollectionEventV1'), false);
assert.equal(workspaceImportSection.includes('createMinimizerCheckpointCollectionProvenanceV1'), false);
assert.equal(workspaceImportSection.includes('collectionProvenanceEvents.push'), false);
assert.equal(workspaceImportSection.includes('importedProvenancePackages.push'), false);

const workspaceCommitStart = phase1dSource.indexOf('async function commitCollectionWorkspace(');
const workspaceCommitEnd = phase1dSource.indexOf(
  'async function refreshCollectionWorkspaceFromLivePackage()',
  workspaceCommitStart,
);
assert.ok(workspaceCommitStart >= 0 && workspaceCommitEnd > workspaceCommitStart);
const workspaceCommitSection = phase1dSource.slice(workspaceCommitStart, workspaceCommitEnd);
assert.equal(workspaceCommitSection.includes('updateMinimizerCheckpointCollectionWorkspaceV1'), true);
assert.equal(workspaceCommitSection.indexOf('collectionWorkspacePackages.splice')
  > workspaceCommitSection.indexOf('await updateMinimizerCheckpointCollectionWorkspaceV1'), true,
  'Browser workspace state must commit only after the candidate validates.');

const liveStart = phase1dSource.indexOf('async function recordLiveCollectionProvenance(');
const liveEnd = phase1dSource.indexOf('async function refreshProvenanceCensus()', liveStart);
assert.ok(liveStart >= 0 && liveEnd > liveStart);
const liveSection = phase1dSource.slice(liveStart, liveEnd);
assert.equal(liveSection.includes('createMinimizerCheckpointCollectionPackageV1'), true);
assert.equal(liveSection.includes('refreshCollectionWorkspaceFromLivePackage()'), true);

console.log('minimizer checkpoint collection workspace tests: PASS');
