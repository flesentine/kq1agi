#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1h_checkpoint_probe.py /path/to/certification-agile-gdx')

root = Path(sys.argv[1]).resolve()
saved_games = root / 'core/src/main/java/com/agifans/agile/SavedGames.java'
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
store = root / 'core/src/main/java/com/agifans/agile/CertificationCheckpointStore.java'

for path in (saved_games, commands, interpreter, worker):
    if not path.exists():
        raise RuntimeError(f'missing Phase -1H source: {path}')

def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)

store.write_text(r'''package com.agifans.agile;

import com.agifans.agile.SavedGames.SavedGame;

/**
 * Certification-only one-shot checkpoint store. It never touches platform storage.
 *
 * Capture mode starts empty so SavedGames chooses slot 1 without UI. Restore mode
 * reports all twelve slots as existing to avoid SavedGames' simple-restore sparse
 * array path; only slot 1 carries the checkpoint description that is selected.
 */
public class CertificationCheckpointStore implements SavedGameStore {
    public static final String DESCRIPTION = "__KQ1_CERT_CHECKPOINT__";
    private byte[] checkpointData;
    private final boolean restoreMode;

    public CertificationCheckpointStore() {
        restoreMode = false;
    }

    public CertificationCheckpointStore(byte[] checkpointData) {
        restoreMode = true;
        this.checkpointData = copyBytes(checkpointData);
    }

    private byte[] copyBytes(byte[] source) {
        if (source == null) return null;
        byte[] copy = new byte[source.length];
        if (source.length > 0) System.arraycopy(source, 0, copy, 0, source.length);
        return copy;
    }

    private SavedGame slot(int num) {
        SavedGame game = new SavedGame();
        game.num = num;
        game.fileName = "\\CertificationCheckpoint\\CHECKPOINT." + num;
        game.fileTime = num;
        game.description = (num == 1 ? DESCRIPTION : "__KQ1_CERT_DUMMY_" + num + "__");
        game.exists = restoreMode;
        game.savedGameData = checkpointData == null ? new byte[0] : copyBytes(checkpointData);
        return game;
    }

    @Override
    public boolean createFolderForGame(String gameId) {
        return true;
    }

    @Override
    public String getFolderNameForGame(String gameId) {
        return "\\CertificationCheckpoint";
    }

    @Override
    public SavedGame getSavedGameByNumber(String gameId, int num) {
        return slot(num);
    }

    @Override
    public boolean saveGame(SavedGame savedGame, byte[] savedGameData, int length) {
        int safeLength = Math.max(0, Math.min(length, savedGameData == null ? 0 : savedGameData.length));
        checkpointData = new byte[safeLength];
        if (safeLength > 0) System.arraycopy(savedGameData, 0, checkpointData, 0, safeLength);
        return true;
    }

    public byte[] getCheckpointData() {
        return copyBytes(checkpointData);
    }
}
''')

s = saved_games.read_text()
if 'captureCertificationCheckpoint()' not in s:
    anchor = '''    /**
     * Saves the GameState of the Interpreter to a saved game file.
     */
    public void saveGameState() {
'''
    methods = r'''    /**
     * Capture the existing AGI save-game reconstruction payload without opening a
     * dialog and without touching the player's SavedGameStore. This is only the
     * reconstruction backbone for the Phase -1H probe; exactness is established by
     * a post-restore semantic-digest comparison, not assumed from this payload.
     */
    public byte[] captureCertificationCheckpoint() {
        // Sierra save serialization requires a current Picture. A certification
        // barrier before the first draw.pic is valid runtime state but is not yet
        // reconstructable through this save-game backbone.
        if (state.currentPicture == null) return null;
        SavedGameStore originalStore = savedGameStore;
        boolean originalFirstTime = firstTime;
        String originalSimpleName = state.simpleName;
        CertificationCheckpointStore checkpointStore = new CertificationCheckpointStore();
        try {
            savedGameStore = checkpointStore;
            firstTime = false;
            state.simpleName = CertificationCheckpointStore.DESCRIPTION;
            saveGameState();
            return checkpointStore.getCheckpointData();
        } finally {
            savedGameStore = originalStore;
            firstTime = originalFirstTime;
            state.simpleName = originalSimpleName;
        }
    }

    /**
     * Destructively restore a certification checkpoint into this interpreter. The
     * caller must run this only while the worker is idle. Ordinary save files are not
     * claimed to be exact checkpoints; Phase -1H immediately republishes semantic-v1
     * after this call and rejects any round-trip mismatch.
     */
    public boolean restoreCertificationCheckpoint(byte[] checkpointData) {
        if (checkpointData == null || checkpointData.length == 0) return false;
        SavedGameStore originalStore = savedGameStore;
        boolean originalFirstTime = firstTime;
        String originalSimpleName = state.simpleName;
        try {
            savedGameStore = new CertificationCheckpointStore(checkpointData);
            firstTime = false;
            state.simpleName = CertificationCheckpointStore.DESCRIPTION;
            return restoreGameState();
        } finally {
            savedGameStore = originalStore;
            firstTime = originalFirstTime;
            // Do not force originalSimpleName back into GameState: restoreGameState()
            // owns restored game semantics. The probe must expose any simpleName loss
            // through semantic digest v1 rather than masking it.
        }
    }

'''
    if anchor not in s:
        raise RuntimeError('SavedGames checkpoint insertion anchor not found')
    s = s.replace(anchor, methods + anchor, 1)
saved_games.write_text(s)

c = commands.read_text()
if 'captureCertificationCheckpoint()' not in c:
    anchor = '''    /**
     * Draws the AGI Picture identified by the given picture number.
'''
    methods = r'''    public byte[] captureCertificationCheckpoint() {
        return savedGames.captureCertificationCheckpoint();
    }

    public boolean restoreCertificationCheckpoint(byte[] checkpointData) {
        if (!savedGames.restoreCertificationCheckpoint(checkpointData)) return false;

        // Match the normal restore.game command's reconstruction path. SavedGames
        // restores the serialized fields and script transcript; Commands owns the
        // replay that rebuilds currentPicture/resources and the visible interpreter
        // state that future cycles depend on.
        soundPlayer.reset();
        menu.enableAllMenus();
        replayScriptEvents();
        showPicture(false);
        textGraphics.updateStatusLine();
        return true;
    }

'''
    if anchor not in c:
        raise RuntimeError('Commands checkpoint insertion anchor not found')
    c = c.replace(anchor, methods + anchor, 1)
commands.write_text(c)

i = interpreter.read_text()
if 'captureCertificationCheckpoint()' not in i:
    anchor = '''    /**
     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a
'''
    methods = r'''    public byte[] captureCertificationCheckpoint() {
        return commands.captureCertificationCheckpoint();
    }

    public boolean restoreCertificationCheckpoint(byte[] checkpointData) {
        return commands.restoreCertificationCheckpoint(checkpointData);
    }

'''
    if anchor not in i:
        raise RuntimeError('Interpreter checkpoint insertion anchor not found')
    i = i.replace(anchor, methods + anchor, 1)
interpreter.write_text(i)

w = worker.read_text()
if 'certificationCheckpointData' not in w:
    anchor = '    private int certificationSeed;\n'
    if anchor not in w:
        raise RuntimeError('worker certification seed field not found')
    w = w.replace(anchor, anchor + '    private byte[] certificationCheckpointData;\n', 1)

# Phase -1B snapshot transport uses 10 slots. Phase -1H adds request/ack/status
# slots 10..12 and therefore requires at least 13 Uint32 entries.
if 'certificationDigestBytes >= 40' in w:
    w = one(w,
        '                if (certificationDigestBytes >= 40 && (certificationDigestBytes & 3) == 0)\n',
        '                if (certificationDigestBytes >= 52 && (certificationDigestBytes & 3) == 0)\n',
        'checkpoint digest size gate')
elif 'certificationDigestBytes >= 52' not in w:
    raise RuntimeError('checkpoint digest size gate anchor not found')

poll = '                publishCertificationSnapshotIfRequested();\n'
if 'serviceCertificationCheckpointProbe();' not in w:
    if w.count(poll) < 1:
        raise RuntimeError('checkpoint idle poll anchor not found')
    w = w.replace(poll, poll + '                serviceCertificationCheckpointProbe();\n', 1)

method_anchor = '    private void publishCertificationSnapshotIfRequested() {\n'
if 'private void serviceCertificationCheckpointProbe()' not in w:
    method = r'''    /**
     * Phase -1H probe transport. Requests are packed as (epoch << 2) | action:
     * action 1 captures a worker-local checkpoint, action 2 restores that same
     * checkpoint. Keeping the payload worker-local lets the first slice prove the
     * semantic round trip before defining a cross-worker serialization format.
     */
    private void serviceCertificationCheckpointProbe() {
        if (!certificationMode || certificationDigest == null || interpreter == null) return;
        int request = certificationDigest.get(10);
        int acknowledgement = certificationDigest.get(11);
        if (request == 0 || request == acknowledgement) return;

        int action = request & 3;
        int status = 0;
        try {
            if (action == 1) {
                certificationCheckpointData = interpreter.captureCertificationCheckpoint();
                status = (certificationCheckpointData != null && certificationCheckpointData.length > 0) ? 1 : 4;
            } else if (action == 2) {
                if (certificationCheckpointData == null || certificationCheckpointData.length == 0) {
                    status = 3;
                } else {
                    boolean restored = interpreter.restoreCertificationCheckpoint(certificationCheckpointData);
                    if (restored) {
                        lastTotalTickCount = variableData.getTotalTicks();
                        publishDiagnosticTrace();
                        status = 2;
                    } else {
                        status = 3;
                    }
                }
            } else {
                status = 3;
            }
        } catch (Throwable checkpointError) {
            status = 3;
        }

        certificationDigest.set(12, status);
        certificationDigest.set(11, request);
    }

'''
    if method_anchor not in w:
        raise RuntimeError('checkpoint worker method anchor not found')
    w = w.replace(method_anchor, method + method_anchor, 1)
worker.write_text(w)

print('Phase -1H checkpoint probe installed: noninteractive worker-local capture/restore + shared request/ack/status transport')
