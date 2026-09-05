#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1h_checkpoint_probe.py /path/to/certification-agile-gdx')

root = Path(sys.argv[1]).resolve()
saved_games = root / 'core/src/main/java/com/agifans/agile/SavedGames.java'
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
picture = root / 'core/src/main/java/com/agifans/agile/agilib/Picture.java'
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
store = root / 'core/src/main/java/com/agifans/agile/CertificationCheckpointStore.java'
checkpoint_random = root / 'core/src/main/java/com/agifans/agile/CertificationCheckpointRandom.java'
certification_random = root / 'core/src/main/java/com/agifans/agile/CertificationRandom.java'
replay_random = root / 'core/src/main/java/com/agifans/agile/CertificationReplayRandom.java'

for path in (saved_games, commands, picture, interpreter, worker):
    if not path.exists():
        raise RuntimeError(f'missing Phase -1H source: {path}')

def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)

checkpoint_random.write_text(r'''package com.agifans.agile;

/** Random source whose exact certification draw position can be restored. */
public interface CertificationCheckpointRandom {
    public int getDrawCount();
    public void restoreCheckpointDrawCount(int drawCount);
}
''')

random_text = certification_random.read_text()
if 'implements CertificationCheckpointRandom' not in random_text:
    random_text = one(
        random_text,
        'public class CertificationRandom extends Random {',
        'public class CertificationRandom extends Random implements CertificationCheckpointRandom {',
        'certification random checkpoint interface',
    )
if 'private final long checkpointSeed;' not in random_text:
    random_text = one(
        random_text,
        '    private int drawCount;\n',
        '    private int drawCount;\n    private final long checkpointSeed;\n',
        'certification random checkpoint seed field',
    )
if 'checkpointSeed = seed;' not in random_text:
    random_text = one(
        random_text,
        '        super(seed);\n        drawCount = 0;\n',
        '        super(seed);\n        checkpointSeed = seed;\n        drawCount = 0;\n',
        'certification random checkpoint seed capture',
    )
if 'restoreCheckpointDrawCount' not in random_text:
    random_text = one(
        random_text,
        '''    public int getDrawCount() {
        return drawCount;
    }
''',
        '''    public int getDrawCount() {
        return drawCount;
    }

    @Override
    public void restoreCheckpointDrawCount(int targetDrawCount) {
        if (targetDrawCount < 0) throw new IllegalArgumentException("Negative certification draw count");
        super.setSeed(checkpointSeed);
        drawCount = 0;
        for (int i = 0; i < targetDrawCount; i++) next(32);
    }
''',
        'certification random checkpoint restore',
    )
certification_random.write_text(random_text)

if replay_random.exists():
    replay_text = replay_random.read_text()
    if 'implements CertificationCheckpointRandom' not in replay_text:
        replay_text = one(
            replay_text,
            'public class CertificationReplayRandom extends Random {',
            'public class CertificationReplayRandom extends Random implements CertificationCheckpointRandom {',
            'replay random checkpoint interface',
        )
    if 'restoreCheckpointDrawCount' not in replay_text:
        replay_text = one(
            replay_text,
            '''    public int getDrawCount() {
        return index;
    }
''',
            '''    public int getDrawCount() {
        return index;
    }

    @Override
    public void restoreCheckpointDrawCount(int targetDrawCount) {
        if (targetDrawCount < 0 || targetDrawCount > values.size()) {
            throw new IllegalArgumentException("Invalid replay checkpoint draw count " + targetDrawCount);
        }
        index = targetDrawCount;
    }
''',
            'replay random checkpoint restore',
        )
    replay_random.write_text(replay_text)

picture_text = picture.read_text()
if 'restoreCertificationDrawingState' not in picture_text:
    picture_text = one(
        picture_text,
        '''        return jagiPictureContext.getPriorityData();
    }
''',
        '''        return jagiPictureContext.getPriorityData();
    }

    public boolean certificationPicColorSet() {
        return jagiPictureContext.picColor != null;
    }

    public int certificationPicColor() {
        return jagiPictureContext.picColor == null ? 0 : jagiPictureContext.picColor.intValue();
    }

    public boolean certificationPriColorSet() {
        return jagiPictureContext.priColor != null;
    }

    public int certificationPriColor() {
        return jagiPictureContext.priColor == null ? 0 : jagiPictureContext.priColor.byteValue();
    }

    public int certificationPenStyle() {
        return jagiPictureContext.penStyle;
    }

    public void restoreCertificationDrawingState(
            int[] visualPixels, int[] priorityPixels,
            boolean picColorSet, int picColor,
            boolean priColorSet, int priColor,
            int penStyle) {
        if (visualPixels == null || priorityPixels == null
                || visualPixels.length != 160 * 168
                || priorityPixels.length != 160 * 168) {
            throw new IllegalArgumentException("Certification current-picture pixel size mismatch");
        }
        System.arraycopy(visualPixels, 0, jagiPictureContext.getPictureData(), 0, visualPixels.length);
        System.arraycopy(priorityPixels, 0, jagiPictureContext.getPriorityData(), 0, priorityPixels.length);
        jagiPictureContext.picColor = picColorSet ? Integer.valueOf(picColor) : null;
        jagiPictureContext.priColor = priColorSet ? Byte.valueOf((byte)priColor) : null;
        jagiPictureContext.penStyle = (byte)penStyle;
    }
''',
        'picture certification drawing state',
    )
picture.write_text(picture_text)

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

    public void restoreCertificationResourceLoadState(
            boolean[] logicLoaded, boolean[] pictureLoaded, boolean[] viewLoaded, boolean[] soundLoaded) {
        if (logicLoaded == null || pictureLoaded == null || viewLoaded == null || soundLoaded == null
                || logicLoaded.length != 256 || pictureLoaded.length != 256
                || viewLoaded.length != 256 || soundLoaded.length != 256) {
            throw new IllegalArgumentException("Certification resource checkpoint size mismatch");
        }
        for (int i = 0; i < 256; i++) {
            if (state.logics[i] != null) state.logics[i].isLoaded = logicLoaded[i];
            if (state.pictures[i] != null) state.pictures[i].isLoaded = pictureLoaded[i];
            if (state.views[i] != null) state.views[i].isLoaded = viewLoaded[i];
            if (state.sounds[i] != null) {
                state.sounds[i].isLoaded = soundLoaded[i];
                if (soundLoaded[i]) soundPlayer.loadSound(state.sounds[i]);
            }
        }
    }

    public int getCertificationCurrentPictureIndex() {
        int pictureIndex = -1;
        for (ScriptBufferEvent event : state.scriptBuffer.events) {
            if (event.type == ScriptBuffer.ScriptBufferEventType.DRAW_PIC) {
                pictureIndex = event.resourceNumber;
            }
        }
        return pictureIndex;
    }

    public void restoreCertificationCurrentPicture(
            int pictureIndex, int[] visualPixels, int[] priorityPixels,
            boolean picColorSet, int picColor,
            boolean priColorSet, int priColor,
            int penStyle) {
        if (pictureIndex < 0) {
            state.currentPicture = null;
            return;
        }
        if (pictureIndex >= state.pictures.length || state.pictures[pictureIndex] == null) {
            throw new IllegalArgumentException("Certification current-picture index mismatch");
        }
        if (visualPixels == null || priorityPixels == null
                || visualPixels.length != 160 * 168
                || priorityPixels.length != 160 * 168) {
            throw new IllegalArgumentException("Certification current-picture payload mismatch");
        }
        Picture restoredPicture = state.pictures[pictureIndex].clone();
        restoredPicture.index = pictureIndex;
        restoredPicture.restoreCertificationDrawingState(
                visualPixels, priorityPixels,
                picColorSet, picColor, priColorSet, priColor, penStyle);
        state.currentPicture = restoredPicture;

        // Rebuild the interpreter's non-shared picture working buffers and animated
        // object save areas from the exact current-picture context. Host framebuffer
        // bytes are restored separately after the worker round-trip.
        updatePixelArrays();
        state.drawObjects();
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
    methods = r'''    private static class CertificationCheckpointOverlay {
        boolean[] controllers;
        boolean acceptInput;
        boolean userControl;
        boolean graphicsMode;
        boolean pictureVisible;
        boolean showStatusLine;
        int statusLineRow;
        int pictureRow;
        int inputLineRow;
        int horizon;
        int textAttribute;
        int foregroundColour;
        int backgroundColour;
        char cursorCharacter;
        long animationTicks;
        boolean gamePaused;
        int currentLogNum;
        int maxDrawn;
        int priorityBase;
        boolean menuEnabled;
        boolean menuOpen;
        boolean holdKey;
        boolean blocking;
        short blockUpperLeftX;
        short blockUpperLeftY;
        short blockLowerRightX;
        short blockLowerRightY;
        String currentInput;
        String lastInput;
        String simpleName;
        int randomDrawCount;
        int scriptMax;
        int[] scanStart;
        boolean[] logicLoaded;
        boolean[] pictureLoaded;
        boolean[] viewLoaded;
        boolean[] soundLoaded;
    }

    private CertificationCheckpointOverlay certificationCheckpointOverlay;

    private CertificationCheckpointOverlay captureCertificationCheckpointOverlay() {
        CertificationCheckpointOverlay overlay = new CertificationCheckpointOverlay();
        overlay.controllers = new boolean[state.controllers.length];
        for (int i = 0; i < state.controllers.length; i++) overlay.controllers[i] = state.controllers[i];
        overlay.acceptInput = state.acceptInput;
        overlay.userControl = state.userControl;
        overlay.graphicsMode = state.graphicsMode;
        overlay.pictureVisible = state.pictureVisible;
        overlay.showStatusLine = state.showStatusLine;
        overlay.statusLineRow = state.statusLineRow;
        overlay.pictureRow = state.pictureRow;
        overlay.inputLineRow = state.inputLineRow;
        overlay.horizon = state.horizon;
        overlay.textAttribute = state.textAttribute;
        overlay.foregroundColour = state.foregroundColour;
        overlay.backgroundColour = state.backgroundColour;
        overlay.cursorCharacter = state.cursorCharacter;
        overlay.animationTicks = state.animationTicks;
        overlay.gamePaused = state.gamePaused;
        overlay.currentLogNum = state.currentLogNum;
        overlay.maxDrawn = state.maxDrawn;
        overlay.priorityBase = state.priorityBase;
        overlay.menuEnabled = state.menuEnabled;
        overlay.menuOpen = state.menuOpen;
        overlay.holdKey = state.holdKey;
        overlay.blocking = state.blocking;
        overlay.blockUpperLeftX = state.blockUpperLeftX;
        overlay.blockUpperLeftY = state.blockUpperLeftY;
        overlay.blockLowerRightX = state.blockLowerRightX;
        overlay.blockLowerRightY = state.blockLowerRightY;
        overlay.currentInput = (state.currentInput == null ? null : state.currentInput.toString());
        overlay.lastInput = state.lastInput;
        overlay.simpleName = state.simpleName;
        overlay.randomDrawCount = getCertificationRandomDrawCount();
        overlay.scriptMax = state.scriptBuffer.maxScript;
        overlay.scanStart = new int[state.scanStart.length];
        overlay.logicLoaded = new boolean[256];
        overlay.pictureLoaded = new boolean[256];
        overlay.viewLoaded = new boolean[256];
        overlay.soundLoaded = new boolean[256];
        for (int i = 0; i < state.scanStart.length; i++) overlay.scanStart[i] = state.scanStart[i];
        for (int i = 0; i < 256; i++) {
            overlay.logicLoaded[i] = state.logics[i] != null && state.logics[i].isLoaded;
            overlay.pictureLoaded[i] = state.pictures[i] != null && state.pictures[i].isLoaded;
            overlay.viewLoaded[i] = state.views[i] != null && state.views[i].isLoaded;
            overlay.soundLoaded[i] = state.sounds[i] != null && state.sounds[i].isLoaded;
        }
        return overlay;
    }

    private void restoreCertificationCheckpointOverlay(CertificationCheckpointOverlay overlay) {
        if (overlay == null) throw new IllegalStateException("Missing certification checkpoint overlay");
        if (overlay.controllers == null || overlay.controllers.length != state.controllers.length) {
            throw new IllegalStateException("Certification controller checkpoint size mismatch");
        }
        for (int i = 0; i < state.controllers.length; i++) state.controllers[i] = overlay.controllers[i];
        state.acceptInput = overlay.acceptInput;
        state.userControl = overlay.userControl;
        state.graphicsMode = overlay.graphicsMode;
        state.pictureVisible = overlay.pictureVisible;
        state.showStatusLine = overlay.showStatusLine;
        state.statusLineRow = overlay.statusLineRow;
        state.pictureRow = overlay.pictureRow;
        state.inputLineRow = overlay.inputLineRow;
        state.horizon = overlay.horizon;
        state.textAttribute = overlay.textAttribute;
        state.foregroundColour = overlay.foregroundColour;
        state.backgroundColour = overlay.backgroundColour;
        state.cursorCharacter = overlay.cursorCharacter;
        state.animationTicks = overlay.animationTicks;
        state.gamePaused = overlay.gamePaused;
        state.currentLogNum = overlay.currentLogNum;
        state.maxDrawn = overlay.maxDrawn;
        state.priorityBase = overlay.priorityBase;
        state.menuEnabled = overlay.menuEnabled;
        state.menuOpen = overlay.menuOpen;
        state.holdKey = overlay.holdKey;
        state.blocking = overlay.blocking;
        state.blockUpperLeftX = overlay.blockUpperLeftX;
        state.blockUpperLeftY = overlay.blockUpperLeftY;
        state.blockLowerRightX = overlay.blockLowerRightX;
        state.blockLowerRightY = overlay.blockLowerRightY;
        state.currentInput = (overlay.currentInput == null ? null : new StringBuilder(overlay.currentInput));
        state.lastInput = overlay.lastInput;
        state.simpleName = overlay.simpleName;
        state.scriptBuffer.maxScript = overlay.scriptMax;
        if (overlay.scanStart == null || overlay.scanStart.length != state.scanStart.length) {
            throw new IllegalStateException("Certification scanStart checkpoint size mismatch");
        }
        for (int i = 0; i < state.scanStart.length; i++) state.scanStart[i] = overlay.scanStart[i];
        commands.restoreCertificationResourceLoadState(
                overlay.logicLoaded, overlay.pictureLoaded, overlay.viewLoaded, overlay.soundLoaded);
        if (overlay.randomDrawCount >= 0) {
            if (!(state.random instanceof CertificationCheckpointRandom)) {
                throw new IllegalStateException("Certification random source is not checkpointable");
            }
            ((CertificationCheckpointRandom)state.random).restoreCheckpointDrawCount(overlay.randomDrawCount);
        }
    }

    public byte[] captureCertificationCheckpoint() {
        CertificationCheckpointOverlay overlay = captureCertificationCheckpointOverlay();
        byte[] checkpointData = commands.captureCertificationCheckpoint();
        if (checkpointData == null || checkpointData.length == 0) return checkpointData;
        certificationCheckpointOverlay = overlay;
        return checkpointData;
    }

    public boolean restoreCertificationCheckpoint(byte[] checkpointData) {
        if (certificationCheckpointOverlay == null) return false;
        if (!commands.restoreCertificationCheckpoint(checkpointData)) return false;
        restoreCertificationCheckpointOverlay(certificationCheckpointOverlay);
        return true;
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
