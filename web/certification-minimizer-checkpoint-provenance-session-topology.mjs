import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
} from './certification-minimizer-checkpoint-provenance-census.mjs';
import {
  createMinimizerCheckpointProvenanceCoverageMatrixV1,
} from './certification-minimizer-checkpoint-provenance-coverage.mjs';

const TOPOLOGY_SCHEMA = 'kq1agi-minimizer-checkpoint-provenance-session-topology-v1';
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

async function identityKey(stage) {
  const gameHash = String(stage?.source?.gameHash ?? '');
  const editConfigHash = String(stage?.source?.editConfigHash ?? '');
  if (!gameHash || !editConfigHash) {
    throw new Error('Provenance session topology stage identity is missing.');
  }
  return Object.freeze({
    cohortKey: await hashCanonicalJsonV1({ gameHash, editConfigHash }),
    gameHash,
    editConfigHash,
  });
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

function compactIdentity(group) {
  return Object.freeze({
    cohortKey: group.cohortKey,
    identity: Object.freeze({
      gameHash: group.gameHash,
      editConfigHash: group.editConfigHash,
    }),
    toolObservedCollectionEvents: group.eventHashes.size,
    distinctEventHashes: group.eventHashes.size,
    distinctStageHashes: group.stageHashes.size,
    eventStageCounts: mapCounts(group.eventStageCounts),
    sourceRecordingHashes: sortedUniqueStrings([...group.sourceRecordingHashes]),
    targetTicks: sortedUniqueIntegers([...group.targetTicks]),
    stageHashes: Object.freeze([...group.stageHashes].sort(lexicalCompare)),
    eventHashes: Object.freeze([...group.eventHashes].sort(lexicalCompare)),
  });
}

/**
 * Describe which exact GAMEFILES + EditConfig identities each canonical I.10
 * collection run touched. This is browser-session topology only, not a blocker,
 * threshold, or independence claim.
 */
export async function createMinimizerCheckpointProvenanceSessionTopologyV1(packages = []) {
  const census = await createMinimizerCheckpointProvenanceCensusV1(packages);
  const matrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1(packages);
  if (matrix.provenanceCensusHash !== census.hash) {
    throw new Error('Provenance session topology census/matrix mismatch.');
  }

  const packagesByProvenance = selectedPackageMap(packages);
  const runs = [];

  for (const run of census.runs) {
    const item = packagesByProvenance.get(run.selectedProvenanceHash);
    if (!item) {
      throw new Error('Provenance session topology cannot resolve selected census snapshot.');
    }
    const stages = stageByHash(item.evidenceReport);
    const identityGroups = new Map();
    const runEventHashes = new Set();
    const runStageHashes = new Set();

    for (const event of item.provenance.events ?? []) {
      const stage = stages.get(String(event.stageHash));
      if (!stage) {
        throw new Error('Provenance session topology event stage is missing from selected report.');
      }
      const identity = await identityKey(stage);
      let group = identityGroups.get(identity.cohortKey);
      if (!group) {
        group = {
          cohortKey: identity.cohortKey,
          gameHash: identity.gameHash,
          editConfigHash: identity.editConfigHash,
          eventHashes: new Set(),
          stageHashes: new Set(),
          sourceRecordingHashes: new Set(),
          targetTicks: new Set(),
          eventStageCounts: new Map(),
        };
        identityGroups.set(identity.cohortKey, group);
      } else if (group.gameHash !== identity.gameHash
          || group.editConfigHash !== identity.editConfigHash) {
        throw new Error('Provenance session topology identity hash collision.');
      }

      group.eventHashes.add(String(event.eventHash));
      group.stageHashes.add(String(event.stageHash));
      group.sourceRecordingHashes.add(String(stage?.source?.recordingHash ?? ''));
      const targetTick = Number(stage?.target?.tick);
      if (Number.isSafeInteger(targetTick) && targetTick >= 0) group.targetTicks.add(targetTick);
      increment(group.eventStageCounts, String(stage?.stage ?? ''));
      runEventHashes.add(String(event.eventHash));
      runStageHashes.add(String(event.stageHash));
    }

    const identities = Object.freeze(
      [...identityGroups.values()]
        .map(compactIdentity)
        .sort((a, b) => lexicalCompare(a.cohortKey, b.cohortKey)),
    );
    const identityEventTotal = identities.reduce(
      (sum, identity) => sum + identity.toolObservedCollectionEvents,
      0,
    );
    if (identityEventTotal !== run.eventCount
        || runEventHashes.size !== run.eventCount
        || runStageHashes.size !== run.distinctStageHashes.length) {
      throw new Error('Provenance session topology run population disagrees with Phase -1I.10.');
    }

    runs.push(Object.freeze({
      collectionRunId: run.collectionRunId,
      selectedProvenanceHash: run.selectedProvenanceHash,
      evidenceReportHash: run.evidenceReportHash,
      eventCount: run.eventCount,
      distinctStageHashes: runStageHashes.size,
      identityCount: identities.length,
      multiIdentity: identities.length > 1,
      identityCohortKeys: Object.freeze(identities.map(identity => identity.cohortKey)),
      identities,
    }));
  }
  runs.sort((a, b) => lexicalCompare(a.collectionRunId, b.collectionRunId));

  const multiIdentityRuns = Object.freeze(
    runs.filter(run => run.multiIdentity).map(run => run.collectionRunId),
  );
  const maxIdentitiesPerRun = runs.reduce(
    (max, run) => Math.max(max, run.identityCount),
    0,
  );
  const totalEvents = runs.reduce((sum, run) => sum + run.eventCount, 0);
  if (totalEvents !== census.toolObservedCollectionEvents
      || runs.length !== census.uniqueCollectionRuns) {
    throw new Error('Provenance session topology totals disagree with Phase -1I.10.');
  }

  const matrixCohortKeys = new Set(matrix.cohorts.map(cohort => cohort.cohortKey));
  const topologyCohortKeys = new Set(runs.flatMap(run => run.identityCohortKeys));
  if (matrixCohortKeys.size !== topologyCohortKeys.size
      || [...matrixCohortKeys].some(key => !topologyCohortKeys.has(key))) {
    throw new Error('Provenance session topology identities disagree with Phase -1I.11.');
  }

  const unsigned = {
    schema: TOPOLOGY_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    topologyDecision: 'DESCRIPTIVE_ONLY',
    provenanceDecision: 'COLLECTION_IDENTITY_ONLY',
    provenanceCensusHash: census.hash,
    provenanceCoverageMatrixHash: matrix.hash,
    cohortIdentity: 'GAMEFILES_HASH_PLUS_EDITCONFIG_HASH',
    uniqueCollectionRuns: census.uniqueCollectionRuns,
    toolObservedCollectionEvents: census.toolObservedCollectionEvents,
    multiIdentityCollectionRuns: multiIdentityRuns.length,
    multiIdentityCollectionRunIds: multiIdentityRuns,
    maxIdentitiesPerRun,
    runs: Object.freeze(runs),
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      maximumIdentitiesPerRun: null,
      maximumMultiIdentityCollectionRuns: null,
    }),
    caveats: Object.freeze([
      'MULTI_IDENTITY_RUNS_ARE_DESCRIPTIVE_NOT_BLOCKERS',
      'COLLECTION_RUN_IDENTITY_IS_NOT_PHYSICAL_INDEPENDENCE',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointProvenanceSessionTopologyV1(topology) {
  if (topology?.schema !== TOPOLOGY_SCHEMA
      || !/^sha256:[0-9a-f]{64}$/.test(String(topology?.hash ?? ''))) {
    throw new TypeError('A complete Phase -1I.12 provenance session topology is required.');
  }
  return `${JSON.stringify(topology, null, 2)}\n`;
}

export const MinimizerCheckpointProvenanceSessionTopologyLayout = Object.freeze({
  TOPOLOGY_SCHEMA,
  POLICY,
});
