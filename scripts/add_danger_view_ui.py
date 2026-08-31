#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_danger_view_ui.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# DANGER is deliberately a VIEW, not another editable mask.
old = '''        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>
        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>
        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>
'''
new = '''        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>
        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>
        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>
        <button id="debug-view-danger" class="debug-small-button debug-danger-button" type="button" title="Show WATER, scripted fall/death triggers, and editable FALL together; read-only">DANGER</button>
'''
one(old, new, 'VIEW button row')

one('      grid-template-columns: 1fr repeat(3, auto);\n',
    '      grid-template-columns: 1fr repeat(4, auto);\n',
    'VIEW grid columns')

css = r'''
    #debug-view-danger {
      color: #ffb06b !important;
      border-color: #7a4c2d !important;
    }
    #debug-view-danger.debug-selected {
      color: #fff4e8 !important;
      border-color: #ff9b45 !important;
      background: #573117 !important;
      box-shadow: inset 0 0 0 1px rgba(255,155,69,.22) !important;
    }
'''
style_close = text.rfind('</style>')
if style_close < 0:
    raise RuntimeError('style close missing for DANGER CSS')
text = text[:style_close] + css + text[style_close:]

one(
'''  const debugViewSolo = document.getElementById('debug-view-solo');
  const debugViewAll = document.getElementById('debug-view-all');
  const debugViewNone = document.getElementById('debug-view-none');
''',
'''  const debugViewSolo = document.getElementById('debug-view-solo');
  const debugViewAll = document.getElementById('debug-view-all');
  const debugViewNone = document.getElementById('debug-view-none');
  const debugViewDanger = document.getElementById('debug-view-danger');
''',
'VIEW consts')

state_anchor = "  let debugViewMode = 'solo';\n"
if text.count(state_anchor) != 1:
    raise RuntimeError('debugViewMode state anchor not found')
text = text.replace(state_anchor, state_anchor + '  let debugDangerActive = false;\n', 1)

# Direct SharedArrayBuffer command. 7/8/9 remain SOLO/ALL/NONE; DANGER does not
# steal a keyboard shortcut or send a synthetic KeyboardEvent that Chrome can
# lose/reorder. 100=off, 101=on, consumed one-shot by SceneMaskEditor.
bridge_anchor = '''  function debugWorkspaceAllowed() {
'''
bridge = '''  const DEBUG_DANGER_VIEW_BRIDGE_INDEX = 5830;

  function setDebugDangerEngineActive(active) {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab) return false;
      const shared = new Int32Array(sab);
      if (shared.length <= DEBUG_DANGER_VIEW_BRIDGE_INDEX) return false;
      Atomics.store(shared, DEBUG_DANGER_VIEW_BRIDGE_INDEX, active ? 101 : 100);
      if (typeof Atomics.notify === 'function') Atomics.notify(shared, DEBUG_DANGER_VIEW_BRIDGE_INDEX, 1);
      return true;
    } catch (error) {
      console.warn('DANGER direct bridge unavailable', error);
      return false;
    }
  }

  function debugWorkspaceAllowed() {
'''
if text.count(bridge_anchor) != 1:
    raise RuntimeError('DANGER bridge insertion anchor not found')
text = text.replace(bridge_anchor, bridge, 1)

# Normal layer selection always exits the composite first.
old = '''  function selectDebugLayer(layer, applyView = true) {
    selectedDebugLayer = Math.max(1, Math.min(5, Number(layer) || 1));
'''
new = '''  function selectDebugLayer(layer, applyView = true) {
    if (debugDangerActive) setDebugDangerEngineActive(false);
    debugDangerActive = false;
    debugViewDanger.classList.remove('debug-selected');
    selectedDebugLayer = Math.max(1, Math.min(5, Number(layer) || 1));
'''
one(old, new, 'selectDebugLayer DANGER reset')

# Context help explains source semantics. WATER is shown as a source plane; the
# recovered black/white scripted marks are what should reveal bridge positions
# that lie above the painted water itself.
old = '''  function updateDebugContextHelp() {
    const help = {
'''
new = '''  function updateDebugContextHelp() {
    if (debugDangerActive) {
      debugContextHelp.innerHTML = '<strong>DANGER</strong> read-only composite · <span class="legend-dot legend-water"></span>cyan = WATER control · black/white dotted marks = Sierra scripted death/fall · striped yellow = editable FALL.';
      return;
    }
    const help = {
'''
one(old, new, 'DANGER context help')

old = '''    const mode = debugMode === 'sprites' ? 'SPRITES'
      : debugMode === 'inspect' ? 'INSPECT'
      : (debugEraserActive ? ('ERASE ' + layerName(selectedDebugLayer)) : layerName(selectedDebugLayer));
'''
new = '''    const mode = debugDangerActive ? 'DANGER'
      : debugMode === 'sprites' ? 'SPRITES'
      : debugMode === 'inspect' ? 'INSPECT'
      : (debugEraserActive ? ('ERASE ' + layerName(selectedDebugLayer)) : layerName(selectedDebugLayer));
'''
one(old, new, 'DANGER workspace status')

# Any ordinary visibility preset exits DANGER before applying its absolute view.
old = '''  function applyDebugViewMode(mode) {
    debugViewMode = mode;
    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');
    debugViewAll.classList.toggle('debug-selected', mode === 'all');
    debugViewNone.classList.toggle('debug-selected', mode === 'none');
'''
new = '''  function applyDebugViewMode(mode) {
    if (debugDangerActive && mode !== 'danger') {
      setDebugDangerEngineActive(false);
      debugDangerActive = false;
    }
    debugViewMode = mode;
    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');
    debugViewAll.classList.toggle('debug-selected', mode === 'all');
    debugViewNone.classList.toggle('debug-selected', mode === 'none');
    debugViewDanger.classList.toggle('debug-selected', mode === 'danger');
'''
one(old, new, 'applyDebugViewMode DANGER state')

old = '''  debugViewSolo.addEventListener('click', () => applyDebugViewMode('solo'));
  debugViewAll.addEventListener('click', () => applyDebugViewMode('all'));
  debugViewNone.addEventListener('click', () => applyDebugViewMode('none'));
'''
new = '''  debugViewSolo.addEventListener('click', () => applyDebugViewMode('solo'));
  debugViewAll.addEventListener('click', () => applyDebugViewMode('all'));
  debugViewNone.addEventListener('click', () => applyDebugViewMode('none'));
  debugViewDanger.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
  debugViewDanger.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    const next = !debugDangerActive;
    if (!setDebugDangerEngineActive(next)) {
      debugContextHelp.textContent = 'DANGER view needs the latest game runtime. Hard refresh once and try again.';
      return;
    }
    debugDangerActive = next;
    if (!next) {
      applyDebugViewMode('solo');
      return;
    }
    debugViewMode = 'danger';
    debugViewSolo.classList.remove('debug-selected');
    debugViewAll.classList.remove('debug-selected');
    debugViewNone.classList.remove('debug-selected');
    debugViewDanger.classList.add('debug-selected');
    debugEraserActive = false;
    debugEraserButton.classList.remove('debug-selected');
    updateDebugContextHelp();
    updateDebugWorkspaceStatus();
  });
'''
one(old, new, 'DANGER view listeners')

# Manual visibility also leaves the composite. There can be more than one copy of
# this state-reset block after the historical UI patches, so update all of them.
old = '''      debugViewMode = 'manual';
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
'''
new = '''      if (debugDangerActive) setDebugDangerEngineActive(false);
      debugDangerActive = false;
      debugViewMode = 'manual';
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
      debugViewDanger.classList.remove('debug-selected');
'''
if text.count(old) < 1:
    raise RuntimeError('manual visibility DANGER reset not found')
text = text.replace(old, new)

# Leaving EDIT by PLAY/Tab/title transition must not leave Java stuck in the
# read-only composite for the next editing session.
old = '''  function setPaintUiActive(active) {
    paintUiActive = !!active;
'''
new = '''  function setPaintUiActive(active) {
    paintUiActive = !!active;
    if (!paintUiActive && debugDangerActive) {
      setDebugDangerEngineActive(false);
      debugDangerActive = false;
      if (debugViewDanger) debugViewDanger.classList.remove('debug-selected');
    }
'''
one(old, new, 'setPaintUiActive DANGER cleanup')

# Cache marker for detector-v2 + direct bridge runtime.
old_tag = "const BUILD_TAG = '20260830-edit-workspace-ux-v1';"
new_tag = "const BUILD_TAG = '20260831-danger-composite-v2';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('EDIT workspace build tag not found')

path.write_text(text)
print('DANGER view UI installed: direct bridge 5830; cyan WATER + recovered scripted hazards + striped editable FALL, read-only')
