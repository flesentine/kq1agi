import {
  canonicalizePlayRecordingV1,
  encodeRandomReplay,
  hashPlayRecordingV1,
} from './certification-recording.mjs';
import { hashCertificationCheckpointV1 } from './certification-host.mjs';

const CHECKPOINT_SCHEMA = 'kq1agi-certification-checkpoint-v1';
const RECORDING_SCHEMA = 'kq1agi-play-recording-v1';

function asTick(value) {
  const n = Number(value);
  return Number.isSafeInteger(n) && n >= 0 ? n : -1;
}

function sameJson(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function prefixAuthority(recording, checkpointTick) {
  const canonical = canonicalizePlayRecordingV1(recording);
  return {
    schema: canonical.schema,
    completeFromStart: canonical.completeFromStart,
    startTick: canonical.startTick,
    gameHash: canonical.gameHash,
    gameBytes: canonical.gameBytes,
    editConfigHash: canonical.editConfigHash,
    overflowed: canonical.overflowed,
    releaseTicks: canonical.releaseTicks.filter(tick => tick <= checkpointTick),
    events: canonical.events.filter(event => Number(event.tick) <= checkpointTick),
    random: canonical.random.filter(draw => Number(draw.tick) <= checkpointTick),
  };
}

function reject(reason, extra = {}) {
  return Object.freeze({
    status: 'CHECKPOINT_CANDIDATE_INCOMPATIBLE',
    reason,
    ...extra,
  });
}

async function verifyRecording(recording, label) {
  if (!recording || recording.schema !== RECORDING_SCHEMA) {
    return { error: reject(label + '-schema') };
  }
  const expected = String(recording.hash ?? '');
  const actual = await hashPlayRecordingV1(recording);
  if (!expected || expected !== actual) {
    return { error: reject(label + '-hash', {
      expectedHash: expected,
      actualHash: actual,
    }) };
  }
  return { recording: canonicalizePlayRecordingV1(recording), hash: actual };
}

/**
 * Prove that a Phase -1H checkpoint captured from sourceRecording can be used as
 * the starting state for candidateRecording.
 *
 * The proof is intentionally recording-only. GAMEFILES and EditConfig identity
 * must remain unchanged, and every release/event/RNG observation that can affect
 * state through checkpoint.logicalTick must be byte-for-byte canonical-equal.
 * The next tick must remain a recorded release boundary because Phase -1I resumes
 * immediately before that release.
 */
export async function proveCheckpointCandidateCompatibilityV1(
  checkpoint,
  sourceRecording,
  candidateRecording,
) {
  if (!checkpoint || checkpoint.schema !== CHECKPOINT_SCHEMA) {
    return reject('checkpoint-schema');
  }

  const expectedCheckpointHash = String(checkpoint.hash ?? '');
  const actualCheckpointHash = await hashCertificationCheckpointV1(checkpoint);
  if (!expectedCheckpointHash || expectedCheckpointHash !== actualCheckpointHash) {
    return reject('checkpoint-hash', {
      expectedHash: expectedCheckpointHash,
      actualHash: actualCheckpointHash,
    });
  }

  const sourceResult = await verifyRecording(sourceRecording, 'source-recording');
  if (sourceResult.error) return sourceResult.error;
  const candidateResult = await verifyRecording(candidateRecording, 'candidate-recording');
  if (candidateResult.error) return candidateResult.error;

  const source = sourceResult.recording;
  const candidate = candidateResult.recording;
  const checkpointTick = asTick(checkpoint.logicalTick);
  if (checkpointTick < 0) return reject('checkpoint-tick');
  const resumeBeforeTick = checkpointTick + 1;

  if (!source.completeFromStart || source.startTick !== 1
      || !candidate.completeFromStart || candidate.startTick !== 1) {
    return reject('recording-start');
  }
  if (source.overflowed || candidate.overflowed) {
    return reject('recording-overflow');
  }
  if (source.finalTick < resumeBeforeTick) {
    return reject('source-before-checkpoint', {
      checkpointTick,
      resumeBeforeTick,
      sourceFinalTick: source.finalTick,
    });
  }
  if (candidate.finalTick < resumeBeforeTick) {
    return reject('candidate-before-checkpoint', {
      checkpointTick,
      resumeBeforeTick,
      candidateFinalTick: candidate.finalTick,
    });
  }

  const context = checkpoint.context ?? {};
  if (context.recordedExternalTiming !== true) {
    return reject('checkpoint-timing-mode');
  }
  const sourceRandomReplaySpec = encodeRandomReplay(sourceRecording);
  if (String(context.recordingHash ?? '') !== sourceResult.hash) {
    return reject('checkpoint-source-recording');
  }
  if (String(context.randomReplaySpec ?? '') !== sourceRandomReplaySpec) {
    return reject('checkpoint-source-random');
  }
  if (String(context.gameHash ?? '') !== source.gameHash
      || Number(context.gameBytes) !== source.gameBytes
      || String(context.editConfigHash ?? '') !== source.editConfigHash) {
    return reject('checkpoint-source-context');
  }

  // Phase -1I.1 never rebinds execution roots. EditConfig changes (Phase -1G)
  // remain ineligible because they can change state from logical tick 1.
  if (candidate.gameHash !== source.gameHash
      || candidate.gameBytes !== source.gameBytes) {
    return reject('game-identity');
  }
  if (candidate.editConfigHash !== source.editConfigHash) {
    return reject('edit-config-identity');
  }

  const sourceBoundary = source.releaseTicks.includes(resumeBeforeTick);
  const candidateBoundary = candidate.releaseTicks.includes(resumeBeforeTick);
  if (!sourceBoundary || !candidateBoundary) {
    return reject('resume-boundary', {
      checkpointTick,
      resumeBeforeTick,
      sourceBoundary,
      candidateBoundary,
    });
  }

  const sourcePrefix = prefixAuthority(source, checkpointTick);
  const candidatePrefix = prefixAuthority(candidate, checkpointTick);
  if (!sameJson(sourcePrefix, candidatePrefix)) {
    return reject('prefix-authority', {
      checkpointTick,
      resumeBeforeTick,
    });
  }

  return Object.freeze({
    status: 'CHECKPOINT_CANDIDATE_COMPATIBLE',
    checkpointTick,
    resumeBeforeTick,
    sourceRecordingHash: sourceResult.hash,
    candidateRecordingHash: candidateResult.hash,
    sourceRandomReplaySpec,
    candidateRandomReplaySpec: encodeRandomReplay(candidateRecording),
    compatibilityKey: [
      expectedCheckpointHash,
      candidateResult.hash,
      checkpointTick,
    ].join('|'),
  });
}

/**
 * Re-authenticate an exact checkpoint for a compatible recording-only candidate.
 * Only recordingHash and randomReplaySpec are allowed to change. The original seed,
 * actual GAMEFILES identity, EditConfig identity, and timing mode remain frozen.
 */
export async function rebindCheckpointForRecordingCandidateV1(
  checkpoint,
  sourceRecording,
  candidateRecording,
) {
  const proof = await proveCheckpointCandidateCompatibilityV1(
    checkpoint,
    sourceRecording,
    candidateRecording,
  );
  if (proof.status !== 'CHECKPOINT_CANDIDATE_COMPATIBLE') return proof;

  const context = Object.freeze({
    seed: Number(checkpoint.context?.seed) | 0,
    gameHash: String(checkpoint.context?.gameHash ?? ''),
    gameBytes: Number(checkpoint.context?.gameBytes),
    editConfigHash: String(checkpoint.context?.editConfigHash ?? ''),
    recordingHash: proof.candidateRecordingHash,
    randomReplaySpec: proof.candidateRandomReplaySpec,
    recordedExternalTiming: checkpoint.context?.recordedExternalTiming === true,
  });

  const reboundBase = {
    ...checkpoint,
    context,
  };
  delete reboundBase.hash;

  const rebound = Object.freeze({
    ...reboundBase,
    hash: await hashCertificationCheckpointV1(reboundBase),
  });

  return Object.freeze({
    status: 'CHECKPOINT_CANDIDATE_REBOUND',
    proof,
    checkpoint: rebound,
  });
}

export const CheckpointCompatibilityLayout = Object.freeze({
  CHECKPOINT_SCHEMA,
  RECORDING_SCHEMA,
});
