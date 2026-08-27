#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_debug_menu.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# ---------------------------------------------------------------------------
# Turn the small brush box into a practical authoring palette. The Java editor
# remains the source of truth; these controls simply send its existing shortcuts
# so keyboard and mouse workflows always stay compatible.
# ---------------------------------------------------------------------------
style_anchor = '  </style>\n'
style = r'''    /* Debug authoring palette v2. */
    #brush-control {
      width: min(336px, calc(100vw - 32px));
      max-height: calc(100vh - 36px);
      overflow: auto;
      padding: 11px 12px 12px;
      scrollbar-width: thin;
    }
    #debug-tools { display: grid; gap: 9px; margin-top: 10px; }
    .debug-section {
      display: grid; gap: 6px; padding-top: 8px;
      border-top: 1px solid rgba(255,255,255,.18);
    }
    .debug-section-title {
      display: flex; justify-content: space-between; align-items: baseline;
      font-size: 10px; letter-spacing: .11em; opacity: .74;
    }
    .debug-section-title small { font-size: 9px; letter-spacing: 0; opacity: .72; font-weight: 500; }
    .debug-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 5px; }
    .debug-grid.debug-grid-five { grid-template-columns: repeat(5, minmax(0,1fr)); }
    #debug-tools button {
      width: 100%; box-sizing: border-box; min-height: 32px; padding: 7px 6px;
      border: 1px solid #777; border-radius: 7px; background: #222; color: #fff;
      font: 700 10px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .015em; cursor: pointer;
    }
    #debug-tools button:hover { background: #393939; }
    #debug-tools button:active { transform: translateY(1px); }
    #debug-tools .debug-layer.debug-selected {
      border-color: #ffd84d; background: rgba(95,76,8,.96);
      box-shadow: inset 0 0 0 1px rgba(255,216,77,.22);
    }
    #debug-tools .debug-layer[data-debug-layer="1"] { color: #ff766f; }
    #debug-tools .debug-layer[data-debug-layer="2"] { color: #75a6ff; }
    #debug-tools .debug-layer[data-debug-layer="3"] { color: #69f984; }
    #debug-tools .debug-layer[data-debug-layer="4"] { color: #68edf7; }
    #debug-tools .debug-layer[data-debug-layer="5"] { color: #ff5bb2; }
    #debug-tools .debug-visibility { position: relative; min-height: 28px; font-size: 9px; opacity: .92; }
    #debug-tools .debug-visibility::before {
      content: ''; display: inline-block; width: 7px; height: 7px; margin-right: 4px;
      border-radius: 50%; background: #63e983; box-shadow: 0 0 0 1px rgba(255,255,255,.28);
    }
    #debug-tools .debug-visibility.debug-hidden { opacity: .48; text-decoration: line-through; }
    #debug-tools .debug-visibility.debug-hidden::before { background: #777; }
    #move-sprite-button.debug-selected-action { background: rgba(95,76,8,.96); }
    #reset-sprite-button { border-color: #ff8b8b !important; background: #2a1717 !important; }
    #debug-clear-layer { border-color: #e1a661 !important; }
    #debug-fall-help {
      padding: 7px 8px; border-radius: 7px; background: rgba(255,45,137,.11);
      border: 1px solid rgba(255,91,178,.40); color: #ffd7e9;
      font-size: 10px; line-height: 1.3; font-weight: 600;
    }
    #debug-move-help, #debug-hotkeys { font-size: 9px; line-height: 1.35; opacity: .72; font-weight: 500; }
    #debug-hotkeys { padding-top: 2px; }
  </style>
'''
if text.count(style_anchor) != 1:
    raise RuntimeError('final style close anchor not found')
text = text.replace(style_anchor, style, 1)

old_tools = '''  <div id="debug-tools">\n    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <button id="reset-sprite-button" type="button" style="width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #ff8b8b;border-radius:7px;background:#2a1717;color:#fff;font:700 12px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;">RESET SPRITE</button>\n    <div id="debug-move-help">MOVE SPRITE is temporary for Graham. RESET SPRITE clears every saved Graham debug pin and returns him to normal AGI movement.</div>\n  </div>\n'''
new_tools = '''  <div id="debug-tools">\n    <div class="debug-section">\n      <div class="debug-section-title"><span>PAINT LAYER</span><small>click, then paint the room</small></div>\n      <div class="debug-grid debug-grid-five">\n        <button id="debug-layer-front" class="debug-layer debug-selected" data-debug-layer="1" type="button" title="Foreground / occluder">FRONT</button>\n        <button id="debug-layer-block" class="debug-layer" data-debug-layer="2" type="button" title="Collision / blocked ground">BLOCK</button>\n        <button id="debug-layer-behind" class="debug-layer" data-debug-layer="3" type="button" title="Behind-zone for foreground occlusion">BEHIND</button>\n        <button id="debug-layer-water" class="debug-layer" data-debug-layer="4" type="button" title="Water control zone">WATER</button>\n        <button id="debug-layer-fall" class="debug-layer" data-debug-layer="5" type="button" title="Fall / AGI special control zone">FALL</button>\n      </div>\n      <div id="debug-fall-help">FALL = AGI HITSPEC / control 2. Paint cliffs, drop-offs, holes, or any place the original room logic should treat as a special danger trigger.</div>\n    </div>\n\n    <div class="debug-section">\n      <div class="debug-section-title"><span>OVERLAY VISIBILITY</span><small>does not change the mask</small></div>\n      <div class="debug-grid debug-grid-five">\n        <button class="debug-visibility" data-debug-visibility="r" type="button">FRONT</button>\n        <button class="debug-visibility" data-debug-visibility="b" type="button">BLOCK</button>\n        <button class="debug-visibility" data-debug-visibility="g" type="button">BEHIND</button>\n        <button class="debug-visibility" data-debug-visibility="w" type="button">WATER</button>\n        <button class="debug-visibility" data-debug-visibility="v" type="button">FALL</button>\n      </div>\n    </div>\n\n    <div class="debug-section">\n      <div class="debug-section-title"><span>SPRITES</span><small>visual authoring only</small></div>\n      <div class="debug-grid">\n        <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n        <button id="reset-sprite-button" type="button">RESET GRAHAM</button>\n      </div>\n      <div id="debug-move-help">MOVE SPRITE: click a cyan box once, then drag anywhere. RESET GRAHAM removes saved visual pins and returns object 0 to normal AGI movement.</div>\n    </div>\n\n    <div class="debug-section">\n      <div class="debug-section-title"><span>MASK TOOLS</span><small>current room</small></div>\n      <div class="debug-grid">\n        <button id="debug-clear-layer" type="button">CLEAR LAYER</button>\n        <button id="debug-save-mask" type="button">SAVE MASK</button>\n        <button id="debug-copy-mask" type="button">COPY MASK JSON</button>\n        <button id="debug-copy-image" type="button">COPY DEBUG IMAGE</button>\n      </div>\n    </div>\n\n    <div id="debug-hotkeys">Tab: exit DEBUG · Shift+Left: rewind · Space+drag: pan · Z / Shift+Z: zoom · Option/right-click: erase</div>\n  </div>\n'''
if text.count(old_tools) != 1:
    raise RuntimeError('final MOVE/RESET debug tools block not found')
text = text.replace(old_tools, new_tools, 1)

# MOVE used to be editor key 5. FALL now owns 5; MOVE is 6. Both the normal
# MOVE button and RESET GRAHAM's compatibility fallback must follow that change.
old_move_key = "tapGameKey('5', 'Digit5', 53);"
move_count = text.count(old_move_key)
if move_count != 2:
    raise RuntimeError(f'expected two browser MOVE key-5 calls, found {move_count}')
text = text.replace(old_move_key, "tapGameKey('6', 'Digit6', 54);")

const_anchor = '''  const resetSpriteButton = document.getElementById('reset-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n'''
const_repl = '''  const resetSpriteButton = document.getElementById('reset-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n  const debugLayerButtons = Array.from(document.querySelectorAll('[data-debug-layer]'));\n  const debugVisibilityButtons = Array.from(document.querySelectorAll('[data-debug-visibility]'));\n  const debugClearLayerButton = document.getElementById('debug-clear-layer');\n  const debugSaveMaskButton = document.getElementById('debug-save-mask');\n  const debugCopyMaskButton = document.getElementById('debug-copy-mask');\n  const debugCopyImageButton = document.getElementById('debug-copy-image');\n'''
if text.count(const_anchor) != 1:
    raise RuntimeError('RESET/debug-copy const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

listener_anchor = '''  debugCopyButton.addEventListener('click', event => {\n'''
listeners = r'''  function ensureDebugEditorActive() {
    if (paintUiActive) return;
    sendF2();
    setPaintUiActive(true);
    applyBrushSize(brushSize);
  }

  function sendEditorShortcut(key) {
    ensureDebugEditorActive();
    const lower = String(key).toLowerCase();
    const digit = /^[1-6]$/.test(lower);
    const code = digit ? ('Digit' + lower) : ('Key' + lower.toUpperCase());
    const keyCode = digit ? (48 + Number(lower)) : lower.toUpperCase().charCodeAt(0);
    tapGameKey(lower, code, keyCode);
    focusGameCanvas();
  }

  function selectDebugLayer(layer) {
    debugLayerButtons.forEach(button => {
      button.classList.toggle('debug-selected', button.dataset.debugLayer === String(layer));
    });
    moveSpriteButton.classList.remove('debug-selected-action');
  }

  debugLayerButtons.forEach(button => {
    button.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const layer = Number(button.dataset.debugLayer);
      sendEditorShortcut(String(layer));
      selectDebugLayer(layer);
    });
  });

  debugVisibilityButtons.forEach(button => {
    button.setAttribute('aria-pressed', 'true');
    button.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      sendEditorShortcut(button.dataset.debugVisibility);
      const hidden = button.classList.toggle('debug-hidden');
      button.setAttribute('aria-pressed', hidden ? 'false' : 'true');
    });
  });

  debugClearLayerButton.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation();
    const current = debugLayerButtons.find(button => button.classList.contains('debug-selected'));
    const name = current ? current.textContent.trim() : 'CURRENT';
    if (!confirm('Clear the ' + name + ' mask for this room?')) return;
    sendEditorShortcut('c');
  });
  debugSaveMaskButton.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation(); sendEditorShortcut('s');
    const old = debugSaveMaskButton.textContent;
    debugSaveMaskButton.textContent = 'SAVED';
    setTimeout(() => { debugSaveMaskButton.textContent = old; }, 800);
  });
  debugCopyMaskButton.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation(); sendEditorShortcut('x');
    const old = debugCopyMaskButton.textContent;
    debugCopyMaskButton.textContent = 'JSON COPIED';
    setTimeout(() => { debugCopyMaskButton.textContent = old; }, 900);
  });
  debugCopyImageButton.addEventListener('click', event => {
    event.preventDefault(); event.stopPropagation(); openCopyDebugFromButton();
  });

  // The original MOVE listener still performs the actual key dispatch. This
  // listener only mirrors selection state in the palette.
  moveSpriteButton.addEventListener('click', () => {
    debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
    moveSpriteButton.classList.add('debug-selected-action');
  });

  // Keep the palette readable when power users use the real editor shortcuts.
  window.addEventListener('keydown', event => {
    if (!event.isTrusted || !paintUiActive || event.repeat) return;
    if (/^[1-5]$/.test(event.key)) selectDebugLayer(Number(event.key));
    else if (event.key === '6') {
      debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
      moveSpriteButton.classList.add('debug-selected-action');
    }
  }, true);

  debugCopyButton.addEventListener('click', event => {
'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('debug-copy listener anchor not found')
text = text.replace(listener_anchor, listeners, 1)

path.write_text(text)
print('Debug palette improved: clickable FRONT/BLOCK/BEHIND/WATER/FALL layers, visibility toggles, mask tools, MOVE key 6')

# Final UX pass: transform the floating palette into the docked editor workspace.
__import__('runpy').run_path(str(Path(__file__).with_name('redesign_debug_workspace.py')), run_name='__main__')
