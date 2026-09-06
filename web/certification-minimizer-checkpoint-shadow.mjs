import { runCheckpointCandidateOracleV1 } from './certification-checkpoint-oracle.mjs';

function asTick(value) {
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 0 ? n : -1;
}

function freezeReasonCounts(map) {
  return Object.freeze(
    [...map.entries()]
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([reason, count]) => Object.freeze({ reason, count })),
  );
}

/**
 * Pick one deterministic experimental checkpoint for minimizer shadow evidence.
 *
 * The checkpoint is intentionally near the midpoint of the target divergence tick,
 * not at the latest possible boundary. That balances useful skipped-prefix telemetry
 * against the chance that Phase -1F candidates still have an unchanged authenticated
 * prefix and are therefore eligible for the Phase -1I.1 rebinding proof.
 *
 * Phase -1E prefix candidates all end at or after targetTick, so any selected
 * checkpoint before targetTick is structurally eligible unless replay authority
 * itself differs.
 */
export function selectMinimizerShadowCheckpointBoundaryV1(recording, targetTick) {
  const target = asTick(targetTick);
  if (target < 2) {
    return Object.freeze({
      status: 'MINIMIZER_SHADOW_NO_BOUNDARY',
      reason: 'target-too-early',
      targetTick: target,
    });
  }

  const releases = [...new Set((recording?.releaseTicks ?? [])
    .map(asTick)
    .filter(tick => tick >= 2 && tick <= target))]
    .sort((a, b) => a - b);

  if (!releases.length) {
    return Object.freeze({
      status: 'MINIMIZER_SHADOW_NO_BOUNDARY',
      reason: 'no-recorded-release',
      targetTick: target,
    });
  }

  const desiredCheckpointTick = Math.max(1, Math.floor(target / 2));
  const candidates = releases.map(pauseBeforeTick => Object.freeze({
    pauseBeforeTick,
    checkpointTick: pauseBeforeTick - 1,
  }));

  candidates.sort((a, b) => {
    const da = Math.abs(a.checkpointTick - desiredCheckpointTick);
    const db = Math.abs(b.checkpointTick - desiredCheckpointTick);
    return da - db || b.checkpointTick - a.checkpointTick;
  });

  const selected = candidates[0];
  return Object.freeze({
    status: 'MINIMIZER_SHADOW_BOUNDARY_SELECTED',
    targetTick: target,
    desiredCheckpointTick,
    pauseBeforeTick: selected.pauseBeforeTick,
    checkpointTick: selected.checkpointTick,
    recordedReleaseCount: releases.length,
  });
}

/**
 * Run one minimizer candidate through the Phase -1I.2 shadow oracle.
 *
 * The returned summary is ALWAYS the full from-start authoritative summary.
 * The checkpoint result is attached only as shadow evidence and must never become
 * the minimizer's reproduction decision in this phase.
 */
export async function runMinimizerCheckpointShadowV1(options = {}) {
  const {
    checkpoint,
    sourceRecording,
    candidateRecording,
    runFullReplay,
    runCheckpointReplay,
  } = options;

  const oracle = await runCheckpointCandidateOracleV1({
    checkpoint,
    sourceRecording,
    candidateRecording,
    runFullReplay,
    runCheckpointReplay,
  });

  return Object.freeze({
    summary: oracle.authoritativeSummary,
    oracle,
  });
}

export function summarizeMinimizerCheckpointShadowV1(results = []) {
  let equivalent = 0;
  let fullOnly = 0;
  let mismatch = 0;
  let checkpointAttempts = 0;
  let trustedCheckpoints = 0;
  let totalSavedTicks = 0;
  let measuredSavedCandidates = 0;
  const reasons = new Map();

  for (const result of results) {
    const oracle = result?.oracle ?? result;
    const status = String(oracle?.status ?? 'UNKNOWN');
    const reason = String(oracle?.reason ?? status);

    if (status === 'CHECKPOINT_ORACLE_EQUIVALENT') equivalent += 1;
    else if (status === 'CHECKPOINT_ORACLE_FULL_ONLY') fullOnly += 1;
    else if (status === 'CHECKPOINT_ORACLE_MISMATCH') mismatch += 1;

    if (oracle?.checkpointAttempted === true) checkpointAttempts += 1;
    if (oracle?.checkpointTrusted === true) trustedCheckpoints += 1;

    if (Number.isSafeInteger(oracle?.savedTicks) && oracle.savedTicks >= 0) {
      totalSavedTicks += oracle.savedTicks;
      measuredSavedCandidates += 1;
    }

    reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
  }

  const totalCandidates = results.length;
  return Object.freeze({
    totalCandidates,
    equivalent,
    fullOnly,
    mismatch,
    checkpointAttempts,
    trustedCheckpoints,
    totalSavedTicks,
    measuredSavedCandidates,
    averageSavedTicks: measuredSavedCandidates
      ? totalSavedTicks / measuredSavedCandidates
      : null,
    reasons: freezeReasonCounts(reasons),
  });
}

export const MinimizerCheckpointShadowLayout = Object.freeze({
  MODE: 'shadow-full-authoritative',
});
