#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1h_checkpoint_serialization.py /path/to/certification-agile-gdx')

root = Path(sys.argv[1]).resolve()
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
for path in (interpreter, worker):
    if not path.exists():
        raise RuntimeError(f'missing Phase -1H serialization source: {path}')

def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)

itext = interpreter.read_text()
if 'int currentPictureIndex;' not in itext:
    itext = one(
        itext,
        '''        boolean[] soundLoaded;
    }
''',
        '''        boolean[] soundLoaded;
        int currentPictureIndex;
        int[] currentPictureVisualPixels;
        int[] currentPicturePriorityPixels;
        boolean currentPicturePicColorSet;
        int currentPicturePicColor;
        boolean currentPicturePriColorSet;
        int currentPicturePriColor;
        int currentPicturePenStyle;
    }
''',
        'checkpoint current-picture overlay fields',
    )

old_overlay_tail = r'''    private CertificationCheckpointOverlay certificationCheckpointOverlay;

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

new_overlay_tail = r'''    private static final int CERTIFICATION_CHECKPOINT_MAGIC = 0x4B513148; // KQ1H
    private static final int CERTIFICATION_CHECKPOINT_VERSION = 2;

    private static class CertificationCheckpointCursor {
        int pos;
    }

    private static class CertificationDecodedCheckpoint {
        byte[] saveData;
        CertificationCheckpointOverlay overlay;
    }

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

        if (state.currentPicture == null) {
            overlay.currentPictureIndex = -1;
            overlay.currentPictureVisualPixels = new int[0];
            overlay.currentPicturePriorityPixels = new int[0];
            overlay.currentPicturePicColorSet = false;
            overlay.currentPicturePicColor = 0;
            overlay.currentPicturePriColorSet = false;
            overlay.currentPicturePriColor = 0;
            overlay.currentPicturePenStyle = 0;
        } else {
            overlay.currentPictureIndex = commands.getCertificationCurrentPictureIndex();
            if (overlay.currentPictureIndex < 0) {
                throw new IllegalStateException("Missing certification current-picture script identity");
            }
            int[] currentVisual = state.currentPicture.getVisualPixels();
            int[] currentPriority = state.currentPicture.getPriorityPixels();
            overlay.currentPictureVisualPixels = new int[currentVisual.length];
            overlay.currentPicturePriorityPixels = new int[currentPriority.length];
            System.arraycopy(currentVisual, 0, overlay.currentPictureVisualPixels, 0, currentVisual.length);
            System.arraycopy(currentPriority, 0, overlay.currentPicturePriorityPixels, 0, currentPriority.length);
            overlay.currentPicturePicColorSet = state.currentPicture.certificationPicColorSet();
            overlay.currentPicturePicColor = state.currentPicture.certificationPicColor();
            overlay.currentPicturePriColorSet = state.currentPicture.certificationPriColorSet();
            overlay.currentPicturePriColor = state.currentPicture.certificationPriColor();
            overlay.currentPicturePenStyle = state.currentPicture.certificationPenStyle();
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
        commands.restoreCertificationCurrentPicture(
                overlay.currentPictureIndex,
                overlay.currentPictureVisualPixels,
                overlay.currentPicturePriorityPixels,
                overlay.currentPicturePicColorSet,
                overlay.currentPicturePicColor,
                overlay.currentPicturePriColorSet,
                overlay.currentPicturePriColor,
                overlay.currentPicturePenStyle);
        if (overlay.randomDrawCount >= 0) {
            if (!(state.random instanceof CertificationCheckpointRandom)) {
                throw new IllegalStateException("Certification random source is not checkpointable");
            }
            ((CertificationCheckpointRandom)state.random).restoreCheckpointDrawCount(overlay.randomDrawCount);
        }
    }

    private int certificationCheckpointWriteInt(byte[] data, int pos, int value) {
        data[pos++] = (byte)(value >>> 24);
        data[pos++] = (byte)(value >>> 16);
        data[pos++] = (byte)(value >>> 8);
        data[pos++] = (byte)value;
        return pos;
    }

    private int certificationCheckpointWriteLong(byte[] data, int pos, long value) {
        pos = certificationCheckpointWriteInt(data, pos, (int)(value >>> 32));
        return certificationCheckpointWriteInt(data, pos, (int)value);
    }

    private int certificationCheckpointWriteString(byte[] data, int pos, String value) {
        if (value == null) return certificationCheckpointWriteInt(data, pos, -1);
        pos = certificationCheckpointWriteInt(data, pos, value.length());
        for (int i = 0; i < value.length(); i++) {
            pos = certificationCheckpointWriteInt(data, pos, value.charAt(i));
        }
        return pos;
    }

    private int certificationCheckpointReadInt(byte[] data, CertificationCheckpointCursor cursor) {
        if (cursor.pos < 0 || cursor.pos + 4 > data.length) {
            throw new IllegalArgumentException("Truncated certification checkpoint");
        }
        int value = ((data[cursor.pos] & 0xFF) << 24)
                | ((data[cursor.pos + 1] & 0xFF) << 16)
                | ((data[cursor.pos + 2] & 0xFF) << 8)
                | (data[cursor.pos + 3] & 0xFF);
        cursor.pos += 4;
        return value;
    }

    private long certificationCheckpointReadLong(byte[] data, CertificationCheckpointCursor cursor) {
        long high = ((long)certificationCheckpointReadInt(data, cursor)) & 0xFFFFFFFFL;
        long low = ((long)certificationCheckpointReadInt(data, cursor)) & 0xFFFFFFFFL;
        return (high << 32) | low;
    }

    private String certificationCheckpointReadString(byte[] data, CertificationCheckpointCursor cursor) {
        int length = certificationCheckpointReadInt(data, cursor);
        if (length == -1) return null;
        if (length < 0 || length > 65535) throw new IllegalArgumentException("Invalid checkpoint string length");
        StringBuilder value = new StringBuilder(length);
        for (int i = 0; i < length; i++) {
            int ch = certificationCheckpointReadInt(data, cursor);
            if (ch < 0 || ch > 0xFFFF) throw new IllegalArgumentException("Invalid checkpoint string character");
            value.append((char)ch);
        }
        return value.toString();
    }

    private byte[] encodeCertificationCheckpoint(byte[] saveData, CertificationCheckpointOverlay overlay) {
        if (saveData == null || overlay == null) return null;
        // Sierra saves are below 20 KiB. The extra envelope is intentionally bounded
        // and uses UTF-16 code units for exact Java String round trips without locale
        // or browser text-encoding dependencies.
        byte[] buffer = new byte[saveData.length + 524288];
        int pos = 0;
        pos = certificationCheckpointWriteInt(buffer, pos, CERTIFICATION_CHECKPOINT_MAGIC);
        pos = certificationCheckpointWriteInt(buffer, pos, CERTIFICATION_CHECKPOINT_VERSION);
        pos = certificationCheckpointWriteInt(buffer, pos, saveData.length);
        System.arraycopy(saveData, 0, buffer, pos, saveData.length);
        pos += saveData.length;

        pos = certificationCheckpointWriteInt(buffer, pos, overlay.controllers.length);
        for (boolean controller : overlay.controllers) pos = certificationCheckpointWriteInt(buffer, pos, controller ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.acceptInput ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.userControl ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.graphicsMode ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.pictureVisible ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.showStatusLine ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.statusLineRow);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.pictureRow);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.inputLineRow);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.horizon);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.textAttribute);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.foregroundColour);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.backgroundColour);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.cursorCharacter);
        pos = certificationCheckpointWriteLong(buffer, pos, overlay.animationTicks);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.gamePaused ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentLogNum);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.maxDrawn);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.priorityBase);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.menuEnabled ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.menuOpen ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.holdKey ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.blocking ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.blockUpperLeftX);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.blockUpperLeftY);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.blockLowerRightX);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.blockLowerRightY);
        pos = certificationCheckpointWriteString(buffer, pos, overlay.currentInput);
        pos = certificationCheckpointWriteString(buffer, pos, overlay.lastInput);
        pos = certificationCheckpointWriteString(buffer, pos, overlay.simpleName);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.randomDrawCount);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.scriptMax);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.scanStart.length);
        for (int value : overlay.scanStart) pos = certificationCheckpointWriteInt(buffer, pos, value);
        pos = certificationCheckpointWriteInt(buffer, pos, 256);
        for (int i = 0; i < 256; i++) {
            int loadedBits = (overlay.logicLoaded[i] ? 1 : 0)
                    | (overlay.pictureLoaded[i] ? 2 : 0)
                    | (overlay.viewLoaded[i] ? 4 : 0)
                    | (overlay.soundLoaded[i] ? 8 : 0);
            pos = certificationCheckpointWriteInt(buffer, pos, loadedBits);
        }

        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPictureIndex);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPictureVisualPixels.length);
        for (int value : overlay.currentPictureVisualPixels) {
            pos = certificationCheckpointWriteInt(buffer, pos, value);
        }
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePriorityPixels.length);
        for (int value : overlay.currentPicturePriorityPixels) {
            pos = certificationCheckpointWriteInt(buffer, pos, value);
        }
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePicColorSet ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePicColor);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePriColorSet ? 1 : 0);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePriColor);
        pos = certificationCheckpointWriteInt(buffer, pos, overlay.currentPicturePenStyle);

        byte[] exact = new byte[pos];
        System.arraycopy(buffer, 0, exact, 0, pos);
        return exact;
    }

    private CertificationDecodedCheckpoint decodeCertificationCheckpoint(byte[] data) {
        if (data == null || data.length < 12) throw new IllegalArgumentException("Invalid certification checkpoint");
        CertificationCheckpointCursor cursor = new CertificationCheckpointCursor();
        if (certificationCheckpointReadInt(data, cursor) != CERTIFICATION_CHECKPOINT_MAGIC) {
            throw new IllegalArgumentException("Certification checkpoint magic mismatch");
        }
        if (certificationCheckpointReadInt(data, cursor) != CERTIFICATION_CHECKPOINT_VERSION) {
            throw new IllegalArgumentException("Certification checkpoint version mismatch");
        }
        int saveLength = certificationCheckpointReadInt(data, cursor);
        if (saveLength <= 0 || cursor.pos + saveLength > data.length) {
            throw new IllegalArgumentException("Invalid certification checkpoint save payload");
        }
        CertificationDecodedCheckpoint decoded = new CertificationDecodedCheckpoint();
        decoded.saveData = new byte[saveLength];
        System.arraycopy(data, cursor.pos, decoded.saveData, 0, saveLength);
        cursor.pos += saveLength;

        CertificationCheckpointOverlay overlay = new CertificationCheckpointOverlay();
        int controllerLength = certificationCheckpointReadInt(data, cursor);
        if (controllerLength != state.controllers.length) {
            throw new IllegalArgumentException("Certification controller checkpoint size mismatch");
        }
        overlay.controllers = new boolean[controllerLength];
        for (int i = 0; i < controllerLength; i++) overlay.controllers[i] = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.acceptInput = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.userControl = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.graphicsMode = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.pictureVisible = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.showStatusLine = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.statusLineRow = certificationCheckpointReadInt(data, cursor);
        overlay.pictureRow = certificationCheckpointReadInt(data, cursor);
        overlay.inputLineRow = certificationCheckpointReadInt(data, cursor);
        overlay.horizon = certificationCheckpointReadInt(data, cursor);
        overlay.textAttribute = certificationCheckpointReadInt(data, cursor);
        overlay.foregroundColour = certificationCheckpointReadInt(data, cursor);
        overlay.backgroundColour = certificationCheckpointReadInt(data, cursor);
        overlay.cursorCharacter = (char)certificationCheckpointReadInt(data, cursor);
        overlay.animationTicks = certificationCheckpointReadLong(data, cursor);
        overlay.gamePaused = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.currentLogNum = certificationCheckpointReadInt(data, cursor);
        overlay.maxDrawn = certificationCheckpointReadInt(data, cursor);
        overlay.priorityBase = certificationCheckpointReadInt(data, cursor);
        overlay.menuEnabled = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.menuOpen = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.holdKey = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.blocking = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.blockUpperLeftX = (short)certificationCheckpointReadInt(data, cursor);
        overlay.blockUpperLeftY = (short)certificationCheckpointReadInt(data, cursor);
        overlay.blockLowerRightX = (short)certificationCheckpointReadInt(data, cursor);
        overlay.blockLowerRightY = (short)certificationCheckpointReadInt(data, cursor);
        overlay.currentInput = certificationCheckpointReadString(data, cursor);
        overlay.lastInput = certificationCheckpointReadString(data, cursor);
        overlay.simpleName = certificationCheckpointReadString(data, cursor);
        overlay.randomDrawCount = certificationCheckpointReadInt(data, cursor);
        overlay.scriptMax = certificationCheckpointReadInt(data, cursor);
        int scanStartLength = certificationCheckpointReadInt(data, cursor);
        if (scanStartLength != state.scanStart.length) {
            throw new IllegalArgumentException("Certification scanStart checkpoint size mismatch");
        }
        overlay.scanStart = new int[scanStartLength];
        for (int i = 0; i < scanStartLength; i++) overlay.scanStart[i] = certificationCheckpointReadInt(data, cursor);
        int resourceLength = certificationCheckpointReadInt(data, cursor);
        if (resourceLength != 256) throw new IllegalArgumentException("Certification resource checkpoint size mismatch");
        overlay.logicLoaded = new boolean[resourceLength];
        overlay.pictureLoaded = new boolean[resourceLength];
        overlay.viewLoaded = new boolean[resourceLength];
        overlay.soundLoaded = new boolean[resourceLength];
        for (int i = 0; i < resourceLength; i++) {
            int loadedBits = certificationCheckpointReadInt(data, cursor);
            overlay.logicLoaded[i] = (loadedBits & 1) != 0;
            overlay.pictureLoaded[i] = (loadedBits & 2) != 0;
            overlay.viewLoaded[i] = (loadedBits & 4) != 0;
            overlay.soundLoaded[i] = (loadedBits & 8) != 0;
        }

        overlay.currentPictureIndex = certificationCheckpointReadInt(data, cursor);
        int currentVisualLength = certificationCheckpointReadInt(data, cursor);
        int expectedPicturePixels = overlay.currentPictureIndex < 0 ? 0 : (160 * 168);
        if (currentVisualLength != expectedPicturePixels) {
            throw new IllegalArgumentException("Certification current-picture visual size mismatch");
        }
        overlay.currentPictureVisualPixels = new int[currentVisualLength];
        for (int i = 0; i < currentVisualLength; i++) {
            overlay.currentPictureVisualPixels[i] = certificationCheckpointReadInt(data, cursor);
        }
        int currentPriorityLength = certificationCheckpointReadInt(data, cursor);
        if (currentPriorityLength != expectedPicturePixels) {
            throw new IllegalArgumentException("Certification current-picture priority size mismatch");
        }
        overlay.currentPicturePriorityPixels = new int[currentPriorityLength];
        for (int i = 0; i < currentPriorityLength; i++) {
            overlay.currentPicturePriorityPixels[i] = certificationCheckpointReadInt(data, cursor);
        }
        overlay.currentPicturePicColorSet = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.currentPicturePicColor = certificationCheckpointReadInt(data, cursor);
        overlay.currentPicturePriColorSet = certificationCheckpointReadInt(data, cursor) != 0;
        overlay.currentPicturePriColor = certificationCheckpointReadInt(data, cursor);
        overlay.currentPicturePenStyle = certificationCheckpointReadInt(data, cursor);

        if (cursor.pos != data.length) throw new IllegalArgumentException("Trailing certification checkpoint data");
        decoded.overlay = overlay;
        return decoded;
    }

    public byte[] captureCertificationCheckpoint() {
        CertificationCheckpointOverlay overlay = captureCertificationCheckpointOverlay();
        byte[] saveData = commands.captureCertificationCheckpoint();
        if (saveData == null || saveData.length == 0) return saveData;
        return encodeCertificationCheckpoint(saveData, overlay);
    }

    public boolean restoreCertificationCheckpoint(byte[] checkpointData) {
        CertificationDecodedCheckpoint decoded = decodeCertificationCheckpoint(checkpointData);
        if (!commands.restoreCertificationCheckpoint(decoded.saveData)) return false;
        restoreCertificationCheckpointOverlay(decoded.overlay);
        return true;
    }
'''

if old_overlay_tail not in itext:
    if 'CERTIFICATION_CHECKPOINT_MAGIC' not in itext:
        raise RuntimeError('Phase -1H checkpoint overlay block not found for serialization')
else:
    itext = one(itext, old_overlay_tail, new_overlay_tail, 'serialized checkpoint envelope')
interpreter.write_text(itext)

wtext = worker.read_text()
if 'private SharedArray certificationCheckpointTransport;' not in wtext:
    wtext = one(
        wtext,
        '    private byte[] certificationCheckpointData;\n',
        '    private byte[] certificationCheckpointData;\n    private SharedArray certificationCheckpointTransport;\n    private int certificationCheckpointTransportSlots;\n',
        'checkpoint transport fields',
    )

if 'certificationCheckpointSAB = getOptionalNestedObject' not in wtext:
    wtext = one(
        wtext,
        '                JavaScriptObject certificationDigestSAB = getOptionalNestedObject(eventObject, "certificationDigestSAB");\n',
        '                JavaScriptObject certificationDigestSAB = getOptionalNestedObject(eventObject, "certificationDigestSAB");\n                JavaScriptObject certificationCheckpointSAB = getOptionalNestedObject(eventObject, "certificationCheckpointSAB");\n',
        'checkpoint transport initialise object',
    )

if 'certificationCheckpointTransport = new SharedArray' not in wtext:
    anchor = '''                int certificationDigestBytes = getBufferByteLength(certificationDigestSAB);
                if (certificationDigestBytes >= 52 && (certificationDigestBytes & 3) == 0)
                    certificationDigest = new SharedArray(certificationDigestSAB);
'''
    replacement = anchor + '''                int certificationCheckpointBytes = getBufferByteLength(certificationCheckpointSAB);
                if (certificationCheckpointBytes >= 8 && (certificationCheckpointBytes & 3) == 0) {
                    certificationCheckpointTransport = new SharedArray(certificationCheckpointSAB);
                    certificationCheckpointTransportSlots = certificationCheckpointBytes / 4;
                }
'''
    if anchor not in wtext:
        raise RuntimeError('checkpoint transport construction anchor not found')
    wtext = one(wtext, anchor, replacement, 'checkpoint transport construction')

old_service = r'''    /**
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

new_service = r'''    /**
     * Phase -1H serialized checkpoint transport. Requests are packed as
     * (epoch << 2) | action. Action 1 captures and exports a deterministic
     * checkpoint envelope through the shared checkpoint transport. Action 2 imports
     * the host-supplied envelope from that same transport before restoring, so a
     * newly started worker does not depend on worker-local checkpoint state.
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
                if (certificationCheckpointData == null || certificationCheckpointData.length == 0) {
                    status = 4;
                } else if (certificationCheckpointTransport == null
                        || certificationCheckpointData.length + 1 > certificationCheckpointTransportSlots) {
                    status = 5;
                } else {
                    certificationCheckpointTransport.set(0, certificationCheckpointData.length);
                    for (int i = 0; i < certificationCheckpointData.length; i++) {
                        certificationCheckpointTransport.set(i + 1, certificationCheckpointData[i] & 0xFF);
                    }
                    status = 1;
                }
            } else if (action == 2) {
                if (certificationCheckpointTransport == null) {
                    status = 3;
                } else {
                    int checkpointLength = certificationCheckpointTransport.get(0);
                    if (checkpointLength <= 0 || checkpointLength + 1 > certificationCheckpointTransportSlots) {
                        status = 3;
                    } else {
                        certificationCheckpointData = new byte[checkpointLength];
                        for (int i = 0; i < checkpointLength; i++) {
                            certificationCheckpointData[i] = (byte)(certificationCheckpointTransport.get(i + 1) & 0xFF);
                        }
                        boolean restored = interpreter.restoreCertificationCheckpoint(certificationCheckpointData);
                        if (restored) {
                            lastTotalTickCount = variableData.getTotalTicks();
                            publishDiagnosticTrace();
                            status = 2;
                        } else {
                            status = 3;
                        }
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

if old_service not in wtext:
    if 'Phase -1H serialized checkpoint transport' not in wtext:
        raise RuntimeError('Phase -1H worker checkpoint service block not found for serialization')
else:
    wtext = one(wtext, old_service, new_service, 'serialized checkpoint worker service')
worker.write_text(wtext)

print('Phase -1H serialized checkpoint installed: deterministic envelope + host-visible shared payload + fresh-worker import')
