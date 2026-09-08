import { formatCertificationResult, readImportedGame } from './certification-panel.mjs';
import { captureEditConfigV1, createEditConfigApplicator, EditConfigLayout, hashEditConfigV1 } from './certification-edit-config.mjs';
import { minimizeDivergentPrefix } from './certification-minimizer.mjs';
import { groupReplayInputEventsV1, minimizeInputGroupsV1 } from './certification-input-minimizer.mjs';
import { groupEditConfigV1, minimizeEditConfigV1 } from './certification-edit-minimizer.mjs';
import { ReplayCertificationHost } from './certification-replay-host.mjs';
import { captureCheckpointOracleEvidenceV1 } from './certification-checkpoint-oracle.mjs';
import {
  runMinimizerCheckpointShadowV1,
  selectMinimizerShadowCheckpointBoundaryV1,
  summarizeMinimizerCheckpointShadowV1,
} from './certification-minimizer-checkpoint-shadow.mjs';
import {
  compactMinimizerCheckpointObservationV1,
  createMinimizerCheckpointEvidenceReportV1,
  createMinimizerCheckpointStageEvidenceV1,
  MinimizerCheckpointEvidenceLayout,
  serializeMinimizerCheckpointEvidenceReportV1,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  createMinimizerCheckpointEvidenceCorpusV1,
  serializeMinimizerCheckpointEvidenceCorpusV1,
  validateMinimizerCheckpointEvidenceArtifactV1,
} from './certification-minimizer-checkpoint-corpus.mjs';
import {
  createMinimizerCheckpointEvidenceReviewV1,
  serializeMinimizerCheckpointEvidenceReviewV1,
} from './certification-minimizer-checkpoint-review.mjs';
import {
  createMinimizerCheckpointEvidenceCohortReviewV1,
  serializeMinimizerCheckpointEvidenceCohortReviewV1,
} from './certification-minimizer-checkpoint-cohort-review.mjs';
import {
  createMinimizerCheckpointEvidenceCoverageProfileV1,
  serializeMinimizerCheckpointEvidenceCoverageProfileV1,
} from './certification-minimizer-checkpoint-coverage.mjs';
import {
  createMinimizerCheckpointCollectionEventV1,
  createMinimizerCheckpointCollectionProvenanceV1,
  createMinimizerCheckpointCollectionRunIdV1,
  MinimizerCheckpointProvenanceLayout,
  serializeMinimizerCheckpointCollectionProvenanceV1,
  validateMinimizerCheckpointCollectionProvenanceV1,
} from './certification-minimizer-checkpoint-provenance.mjs';
import {
  createMinimizerCheckpointProvenanceCensusV1,
  serializeMinimizerCheckpointProvenanceCensusV1,
} from './certification-minimizer-checkpoint-provenance-census.mjs';
import {
  createMinimizerCheckpointProvenanceCoverageMatrixV1,
  serializeMinimizerCheckpointProvenanceCoverageMatrixV1,
} from './certification-minimizer-checkpoint-provenance-coverage.mjs';
import {
  createMinimizerCheckpointProvenanceSessionTopologyV1,
  serializeMinimizerCheckpointProvenanceSessionTopologyV1,
} from './certification-minimizer-checkpoint-provenance-session-topology.mjs';
import {
  encodeRandomReplay,
  freezePlayRecordingV1,
  getPlayRecordingStats,
  hashArrayBufferV1,
  runCertificationReplaySession,
} from './certification-recording.mjs';

function shortHash(value) {
  const hash = String(value ?? 'none');
  return hash.startsWith('sha256:') ? `sha256:${hash.slice(7, 19)}` : hash;
}

function editConfigIdentity(config) {
  return `${shortHash(config?.hash)} · ${config?.rooms?.length ?? 0} room(s) · ${config?.visualPins?.length ?? 0} visual pin(s)`;
}

function recordingIdentity(recording) {
  return `${shortHash(recording?.hash)} · ticks 1–${recording?.finalTick ?? 0} · ${recording?.events?.length ?? 0} transport event(s) · ${recording?.random?.length ?? 0} RNG draw(s)`;
}

function minimizationFocusText(focus) {
  if (!focus) return 'No focus data.';
  const eventTicks = (focus.events ?? []).map(event => `${event.tick}:${event.type}`).join(', ') || 'none';
  const randomTicks = (focus.random ?? []).map(draw => `${draw.tick}:${draw.bound}→${draw.value}`).join(', ') || 'none';
  const releaseTicks = (focus.releaseTicks ?? []).join(', ') || 'none';
  return [
    `focus ticks ${focus.startTick}–${focus.endTick}`,
    `transport: ${eventTicks}`,
    `RNG: ${randomTicks}`,
    `releases: ${releaseTicks}`,
  ].join('\n');
}

function inputGroupsText(groups, limit = 12) {
  if (!groups?.length) return 'remaining groups: none';
  const shown = groups.slice(0, limit).map(group =>
    `${group.id} ${group.kind} ticks ${group.startTick}–${group.endTick} seq ${group.startSeq}–${group.endSeq}`);
  if (groups.length > limit) shown.push(`… ${groups.length - limit} more group(s)`);
  return ['remaining groups:', ...shown].join('\n');
}

function editGroupsText(groups, limit = 12) {
  if (!groups?.length) return 'remaining edit groups: none';
  const shown = groups.slice(0, limit).map(group => {
    if (group.kind === 'room-config') {
      return `${group.id} room ${group.room} · ${group.maskLayers?.length ?? 0} configured mask layer(s)`;
    }
    return `${group.id} visual pins · ${group.count ?? 0} record(s)`;
  });
  if (groups.length > limit) shown.push(`… ${groups.length - limit} more group(s)`);
  return ['remaining edit groups:', ...shown].join('\n');
}

function checkpointShadowSummaryText(shadowState, results) {
  if (!shadowState?.checkpoint) {
    const reason = shadowState?.reason ?? shadowState?.selection?.reason ?? 'checkpoint unavailable';
    return `checkpoint shadow: unavailable (${reason}) · full replay remained authoritative`;
  }

  const summary = summarizeMinimizerCheckpointShadowV1(results);
  const reasons = summary.reasons.length
    ? summary.reasons.map(item => `${item.reason}=${item.count}`).join(', ')
    : 'none';
  const average = summary.averageSavedTicks == null
    ? 'n/a'
    : summary.averageSavedTicks.toFixed(1);

  return [
    `checkpoint shadow: source tick ${shadowState.checkpoint.logicalTick} · pause before ${shadowState.selection.pauseBeforeTick} · full replay authoritative`,
    `oracle candidates=${summary.totalCandidates} · equivalent=${summary.equivalent} · full-only=${summary.fullOnly} · mismatch=${summary.mismatch}`,
    `checkpoint attempts=${summary.checkpointAttempts} · trusted=${summary.trustedCheckpoints} · measured saved ticks=${summary.totalSavedTicks} · average=${average}`,
    `oracle reasons: ${reasons}`,
  ].join('\n');
}


function checkpointEvidencePopulationText(report) {
  const population = report?.population;
  if (!population) return 'evidence report: unavailable';
  return [
    `Phase -1I.4 report ${shortHash(report.hash)} · full replay policy unchanged`,
    `population: ${population.totalObservations} observation(s) · ${population.uniqueSamples} unique sample(s) · ${population.duplicateObservations} duplicate observation(s) · compaction failures=${population.compactionFailures}`,
    `consistency: ${population.inconsistentSamples} inconsistent repeated sample(s) · attempts=${population.checkpointAttempts} · trusted=${population.trustedCheckpoints} · mismatches=${population.mismatch}`,
  ].join('\n');
}

function checkpointEvidenceCorpusText(corpus) {
  const summary = corpus?.summary;
  if (!summary) return 'evidence corpus: unavailable';
  const saved = summary.savedTicks?.count
    ? `saved ticks n=${summary.savedTicks.count} · min=${summary.savedTicks.min} · median=${summary.savedTicks.median} · p90=${summary.savedTicks.p90} · max=${summary.savedTicks.max} · avg=${summary.savedTicks.average.toFixed(1)}`
    : 'saved ticks: no clean equivalent samples';
  return [
    `Phase -1I.5 corpus ${shortHash(corpus.hash)} · full replay policy unchanged`,
    `stages=${summary.uniqueStageRecords} · observations=${summary.totalObservations} · unique samples=${summary.uniqueSamples} · duplicate observations=${summary.duplicateObservations}`,
    `attempted unique=${summary.uniqueCheckpointAttemptedSamples} · clean equivalent=${summary.cleanEquivalentSamples} · mismatch samples=${summary.mismatchSamples} · inconsistent samples=${summary.inconsistentSamples} · collection gaps=${summary.compactionFailures}`,
    `identities: game=${summary.distinctGameHashes} · EditConfig=${summary.distinctEditConfigHashes} · source recordings=${summary.distinctSourceRecordings}`,
    saved,
    'policy: EVIDENCE_ONLY · no checkpoint acceleration is enabled',
  ].join('\n');
}

function checkpointEvidenceReviewText(review) {
  if (!review) return 'evidence review: unavailable';
  const blockers = review.blockers?.length ? review.blockers.join(', ') : 'none';
  return [
    `Phase -1I.6 review ${shortHash(review.hash)} · status=${review.reviewStatus}`,
    `blockers: ${blockers}`,
    `review population: attempted unique=${review.evidence.uniqueCheckpointAttemptedSamples} · clean equivalent=${review.evidence.cleanEquivalentSamples} · mismatches=${review.evidence.mismatchSamples} · inconsistent=${review.evidence.inconsistentSamples} · collection gaps=${review.evidence.compactionFailures}`,
    'threshold: UNSET · accelerationAllowed=false · full replay remains mandatory',
  ].join('\n');
}

function checkpointEvidenceCohortReviewText(bundle) {
  if (!bundle) return 'identity cohorts: unavailable';
  const statuses = Object.entries(bundle.statusCounts ?? {})
    .map(([status, count]) => `${status}=${count}`)
    .join(', ') || 'none';
  return [
    `Phase -1I.7 identity cohorts ${shortHash(bundle.hash)} · exact GAMEFILES + EditConfig partition`,
    `cohorts=${bundle.cohortCount} · statuses: ${statuses}`,
    'global Phase -1I.6 review remains separate · threshold UNSET · accelerationAllowed=false',
  ].join('\n');
}

function checkpointEvidenceCoverageText(profile) {
  if (!profile) return 'coverage profile: unavailable';
  const flags = Object.entries(profile.flagCounts ?? {})
    .map(([flag, count]) => `${flag}=${count}`)
    .join(', ') || 'none';
  return [
    `Phase -1I.8 coverage ${shortHash(profile.hash)} · DESCRIPTIVE_ONLY`,
    `cohorts=${profile.cohortCount} · concentration flags: ${flags}`,
    'coverage flags are descriptive, not review blockers · threshold UNSET · accelerationAllowed=false',
  ].join('\n');
}

function checkpointProvenanceCensusText(census) {
  if (!census) return 'provenance census: unavailable';
  return [
    `Phase -1I.10 provenance census ${shortHash(census.hash)} · DESCRIPTIVE_ONLY`,
    `runs=${census.uniqueCollectionRuns} · tool-observed events=${census.toolObservedCollectionEvents} · deterministic stages=${census.distinctStageHashes}`,
    `unique sidecar snapshots=${census.uniqueProvenanceSnapshots} · superseded same-run snapshots=${census.supersededSnapshots} · stages repeated across runs=${census.crossRunRepeatedStageHashes}`,
    'I.5 corpus counts unchanged · threshold UNSET · accelerationAllowed=false',
  ].join('\n');
}

function checkpointProvenanceCoverageText(matrix) {
  if (!matrix) return 'provenance coverage: unavailable';
  const flags = Object.entries(matrix.flagCounts ?? {})
    .map(([flag, count]) => `${flag}=${count}`)
    .join(', ') || 'none';
  return [
    `Phase -1I.11 provenance coverage ${shortHash(matrix.hash)} · DESCRIPTIVE_ONLY`,
    `cohorts=${matrix.cohortCount} · runs=${matrix.uniqueCollectionRuns} · events=${matrix.toolObservedCollectionEvents} · deterministic stages=${matrix.distinctStageHashes}`,
    `coverage flags: ${flags}`,
    'provenance coverage is descriptive · I.5 counts unchanged · threshold UNSET · accelerationAllowed=false',
  ].join('\n');
}

function checkpointProvenanceTopologyText(topology) {
  if (!topology) return 'provenance session topology: unavailable';
  return [
    `Phase -1I.12 session topology ${shortHash(topology.hash)} · DESCRIPTIVE_ONLY`,
    `runs=${topology.uniqueCollectionRuns} · events=${topology.toolObservedCollectionEvents} · multi-identity runs=${topology.multiIdentityCollectionRuns} · max identities/run=${topology.maxIdentitiesPerRun}`,
    'multi-identity sessions are descriptive, not blockers · I.5 counts unchanged · threshold UNSET · accelerationAllowed=false',
  ].join('\n');
}

/**
 * Re-verify the immutable replay identities before Phase -1E derives candidates.
 * The recording hash protects the declared EditConfig hash, but EditConfig's nested
 * arrays are not deep-frozen; hashing the actual config again prevents a later
 * in-memory mutation from being replayed under the old recording identity.
 */
export async function validateFrozenReplayIdentityV1(recording, gameBuffer, editConfig) {
  if (!recording || typeof recording !== 'object') throw new TypeError('A frozen PLAY recording is required.');
  if (!(gameBuffer instanceof ArrayBuffer)) throw new TypeError('A GAMEFILES.DAT ArrayBuffer is required.');

  const expectedGameHash = String(recording.gameHash ?? '');
  const expectedGameBytes = Number(recording.gameBytes);
  const actualGameHash = await hashArrayBufferV1(gameBuffer);
  if (!expectedGameHash
      || !Number.isSafeInteger(expectedGameBytes)
      || expectedGameBytes < 0
      || actualGameHash !== expectedGameHash
      || gameBuffer.byteLength !== expectedGameBytes) {
    throw new Error(`The local GAMEFILES.DAT changed after the divergent replay (expected ${expectedGameHash || 'missing'}/${recording.gameBytes ?? 'missing'} bytes, got ${actualGameHash}/${gameBuffer.byteLength} bytes).`);
  }

  const expectedEditConfigHash = String(recording.editConfigHash ?? '');
  const declaredEditConfigHash = String(editConfig?.hash ?? '');
  const editConfigSchema = String(editConfig?.schema ?? '');
  const actualEditConfigHash = await hashEditConfigV1(editConfig);
  if (!expectedEditConfigHash
      || editConfigSchema !== EditConfigLayout.SCHEMA
      || declaredEditConfigHash !== expectedEditConfigHash
      || actualEditConfigHash !== expectedEditConfigHash) {
    throw new Error(`The frozen EditConfig changed after the divergent replay (recording ${expectedEditConfigHash || 'missing'}, declared ${declaredEditConfigHash || 'missing'}, actual ${actualEditConfigHash}).`);
  }

  return Object.freeze({ gameHash: actualGameHash, editConfigHash: actualEditConfigHash });
}

/**
 * Freeze only at a normal-PLAY worker completion boundary. RecordingRandomDraw and
 * RecordingCycleComplete are FIFO messages from the same worker, so seeing the
 * completion marker for the most recent released cycle means every RNG observation
 * from that cycle has reached the UI journal before we copy it.
 */
export function snapshotReadyPlayJournal(options = {}) {
  const source = options.rawEvents ?? globalThis.__kq1agiPlayRecordingRaw;
  const variableSAB = options.variableSAB ?? globalThis.__kq1agiVariableSAB ?? null;
  const lastCompletedTick = Number(options.lastCompletedTick ?? globalThis.__kq1agiPlayLastCompletedTick ?? 0) | 0;
  const gameDirectory = String(options.gameDirectory ?? globalThis.__kq1agiPlayGameDirectory ?? '');
  const overflowed = options.overflowed ?? !!globalThis.__kq1agiPlayRecordingOverflow;
  const base = { gameDirectory, lastCompletedTick, lastReleaseTick: 0 };
  if (!Array.isArray(source)) return { ready: false, reason: 'no-journal', ...base };
  if (!variableSAB) return { ready: false, reason: 'no-shared-state', ...base };
  if (!gameDirectory) return { ready: false, reason: 'no-game-identity', ...base };

  let vars;
  try {
    vars = new Int32Array(variableSAB);
    if (vars.length <= 517) throw new Error('short shared variable buffer');
  } catch {
    return { ready: false, reason: 'no-shared-state', ...base };
  }

  let inTick;
  try {
    inTick = Atomics.load(vars, 517) | 0;
  } catch {
    return { ready: false, reason: 'no-shared-state', ...base };
  }

  let lastReleaseTick = 0;
  for (const event of source) {
    if (event?.type === 'pulse' && event.released) lastReleaseTick = Math.max(lastReleaseTick, Number(event.tick) | 0);
  }
  if (lastReleaseTick < 1) return { ready: false, reason: 'no-cycle-release', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  if (inTick !== 0) return { ready: false, reason: 'worker-busy', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  if (lastCompletedTick !== lastReleaseTick) {
    return { ready: false, reason: 'worker-events-pending', gameDirectory, inTick, lastCompletedTick, lastReleaseTick };
  }
  return {
    ready: true,
    reason: 'complete',
    gameDirectory,
    inTick,
    lastCompletedTick,
    lastReleaseTick,
    overflowed: !!overflowed,
    rawEvents: source.map(event => ({ ...event })),
  };
}

function boundaryMessage(boundary) {
  if (boundary.reason === 'worker-busy') return 'Normal PLAY is still inside its current interpreter cycle. Try REPLAY PLAY again when the worker is idle.';
  if (boundary.reason === 'worker-events-pending') return `Normal PLAY finished its shared cycle, but its worker observations have not all reached the journal yet (last release ${boundary.lastReleaseTick}, confirmed complete ${boundary.lastCompletedTick}). Try REPLAY PLAY again.`;
  if (boundary.reason === 'no-cycle-release') return 'Normal PLAY has not completed its first interpreter cycle yet.';
  if (boundary.reason === 'no-game-identity') return 'Phase -1D could not identify the game currently running in normal PLAY. Reload before reproducing the event again.';
  return 'The normal PLAY shared state is not ready for an authoritative replay snapshot yet.';
}

function contractMissText(summary, recording, editConfig) {
  const result = summary.result ?? {};
  const identity = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}`;
  if (result.reason === 'random-stream-consumption') {
    return `${identity}\n\nThe replay did not consume the complete recorded RNG stream (expected ${result.expectedRandomDraws}, ORIGINAL ${result.truthRandomDraws}, EDITED ${result.editedRandomDraws}). This is a reproduction-contract failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
  }
  return `${identity}\n\nThe frozen PLAY transport contract could not be reproduced (${result.reason ?? 'unknown-contract'} at logical tick ${result.tick ?? '?'}). This is a reproduction-contract failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
}

function installPhase1D() {
  const panel = document.getElementById('certify-panel');
  const replayButton = document.getElementById('certify-replay-button');
  const recordingStatus = document.getElementById('certify-recording');
  const runButton = document.getElementById('certify-run-button');
  const refreshButton = document.getElementById('certify-refresh-button');
  const stopButton = document.getElementById('certify-stop-button');
  const gameSelect = document.getElementById('certify-game-select');
  const barrierInput = document.getElementById('certify-barrier-count');
  const status = document.getElementById('certify-status');
  const progress = document.getElementById('certify-progress');
  const detail = document.getElementById('certify-detail');
  if (!panel || !replayButton || !recordingStatus || !runButton || !stopButton || !gameSelect || !status || !progress || !detail) return;

  let minimizeButton = document.getElementById('certify-minimize-button');
  if (!minimizeButton) {
    minimizeButton = document.createElement('button');
    minimizeButton.id = 'certify-minimize-button';
    minimizeButton.type = 'button';
    minimizeButton.textContent = 'MINIMIZE';
    minimizeButton.title = 'Shrink the last divergent PLAY replay to the shortest reproducing prefix';
    minimizeButton.disabled = true;
    replayButton.insertAdjacentElement('afterend', minimizeButton);
  }

  let reduceInputsButton = document.getElementById('certify-reduce-inputs-button');
  if (!reduceInputsButton) {
    reduceInputsButton = document.createElement('button');
    reduceInputsButton.id = 'certify-reduce-inputs-button';
    reduceInputsButton.type = 'button';
    reduceInputsButton.textContent = 'REDUCE INPUTS';
    reduceInputsButton.title = 'Remove dependency-safe keyboard/mouse groups while preserving the exact divergence';
    reduceInputsButton.disabled = true;
    minimizeButton.insertAdjacentElement('afterend', reduceInputsButton);
  }

  let reduceEditsButton = document.getElementById('certify-reduce-edits-button');
  if (!reduceEditsButton) {
    reduceEditsButton = document.createElement('button');
    reduceEditsButton.id = 'certify-reduce-edits-button';
    reduceEditsButton.type = 'button';
    reduceEditsButton.textContent = 'REDUCE EDITS';
    reduceEditsButton.title = 'Remove whole room EditConfig groups and visual pins while preserving the exact divergence';
    reduceEditsButton.disabled = true;
    reduceInputsButton.insertAdjacentElement('afterend', reduceEditsButton);
  }

  let exportShadowEvidenceButton = document.getElementById('certify-export-shadow-evidence-button');
  if (!exportShadowEvidenceButton) {
    exportShadowEvidenceButton = document.createElement('button');
    exportShadowEvidenceButton.id = 'certify-export-shadow-evidence-button';
    exportShadowEvidenceButton.type = 'button';
    exportShadowEvidenceButton.textContent = 'EXPORT EVIDENCE';
    exportShadowEvidenceButton.title = 'Download the compact Phase -1I.4 checkpoint shadow evidence ledger';
    exportShadowEvidenceButton.disabled = true;
    reduceEditsButton.insertAdjacentElement('afterend', exportShadowEvidenceButton);
  }

  let importEvidenceButton = document.getElementById('certify-import-evidence-button');
  if (!importEvidenceButton) {
    importEvidenceButton = document.createElement('button');
    importEvidenceButton.id = 'certify-import-evidence-button';
    importEvidenceButton.type = 'button';
    importEvidenceButton.textContent = 'IMPORT EVIDENCE';
    importEvidenceButton.title = 'Import one or more hash-validated Phase -1I.4 reports / Phase -1I.5 corpora';
    exportShadowEvidenceButton.insertAdjacentElement('afterend', importEvidenceButton);
  }

  let exportEvidenceCorpusButton = document.getElementById('certify-export-evidence-corpus-button');
  if (!exportEvidenceCorpusButton) {
    exportEvidenceCorpusButton = document.createElement('button');
    exportEvidenceCorpusButton.id = 'certify-export-evidence-corpus-button';
    exportEvidenceCorpusButton.type = 'button';
    exportEvidenceCorpusButton.textContent = 'EXPORT CORPUS';
    exportEvidenceCorpusButton.title = 'Download the deduplicated Phase -1I.5 cross-session evidence corpus';
    exportEvidenceCorpusButton.disabled = true;
    importEvidenceButton.insertAdjacentElement('afterend', exportEvidenceCorpusButton);
  }

  let exportEvidenceReviewButton = document.getElementById('certify-export-evidence-review-button');
  if (!exportEvidenceReviewButton) {
    exportEvidenceReviewButton = document.createElement('button');
    exportEvidenceReviewButton.id = 'certify-export-evidence-review-button';
    exportEvidenceReviewButton.type = 'button';
    exportEvidenceReviewButton.textContent = 'EXPORT REVIEW';
    exportEvidenceReviewButton.title = 'Download the deterministic Phase -1I.6 evidence review record';
    exportEvidenceReviewButton.disabled = true;
    exportEvidenceCorpusButton.insertAdjacentElement('afterend', exportEvidenceReviewButton);
  }

  let exportEvidenceCohortsButton = document.getElementById('certify-export-evidence-cohorts-button');
  if (!exportEvidenceCohortsButton) {
    exportEvidenceCohortsButton = document.createElement('button');
    exportEvidenceCohortsButton.id = 'certify-export-evidence-cohorts-button';
    exportEvidenceCohortsButton.type = 'button';
    exportEvidenceCohortsButton.textContent = 'EXPORT COHORTS';
    exportEvidenceCohortsButton.title = 'Download the Phase -1I.7 GAMEFILES + EditConfig identity-scoped review bundle';
    exportEvidenceCohortsButton.disabled = true;
    exportEvidenceReviewButton.insertAdjacentElement('afterend', exportEvidenceCohortsButton);
  }

  let exportEvidenceCoverageButton = document.getElementById('certify-export-evidence-coverage-button');
  if (!exportEvidenceCoverageButton) {
    exportEvidenceCoverageButton = document.createElement('button');
    exportEvidenceCoverageButton.id = 'certify-export-evidence-coverage-button';
    exportEvidenceCoverageButton.type = 'button';
    exportEvidenceCoverageButton.textContent = 'EXPORT COVERAGE';
    exportEvidenceCoverageButton.title = 'Download the descriptive Phase -1I.8 evidence coverage profile';
    exportEvidenceCoverageButton.disabled = true;
    exportEvidenceCohortsButton.insertAdjacentElement('afterend', exportEvidenceCoverageButton);
  }

  let exportCollectionProvenanceButton = document.getElementById('certify-export-collection-provenance-button');
  if (!exportCollectionProvenanceButton) {
    exportCollectionProvenanceButton = document.createElement('button');
    exportCollectionProvenanceButton.id = 'certify-export-collection-provenance-button';
    exportCollectionProvenanceButton.type = 'button';
    exportCollectionProvenanceButton.textContent = 'EXPORT PROVENANCE';
    exportCollectionProvenanceButton.title = 'Download Phase -1I.9 provenance for live evidence collected in this browser session';
    exportCollectionProvenanceButton.disabled = true;
    exportEvidenceCoverageButton.insertAdjacentElement('afterend', exportCollectionProvenanceButton);
  }

  let importProvenanceButton = document.getElementById('certify-import-provenance-button');
  if (!importProvenanceButton) {
    importProvenanceButton = document.createElement('button');
    importProvenanceButton.id = 'certify-import-provenance-button';
    importProvenanceButton.type = 'button';
    importProvenanceButton.textContent = 'IMPORT PROVENANCE';
    importProvenanceButton.title = 'Import Phase -1I.4 reports plus Phase -1I.9 provenance sidecars for cross-session census';
    exportCollectionProvenanceButton.insertAdjacentElement('afterend', importProvenanceButton);
  }

  let exportProvenanceCensusButton = document.getElementById('certify-export-provenance-census-button');
  if (!exportProvenanceCensusButton) {
    exportProvenanceCensusButton = document.createElement('button');
    exportProvenanceCensusButton.id = 'certify-export-provenance-census-button';
    exportProvenanceCensusButton.type = 'button';
    exportProvenanceCensusButton.textContent = 'EXPORT CENSUS';
    exportProvenanceCensusButton.title = 'Download the Phase -1I.10 cross-session provenance census';
    exportProvenanceCensusButton.disabled = true;
    importProvenanceButton.insertAdjacentElement('afterend', exportProvenanceCensusButton);
  }

  let exportProvenanceCoverageButton = document.getElementById('certify-export-provenance-coverage-button');
  if (!exportProvenanceCoverageButton) {
    exportProvenanceCoverageButton = document.createElement('button');
    exportProvenanceCoverageButton.id = 'certify-export-provenance-coverage-button';
    exportProvenanceCoverageButton.type = 'button';
    exportProvenanceCoverageButton.textContent = 'EXPORT PROV COVERAGE';
    exportProvenanceCoverageButton.title = 'Download the Phase -1I.11 provenance-backed coverage matrix';
    exportProvenanceCoverageButton.disabled = true;
    exportProvenanceCensusButton.insertAdjacentElement('afterend', exportProvenanceCoverageButton);
  }

  let exportProvenanceTopologyButton = document.getElementById('certify-export-provenance-topology-button');
  if (!exportProvenanceTopologyButton) {
    exportProvenanceTopologyButton = document.createElement('button');
    exportProvenanceTopologyButton.id = 'certify-export-provenance-topology-button';
    exportProvenanceTopologyButton.type = 'button';
    exportProvenanceTopologyButton.textContent = 'EXPORT RUN TOPOLOGY';
    exportProvenanceTopologyButton.title = 'Download the Phase -1I.12 run-centric exact-identity session topology';
    exportProvenanceTopologyButton.disabled = true;
    exportProvenanceCoverageButton.insertAdjacentElement('afterend', exportProvenanceTopologyButton);
  }

  let importProvenanceInput = document.getElementById('certify-import-provenance-input');
  if (!importProvenanceInput) {
    importProvenanceInput = document.createElement('input');
    importProvenanceInput.id = 'certify-import-provenance-input';
    importProvenanceInput.type = 'file';
    importProvenanceInput.accept = '.json,application/json';
    importProvenanceInput.multiple = true;
    importProvenanceInput.hidden = true;
    exportProvenanceCensusButton.insertAdjacentElement('afterend', importProvenanceInput);
  }

  let importEvidenceInput = document.getElementById('certify-import-evidence-input');
  if (!importEvidenceInput) {
    importEvidenceInput = document.createElement('input');
    importEvidenceInput.id = 'certify-import-evidence-input';
    importEvidenceInput.type = 'file';
    importEvidenceInput.accept = '.json,application/json';
    importEvidenceInput.multiple = true;
    importEvidenceInput.hidden = true;
    exportEvidenceCorpusButton.insertAdjacentElement('afterend', importEvidenceInput);
  }

  let replayHost = null;
  let replayRunning = false;
  let stopRequested = false;
  let lastDivergenceContext = null;
  let lastMinimizedContext = null;
  let lastInputReducedContext = null;
  const shadowEvidenceStages = [];
  const importedEvidenceArtifacts = [];
  let latestShadowEvidenceReport = null;
  let latestEvidenceCorpus = null;
  let latestEvidenceReview = null;
  let latestEvidenceCohortReview = null;
  let latestEvidenceCoverageProfile = null;
  const collectionProvenanceEvents = [];
  const importedProvenancePackages = [];
  let collectionRunId = null;
  let latestCollectionProvenance = null;
  let latestProvenanceCensus = null;
  let latestProvenanceCoverageMatrix = null;
  let latestProvenanceSessionTopology = null;
  try {
    collectionRunId = createMinimizerCheckpointCollectionRunIdV1();
    globalThis.__kq1agiCheckpointCollectionRunId = collectionRunId;
    globalThis.__kq1agiCheckpointCollectionProvenanceError = null;
  } catch (error) {
    globalThis.__kq1agiCheckpointCollectionRunId = null;
    globalThis.__kq1agiCheckpointCollectionProvenanceError = String(error?.message ?? error);
  }

  const setStatus = (text, state) => {
    status.textContent = text;
    status.dataset.state = state;
  };

  const invalidateMinimization = () => {
    lastDivergenceContext = null;
    lastMinimizedContext = null;
    lastInputReducedContext = null;
    minimizeButton.disabled = true;
    reduceInputsButton.disabled = true;
    reduceEditsButton.disabled = true;
  };

  const setReplayRunning = value => {
    replayRunning = value;
    replayButton.disabled = value;
    minimizeButton.disabled = value || !lastDivergenceContext;
    reduceInputsButton.disabled = value || !lastMinimizedContext;
    reduceEditsButton.disabled = value || !lastInputReducedContext;
    exportShadowEvidenceButton.disabled = value || !latestShadowEvidenceReport;
    importEvidenceButton.disabled = value;
    exportEvidenceCorpusButton.disabled = value || !latestEvidenceCorpus;
    exportEvidenceReviewButton.disabled = value || !latestEvidenceReview;
    exportEvidenceCohortsButton.disabled = value || !latestEvidenceCohortReview;
    exportEvidenceCoverageButton.disabled = value || !latestEvidenceCoverageProfile;
    exportCollectionProvenanceButton.disabled = value || !latestCollectionProvenance;
    importProvenanceButton.disabled = value;
    exportProvenanceCensusButton.disabled = value || !latestProvenanceCensus;
    exportProvenanceCoverageButton.disabled = value || !latestProvenanceCoverageMatrix;
    exportProvenanceTopologyButton.disabled = value || !latestProvenanceSessionTopology;
    runButton.disabled = value;
    if (refreshButton) refreshButton.disabled = value;
    gameSelect.disabled = value;
    if (barrierInput) barrierInput.disabled = value;
    stopButton.disabled = !value;
  };

  async function refreshEvidenceReview() {
    if (!latestEvidenceCorpus) {
      latestEvidenceReview = null;
      globalThis.__kq1agiCheckpointEvidenceReview = null;
      exportEvidenceReviewButton.disabled = true;
      return null;
    }
    try {
      latestEvidenceReview = await createMinimizerCheckpointEvidenceReviewV1(latestEvidenceCorpus);
      globalThis.__kq1agiCheckpointEvidenceReview = latestEvidenceReview;
      globalThis.__kq1agiCheckpointEvidenceReviewError = null;
    } catch (error) {
      latestEvidenceReview = null;
      globalThis.__kq1agiCheckpointEvidenceReview = null;
      globalThis.__kq1agiCheckpointEvidenceReviewError = String(error?.message ?? error);
    }
    exportEvidenceReviewButton.disabled = replayRunning || !latestEvidenceReview;
    return latestEvidenceReview;
  }

  async function refreshEvidenceCohortReview() {
    if (!latestEvidenceCorpus) {
      latestEvidenceCohortReview = null;
      globalThis.__kq1agiCheckpointEvidenceCohortReview = null;
      exportEvidenceCohortsButton.disabled = true;
      return null;
    }
    try {
      latestEvidenceCohortReview = await createMinimizerCheckpointEvidenceCohortReviewV1(latestEvidenceCorpus);
      globalThis.__kq1agiCheckpointEvidenceCohortReview = latestEvidenceCohortReview;
      globalThis.__kq1agiCheckpointEvidenceCohortReviewError = null;
    } catch (error) {
      latestEvidenceCohortReview = null;
      globalThis.__kq1agiCheckpointEvidenceCohortReview = null;
      globalThis.__kq1agiCheckpointEvidenceCohortReviewError = String(error?.message ?? error);
    }
    exportEvidenceCohortsButton.disabled = replayRunning || !latestEvidenceCohortReview;
    return latestEvidenceCohortReview;
  }

  async function refreshEvidenceCoverageProfile() {
    if (!latestEvidenceCorpus) {
      latestEvidenceCoverageProfile = null;
      globalThis.__kq1agiCheckpointEvidenceCoverageProfile = null;
      exportEvidenceCoverageButton.disabled = true;
      return null;
    }
    try {
      latestEvidenceCoverageProfile = await createMinimizerCheckpointEvidenceCoverageProfileV1(latestEvidenceCorpus);
      globalThis.__kq1agiCheckpointEvidenceCoverageProfile = latestEvidenceCoverageProfile;
      globalThis.__kq1agiCheckpointEvidenceCoverageProfileError = null;
    } catch (error) {
      latestEvidenceCoverageProfile = null;
      globalThis.__kq1agiCheckpointEvidenceCoverageProfile = null;
      globalThis.__kq1agiCheckpointEvidenceCoverageProfileError = String(error?.message ?? error);
    }
    exportEvidenceCoverageButton.disabled = replayRunning || !latestEvidenceCoverageProfile;
    return latestEvidenceCoverageProfile;
  }

  async function recordLiveCollectionProvenance(stageEvidence) {
    if (!collectionRunId || !latestShadowEvidenceReport) return null;
    try {
      const event = await createMinimizerCheckpointCollectionEventV1({
        collectionRunId,
        ordinal: collectionProvenanceEvents.length,
        stageHash: stageEvidence.hash,
      });
      collectionProvenanceEvents.push(event);
      latestCollectionProvenance = await createMinimizerCheckpointCollectionProvenanceV1({
        collectionRunId,
        evidenceReport: latestShadowEvidenceReport,
        events: collectionProvenanceEvents,
      });
      globalThis.__kq1agiCheckpointCollectionProvenance = latestCollectionProvenance;
      globalThis.__kq1agiCheckpointCollectionProvenanceError = null;
    } catch (error) {
      latestCollectionProvenance = null;
      globalThis.__kq1agiCheckpointCollectionProvenance = null;
      globalThis.__kq1agiCheckpointCollectionProvenanceError = String(error?.message ?? error);
    }
    exportCollectionProvenanceButton.disabled = replayRunning || !latestCollectionProvenance;
    await refreshProvenanceCensus();
    return latestCollectionProvenance;
  }

  async function refreshProvenanceCensus() {
    const packages = [
      ...importedProvenancePackages,
      ...(latestCollectionProvenance && latestShadowEvidenceReport
        ? [{ evidenceReport: latestShadowEvidenceReport, provenance: latestCollectionProvenance }]
        : []),
    ];
    if (!packages.length) {
      latestProvenanceCensus = null;
      latestProvenanceCoverageMatrix = null;
      latestProvenanceSessionTopology = null;
      globalThis.__kq1agiCheckpointProvenanceCensus = null;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrix = null;
      globalThis.__kq1agiCheckpointProvenanceSessionTopology = null;
      exportProvenanceCensusButton.disabled = true;
      exportProvenanceCoverageButton.disabled = true;
      exportProvenanceTopologyButton.disabled = true;
      return null;
    }
    try {
      latestProvenanceCensus = await createMinimizerCheckpointProvenanceCensusV1(packages);
      latestProvenanceCoverageMatrix = await createMinimizerCheckpointProvenanceCoverageMatrixV1(packages);
      latestProvenanceSessionTopology = await createMinimizerCheckpointProvenanceSessionTopologyV1(packages);
      if (latestProvenanceCoverageMatrix.provenanceCensusHash !== latestProvenanceCensus.hash
          || latestProvenanceSessionTopology.provenanceCensusHash !== latestProvenanceCensus.hash
          || latestProvenanceSessionTopology.provenanceCoverageMatrixHash !== latestProvenanceCoverageMatrix.hash) {
        throw new Error('Provenance derived artifact hash mismatch.');
      }
      globalThis.__kq1agiCheckpointProvenanceCensus = latestProvenanceCensus;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrix = latestProvenanceCoverageMatrix;
      globalThis.__kq1agiCheckpointProvenanceSessionTopology = latestProvenanceSessionTopology;
      globalThis.__kq1agiCheckpointProvenanceCensusError = null;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrixError = null;
      globalThis.__kq1agiCheckpointProvenanceSessionTopologyError = null;
    } catch (error) {
      latestProvenanceCensus = null;
      latestProvenanceCoverageMatrix = null;
      latestProvenanceSessionTopology = null;
      globalThis.__kq1agiCheckpointProvenanceCensus = null;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrix = null;
      globalThis.__kq1agiCheckpointProvenanceSessionTopology = null;
      globalThis.__kq1agiCheckpointProvenanceCensusError = String(error?.message ?? error);
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrixError = String(error?.message ?? error);
      globalThis.__kq1agiCheckpointProvenanceSessionTopologyError = String(error?.message ?? error);
    }
    exportProvenanceCensusButton.disabled = replayRunning || !latestProvenanceCensus;
    exportProvenanceCoverageButton.disabled = replayRunning || !latestProvenanceCoverageMatrix;
    exportProvenanceTopologyButton.disabled = replayRunning || !latestProvenanceSessionTopology;
    return latestProvenanceCensus;
  }

  async function recordShadowEvidenceStage(stage, context, shadowState, observations, collectionErrorCandidateHashes, outcome) {
    try {
      const stageEvidence = await createMinimizerCheckpointStageEvidenceV1({
        stage,
        sourceRecording: context.recording,
        targetDivergence: context.firstDivergence,
        shadowState,
        observations,
        collectionErrorCandidateHashes,
        outcome,
      });
      shadowEvidenceStages.push(stageEvidence);
      latestShadowEvidenceReport = await createMinimizerCheckpointEvidenceReportV1(shadowEvidenceStages);
      globalThis.__kq1agiCheckpointShadowEvidenceReport = latestShadowEvidenceReport;
      globalThis.__kq1agiCheckpointShadowEvidenceReportError = null;
      exportShadowEvidenceButton.disabled = replayRunning || !latestShadowEvidenceReport;
      await recordLiveCollectionProvenance(stageEvidence);
      try {
        latestEvidenceCorpus = await createMinimizerCheckpointEvidenceCorpusV1([
          ...importedEvidenceArtifacts,
          latestShadowEvidenceReport,
        ]);
        importedEvidenceArtifacts.splice(0, importedEvidenceArtifacts.length, latestEvidenceCorpus);
        globalThis.__kq1agiCheckpointEvidenceCorpus = latestEvidenceCorpus;
        globalThis.__kq1agiCheckpointEvidenceCorpusError = null;
        await refreshEvidenceReview();
        await refreshEvidenceCohortReview();
        await refreshEvidenceCoverageProfile();
      } catch (corpusError) {
        latestEvidenceCorpus = null;
        latestEvidenceReview = null;
        latestEvidenceCohortReview = null;
        latestEvidenceCoverageProfile = null;
        globalThis.__kq1agiCheckpointEvidenceCorpus = null;
        globalThis.__kq1agiCheckpointEvidenceReview = null;
        globalThis.__kq1agiCheckpointEvidenceCohortReview = null;
        globalThis.__kq1agiCheckpointEvidenceCoverageProfile = null;
        globalThis.__kq1agiCheckpointEvidenceCorpusError = String(corpusError?.message ?? corpusError);
        globalThis.__kq1agiCheckpointEvidenceReviewError = 'Evidence review unavailable because corpus construction failed.';
        globalThis.__kq1agiCheckpointEvidenceCohortReviewError = 'Identity cohort review unavailable because corpus construction failed.';
        globalThis.__kq1agiCheckpointEvidenceCoverageProfileError = 'Coverage profile unavailable because corpus construction failed.';
        exportEvidenceReviewButton.disabled = true;
        exportEvidenceCohortsButton.disabled = true;
        exportEvidenceCoverageButton.disabled = true;
      }
      exportEvidenceCorpusButton.disabled = replayRunning || !latestEvidenceCorpus;
      return latestShadowEvidenceReport;
    } catch (error) {
      globalThis.__kq1agiCheckpointShadowEvidenceReportError = String(error?.message ?? error);
      exportShadowEvidenceButton.disabled = replayRunning || !latestShadowEvidenceReport;
      return null;
    }
  }

  function exportShadowEvidence() {
    if (!latestShadowEvidenceReport) return;
    const body = serializeMinimizerCheckpointEvidenceReportV1(latestShadowEvidenceReport);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-shadow-evidence-${latestShadowEvidenceReport.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportEvidenceCorpus() {
    if (!latestEvidenceCorpus) return;
    const body = serializeMinimizerCheckpointEvidenceCorpusV1(latestEvidenceCorpus);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-evidence-corpus-${latestEvidenceCorpus.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportEvidenceReview() {
    if (!latestEvidenceReview) return;
    const body = serializeMinimizerCheckpointEvidenceReviewV1(latestEvidenceReview);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-evidence-review-${latestEvidenceReview.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportEvidenceCohorts() {
    if (!latestEvidenceCohortReview) return;
    const body = serializeMinimizerCheckpointEvidenceCohortReviewV1(latestEvidenceCohortReview);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-evidence-cohorts-${latestEvidenceCohortReview.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportEvidenceCoverage() {
    if (!latestEvidenceCoverageProfile) return;
    const body = serializeMinimizerCheckpointEvidenceCoverageProfileV1(latestEvidenceCoverageProfile);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-evidence-coverage-${latestEvidenceCoverageProfile.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportCollectionProvenance() {
    if (!latestCollectionProvenance) return;
    const body = serializeMinimizerCheckpointCollectionProvenanceV1(latestCollectionProvenance);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-collection-provenance-${latestCollectionProvenance.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportProvenanceCensus() {
    if (!latestProvenanceCensus) return;
    const body = serializeMinimizerCheckpointProvenanceCensusV1(latestProvenanceCensus);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-provenance-census-${latestProvenanceCensus.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportProvenanceCoverage() {
    if (!latestProvenanceCoverageMatrix) return;
    const body = serializeMinimizerCheckpointProvenanceCoverageMatrixV1(latestProvenanceCoverageMatrix);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-provenance-coverage-${latestProvenanceCoverageMatrix.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  function exportProvenanceTopology() {
    if (!latestProvenanceSessionTopology) return;
    const body = serializeMinimizerCheckpointProvenanceSessionTopologyV1(latestProvenanceSessionTopology);
    const blob = new Blob([body], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `kq1agi-checkpoint-provenance-topology-${latestProvenanceSessionTopology.hash.slice(7, 19)}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  }

  async function importProvenanceFiles() {
    const files = [...(importProvenanceInput.files ?? [])];
    importProvenanceInput.value = '';
    if (!files.length) return;

    try {
      const reportsByHash = new Map();
      for (const item of importedProvenancePackages) {
        reportsByHash.set(item.evidenceReport.hash, item.evidenceReport);
      }
      if (latestShadowEvidenceReport) {
        reportsByHash.set(latestShadowEvidenceReport.hash, latestShadowEvidenceReport);
      }

      const sidecars = [];
      for (const file of files) {
        if (file.size > 16 * 1024 * 1024) {
          throw new Error(`Provenance file is larger than 16 MiB: ${file.name}`);
        }
        const parsed = JSON.parse(await file.text());
        if (parsed?.schema === MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
          const validated = await validateMinimizerCheckpointEvidenceArtifactV1(parsed);
          if (validated.kind !== 'report') throw new Error('Provenance import requires Phase -1I.4 reports.');
          reportsByHash.set(parsed.hash, parsed);
        } else if (parsed?.schema === MinimizerCheckpointProvenanceLayout.PROVENANCE_SCHEMA) {
          sidecars.push(parsed);
        } else {
          throw new Error(`Unsupported provenance import schema in ${file.name}`);
        }
      }
      if (!sidecars.length) throw new Error('Provenance import requires at least one Phase -1I.9 sidecar.');

      const batch = [];
      for (const provenance of sidecars) {
        const evidenceReport = reportsByHash.get(provenance.evidenceReportHash);
        if (!evidenceReport) {
          throw new Error(`Missing Phase -1I.4 report for provenance ${shortHash(provenance.hash)}.`);
        }
        await validateMinimizerCheckpointCollectionProvenanceV1(provenance, evidenceReport);
        batch.push(Object.freeze({ evidenceReport, provenance }));
      }

      const knownProvenanceHashes = new Set(
        importedProvenancePackages.map(item => item.provenance.hash),
      );
      const committedBatch = [];
      for (const item of batch) {
        if (knownProvenanceHashes.has(item.provenance.hash)) continue;
        knownProvenanceHashes.add(item.provenance.hash);
        committedBatch.push(item);
      }
      const candidatePackages = [
        ...importedProvenancePackages,
        ...committedBatch,
        ...(latestCollectionProvenance && latestShadowEvidenceReport
          ? [{ evidenceReport: latestShadowEvidenceReport, provenance: latestCollectionProvenance }]
          : []),
      ];
      const census = await createMinimizerCheckpointProvenanceCensusV1(candidatePackages);
      const provenanceCoverage = await createMinimizerCheckpointProvenanceCoverageMatrixV1(candidatePackages);
      const provenanceTopology = await createMinimizerCheckpointProvenanceSessionTopologyV1(candidatePackages);
      if (provenanceCoverage.provenanceCensusHash !== census.hash
          || provenanceTopology.provenanceCensusHash !== census.hash
          || provenanceTopology.provenanceCoverageMatrixHash !== provenanceCoverage.hash) {
        throw new Error('Provenance derived artifact hash mismatch.');
      }
      importedProvenancePackages.push(...committedBatch);
      latestProvenanceCensus = census;
      latestProvenanceCoverageMatrix = provenanceCoverage;
      latestProvenanceSessionTopology = provenanceTopology;
      globalThis.__kq1agiCheckpointProvenanceCensus = census;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrix = provenanceCoverage;
      globalThis.__kq1agiCheckpointProvenanceSessionTopology = provenanceTopology;
      globalThis.__kq1agiCheckpointProvenanceCensusError = null;
      globalThis.__kq1agiCheckpointProvenanceCoverageMatrixError = null;
      globalThis.__kq1agiCheckpointProvenanceSessionTopologyError = null;
      exportProvenanceCensusButton.disabled = replayRunning || !latestProvenanceCensus;
      exportProvenanceCoverageButton.disabled = replayRunning || !latestProvenanceCoverageMatrix;
      exportProvenanceTopologyButton.disabled = replayRunning || !latestProvenanceSessionTopology;
      setStatus('PROVENANCE TOPOLOGY READY', 'MATCH');
      progress.textContent = `Phase -1I.10/-1I.12 imported ${sidecars.length} provenance sidecar(s) · census + coverage + topology validation PASS`;
      detail.textContent = [
        checkpointProvenanceCensusText(census),
        '',
        checkpointProvenanceCoverageText(provenanceCoverage),
        '',
        checkpointProvenanceTopologyText(provenanceTopology),
      ].join('\n');
    } catch (error) {
      globalThis.__kq1agiCheckpointProvenanceCensusError = String(error?.message ?? error);
      setStatus('PROVENANCE IMPORT REJECTED', 'ERROR');
      progress.textContent = 'Phase -1I.10 provenance import rejected';
      detail.textContent = String(error?.stack ?? error);
    }
  }

  async function importEvidenceFiles() {
    const files = [...(importEvidenceInput.files ?? [])];
    importEvidenceInput.value = '';
    if (!files.length) return;

    try {
      const batch = [];
      for (const file of files) {
        if (file.size > 16 * 1024 * 1024) {
          throw new Error(`Evidence file is larger than 16 MiB: ${file.name}`);
        }
        const parsed = JSON.parse(await file.text());
        await validateMinimizerCheckpointEvidenceArtifactV1(parsed);
        batch.push(parsed);
      }

      const inputs = [
        ...importedEvidenceArtifacts,
        ...batch,
        ...(latestShadowEvidenceReport ? [latestShadowEvidenceReport] : []),
      ];
      const corpus = await createMinimizerCheckpointEvidenceCorpusV1(inputs);
      importedEvidenceArtifacts.splice(0, importedEvidenceArtifacts.length, corpus);
      latestEvidenceCorpus = corpus;
      globalThis.__kq1agiCheckpointEvidenceCorpus = corpus;
      globalThis.__kq1agiCheckpointEvidenceCorpusError = null;
      const review = await refreshEvidenceReview();
      const cohortReview = await refreshEvidenceCohortReview();
      const coverageProfile = await refreshEvidenceCoverageProfile();
      exportEvidenceCorpusButton.disabled = replayRunning || !latestEvidenceCorpus;
      setStatus('EVIDENCE CORPUS READY', 'MATCH');
      progress.textContent = review && cohortReview && coverageProfile
        ? `Phase -1I.5 imported ${files.length} evidence file(s) · hash validation PASS · I.6 review ready · I.7 cohorts ready · I.8 coverage ready`
        : `Phase -1I.5 imported ${files.length} evidence file(s) · hash validation PASS · derived evidence artifact unavailable`;
      detail.textContent = [
        checkpointEvidenceCorpusText(corpus),
        '',
        checkpointEvidenceReviewText(review),
        '',
        checkpointEvidenceCohortReviewText(cohortReview),
        '',
        checkpointEvidenceCoverageText(coverageProfile),
      ].join('\n');
    } catch (error) {
      globalThis.__kq1agiCheckpointEvidenceCorpusError = String(error?.message ?? error);
      setStatus('EVIDENCE IMPORT REJECTED', 'ERROR');
      progress.textContent = 'Phase -1I.5 evidence import rejected';
      detail.textContent = String(error?.stack ?? error);
    }
  }

  function refreshJournal() {
    const stats = getPlayRecordingStats();
    if (stats.overflowed) {
      recordingStatus.textContent = 'PLAY journal reached its safety limit · reload before reproducing again';
      return;
    }
    if (!stats.rawCount) {
      recordingStatus.textContent = 'PLAY journal: waiting for the first logical tick…';
      return;
    }
    if (!stats.completeFromStart) {
      recordingStatus.textContent = `PLAY journal started at tick ${stats.startTick || '?'} · reload required for replay from game start`;
      return;
    }
    const boundary = snapshotReadyPlayJournal();
    const game = boundary.gameDirectory ? ` · game ${boundary.gameDirectory}` : '';
    const suffix = boundary.ready ? ' · replay boundary ready' : ' · waiting for worker boundary';
    recordingStatus.textContent = `PLAY journal: ticks 1–${stats.finalTick} · ${stats.eventCount} transport event(s) · ${stats.randomCount} RNG draw(s) · ${stats.releaseCount} cycle release(s)${game}${suffix}`;
  }

  async function runFrozenRecording(recording, gameBuffer, editConfig, options = {}) {
    const truthWorkerUrl = new URL('./truth-worker/worker.nocache.js', import.meta.url).href;
    const editedWorkerUrl = new URL('./edited-worker/worker.nocache.js', import.meta.url).href;
    replayHost?.terminate();
    replayHost = new ReplayCertificationHost({
      truthWorkerUrl,
      editedWorkerUrl,
      randomReplaySpec: encodeRandomReplay(recording),
      recordedExternalTiming: true,
      checkpointContext: {
        gameHash: recording.gameHash,
        gameBytes: recording.gameBytes,
        editConfigHash: recording.editConfigHash,
        recordingHash: recording.hash,
      },
    });
    try {
      await replayHost.start(gameBuffer);
      const applyEditConfig = createEditConfigApplicator(editConfig);
      applyEditConfig(replayHost);
      const summary = await runCertificationReplaySession(replayHost, recording, {
        pulseIntervalMs: options.pulseIntervalMs ?? (1000 / 60),
        beforePulse: () => applyEditConfig(replayHost),
        shouldStop: () => stopRequested,
        onUpdate: options.onUpdate ?? (() => {}),
        checkpoint: options.checkpoint ?? null,
      });

      if (!options.captureEvidence) return summary;

      let evidence = null;
      let evidenceError = null;
      if (['REPLAY_MATCH', 'DIVERGED', 'COMPLETE'].includes(String(summary?.status ?? ''))) {
        try {
          evidence = await captureCheckpointOracleEvidenceV1(replayHost);
        } catch (error) {
          evidenceError = String(error?.stack ?? error);
        }
      }
      return Object.freeze({ summary, evidence, evidenceError });
    } finally {
      replayHost?.terminate();
      replayHost = null;
    }
  }

  async function captureFrozenRecordingCheckpoint(recording, gameBuffer, editConfig, selection) {
    if (selection?.status !== 'MINIMIZER_SHADOW_BOUNDARY_SELECTED') {
      return Object.freeze({
        status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
        reason: selection?.reason ?? 'no-boundary',
        selection,
      });
    }

    const truthWorkerUrl = new URL('./truth-worker/worker.nocache.js', import.meta.url).href;
    const editedWorkerUrl = new URL('./edited-worker/worker.nocache.js', import.meta.url).href;
    replayHost?.terminate();
    replayHost = new ReplayCertificationHost({
      truthWorkerUrl,
      editedWorkerUrl,
      randomReplaySpec: encodeRandomReplay(recording),
      recordedExternalTiming: true,
      checkpointContext: {
        gameHash: recording.gameHash,
        gameBytes: recording.gameBytes,
        editConfigHash: recording.editConfigHash,
        recordingHash: recording.hash,
      },
    });

    try {
      await replayHost.start(gameBuffer);
      const applyEditConfig = createEditConfigApplicator(editConfig);
      applyEditConfig(replayHost);
      const paused = await runCertificationReplaySession(replayHost, recording, {
        pulseIntervalMs: 0,
        beforePulse: () => applyEditConfig(replayHost),
        shouldStop: () => stopRequested,
        pauseBeforeTick: selection.pauseBeforeTick,
      });
      if (paused?.status !== 'REPLAY_PAUSED') {
        return Object.freeze({
          status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
          reason: `pause-${paused?.status ?? 'unknown'}`,
          selection,
          paused,
        });
      }

      const checkpoint = await replayHost.captureCheckpointProbe();
      if (checkpoint?.status !== 'CHECKPOINT_CAPTURED') {
        return Object.freeze({
          status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
          reason: checkpoint?.status ?? 'capture-failed',
          selection,
          checkpointResult: checkpoint ?? null,
        });
      }
      if ((Number(checkpoint.logicalTick) >>> 0) !== (Number(selection.checkpointTick) >>> 0)) {
        return Object.freeze({
          status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
          reason: 'checkpoint-position',
          selection,
          checkpointResult: checkpoint,
        });
      }

      return Object.freeze({
        status: 'MINIMIZER_SHADOW_CHECKPOINT_CAPTURED',
        selection,
        checkpoint,
      });
    } catch (error) {
      return Object.freeze({
        status: 'MINIMIZER_SHADOW_CHECKPOINT_UNAVAILABLE',
        reason: 'capture-exception',
        selection,
        error: String(error?.stack ?? error),
      });
    } finally {
      replayHost?.terminate();
      replayHost = null;
    }
  }

  async function startReplay() {
    if (replayRunning || runButton.disabled) return;
    invalidateMinimization();
    if (!window.crossOriginIsolated) {
      setStatus('NOT ISOLATED', 'ERROR');
      detail.textContent = 'REPLAY PLAY requires the same cross-origin isolation used by the AGILE SharedArrayBuffer runtime.';
      return;
    }
    const directoryName = gameSelect.value;
    if (!directoryName) {
      setStatus('NO LOCAL GAME', 'ERROR');
      return;
    }

    const boundary = snapshotReadyPlayJournal();
    if (!boundary.ready) {
      setStatus('WAIT FOR PLAY IDLE', 'WAITING');
      detail.textContent = boundaryMessage(boundary);
      refreshJournal();
      return;
    }
    if (boundary.gameDirectory !== directoryName) {
      setStatus('PLAY GAME MISMATCH', 'ERROR');
      detail.textContent = `The frozen PLAY journal belongs to local game "${boundary.gameDirectory}", but CERTIFY currently selects "${directoryName}". Select the same imported game before replaying.`;
      return;
    }
    const rawEvents = boundary.rawEvents;
    const overflowed = boundary.overflowed;

    stopRequested = false;
    setReplayRunning(true);
    setStatus('FREEZING PLAY WINDOW', 'BUSY');
    progress.textContent = 'Preparing Phase -1D replay…';
    detail.textContent = `Normal PLAY boundary confirmed for ${boundary.gameDirectory} at released cycle tick ${boundary.lastReleaseTick}. Hashing local GAMEFILES.DAT, frozen EditConfig v1, and the in-memory PLAY journal…`;

    try {
      const gameBuffer = await readImportedGame(directoryName);
      const editConfig = await captureEditConfigV1();
      const recording = await freezePlayRecordingV1({ gameBuffer, editConfig, rawEvents, overflowed });

      setStatus('REPLAYING PLAY', 'BUSY');
      detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nORIGINAL receives the recorded PLAY transport unchanged. Frozen EditConfig applies only to EDITED.`;
      const summary = await runFrozenRecording(recording, gameBuffer, editConfig, {
        pulseIntervalMs: 1000 / 60,
        onUpdate: update => {
          progress.textContent = `replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${recording.finalTick} · ${update.certifiedBarriers} certified barrier(s)`;
          if (update.result?.status === 'MATCH' || update.result?.status === 'DIVERGED') {
            detail.textContent = `${formatCertificationResult(update.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
          }
        },
      });

      if (summary.status === 'REPLAY_MATCH') {
        setStatus(`REPLAY MATCH × ${summary.certifiedBarriers}`, 'MATCH');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe recorded PLAY window reached tick ${summary.finalTick}, settled its final in-flight cycle at that same logical tick, consumed the complete recorded RNG stream, and found no covered semantic divergence across ${summary.certifiedBarriers} shared barrier(s).`;
      } else if (summary.status === 'DIVERGED') {
        lastDivergenceContext = Object.freeze({ directoryName, recording, editConfig, firstDivergence: summary.firstDivergence });
        minimizeButton.disabled = false;
        setStatus(`DIVERGED @ ${summary.firstDivergence.tick}`, 'DIVERGED');
        detail.textContent = `${formatCertificationResult(summary.firstDivergence)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}\n\nThis is the first divergent shared barrier in the recorded PLAY window. MINIMIZE can now search for the shortest from-start prefix that reproduces this exact mismatch.`;
      } else if (summary.status === 'COMPLETE') {
        setStatus('REPLAY COMPLETE / MATCH', 'MATCH');
        detail.textContent = `${formatCertificationResult(summary.result)}\neditConfig=${editConfigIdentity(editConfig)}\nrecording=${recordingIdentity(recording)}`;
      } else if (summary.status === 'REPLAY_TIMING_MISS') {
        setStatus(`REPLAY TIMING MISS @ ${summary.result.tick}`, 'WAITING');
        detail.textContent = `recording=${recordingIdentity(recording)}\neditConfig=${editConfigIdentity(editConfig)}\n\nThe certification workers could not reproduce recorded timing (${summary.result.reason ?? 'timing'} at tick ${summary.result.tick}). This is a reproduction failure, not an ORIGINAL-vs-EDITED semantic divergence.`;
      } else if (summary.status === 'REPLAY_CONTRACT_MISS') {
        setStatus(`REPLAY CONTRACT MISS @ ${summary.result.tick}`, 'WAITING');
        detail.textContent = contractMissText(summary, recording, editConfig);
      } else if (summary.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(summary.status, 'ERROR');
        detail.textContent = `${formatCertificationResult(summary.result)}\nrecording=${recordingIdentity(recording)}`;
      }
    } catch (error) {
      invalidateMinimization();
      setStatus('REPLAY ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startMinimize() {
    if (replayRunning || !lastDivergenceContext) return;
    lastMinimizedContext = null;
    lastInputReducedContext = null;
    reduceInputsButton.disabled = true;
    reduceEditsButton.disabled = true;
    const context = lastDivergenceContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('MINIMIZE GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after the divergent replay. Replay the intended game again before minimizing.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    setStatus('MINIMIZING', 'BUSY');
    progress.textContent = `target divergence tick ${context.firstDivergence.tick}`;
    detail.textContent = `recording=${recordingIdentity(context.recording)}\neditConfig=${editConfigIdentity(context.editConfig)}\n\nSearching only hash-valid prefixes that start at logical tick 1 and reproduce the exact same first divergence.`;

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);

      const shadowSelection = selectMinimizerShadowCheckpointBoundaryV1(
        context.recording,
        context.firstDivergence.tick,
      );
      progress.textContent = shadowSelection.status === 'MINIMIZER_SHADOW_BOUNDARY_SELECTED'
        ? `capturing Phase -1E shadow checkpoint @ tick ${shadowSelection.checkpointTick}…`
        : `Phase -1E checkpoint shadow unavailable · ${shadowSelection.reason}`;
      const shadowState = await captureFrozenRecordingCheckpoint(
        context.recording,
        gameBuffer,
        context.editConfig,
        shadowSelection,
      );
      const shadowResults = [];
      const shadowEvidenceErrors = [];

      const replayCandidate = async candidate => {
        attemptNumber += 1;
        if (!shadowState.checkpoint) {
          return runFrozenRecording(candidate, gameBuffer, context.editConfig, {
            pulseIntervalMs: 0,
            onUpdate: update => {
              progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${candidate.finalTick} · full replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}`;
            },
          });
        }

        const shadow = await runMinimizerCheckpointShadowV1({
          checkpoint: shadowState.checkpoint,
          sourceRecording: context.recording,
          candidateRecording: candidate,
          runFullReplay: recording => runFrozenRecording(recording, gameBuffer, context.editConfig, {
            pulseIntervalMs: 0,
            captureEvidence: true,
            onUpdate: update => {
              progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${candidate.finalTick} · full replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}`;
            },
          }),
          runCheckpointReplay: (recording, reboundCheckpoint) => runFrozenRecording(
            recording,
            gameBuffer,
            context.editConfig,
            {
              pulseIntervalMs: 0,
              checkpoint: reboundCheckpoint,
              captureEvidence: true,
              onUpdate: update => {
                progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${candidate.finalTick} · checkpoint replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}`;
              },
            },
          ),
        });
        try {
          const observation = await compactMinimizerCheckpointObservationV1(shadow, candidate.hash);
          shadowResults.push(observation);
        } catch {
          shadowEvidenceErrors.push(String(candidate.hash ?? 'unknown-candidate'));
        }
        return shadow.summary;
      };

      const minimized = await minimizeDivergentPrefix(
        context.recording,
        context.firstDivergence,
        replayCandidate,
        {
          focusRadius: 60,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `minimize attempt ${attemptNumber} · candidate tick ${attempt.finalTick} · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );
      const evidenceReport = await recordShadowEvidenceStage(
        'phase-1e',
        context,
        shadowState,
        shadowResults,
        shadowEvidenceErrors,
        { status: minimized.status, attempts: minimized.attempts?.length ?? attemptNumber },
      );

      if (minimized.status === 'MINIMIZED') {
        lastMinimizedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: minimized.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        reduceInputsButton.disabled = false;
        setStatus(`MINIMIZED TO ${minimized.minimizedFinalTick}`, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `recording=${recordingIdentity(context.recording)}`,
          `minimized=${recordingIdentity(minimized.recording)}`,
          `removedTicks=${minimized.removedTicks}`,
          `attempts=${minimized.attempts.length}`,
          '',
          minimizationFocusText(minimized.focus),
          '',
          'The focused window is diagnostic context only; authoritative replay still starts at logical tick 1.',
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (minimized.status === 'NOT_REPRODUCED') {
        setStatus('MINIMIZE NOT REPRODUCED', 'WAITING');
        detail.textContent = [
          'The frozen source no longer reproduced the exact target divergence. No reduced recording was accepted.',
          `recording=${recordingIdentity(context.recording)}`,
          `attempts=${minimized.attempts.length}`,
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (minimized.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(minimized.status, 'ERROR');
        detail.textContent = JSON.stringify(minimized, null, 2);
      }
    } catch (error) {
      setStatus('MINIMIZE ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startReduceInputs() {
    if (replayRunning || !lastMinimizedContext) return;
    lastInputReducedContext = null;
    reduceEditsButton.disabled = true;
    const context = lastMinimizedContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('INPUT GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after prefix minimization. Replay and minimize the intended game again before reducing inputs.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    const groups = groupReplayInputEventsV1(context.recording);
    setStatus('REDUCING INPUTS', 'BUSY');
    progress.textContent = `${groups.length} dependency-safe input group(s) · target tick ${context.firstDivergence.tick}`;
    detail.textContent = [
      `recording=${recordingIdentity(context.recording)}`,
      `editConfig=${editConfigIdentity(context.editConfig)}`,
      '',
      'Keeping release timing, RNG draws, sound completions, game identity, EditConfig identity, and final tick frozen while delta-debugging keyboard/mouse groups.',
    ].join('\n');

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);

      const shadowSelection = selectMinimizerShadowCheckpointBoundaryV1(
        context.recording,
        context.firstDivergence.tick,
      );
      progress.textContent = shadowSelection.status === 'MINIMIZER_SHADOW_BOUNDARY_SELECTED'
        ? `capturing Phase -1F shadow checkpoint @ tick ${shadowSelection.checkpointTick}…`
        : `Phase -1F checkpoint shadow unavailable · ${shadowSelection.reason}`;
      const shadowState = await captureFrozenRecordingCheckpoint(
        context.recording,
        gameBuffer,
        context.editConfig,
        shadowSelection,
      );
      const shadowResults = [];
      const shadowEvidenceErrors = [];

      const replayCandidate = async candidate => {
        attemptNumber += 1;
        if (!shadowState.checkpoint) {
          return runFrozenRecording(candidate, gameBuffer, context.editConfig, {
            pulseIntervalMs: 0,
            onUpdate: update => {
              progress.textContent = `input attempt ${attemptNumber} · full replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidate.finalTick}`;
            },
          });
        }

        const shadow = await runMinimizerCheckpointShadowV1({
          checkpoint: shadowState.checkpoint,
          sourceRecording: context.recording,
          candidateRecording: candidate,
          runFullReplay: recording => runFrozenRecording(recording, gameBuffer, context.editConfig, {
            pulseIntervalMs: 0,
            captureEvidence: true,
            onUpdate: update => {
              progress.textContent = `input attempt ${attemptNumber} · full replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidate.finalTick}`;
            },
          }),
          runCheckpointReplay: (recording, reboundCheckpoint) => runFrozenRecording(
            recording,
            gameBuffer,
            context.editConfig,
            {
              pulseIntervalMs: 0,
              checkpoint: reboundCheckpoint,
              captureEvidence: true,
              onUpdate: update => {
                progress.textContent = `input attempt ${attemptNumber} · checkpoint replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidate.finalTick}`;
              },
            },
          ),
        });
        try {
          const observation = await compactMinimizerCheckpointObservationV1(shadow, candidate.hash);
          shadowResults.push(observation);
        } catch {
          shadowEvidenceErrors.push(String(candidate.hash ?? 'unknown-candidate'));
        }
        return shadow.summary;
      };

      const reduced = await minimizeInputGroupsV1(
        context.recording,
        context.firstDivergence,
        replayCandidate,
        {
          maxAttempts: 256,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `input attempt ${attempt.number} · kept ${attempt.keptGroups}/${groups.length} group(s) · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );
      const evidenceReport = await recordShadowEvidenceStage(
        'phase-1f',
        context,
        shadowState,
        shadowResults,
        shadowEvidenceErrors,
        { status: reduced.status, attempts: reduced.attempts?.length ?? attemptNumber },
      );

      if (reduced.status === 'INPUTS_MINIMIZED' || reduced.status === 'INPUTS_ALREADY_MINIMAL') {
        const label = reduced.status === 'INPUTS_MINIMIZED'
          ? `INPUTS ${reduced.keptGroups.length}/${reduced.totalGroups}`
          : 'INPUTS ALREADY MINIMAL';
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        reduceEditsButton.disabled = false;
        setStatus(label, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `source=${recordingIdentity(context.recording)}`,
          `reduced=${recordingIdentity(reduced.recording)}`,
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `input events=${reduced.totalInputEvents} → ${reduced.keptInputEvents}`,
          `locked events retained=${reduced.lockedEvents}`,
          `attempts=${reduced.attempts.length}`,
          '',
          inputGroupsText(reduced.keptGroups),
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (reduced.status === 'NO_REMOVABLE_INPUTS') {
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: context.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        reduceEditsButton.disabled = false;
        setStatus('NO REMOVABLE INPUTS', 'MATCH');
        detail.textContent = [
          `The minimized prefix contains no dependency-safe keyboard/mouse groups. ${reduced.lockedEvents} locked reproduction event(s) remain. REDUCE EDITS can now minimize the frozen EditConfig.`,
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (reduced.status === 'NOT_REPRODUCED') {
        setStatus('INPUT TARGET NOT REPRODUCED', 'WAITING');
        detail.textContent = [
          'The Phase -1E source no longer reproduced the exact target divergence. No input reduction was accepted.',
          `attempts=${reduced.attempts.length}`,
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (reduced.status === 'PARTIAL') {
        setStatus(`INPUTS PARTIAL ${reduced.keptGroups.length}/${reduced.totalGroups}`, 'WAITING');
        detail.textContent = [
          'The input attempt budget ended before 1-minimality was proven.',
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `input events=${reduced.totalInputEvents} → ${reduced.keptInputEvents}`,
          `attempts=${reduced.attempts.length}`,
          '',
          inputGroupsText(reduced.keptGroups),
          '',
          checkpointShadowSummaryText(shadowState, shadowResults),
          '',
          checkpointEvidencePopulationText(evidenceReport),
        ].join('\n');
      } else if (reduced.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(reduced.status, 'ERROR');
        detail.textContent = JSON.stringify(reduced, null, 2);
      }
    } catch (error) {
      setStatus('INPUT REDUCTION ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  async function startReduceEdits() {
    if (replayRunning || !lastInputReducedContext) return;
    const context = lastInputReducedContext;
    if (gameSelect.value !== context.directoryName) {
      invalidateMinimization();
      setStatus('EDIT GAME MISMATCH', 'ERROR');
      detail.textContent = 'The selected imported game changed after input minimization. Replay the intended game and repeat the reduction pipeline before reducing edits.';
      return;
    }

    stopRequested = false;
    setReplayRunning(true);
    let groups = [];
    setStatus('REDUCING EDITS', 'BUSY');
    progress.textContent = 'Verifying frozen EditConfig identity…';
    detail.textContent = [
      `recording=${recordingIdentity(context.recording)}`,
      `editConfig=${editConfigIdentity(context.editConfig)}`,
      '',
      'Keeping GAMEFILES.DAT, minimized ticks, input transport, RNG draws, sound completions, and exact divergence frozen while delta-debugging whole room configs and the visual-pin set.',
    ].join('\n');

    let attemptNumber = 0;
    try {
      const gameBuffer = await readImportedGame(context.directoryName);
      await validateFrozenReplayIdentityV1(context.recording, gameBuffer, context.editConfig);
      groups = groupEditConfigV1(context.editConfig);
      progress.textContent = `${groups.length} dependency-safe EditConfig group(s) · target tick ${context.firstDivergence.tick}`;

      const replayCandidate = async (candidateRecording, candidateConfig) => {
        attemptNumber += 1;
        await validateFrozenReplayIdentityV1(candidateRecording, gameBuffer, candidateConfig);
        return runFrozenRecording(candidateRecording, gameBuffer, candidateConfig, {
          pulseIntervalMs: 0,
          onUpdate: update => {
            progress.textContent = `edit attempt ${attemptNumber} · replay tick ${replayHost?.logicalTick ?? update.targetTick ?? 0}/${candidateRecording.finalTick}`;
          },
        });
      };

      const reduced = await minimizeEditConfigV1(
        context.recording,
        context.editConfig,
        context.firstDivergence,
        replayCandidate,
        {
          maxAttempts: 128,
          shouldStop: () => stopRequested,
          onAttempt: attempt => {
            progress.textContent = `edit attempt ${attempt.number} · kept ${attempt.keptGroups}/${groups.length} group(s) · ${attempt.reproduced ? 'same divergence' : attempt.status}`;
          },
        },
      );

      if (reduced.status === 'EDITS_MINIMIZED' || reduced.status === 'EDITS_ALREADY_MINIMAL') {
        const label = reduced.status === 'EDITS_MINIMIZED'
          ? `EDITS ${reduced.keptGroups.length}/${reduced.totalGroups}`
          : 'EDITS ALREADY MINIMAL';
        const reducedContext = Object.freeze({
          directoryName: context.directoryName,
          recording: reduced.recording,
          editConfig: reduced.editConfig,
          firstDivergence: context.firstDivergence,
        });
        lastMinimizedContext = reducedContext;
        lastInputReducedContext = reducedContext;
        setStatus(label, 'MATCH');
        detail.textContent = [
          `target=${formatCertificationResult(context.firstDivergence)}`,
          `source recording=${recordingIdentity(context.recording)}`,
          `rebound recording=${recordingIdentity(reduced.recording)}`,
          `source EditConfig=${editConfigIdentity(context.editConfig)}`,
          `reduced EditConfig=${editConfigIdentity(reduced.editConfig)}`,
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `room configs=${reduced.totalRoomGroups} → ${reduced.keptRoomGroups}`,
          `visual pins=${reduced.totalVisualPins} → ${reduced.keptVisualPins}`,
          `attempts=${reduced.attempts.length}`,
          '',
          editGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'NO_REMOVABLE_EDITS') {
        setStatus('NO REMOVABLE EDITS', 'MATCH');
        detail.textContent = 'The current minimized reproduction has no configured rooms or visual pins to remove.';
      } else if (reduced.status === 'NOT_REPRODUCED') {
        setStatus('EDIT TARGET NOT REPRODUCED', 'WAITING');
        detail.textContent = `The Phase -1F source no longer reproduced the exact target divergence. No EditConfig reduction was accepted.\nattempts=${reduced.attempts.length}`;
      } else if (reduced.status === 'PARTIAL') {
        setStatus(`EDITS PARTIAL ${reduced.keptGroups.length}/${reduced.totalGroups}`, 'WAITING');
        detail.textContent = [
          'The EditConfig attempt budget ended before 1-minimality was proven.',
          `groups=${reduced.totalGroups} → ${reduced.keptGroups.length}`,
          `room configs=${reduced.totalRoomGroups} → ${reduced.keptRoomGroups}`,
          `visual pins=${reduced.totalVisualPins} → ${reduced.keptVisualPins}`,
          `attempts=${reduced.attempts.length}`,
          '',
          editGroupsText(reduced.keptGroups),
        ].join('\n');
      } else if (reduced.status === 'STOPPED') {
        setStatus('STOPPED', 'IDLE');
      } else {
        setStatus(reduced.status, 'ERROR');
        detail.textContent = JSON.stringify(reduced, null, 2);
      }
    } catch (error) {
      setStatus('EDIT REDUCTION ERROR', 'ERROR');
      detail.textContent = String(error?.stack ?? error);
    } finally {
      replayHost?.terminate();
      replayHost = null;
      setReplayRunning(false);
      refreshJournal();
    }
  }

  replayButton.addEventListener('click', startReplay);
  minimizeButton.addEventListener('click', startMinimize);
  reduceInputsButton.addEventListener('click', startReduceInputs);
  reduceEditsButton.addEventListener('click', startReduceEdits);
  exportShadowEvidenceButton.addEventListener('click', exportShadowEvidence);
  importEvidenceButton.addEventListener('click', () => {
    if (!replayRunning) importEvidenceInput.click();
  });
  importEvidenceInput.addEventListener('change', importEvidenceFiles);
  exportEvidenceCorpusButton.addEventListener('click', exportEvidenceCorpus);
  exportEvidenceReviewButton.addEventListener('click', exportEvidenceReview);
  exportEvidenceCohortsButton.addEventListener('click', exportEvidenceCohorts);
  exportEvidenceCoverageButton.addEventListener('click', exportEvidenceCoverage);
  exportCollectionProvenanceButton.addEventListener('click', exportCollectionProvenance);
  importProvenanceButton.addEventListener('click', () => {
    if (!replayRunning) importProvenanceInput.click();
  });
  importProvenanceInput.addEventListener('change', importProvenanceFiles);
  exportProvenanceCensusButton.addEventListener('click', exportProvenanceCensus);
  exportProvenanceCoverageButton.addEventListener('click', exportProvenanceCoverage);
  exportProvenanceTopologyButton.addEventListener('click', exportProvenanceTopology);
  gameSelect.addEventListener('change', invalidateMinimization);
  runButton.addEventListener('click', invalidateMinimization, { capture: true });
  stopButton.addEventListener('click', () => {
    if (!replayRunning) return;
    stopRequested = true;
    setStatus('STOPPING…', 'BUSY');
  });
  window.addEventListener('beforeunload', () => replayHost?.terminate());
  setInterval(() => {
    if (!replayRunning && panel.getAttribute('aria-hidden') === 'false') refreshJournal();
  }, 1000);
  refreshJournal();
}

if (typeof document !== 'undefined') installPhase1D();
