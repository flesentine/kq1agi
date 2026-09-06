import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

import {
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
  hashCanonicalJsonV1,
  hashMinimizerCheckpointObservationSemanticV1,
  MinimizerCheckpointEvidenceLayout,
} from '../web/certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointEvidenceCorpusV1,
  MinimizerCheckpointCorpusLayout,
  serializeMinimizerCheckpointEvidenceCorpusV1,
  validateMinimizerCheckpointEvidenceArtifactV1,
  validateMinimizerCheckpointEvidenceCorpusV1,
  validateMinimizerCheckpointEvidenceReportV1,
} from '../web/certification-minimizer-checkpoint-corpus.mjs';

const sha = char => `sha256:${char.repeat(64)}`;
const sourceHash = sha('1');
const gameHash = sha('2');
const editHash = sha('3');
const checkpointHash = sha('4');

async function makeObservation({
  candidateHash,
  sourceRecordingHash = sourceHash,
  checkpointIdentityHash = checkpointHash,
  status = 'CHECKPOINT_ORACLE_EQUIVALENT',
  savedTicks = 5,
  evidenceHash = sha('6'),
  checkpointEvidenceHash = evidenceHash,
} = {}) {
  const attempted = status !== 'CHECKPOINT_ORACLE_FULL_ONLY';
  const equivalent = status === 'CHECKPOINT_ORACLE_EQUIVALENT';
  const mismatch = status === 'CHECKPOINT_ORACLE_MISMATCH';
  const decisionHash = sha('5');
  const observation = {
    schema: MinimizerCheckpointEvidenceLayout.OBSERVATION_SCHEMA,
    candidateRecordingHash: candidateHash,
    status,
    reason: mismatch ? 'evidence' : status === 'CHECKPOINT_ORACLE_FULL_ONLY'
      ? 'checkpoint-incompatible'
      : status,
    checkpointAttempted: attempted,
    checkpointTrusted: equivalent,
    savedTicks: equivalent ? savedTicks : null,
    fullTelemetry: { consumedTicks: 12, replayStartTick: 0 },
    checkpointTelemetry: attempted ? { consumedTicks: 7, replayStartTick: 5 } : null,
    compatibility: {
      checkpointTick: 5,
      sourceRecordingHash,
      candidateRecordingHash: candidateHash,
      checkpointHash: checkpointIdentityHash,
    },
    comparison: equivalent
      ? { category: 'exact', equivalent: true, differencePath: null, differenceReason: null }
      : mismatch
        ? {
          category: 'evidence',
          equivalent: false,
          differencePath: '$.evidence.edited.workerPayload[0]',
          differenceReason: 'value',
        }
        : null,
    authoritativeStatus: 'REPLAY_MATCH',
    authoritativeResultStatus: 'MATCH',
    authoritativeResultTick: 12,
    fullDecisionHash: decisionHash,
    checkpointDecisionHash: attempted ? decisionHash : null,
    fullEvidenceValidation: { valid: true, reason: 'complete' },
    checkpointEvidenceValidation: attempted ? { valid: true, reason: 'complete' } : null,
    fullEvidenceHash: evidenceHash,
    checkpointEvidenceHash: attempted ? checkpointEvidenceHash : null,
  };
  return Object.freeze({
    ...observation,
    semanticFingerprint: await hashMinimizerCheckpointObservationSemanticV1(observation),
  });
}

function sourceRecording(overrides = {}) {
  return Object.freeze({
    hash: sourceHash,
    gameHash,
    gameBytes: 17295,
    editConfigHash: editHash,
    finalTick: 12,
    events: [{ tick: 2 }],
    random: [{ tick: 2 }],
    releaseTicks: [1, 3, 6, 8, 12],
    ...overrides,
  });
}

function shadowState() {
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
    selection: Object.freeze({
      desiredCheckpointTick: 6,
      pauseBeforeTick: 6,
      checkpointTick: 5,
    }),
    checkpoint: Object.freeze({
      hash: checkpointHash,
      logicalTick: 5,
    }),
  });
}

async function makeStage(observation, overrides = {}) {
  return createMinimizerCheckpointStageEvidenceV1({
    stage: overrides.stage ?? 'phase-1e',
    sourceRecording: overrides.sourceRecording ?? sourceRecording(),
    targetDivergence: { tick: 12 },
    shadowState: shadowState(),
    observations: [observation],
    collectionErrorCandidateHashes: overrides.collectionErrorCandidateHashes ?? [],
    outcome: { status: 'MINIMIZED', attempts: 1 },
  });
}

const candidateA = sha('a');
const candidateB = sha('b');
const candidateC = sha('c');
const equivalentA = await makeObservation({ candidateHash: candidateA });
const equivalentB = await makeObservation({ candidateHash: candidateB, savedTicks: 7 });
const mismatchA = await makeObservation({
  candidateHash: candidateA,
  status: 'CHECKPOINT_ORACLE_MISMATCH',
  evidenceHash: sha('6'),
  checkpointEvidenceHash: sha('7'),
});
const fullOnlyC = await makeObservation({
  candidateHash: candidateC,
  status: 'CHECKPOINT_ORACLE_FULL_ONLY',
});

function legacyPhase1I4FingerprintInput(observation) {
  return {
    candidateRecordingHash: observation.candidateRecordingHash,
    status: observation.status,
    reason: observation.reason,
    checkpointAttempted: observation.checkpointAttempted,
    checkpointTrusted: observation.checkpointTrusted,
    savedTicks: observation.savedTicks,
    compatibility: observation.compatibility,
    comparison: observation.comparison,
    authoritativeStatus: observation.authoritativeStatus,
    authoritativeResultStatus: observation.authoritativeResultStatus,
    authoritativeResultTick: observation.authoritativeResultTick,
    fullDecisionHash: observation.fullDecisionHash,
    checkpointDecisionHash: observation.checkpointDecisionHash,
    fullEvidenceHash: observation.fullEvidenceHash,
    checkpointEvidenceHash: observation.checkpointEvidenceHash,
  };
}

assert.equal(
  mismatchA.semanticFingerprint,
  await hashCanonicalJsonV1(legacyPhase1I4FingerprintInput(mismatchA)),
  'Phase -1I.5 must preserve the exact Phase -1I.4 fingerprint for null savedTicks.',
);
assert.equal(
  fullOnlyC.semanticFingerprint,
  await hashCanonicalJsonV1(legacyPhase1I4FingerprintInput(fullOnlyC)),
  'Phase -1I.5 must preserve the exact Phase -1I.4 full-only fingerprint.',
);

const stageEquivalentA = await makeStage(equivalentA);
const stageMismatchA = await makeStage(mismatchA);
const stageEquivalentB = await makeStage(equivalentB, { stage: 'phase-1f' });
const stageFullOnlyC = await makeStage(fullOnlyC, { stage: 'phase-1f' });

assert.equal(stageEquivalentA.stageKey, stageMismatchA.stageKey);
assert.notEqual(stageEquivalentA.hash, stageMismatchA.hash);

const reportEquivalent = await createMinimizerCheckpointEvidenceReportV1([
  stageEquivalentA,
  stageEquivalentB,
]);
const reportOverlap = await createMinimizerCheckpointEvidenceReportV1([
  stageEquivalentA,
  stageMismatchA,
  stageFullOnlyC,
]);

const validatedReport = await validateMinimizerCheckpointEvidenceReportV1(reportEquivalent);
assert.equal(validatedReport.valid, true);
assert.equal(validatedReport.kind, 'report');
assert.equal(validatedReport.hash, reportEquivalent.hash);
assert.equal((await validateMinimizerCheckpointEvidenceArtifactV1(reportEquivalent)).kind, 'report');

const cleanCorpus = await createMinimizerCheckpointEvidenceCorpusV1([reportEquivalent]);
assert.equal(cleanCorpus.schema, MinimizerCheckpointCorpusLayout.CORPUS_SCHEMA);
assert.equal(cleanCorpus.policy, 'full-replay-authoritative');
assert.equal(cleanCorpus.policyFrozen, false);
assert.equal(cleanCorpus.policyDecision, 'EVIDENCE_ONLY');
assert.equal(cleanCorpus.summary.uniqueStageRecords, 2);
assert.equal(cleanCorpus.summary.totalObservations, 2);
assert.equal(cleanCorpus.summary.uniqueSamples, 2);
assert.equal(cleanCorpus.summary.uniqueCheckpointAttemptedSamples, 2);
assert.equal(cleanCorpus.summary.cleanEquivalentSamples, 2);
assert.equal(cleanCorpus.summary.mismatchSamples, 0);
assert.equal(cleanCorpus.summary.inconsistentSamples, 0);
assert.equal(cleanCorpus.summary.savedTicks.count, 2);
assert.equal(cleanCorpus.summary.savedTicks.min, 5);
assert.equal(cleanCorpus.summary.savedTicks.median, 6);
assert.equal(cleanCorpus.summary.savedTicks.p90, 7);
assert.equal(cleanCorpus.summary.savedTicks.max, 7);
assert.equal(cleanCorpus.summary.savedTicks.average, 6);
assert.equal(cleanCorpus.summary.reviewFlags.hasMismatch, false);
assert.equal(cleanCorpus.summary.reviewFlags.hasInconsistentSamples, false);
assert.match(cleanCorpus.hash, /^sha256:[0-9a-f]{64}$/);

const validatedCorpus = await validateMinimizerCheckpointEvidenceCorpusV1(cleanCorpus);
assert.equal(validatedCorpus.valid, true);
assert.equal(validatedCorpus.kind, 'corpus');
assert.equal((await validateMinimizerCheckpointEvidenceArtifactV1(cleanCorpus)).kind, 'corpus');

const combined = await createMinimizerCheckpointEvidenceCorpusV1([
  reportEquivalent,
  reportOverlap,
]);
assert.equal(combined.summary.uniqueStageRecords, 4, 'Overlapping stage evidence record must be deduped by stage hash.');
assert.equal(combined.summary.totalObservations, 4);
assert.equal(combined.summary.uniqueSamples, 3);
assert.equal(combined.summary.duplicateObservations, 1);
assert.equal(combined.summary.repeatedSamples, 1);
assert.equal(combined.summary.inconsistentSamples, 1);
assert.equal(combined.summary.uniqueCheckpointAttemptedSamples, 2);
assert.equal(combined.summary.cleanEquivalentSamples, 1);
assert.equal(combined.summary.mismatchSamples, 1);
assert.equal(combined.summary.fullOnlySamples, 1);
assert.equal(combined.summary.reviewFlags.hasMismatch, true);
assert.equal(combined.summary.reviewFlags.hasInconsistentSamples, true);
assert.equal(combined.summary.savedTicks.count, 1);
assert.equal(combined.summary.savedTicks.min, 7);

const incremental = await createMinimizerCheckpointEvidenceCorpusV1([
  cleanCorpus,
  reportOverlap,
]);
assert.equal(incremental.hash, combined.hash, 'Corpus identity must not depend on report-vs-corpus import path.');
assert.deepEqual(incremental.summary, combined.summary);

const reversed = await createMinimizerCheckpointEvidenceCorpusV1([
  reportOverlap,
  reportEquivalent,
]);
assert.equal(reversed.hash, combined.hash, 'Corpus identity must not depend on import order.');

const duplicateOnly = await createMinimizerCheckpointEvidenceCorpusV1([
  reportEquivalent,
  reportEquivalent,
  cleanCorpus,
]);
assert.equal(duplicateOnly.hash, cleanCorpus.hash, 'Repeated identical reports/corpora must not inflate the corpus.');

const mixedSourceHash = sha('8');
const mixedSourceStage = await makeStage(
  await makeObservation({
    candidateHash: sha('d'),
    sourceRecordingHash: mixedSourceHash,
  }),
  {
    sourceRecording: sourceRecording({
      hash: mixedSourceHash,
      gameHash: sha('9'),
      editConfigHash: sha('0'),
    }),
  },
);
const mixedReport = await createMinimizerCheckpointEvidenceReportV1([mixedSourceStage]);
const mixedCorpus = await createMinimizerCheckpointEvidenceCorpusV1([reportEquivalent, mixedReport]);
assert.equal(mixedCorpus.summary.distinctGameHashes, 2);
assert.equal(mixedCorpus.summary.distinctEditConfigHashes, 2);
assert.equal(mixedCorpus.summary.reviewFlags.mixedGameIdentity, true);
assert.equal(mixedCorpus.summary.reviewFlags.mixedEditConfigIdentity, true);

const unavailableStage = await createMinimizerCheckpointStageEvidenceV1({
  stage: 'phase-1e',
  sourceRecording: sourceRecording(),
  targetDivergence: { tick: 12 },
  shadowState: Object.freeze({
    status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
    reason: 'no-recorded-release',
    selection: Object.freeze({
      status: 'MINIMIZER_SHADOW_NO_BOUNDARY',
      reason: 'no-recorded-release',
      targetTick: 12,
    }),
  }),
  observations: [],
  collectionErrorCandidateHashes: [],
  outcome: { status: 'MINIMIZED', attempts: 1 },
});
const unavailableReport = await createMinimizerCheckpointEvidenceReportV1([unavailableStage]);
await validateMinimizerCheckpointEvidenceReportV1(unavailableReport);
const unavailableCorpus = await createMinimizerCheckpointEvidenceCorpusV1([unavailableReport]);
assert.equal(unavailableCorpus.summary.uniqueStageRecords, 1);
assert.equal(unavailableCorpus.summary.totalObservations, 0);
assert.equal(unavailableCorpus.summary.uniqueSamples, 0);
assert.equal(unavailableCorpus.summary.savedTicks.count, 0);

const failureStage = await makeStage(
  await makeObservation({ candidateHash: sha('e'), status: 'CHECKPOINT_ORACLE_FULL_ONLY' }),
  { collectionErrorCandidateHashes: [sha('f')] },
);
const failureReport = await createMinimizerCheckpointEvidenceReportV1([failureStage]);
const failureCorpus = await createMinimizerCheckpointEvidenceCorpusV1([failureReport]);
assert.equal(failureCorpus.summary.compactionFailures, 1);
assert.equal(failureCorpus.summary.reviewFlags.hasCollectionGaps, true);

const serialized = serializeMinimizerCheckpointEvidenceCorpusV1(combined);
assert.equal(serialized.endsWith('\n'), true);
assert.equal(serialized.includes('"policyFrozen": false'), true);
assert.equal(serialized.includes('"policyDecision": "EVIDENCE_ONLY"'), true);
assert.equal(serialized.includes('"workerPayload": ['), false);

const populationTamper = structuredClone(reportEquivalent);
populationTamper.population.uniqueSamples += 1;
await assert.rejects(
  validateMinimizerCheckpointEvidenceReportV1(populationTamper),
  /population mismatch|hash mismatch/,
);

const badStageKey = structuredClone(stageEquivalentA);
badStageKey.stageKey = sha('f');
{
  const { hash: _oldHash, ...unsigned } = badStageKey;
  badStageKey.hash = await hashCanonicalJsonV1(unsigned);
}
const badStageKeyReport = await createMinimizerCheckpointEvidenceReportV1([badStageKey]);
await assert.rejects(
  validateMinimizerCheckpointEvidenceReportV1(badStageKeyReport),
  /stage key mismatch/,
);

const badFingerprintObservation = Object.freeze({
  ...equivalentA,
  savedTicks: equivalentA.savedTicks + 1,
});
const badFingerprintStage = await makeStage(badFingerprintObservation);
const badFingerprintReport = await createMinimizerCheckpointEvidenceReportV1([badFingerprintStage]);
await assert.rejects(
  validateMinimizerCheckpointEvidenceReportV1(badFingerprintReport),
  /semantic fingerprint mismatch/,
);

const rawPayloadTamper = structuredClone(reportEquivalent);
rawPayloadTamper.stages[0].observations[0].workerPayload = [1, 2, 3];
{
  const stage = rawPayloadTamper.stages[0];
  const { hash: _oldHash, ...unsignedStage } = stage;
  stage.hash = await hashCanonicalJsonV1(unsignedStage);
}
{
  const { hash: _oldHash, ...unsignedReport } = rawPayloadTamper;
  rawPayloadTamper.hash = await hashCanonicalJsonV1(unsignedReport);
}
await assert.rejects(
  validateMinimizerCheckpointEvidenceReportV1(rawPayloadTamper),
  /forbidden raw oracle field/,
);

const corpusTamper = structuredClone(cleanCorpus);
corpusTamper.summary.cleanEquivalentSamples = 999;
await assert.rejects(
  validateMinimizerCheckpointEvidenceCorpusV1(corpusTamper),
  /summary mismatch|hash mismatch/,
);

await assert.rejects(
  createMinimizerCheckpointEvidenceCorpusV1([]),
  /At least one/,
);
await assert.rejects(
  validateMinimizerCheckpointEvidenceArtifactV1({ schema: 'unknown' }),
  /Unsupported/,
);

const phase1dSource = await readFile(new URL('../web/certification-phase1d.mjs', import.meta.url), 'utf8');
assert.equal(phase1dSource.includes('certify-import-evidence-button'), true);
assert.equal(phase1dSource.includes('certify-export-evidence-corpus-button'), true);
assert.equal(phase1dSource.includes('__kq1agiCheckpointEvidenceCorpus'), true);
assert.equal(phase1dSource.includes('importedEvidenceArtifacts.push('), false, 'Raw imported reports must not accumulate after corpus construction.');
assert.equal(
  (phase1dSource.match(/importedEvidenceArtifacts\.splice\(0, importedEvidenceArtifacts\.length,/g) ?? []).length,
  2,
  'Phase -1I.5 must replace imported evidence with the canonical corpus after local rebuilds and imports.',
);
assert.equal((phase1dSource.match(/createMinimizerCheckpointEvidenceCorpusV1/g) ?? []).length, 3);
const editStart = phase1dSource.indexOf('async function startReduceEdits()');
const editEnd = phase1dSource.indexOf("replayButton.addEventListener", editStart);
assert.ok(editStart >= 0 && editEnd > editStart);
const editSection = phase1dSource.slice(editStart, editEnd);
assert.equal(editSection.includes('createMinimizerCheckpointEvidenceCorpusV1'), false);
assert.equal(editSection.includes('validateMinimizerCheckpointEvidenceArtifactV1'), false);

console.log('minimizer checkpoint evidence corpus tests: PASS');
