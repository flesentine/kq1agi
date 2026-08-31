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

# DANGER is deliberately a VIEW, not another editable mask. It combines only
# hazard sources the runtime has evidence for: deadly WATER, scripted fall/death
# positions, and editable FALL/HITSPEC.
old = '''        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>
        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>
        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>
'''
new = '''        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>
        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>
        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>
        <button id="debug-view-danger" class="debug-small-button debug-danger-button" type="button" title="Show all detected fall/death hazards; read-only">DANGER</button>
'''
one(old, new, 'VIEW button row')

# The existing row has one label + three compact buttons. Give DANGER a fourth.
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

# Numeric 7 is the Java editor's read-only DANGER composite shortcut.
old = "    const digit = /^[1-6]$/.test(lower);\n"
new = "    const digit = /^[1-7]$/.test(lower);\n"
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise RuntimeError('sendEditorShortcut digit range not found')

state_anchor = "  let debugViewMode = 'solo';\n"
if state_anchor not in text:
    raise RuntimeError('debugViewMode state anchor not found')
text = text.replace(state_anchor, state_anchor + '  let debugDangerActive = false;\n', 1)

# When a normal paint layer is selected, Java exits DANGER automatically; mirror
# that state in the dock and let the selected layer's normal SOLO preset win.
old = '''  function selectDebugLayer(layer, applyView = true) {
    selectedDebugLayer = Math.max(1, Math.min(5, Number(layer) || 1));
'''
new = '''  function selectDebugLayer(layer, applyView = true) {
    debugDangerActive = false;
    debugViewDanger.classList.remove('debug-selected');
    selectedDebugLayer = Math.max(1, Math.min(5, Number(layer) || 1));
'''
one(old, new, 'selectDebugLayer danger reset')

# Context help should explain what the three colors mean instead of pretending a
# DANGER composite is an editable layer.
old = '''  function updateDebugContextHelp() {
    const help = {
'''
new = '''  function updateDebugContextHelp() {
    if (debugDangerActive) {
      debugContextHelp.innerHTML = '<strong>DANGER</strong> read-only composite · <span class="legend-dot legend-water"></span>cyan = deadly WATER · <span class="legend-dot legend-script"></span>orange = Sierra scripted death/fall · <span class="legend-dot legend-fall"></span>pink = editable FALL.';
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

# Any regular VIEW preset exits the Java DANGER composite first.
old = '''  function applyDebugViewMode(mode) {
    debugViewMode = mode;
    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');
    debugViewAll.classList.toggle('debug-selected', mode === 'all');
    debugViewNone.classList.toggle('debug-selected', mode === 'none');
'''
new = '''  function applyDebugViewMode(mode) {
    if (debugDangerActive && mode !== 'danger') {
      sendEditorShortcut('7');
      debugDangerActive = false;
    }
    debugViewMode = mode;
    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');
    debugViewAll.classList.toggle('debug-selected', mode === 'all');
    debugViewNone.classList.toggle('debug-selected', mode === 'none');
    debugViewDanger.classList.toggle('debug-selected', mode === 'danger');
'''
one(old, new, 'applyDebugViewMode danger state')

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
    if (debugDangerActive) {
      sendEditorShortcut('7');
      debugDangerActive = false;
      applyDebugViewMode('solo');
    } else {
      sendEditorShortcut('7');
      debugDangerActive = true;
      debugViewMode = 'danger';
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
      debugViewDanger.classList.add('debug-selected');
      debugEraserActive = false;
      debugEraserButton.classList.remove('debug-selected');
      updateDebugContextHelp();
      updateDebugWorkspaceStatus();
    }
  });
'''
one(old, new, 'DANGER view listeners')

# Manual visibility means the user is leaving the composite view. The actual
# visibility shortcut also changes the engine view, so just mirror browser state.
old = '''      debugViewMode = 'manual';
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
'''
new = '''      debugViewMode = 'manual';
      debugDangerActive = false;
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
      debugViewDanger.classList.remove('debug-selected');
'''
# There is one final manual-visibility handler in the redesigned workspace.
if text.count(old) < 1:
    raise RuntimeError('manual visibility view reset not found')
text = text.replace(old, new)

# Physical 7 is useful for keyboard-driven authoring too. Java receives the real
# key normally; this listener only keeps the browser chrome synchronized.
body_close = text.rfind('</script>')
if body_close < 0:
    raise RuntimeError('script close missing for DANGER keyboard sync')
keyboard = r'''
  window.addEventListener('keydown', event => {
    if (!event.isTrusted || !paintUiActive || event.repeat || event.key !== '7') return;
    debugDangerActive = !debugDangerActive;
    debugViewMode = debugDangerActive ? 'danger' : 'solo';
    debugViewSolo.classList.toggle('debug-selected', !debugDangerActive);
    debugViewAll.classList.remove('debug-selected');
    debugViewNone.classList.remove('debug-selected');
    debugViewDanger.classList.toggle('debug-selected', debugDangerActive);
    updateDebugContextHelp();
    updateDebugWorkspaceStatus();
  }, true);
'''
text = text[:body_close] + keyboard + text[body_close:]

# Cache marker for the new runtime semantics and editor control.
old_tag = "const BUILD_TAG = '20260830-edit-workspace-ux-v1';"
new_tag = "const BUILD_TAG = '20260831-danger-composite-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('EDIT workspace build tag not found')

path.write_text(text)
print('DANGER view UI installed: read-only composite of deadly WATER, scripted hazards, and editable FALL')
