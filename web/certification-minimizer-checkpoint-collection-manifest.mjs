import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  extractMinimizerCheckpointCollectionPackageV1,
  MinimizerCheckpointCollectionPackageLayout,
  validateMinimizerCheckpointCollectionPackageV1,
} from './certification-minimizer-checkpoint-collection-package.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
  MinimizerCheckpointProvenanceCensusLayout,
} from './certification-minimizer-checkpoint-provenance-census.mjs';
import {
  createMinimizerCheckpointProvenanceCoverageMatrixV1,
} from './certification-minimizer-checkpoint-provenance-coverage.mjs';
import {
  createMinimizerCheckpointProvenanceSessionTopologyV1,
} from './certification-minimizer-checkpoint-provenance-session-topology.mjs';

const MANIFEST_SCHEMA = 'kq1agi-minimizer-checkpoint-collection-manifest-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;

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

function packageSummary(collectionPackage) {
  return Object.freeze({
    packageHash: collectionPackage.hash,
    collectionRunId: collectionPackage.collectionRunId,
    evidenceReportHash: collectionPackage.evidenceReportHash,
    provenanceHash: collectionPackage.provenanceHash,
    eventCount: collectionPackage.eventCount,
    distinctStageHashes: Object.freeze([...(collectionPackage.distinctStageHashes ?? [])]),
    provenanceCensusHash: collectionPackage.derived.provenanceCensusHash,
    provenanceCoverageMatrixHash: collectionPackage.derived.provenanceCoverageMatrixHash,
    provenanceSessionTopologyHash: collectionPackage.derived.provenanceSessionTopologyHash,
    cohortCount: collectionPackage.derived.cohortCount,
    multiIdentity: collectionPackage.derived.multiIdentity,
    identityCount: collectionPackage.derived.identityCount,
    identityCohortKeys: Object.freeze([...(collectionPackage.derived.identityCohortKeys ?? [])]),
  });
}

async function normalizePackages(collectionPackages) {
  if (!Array.isArray(collectionPackages) || collectionPackages.length === 0) {
    throw new Error('Collection manifest requires at least one Phase -1I.13 package.');
  }
  if (collectionPackages.length > MinimizerCheckpointProvenanceCensusLayout.MAX_PACKAGES) {
    throw new Error('Collection manifest exceeds the package safety limit.');
  }

  const uniqueByHash = new Map();
  for (const collectionPackage of collectionPackages) {
    await validateMinimizerCheckpointCollectionPackageV1(collectionPackage);
    if (collectionPackage.schema !== MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA) {
      throw new Error('Collection manifest package schema mismatch.');
    }
    uniqueByHash.set(collectionPackage.hash, collectionPackage);
  }

  return Object.freeze([...uniqueByHash.values()].sort((a, b) => lexicalCompare(a.hash, b.hash)));
}

async function deriveSetArtifacts(packages) {
  const pairs = [];
  for (const collectionPackage of packages) {
    pairs.push(await extractMinimizerCheckpointCollectionPackageV1(collectionPackage));
  }
  const census = await createMinimizerCheckpointProvenanceCensusV1(pairs);
  const matrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1(pairs);
  const topology = await createMinimizerCheckpointProvenanceSessionTopologyV1(pairs);
  if (matrix.provenanceCensusHash !== census.hash
      || topology.provenanceCensusHash !== census.hash
      || topology.provenanceCoverageMatrixHash !== matrix.hash) {
    throw new Error('Collection manifest derived artifact hash mismatch.');
  }
  return Object.freeze({ census, matrix, topology });
}

/**
 * Build a deterministic archive manifest over one or more validated Phase -1I.13
 * collection packages. Exact duplicate package hashes are idempotent. Same-run
 * snapshot reconciliation remains delegated to the already-qualified I.10-I.12
 * provenance chain. This artifact is descriptive/archive-only and never changes
 * Phase -1I.5 evidence counts or replay authority.
 */
export async function createMinimizerCheckpointCollectionManifestV1(collectionPackages) {
  const packages = await normalizePackages(collectionPackages);
  const derived = await deriveSetArtifacts(packages);
  const summaries = Object.freeze(packages.map(packageSummary));
  const collectionRunIds = Object.freeze([...new Set(
    summaries.map(item => item.collectionRunId),
  )].sort(lexicalCompare));
  const unsigned = {
    schema: MANIFEST_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    manifestDecision: 'COLLECTION_SET_ARCHIVE_ONLY',
    packageCount: summaries.length,
    collectionRunCount: collectionRunIds.length,
    collectionRunIds,
    packageHashes: Object.freeze(summaries.map(item => item.packageHash)),
    packages: summaries,
    derived: Object.freeze({
      provenanceCensusHash: derived.census.hash,
      provenanceCoverageMatrixHash: derived.matrix.hash,
      provenanceSessionTopologyHash: derived.topology.hash,
      uniqueCollectionRuns: derived.census.uniqueCollectionRuns,
      toolObservedCollectionEvents: derived.census.toolObservedCollectionEvents,
      distinctStageHashes: derived.census.distinctStageHashes,
      crossRunRepeatedStageHashes: derived.census.crossRunRepeatedStageHashes,
      cohortCount: derived.matrix.cohortCount,
      multiIdentityCollectionRuns: derived.topology.multiIdentityCollectionRuns,
      maxIdentitiesPerRun: derived.topology.maxIdentitiesPerRun,
    }),
    caveats: Object.freeze([
      'MANIFEST_BINDS_EXISTING_I13_PACKAGES_ONLY',
      'EXACT_DUPLICATE_PACKAGE_HASHES_ARE_IDEMPOTENT',
      'SAME_RUN_HISTORY_IS_RECONCILED_BY_PHASE_1I10',
      'COLLECTION_RUN_IDENTITY_IS_NOT_PHYSICAL_INDEPENDENCE',
      'PHASE_1I5_CORPUS_COUNTS_REMAIN_UNCHANGED',
      'NO_EVIDENCE_SUFFICIENCY_THRESHOLD_IS_DEFINED',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export async function validateMinimizerCheckpointCollectionManifestV1(manifest, collectionPackages) {
  if (!isObject(manifest)) {
    throw new Error('Collection manifest must be an object.');
  }
  if (manifest.schema !== MANIFEST_SCHEMA) {
    throw new Error('Collection manifest schema mismatch.');
  }
  if (manifest.policy !== POLICY
      || manifest.policyFrozen !== false
      || manifest.policyDecision !== 'EVIDENCE_ONLY'
      || manifest.accelerationAllowed !== false
      || manifest.manifestDecision !== 'COLLECTION_SET_ARCHIVE_ONLY') {
    throw new Error('Collection manifest changes the evidence-only replay policy.');
  }
  if (!isSha256(manifest.hash)) {
    throw new Error('Collection manifest hash is invalid.');
  }
  const { hash: submittedHash, ...submittedUnsigned } = manifest;
  if (await hashCanonicalJsonV1(submittedUnsigned) !== submittedHash) {
    throw new Error('Collection manifest hash mismatch.');
  }

  const expected = await createMinimizerCheckpointCollectionManifestV1(collectionPackages);
  if (expected.hash !== submittedHash) {
    throw new Error('Collection manifest population mismatch.');
  }
  return Object.freeze({
    valid: true,
    hash: submittedHash,
    packageCount: manifest.packageCount,
    collectionRunCount: manifest.collectionRunCount,
    provenanceCensusHash: manifest.derived.provenanceCensusHash,
    provenanceCoverageMatrixHash: manifest.derived.provenanceCoverageMatrixHash,
    provenanceSessionTopologyHash: manifest.derived.provenanceSessionTopologyHash,
  });
}

export function serializeMinimizerCheckpointCollectionManifestV1(manifest) {
  if (manifest?.schema !== MANIFEST_SCHEMA || !isSha256(manifest?.hash)) {
    throw new TypeError('A complete Phase -1I.14 collection manifest is required.');
  }
  return `${JSON.stringify(manifest, null, 2)}\n`;
}

export const MinimizerCheckpointCollectionManifestLayout = Object.freeze({
  MANIFEST_SCHEMA,
  POLICY,
  MAX_PACKAGES: MinimizerCheckpointProvenanceCensusLayout.MAX_PACKAGES,
});
