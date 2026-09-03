import assert from 'node:assert/strict';
import {
  applyEditConfigRoom,
  applyEditConfigVisualPins,
  captureEditConfigV1,
  createEditConfigApplicator,
  decodeMaskHex,
  EditConfigLayout,
  encodeMaskWords,
  hashEditConfigV1,
} from '../web/certification-edit-config.mjs';

class MemoryStorage {
  constructor(entries = {}) { this.map = new Map(Object.entries(entries)); }
  getItem(key) { return this.map.has(key) ? this.map.get(key) : null; }
  setItem(key, value) { this.map.set(key, String(value)); }
}

const { PREF_PREFIX, MASK_HEX_LENGTH, SLOT } = EditConfigLayout;
const emptyMask = '0'.repeat(MASK_HEX_LENGTH);
const markedMask = `1${'0'.repeat(MASK_HEX_LENGTH - 2)}8`;
const storage = new MemoryStorage({
  [`${PREF_PREFIX}room_1_occluders`]: markedMask,
  [`${PREF_PREFIX}room_1_collisions`]: emptyMask,
  [`${PREF_PREFIX}room_1_behinds`]: emptyMask,
  [`${PREF_PREFIX}room_1_waters`]: emptyMask,
  [`${PREF_PREFIX}room_1_falls`]: emptyMask,
  [`${PREF_PREFIX}room_1_scriptFalls`]: emptyMask,
  [`${PREF_PREFIX}room_1_activeb`]: 'true',
  [`${PREF_PREFIX}room_1_waterActiveb`]: 'false',
  [`${PREF_PREFIX}room_1_fallActiveb`]: 'true',
  [`${PREF_PREFIX}room_1_unifiedControlV1b`]: 'true',
  [`${PREF_PREFIX}room_1_scriptFallDetectorVersioni`]: '4',
  [`${PREF_PREFIX}visualPinsV1s`]: '1,2,3,-4,5;2,7,8,9,-10',
});

const persisted = await captureEditConfigV1({ storage, liveSharedBuffer: null });
assert.equal(persisted.schema, 'kq1agi-edit-config-v1');
assert.equal(persisted.rooms.length, 1);
assert.equal(persisted.rooms[0].room, 1);
assert.equal(persisted.rooms[0].enabled, true);
assert.equal(persisted.rooms[0].fallActive, true);
assert.equal(persisted.rooms[0].controlSeedState, 2);
assert.equal(persisted.rooms[0].scriptDangerSeedState, 2);
assert.deepEqual(persisted.visualPins, [[1, 2, 3, -4, 5], [2, 7, 8, 9, -10]]);
assert.match(persisted.hash, /^(sha256:[0-9a-f]{64}|fnv1a32:[0-9a-f]{8})$/);
assert.equal(await hashEditConfigV1(persisted), persisted.hash);

const decoded = decodeMaskHex(markedMask);
assert.equal(decoded[0] & 1, 1);
const lastBit = (160 * 168) - 1;
assert.notEqual(decoded[lastBit >>> 5] & (1 << (lastBit & 31)), 0);

const applied = new Int32Array(8353);
applyEditConfigVisualPins(persisted, applied);
assert.equal(applied[SLOT.VISUAL_OFFSET_COUNT], 2);
assert.equal(applied[SLOT.VISUAL_OFFSETS + 3], -4);
assert.equal(applyEditConfigRoom(persisted, applied, 1), true);
assert.equal(applied[SLOT.ENABLED], 1);
assert.equal(applied[SLOT.ROOM], 1);
assert.equal(applied[SLOT.FALL_ACTIVE], 1);
assert.equal(applied[SLOT.CONTROL_SEED_STATE], 2);
assert.equal(encodeMaskWords(applied, 0), markedMask);
assert.equal(applyEditConfigRoom(persisted, applied, 9), false);
assert.equal(applied[SLOT.ENABLED], 0);
assert.equal(applied[SLOT.ROOM], 9);
assert.equal(encodeMaskWords(applied, 0), emptyMask);

// A live current-room SharedArrayBuffer must override stale persisted data, including
// unsaved masks and visual offsets.
const live = new SharedArrayBuffer(8353 * 4);
const liveVars = new Int32Array(live);
liveVars[SLOT.CURROOM] = 1;
liveVars[SLOT.ROOM] = 1;
liveVars[SLOT.ENABLED] = 1;
liveVars[SLOT.WATER_ACTIVE] = 1;
liveVars[SLOT.FALL_ACTIVE] = 0;
liveVars[SLOT.CONTROL_SEED_STATE] = 99;
liveVars[SLOT.SCRIPT_DANGER_SEED_STATE] = 77;
liveVars[SLOT.MASK_BASE] = 2; // x=1 in layer 0, different from persisted x=0.
liveVars[SLOT.VISUAL_OFFSET_COUNT] = 1;
liveVars[SLOT.VISUAL_OFFSETS + 0] = 1;
liveVars[SLOT.VISUAL_OFFSETS + 1] = 9;
liveVars[SLOT.VISUAL_OFFSETS + 2] = 10;
liveVars[SLOT.VISUAL_OFFSETS + 3] = -11;
liveVars[SLOT.VISUAL_OFFSETS + 4] = 12;
const liveConfig = await captureEditConfigV1({ storage, liveSharedBuffer: live });
assert.equal(liveConfig.rooms.length, 1);
assert.equal(liveConfig.rooms[0].waterActive, true);
assert.equal(liveConfig.rooms[0].controlSeedState, 99);
assert.equal(liveConfig.rooms[0].scriptDangerSeedState, 77);
assert.equal(liveConfig.rooms[0].masks[0][0], '2');
assert.deepEqual(liveConfig.visualPins, [[1, 9, 10, -11, 12]]);
assert.notEqual(liveConfig.hash, persisted.hash);

await assert.rejects(
  captureEditConfigV1({ storage: new MemoryStorage({ [`${PREF_PREFIX}room_4_occluders`]: 'xyz' }), liveSharedBuffer: null }),
  /Invalid EditConfig mask/
);

// Bridge integration: the applicator writes only the edited lane, snapshots visual
// pins once, and switches room config before the next host pulse.
const truthVars = new Int32Array(8353);
const editedVars = new Int32Array(8353);
editedVars[SLOT.CURROOM] = 1;
const fakeHost = { truth: { vars: truthVars }, edited: { vars: editedVars } };
const room2 = { ...persisted.rooms[0], room: 2, enabled: false };
const bridgeConfig = { ...persisted, rooms: [persisted.rooms[0], room2] };
const applyConfig = createEditConfigApplicator(bridgeConfig);
let state = applyConfig(fakeHost);
assert.deepEqual(state, { applied: true, room: 1, hasConfig: true });
assert.equal(editedVars[SLOT.ENABLED], 1);
assert.equal(editedVars[SLOT.VISUAL_OFFSET_COUNT], 2);
assert.equal(truthVars[SLOT.ENABLED], 0);
assert.equal(truthVars[SLOT.VISUAL_OFFSET_COUNT], 0);
state = applyConfig(fakeHost);
assert.equal(state.applied, false);
editedVars[SLOT.CURROOM] = 2;
state = applyConfig(fakeHost);
assert.deepEqual(state, { applied: true, room: 2, hasConfig: true });
assert.equal(editedVars[SLOT.ROOM], 2);
assert.equal(editedVars[SLOT.ENABLED], 0);
assert.equal(truthVars[SLOT.ROOM], 0);

console.log('certification edit config tests: PASS');
