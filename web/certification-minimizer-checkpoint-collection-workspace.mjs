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

  const submittedCount = currentPackages.length + incomingPackages.length;
  if (submittedCount === 0) {
    throw new Error('Collection workspace requires at least one Phase -1I.13 package.');
  }
  if (submittedCount > MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES) {
    throw new Error('Collection workspace exceeds the package safety limit.');
  }

  const uniqueByHash = new Map();
  for (const collectionPackage of [...currentPackages, ...incomingPackages]) {
    if (collectionPackage?.schema !== MinimizerCheckpointCollectionPackageLayout.PACKAGE_SCHEMA) {
      throw new Error('Collection workspace accepts Phase -1I.13 packages only.');
    }
    await validateMinimizerCheckpointCollectionPackageV1(collectionPackage);
    if (!uniqueByHash.has(collectionPackage.hash)) {
      uniqueByHash.set(collectionPackage.hash, collectionPackage);
    }
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

export const MinimizerCheckpointCollectionWorkspaceLayout = Object.freeze({
  MAX_PACKAGES: MinimizerCheckpointCollectionManifestLayout.MAX_PACKAGES,
});
