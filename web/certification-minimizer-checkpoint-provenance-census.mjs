import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  MinimizerCheckpointProvenanceLayout,
  validateMinimizerCheckpointCollectionProvenanceV1,
} from './certification-minimizer-checkpoint-provenance.mjs';

const CENSUS_SCHEMA = 'kq1agi-minimizer-checkpoint-provenance-census-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;
const MAX_PACKAGES = 4096;

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isSha256(value) {
  return /^sha256:[0-9a-f]{64}$/.test(String(value ?? ''));
}

function lexicalCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

function sameEventPrefix(shorter, longer) {
  const left = shorter?.events ?? [];
  const right = longer?.events ?? [];
  if (left.length > right.length) return false;
  for (let index = 0; index < left.length; index += 1) {
    if (left[index]?.eventHash !== right[index]?.eventHash
        || left[index]?.stageHash !== right[index]?.stageHash
        || left[index]?.ordinal !== right[index]?.ordinal) {
      return false;
    }
  }
  return true;
}

async function validatePackageV1(input) {
  if (!isObject(input)) throw new Error('Provenance census package must be an object.');
  const evidenceReport = input.evidenceReport;
  const provenance = input.provenance;
  if (evidenceReport?.schema !== MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
    throw new Error('Provenance census package requires a Phase -1I.4 evidence report.');
  }
  if (provenance?.schema !== MinimizerCheckpointProvenanceLayout.PROVENANCE_SCHEMA) {
    throw new Error('Provenance census package requires a Phase -1I.9 provenance sidecar.');
  }
  const validated = await validateMinimizerCheckpointCollectionProvenanceV1(
    provenance,
    evidenceReport,
  );
  if (validated.hash !== provenance.hash || provenance.evidenceReportHash !== evidenceReport.hash) {
    throw new Error('Provenance census package report binding mismatch.');
  }
  return Object.freeze({ evidenceReport, provenance });
}

function compactRunSnapshot(provenance, snapshotCount) {
  return Object.freeze({
    collectionRunId: provenance.collectionRunId,
    selectedProvenanceHash: provenance.hash,
    evidenceReportHash: provenance.evidenceReportHash,
    eventCount: provenance.eventCount,
    distinctStageHashes: Object.freeze([...(provenance.distinctStageHashes ?? [])]),
    eventHashes: Object.freeze((provenance.events ?? []).map(event => event.eventHash)),
    snapshotCount,
  });
}

function stagePopulation(runs) {
  const stages = new Map();
  for (const run of runs) {
    const selected = run.selected;
    for (const event of selected.events ?? []) {
      let item = stages.get(event.stageHash);
      if (!item) {
        item = { eventCount: 0, collectionRunIds: new Set() };
        stages.set(event.stageHash, item);
      }
      item.eventCount += 1;
      item.collectionRunIds.add(selected.collectionRunId);
    }
  }
  return Object.freeze(
    [...stages.entries()]
      .map(([stageHash, item]) => Object.freeze({
        stageHash,
        eventCount: item.eventCount,
        collectionRunCount: item.collectionRunIds.size,
        collectionRunIds: Object.freeze([...item.collectionRunIds].sort(lexicalCompare)),
      }))
      .sort((a, b) => lexicalCompare(a.stageHash, b.stageHash)),
  );
}

/**
 * Aggregate validated Phase -1I.9 report+sidecar packages across browser sessions.
 *
 * Duplicate imports are ignored by provenance hash. Multiple snapshots from the
 * same collection run must form one consistent prefix chain; only the longest
 * snapshot contributes events. This is descriptive provenance accounting only.
 */
export async function createMinimizerCheckpointProvenanceCensusV1(packages = []) {
  if (!Array.isArray(packages) || packages.length === 0) {
    throw new Error('Provenance census requires at least one report+sidecar package.');
  }
  if (packages.length > MAX_PACKAGES) {
    throw new Error('Provenance census exceeds the package safety limit.');
  }

  const validatedPackages = [];
  for (const item of packages) validatedPackages.push(await validatePackageV1(item));

  const uniqueByProvenanceHash = new Map();
  let duplicateSnapshots = 0;
  for (const item of validatedPackages) {
    const hash = item.provenance.hash;
    if (uniqueByProvenanceHash.has(hash)) {
      duplicateSnapshots += 1;
      continue;
    }
    uniqueByProvenanceHash.set(hash, item);
  }

  const byRun = new Map();
  for (const item of uniqueByProvenanceHash.values()) {
    const runId = item.provenance.collectionRunId;
    const list = byRun.get(runId) ?? [];
    list.push(item);
    byRun.set(runId, list);
  }

  const runs = [];
  let supersededSnapshots = 0;
  for (const [runId, items] of byRun.entries()) {
    items.sort((a, b) => {
      const countDelta = a.provenance.eventCount - b.provenance.eventCount;
      return countDelta || lexicalCompare(a.provenance.hash, b.provenance.hash);
    });

    for (let index = 1; index < items.length; index += 1) {
      const previous = items[index - 1].provenance;
      const current = items[index].provenance;
      if (previous.eventCount === current.eventCount) {
        throw new Error(`Conflicting provenance snapshots share collection run ${runId} and event count ${current.eventCount}.`);
      }
      if (!sameEventPrefix(previous, current)) {
        throw new Error(`Conflicting provenance history for collection run ${runId}.`);
      }
    }

    const selected = items[items.length - 1].provenance;
    supersededSnapshots += Math.max(0, items.length - 1);
    runs.push(Object.freeze({
      runId,
      selected,
      compact: compactRunSnapshot(selected, items.length),
    }));
  }
  runs.sort((a, b) => lexicalCompare(a.runId, b.runId));

  const stagePopulations = stagePopulation(runs);
  const selectedRuns = Object.freeze(runs.map(run => run.compact));
  const toolObservedCollectionEvents = runs.reduce(
    (sum, run) => sum + Number(run.selected.eventCount || 0),
    0,
  );
  const distinctEventHashes = new Set();
  for (const run of runs) {
    for (const event of run.selected.events ?? []) distinctEventHashes.add(event.eventHash);
  }
  if (distinctEventHashes.size !== toolObservedCollectionEvents) {
    throw new Error('Provenance census event identity collision detected.');
  }

  const crossRunRepeatedStageHashes = stagePopulations.filter(
    item => item.collectionRunCount > 1,
  ).length;
  const maxCollectionRunsPerStage = stagePopulations.reduce(
    (max, item) => Math.max(max, item.collectionRunCount),
    0,
  );

  const unsigned = {
    schema: CENSUS_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    censusDecision: 'DESCRIPTIVE_ONLY',
    provenanceDecision: 'COLLECTION_IDENTITY_ONLY',
    inputPackages: packages.length,
    uniqueProvenanceSnapshots: uniqueByProvenanceHash.size,
    duplicateSnapshots,
    supersededSnapshots,
    uniqueCollectionRuns: selectedRuns.length,
    toolObservedCollectionEvents,
    distinctEventHashes: distinctEventHashes.size,
    distinctStageHashes: stagePopulations.length,
    crossRunRepeatedStageHashes,
    maxCollectionRunsPerStage,
    runs: selectedRuns,
    stagePopulations,
    thresholdPolicy: Object.freeze({
      status: 'UNSET',
      minimumCollectionRuns: null,
      minimumCollectionEvents: null,
      minimumCrossRunStageRepetitions: null,
    }),
    caveats: Object.freeze([
      'CENSUS_COUNTS_TOOL_OBSERVED_COLLECTION_EVENTS_NOT_PHYSICAL_INDEPENDENCE',
      'SAME_RUN_SNAPSHOTS_COUNT_ONLY_LONGEST_CONSISTENT_PREFIX',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export function serializeMinimizerCheckpointProvenanceCensusV1(census) {
  if (census?.schema !== CENSUS_SCHEMA || !isSha256(census?.hash)) {
    throw new TypeError('A complete Phase -1I.10 provenance census is required.');
  }
  return `${JSON.stringify(census, null, 2)}\n`;
}

export const MinimizerCheckpointProvenanceCensusLayout = Object.freeze({
  CENSUS_SCHEMA,
  POLICY,
  MAX_PACKAGES,
});
