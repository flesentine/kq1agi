#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: instrument_phase1d_recording_boundary.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
runner = root / 'html/src/main/java/com/agifans/agile/gwt/GwtAgileRunner.java'
worker = root / 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'


def one(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    return text.replace(old, new, 1)


if not runner.exists() or not worker.exists():
    raise RuntimeError('AGILE source tree is incomplete')

# Worker messages are FIFO. The cycle-complete marker is posted after the
# interpreter returns and therefore arrives after every RecordingRandomDraw message
# from that cycle. The UI uses it only to decide when the in-memory journal can be
# frozen without losing worker-originated RNG observations.
t = runner.read_text()
if 'case "RecordingCycleComplete":' not in t:
    t = one(t,
'''                    case "RecordingRandomDraw":
                        recordRandomDraw(
                                getNestedInt(eventObject, "bound"),
                                getNestedInt(eventObject, "value"),
                                getNestedInt(eventObject, "tick"));
                        break;
''',
'''                    case "RecordingRandomDraw":
                        recordRandomDraw(
                                getNestedInt(eventObject, "bound"),
                                getNestedInt(eventObject, "value"),
                                getNestedInt(eventObject, "tick"));
                        break;

                    case "RecordingCycleComplete":
                        recordCycleComplete(getNestedInt(eventObject, "tick"));
                        break;
''', 'runner cycle-complete message case')

if 'private native void recordCycleComplete' not in t:
    t = one(t,
'''    private native void recordRandomDraw(int bound, int value, int tick) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'random', bound: bound | 0, value: value | 0, tick: tick | 0});
    }-*/;
''',
'''    private native void recordRandomDraw(int bound, int value, int tick) /*-{
        var fn = $wnd.__kq1agiRecordTransportEvent;
        if (typeof fn === 'function') fn({type: 'random', bound: bound | 0, value: value | 0, tick: tick | 0});
    }-*/;

    private native void recordCycleComplete(int tick) /*-{
        $wnd.__kq1agiPlayLastCompletedTick = tick | 0;
    }-*/;
''', 'runner cycle-complete recorder')

# AppConfigItem.filePath is the exact directory name passed to OPFSGameFiles for
# imported games. Capture it at PLAY start so REPLAY PLAY cannot accidentally bind
# one game's journal to a different GAMEFILES.DAT selected in the CERTIFY panel.
# Reset the in-memory journal at the same point so switching games in one page
# cannot merge two independent PLAY sessions into one apparently valid recording.
if 'recordPlayGameDirectory(appConfigItem.getFilePath());' not in t:
    t = one(t,
'''    @Override
    public void start(AppConfigItem appConfigItem) {
        String newURL = "";
''',
'''    @Override
    public void start(AppConfigItem appConfigItem) {
        recordPlayGameDirectory(appConfigItem.getFilePath());
        String newURL = "";
''', 'runner PLAY game identity')

if 'private native void recordPlayGameDirectory' not in t:
    t = one(t,
'''    private native void recordCycleComplete(int tick) /*-{
        $wnd.__kq1agiPlayLastCompletedTick = tick | 0;
    }-*/;
''',
'''    private native void recordCycleComplete(int tick) /*-{
        $wnd.__kq1agiPlayLastCompletedTick = tick | 0;
    }-*/;

    private native void recordPlayGameDirectory(String gameDirectory) /*-{
        var journal = $wnd.__kq1agiPlayRecordingRaw;
        if (Array.isArray(journal)) journal.length = 0;
        else $wnd.__kq1agiPlayRecordingRaw = [];
        $wnd.__kq1agiPlayRecordingSeq = 0;
        $wnd.__kq1agiPlayRecordingOverflow = false;
        $wnd.__kq1agiPlayLastCompletedTick = 0;
        $wnd.__kq1agiPlayGameDirectory = gameDirectory || '';
    }-*/;
''', 'runner PLAY game identity helper')
runner.write_text(t)


t = worker.read_text()
if 'postObject("RecordingCycleComplete"' not in t:
    t = one(t,
'''            // Perform one animation tick.
            interpreter.animationTick();
            
            variableData.setInTick(false);
''',
'''            // Perform one animation tick.
            interpreter.animationTick();
            postObject("RecordingCycleComplete", createRecordingCycleComplete(currentTotalTicks));
            
            variableData.setInTick(false);
''', 'worker cycle-complete post')

if 'private native JavaScriptObject createRecordingCycleComplete' not in t:
    t = one(t,
'''    private native JavaScriptObject createRecordingRandomDraw(int bound, int value, int tick)/*-{
        return {bound: bound | 0, value: value | 0, tick: tick | 0};
    }-*/;
''',
'''    private native JavaScriptObject createRecordingRandomDraw(int bound, int value, int tick)/*-{
        return {bound: bound | 0, value: value | 0, tick: tick | 0};
    }-*/;

    private native JavaScriptObject createRecordingCycleComplete(int tick)/*-{
        return {tick: tick | 0};
    }-*/;
''', 'worker cycle-complete object helper')
worker.write_text(t)

print('Phase -1D PLAY completion boundary, session reset, and local-game identity installed')
