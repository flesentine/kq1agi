import assert from 'node:assert/strict';
import {
  discoverImportedGames,
  divergenceCategory,
  formatCertificationResult,
  readImportedGame,
  runCertificationSession,
} from '../web/certification-panel.mjs';

function notFound() {
  const error = new Error('not found');
  error.name = 'NotFoundError';
  return error;
}

function fakeDirectory(files = {}) {
  return {
    kind: 'directory',
    async getFileHandle(name) {
      if (!(name in files)) throw notFound();
      const bytes = files[name];
      return {
        async getFile() {
          return {
            size: bytes,
            async arrayBuffer() { return new ArrayBuffer(bytes); },
          };
        },
      };
    },
  };
}

const alphaGame = fakeDirectory({ 'GAMEFILES.DAT': 2000 });
const zetaGame = fakeDirectory({ 'GAMEFILES.DAT': 5000 });
const emptyGame = fakeDirectory({ 'GAMEFILES.DAT': 0 });
const gameFiles = {
  async *entries() {
    yield ['zeta-game', zetaGame];
    yield ['empty-game', emptyGame];
    yield ['not-a-dir', { kind: 'file' }];
    yield ['alpha-game', alphaGame];
  },
  async getDirectoryHandle(name) {
    if (name === 'alpha-game') return alphaGame;
    if (name === 'zeta-game') return zetaGame;
    if (name === 'empty-game') return emptyGame;
    throw notFound();
  },
};
const root = {
  async getDirectoryHandle(name) {
    assert.equal(name, 'Game Files');
    return gameFiles;
  },
};

assert.deepEqual(await discoverImportedGames(root), [
  { directoryName: 'alpha-game', size: 2000 },
  { directoryName: 'zeta-game', size: 5000 },
]);
assert.equal((await readImportedGame('alpha-game', root)).byteLength, 2000);
await assert.rejects(readImportedGame('empty-game', root), /empty GAMEFILES\.DAT/);
await assert.rejects(readImportedGame('', root), /Choose an imported game/);
assert.deepEqual(await discoverImportedGames({
  async getDirectoryHandle() { throw notFound(); },
}), []);

assert.equal(divergenceCategory({ status: 'DIVERGED', reason: 'trace', index: 4 }), 'trace:ego-y');
assert.equal(divergenceCategory({ status: 'DIVERGED', reason: 'semantic-digest', index: 2 }), 'digest:animated-objects');
assert.equal(divergenceCategory({ status: 'DIVERGED', reason: 'random-stream', index: 5 }), 'digest:random-stream');
assert.equal(divergenceCategory({ status: 'DIVERGED', reason: 'quit-state' }), 'terminal-state');

const formatted = formatCertificationResult({
  status: 'MATCH', scope: 'semantic-v1', tick: 7, cycle: 1,
  room: 1, x: 50, y: 100, randomDraws: 3, digest: [1, 2, 3, 4],
});
assert.match(formatted, /status=MATCH/);
assert.match(formatted, /room=1/);
assert.match(formatted, /0x00000001/);

class FakeHost {
  constructor(results) { this.results = [...results]; }
  async pulse() {
    if (!this.results.length) throw new Error('fake host exhausted');
    return this.results.shift();
  }
}

let summary = await runCertificationSession(new FakeHost([
  { status: 'BUSY', tick: 1 },
  { status: 'MATCH', tick: 2 },
  { status: 'MATCH', tick: 3 },
]), { targetBarriers: 2, maxBusyPulses: 5 });
assert.equal(summary.status, 'MATCH_LIMIT');
assert.equal(summary.barriers, 2);

summary = await runCertificationSession(new FakeHost([
  { status: 'MATCH', tick: 1 },
  { status: 'DIVERGED', tick: 2, reason: 'semantic-digest', index: 1, truth: 3, edited: 4 },
]), { targetBarriers: 5 });
assert.equal(summary.status, 'DIVERGED');
assert.equal(summary.firstDivergence.tick, 2);

summary = await runCertificationSession(new FakeHost([
  { status: 'BUSY', tick: 1 },
  { status: 'BUSY', tick: 2 },
  { status: 'BUSY', tick: 3 },
]), { targetBarriers: 5, maxBusyPulses: 3 });
assert.equal(summary.status, 'WAITING');
assert.equal(summary.busyPulses, 3);

summary = await runCertificationSession(new FakeHost([
  { status: 'COMPLETE', tick: 9, scope: 'semantic-v1' },
]), { targetBarriers: 5 });
assert.equal(summary.status, 'COMPLETE');

summary = await runCertificationSession(new FakeHost([]), {
  shouldStop: () => true,
});
assert.equal(summary.status, 'STOPPED');
assert.equal(summary.pulses, 0);

console.log('certification panel tests: PASS');
