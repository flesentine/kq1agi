#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_shift_left_rewind.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# ---------------------------------------------------------------------------
# 1) SavedGames: add a no-dialog path that reuses AGILE's real save/restore
# serializer, but targets hidden in-memory slots instead of the player's 12 saves.
# ---------------------------------------------------------------------------
saved_games = root / 'core/src/main/java/com/agifans/agile/SavedGames.java'
text = saved_games.read_text()

field_anchor = '''    private boolean firstTime = true;\n'''
field_repl = '''    private boolean firstTime = true;\n\n    // Rewind snapshots deliberately bypass the normal save-game picker. They still\n    // use AGILE's complete save/restore serializer, so room, score, inventory,\n    // flags, animated objects, script state, etc. rewind together.\n    private SavedGame forcedSavedGame;\n    private static final String REWIND_DESCRIPTION = "__AGILE_REWIND__";\n'''
if text.count(field_anchor) != 1:
    raise RuntimeError('SavedGames firstTime field anchor not found')
text = text.replace(field_anchor, field_repl, 1)

choose_anchor = '''    private SavedGame chooseGame(char function) {\n        SavedGame[] game = new SavedGame[NUM_GAMES];\n'''
choose_repl = '''    private SavedGame chooseGame(char function) {\n        if (forcedSavedGame != null) return forcedSavedGame;\n\n        SavedGame[] game = new SavedGame[NUM_GAMES];\n'''
if text.count(choose_anchor) != 1:
    raise RuntimeError('SavedGames chooseGame anchor not found')
text = text.replace(choose_anchor, choose_repl, 1)

save_anchor = '''    /**\n     * Saves the GameState of the Interpreter to a saved game file.\n     */\n    public void saveGameState() {\n'''
rewind_methods = '''    /** Save a complete rewind snapshot without showing any Sierra save UI. */\n    public boolean saveRewindState(int slot) {\n        String previousSimpleName = state.simpleName;\n        SavedGame previousForcedGame = forcedSavedGame;\n        try {\n            SavedGame rewindGame = savedGameStore.getSavedGameByNumber(state.gameId, slot);\n            rewindGame.description = REWIND_DESCRIPTION;\n            forcedSavedGame = rewindGame;\n            // Existing saveGameState already skips confirmations in simple-save mode.\n            state.simpleName = REWIND_DESCRIPTION;\n            saveGameState();\n            return true;\n        } finally {\n            forcedSavedGame = previousForcedGame;\n            state.simpleName = previousSimpleName;\n        }\n    }\n\n    /** Restore a complete rewind snapshot without showing any Sierra restore UI. */\n    public boolean restoreRewindState(int slot) {\n        String previousSimpleName = state.simpleName;\n        SavedGame previousForcedGame = forcedSavedGame;\n        try {\n            SavedGame rewindGame = savedGameStore.getSavedGameByNumber(state.gameId, slot);\n            if (rewindGame == null || !rewindGame.exists || rewindGame.savedGameData == null\n                    || rewindGame.savedGameData.length == 0) return false;\n            forcedSavedGame = rewindGame;\n            state.simpleName = REWIND_DESCRIPTION;\n            return restoreGameState();\n        } finally {\n            forcedSavedGame = previousForcedGame;\n            state.simpleName = previousSimpleName;\n        }\n    }\n\n    /**\n     * Saves the GameState of the Interpreter to a saved game file.\n     */\n    public void saveGameState() {\n'''
if text.count(save_anchor) != 1:
    raise RuntimeError('SavedGames saveGameState anchor not found')
text = text.replace(save_anchor, rewind_methods, 1)
saved_games.write_text(text)

# ---------------------------------------------------------------------------
# 2) Browser SavedGameStore: slots above 12 are private RAM-only rewind slots.
# Player saves 1..12 remain completely unchanged and continue to use OPFS.
# ---------------------------------------------------------------------------
gwt_store = root / 'html/src/main/java/com/agifans/agile/gwt/GwtSavedGameStore.java'
text = gwt_store.read_text()

store_field = '''    private OPFSSavedGames opfsSavedGames;\n'''
store_field_repl = '''    private OPFSSavedGames opfsSavedGames;\n\n    // Hidden slots 13+ are volatile rewind snapshots. Keeping them in worker RAM\n    // avoids touching the player's 12 normal save files and makes 1-second\n    // snapshots cheap enough for continuous play.\n    private final java.util.Map<Integer, byte[]> rewindSavedGames =\n            new java.util.HashMap<Integer, byte[]>();\n'''
if text.count(store_field) != 1:
    raise RuntimeError('GwtSavedGameStore field anchor not found')
text = text.replace(store_field, store_field_repl, 1)

get_anchor = '''    public SavedGame getSavedGameByNumber(String gameId, int num) {\n        SavedGame theGame = new SavedGame();\n        theGame.num = num;\n\n        // Build full path to the saved game of this number for this game ID.\n'''
get_repl = '''    public SavedGame getSavedGameByNumber(String gameId, int num) {\n        SavedGame theGame = new SavedGame();\n        theGame.num = num;\n\n        if (num > 12) {\n            byte[] stored = rewindSavedGames.get(num);\n            theGame.fileName = "memory://rewind/" + num;\n            if (stored != null && stored.length > 0) {\n                // restoreGameState mutates AGI V3 object bytes while decrypting, so\n                // always hand it a fresh copy rather than the canonical snapshot.\n                byte[] copy = new byte[stored.length];\n                System.arraycopy(stored, 0, copy, 0, stored.length);\n                theGame.savedGameData = copy;\n                theGame.description = "__AGILE_REWIND__";\n                theGame.fileTime = System.currentTimeMillis();\n                theGame.exists = true;\n            } else {\n                theGame.savedGameData = new byte[0];\n                theGame.description = "";\n                theGame.exists = false;\n            }\n            return theGame;\n        }\n\n        // Build full path to the saved game of this number for this game ID.\n'''
if text.count(get_anchor) != 1:
    raise RuntimeError('GwtSavedGameStore getSavedGameByNumber anchor not found')
text = text.replace(get_anchor, get_repl, 1)

save_store_anchor = '''    public boolean saveGame(SavedGame savedGame, byte[] savedGameData, int length) {\n        // Convert the Java byte array into an Int8Array.\n'''
save_store_repl = '''    public boolean saveGame(SavedGame savedGame, byte[] savedGameData, int length) {\n        if (savedGame != null && savedGame.num > 12) {\n            byte[] copy = new byte[length];\n            System.arraycopy(savedGameData, 0, copy, 0, length);\n            rewindSavedGames.put(savedGame.num, copy);\n            return true;\n        }\n\n        // Convert the Java byte array into an Int8Array.\n'''
if text.count(save_store_anchor) != 1:
    raise RuntimeError('GwtSavedGameStore saveGame anchor not found')
text = text.replace(save_store_anchor, save_store_repl, 1)
gwt_store.write_text(text)

# ---------------------------------------------------------------------------
# 3) Commands: expose the hidden snapshot operations to Interpreter.
# ---------------------------------------------------------------------------
commands = root / 'core/src/main/java/com/agifans/agile/Commands.java'
text = commands.read_text()
constructor_tail = '''        this.savedGames = new SavedGames(state, userInput, textGraphics, pixelData, savedGameStore);\n        this.soundPlayer = soundPlayer;\n    }\n\n    /**\n     * Draws the AGI Picture identified by the given picture number.\n'''
constructor_repl = '''        this.savedGames = new SavedGames(state, userInput, textGraphics, pixelData, savedGameStore);\n        this.soundPlayer = soundPlayer;\n    }\n\n    public boolean saveRewindState(int slot) {\n        return savedGames.saveRewindState(slot);\n    }\n\n    public boolean restoreRewindState(int slot) {\n        return savedGames.restoreRewindState(slot);\n    }\n\n    /**\n     * Draws the AGI Picture identified by the given picture number.\n'''
if text.count(constructor_tail) != 1:
    raise RuntimeError('Commands constructor tail anchor not found')
text = text.replace(constructor_tail, constructor_repl, 1)
commands.write_text(text)

# ---------------------------------------------------------------------------
# 4) UserInput: Shift+Left belongs to rewind, not Sierra movement/key mapping.
# The raw key states are still updated so Interpreter can detect the chord.
# ---------------------------------------------------------------------------
user_input = root / 'core/src/main/java/com/agifans/agile/UserInput.java'
text = user_input.read_text()
input_anchor = '''        setKey((keycode & 0xFF), true);\n\n        // Update modifies for ALT/SHIFT/CONTROL but do not enqueue key presses that \n'''
input_repl = '''        setKey((keycode & 0xFF), true);\n\n        // Shift+Left is the browser rewind chord. Preserve the raw pressed state\n        // for Interpreter, but never enqueue LEFT into the AGI game itself.\n        if (keycode == Keys.LEFT\n                && (keys(Keys.SHIFT_LEFT) || keys(Keys.SHIFT_RIGHT))) {\n            return true;\n        }\n\n        // Update modifies for ALT/SHIFT/CONTROL but do not enqueue key presses that \n'''
if text.count(input_anchor) != 1:
    raise RuntimeError('UserInput setKey anchor not found')
text = text.replace(input_anchor, input_repl, 1)
user_input.write_text(text)

# ---------------------------------------------------------------------------
# 5) Interpreter: keep 60 one-second snapshots. Tap Shift+Left steps back about
# one second; holding it repeatedly steps backward while forward simulation pauses.
# Releasing the chord forks history from the restored point.
# ---------------------------------------------------------------------------
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
text = interpreter.read_text()

interpreter_field = '''    private volatile boolean inTick;\n'''
interpreter_field_repl = '''    private volatile boolean inTick;\n\n    private static final int REWIND_FIRST_SLOT = 13;\n    private static final int REWIND_SLOT_COUNT = 60;\n    private static final long REWIND_CAPTURE_MS = 1000L;\n    private static final long REWIND_HOLD_STEP_MS = 150L;\n\n    private int rewindNextIndex;\n    private int rewindCount;\n    private int rewindCursorIndex = -1;\n    private int rewindStepsBack;\n    private boolean rewindHeld;\n    private long rewindLastCaptureMillis;\n    private long rewindLastStepMillis;\n'''
if text.count(interpreter_field) != 1:
    raise RuntimeError('Interpreter inTick field anchor not found')
text = text.replace(interpreter_field, interpreter_field_repl, 1)

animation_doc = '''    /**\n     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a\n     * second, but the rate at which the logics are run and the animation updated is determined\n     * by the animation interval variable.\n     */\n    public void animationTick() {\n'''
rewind_helpers = '''    private boolean rewindChordDown() {\n        boolean shift = userInput.keys(Keys.SHIFT_LEFT) || userInput.keys(Keys.SHIFT_RIGHT);\n        return shift && userInput.keys(Keys.LEFT);\n    }\n\n    private boolean rewindIsSafeNow() {\n        return state.currentPicture != null\n                && state.currentInput != null\n                && state.currentInput.length() == 0\n                && !state.menuOpen\n                && !textGraphics.isWindowOpen();\n    }\n\n    private void captureRewindIfDue(long now) {\n        if (rewindHeld || !rewindIsSafeNow()) return;\n        if (rewindLastCaptureMillis != 0\n                && (now - rewindLastCaptureMillis) < REWIND_CAPTURE_MS) return;\n\n        int slot = REWIND_FIRST_SLOT + rewindNextIndex;\n        if (commands.saveRewindState(slot)) {\n            rewindNextIndex = (rewindNextIndex + 1) % REWIND_SLOT_COUNT;\n            if (rewindCount < REWIND_SLOT_COUNT) rewindCount++;\n            rewindLastCaptureMillis = now;\n        }\n    }\n\n    private void finishRewind(long now) {\n        if (rewindStepsBack > 0) {\n            // The current restored snapshot becomes the newest point in history.\n            // Any snapshots that were newer than it belong to the abandoned future.\n            int currentIndex = (rewindNextIndex - rewindStepsBack) % REWIND_SLOT_COUNT;\n            if (currentIndex < 0) currentIndex += REWIND_SLOT_COUNT;\n            rewindNextIndex = (currentIndex + 1) % REWIND_SLOT_COUNT;\n            rewindCount = Math.max(1, rewindCount - Math.max(0, rewindStepsBack - 1));\n        }\n\n        rewindHeld = false;\n        rewindCursorIndex = -1;\n        rewindStepsBack = 0;\n        rewindLastStepMillis = 0;\n        rewindLastCaptureMillis = now;\n    }\n\n    /**\n     * @return true while rewind owns this frame and normal forward simulation must pause.\n     */\n    private boolean handleRewindInput(long now) {\n        if (!rewindChordDown()) {\n            if (rewindHeld) finishRewind(now);\n            return false;\n        }\n\n        if (!rewindIsSafeNow() || rewindCount <= 0) return false;\n\n        if (!rewindHeld) {\n            rewindHeld = true;\n            rewindCursorIndex = (rewindNextIndex - 1 + REWIND_SLOT_COUNT) % REWIND_SLOT_COUNT;\n            rewindStepsBack = 0;\n            rewindLastStepMillis = 0;\n        }\n\n        if (rewindStepsBack < rewindCount\n                && (rewindLastStepMillis == 0\n                    || (now - rewindLastStepMillis) >= REWIND_HOLD_STEP_MS)) {\n            int slot = REWIND_FIRST_SLOT + rewindCursorIndex;\n            if (commands.restoreRewindState(slot)) {\n                rewindStepsBack++;\n                rewindCursorIndex = (rewindCursorIndex - 1 + REWIND_SLOT_COUNT) % REWIND_SLOT_COUNT;\n                rewindLastStepMillis = now;\n            }\n        }\n\n        return true;\n    }\n\n    /**\n     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a\n     * second, but the rate at which the logics are run and the animation updated is determined\n     * by the animation interval variable.\n     */\n    public void animationTick() {\n'''
if text.count(animation_doc) != 1:
    raise RuntimeError('Interpreter animationTick documentation anchor not found')
text = text.replace(animation_doc, rewind_helpers, 1)

start_anchor = '''        if (!inTick) {\n            inTick = true;\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
start_repl = '''        if (!inTick) {\n            inTick = true;\n\n            // Rewind is checked before the normal animation interval gate so holding\n            // Shift+Left feels immediate and forward simulation freezes between steps.\n            if (handleRewindInput(System.currentTimeMillis())) {\n                userInput.copyKeysToOldKeys();\n                state.copyMouseButtonToOldMouseButton();\n                inTick = false;\n                return;\n            }\n\n            // Proceed only if the animation tick count has reached the set animation interval x 3.\n'''
if text.count(start_anchor) != 1:
    raise RuntimeError('Interpreter animationTick start anchor not found')
text = text.replace(start_anchor, start_repl, 1)

end_anchor = '''            // Store what the key and mouse button states were in this cycle before leaving.\n            userInput.copyKeysToOldKeys();\n'''
end_repl = '''            // Capture only coherent, completed interpreter cycles. The 60 hidden\n            // one-second snapshots provide roughly one minute of rewind history.\n            captureRewindIfDue(System.currentTimeMillis());\n\n            // Store what the key and mouse button states were in this cycle before leaving.\n            userInput.copyKeysToOldKeys();\n'''
if text.count(end_anchor) != 1:
    raise RuntimeError('Interpreter animationTick end anchor not found')
text = text.replace(end_anchor, end_repl, 1)
interpreter.write_text(text)

print('Shift+Left rewind installed: 60 seconds of full-state snapshots, tap to step back, hold to keep rewinding')
