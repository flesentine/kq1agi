#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) not in (2, 3):
    raise SystemExit('usage: check_truth_engine_feasibility.py /path/to/instrumented-pristine-agile [report.json]')

root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve() if len(sys.argv) == 3 else Path('truth-engine-feasibility.json').resolve()


def read(rel: str) -> str:
    path = root / rel
    if not path.exists():
        raise RuntimeError(f'missing upstream source: {rel}')
    return path.read_text()


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f'{label}: expected source marker not found: {needle!r}')


user_input = read('core/src/main/java/com/agifans/agile/UserInput.java')
gwt_input = read('html/src/main/java/com/agifans/agile/gwt/GwtUserInput.java')
gwt_vars = read('html/src/main/java/com/agifans/agile/gwt/GwtVariableData.java')
gwt_pixels = read('html/src/main/java/com/agifans/agile/gwt/GwtPixelData.java')
runner = read('html/src/main/java/com/agifans/agile/gwt/GwtAgileRunner.java')
worker = read('html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java')
game_state = read('core/src/main/java/com/agifans/agile/GameState.java')
interpreter = read('core/src/main/java/com/agifans/agile/Interpreter.java')

# 1) Independent runtime lane: each UI-side data object allocates its own SAB when
# constructed without an injected buffer, and the worker accepts those buffers.
require(gwt_input, 'SharedQueue.getStorageForCapacity(256)', 'independent key queue allocation')
require(gwt_input, 'SharedArray.getStorageForCapacity(256)', 'independent key-state allocation')
require(gwt_vars, 'if (variableArraySAB == null)', 'independent variable-state allocation')
require(gwt_pixels, 'pixelArray = createPixelArray(width, height);', 'independent pixel-state allocation')
require(runner, 'worker.postObject("Initialise", createInitialiseObject(', 'worker SAB injection')
require(worker, 'userInput = new GwtUserInput(keyPressQueueSAB, keysSAB, oldKeysSAB);', 'worker input attachment')
require(worker, 'variableData = new GwtVariableData(variableSAB);', 'worker variable attachment')

# 2) Deterministic input surface: all keyboard input funnels through setKey and the
# encoded key queue. Both are SharedArrayBuffer-backed and can be mirrored. Tick
# scheduling is also explicitly gated by IN_TICK, so a two-worker barrier is possible.
require(user_input, 'setKey((keycode & 0xFF), true);', 'keyboard state funnel')
require(user_input, 'keyPressQueueAdd(', 'keyboard queue funnel')
require(gwt_input, 'protected boolean keyPressQueueAdd(Integer key)', 'GWT key queue hook')
require(runner, 'variableData.setInTick(true)', 'UI tick gate')
require(worker, 'while (variableData.getInTick() == false)', 'worker tick gate')

# 3) Read-only semantic trace: observer instrumentation must compile against the
# pristine interpreter without replacing movement or logic code.
require(interpreter, 'public int getDiagnosticValue(int slot)', 'read-only interpreter snapshot')
require(worker, 'private SharedArray diagnosticTrace;', 'truth trace SAB')
require(worker, 'publishDiagnosticTrace();', 'post-tick truth trace publication')

# Known determinism constraints discovered by the spike. These are deliberately
# reported as blockers/constraints rather than being papered over.
rng_unseeded = 'public Random random = new Random();' in game_state
sound_async = 'currentlyPlayingSound = playSound(soundBuffer, endFlag);' in runner and 'variableData.setFlag(endFlag, true);' in runner
saved_store_shared = 'savedGameStore = new GwtSavedGameStore();' in worker
mouse_shared = 'MOUSE_X' in gwt_vars and 'MOUSE_Y' in gwt_vars and 'MOUSE_BUTTON' in gwt_vars

report = {
    'schema': 1,
    'upstream_contract': {
        'independent_worker_state': {
            'status': 'PASS_WITH_EXTERNAL_STORE_CONSTRAINT',
            'evidence': 'Fresh GwtUserInput/GwtVariableData/GwtPixelData objects allocate independent SharedArrayBuffers; worker state is attached only to buffers supplied at Initialise.',
        },
        'keyboard_input_mirroring': {
            'status': 'PASS',
            'evidence': 'Keyboard state and encoded key presses funnel through SAB-backed GwtUserInput storage and can be duplicated before either worker consumes them.',
        },
        'tick_barrier': {
            'status': 'PASS',
            'evidence': 'Both UI and worker coordinate each interpreter tick through VariableData.IN_TICK, allowing a dual-worker host to release ticks only when both lanes are idle.',
        },
        'read_only_semantic_trace': {
            'status': 'PASS',
            'evidence': 'The pristine worker compiles with a post-tick observer that publishes room/ego/flag state without participating in interpreter decisions.',
        },
    },
    'determinism_constraints': {
        'random_number_generator': {
            'status': 'BLOCKS_BIT_EXACT_PARITY' if rng_unseeded else 'REVIEW',
            'evidence': 'GameState constructs java.util.Random with no shared seed.' if rng_unseeded else 'Unseeded Random marker changed; re-audit required.',
            'required_fix': 'Supply the same deterministic seed/state stream to both lanes without changing normal non-certification play.',
        },
        'sound_completion': {
            'status': 'BLOCKS_GENERAL_PARITY' if sound_async else 'REVIEW',
            'evidence': 'Sound end flags are set asynchronously on the UI thread.' if sound_async else 'Expected asynchronous sound callback marker changed; re-audit required.',
            'required_fix': 'Record/replay sound-completion events, or use a certification clock that feeds the same completion event to both lanes.',
        },
        'saved_game_store': {
            'status': 'MUST_ISOLATE' if saved_store_shared else 'REVIEW',
            'evidence': 'Each worker constructs GwtSavedGameStore against the same browser origin.' if saved_store_shared else 'Saved-game store construction changed; re-audit required.',
            'required_fix': 'Namespace or disable writes in the truth lane during certification.',
        },
        'mouse_input': {
            'status': 'MIRRORABLE' if mouse_shared else 'REVIEW',
            'evidence': 'Mouse X/Y/button are already carried in VariableData shared slots.' if mouse_shared else 'Mouse transport markers changed; re-audit required.',
        },
    },
    'overall': {
        'status': 'FEASIBLE_WITH_DETERMINISM_WORK_REQUIRED',
        'next_step': 'Build an opt-in dual-worker certification host only after shared PRNG and external-event replay are defined. Do not use pixel comparison or the modified engine itself as the oracle.',
    },
}

out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
