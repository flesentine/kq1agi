import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
} from './certification-minimizer-checkpoint-provenance-census.mjs';

const COVERAGE_SCHEMA = 'kq1agi-minimizer-checkpoint-provenance-cohort-coverage-v1';
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
    [...new Set(values.filter(value => Number.isSafeInteger(value) && value >= 0))]
      .sort(numericCompare),
  );
}

async function stageCanonicalDigest(stage) {
  return hashCanonicalJsonV1(stage);
}

async function buildStageIndex(packages) {
  const stages = new Map();
  for (const item of packages ?? []) {
    for (const stage of item?.evidenceReport?.stages ?? []) {
      const stageHash = String(stage?.hash ?? '');
      if (!stageHash) continue;
      const digest = await stageCanonicalDigest(stage);
      const existing = stages.get(stageHash);
      if (existing && existing.digest !== digest) {
        throw new Error(`Conflicting stage content for deterministic stage hash ${stageHash}.`);
      }
      if (!existing) stages.set(stageHash, { stage, digest });
    }
  }
  return stages;
}

async function cohortKey(stage) {
  return hashCanonicalJsonV1({
    gameHash: String(stage?.source?.gameHash ?? ''),
    editConfigHash: String(stage?.source?.editConfigHash ?? ''),
  });
}

function compactStagePopulation(stagePopulation, stage) {
  return Object.freeze({
    stageHash: stagePopulation.stageHash,
    stage: String(stage?.stage ?? ''),
    sourceRecordingHash: String(stage?.source?.recordingHash ?? ''),
    targetTick: Number(stage?.target?.tick),
    checkpointStatus: String(stage?.checkpoint?.status ?? ''),
    checkpointReason: stage?.checkpoint?.reason == null ? null : String(stage.checkpoint.reason),
    checkpointTick: stage?.checkpoint?.logicalTick == null
      ? null
      : Number(stage.checkpoint.logicalTick),
    checkpointHash: stage?.checkpoint?.hash == null ? null : String(stage.checkpoint.hash),
    toolObservedEvents: stagePopulation.eventCount,
    collectionRunCount: stagePopulation.collectionRunCount,
    collectionRunIds: stagePopulation.collectionRunIds,
  });
}

function cohortFlags(cohort) {
  return Object.freeze({
    missingPhase1E: cohort.phaseEventCounts['phase-1e'] === 0,
    missingPhase1F: cohort.phaseEventCounts['phase-1f'] === 0,
    singleCollectionRun: cohort.collectionRunCount === 1,
    singleDeterministicStage: cohort.distinctStageHashes === 1,
    noCrossRunStageRepeat: cohort.crossRunRepeatedStageHashes === 0,
    singleSourceRecording: cohort.sourceRecordingHashes.length === 1,
    singleTargetTick: cohort.targetTicks.length === 1,
  });
}

/**
 * Join the canonical Phase -1I.10 provenance census back to exact GAMEFILES +
 * EditConfig stage identity. This is descriptive provenance-backed breadth only.
 */
export async function createMinimizerCheckpointProvenanceCohortCoverageV1(packages = []) {
  const census = await createMinimizerCheckpointProvenanceCensusV1(packages);
  const stageIndex = await buildStageIndex(packages);
  const groups = new Map();

  for (const population of census.stagePopulations ?? []) {
    const indexed = stageIndex.get(population.stageHash);
    if (!indexed) {
      throw new Error(`Provenance census stage ${population.stageHash} is missing from supplied evidence reports.`);
    }
    const stage = indexed.stage;
    const gameHash = String(stage?.source?.gameHash ?? '');
    const editConfigHash = String(stage?.source?.editConfigHash ?? '');
    if (!gameHash || !editConfigHash) {
      throw new Error('Provenance cohort coverage stage identity is incomplete.');
    }
    const key = await cohortKey(stage);
    let group = groups.get(key);
    if (!group) {
      group = {
        cohortKey: key,
        identity: Object.freeze({ gameHash, editConfigHash }),
        stages: [],
      };
      groups.set(key, group);
    } else if (group.identity.gameHash !== gameHash
        || group.identity.editConfigHash !== editConfigHash) {
      throw new Error('Provenance cohort identity hash collision.');
    }
    group.stages.push(compactStagePopulation(population, stage));
  }

  const cohorts = [];
  const runCohortMembership = new Map();
  for (const group of groups.values()) {
    const stages = group.stages.sort((a, b) => lexicalCompare(a.stageHash, b.stageHash));
    const runIds = sortedUniqueStrings(stages.flatMap(stage => stage.collectionRunIds ?? []));
    for (const runId of runIds) {
      const keys = runCohortMembership.get(runId) ?? new Set();
      keys.add(group.cohortKey);
      runCohortMembership.set(runId, keys);
    }

    const phaseEventCounts = { 'phase-1e': 0, 'phase-1f': 0 };
    const phaseDeterministicStageCounts = { 'phase-1e': 0, 'phase-1f': 0 };
    for (const stage of stages) {
      if (stage.stage === 'phase-1e' || stage.stage === 'phase-1f') {
        phaseEventCounts[stage.stage] += stage.toolObservedEvents;
        phaseDeterministicStageCounts[stage.stage] += 1;
      }
    }

    const base = {
      cohortKey: group.cohortKey,
      identity: group.identity,
      collectionRunCount: runIds.length,
      collectionRunIds: runIds,
      toolObservedCollectionEvents: stages.reduce(
        (sum, stage) => sum + stage.toolObservedEvents,
        0,
      ),
      distinctStageHashes: stages.length,
      crossRunRepeatedStageHashes: stages.filter(stage => stage.collectionRunCount > 1).length,
      maxCollectionRunsPerStage: stages.reduce(
        (max, stage) => Math.max(max, stage.collectionRunCount),
        0,
      ),
      phaseEventCounts: Object.freeze(phaseEventCounts),
      phaseDeterministicStageCounts: Object.freeze(phaseDeterministicStageCounts),
      sourceRecordingHashes: sortedUniqueStrings(stages.map(stage => stage.sourceRecordingHash)),
      targetTicks: sortedUniqueIntegers(stages.map(stage => stage.targetTick)),
      capturedCheckpointTicks: sortedUniqueIntegers(stages.map(stage => stage.checkpointTick)),
      checkpointHashes: sortedUniqueStrings(stages.map(stage => stage.checkpointHash)),
      unavailableCheckpointReasons: sortedUniqueStrings(
        stages.filter(stage => stage.checkpointHash == null).map(stage => stage.checkpointReason),
      ),
      stages: Object.freeze(stages),
    };
    cohorts.push(Object.freeze({ ...base, coverageFlags: cohortFlags(base) }));
  }
  cohorts.sort((a, b) => lexicalCompare(a.cohortKey, b.cohortKey));

  const toolObservedCollectionEvents = cohorts.reduce(
    (sum, cohort) => sum + cohort.toolObservedCollectionEvents,
    0,
  );
  const distinctStageHashes = cohorts.reduce(
    (sum, cohort) => sum + cohort.distinctStageHashes,
    0,
  );
  if (toolObservedCollectionEvents !== census.toolObservedCollectionEvents
      || distinctStageHashes !== census.distinctStageHashes) {
    throw new Error('Provenance cohort coverage population disagrees with Phase -1I.10 census.');
  }

  const crossIdentityCollectionRunIds = Object.freeze(
    [...runCohortMembership.entries()]
      .filter(([, keys]) => keys.size > 1)
      .map(([runId]) => runId)
      .sort(lexicalCompare),
  );

  const unsigned = {
    schema: COVERAGE_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    coverageDecision: 'DESCRIPTIVE_ONLY',
    provenanceDecision: 'COLLECTION_IDENTITY_ONLY',
    provenanceCensusHash: census.hash,
    cohortIdentity: 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH',
    cohortCount: cohorts.length,
    uniqueCollectionRuns: census.uniqueCollectionRuns,
    toolObservedCollectionEvents: census.toolObservedCollectionEvents,
    distinctStageHashes: census.distinctStageHashes,
    crossRunRepeatedStageHashes: census.crossRunRepeatedStageHashes,
    crossIdentityCollectionRuns: crossIdentityCollectionRunIds.length,
    crossIdentityCollectionRunIds,
    cohorts: Object.freeze(cohorts),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumCollectionRunsPerCohort: null,
      minimumCollectionEventsPerCohort: null,
      minimumCrossRunStageRepetitionsPerCohort: null,
      minimumDistinctSourceRecordingsPerCohort: null,
      minimumTargetTickCoveragePerCohort: null,
    }),
    caveats: Object.freeze([
      'PROVENANCE_COVERAGE_IS_DESCRIPTIVE_NOT_SUFFICIENCY',
      'COLLECTION_RUN_IDENTITY_IS_NOT_PHYSICAL_INDEPENDENCE',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointProvenanceCohortCoverageV1(coverage) {
  if (coverage?.schema !== COVERAGE_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(coverage?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.11 provenance cohort coverage artifact is required.');
  }
  return `${JSON.stringify(coverage, null, 2)}\n`;
}

export const MinimizerCheckpointProvenanceCohortCoverageLayout = Object.freeze({
  COVERAGE_SCHEMA,
  POLICY,
});
