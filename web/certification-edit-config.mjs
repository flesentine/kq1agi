const SCHEMA = 'kq1agi-edit-config-v1';
const PREF_PREFIX = 'agi-scene-mask-editor-v3:';
const WIDTH = 160;
const HEIGHT = 168;
const WORDS_PER_MASK = Math.ceil((WIDTH * HEIGHT) / 32); // 840
const MASK_HEX_LENGTH = HEIGHT * (WIDTH / 4); // 6720

const SLOT = Object.freeze({
  CURROOM: 0,
  IN_TICK: 517,
  ENABLED: 519,
  ROOM: 520,
  OCCLUDER_ACTIVE: 521,
  PAINT_MODE: 522,
  WATER_ACTIVE: 523,
  MASK_BASE: 524,
  VISUAL_OFFSET_COUNT: 3981,
  VISUAL_OFFSETS: 3982,
  VISUAL_OFFSET_MAX: 32,
  VISUAL_OFFSET_FIELDS: 5,
  FALL_ACTIVE: 4142,
  FALL_BASE: 4143,
  CONTROL_SEED_STATE: 4983,
  SCRIPT_FALL_BASE: 4984,
  SCRIPT_DANGER_SEED_STATE: 5824,
});

const ROOM_KEYS = Object.freeze([
  ['occluder', 's'], ['collision', 's'], ['behind', 's'], ['water', 's'],
  ['fall', 's'], ['scriptFall', 's'], ['active', 'b'], ['waterActive', 'b'],
  ['fallActive', 'b'], ['unifiedControlV1', 'b'], ['scriptFallDetectorVersion', 'i'],
]);

function storageGet(storage, logicalKey, type) {
  if (!storage || typeof storage.getItem !== 'function') return null;
  return storage.getItem(`${PREF_PREFIX}${logicalKey}${type}`);
}

function readBool(storage, logicalKey, fallback = false) {
  const value = storageGet(storage, logicalKey, 'b');
  return value == null ? fallback : value === 'true';
}

function readInt(storage, logicalKey, fallback = 0) {
  const value = storageGet(storage, logicalKey, 'i');
  if (value == null) return fallback;
  const parsed = Number.parseInt(value, 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function readString(storage, logicalKey, fallback = '') {
  const value = storageGet(storage, logicalKey, 's');
  return value == null ? fallback : value;
}

function hasRoomPreference(storage, room) {
  return ROOM_KEYS.some(([key, type]) => storageGet(storage, `room_${room}_${key}`, type) != null);
}

function normalizeMaskHex(value) {
  const text = String(value ?? '').trim().toLowerCase();
  if (!text) return '';
  if (text.length !== MASK_HEX_LENGTH || !/^[0-9a-f]+$/.test(text)) {
    throw new Error(`Invalid EditConfig mask: expected ${MASK_HEX_LENGTH} hexadecimal nibbles, got ${text.length}.`);
  }
  return text;
}

function maskBase(layer) {
  if (layer === 4) return SLOT.FALL_BASE;
  if (layer === 5) return SLOT.SCRIPT_FALL_BASE;
  if (layer >= 0 && layer <= 3) return SLOT.MASK_BASE + (layer * WORDS_PER_MASK);
  throw new RangeError(`Unknown EditConfig mask layer ${layer}.`);
}

function readWord(vars, index) {
  return Number(vars[index]) >>> 0;
}

function writeWord(vars, index, value) {
  if (typeof SharedArrayBuffer !== 'undefined' && vars?.buffer instanceof SharedArrayBuffer) {
    Atomics.store(vars, index, value | 0);
  } else {
    vars[index] = value | 0;
  }
}

export function encodeMaskWords(vars, layer) {
  const base = maskBase(layer);
  let out = '';
  for (let y = 0; y < HEIGHT; y += 1) {
    for (let x = 0; x < WIDTH; x += 4) {
      let nibble = 0;
      for (let bit = 0; bit < 4; bit += 1) {
        const bitIndex = (y * WIDTH) + x + bit;
        const word = readWord(vars, base + (bitIndex >>> 5));
        if ((word & (1 << (bitIndex & 31))) !== 0) nibble |= (1 << bit);
      }
      out += nibble.toString(16);
    }
  }
  return out;
}

export function decodeMaskHex(maskHex) {
  const text = normalizeMaskHex(maskHex);
  const words = new Uint32Array(WORDS_PER_MASK);
  if (!text) return words;
  let p = 0;
  for (let y = 0; y < HEIGHT; y += 1) {
    for (let x = 0; x < WIDTH; x += 4) {
      const nibble = Number.parseInt(text[p++], 16);
      for (let bit = 0; bit < 4; bit += 1) {
        if ((nibble & (1 << bit)) === 0) continue;
        const bitIndex = (y * WIDTH) + x + bit;
        words[bitIndex >>> 5] |= (1 << (bitIndex & 31)) >>> 0;
      }
    }
  }
  return words;
}

function persistedRoom(storage, room) {
  if (!hasRoomPreference(storage, room)) return null;
  const prefix = `room_${room}_`;
  const unifiedControl = readBool(storage, `${prefix}unifiedControlV1`, false);
  const scriptFallVersion = readInt(storage, `${prefix}scriptFallDetectorVersion`, 0);
  return {
    room,
    enabled: readBool(storage, `${prefix}active`, false),
    waterActive: readBool(storage, `${prefix}waterActive`, false),
    fallActive: readBool(storage, `${prefix}fallActive`, false),
    controlSeedState: unifiedControl ? room + 1 : -(room + 1),
    scriptDangerSeedState: scriptFallVersion >= 4 ? room + 1 : -(room + 1),
    masks: [
      readString(storage, `${prefix}occluder`, ''),
      readString(storage, `${prefix}collision`, ''),
      readString(storage, `${prefix}behind`, ''),
      readString(storage, `${prefix}water`, ''),
      readString(storage, `${prefix}fall`, ''),
      readString(storage, `${prefix}scriptFall`, ''),
    ].map(normalizeMaskHex),
  };
}

function parseVisualPins(text) {
  const pins = [];
  if (!text) return pins;
  for (const record of String(text).split(';')) {
    if (!record) continue;
    const fields = record.split(',').map(value => Number.parseInt(value, 10));
    if (fields.length !== SLOT.VISUAL_OFFSET_FIELDS || fields.some(value => !Number.isFinite(value))) continue;
    pins.push(fields.map(value => value | 0));
    if (pins.length >= SLOT.VISUAL_OFFSET_MAX) break;
  }
  return pins;
}

function captureLiveVisualPins(vars) {
  const count = Math.max(0, Math.min(SLOT.VISUAL_OFFSET_MAX, Number(vars[SLOT.VISUAL_OFFSET_COUNT]) | 0));
  const pins = [];
  for (let record = 0; record < count; record += 1) {
    const fields = [];
    for (let field = 0; field < SLOT.VISUAL_OFFSET_FIELDS; field += 1) {
      fields.push(Number(vars[SLOT.VISUAL_OFFSETS + (record * SLOT.VISUAL_OFFSET_FIELDS) + field]) | 0);
    }
    pins.push(fields);
  }
  return pins;
}

function captureLiveRoom(vars) {
  if (!vars || vars.length <= SLOT.SCRIPT_DANGER_SEED_STATE) return null;
  const room = Number(vars[SLOT.CURROOM]) & 0xff;
  const sceneRoom = Number(vars[SLOT.ROOM]) | 0;
  if (sceneRoom !== room && Number(vars[SLOT.ENABLED]) === 0) return null;
  return {
    room,
    enabled: Number(vars[SLOT.ENABLED]) !== 0 && sceneRoom === room,
    waterActive: Number(vars[SLOT.WATER_ACTIVE]) !== 0,
    fallActive: Number(vars[SLOT.FALL_ACTIVE]) !== 0,
    controlSeedState: Number(vars[SLOT.CONTROL_SEED_STATE]) | 0,
    scriptDangerSeedState: Number(vars[SLOT.SCRIPT_DANGER_SEED_STATE]) | 0,
    masks: Array.from({ length: 6 }, (_, layer) => encodeMaskWords(vars, layer)),
  };
}

function canonicalConfig(config) {
  return {
    schema: SCHEMA,
    rooms: [...(config.rooms ?? [])]
      .map(room => ({
        room: Number(room.room) & 0xff,
        enabled: !!room.enabled,
        waterActive: !!room.waterActive,
        fallActive: !!room.fallActive,
        controlSeedState: Number(room.controlSeedState) | 0,
        scriptDangerSeedState: Number(room.scriptDangerSeedState) | 0,
        masks: Array.from({ length: 6 }, (_, layer) => normalizeMaskHex(room.masks?.[layer] ?? '')),
      }))
      .sort((a, b) => a.room - b.room),
    visualPins: (config.visualPins ?? []).slice(0, SLOT.VISUAL_OFFSET_MAX).map(pin =>
      Array.from({ length: SLOT.VISUAL_OFFSET_FIELDS }, (_, index) => Number(pin?.[index] ?? 0) | 0)),
  };
}

export function canonicalizeEditConfigV1(config) {
  const canonical = canonicalConfig(config ?? {});
  return Object.freeze({
    ...canonical,
    rooms: Object.freeze(canonical.rooms.map(room => Object.freeze({
      ...room,
      masks: Object.freeze([...room.masks]),
    }))),
    visualPins: Object.freeze(canonical.visualPins.map(pin => Object.freeze([...pin]))),
  });
}

function fallbackHash(bytes) {
  let hash = 0x811c9dc5;
  for (const byte of bytes) hash = Math.imul(hash ^ byte, 0x01000193) >>> 0;
  return `fnv1a32:${hash.toString(16).padStart(8, '0')}`;
}

export async function hashEditConfigV1(config) {
  const canonical = JSON.stringify(canonicalConfig(config));
  const bytes = new TextEncoder().encode(canonical);
  const cryptoObject = globalThis.crypto;
  if (cryptoObject?.subtle?.digest) {
    const digest = new Uint8Array(await cryptoObject.subtle.digest('SHA-256', bytes));
    return `sha256:${Array.from(digest, byte => byte.toString(16).padStart(2, '0')).join('')}`;
  }
  return fallbackHash(bytes);
}

export async function captureEditConfigV1(options = {}) {
  const storage = options.storage ?? globalThis.localStorage ?? null;
  const liveSharedBuffer = options.liveSharedBuffer ?? globalThis.__kq1agiVariableSAB ?? null;
  const roomMap = new Map();

  for (let room = 0; room <= 255; room += 1) {
    const persisted = persistedRoom(storage, room);
    if (persisted) roomMap.set(room, persisted);
  }

  let visualPins = parseVisualPins(readString(storage, 'visualPinsV1', ''));
  if (liveSharedBuffer && liveSharedBuffer.byteLength >= 8353 * 4) {
    const vars = new Int32Array(liveSharedBuffer);
    const liveRoom = captureLiveRoom(vars);
    if (liveRoom) roomMap.set(liveRoom.room, liveRoom);
    visualPins = captureLiveVisualPins(vars);
  }

  const config = canonicalConfig({ rooms: [...roomMap.values()], visualPins });
  return Object.freeze({ ...config, hash: await hashEditConfigV1(config) });
}

function clearMask(vars, layer) {
  const base = maskBase(layer);
  for (let i = 0; i < WORDS_PER_MASK; i += 1) writeWord(vars, base + i, 0);
}

function applyMask(vars, layer, text) {
  clearMask(vars, layer);
  const words = decodeMaskHex(text);
  const base = maskBase(layer);
  for (let i = 0; i < words.length; i += 1) writeWord(vars, base + i, words[i]);
}

export function applyEditConfigVisualPins(config, vars) {
  if (!config || config.schema !== SCHEMA || !vars) return;
  const pins = (config.visualPins ?? []).slice(0, SLOT.VISUAL_OFFSET_MAX);
  writeWord(vars, SLOT.VISUAL_OFFSET_COUNT, pins.length);
  for (let record = 0; record < SLOT.VISUAL_OFFSET_MAX; record += 1) {
    for (let field = 0; field < SLOT.VISUAL_OFFSET_FIELDS; field += 1) {
      const value = record < pins.length ? Number(pins[record]?.[field] ?? 0) | 0 : 0;
      writeWord(vars, SLOT.VISUAL_OFFSETS + (record * SLOT.VISUAL_OFFSET_FIELDS) + field, value);
    }
  }
}

export function applyEditConfigRoom(config, vars, room) {
  if (!config || config.schema !== SCHEMA || !vars) return false;
  const roomNumber = Number(room) & 0xff;
  const entry = (config.rooms ?? []).find(candidate => (Number(candidate.room) & 0xff) === roomNumber);

  writeWord(vars, SLOT.PAINT_MODE, 0);
  writeWord(vars, SLOT.OCCLUDER_ACTIVE, 0);
  if (!entry) {
    writeWord(vars, SLOT.ENABLED, 0);
    writeWord(vars, SLOT.ROOM, roomNumber);
    writeWord(vars, SLOT.WATER_ACTIVE, 0);
    writeWord(vars, SLOT.FALL_ACTIVE, 0);
    writeWord(vars, SLOT.CONTROL_SEED_STATE, 0);
    writeWord(vars, SLOT.SCRIPT_DANGER_SEED_STATE, 0);
    for (let layer = 0; layer < 6; layer += 1) clearMask(vars, layer);
    return false;
  }

  writeWord(vars, SLOT.ROOM, roomNumber);
  writeWord(vars, SLOT.ENABLED, entry.enabled ? 1 : 0);
  writeWord(vars, SLOT.WATER_ACTIVE, entry.waterActive ? 1 : 0);
  writeWord(vars, SLOT.FALL_ACTIVE, entry.fallActive ? 1 : 0);
  writeWord(vars, SLOT.CONTROL_SEED_STATE, Number(entry.controlSeedState) | 0);
  writeWord(vars, SLOT.SCRIPT_DANGER_SEED_STATE, Number(entry.scriptDangerSeedState) | 0);
  for (let layer = 0; layer < 6; layer += 1) applyMask(vars, layer, entry.masks?.[layer] ?? '');
  return true;
}

export function createEditConfigApplicator(config) {
  let visualPinsApplied = false;
  let appliedRoom = null;
  return host => {
    const vars = host?.edited?.vars;
    const truthVars = host?.truth?.vars;
    if (!vars || !config || config.schema !== SCHEMA) return { applied: false, room: null };
    const room = readWord(vars, SLOT.CURROOM) & 0xff;
    // Never mutate the edited lane's shared editor state while either interpreter
    // is inside a cycle. Room/config changes are staged only at a common idle barrier.
    if (readWord(vars, SLOT.IN_TICK) !== 0 || (truthVars && readWord(truthVars, SLOT.IN_TICK) !== 0)) {
      return { applied: false, room, deferred: true };
    }
    if (!visualPinsApplied) {
      applyEditConfigVisualPins(config, vars);
      visualPinsApplied = true;
    }
    if (room !== appliedRoom) {
      const hasConfig = applyEditConfigRoom(config, vars, room);
      appliedRoom = room;
      return { applied: true, room, hasConfig };
    }
    return { applied: false, room, hasConfig: (config.rooms ?? []).some(entry => (Number(entry.room) & 0xff) === room) };
  };
}

export const EditConfigLayout = Object.freeze({
  SCHEMA, PREF_PREFIX, WIDTH, HEIGHT, WORDS_PER_MASK, MASK_HEX_LENGTH, SLOT,
});
