import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  compactMinimizerCheckpointObservationV1,
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
  serializeMinimizerCheckpointEvidenceReportV1,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';

function evidence(recordingHash, workerByte = 1) {
  const lane = {
    trace: [1, 2, 3],
    digest: [4, 5, 6],
    transport: {
      queue: [0, 1],
      keys: [0, 1],
      oldKeys: [0, 0],
      vars: [1, 2, 3],
      pixels: [4, 5, 6],
    },
    workerPayload: [workerByte, 2, 3, 4],
    quit: false,
    error: null,
    soundRequests: [],
  };
  return {
    schema: 'kq1agi-checkpoint-oracle-evidence-v1',
    context: {
      seed: 1234,
      gameHash: 'sha256:game',
      gameBytes: 17295,
      editConfigHash: 'sha256:edit',
      recordingHash,
      randomReplaySpec: 'fixture',
      recordedExternalTiming: true,
    },
    logicalTick: 12,
    cycle: 12,
    comparedCycle: 12,
    truth: structuredClone(lane),
    edited: structuredClone(lane),
    pendingSoundCompletions: [],
    pendingExternalDivergence: null,
  };
}

function summary(replayStartTick, consumedTicks) {
  return {
    status: 'REPLAY_MATCH',
    certifiedBarriers: consumedTicks,
    consumedTicks,
    replayStartTick,
    skippedPrefixTicks: replayStartTick,
    finalTick: 12,
    result: {
      status: 'MATCH',
      tick: 12,
      cycle: 12,
      snapshotEpoch: replayStartTick ? 2 : 99,
    },
  };
}

function equivalentShadow(candidateHash) {
  const fullEvidence = evidence(candidateHash);
  const checkpointEvidence = structuredClone(fullEvidence);
  return {
    summary: summary(0, 12),
    oracle: {
      status: 'CHECKPOINT_ORACLE_EQUIVALENT',
      authoritativeSummary: summary(0, 12),
      fullRun: { summary: summary(0, 12), evidence: fullEvidence },
      acceleratedRun: { summary: summary(5, 7), evidence: checkpointEvidence },
      fullTelemetry: { consumedTicks: 12, replayStartTick: 0 },
      checkpointTelemetry: { consumedTicks: 7, replayStartTick: 5 },
      checkpointAttempted: true,
      checkpointTrusted: true,
      savedTicks: 5,
      compatibility: {
        checkpointTick: 5,
        sourceRecordingHash: 'sha256:source',
        candidateRecordingHash: candidateHash,
        checkpointHash: 'sha256:checkpoint',
      },
      comparison: { equivalent: true, category: 'exact' },
    },
  };
}

function mismatchShadow(candidateHash) {
  const fullEvidence = evidence(candidateHash);
  const checkpointEvidence = evidence(candidateHash, 9);
  return {
    summary: summary(0, 12),
    oracle: {
      status: 'CHECKPOINT_ORACLE_MISMATCH',
      reason: 'evidence',
      authoritativeSummary: summary(0, 12),
      fullRun: { summary: summary(0, 12), evidence: fullEvidence },
      acceleratedRun: { summary: summary(5, 7), evidence: checkpointEvidence },
      fullTelemetry: { consumedTicks: 12, replayStartTick: 0 },
      checkpointTelemetry: { consumedTicks: 7, replayStartTick: 5 },
      checkpointAttempted: true,
      checkpointTrusted: false,
      compatibility: {
        checkpointTick: 5,
        sourceRecordingHash: 'sha256:source',
        candidateRecordingHash: candidateHash,
        checkpointHash: 'sha256:checkpoint',
      },
      comparison: {
        equivalent: false,
        category: 'evidence',
        difference: {
          path: '$.evidence.edited.workerPayload[0]',
          expected: 1,
          actual: 9,
          reason: 'value',
        },
      },
    },
  };
}

function fullOnlyShadow(candidateHash) {
  const fullEvidence = evidence(candidateHash);
  return {
    summary: summary(0, 12),
    oracle: {
      status: 'CHECKPOINT_ORACLE_FULL_ONLY',
      reason: 'checkpoint-incompatible',
      authoritativeSummary: summary(0, 12),
      fullRun: { summary: summary(0, 12), evidence: fullEvidence },
      fullTelemetry: { consumedTicks: 12, replayStartTick: 0 },
      checkpointAttempted: false,
      checkpointTrusted: false,
      compatibility: {
        checkpointTick: 5,
        sourceRecordingHash: 'sha256:source',
        candidateRecordingHash: candidateHash,
        checkpointHash: 'sha256:checkpoint',
      },
    },
  };
}

const candidateA = 'sha256:candidate-a';
const candidateB = 'sha256:candidate-b';
const equivalent = await compactMinimizerCheckpointObservationV1(equivalentShadow(candidateA), candidateA);
assert.equal(equivalent.schema, MinimizerCheckpointEvidenceLayout.OBSERVATION_SCHEMA);
assert.equal(equivalent.status, 'CHECKPOINT_ORACLE_EQUIVALENT');
assert.equal(equivalent.checkpointTrusted, true);
assert.equal(equivalent.savedTicks, 5);
assert.equal(equivalent.fullDecisionHash, equivalent.checkpointDecisionHash);
assert.equal(equivalent.fullEvidenceHash, equivalent.checkpointEvidenceHash);
assert.equal(equivalent.fullEvidenceValidation.valid, true);
assert.equal(equivalent.checkpointEvidenceValidation.valid, true);
assert.equal(Object.hasOwn(equivalent, 'fullRun'), false);
assert.equal(Object.hasOwn(equivalent, 'acceleratedRun'), false);
assert.equal(JSON.stringify(equivalent).includes('workerPayload'), false);

const mismatch = await compactMinimizerCheckpointObservationV1(mismatchShadow(candidateA), candidateA);
assert.equal(mismatch.status, 'CHECKPOINT_ORACLE_MISMATCH');
assert.equal(mismatch.reason, 'evidence');
assert.equal(mismatch.checkpointTrusted, false);
assert.equal(mismatch.fullDecisionHash, mismatch.checkpointDecisionHash);
assert.notEqual(mismatch.fullEvidenceHash, mismatch.checkpointEvidenceHash);
assert.equal(mismatch.comparison.differencePath, '$.evidence.edited.workerPayload[0]');
assert.equal(mismatch.comparison.differenceReason, 'value');
assert.notEqual(mismatch.semanticFingerprint, equivalent.semanticFingerprint);

const fullOnly = await compactMinimizerCheckpointObservationV1(fullOnlyShadow(candidateB), candidateB);
assert.equal(fullOnly.status, 'CHECKPOINT_ORACLE_FULL_ONLY');
assert.equal(fullOnly.reason, 'checkpoint-incompatible');
assert.equal(fullOnly.checkpointAttempted, false);
assert.equal(fullOnly.checkpointDecisionHash, null);
assert.equal(fullOnly.checkpointEvidenceHash, null);

const sourceRecording = Object.freeze({
  hash: 'sha256:source',
  gameHash: 'sha256:game',
  gameBytes: 17295,
  editConfigHash: 'sha256:edit',
  finalTick: 12,
  events: [{ tick: 2 }],
  random: [{ tick: 2 }],
  releaseTicks: [1, 3, 6, 8, 12],
});
const shadowState = Object.freeze({
  status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
  selection: Object.freeze({ desiredCheckpointTick: 6, pauseBeforeTick: 6, checkpointTick: 5 }),
  checkpoint: Object.freeze({ hash: 'sha256:checkpoint', logicalTick: 5 }),
});

const stage1 = await createMinimizerCheckpointStageEvidenceV1({
  stage: 'phase-1e',
  sourceRecording,
  targetDivergence: { tick: 12 },
  shadowState,
  observations: [equivalent, fullOnly],
  outcome: { status: 'MINIMIZED', attempts: 2 },
});
const stage2 = await createMinimizerCheckpointStageEvidenceV1({
  stage: 'phase-1e',
  sourceRecording,
  targetDivergence: { tick: 12 },
  shadowState,
  observations: [mismatch],
  outcome: { status: 'MINIMIZED', attempts: 1 },
});
assert.equal(stage1.stageKey, stage2.stageKey, 'Repeated execution of the same stage/checkpoint must share a population key.');
assert.notEqual(stage1.hash, stage2.hash, 'Different observed outcomes must produce different execution hashes.');

const report = await createMinimizerCheckpointEvidenceReportV1([stage1, stage2]);
assert.equal(report.schema, MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA);
assert.equal(report.policy, 'full-replay-authoritative');
assert.equal(report.policyFrozen, false);
assert.equal(report.policyDecision, 'EVIDENCE_ONLY');
assert.equal(report.population.stageExecutions, 2);
assert.equal(report.population.totalObservations, 3);
assert.equal(report.population.compactionFailures, 0);
assert.equal(report.population.uniqueSamples, 2);
assert.equal(report.population.duplicateObservations, 1);
assert.equal(report.population.repeatedSamples, 1);
assert.equal(report.population.inconsistentSamples, 1);
assert.equal(report.population.equivalent, 1);
assert.equal(report.population.fullOnly, 1);
assert.equal(report.population.mismatch, 1);
assert.equal(report.population.checkpointAttempts, 2);
assert.equal(report.population.trustedCheckpoints, 1);
assert.equal(report.population.totalSavedTicks, 5);
assert.equal(report.population.equivalentRateAmongAttempts, 0.5);
assert.equal(report.population.mismatchRateAmongAttempts, 0.5);

const failureStage = await createMinimizerCheckpointStageEvidenceV1({
  stage: 'phase-1f',
  sourceRecording,
  targetDivergence: { tick: 12 },
  shadowState,
  observations: [],
  collectionErrorCandidateHashes: ['sha256:candidate-c'],
  outcome: { status: 'PARTIAL', attempts: 1 },
});
assert.equal(failureStage.collection.compactionFailures, 1);
assert.deepEqual(failureStage.collection.failedCandidateHashes, ['sha256:candidate-c']);
const failureReport = await createMinimizerCheckpointEvidenceReportV1([failureStage]);
assert.equal(failureReport.population.totalObservations, 0);
assert.equal(failureReport.population.compactionFailures, 1);

const reportAgain = await createMinimizerCheckpointEvidenceReportV1([stage1, stage2]);
assert.equal(report.hash, reportAgain.hash, 'Evidence report hashing must be deterministic.');
assert.match(report.hash, /^sha256:[0-9a-f]{64}$/);
assert.equal(await hashCanonicalJsonV1({ b: 2, a: 1 }), await hashCanonicalJsonV1({ a: 1, b: 2 }));
const serialized = serializeMinimizerCheckpointEvidenceReportV1(report);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('\"workerPayload\": ['), false, 'Exported evidence must not retain raw hidden worker payload arrays.');
assert.equal(serialized.includes('EVIDENCE_ONLY'), true);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(
  (phase1dSource.match(/compactMinimizerCheckpointObservationV1/g) ?? []).length,
  3,
  'Phase -1I.4 expects one import plus exactly two compact-observation call sites.',
);
assert.equal(
  (phase1dSource.match(/recordShadowEvidenceStage/g) ?? []).length,
  3,
  'Phase -1I.4 expects one ledger helper plus exactly two recording-only stage call sites.',
);
assert.equal(phase1dSource.includes('shadowResults.push(shadow)'), false, 'Raw oracle results must not be retained across minimizer candidates.');
assert.equal((phase1dSource.match(/shadowResults\.push\(observation\)/g) ?? []).length, 2);
assert.equal(phase1dSource.includes('certify-export-shadow-evidence-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointShadowEvidenceReport'), true);
assert.equal((phase1dSource.match(/shadowEvidenceErrors\.push/g) ?? []).length, 2, 'Compaction failures must be recorded without blocking the authoritative result.');
assert.equal(phase1dSource.includes('__kq1agiCheckpointShadowEvidenceReportError'), true);
const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf("replayButton.addEventListener", editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('compactMinimizerCheckpointObservationV1'), false, 'Phase -1G remains outside recording-only checkpoint evidence collection.');
assert.equal(editSection.includes('recordShadowEvidenceStage'), false, 'Phase -1G remains full-only and must not enter the Phase -1I.4 population.');

console.log('minimizer checkpoint evidence tests: PASS');
