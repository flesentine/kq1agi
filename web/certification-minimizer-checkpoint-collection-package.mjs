import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  MinimizerCheckpointProvenanceLayout,
  validateMinimizerCheckpointCollectionProvenanceV1,
} from './certification-minimizer-checkpoint-provenance.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
} from './certification-minimizer-checkpoint-provenance-census.mjs';
import {
  createMinimizerCheckpointProvenanceCoverageMatrixV1,
} from './certification-minimizer-checkpoint-provenance-coverage.mjs';
import {
  createMinimizerCheckpointProvenanceSessionTopologyV1,
} from './certification-minimizer-checkpoint-provenance-session-topology.mjs';

const PACKAGE_SCHEMA = 'kq1agi-minimizer-checkpoint-collection-package-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;
const FORBIDDEN_KEYS = new Set([
  'workerPayload',
  'truthWorkerPayload',
  'editedWorkerPayload',
  'fullRun',
  'acceleratedRun',
]);

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function isSha256(value) {
  return /^sha256:[0-9a-f]{64}$/.test(String(value ?? ''));
}

function rejectForbiddenKeys(value, path = '$') {
  if (Array.isArray(value)) {
    for (let index = 0; index < value.length; index += 1) {
      rejectForbiddenKeys(value[index], `${path}[${index}]`);
    }
    return;
  }
  if (!isObject(value)) return;
  for (const [key, item] of Object.entries(value)) {
    if (FORBIDDEN_KEYS.has(key)) {
      throw new Error(`Collection package contains forbidden raw oracle field at ${path}.${key}.`);
    }
    rejectForbiddenKeys(item, `${path}.${key}`);
  }
}

async function deriveSingletonArtifacts(evidenceReport, provenance) {
  const packages = [Object.freeze({ evidenceReport, provenance })];
  const census = await createMinimizerCheckpointProvenanceCensusV1(packages);
  const matrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1(packages);
  const topology = await createMinimizerCheckpointProvenanceSessionTopologyV1(packages);
  if (matrix.provenanceCensusHash !== census.hash
      || topology.provenanceCensusHash !== census.hash
      || topology.provenanceCoverageMatrixHash !== matrix.hash) {
    throw new Error('Collection package derived artifact hash mismatch.');
  }
  if (census.uniqueCollectionRuns !== 1
      || census.runs.length !== 1
      || census.runs[0].collectionRunId !== provenance.collectionRunId
      || census.runs[0].selectedProvenanceHash !== provenance.hash) {
    throw new Error('Collection package singleton provenance population mismatch.');
  }
  return Object.freeze({ census, matrix, topology });
}

function derivedSummary(derived) {
  const run = derived.topology.runs[0];
  return Object.freeze({
    provenanceCensusHash: derived.census.hash,
    provenanceCoverageMatrixHash: derived.matrix.hash,
    provenanceSessionTopologyHash: derived.topology.hash,
    cohortCount: derived.matrix.cohortCount,
    multiIdentity: run.multiIdentity,
    identityCount: run.identityCount,
    identityCohortKeys: run.identityCohortKeys,
  });
}

/**
 * Archive one live browser collection snapshot as a self-contained Phase -1I.4
 * report + Phase -1I.9 provenance pair. The package does not mint provenance;
 * it only binds and hashes artifacts that already exist.
 */
export async function createMinimizerCheckpointCollectionPackageV1({
  evidenceReport,
  provenance,
} = {}) {
  if (evidenceReport?.schema !== MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
    throw new Error('Collection package requires a Phase -1I.4 evidence report.');
  }
  if (provenance?.schema !== MinimizerCheckpointProvenanceLayout.PROVENANCE_SCHEMA) {
    throw new Error('Collection package requires a Phase -1I.9 provenance sidecar.');
  }
  rejectForbiddenKeys(evidenceReport);
  rejectForbiddenKeys(provenance);

  const validated = await validateMinimizerCheckpointCollectionProvenanceV1(
    provenance,
    evidenceReport,
  );
  if (!validated.valid
      || provenance.evidenceReportHash !== evidenceReport.hash
      || validated.hash !== provenance.hash) {
    throw new Error('Collection package report/provenance binding mismatch.');
  }

  const derived = await deriveSingletonArtifacts(evidenceReport, provenance);
  const summary = derivedSummary(derived);
  const unsigned = {
    schema: PACKAGE_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    packageDecision: 'COLLECTION_ARCHIVE_ONLY',
    collectionRunId: provenance.collectionRunId,
    evidenceReportHash: evidenceReport.hash,
    provenanceHash: provenance.hash,
    eventCount: provenance.eventCount,
    distinctStageHashes: Object.freeze([...(provenance.distinctStageHashes ?? [])]),
    derived: summary,
    evidenceReport,
    provenance,
    caveats: Object.freeze([
      'PACKAGE_EMBEDS_EXISTING_REPORT_AND_PROVENANCE_ONLY',
      'IMPORTING_PACKAGE_DOES_NOT_MINT_COLLECTION_IDENTITY',
      'COLLECTION_RUN_IDENTITY_IS_NOT_PHYSICAL_INDEPENDENCE',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export async function validateMinimizerCheckpointCollectionPackageV1(collectionPackage) {
  if (!isObject(collectionPackage)) {
    throw new Error('Collection package must be an object.');
  }
  rejectForbiddenKeys(collectionPackage);
  if (collectionPackage.schema !== PACKAGE_SCHEMA) {
    throw new Error('Collection package schema mismatch.');
  }
  if (collectionPackage.policy !== POLICY
      || collectionPackage.policyFrozen !== false
      || collectionPackage.policyDecision !== 'EVIDENCE_ONLY'
      || collectionPackage.accelerationAllowed !== false
      || collectionPackage.packageDecision !== 'COLLECTION_ARCHIVE_ONLY') {
    throw new Error('Collection package changes the evidence-only replay policy.');
  }
  if (!isSha256(collectionPackage.hash)) {
    throw new Error('Collection package hash is invalid.');
  }

  const expected = await createMinimizerCheckpointCollectionPackageV1({
    evidenceReport: collectionPackage.evidenceReport,
    provenance: collectionPackage.provenance,
  });
  if (expected.collectionRunId !== collectionPackage.collectionRunId
      || expected.evidenceReportHash !== collectionPackage.evidenceReportHash
      || expected.provenanceHash !== collectionPackage.provenanceHash
      || expected.eventCount !== collectionPackage.eventCount
      || await hashCanonicalJsonV1(expected.distinctStageHashes)
        !== await hashCanonicalJsonV1(collectionPackage.distinctStageHashes)
      || await hashCanonicalJsonV1(expected.derived)
        !== await hashCanonicalJsonV1(collectionPackage.derived)
      || expected.hash !== collectionPackage.hash) {
    throw new Error('Collection package validation mismatch.');
  }
  return Object.freeze({
    valid: true,
    hash: collectionPackage.hash,
    collectionRunId: collectionPackage.collectionRunId,
    evidenceReportHash: collectionPackage.evidenceReportHash,
    provenanceHash: collectionPackage.provenanceHash,
    eventCount: collectionPackage.eventCount,
  });
}

export async function extractMinimizerCheckpointCollectionPackageV1(collectionPackage) {
  await validateMinimizerCheckpointCollectionPackageV1(collectionPackage);
  return Object.freeze({
    evidenceReport: collectionPackage.evidenceReport,
    provenance: collectionPackage.provenance,
  });
}

export function serializeMinimizerCheckpointCollectionPackageV1(collectionPackage) {
  if (collectionPackage?.schema !== PACKAGE_SCHEMA || !isSha256(collectionPackage?.hash)) {
    throw new TypeError('A complete Phase -1I.13 collection package is required.');
  }
  return `${JSON.stringify(collectionPackage, null, 2)}\n`;
}

export const MinimizerCheckpointCollectionPackageLayout = Object.freeze({
  PACKAGE_SCHEMA,
  POLICY,
});
