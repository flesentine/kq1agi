#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_fall_scan_refresh.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# FALL data should normally be preloaded by the interpreter before DEBUG opens.
# Keep the browser as a repair/diagnostic layer: it can reissue stale room state,
# time a genuinely stuck handshake, expose the raw seed values, and let the user
# retry instead of showing SCANNING forever.
read_anchor = '''  function readFallAccessibilityState() {\n'''
read_repl = '''  const FALL_EDITOR_ROOM_INDEX = 520;\n  let fallScanWatch = { room: -1, startedAt: 0 };\n\n  function readFallAccessibilityState() {\n'''
one(read_anchor, read_repl, 'FALL scan watch anchor')

old_state = '''      const room = readDebugInt(values, 0) & 255;\n      const fallReady = readDebugInt(values, FALL_CONTROL_SEED_STATE) === room + 1;\n      const scriptReady = readDebugInt(values, SCRIPT_FALL_SEED_STATE) === room + 1;\n      return {\n        available: true,\n        room,\n        fallReady,\n        scriptReady,\n        fallPixels: fallReady ? countExactMaskPixels(values, FALL_MASK_BITS_BASE) : null,\n        scriptPixels: scriptReady ? countExactMaskPixels(values, SCRIPT_FALL_BITS_BASE) : null\n      };\n'''
new_state = '''      const room = readDebugInt(values, 0) & 255;\n      const editorRoom = readDebugInt(values, FALL_EDITOR_ROOM_INDEX);\n      const expectedSeed = room + 1;\n      let fallSeed = readDebugInt(values, FALL_CONTROL_SEED_STATE);\n      let scriptSeed = readDebugInt(values, SCRIPT_FALL_SEED_STATE);\n\n      // Normal gameplay preloads these. This is only a repair path for a cleared\n      // slot or stale room value. A negative value is the worker request.\n      if (room > 0 && fallSeed !== expectedSeed && fallSeed !== -expectedSeed) {\n        Atomics.store(values, FALL_CONTROL_SEED_STATE, -expectedSeed);\n        fallSeed = -expectedSeed;\n      }\n      if (room > 0 && scriptSeed !== expectedSeed && scriptSeed !== -expectedSeed) {\n        Atomics.store(values, SCRIPT_FALL_SEED_STATE, -expectedSeed);\n        scriptSeed = -expectedSeed;\n      }\n\n      const fallReady = fallSeed === expectedSeed;\n      const scriptReady = scriptSeed === expectedSeed;\n      const ready = fallReady && scriptReady;\n      const now = Date.now();\n      if (fallScanWatch.room !== room) fallScanWatch = { room, startedAt: ready ? 0 : now };\n      if (ready) fallScanWatch.startedAt = 0;\n      else if (!fallScanWatch.startedAt) fallScanWatch.startedAt = now;\n      const scanAgeMs = ready ? 0 : Math.max(0, now - fallScanWatch.startedAt);\n\n      return {\n        available: true,\n        room,\n        editorRoom,\n        fallReady,\n        scriptReady,\n        fallSeed,\n        scriptSeed,\n        stalled: !ready && scanAgeMs >= 4000,\n        scanAgeMs,\n        fallPixels: fallReady ? countExactMaskPixels(values, FALL_MASK_BITS_BASE) : null,\n        scriptPixels: scriptReady ? countExactMaskPixels(values, SCRIPT_FALL_BITS_BASE) : null\n      };\n'''
one(old_state, new_state, 'FALL scan state block')

old_text = '''    const fallText = state.fallReady ? (state.fallPixels + ' px') : 'SCANNING…';\n    const scriptText = state.scriptReady ? (state.scriptPixels + ' px') : 'SCANNING…';\n'''
new_text = '''    const fallText = state.fallReady ? (state.fallPixels + ' px') : (state.stalled ? 'STALLED' : 'SCANNING…');\n    const scriptText = state.scriptReady ? (state.scriptPixels + ' px') : (state.stalled ? 'STALLED' : 'SCANNING…');\n'''
one(old_text, new_text, 'FALL scan label text')

old_wait = '''    } else if (!ready) {\n      html += '<span class="fall-access-status">Waiting for the room control/script scan before deciding whether FALL is empty.</span>';\n    }\n'''
new_wait = '''    } else if (!ready) {\n      if (state.stalled) {\n        html += '<span class="fall-access-status fall-access-warning">SCAN STALLED · game room='\n          + state.room + ' · editor room=' + state.editorRoom\n          + ' · control seed=' + state.fallSeed + ' · script seed=' + state.scriptSeed\n          + '<button id="debug-fall-retry" type="button" style="min-height:20px!important;padding:2px 7px!important;margin-left:6px;font-size:8px">RETRY</button></span>';\n      } else {\n        html += '<span class="fall-access-status">Preloading room control/script data…</span>';\n      }\n    }\n'''
one(old_wait, new_wait, 'FALL waiting/stalled help')

help_anchor = '''  function updateDebugContextHelp() {\n'''
help_repl = '''  function retryFallScan() {\n    try {\n      const sab = window.__kq1agiVariableSAB;\n      if (!sab) return;\n      const values = new Int32Array(sab);\n      const room = readDebugInt(values, 0) & 255;\n      if (room <= 0) return;\n      // Reset to idle; the next status refresh and worker preload path both turn\n      // this into a fresh room-scoped negative request.\n      Atomics.store(values, FALL_CONTROL_SEED_STATE, 0);\n      Atomics.store(values, SCRIPT_FALL_SEED_STATE, 0);\n      fallScanWatch = { room, startedAt: Date.now() };\n      updateDebugContextHelp();\n    } catch (error) {\n      console.warn('FALL scan retry failed', error);\n    }\n  }\n\n  debugContextHelp.addEventListener('click', event => {\n    if (event.target && event.target.id === 'debug-fall-retry') retryFallScan();\n  });\n\n  function updateDebugContextHelp() {\n'''
one(help_anchor, help_repl, 'FALL retry handler anchor')

old = "const BUILD_TAG = '20260828-fall-accessible-v1';"
new = "const BUILD_TAG = '20260828-fall-accessible-v6-adopt';"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError('FALL accessibility build tag not found for preload-adoption refresh')

path.write_text(text)
print('FALL preload-adoption UI tag installed: worker-ready maps survive initial editor sync')
