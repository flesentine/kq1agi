import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
} from './certification-minimizer-checkpoint-provenance-census.mjs';

const MATRIX_SCHEMA = 'kq1agi-minimizer-checkpoint-provenance-coverage-matrix-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;

function lexicalCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

function numericCompare(left, right) {
  return Number(left) - Number(right);
}

function sortedUniqueStrings(values) {
  return Object.freeze(
    [...new Set(values.filter(value => value != null).map(String).filter(Boolean))]
      .sort(lexicalCompare),
  );
}

function sortedUniqueIntegers(values) {
  return Object.freeze(
    [...new Set(
      values.filter(value => Number.isSafeInteger(value) && value >= 0),
    )].sort(numericCompare),
  );
}

function increment(map, key) {
  map.set(key, (map.get(key) ?? 0) + 1);
}

function mapCounts(map) {
  return Object.freeze(
    [...map.entries()]
      .sort((a, b) => lexicalCompare(a[0], b[0]))
      .reduce((out, [key, value]) => {
        out[key] = value;
        return out;
      }, {}),
  );
}

async function cohortKey(stage) {
  const gameHash = String(stage?.gameHash ?? stage?.source?.gameHash ?? '');
  const editConfigHash = String(stage?.editConfigHash ?? stage?.source?.editConfigHash ?? '');
  if (!gameHash || !editConfigHash) {
    throw new Error('Provenance coverage matrix stage identity is missing.');
  }
  return hashCanonicalJsonV1({ gameHash, editConfigHash });
}

function selectedPackageMap(packages) {
  const map = new Map();
  for (const item of packages ?? []) {
    const provenanceHash = String(item?.provenance?.hash ?? '');
    if (!provenanceHash) continue;
    if (!map.has(provenanceHash)) map.set(provenanceHash, item);
  }
  return map;
}

function stageByHash(report) {
  const map = new Map();
  for (const stage of report?.stages ?? []) map.set(String(stage.hash), stage);
  return map;
}

function compactStage(stage) {
  const checkpoint = stage?.checkpoint ?? {};
  return Object.freeze({
    stageHash: String(stage?.hash ?? ''),
    stage: String(stage?.stage ?? ''),
    sourceRecordingHash: String(stage?.source?.recordingHash ?? ''),
    gameHash: String(stage?.source?.gameHash ?? ''),
    editConfigHash: String(stage?.source?.editConfigHash ?? ''),
    targetTick: Number(stage?.target?.tick),
    checkpointStatus: String(checkpoint.status ?? ''),
    checkpointReason: checkpoint.reason == null ? null : String(checkpoint.reason),
    checkpointTick: checkpoint.logicalTick == null ? null : Number(checkpoint.logicalTick),
    checkpointHash: checkpoint.hash == null ? null : String(checkpoint.hash),
  });
}

function descriptorKey(stage) {
  return JSON.stringify(stage);
}

function coverageFlags(base) {
  return Object.freeze({
    missingPhase1E: (base.eventStageCounts['phase-1e'] ?? 0) === 0,
    missingPhase1F: (base.eventStageCounts['phase-1f'] ?? 0) === 0,
    singleCollectionRun: base.collectionRunIds.length === 1,
    singleSourceRecording: base.sourceRecordingHashes.length === 1,
    singleTargetTick: base.targetTicks.length === 1,
    noCapturedCheckpoint: base.capturedCheckpointTicks.length === 0,
    singleCapturedCheckpointTick: base.capturedCheckpointTicks.length === 1,
    noCrossRunRepeatedStage: base.crossRunRepeatedStageHashes.length === 0,
  });
}

/**
 * Join the selected Phase -1I.10 provenance events back to exact Phase -1I.4
 * stage metadata. This describes where live collection identity exists across
 * minimizer stage/source/tick dimensions without changing corpus population.
 */
export async function createMinimizerCheckpointProvenanceCoverageMatrixV1(packages = []) {
  const census = await createMinimizerCheckpointProvenanceCensusV1(packages);
  const packagesByProvenance = selectedPackageMap(packages);
  const stageDescriptorByHash = new Map();
  const eventRecords = [];

  for (const run of census.runs) {
    const item = packagesByProvenance.get(run.selectedProvenanceHash);
    if (!item) {
      throw new Error('Provenance coverage matrix cannot resolve a selected census snapshot.');
    }
    const stages = stageByHash(item.evidenceReport);
    const provenance = item.provenance;
    for (const event of provenance.events ?? []) {
      const rawStage = stages.get(String(event.stageHash));
      if (!rawStage) {
        throw new Error('Provenance coverage matrix event stage is missing from selected report.');
      }
      const stage = compactStage(rawStage);
      const existing = stageDescriptorByHash.get(stage.stageHash);
      if (existing && descriptorKey(existing) !== descriptorKey(stage)) {
        throw new Error('Provenance coverage matrix found inconsistent metadata for one stage hash.');
      }
      stageDescriptorByHash.set(stage.stageHash, stage);
      eventRecords.push(Object.freeze({
        collectionRunId: run.collectionRunId,
        eventHash: String(event.eventHash),
        ordinal: Number(event.ordinal),
        stage,
      }));
    }
  }

  const censusStagePopulation = new Map(
    census.stagePopulations.map(item => [item.stageHash, item]),
  );
  const cohortsByKey = new Map();

  for (const record of eventRecords) {
    const key = await cohortKey(record.stage);
    let cohort = cohortsByKey.get(key);
    if (!cohort) {
      cohort = {
        cohortKey: key,
        gameHash: record.stage.gameHash,
        editConfigHash: record.stage.editConfigHash,
        collectionRunIds: new Set(),
        eventHashes: new Set(),
        stageHashes: new Set(),
        sourceRecordingHashes: new Set(),
        targetTicks: new Set(),
        capturedCheckpointTicks: new Set(),
        checkpointHashes: new Set(),
        unavailableCheckpointReasons: new Set(),
        eventStageCounts: new Map(),
        deterministicStageCounts: new Map(),
        seenStagePhase: new Set(),
        stageEvents: new Map(),
      };
      cohortsByKey.set(key, cohort);
    } else if (cohort.gameHash !== record.stage.gameHash
        || cohort.editConfigHash !== record.stage.editConfigHash) {
      throw new Error('Provenance coverage matrix cohort hash collision.');
    }

    cohort.collectionRunIds.add(record.collectionRunId);
    cohort.eventHashes.add(record.eventHash);
    cohort.stageHashes.add(record.stage.stageHash);
    cohort.sourceRecordingHashes.add(record.stage.sourceRecordingHash);
    if (Number.isSafeInteger(record.stage.targetTick) && record.stage.targetTick >= 0) {
      cohort.targetTicks.add(record.stage.targetTick);
    }
    if (record.stage.checkpointTick != null) cohort.capturedCheckpointTicks.add(record.stage.checkpointTick);
    if (record.stage.checkpointHash != null) cohort.checkpointHashes.add(record.stage.checkpointHash);
    if (record.stage.checkpointHash == null && record.stage.checkpointReason) {
      cohort.unavailableCheckpointReasons.add(record.stage.checkpointReason);
    }
    increment(cohort.eventStageCounts, record.stage.stage);

    const stagePhaseKey = `${record.stage.stageHash}\u0000${record.stage.stage}`;
    if (!cohort.seenStagePhase.has(stagePhaseKey)) {
      cohort.seenStagePhase.add(stagePhaseKey);
      increment(cohort.deterministicStageCounts, record.stage.stage);
    }

    let stageEvent = cohort.stageEvents.get(record.stage.stageHash);
    if (!stageEvent) {
      stageEvent = {
        descriptor: record.stage,
        eventCount: 0,
        collectionRunIds: new Set(),
      };
      cohort.stageEvents.set(record.stage.stageHash, stageEvent);
    }
    stageEvent.eventCount += 1;
    stageEvent.collectionRunIds.add(record.collectionRunId);
  }

  const cohorts = [];
  for (const cohort of cohortsByKey.values()) {
    const stageEvents = Object.freeze(
      [...cohort.stageEvents.entries()]
        .map(([stageHash, item]) => Object.freeze({
          ...item.descriptor,
          stageHash,
          eventCount: item.eventCount,
          collectionRunCount: item.collectionRunIds.size,
          collectionRunIds: Object.freeze([...item.collectionRunIds].sort(lexicalCompare)),
        }))
        .sort((a, b) => lexicalCompare(a.stageHash, b.stageHash)),
    );
    const repeatedStageHashes = Object.freeze(
      stageEvents
        .filter(item => (censusStagePopulation.get(item.stageHash)?.collectionRunCount ?? 0) > 1)
        .map(item => item.stageHash)
        .sort(lexicalCompare),
    );

    const base = {
      cohortKey: cohort.cohortKey,
      identity: Object.freeze({
        gameHash: cohort.gameHash,
        editConfigHash: cohort.editConfigHash,
      }),
      collectionRunIds: Object.freeze([...cohort.collectionRunIds].sort(lexicalCompare)),
      toolObservedCollectionEvents: cohort.eventHashes.size,
      distinctEventHashes: cohort.eventHashes.size,
      distinctStageHashes: cohort.stageHashes.size,
      eventStageCounts: mapCounts(cohort.eventStageCounts),
      deterministicStageCounts: mapCounts(cohort.deterministicStageCounts),
      sourceRecordingHashes: sortedUniqueStrings([...cohort.sourceRecordingHashes]),
      targetTicks: sortedUniqueIntegers([...cohort.targetTicks]),
      capturedCheckpointTicks: sortedUniqueIntegers([...cohort.capturedCheckpointTicks]),
      checkpointHashes: sortedUniqueStrings([...cohort.checkpointHashes]),
      unavailableCheckpointReasons: sortedUniqueStrings([...cohort.unavailableCheckpointReasons]),
      crossRunRepeatedStageHashes: repeatedStageHashes,
      stages: stageEvents,
    };
    cohorts.push(Object.freeze({
      ...base,
      coverageFlags: coverageFlags(base),
    }));
  }
  cohorts.sort((a, b) => lexicalCompare(a.cohortKey, b.cohortKey));

  const flagCounts = {};
  for (const cohort of cohorts) {
    for (const [flag, enabled] of Object.entries(cohort.coverageFlags)) {
      if (enabled) flagCounts[flag] = (flagCounts[flag] ?? 0) + 1;
    }
  }
  const orderedFlagCounts = Object.freeze(
    Object.keys(flagCounts).sort(lexicalCompare).reduce((out, key) => {
      out[key] = flagCounts[key];
      return out;
    }, {}),
  );

  const unsigned = {
    schema: MATRIX_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    matrixDecision: 'DESCRIPTIVE_ONLY',
    provenanceDecision: 'COLLECTION_IDENTITY_ONLY',
    provenanceCensusHash: census.hash,
    cohortIdentity: 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH',
    cohortCount: cohorts.length,
    uniqueCollectionRuns: census.uniqueCollectionRuns,
    toolObservedCollectionEvents: census.toolObservedCollectionEvents,
    distinctStageHashes: census.distinctStageHashes,
    crossRunRepeatedStageHashes: census.crossRunRepeatedStageHashes,
    flagCounts: orderedFlagCounts,
    cohorts: Object.freeze(cohorts),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumCollectionRunsPerCohort: null,
      minimumPhase1EEvents: null,
      minimumPhase1FEvents: null,
      minimumDistinctSourceRecordings: null,
      minimumTargetTickCoverage: null,
      minimumCrossRunStageRepetitions: null,
    }),
    caveats: Object.freeze([
      'PROVENANCE_COVERAGE_IS_DESCRIPTIVE_NOT_SUFFICIENCY',
      'TOOL_OBSERVED_RUN_IDENTITY_IS_NOT_PHYSICAL_INDEPENDENCE',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointProvenanceCoverageMatrixV1(matrix) {
  if (matrix?.schema !== MATRIX_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(matrix?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.11 provenance coverage matrix is required.');
  }
  return `${JSON.stringify(matrix, null, 2)}\n`;
}

export const MinimizerCheckpointProvenanceCoverageLayout = Object.freeze({
  MATRIX_SCHEMA,
  POLICY,
});
