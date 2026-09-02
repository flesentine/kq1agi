#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_certification_runtime.py /path/to/instrumented-agile-gdx')

root = Path(sys.argv[1]).resolve()
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
random_java = root / 'core/src/main/java/com/agifans/agile/CertificationRandom.java'
store_java = root / 'html/src/main/java/com/agifans/agile/gwt/CertificationSavedGameStore.java'


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


if not interpreter.exists() or not worker.exists():
    raise RuntimeError('AGILE source tree is incomplete')

itext = interpreter.read_text()
if 'public int getDiagnosticValue(int slot)' not in itext or 'case 0: return 2;' not in itext:
    raise RuntimeError('trace v2 observer missing; run instrument_truth_worker.py before certification instrumentation')

random_java.write_text(r'''package com.agifans.agile;

import java.util.Random;

/**
 * Deterministic java.util.Random used only by the opt-in certification runtime.
 * It preserves Random semantics while exposing the number of underlying PRNG draws.
 */
public class CertificationRandom extends Random {
    private static final long serialVersionUID = 1L;
    private int drawCount;

    public CertificationRandom(long seed) {
        super(seed);
        drawCount = 0;
    }

    @Override
    protected int next(int bits) {
        drawCount++;
        return super.next(bits);
    }

    public int getDrawCount() {
        return drawCount;
    }
}
''')

store_java.write_text(r'''package com.agifans.agile.gwt;

import java.util.HashMap;
import java.util.Map;

import com.agifans.agile.SavedGames.SavedGame;

/**
 * Session-local saved-game store for certification. It never touches OPFS and uses
 * deterministic sequence numbers instead of wall-clock timestamps.
 */
public class CertificationSavedGameStore extends GwtSavedGameStore {
    private final Map<Integer, SavedGame> games = new HashMap<Integer, SavedGame>();
    private long sequence;
    private String gameId = "CERT";

    @Override
    public void initialise(String gameId) {
        this.gameId = (gameId == null ? "CERT" : gameId);
        games.clear();
        sequence = 0;
    }

    @Override
    public boolean createFolderForGame(String gameId) {
        return true;
    }

    @Override
    public String getFolderNameForGame(String gameId) {
        return "\\Certification\\" + (gameId == null ? this.gameId : gameId);
    }

    private SavedGame empty(int num) {
        SavedGame game = new SavedGame();
        game.num = num;
        game.exists = false;
        game.fileName = getFolderNameForGame(gameId) + "\\" + gameId + "SG." + num;
        game.fileTime = 0;
        game.description = "";
        game.savedGameData = new byte[0];
        return game;
    }

    private SavedGame copy(SavedGame source) {
        if (source == null) return null;
        SavedGame game = new SavedGame();
        game.num = source.num;
        game.exists = source.exists;
        game.fileName = source.fileName;
        game.fileTime = source.fileTime;
        game.description = source.description;
        game.savedGameData = (source.savedGameData == null ? new byte[0] : source.savedGameData.clone());
        return game;
    }

    @Override
    public SavedGame getSavedGameByNumber(String gameId, int num) {
        SavedGame game = games.get(num);
        return (game == null ? empty(num) : copy(game));
    }

    @Override
    public boolean saveGame(SavedGame savedGame, byte[] savedGameData, int length) {
        SavedGame stored = copy(savedGame);
        if (stored == null) return false;
        stored.exists = true;
        stored.fileTime = ++sequence;
        int safeLength = Math.max(0, Math.min(length, savedGameData == null ? 0 : savedGameData.length));
        stored.savedGameData = new byte[safeLength];
        if (safeLength > 0) System.arraycopy(savedGameData, 0, stored.savedGameData, 0, safeLength);
        games.put(stored.num, stored);
        return true;
    }
}
''')

cert_methods = r'''    /**
     * Enables deterministic certification semantics before the first interpreter tick.
     * Normal gameplay never calls this method.
     */
    public void configureCertification(int seed) {
        state.random = new CertificationRandom(((long)seed) & 0xFFFFFFFFL);
    }

    public int getCertificationRandomDrawCount() {
        return (state.random instanceof CertificationRandom)
                ? ((CertificationRandom)state.random).getDrawCount() : -1;
    }

    private int certificationMix(int hash, int value) {
        return (hash ^ value) * 16777619;
    }

    private int certificationMixLong(int hash, long value) {
        hash = certificationMix(hash, (int)value);
        return certificationMix(hash, (int)(value >>> 32));
    }

    private int certificationMixString(int hash, String value) {
        if (value == null) return certificationMix(hash, -1);
        hash = certificationMix(hash, value.length());
        for (int i = 0; i < value.length(); i++) hash = certificationMix(hash, value.charAt(i));
        return hash;
    }

    /**
     * Four-part deterministic semantic digest. This intentionally hashes interpreter
     * state rather than rendered pixels or editor-only metadata.
     */
    public int getCertificationDigestValue(int slot) {
        int hash = 0x811C9DC5 ^ (slot * 0x9E3779B9);
        switch (slot) {
            case 0:
                hash = certificationMix(hash, state.getTotalTicks());
                for (int i = 0; i < Defines.NUMVARS; i++) hash = certificationMix(hash, state.getVar(i));
                for (int i = 0; i < Defines.NUMFLAGS; i++) hash = certificationMix(hash, state.getFlag(i) ? 1 : 0);
                for (boolean controller : state.controllers) hash = certificationMix(hash, controller ? 1 : 0);
                hash = certificationMix(hash, state.acceptInput ? 1 : 0);
                hash = certificationMix(hash, state.userControl ? 1 : 0);
                hash = certificationMix(hash, state.graphicsMode ? 1 : 0);
                hash = certificationMix(hash, state.pictureVisible ? 1 : 0);
                hash = certificationMix(hash, state.showStatusLine ? 1 : 0);
                hash = certificationMix(hash, state.statusLineRow);
                hash = certificationMix(hash, state.pictureRow);
                hash = certificationMix(hash, state.inputLineRow);
                hash = certificationMix(hash, state.horizon);
                hash = certificationMix(hash, state.textAttribute);
                hash = certificationMix(hash, state.foregroundColour);
                hash = certificationMix(hash, state.backgroundColour);
                hash = certificationMix(hash, state.cursorCharacter);
                hash = certificationMixLong(hash, state.animationTicks);
                hash = certificationMix(hash, state.gamePaused ? 1 : 0);
                hash = certificationMix(hash, state.currentLogNum);
                hash = certificationMix(hash, state.maxDrawn);
                hash = certificationMix(hash, state.priorityBase);
                hash = certificationMix(hash, state.menuEnabled ? 1 : 0);
                hash = certificationMix(hash, state.menuOpen ? 1 : 0);
                hash = certificationMix(hash, state.holdKey ? 1 : 0);
                hash = certificationMix(hash, state.blocking ? 1 : 0);
                hash = certificationMix(hash, state.blockUpperLeftX);
                hash = certificationMix(hash, state.blockUpperLeftY);
                hash = certificationMix(hash, state.blockLowerRightX);
                hash = certificationMix(hash, state.blockLowerRightY);
                hash = certificationMixString(hash, state.currentInput == null ? null : state.currentInput.toString());
                hash = certificationMixString(hash, state.lastInput);
                hash = certificationMixString(hash, state.simpleName);
                return hash;

            case 1:
                for (AnimatedObject obj : state.animatedObjects) {
                    hash = certificationMix(hash, obj.objectNumber);
                    hash = certificationMix(hash, obj.x);
                    hash = certificationMix(hash, obj.y);
                    hash = certificationMix(hash, obj.prevX);
                    hash = certificationMix(hash, obj.prevY);
                    hash = certificationMix(hash, obj.currentView);
                    hash = certificationMix(hash, obj.currentLoop);
                    hash = certificationMix(hash, obj.currentCel);
                    hash = certificationMix(hash, obj.stepTime);
                    hash = certificationMix(hash, obj.stepTimeCount);
                    hash = certificationMix(hash, obj.stepSize);
                    hash = certificationMix(hash, obj.cycleTime);
                    hash = certificationMix(hash, obj.cycleTimeCount);
                    hash = certificationMix(hash, obj.direction);
                    hash = certificationMix(hash, obj.motionType == null ? -1 : obj.motionType.ordinal());
                    hash = certificationMix(hash, obj.cycleType == null ? -1 : obj.cycleType.ordinal());
                    hash = certificationMix(hash, obj.priority);
                    hash = certificationMix(hash, obj.controlBoxColour);
                    hash = certificationMix(hash, obj.drawn ? 1 : 0);
                    hash = certificationMix(hash, obj.ignoreBlocks ? 1 : 0);
                    hash = certificationMix(hash, obj.fixedPriority ? 1 : 0);
                    hash = certificationMix(hash, obj.ignoreHorizon ? 1 : 0);
                    hash = certificationMix(hash, obj.update ? 1 : 0);
                    hash = certificationMix(hash, obj.cycle ? 1 : 0);
                    hash = certificationMix(hash, obj.animated ? 1 : 0);
                    hash = certificationMix(hash, obj.blocked ? 1 : 0);
                    hash = certificationMix(hash, obj.stayOnWater ? 1 : 0);
                    hash = certificationMix(hash, obj.stayOnLand ? 1 : 0);
                    hash = certificationMix(hash, obj.ignoreObjects ? 1 : 0);
                    hash = certificationMix(hash, obj.repositioned ? 1 : 0);
                    hash = certificationMix(hash, obj.noAdvance ? 1 : 0);
                    hash = certificationMix(hash, obj.fixedLoop ? 1 : 0);
                    hash = certificationMix(hash, obj.stopped ? 1 : 0);
                    hash = certificationMix(hash, obj.motionParam1);
                    hash = certificationMix(hash, obj.motionParam2);
                    hash = certificationMix(hash, obj.motionParam3);
                    hash = certificationMix(hash, obj.motionParam4);
                }
                return hash;

            case 2:
                for (int i = 0; i < state.scanStart.length; i++) hash = certificationMix(hash, state.scanStart[i]);
                for (int i = 0; i < 256; i++) {
                    hash = certificationMix(hash, state.logics[i] != null && state.logics[i].isLoaded ? 1 : 0);
                    hash = certificationMix(hash, state.pictures[i] != null && state.pictures[i].isLoaded ? 1 : 0);
                    hash = certificationMix(hash, state.views[i] != null && state.views[i].isLoaded ? 1 : 0);
                    hash = certificationMix(hash, state.sounds[i] != null && state.sounds[i].isLoaded ? 1 : 0);
                }
                hash = certificationMix(hash, state.objects.count());
                hash = certificationMix(hash, state.objects.numOfAnimatedObjects);
                for (int i = 0; i < state.objects.objects.size(); i++) {
                    hash = certificationMix(hash, state.objects.objects.get(i).room);
                    hash = certificationMixString(hash, state.objects.objects.get(i).name);
                }
                hash = certificationMix(hash, state.scriptBuffer.maxScript);
                hash = certificationMix(hash, state.scriptBuffer.scriptSize);
                hash = certificationMix(hash, state.scriptBuffer.savedScript);
                hash = certificationMix(hash, state.scriptBuffer.events.size());
                for (ScriptBuffer.ScriptBufferEvent event : state.scriptBuffer.events) {
                    hash = certificationMix(hash, event.type == null ? -1 : event.type.ordinal());
                    hash = certificationMix(hash, event.resourceNumber);
                    if (event.data == null) {
                        hash = certificationMix(hash, -1);
                    } else {
                        hash = certificationMix(hash, event.data.length);
                        for (byte b : event.data) hash = certificationMix(hash, b & 0xFF);
                    }
                }
                return hash;

            case 3:
                for (String value : state.strings) hash = certificationMixString(hash, value);
                hash = certificationMix(hash, state.recognisedWords.size());
                for (String value : state.recognisedWords) hash = certificationMixString(hash, value);
                hash = certificationMix(hash, state.keyToControllerMap.size());
                for (java.util.Map.Entry<Integer, Integer> entry : state.keyToControllerMap.entrySet()) {
                    hash = certificationMix(hash, entry.getKey());
                    hash = certificationMix(hash, entry.getValue());
                }
                return hash;

            default:
                return 0;
        }
    }

'''

animation_anchor = '''    /**\n     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a\n'''
itext = one(itext, animation_anchor, cert_methods + animation_anchor, 'certification interpreter methods')
interpreter.write_text(itext)

wtext = worker.read_text()
wtext = one(
    wtext,
    'import com.agifans.agile.gwt.GwtSavedGameStore;\n',
    'import com.agifans.agile.gwt.GwtSavedGameStore;\nimport com.agifans.agile.gwt.CertificationSavedGameStore;\n',
    'certification saved-store import',
)
wtext = one(
    wtext,
    '''    // Optional read-only trace transport supplied by a future dual-runner host.\n    private SharedArray diagnosticTrace;\n''',
    '''    // Optional read-only trace transport supplied by a future dual-runner host.\n    private SharedArray diagnosticTrace;\n\n    // Phase -1B deterministic certification transport. Dormant in normal gameplay.\n    private SharedArray certificationDigest;\n    private boolean certificationMode;\n    private int certificationSeed;\n''',
    'certification worker fields',
)
wtext = one(
    wtext,
    '''                JavaScriptObject diagnosticTraceSAB = getOptionalNestedObject(eventObject, "diagnosticTraceSAB");\n''',
    '''                JavaScriptObject diagnosticTraceSAB = getOptionalNestedObject(eventObject, "diagnosticTraceSAB");\n                JavaScriptObject certificationDigestSAB = getOptionalNestedObject(eventObject, "certificationDigestSAB");\n                certificationMode = getOptionalNestedBoolean(eventObject, "certificationMode");\n                certificationSeed = getOptionalNestedInt(eventObject, "certificationSeed");\n''',
    'certification Initialise fields',
)
wtext = one(
    wtext,
    '''                int diagnosticTraceBytes = getBufferByteLength(diagnosticTraceSAB);\n                if (diagnosticTraceBytes >= 64 && (diagnosticTraceBytes & 3) == 0)\n                    diagnosticTrace = new SharedArray(diagnosticTraceSAB);\n''',
    '''                int diagnosticTraceBytes = getBufferByteLength(diagnosticTraceSAB);\n                if (diagnosticTraceBytes >= 64 && (diagnosticTraceBytes & 3) == 0)\n                    diagnosticTrace = new SharedArray(diagnosticTraceSAB);\n                int certificationDigestBytes = getBufferByteLength(certificationDigestSAB);\n                if (certificationDigestBytes >= 32 && (certificationDigestBytes & 3) == 0)\n                    certificationDigest = new SharedArray(certificationDigestSAB);\n''',
    'certification digest construction',
)
wtext = one(
    wtext,
    '''                savedGameStore = new GwtSavedGameStore();\n''',
    '''                savedGameStore = certificationMode ? new CertificationSavedGameStore() : new GwtSavedGameStore();\n''',
    'certification saved-store isolation',
)
start_anchor = '''                interpreter = new Interpreter(\n                        game, userInput, wavePlayer, savedGameStore, \n                        pixelData, variableData);\n                lastTotalTickCount = variableData.getTotalTicks();\n'''
start_repl = '''                interpreter = new Interpreter(\n                        game, userInput, wavePlayer, savedGameStore, \n                        pixelData, variableData);\n                if (certificationMode) {\n                    interpreter.configureCertification(certificationSeed);\n                    postObject("CertificationReady", JavaScriptObject.createObject());\n                }\n                lastTotalTickCount = variableData.getTotalTicks();\n'''
wtext = one(wtext, start_anchor, start_repl, 'certification interpreter setup')

publish_old = r'''    private void publishDiagnosticTrace() {
        if (diagnosticTrace == null || interpreter == null) return;
        for (int slot = 0; slot < 16; slot++) {
            diagnosticTrace.set(slot, interpreter.getDiagnosticValue(slot));
        }
    }
'''
publish_new = r'''    private void publishDiagnosticTrace() {
        if (interpreter == null) return;
        if (diagnosticTrace != null) {
            for (int slot = 0; slot < 16; slot++) {
                diagnosticTrace.set(slot, interpreter.getDiagnosticValue(slot));
            }
        }
        if (certificationDigest != null) {
            certificationDigest.set(0, 1); // semantic digest schema
            for (int slot = 0; slot < 4; slot++) {
                certificationDigest.set(slot + 1, interpreter.getCertificationDigestValue(slot));
            }
            certificationDigest.set(5, interpreter.getCertificationRandomDrawCount());
            certificationDigest.set(6, interpreter.getDiagnosticValue(2));
            certificationDigest.set(7, 0);
        }
    }
'''
wtext = one(wtext, publish_old, publish_new, 'certification digest publication')

buffer_anchor = r'''    private native int getBufferByteLength(JavaScriptObject obj)/*-{
        return (obj && typeof obj.byteLength === 'number') ? obj.byteLength : 0;
    }-*/;
'''
buffer_repl = buffer_anchor + r'''

    private native boolean getOptionalNestedBoolean(JavaScriptObject obj, String fieldName)/*-{
        return !!(obj && obj.object && obj.object[fieldName]);
    }-*/;

    private native int getOptionalNestedInt(JavaScriptObject obj, String fieldName)/*-{
        var value = (obj && obj.object) ? obj.object[fieldName] : 0;
        return (typeof value === 'number') ? (value | 0) : 0;
    }-*/;
'''
wtext = one(wtext, buffer_anchor, buffer_repl, 'certification native accessors')
worker.write_text(wtext)

print('Certification runtime instrumented: deterministic seed, semantic digest v1, isolated saves, ready handshake')
