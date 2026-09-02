#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_truth_worker.py /path/to/pristine-agile-gdx')

root = Path(sys.argv[1]).resolve()
interpreter = root / 'core/src/main/java/com/agifans/agile/Interpreter.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


# Read-only diagnostic access. This deliberately does not change movement, logic,
# input, timing, random state, flags, or any other interpreter behavior.
text = interpreter.read_text()
anchor = '''    /**\n     * Executes a single AGI interpreter animation tick. This method is invoked 60 times a\n'''
diagnostic = r'''    /**
     * Read-only truth-engine snapshot contract. The reference worker calls this
     * after a completed interpreter tick. No state is mutated by this method.
     *
     *  0 schema version
     *  1 total ticks
     *  2 current room
     *  3 ego x
     *  4 ego y (baseline)
     *  5 ego direction
     *  6 ONWATER
     *  7 HITSPEC
     *  8 EGOEDGE
     *  9 ego view
     * 10 ego loop
     * 11 ego cel
     * 12 ego priority
     * 13 user-control flag
     * 14 hold-key mode
     * 15 reserved
     */
    public int getDiagnosticValue(int slot) {
        switch (slot) {
            case 0: return 1;
            case 1: return state.getTotalTicks();
            case 2: return state.getVar(Defines.CURROOM);
            case 3: return state.ego.x;
            case 4: return state.ego.y;
            case 5: return state.getVar(Defines.EGODIR);
            case 6: return state.getFlag(Defines.ONWATER) ? 1 : 0;
            case 7: return state.getFlag(Defines.HITSPEC) ? 1 : 0;
            case 8: return state.getVar(Defines.EGOEDGE);
            case 9: return state.ego.currentView;
            case 10: return state.ego.currentLoop;
            case 11: return state.ego.currentCel;
            case 12: return state.ego.priority;
            case 13: return state.userControl ? 1 : 0;
            case 14: return state.holdKey ? 1 : 0;
            default: return 0;
        }
    }

'''
text = one(text, anchor, diagnostic + anchor, 'Interpreter diagnostic insertion')
interpreter.write_text(text)


text = worker.read_text()
text = one(
    text,
    'import com.agifans.agile.gwt.OPFSGameFiles;\n',
    'import com.agifans.agile.gwt.OPFSGameFiles;\nimport com.agifans.agile.gwt.SharedArray;\n',
    'truth trace SharedArray import',
)
text = one(
    text,
    '''    private Interpreter interpreter;\n''',
    '''    private Interpreter interpreter;\n\n    // Optional read-only trace transport supplied by a future dual-runner host.\n    private SharedArray diagnosticTrace;\n''',
    'truth trace field',
)

# Attach an optional trace SAB without making the pristine worker depend on one.
init_anchor = '''                JavaScriptObject pixelDataSAB = getNestedObject(eventObject, "pixelDataSAB");\n'''
init_repl = init_anchor + '''                JavaScriptObject diagnosticTraceSAB = getOptionalNestedObject(eventObject, "diagnosticTraceSAB");\n'''
text = one(text, init_anchor, init_repl, 'truth trace Initialise field')

construct_anchor = '''                pixelData = new GwtPixelData(pixelDataSAB);\n'''
construct_repl = construct_anchor + '''                if (diagnosticTraceSAB != null) diagnosticTrace = new SharedArray(diagnosticTraceSAB);\n'''
text = one(text, construct_anchor, construct_repl, 'truth trace construction')

# Publish only after the interpreter has completed the tick. This observer does not
# participate in any interpreter decisions.
tick_anchor = '''            interpreter.animationTick();\n'''
tick_repl = tick_anchor + '''            publishDiagnosticTrace();\n'''
text = one(text, tick_anchor, tick_repl, 'truth trace tick observer')

native_anchor = '''    public native void exportPerformAnimationTick() /*-{\n'''
publisher = r'''    private void publishDiagnosticTrace() {
        if (diagnosticTrace == null || interpreter == null) return;
        for (int slot = 0; slot < 16; slot++) {
            diagnosticTrace.set(slot, interpreter.getDiagnosticValue(slot));
        }
    }

'''
text = one(text, native_anchor, publisher + native_anchor, 'truth trace publisher')

nested_anchor = '''    private native JavaScriptObject getNestedObject(JavaScriptObject obj, String fieldName)/*-{\n        return obj.object[fieldName];\n    }-*/;\n'''
nested_repl = nested_anchor + r'''
    private native JavaScriptObject getOptionalNestedObject(JavaScriptObject obj, String fieldName)/*-{
        return (obj && obj.object && obj.object[fieldName]) ? obj.object[fieldName] : null;
    }-*/;
'''
text = one(text, nested_anchor, nested_repl, 'optional truth trace SAB accessor')
worker.write_text(text)

print('Truth worker instrumented read-only: 16-slot semantic snapshot published after completed ticks')
