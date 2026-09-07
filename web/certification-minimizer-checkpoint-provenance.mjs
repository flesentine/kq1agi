import {
  hashCanonicalJsonV1,
  MinimizerCheckpointEvidenceLayout,
} from './certification-minimizer-checkpoint-evidence.mjs';
import {
  validateMinimizerCheckpointEvidenceArtifactV1,
} from './certification-minimizer-checkpoint-corpus.mjs';

const PROVENANCE_SCHEMA = 'kq1agi-minimizer-checkpoint-collection-provenance-v1';
const EVENT_SCHEMA = 'kq1agi-minimizer-checkpoint-collection-event-v1';
const POLICY = MinimizerCheckpointEvidenceLayout.POLICY;
const RUN_ID_PREFIX = 'kq1agi-collection-run-v1:';
const RUN_ID_RE = /^kq1agi-collection-run-v1:[0-9a-f]{32}$/;
const MAX_EVENTS = 4096;
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
      throw new Error(`Collection provenance contains forbidden raw oracle field at ${path}.${key}.`);
    }
    rejectForbiddenKeys(item, `${path}.${key}`);
  }
}

function hex(bytes) {
  return [...bytes].map(value => value.toString(16).padStart(2, '0')).join('');
}

export function createMinimizerCheckpointCollectionRunIdV1() {
  if (!globalThis.crypto?.getRandomValues) {
    throw new Error('Crypto.getRandomValues is required for collection provenance.');
  }
  const bytes = new Uint8Array(16);
  globalThis.crypto.getRandomValues(bytes);
  return `${RUN_ID_PREFIX}${hex(bytes)}`;
}

export async function createMinimizerCheckpointCollectionEventV1({
  collectionRunId,
  ordinal,
  stageHash,
} = {}) {
  const runId = String(collectionRunId ?? '');
  const eventOrdinal = Number(ordinal);
  const hash = String(stageHash ?? '');
  if (!RUN_ID_RE.test(runId)) throw new Error('Collection provenance run ID is invalid.');
  if (!Number.isSafeInteger(eventOrdinal) || eventOrdinal < 0 || eventOrdinal >= MAX_EVENTS) {
    throw new Error('Collection provenance event ordinal is invalid.');
  }
  if (!isSha256(hash)) throw new Error('Collection provenance stage hash is invalid.');

  const unsigned = {
    schema: EVENT_SCHEMA,
    collectionRunId: runId,
    ordinal: eventOrdinal,
    stageHash: hash,
  };
  const eventHash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, eventHash });
}

async function validateEventV1(event, expectedRunId, expectedOrdinal, reportStageHashes) {
  if (!isObject(event) || event.schema !== EVENT_SCHEMA) {
    throw new Error('Collection provenance event schema mismatch.');
  }
  if (event.collectionRunId !== expectedRunId) {
    throw new Error('Collection provenance event run ID mismatch.');
  }
  if (event.ordinal !== expectedOrdinal) {
    throw new Error('Collection provenance event ordinal sequence mismatch.');
  }
  if (!isSha256(event.stageHash) || !reportStageHashes.has(event.stageHash)) {
    throw new Error('Collection provenance event references a stage outside its evidence report.');
  }
  if (!isSha256(event.eventHash)) {
    throw new Error('Collection provenance event hash is invalid.');
  }
  const expected = await createMinimizerCheckpointCollectionEventV1({
    collectionRunId: event.collectionRunId,
    ordinal: event.ordinal,
    stageHash: event.stageHash,
  });
  if (expected.eventHash !== event.eventHash) {
    throw new Error('Collection provenance event hash mismatch.');
  }
}

export async function createMinimizerCheckpointCollectionProvenanceV1({
  collectionRunId,
  evidenceReport,
  events = [],
} = {}) {
  const runId = String(collectionRunId ?? '');
  if (!RUN_ID_RE.test(runId)) throw new Error('Collection provenance run ID is invalid.');
  if (evidenceReport?.schema !== MinimizerCheckpointEvidenceLayout.REPORT_SCHEMA) {
    throw new Error('Collection provenance requires a Phase -1I.4 evidence report.');
  }
  const validated = await validateMinimizerCheckpointEvidenceArtifactV1(evidenceReport);
  if (validated.kind !== 'report') {
    throw new Error('Collection provenance requires a Phase -1I.4 evidence report.');
  }
  if (!Array.isArray(events) || events.length === 0) {
    throw new Error('Collection provenance requires at least one live collection event.');
  }
  rejectForbiddenKeys(events);
  if (events.length > MAX_EVENTS) {
    throw new Error('Collection provenance exceeds the event safety limit.');
  }

  const reportStageHashes = new Set(
    (evidenceReport.stages ?? []).map(stage => String(stage.hash)),
  );
  const ordered = [...events].sort((a, b) => Number(a?.ordinal) - Number(b?.ordinal));
  for (let index = 0; index < ordered.length; index += 1) {
    await validateEventV1(ordered[index], runId, index, reportStageHashes);
  }

  const unsigned = {
    schema: PROVENANCE_SCHEMA,
    policy: POLICY,
    policyFrozen: false,
    policyDecision: 'EVIDENCE_ONLY',
    accelerationAllowed: false,
    provenanceDecision: 'COLLECTION_IDENTITY_ONLY',
    collectionRunId: runId,
    evidenceReportHash: String(evidenceReport.hash),
    eventCount: ordered.length,
    distinctStageHashes: [...new Set(ordered.map(event => event.stageHash))].sort(),
    events: Object.freeze(ordered),
    caveats: Object.freeze([
      'RUN_ID_MINTED_ONLY_ON_LIVE_BROWSER_SESSION',
      'IMPORTED_EVIDENCE_DOES_NOT_MINT_COLLECTION_EVENTS',
      'PROVENANCE_DISTINGUISHES_TOOL_COLLECTION_EVENTS_NOT_PHYSICAL_INDEPENDENCE',
      'FULL_REPLAY_REMAINS_MANDATORY',
    ]),
  };
  const hash = await hashCanonicalJsonV1(unsigned);
  return Object.freeze({ ...unsigned, hash });
}

export async function validateMinimizerCheckpointCollectionProvenanceV1(
  provenance,
  evidenceReport,
) {
  if (!isObject(provenance)) throw new Error('Collection provenance must be an object.');
  rejectForbiddenKeys(provenance);
  if (provenance.schema !== PROVENANCE_SCHEMA) {
    throw new Error('Collection provenance schema mismatch.');
  }
  if (provenance.policy !== POLICY
      || provenance.policyFrozen !== false
      || provenance.policyDecision !== 'EVIDENCE_ONLY'
      || provenance.accelerationAllowed !== false
      || provenance.provenanceDecision !== 'COLLECTION_IDENTITY_ONLY') {
    throw new Error('Collection provenance changes the evidence-only replay policy.');
  }
  if (!RUN_ID_RE.test(String(provenance.collectionRunId ?? ''))) {
    throw new Error('Collection provenance run ID is invalid.');
  }
  const expected = await createMinimizerCheckpointCollectionProvenanceV1({
    collectionRunId: provenance.collectionRunId,
    evidenceReport,
    events: provenance.events,
  });
  if (expected.evidenceReportHash !== provenance.evidenceReportHash) {
    throw new Error('Collection provenance evidence report hash mismatch.');
  }
  if (expected.eventCount !== provenance.eventCount) {
    throw new Error('Collection provenance event count mismatch.');
  }
  if ((await hashCanonicalJsonV1(expected.distinctStageHashes))
      !== (await hashCanonicalJsonV1(provenance.distinctStageHashes))) {
    throw new Error('Collection provenance distinct stage hashes mismatch.');
  }
  if (expected.hash !== provenance.hash) {
    throw new Error('Collection provenance hash mismatch.');
  }
  return Object.freeze({
    valid: true,
    hash: provenance.hash,
    collectionRunId: provenance.collectionRunId,
    eventCount: provenance.eventCount,
  });
}

export function serializeMinimizerCheckpointCollectionProvenanceV1(provenance) {
  if (provenance?.schema !== PROVENANCE_SCHEMA || !isSha256(provenance?.hash)) {
    throw new TypeError('A complete Phase -1I.9 collection provenance artifact is required.');
  }
  return `${JSON.stringify(provenance, null, 2)}\n`;
}

export const MinimizerCheckpointProvenanceLayout = Object.freeze({
  PROVENANCE_SCHEMA,
  EVENT_SCHEMA,
  POLICY,
  RUN_ID_PREFIX,
  MAX_EVENTS,
});
