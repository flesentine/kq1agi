import {
  MinimizerCheckpointCollectionPackageLayout,
  validateMinimizerCheckpointCollectionPackageV1,
} from './certification-minimizer-checkpoint-collection-package.mjs';
import {
  createMinimizerCheckpointCollectionManifestV1,
  MinimizerCheckpointCollectionManifestLayout,
} from './certification-minimizer-checkpoint-collection-manifest.mjs';

function lexicalCompare(left, right) {
  const a = String(left);
  const b = String(right);
  return a < b ? -1 : a > b ? 1 : 0;
}

/**
 * Build one transactional candidate for the browser collection-set workspace.
 *
 * Nothing is mutated until the caller chooses to commit the returned packages
 * and manifest. Every submitted I.13 package is fully validated before exact
 * duplicate hashes are collapsed. The resulting I.14 manifest remains the
 * authoritative description of this archive-only workspace population.
 */
export async function updateMinimizerCheckpointCollectionWorkspaceV1({
  currentPackages = [],
  incomingPackages = [],
} = {}) {
  if (!Array.isArray(currentPackages) || !Array.isArray(incomingPackages)) {
    throw new TypeError('Collection workspace package populations must be arrays.');
  }

  if (currentPackages.length === 0 && incomingPackages.length === 0) {
    throw new Error('Collection workspace requires at least one Phase -1I.13 package.');
  }
  if (currentPackages.length > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES) {
    throw new Error('Collection workspace current population exceeds the package safety limit.');
  }
  if (incomingPackages.length > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES) {
    throw new Error('Collection workspace incoming batch exceeds the package safety limit.');
  }

  const uniqueByHash = new Map();
  const validatedReferences = new WeakSet();
  for (const collectionPackage of [...currentPackages, ...incomingPackages]) {
    if (collectionPackage?.schema !== MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA) {
      throw new Error('Collection workspace accepts Phase -1I.13 packages only.');
    }
    if (!validatedReferences.has(collectionPackage)) {
      await validateMinimizerCheckpointCollectionPackageV1(collectionPackage);
      validatedReferences.add(collectionPackage);
    }
    if (!uniqueByHash.has(collectionPackage.hash)) {
      uniqueByHash.set(collectionPackage.hash, collectionPackage);
    }
  }
  if (uniqueByHash.size > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES) {
    throw new Error('Collection workspace exceeds the unique package capacity.');
  }

  const packages = Object.freeze(
    [...uniqueByHash.values()].sort((a, b) => lexicalCompare(a.hash, b.hash)),
  );
  const manifest = await createMinimizerCheckpointCollectionManifestV1(packages);

  return Object.freeze({
    packages,
    manifest,
    packageCount: packages.length,
    packageHashes: Object.freeze(packages.map(collectionPackage => collectionPackage.hash)),
  });
}


function deepFreeze(value, seen = new WeakSet()) {
  if (!value || typeof value !== 'object' || seen.has(value)) return value;
  seen.add(value);
  for (const child of Object.values(value)) {
    deepFreeze(child, seen);
  }
  return Object.freeze(value);
}

function emptyWorkspaceSnapshot() {
  return Object.freeze({
    packages: Object.freeze([]),
    manifest: null,
    packageCount: 0,
    packageHashes: Object.freeze([]),
  });
}

/**
 * Stateful serialized workspace used by the browser.
 *
 * Each commit starts only after the previous commit settles, so concurrent UI
 * imports cannot snapshot the same stale population and overwrite one another.
 * Failed commits leave the last successful snapshot intact and do not poison
 * later queued commits.
 */
export function createMinimizerCheckpointCollectionWorkspaceStoreV1() {
  let committed = emptyWorkspaceSnapshot();
  let queue = Promise.resolve();

  const commit = incomingPackages => {
    const capturedIncoming = Array.isArray(incomingPackages)
      ? incomingPackages.map(collectionPackage => structuredClone(collectionPackage))
      : incomingPackages;
    const operation = queue.then(async () => {
      const candidate = await updateMinimizerCheckpointCollectionWorkspaceV1({
        currentPackages: committed.packages,
        incomingPackages: capturedIncoming,
      });
      for (const collectionPackage of candidate.packages) {
        deepFreeze(collectionPackage);
      }
      committed = candidate;
      return committed;
    });

    queue = operation.catch(() => undefined);
    return operation;
  };

  return Object.freeze({
    commit,
    snapshot: () => committed,
  });
}

export const MinimizerCheckpointCollectionWorkspaceLayout = Object.freeze({
  MAX_PACKAGES: MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES,
  MAX_IMPORT_FILE_BYTES: 16 * 1024 * 1024,
  MAX_IMPORT_BATCH_BYTES: 64 * 1024 * 1024,
});
