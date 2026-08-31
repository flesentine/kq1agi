#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: polish_danger_compare_ui.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# Make source provenance explicit and promote DANGER from a tiny VIEW preset to a
# full-width analysis mode. ORIGINAL is always read-only and never mutates masks.
old = '''      <div class="debug-control-row">\n        <span>VIEW</span>\n        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>\n        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>\n        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>\n        <button id="debug-view-danger" class="debug-small-button debug-danger-button" type="button" title="Show WATER, scripted fall/death triggers, and editable FALL together; read-only">DANGER</button>\n      </div>\n'''
new = '''      <div id="debug-source-card" class="debug-source-card">\n        <div class="debug-source-copy">\n          <span>CONTROL SOURCE</span>\n          <small id="debug-source-note">YOUR EDITED MAP</small>\n        </div>\n        <div class="debug-source-toggle" role="group" aria-label="Control map source">\n          <button id="debug-source-edited" class="debug-source-button debug-selected" type="button">EDITED</button>\n          <button id="debug-source-original" class="debug-source-button" type="button">SIERRA</button>\n        </div>\n      </div>\n\n      <div class="debug-control-row">\n        <span>VIEW</span>\n        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>\n        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>\n        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>\n      </div>\n\n      <button id="debug-view-danger" class="debug-danger-mode-button" type="button" title="Analyze WATER, FALL/HITSPEC, and Sierra scripted death triggers together">\n        <span>DANGER</span><small>WATER + FALL + SCRIPTED DEATH</small>\n      </button>\n'''
one(old, new, 'source selector + promoted DANGER markup')

# DANGER no longer consumes a compact VIEW-grid column.
one('      grid-template-columns: 1fr repeat(4, auto);\n',
    '      grid-template-columns: 1fr repeat(3, auto);\n',
    'VIEW grid columns after DANGER promotion')

css = r'''
    .debug-source-card {
      display: grid;
      grid-template-columns: 1fr auto;
      align-items: center;
      gap: 8px;
      padding: 7px 8px;
      border: 1px solid rgba(255,255,255,.15);
      border-radius: 8px;
      background: #0b0b0c;
    }
    .debug-source-copy { display: grid; gap: 1px; min-width: 0; }
    .debug-source-copy > span {
      color: #bcbcbc;
      font: 800 8px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .10em;
    }
    .debug-source-copy > small {
      color: #777;
      font: 700 8px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      white-space: nowrap;
    }
    .debug-source-toggle {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 2px;
      padding: 2px;
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 7px;
      background: #050505;
    }
    .debug-source-button {
      min-width: 55px;
      min-height: 27px;
      padding: 0 7px;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: #858585;
      font: 850 8px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .05em;
      cursor: pointer;
    }
    .debug-source-button.debug-selected {
      background: #303030;
      color: #fff;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.18);
    }
    body.debug-source-original .debug-source-card {
      border-color: #947139;
      background: #18140d;
      box-shadow: inset 3px 0 0 #d7a94d;
    }
    body.debug-source-original #debug-source-note { color: #e4bc69; }
    body.debug-source-original #debug-source-original.debug-selected {
      background: #59441d;
      color: #fff3cf;
      box-shadow: inset 0 0 0 1px rgba(255,211,112,.35);
    }

    #debug-view-danger.debug-danger-mode-button {
      width: 100%;
      min-height: 39px;
      display: grid;
      grid-template-columns: auto 1fr;
      align-items: center;
      gap: 8px;
      padding: 0 10px;
      border: 1px solid #6c4027 !important;
      border-radius: 8px;
      background: #17100c !important;
      color: #ffb06b !important;
      cursor: pointer;
      text-align: left;
    }
    #debug-view-danger.debug-danger-mode-button > span {
      font: 900 10px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .07em;
    }
    #debug-view-danger.debug-danger-mode-button > small {
      color: #9a7357;
      font: 750 7px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .03em;
      justify-self: end;
    }
    #debug-view-danger.debug-danger-mode-button.debug-selected {
      border-color: #ff9b45 !important;
      background: #573117 !important;
      color: #fff4e8 !important;
      box-shadow: inset 3px 0 0 #ff9b45, inset 0 0 0 1px rgba(255,155,69,.18) !important;
    }
    #debug-view-danger.debug-danger-mode-button.debug-selected > small { color: #ffd2ad; }

    /* Sierra source is a viewer, not an editor. Keep the controls visible so the
       difference is obvious, but visually lock operations that could imply edits. */
    body.debug-source-original #brush-size,
    body.debug-source-original .debug-layer-grid,
    body.debug-source-original .debug-view-tools,
    body.debug-source-original .debug-undo-grid,
    body.debug-source-original #debug-view-solo,
    body.debug-source-original #debug-view-all,
    body.debug-source-original #debug-view-none {
      opacity: .34;
      filter: saturate(.55);
    }
    body.debug-source-original #debug-context-help {
      border-color: rgba(215,169,77,.32);
      background: rgba(83,61,18,.15);
    }
'''
style_close = text.rfind('</style>')
if style_close < 0:
    raise RuntimeError('style close missing for source/DANGER UX CSS')
text = text[:style_close] + css + text[style_close:]

# Browser state + direct source bridge. Shared slot 8352 is appended by the
# runtime comparison patch; 100=EDITED, 101=SIERRA ORIGINAL.
one(
'''  const debugViewDanger = document.getElementById('debug-view-danger');\n''',
'''  const debugViewDanger = document.getElementById('debug-view-danger');\n  const debugSourceEdited = document.getElementById('debug-source-edited');\n  const debugSourceOriginal = document.getElementById('debug-source-original');\n  const debugSourceNote = document.getElementById('debug-source-note');\n''',
'source UI consts')

state_anchor = '  let debugDangerActive = false;\n'
if text.count(state_anchor) != 1:
    raise RuntimeError('DANGER state anchor missing for source UI')
text = text.replace(state_anchor, state_anchor + '  let debugSourceOriginalActive = false;\n', 1)

bridge_anchor = '  const DEBUG_DANGER_VIEW_BRIDGE_INDEX = 5830;\n'
bridge = bridge_anchor + '''  const DEBUG_SOURCE_VIEW_BRIDGE_INDEX = 8352;\n\n  function setDebugSourceEngineOriginal(original) {\n    try {\n      const sab = window.__kq1agiVariableSAB;\n      if (!sab) return false;\n      const shared = new Int32Array(sab);\n      if (shared.length <= DEBUG_SOURCE_VIEW_BRIDGE_INDEX) return false;\n      Atomics.store(shared, DEBUG_SOURCE_VIEW_BRIDGE_INDEX, original ? 101 : 100);\n      if (typeof Atomics.notify === 'function') Atomics.notify(shared, DEBUG_SOURCE_VIEW_BRIDGE_INDEX, 1);\n      return true;\n    } catch (error) {\n      console.warn('Control-source direct bridge unavailable', error);\n      return false;\n    }\n  }\n\n'''
if text.count(bridge_anchor) != 1:
    raise RuntimeError('DANGER bridge constant anchor missing for source bridge')
text = text.replace(bridge_anchor, bridge, 1)

# Source-aware help/status. Keep scripted hazards in both source modes because
# those are game logic, not user-authored control-picture pixels.
old = '''  function updateDebugContextHelp() {\n    if (debugDangerActive) {\n      debugContextHelp.innerHTML = '<strong>DANGER</strong> read-only composite · <span class="legend-dot legend-water"></span>cyan = WATER control · black/white dotted marks = Sierra scripted death/fall · striped yellow = editable FALL.';\n      return;\n    }\n'''
new = '''  function updateDebugContextHelp() {\n    if (debugSourceOriginalActive && debugDangerActive) {\n      debugContextHelp.innerHTML = '<strong>SIERRA ORIGINAL · DANGER</strong> · cyan = original WATER · gold = original FALL/HITSPEC · black/white = Sierra scripted death/fall. Your edits are untouched.';\n      return;\n    }\n    if (debugSourceOriginalActive) {\n      debugContextHelp.innerHTML = '<strong>SIERRA ORIGINAL · READ ONLY</strong> · blue = BLOCK · cyan = WATER · gold = FALL/HITSPEC. Switch to EDITED to paint.';\n      return;\n    }\n    if (debugDangerActive) {\n      debugContextHelp.innerHTML = '<strong>EDITED · DANGER</strong> read-only composite · <span class="legend-dot legend-water"></span>cyan = your WATER · black/white = Sierra scripted death/fall · striped yellow = your FALL.';\n      return;\n    }\n'''
one(old, new, 'source-aware context help')

old = '''    const mode = debugDangerActive ? 'DANGER'\n      : debugMode === 'sprites' ? 'SPRITES'\n'''
new = '''    const mode = debugDangerActive ? (debugSourceOriginalActive ? 'DANGER · SIERRA' : 'DANGER · EDITED')\n      : debugSourceOriginalActive ? 'SIERRA ORIGINAL'\n      : debugMode === 'sprites' ? 'SPRITES'\n'''
one(old, new, 'source-aware workspace status')

# Centralized source UI also hard-disables meaningless edit controls while Sierra
# is being inspected. DANGER stays live so users can compare the same hazard view.
listener_anchor = '''  debugViewDanger.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });\n'''
source_helpers = r'''  function refreshDebugSourceUi() {
    document.body.classList.toggle('debug-source-original', debugSourceOriginalActive);
    debugSourceEdited.classList.toggle('debug-selected', !debugSourceOriginalActive);
    debugSourceOriginal.classList.toggle('debug-selected', debugSourceOriginalActive);
    debugSourceNote.textContent = debugSourceOriginalActive ? 'SIERRA ORIGINAL · READ ONLY' : 'YOUR EDITED MAP';
    const lockIds = [
      'brush-size', 'debug-layer-front', 'debug-layer-block', 'debug-layer-behind',
      'debug-layer-water', 'debug-layer-fall', 'debug-eraser-button',
      'debug-fill-button', 'debug-outline-button', 'debug-undo-button', 'debug-redo-button',
      'debug-view-solo', 'debug-view-all', 'debug-view-none'
    ];
    for (const id of lockIds) {
      const el = document.getElementById(id);
      if (el) el.disabled = debugSourceOriginalActive;
    }
    updateDebugContextHelp();
    updateDebugWorkspaceStatus();
  }

  function setDebugSourceOriginal(original) {
    original = !!original;
    if (debugSourceOriginalActive === original) return;
    if (!setDebugSourceEngineOriginal(original)) {
      debugContextHelp.textContent = 'ORIGINAL comparison needs the latest game runtime. Hard refresh once and try again.';
      return;
    }
    debugSourceOriginalActive = original;
    debugEraserActive = false;
    debugEraserButton.classList.remove('debug-selected');
    refreshDebugSourceUi();
  }

  debugSourceEdited.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation(); setDebugSourceOriginal(false);
  });
  debugSourceOriginal.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation(); setDebugSourceOriginal(true);
  });

'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('DANGER listener anchor missing for source controls')
text = text.replace(listener_anchor, source_helpers + listener_anchor, 1)

# Keep body-level mode styling in sync with the existing DANGER toggle.
old = '''    debugDangerActive = next;\n    if (!next) {\n'''
new = '''    debugDangerActive = next;\n    document.body.classList.toggle('debug-danger-active', debugDangerActive);\n    if (!next) {\n'''
one(old, new, 'DANGER body state')

# Closing EDIT must always return the engine to EDITED for the next session.
old = '''    if (!paintUiActive && debugDangerActive) {\n      setDebugDangerEngineActive(false);\n      debugDangerActive = false;\n      if (debugViewDanger) debugViewDanger.classList.remove('debug-selected');\n    }\n'''
new = '''    if (!paintUiActive && debugDangerActive) {\n      setDebugDangerEngineActive(false);\n      debugDangerActive = false;\n      document.body.classList.remove('debug-danger-active');\n      if (debugViewDanger) debugViewDanger.classList.remove('debug-selected');\n    }\n    if (!paintUiActive && debugSourceOriginalActive) {\n      setDebugSourceEngineOriginal(false);\n      debugSourceOriginalActive = false;\n      document.body.classList.remove('debug-source-original');\n      if (debugSourceEdited) debugSourceEdited.classList.add('debug-selected');\n      if (debugSourceOriginal) debugSourceOriginal.classList.remove('debug-selected');\n    }\n'''
one(old, new, 'EDIT close source cleanup')

# Initial state is explicit and self-documenting.
init_anchor = '  refreshDebugButtonAvailability();\n'
if text.count(init_anchor) < 1:
    raise RuntimeError('debug availability init anchor missing')
text = text.replace(init_anchor, '  refreshDebugSourceUi();\n' + init_anchor, 1)

old_tag = "const BUILD_TAG = '20260831-danger-composite-v2';"
new_tag = "const BUILD_TAG = '20260831-edit-source-compare-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('DANGER build tag not found for source compare')

path.write_text(text)
print('EDIT source UX polished: DANGER promoted to analysis mode; EDITED/SIERRA read-only comparison added')
