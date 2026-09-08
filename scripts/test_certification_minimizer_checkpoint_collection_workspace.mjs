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
  createMinimizerCheckpointCollectionWorkspaceStoreV1,
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
assert.equal(
  MinimizerCheckpointCollectionWorkspaceLayout.MAX_IMPORT_FILE_BYTES,
  16 * 1024 * 1024,
);
assert.equal(
  MinimizerCheckpointCollectionWorkspaceLayout.MAX_IMPORT_BATCH_BYTES,
  64 * 1024 * 1024,
);

const duplicateAtRawCapacity = await updateMinimizerCheckpointCollectionWorkspaceV1({
  currentPackages: Array(
    MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES,
  ).fill(packageB),
  incomingPackages: [packageB],
});
assert.equal(duplicateAtRawCapacity.packageCount, 1,
  'An exact duplicate must remain idempotent even when raw submitted count exceeds the final unique capacity.');

await assert.rejects(
  updateMinimizerCheckpointCollectionWorkspaceV1({
    incomingPackages: Array(
      MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES + 1,
    ).fill(packageB),
  }),
  /package safety limit/,
);

const concurrentStore = createMinimizerCheckpointCollectionWorkspaceStoreV1();
const [concurrentA, concurrentB] = await Promise.all([
  concurrentStore.commit([packageA1]),
  concurrentStore.commit([packageB]),
]);
assert.equal(concurrentA.packageCount, 1);
assert.equal(concurrentB.packageCount, 2,
  'Queued workspace commits must include the previously committed concurrent batch.');
assert.equal(concurrentStore.snapshot().packageCount, 2);
assert.deepEqual(
  concurrentStore.snapshot().packageHashes,
  concurrentB.packageHashes,
);

await assert.rejects(
  concurrentStore.commit([packageAConflict]),
  /Conflicting provenance snapshots share collection run/,
);
const afterRejectedConcurrent = concurrentStore.snapshot();
assert.equal(afterRejectedConcurrent.packageCount, 2,
  'Rejected queued commits must preserve the last successful workspace.');

const afterRejectedFollowup = await concurrentStore.commit([packageA2]);
assert.equal(afterRejectedFollowup.packageCount, 3,
  'A rejected queued commit must not poison later commits.');
assert.equal(afterRejectedFollowup.manifest.derived.toolObservedCollectionEvents, 3);

const [phase1dSource, panelSource, workspaceSource] = await Promise.all([
  readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8'),
  readFile(new URL('../web/certification-panel.mjs', import.meta.url), 'utf8'),
  readFile(new URL('../web/certification-minimizer-checkpoint-collection-workspace.mjs', import.meta.url), 'utf8'),
]);
assert.equal(
  phase1dSource.includes("from './certification-minimizer-checkpoint-collection-workspace.mjs'"),
  true,
);
assert.equal(phase1dSource.includes('certify-import-collection-packages-button'), true);
assert.equal(phase1dSource.includes('certify-export-collection-manifest-button'), true);
assert.equal(phase1dSource.includes('certify-import-collection-packages-input'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointCollectionManifest'), true);
assert.equal(phase1dSource.includes('serializeMinimizerCheckpointCollectionManifestV1'), true);
assert.equal(phase1dSource.includes('createMinimizerCheckpointCollectionWorkspaceStoreV1'), true);
assert.equal(phase1dSource.includes('MinimizerCheckpointCollectionWorkspaceLayout'), true);
assert.equal(phase1dSource.includes('collectionPackageImportRunning'), true);
assert.equal(phase1dSource.includes('certificationPanelController'), true);
assert.equal(phase1dSource.includes('subscribeBusy'), true);
assert.equal(phase1dSource.includes('handlingCertificationPanelBusyNotification'), true);
assert.equal(phase1dSource.includes('acquireReplayPanelBusy'), true);
assert.equal(phase1dSource.includes('releaseReplayPanelBusy'), true);
assert.equal(phase1dSource.includes('const acquireReplayPanelBusy = label =>'), true);
assert.equal((phase1dSource.match(/acquireReplayPanelBusy\('/g) ?? []).length, 4,
  'Expected four Phase -1D acquisition sites.');
assert.equal((phase1dSource.match(/releaseReplayPanelBusy\(\);/g) ?? []).length, 4,
  'Every Phase -1D work path must release the shared busy lock in finally.');
assert.equal(panelSource.includes('__kq1agiCertificationPanelController'), true);
assert.equal(panelSource.includes('acquireExternalBusy'), true);
assert.equal(panelSource.includes('releaseExternalBusy'), true);
assert.equal(panelSource.includes('subscribeBusy'), true);
assert.equal(panelSource.includes('stopButton.disabled = !running'), true);
assert.equal(panelSource.includes('if (running || refreshing || externalBusyCount > 0) return;'), true);
assert.equal(workspaceSource.includes('submittedCount'), false);
assert.equal(workspaceSource.includes('incomingPackages.length > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES'), true);
assert.equal(workspaceSource.includes('uniqueByHash.size > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES'), true);
assert.equal(workspaceSource.includes('validatedReferences'), true);
assert.equal(workspaceSource.includes('MAX_IMPORT_FILE_BYTES: 16 * 1024 * 1024'), true);
assert.equal(workspaceSource.includes('MAX_IMPORT_BATCH_BYTES: 64 * 1024 * 1024'), true);

const workspaceImportStart = phase1dSource.indexOf('async function importCollectionPackageFiles()');
const workspaceImportEnd = phase1dSource.indexOf('function exportProvenanceCensus()', workspaceImportStart);
assert.ok(workspaceImportStart >= 0 && workspaceImportEnd > workspaceImportStart);
const workspaceImportSection = phase1dSource.slice(workspaceImportStart, workspaceImportEnd);
assert.equal(workspaceImportSection.includes('MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA'), true);
assert.equal(workspaceImportSection.includes('commitCollectionWorkspace(batch)'), true);
assert.equal(workspaceImportSection.includes('collectionPackageImportRunning'), true);
assert.equal(workspaceImportSection.includes("setStatus('COLLECTION IMPORT BUSY'"), true);
assert.equal(workspaceImportSection.includes('workspacePackageCount'), false,
  'Browser preflight must not count already committed packages before deduplication.');
assert.equal(workspaceImportSection.includes(
  'if (files.length > MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES)'
), true);
assert.equal(
  workspaceImportSection.indexOf('MinimizerCheckpointCollectionWorkspaceLayout.MAX_PACKAGES')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'Browser package-count rejection must happen before any selected file is read.',
);
assert.equal(
  workspaceImportSection.indexOf('MAX_IMPORT_BATCH_BYTES')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'Browser aggregate-byte rejection must happen before any selected file is read.',
);
assert.equal(
  workspaceImportSection.indexOf('MAX_IMPORT_FILE_BYTES')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'Browser per-file byte rejection must happen before the selected file is read.',
);
assert.equal(workspaceImportSection.includes(
  'Collection workspace incoming files exceed the aggregate byte safety limit.'
), true);
assert.equal(
  workspaceImportSection.indexOf('collectionPackageImportRunning = true')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'Browser file parsing must be serialized before any selected file is read.',
);
assert.equal(
  workspaceImportSection.indexOf('acquireExternalBusy')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'The base certification controller lock must be acquired before package-file parsing begins.',
);
assert.equal(
  workspaceImportSection.indexOf('setReplayRunning(replayRunning)')
    < workspaceImportSection.indexOf('file.text()'),
  true,
  'Phase -1I controls must lock before package-file parsing begins.',
);
assert.equal(workspaceImportSection.includes('releaseExternalBusy'), true);
assert.equal(workspaceImportSection.includes('collectionPackageImportRunning = false'), true);
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
assert.equal(workspaceCommitSection.includes('collectionWorkspaceStore.commit(incomingPackages)'), true);
assert.equal(workspaceCommitSection.includes('collectionWorkspacePackages.splice'), false);
assert.equal(workspaceCommitSection.includes('updateMinimizerCheckpointCollectionWorkspaceV1'), false);

for (const functionName of ['startReplay', 'startMinimize', 'startReduceInputs', 'startReduceEdits']) {
  const start = phase1dSource.indexOf(`async function ${functionName}()`);
  assert.ok(start >= 0, `Missing ${functionName}`);
  const next = phase1dSource.indexOf('\n  async function ', start + 1);
  const section = phase1dSource.slice(start, next >= 0 ? next : phase1dSource.length);
  assert.equal(section.includes('acquireReplayPanelBusy('), true,
    `${functionName} must acquire the shared base-panel lock.`);
  assert.equal(section.includes('setReplayRunning(true)'), true);
  assert.equal(section.includes('setReplayRunning(false);\n      releaseReplayPanelBusy();'), true,
    `${functionName} must release the shared lock only after local replay state is cleared.`);
}

const liveStart = phase1dSource.indexOf('async function recordLiveCollectionProvenance(');
const liveEnd = phase1dSource.indexOf('async function refreshProvenanceCensus()', liveStart);
assert.ok(liveStart >= 0 && liveEnd > liveStart);
const liveSection = phase1dSource.slice(liveStart, liveEnd);
assert.equal(liveSection.includes('createMinimizerCheckpointCollectionPackageV1'), true);
assert.equal(liveSection.includes('refreshCollectionWorkspaceFromLivePackage()'), true);

console.log('minimizer checkpoint collection workspace tests: PASS');
