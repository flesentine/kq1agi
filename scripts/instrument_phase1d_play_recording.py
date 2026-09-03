#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1d_play_recording.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# Core random observer. With no sink installed this is exactly Random.nextInt.
# ---------------------------------------------------------------------------
p = root / 'core/src/main/java/com/agifans/agile/GameState.java'
t = p.read_text()
if 'interface RandomEventSink' not in t:
    t = one(t,
'''    public Random random = new Random();
''',
'''    public Random random = new Random();

    /** Optional observer used by Phase -1D PLAY recording. */
    public interface RandomEventSink {
        void onRandom(int bound, int value, int totalTick);
    }

    private RandomEventSink randomEventSink;

    public void setRandomEventSink(RandomEventSink sink) {
        randomEventSink = sink;
    }

    public int nextRandomInt(int bound) {
        int value = random.nextInt(bound);
        if (randomEventSink != null) randomEventSink.onRandom(bound, value, getTotalTicks());
        return value;
    }
''', 'GameState random observer')
p.write_text(t)

p = root / 'core/src/main/java/com/agifans/agile/AnimatedObject.java'
t = p.read_text()
for old, new, label in [
    ('state.random.nextInt(9)', 'state.nextRandomInt(9)', 'wander direction RNG'),
    ('state.random.nextInt((Defines.MAXDIST - Defines.MINDIST))',
     'state.nextRandomInt((Defines.MAXDIST - Defines.MINDIST))', 'wander distance RNG'),
]:
    if old in t:
        t = one(t, old, new, label)
    elif new not in t:
        raise RuntimeError(f'{label}: neither original nor instrumented call found')
p.write_text(t)

p = root / 'core/src/main/java/com/agifans/agile/Commands.java'
t = p.read_text()
old = 'state.random.nextInt(255)'
new = 'state.nextRandomInt(255)'
if old in t:
    t = one(t, old, new, 'AGI random command RNG')
elif new not in t:
    raise RuntimeError('AGI random command RNG: neither original nor instrumented call found')
p.write_text(t)

p = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
t = p.read_text()
if 'setRandomEventSink(GameState.RandomEventSink sink)' not in t:
    anchor = '''    /**
     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a
'''
    method = '''    public void setRandomEventSink(GameState.RandomEventSink sink) {
        state.setRandomEventSink(sink);
    }

'''
    if t.count(anchor) != 1:
        raise RuntimeError('Interpreter animation anchor not found')
    t = t.replace(anchor, method + anchor, 1)
p.write_text(t)

# ---------------------------------------------------------------------------
# UI-thread exact transport capture: key state, encoded AGI queue and mouse SAB.
# ---------------------------------------------------------------------------
p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtUserInput.java'
t = p.read_text()
t = one(t,
'''    @Override
    public void setKey(int keycode, boolean value) {
        keys.set(keycode, value? TRUE : FALSE);
    }
''',
'''    @Override
    public void setKey(int keycode, boolean value) {
        keys.set(keycode, value? TRUE : FALSE);
        recordKeyState(keycode, value);
    }
''', 'GwtUserInput key state recorder')
t = one(t,
'''    @Override
    protected boolean keyPressQueueAdd(Integer key) {
        return keyPressQueue.add(key);
    }
''',
'''    @Override
    protected boolean keyPressQueueAdd(Integer key) {
        boolean added = keyPressQueue.add(key);
        if (added) recordQueuedKey(key.intValue());
        return added;
    }

    private native void recordKeyState(int keyCode, boolean pressed) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'key-state', keyCode: keyCode | 0, pressed: !!pressed});
    }-*/;

    private native void recordQueuedKey(int encodedKey) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'key-queue', encodedKey: encodedKey >>> 0});
    }-*/;
''', 'GwtUserInput queue recorder')
p.write_text(t)

p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java'
t = p.read_text()
if 'recordMouseState()' not in t:
    t = one(t,
'''    @Override
    public void setMouseX(int mouseX) {
        variableArray.set(MOUSE_X, mouseX);
    }
''',
'''    @Override
    public void setMouseX(int mouseX) {
        variableArray.set(MOUSE_X, mouseX);
        recordMouseState();
    }
''', 'mouse X recorder')
    t = one(t,
'''    @Override
    public void setMouseY(int mouseY) {
        variableArray.set(MOUSE_Y, mouseY);
    }
''',
'''    @Override
    public void setMouseY(int mouseY) {
        variableArray.set(MOUSE_Y, mouseY);
        recordMouseState();
    }
''', 'mouse Y recorder')
    t = one(t,
'''    @Override
    public void setMouseButton(int mouseButton) {
        variableArray.set(MOUSE_BUTTON, mouseButton);
    }
''',
'''    @Override
    public void setMouseButton(int mouseButton) {
        variableArray.set(MOUSE_BUTTON, mouseButton);
        recordMouseState();
    }

    private native void recordMouseState() /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn !== 'function') return;
        var sab = $wnd.__kq1agiVariableSAB;
        if (!sab) return;
        var vars = new Int32Array(sab);
        fn({type: 'mouse', x: vars[514] | 0, y: vars[515] | 0, button: vars[513] | 0});
    }-*/;
''', 'mouse button recorder')
p.write_text(t)

# ---------------------------------------------------------------------------
# Runner: record exact 60 Hz release decisions, actual sound completion timing,
# and worker-observed random values.
# ---------------------------------------------------------------------------
p = root / 'html/src/main/java/com/agifans/agile/gwt/GwtAgileRunner.java'
t = p.read_text()
if 'case "RecordingRandomDraw":' not in t:
    t = one(t,
'''                    case "StopSound":
                        stopCurrentSound();
                        break;
                        
                    default:
''',
'''                    case "StopSound":
                        stopCurrentSound();
                        break;

                    case "RecordingRandomDraw":
                        recordRandomDraw(
                                getNestedInt(eventObject, "bound"),
                                getNestedInt(eventObject, "value"),
                                getNestedInt(eventObject, "tick"));
                        break;
                        
                    default:
''', 'runner random message case')

t = one(t,
'''    private void soundEnded(int endFlag) {
        // The GWT VariableData implementation uses shared memory, so this is seen
        // by the web worker almost instantly, meaning that any LOGIC code that is 
        // waiting for it can continue.
        variableData.setFlag(endFlag, true);
    }
''',
'''    private void soundEnded(int endFlag) {
        // The GWT VariableData implementation uses shared memory, so this is seen
        // by the web worker almost instantly, meaning that any LOGIC code that is 
        // waiting for it can continue.
        variableData.setFlag(endFlag, true);
        recordSoundEnd(endFlag);
    }
''', 'runner sound-end recorder')

t = one(t,
'''    @Override
    public void animationTick() {
        if ((variableData.getInTick() == false) && (worker != null)) {
            // Signals to web worker to start tick.
            variableData.setInTick(true);  // NOTE: Set to false by web worker.
        }
    }
''',
'''    @Override
    public void animationTick() {
        boolean released = (variableData.getInTick() == false) && (worker != null);
        recordLogicalPulse(variableData.getTotalTicks(), released);
        if (released) {
            // Signals to web worker to start tick.
            variableData.setInTick(true);  // NOTE: Set to false by web worker.
        }
    }

    private native void recordLogicalPulse(int tick, boolean released) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'pulse', tick: tick | 0, released: !!released});
    }-*/;

    private native void recordSoundEnd(int endFlag) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'sound-end', endFlag: endFlag | 0});
    }-*/;

    private native void recordRandomDraw(int bound, int value, int tick) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'random', bound: bound | 0, value: value | 0, tick: tick | 0});
    }-*/;
''', 'runner logical pulse recorder')
p.write_text(t)

# Worker: install the random observer only for the browser PLAY journal. The
# observer posts values; it does not alter the underlying Random implementation.
p = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
t = p.read_text()
if 'import com.agifans.agile.GameState;' not in t:
    t = one(t, 'import com.agifans.agile.Interpreter;\n',
            'import com.agifans.agile.Interpreter;\nimport com.agifans.agile.GameState;\n', 'worker GameState import')
if 'setRandomEventSink(new GameState.RandomEventSink()' not in t:
    anchor = '''                interpreter = new Interpreter(
                        game, userInput, wavePlayer, savedGameStore, 
                        pixelData, variableData);
'''
    repl = anchor + '''                interpreter.setRandomEventSink(new GameState.RandomEventSink() {
                    @Override
                    public void onRandom(int bound, int value, int totalTick) {
                        postObject("RecordingRandomDraw", createRecordingRandomDraw(bound, value, totalTick));
                    }
                });
'''
    if t.count(anchor) != 1:
        raise RuntimeError(f'worker Interpreter construction: expected 1 match, found {t.count(anchor)}')
    t = t.replace(anchor, repl, 1)
if 'setRandomEventSink(new GameState.RandomEventSink()' not in t:
    raise RuntimeError('worker random recorder insertion failed')
if 'private native JavaScriptObject createRecordingRandomDraw' not in t:
    marker = '''    private native String getEventType(JavaScriptObject obj)/*-{
'''
    helper = '''    private native JavaScriptObject createRecordingRandomDraw(int bound, int value, int tick)/*-{
        return {bound: bound | 0, value: value | 0, tick: tick | 0};
    }-*/;

'''
    if t.count(marker) != 1:
        raise RuntimeError('worker native helper anchor not found')
    t = t.replace(marker, helper + marker, 1)
p.write_text(t)

print('Phase -1D PLAY journal instrumentation installed')
