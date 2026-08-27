#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: redesign_debug_workspace.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

# ---------------------------------------------------------------------------
# 1) Replace the floating palette with a docked level-editor workspace.
# ---------------------------------------------------------------------------
panel_start = text.find('<div id="brush-control"')
panel_end = text.find('<div id="boot-message"', panel_start)
if panel_start < 0 or panel_end < 0:
    raise RuntimeError('debug brush-control panel bounds not found')

panel = r'''<div id="brush-control" aria-label="Debug room editor">
  <div class="debug-workspace-header">
    <div>
      <div class="debug-workspace-title">DEBUG</div>
      <div id="debug-status" class="debug-workspace-status">ROOM 1 · FRONT · 2 PX · AUTO-SAVED</div>
    </div>
    <button id="debug-test-button" type="button" title="Close the editor and test the room">TEST ▶</button>
  </div>

  <div class="debug-mode-tabs" role="tablist" aria-label="Debug mode">
    <button id="debug-mode-paint" class="debug-mode-button debug-selected" type="button">PAINT</button>
    <button id="debug-mode-sprites" class="debug-mode-button" type="button">SPRITES</button>
    <button id="debug-mode-inspect" class="debug-mode-button" type="button">INSPECT</button>
  </div>

  <div id="debug-tools">
    <section id="debug-paint-section" class="debug-section">
      <div class="debug-section-title"><span>PAINT</span><small>SOLO view by default</small></div>

      <div class="brush-row"><span>BRUSH</span><span id="brush-value" class="brush-value">2 PX</span></div>
      <input id="brush-size" type="range" min="1" max="12" step="1" value="2" aria-label="Brush size from 1 to 12 pixels">

      <div class="debug-grid debug-layer-grid">
        <button id="debug-layer-front" class="debug-layer debug-selected" data-debug-layer="1" type="button">FRONT</button>
        <button id="debug-layer-block" class="debug-layer" data-debug-layer="2" type="button">BLOCK</button>
        <button id="debug-layer-behind" class="debug-layer" data-debug-layer="3" type="button">BEHIND</button>
        <button id="debug-layer-water" class="debug-layer" data-debug-layer="4" type="button">WATER</button>
        <button id="debug-layer-fall" class="debug-layer" data-debug-layer="5" type="button">FALL</button>
        <button id="debug-eraser-button" class="debug-tool-button" type="button">ERASE</button>
      </div>

      <div class="debug-control-row">
        <span>VIEW</span>
        <button id="debug-view-solo" class="debug-small-button debug-selected" type="button">SOLO</button>
        <button id="debug-view-all" class="debug-small-button" type="button">ALL</button>
        <button id="debug-view-none" class="debug-small-button" type="button">NONE</button>
      </div>

      <div class="debug-slider-row">
        <label for="debug-opacity">OVERLAY</label>
        <input id="debug-opacity" type="range" min="25" max="100" step="5" value="70">
        <span id="debug-opacity-value">70%</span>
      </div>

      <div class="debug-control-row debug-view-tools">
        <button id="debug-fill-button" class="debug-small-button debug-selected" type="button">FILL</button>
        <button id="debug-outline-button" class="debug-small-button" type="button">OUTLINE</button>
        <button id="debug-fit-button" class="debug-small-button" type="button">FIT</button>
      </div>

      <div class="debug-grid debug-undo-grid">
        <button id="debug-undo-button" type="button">↶ UNDO</button>
        <button id="debug-redo-button" type="button">REDO ↷</button>
      </div>

      <div id="debug-context-help" class="debug-context-help">
        <span class="legend-dot legend-front"></span><strong>FRONT</strong> redraws room pixels over Graham.
      </div>
    </section>

    <details id="debug-advanced">
      <summary>ADVANCED</summary>

      <div class="debug-section">
        <div class="debug-section-title"><span>MANUAL VISIBILITY</span><small>normally use SOLO / ALL</small></div>
        <div class="debug-grid debug-grid-five">
          <button class="debug-visibility" data-debug-visibility="r" data-layer-index="1" type="button">FRONT</button>
          <button class="debug-visibility" data-debug-visibility="b" data-layer-index="2" type="button">BLOCK</button>
          <button class="debug-visibility" data-debug-visibility="g" data-layer-index="3" type="button">BEHIND</button>
          <button class="debug-visibility" data-debug-visibility="w" data-layer-index="4" type="button">WATER</button>
          <button class="debug-visibility" data-debug-visibility="v" data-layer-index="5" type="button">FALL</button>
        </div>
      </div>

      <div class="debug-section">
        <div class="debug-section-title"><span>SPRITE TOOLS</span><small>visual placement</small></div>
        <div class="debug-grid">
          <button id="move-sprite-button" type="button">MOVE SPRITE</button>
          <button id="reset-sprite-button" type="button">RESET GRAHAM</button>
        </div>
        <div id="debug-move-help">Select SPRITES above, click a cyan box, then drag. RESET GRAHAM removes saved visual pins.</div>
      </div>

      <div class="debug-section">
        <div class="debug-section-title"><span>ROOM TOOLS</span><small>auto-save is already on</small></div>
        <div class="debug-grid">
          <button id="debug-clear-layer" type="button">CLEAR LAYER</button>
          <button id="debug-save-mask" type="button">SAVE NOW</button>
          <button id="debug-copy-mask" type="button">COPY MASK JSON</button>
          <button id="debug-copy-image" type="button">COPY DEBUG IMAGE</button>
          <button id="debug-export-bg" type="button">EXPORT BG</button>
        </div>
      </div>
    </details>

    <div id="debug-hotkeys">H hold: hide overlays · A hold: show all · Space+drag: pan · Cmd/Ctrl+Z: undo · Option/right-click: erase</div>
  </div>
</div>
'''
text = text[:panel_start] + panel + text[panel_end:]

# ---------------------------------------------------------------------------
# 2) Docked workspace styling. The game gets its own unobstructed viewport.
# ---------------------------------------------------------------------------
style_anchor = '  </style>\n'
css = r'''    /* Debug workspace v3: docked, uncluttered level-editor layout. */
    :root { --debug-sidebar-width: 296px; }

    body.debug-workspace {
      background: #050505;
    }
    body.debug-workspace #brush-control {
      display: flex !important;
    }
    body.debug-workspace #paint-button,
    body.debug-workspace #export-bg-button,
    body.debug-workspace #debug-snap-button {
      display: none !important;
    }
    body.debug-workspace #embed-html {
      position: fixed;
      left: var(--debug-sidebar-width);
      right: 0;
      top: 0;
      bottom: 0;
      width: auto;
      height: 100vh;
      display: grid;
      place-items: center;
      overflow: hidden;
      background: #000;
    }
    body.debug-workspace #embed-html canvas {
      max-width: 100% !important;
      max-height: 100vh !important;
      width: auto !important;
      height: auto !important;
      object-fit: contain;
    }

    #brush-control {
      left: 0;
      top: 0;
      bottom: 0;
      width: var(--debug-sidebar-width) !important;
      max-height: none !important;
      height: 100vh;
      border: 0;
      border-right: 1px solid rgba(255,255,255,.22);
      border-radius: 0;
      padding: 14px 13px 12px !important;
      background: rgba(13,13,14,.985);
      box-shadow: 10px 0 28px rgba(0,0,0,.35);
      overflow-y: auto;
      overflow-x: hidden;
      box-sizing: border-box;
      scrollbar-width: thin;
      font-family: system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
    }
    .debug-workspace-header {
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 10px;
      padding-bottom: 11px;
      border-bottom: 1px solid rgba(255,255,255,.18);
    }
    .debug-workspace-title {
      font-size: 17px;
      font-weight: 850;
      letter-spacing: .08em;
    }
    .debug-workspace-status {
      margin-top: 3px;
      max-width: 185px;
      color: #aaa;
      font-size: 9px;
      line-height: 1.25;
      letter-spacing: .02em;
      font-weight: 650;
    }
    #debug-test-button {
      min-width: 76px;
      min-height: 38px;
      border: 1px solid #7de393;
      border-radius: 8px;
      background: #17351e;
      color: #d9ffe2;
      font: 800 11px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .04em;
      cursor: pointer;
    }
    #debug-test-button:hover { background: #214b2a; }

    .debug-mode-tabs {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 5px;
      margin: 10px 0 6px;
      padding: 3px;
      border-radius: 9px;
      background: #090909;
      border: 1px solid rgba(255,255,255,.15);
    }
    .debug-mode-button {
      min-height: 31px;
      border: 0;
      border-radius: 6px;
      background: transparent;
      color: #9a9a9a;
      font: 800 9px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .06em;
      cursor: pointer;
    }
    .debug-mode-button.debug-selected {
      color: #fff;
      background: #303030;
      box-shadow: inset 0 0 0 1px rgba(255,255,255,.18);
    }

    #debug-tools { display: grid; gap: 9px; margin-top: 0; }
    .debug-section {
      display: grid;
      gap: 7px;
      padding-top: 10px;
      border-top: 1px solid rgba(255,255,255,.13);
    }
    #debug-paint-section { border-top: 0; padding-top: 4px; }
    .debug-section-title {
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      font-size: 9px;
      letter-spacing: .11em;
      color: #bbb;
    }
    .debug-section-title small {
      font-size: 8px;
      letter-spacing: 0;
      opacity: .62;
      font-weight: 500;
    }
    #brush-control .brush-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      color: #aaa;
      font-size: 9px;
      letter-spacing: .08em;
    }
    #brush-control .brush-value { color: #fff; font-variant-numeric: tabular-nums; }
    #brush-size, #debug-opacity { width: 100%; accent-color: #e8e8e8; cursor: pointer; }

    .debug-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 5px; }
    .debug-grid-five { grid-template-columns: repeat(5, minmax(0,1fr)); }
    .debug-layer-grid { grid-template-columns: repeat(3, minmax(0,1fr)); }
    #debug-tools button {
      box-sizing: border-box;
      min-height: 32px;
      padding: 7px 5px;
      border: 1px solid #555;
      border-radius: 7px;
      background: #202020;
      color: #fff;
      font: 800 9px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;
      letter-spacing: .015em;
      cursor: pointer;
    }
    #debug-tools button:hover { background: #323232; }
    #debug-tools button:active { transform: translateY(1px); }
    #debug-tools button.debug-selected {
      border-color: #ffd84d;
      background: #4e420d;
      box-shadow: inset 0 0 0 1px rgba(255,216,77,.18);
    }
    .debug-layer[data-debug-layer="1"] { color: #ff837d !important; }
    .debug-layer[data-debug-layer="2"] { color: #82adff !important; }
    .debug-layer[data-debug-layer="3"] { color: #79f28c !important; }
    .debug-layer[data-debug-layer="4"] { color: #77eff7 !important; }
    .debug-layer[data-debug-layer="5"] { color: #ff70bc !important; }
    #debug-eraser-button.debug-selected { color: #fff; border-color: #ffad77; background: #51301d; }

    .debug-control-row {
      display: grid;
      grid-template-columns: 1fr repeat(3, auto);
      gap: 5px;
      align-items: center;
      color: #999;
      font-size: 9px;
      letter-spacing: .08em;
    }
    .debug-control-row.debug-view-tools { grid-template-columns: repeat(3, 1fr); }
    .debug-small-button { min-height: 27px !important; padding: 5px 8px !important; }
    .debug-slider-row {
      display: grid;
      grid-template-columns: 54px 1fr 35px;
      gap: 7px;
      align-items: center;
      color: #999;
      font-size: 9px;
      letter-spacing: .06em;
    }
    #debug-opacity-value { color: #ddd; text-align: right; font-variant-numeric: tabular-nums; }

    .debug-context-help {
      min-height: 34px;
      padding: 7px 8px;
      border: 1px solid rgba(255,255,255,.14);
      border-radius: 7px;
      background: rgba(255,255,255,.035);
      color: #c9c9c9;
      font-size: 9px;
      line-height: 1.35;
      font-weight: 550;
    }
    .legend-dot {
      display: inline-block;
      width: 8px;
      height: 8px;
      margin-right: 5px;
      border-radius: 2px;
      vertical-align: 0;
    }
    .legend-front { background: #ff655f; }
    .legend-block { background: #5488ff; }
    .legend-behind { background: #53e56a; }
    .legend-water { background: #4de7f1; }
    .legend-fall { background: #ff3b9c; }
    .legend-script { border: 2px solid #ff812e; background: transparent; box-sizing: border-box; }

    #debug-advanced {
      margin-top: 2px;
      border-top: 1px solid rgba(255,255,255,.13);
      padding-top: 7px;
    }
    #debug-advanced summary {
      cursor: pointer;
      color: #aaa;
      font-size: 9px;
      font-weight: 800;
      letter-spacing: .1em;
      list-style-position: inside;
      padding: 5px 0;
    }
    #debug-advanced .debug-section:first-of-type { margin-top: 5px; }
    .debug-visibility { opacity: .92; font-size: 8px !important; }
    .debug-visibility::before {
      content: '';
      display: inline-block;
      width: 6px;
      height: 6px;
      margin-right: 3px;
      border-radius: 50%;
      background: #68e885;
    }
    .debug-visibility.debug-hidden { opacity: .42; text-decoration: line-through; }
    .debug-visibility.debug-hidden::before { background: #666; }
    #reset-sprite-button { border-color: #a76464 !important; }
    #debug-clear-layer { border-color: #b8854c !important; }
    #debug-move-help, #debug-hotkeys {
      color: #888;
      font-size: 8px;
      line-height: 1.35;
      font-weight: 500;
    }
    #debug-hotkeys {
      padding-top: 7px;
      border-top: 1px solid rgba(255,255,255,.11);
    }

    @media (max-width: 760px) {
      :root { --debug-sidebar-width: 250px; }
      .debug-workspace-status { max-width: 145px; }
      #brush-control { padding-left: 10px !important; padding-right: 10px !important; }
    }
  </style>
'''
if text.count(style_anchor) != 1:
    raise RuntimeError('style close anchor not found')
text = text.replace(style_anchor, css, 1)

# ---------------------------------------------------------------------------
# 3) Browser workspace state + controls.
# ---------------------------------------------------------------------------
const_anchor = '''  const debugCopyImageButton = document.getElementById('debug-copy-image');
  let debugSnapshot = null;
'''
const_repl = r'''  const debugCopyImageButton = document.getElementById('debug-copy-image');
  const debugTestButton = document.getElementById('debug-test-button');
  const debugStatus = document.getElementById('debug-status');
  const debugModePaint = document.getElementById('debug-mode-paint');
  const debugModeSprites = document.getElementById('debug-mode-sprites');
  const debugModeInspect = document.getElementById('debug-mode-inspect');
  const debugEraserButton = document.getElementById('debug-eraser-button');
  const debugViewSolo = document.getElementById('debug-view-solo');
  const debugViewAll = document.getElementById('debug-view-all');
  const debugViewNone = document.getElementById('debug-view-none');
  const debugOpacity = document.getElementById('debug-opacity');
  const debugOpacityValue = document.getElementById('debug-opacity-value');
  const debugFillButton = document.getElementById('debug-fill-button');
  const debugOutlineButton = document.getElementById('debug-outline-button');
  const debugFitButton = document.getElementById('debug-fit-button');
  const debugUndoButton = document.getElementById('debug-undo-button');
  const debugRedoButton = document.getElementById('debug-redo-button');
  const debugContextHelp = document.getElementById('debug-context-help');
  const debugExportButton = document.getElementById('debug-export-bg');

  const DEBUG_WORKSPACE_KEY = 'kq1agi-debug-workspace-v3';
  const visibilityKeys = { 1: 'r', 2: 'b', 3: 'g', 4: 'w', 5: 'v' };
  let selectedDebugLayer = 1;
  let overlayVisibility = { 1: true, 2: true, 3: true, 4: true, 5: true };
  let debugViewMode = 'solo';
  let debugMode = 'paint';
  let debugInspectActive = false;
  let debugEraserActive = false;
  let debugOutline = false;
  let runtimeOutline = false;
  let overlayOpacity = 70;
  let runtimeOpacity = 70;
  let peekVisibilityState = null;
  let debugSnapshot = null;
'''
if text.count(const_anchor) != 1:
    raise RuntimeError('debug workspace const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

set_active_old = r'''  function setPaintUiActive(active) {
    paintUiActive = !!active;
    brushControl.style.display = paintUiActive ? 'block' : 'none';
    paintButton.textContent = 'DEBUG';
    paintButton.classList.toggle('debug-active', paintUiActive);
    paintButton.title = paintUiActive ? 'Debug edit mode is active — click to exit (Tab shortcut)' : 'Open debug edit mode (Tab shortcut)';
  }
'''
set_active_new = r'''  function setPaintUiActive(active) {
    paintUiActive = !!active;
    document.body.classList.toggle('debug-workspace', paintUiActive);
    brushControl.style.display = paintUiActive ? 'flex' : 'none';
    paintButton.textContent = 'DEBUG';
    paintButton.classList.toggle('debug-active', paintUiActive);
    paintButton.title = paintUiActive ? 'Debug editor active' : 'Open debug editor (Tab shortcut)';
    if (paintUiActive) {
      loadDebugWorkspacePrefs();
      setTimeout(() => {
        applyBrushSize(brushSize);
        applyOverlayOpacity(overlayOpacity);
        setOutlineView(debugOutline);
        if (debugMode === 'sprites') setDebugMode('sprites');
        else if (debugMode === 'inspect') setDebugMode('inspect');
        else {
          setDebugMode('paint');
          applyDebugViewMode(debugViewMode);
        }
        updateDebugWorkspaceStatus();
      }, 70);
    } else {
      debugInspectActive = false;
      debugMode = 'paint';
      debugModeButtons();
      saveDebugWorkspacePrefs();
    }
    setTimeout(() => window.dispatchEvent(new Event('resize')), 0);
  }
'''
if text.count(set_active_old) != 1:
    raise RuntimeError('setPaintUiActive anchor not found')
text = text.replace(set_active_old, set_active_new, 1)

function_anchor = '''  function applyBrushSize(value) {
'''
workspace_functions = r'''  function currentDebugRoom() {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab) return 1;
      return (new Int32Array(sab)[0] || 0) & 255;
    } catch (error) {
      return 1;
    }
  }

  function layerName(layer) {
    return ({ 1: 'FRONT', 2: 'BLOCK', 3: 'BEHIND', 4: 'WATER', 5: 'FALL' })[layer] || 'FRONT';
  }

  function updateDebugContextHelp() {
    const help = {
      1: '<span class="legend-dot legend-front"></span><strong>FRONT</strong> redraws room pixels over Graham.',
      2: '<span class="legend-dot legend-block"></span><strong>BLOCK</strong> is the active walk/collision map.',
      3: '<span class="legend-dot legend-behind"></span><strong>BEHIND</strong> marks where Graham passes behind foreground art.',
      4: '<span class="legend-dot legend-water"></span><strong>WATER</strong> is the editable AGI water control.',
      5: '<span class="legend-dot legend-fall"></span><strong>FALL</strong> editable danger · <span class="legend-dot legend-script"></span>orange = original scripted danger.'
    };
    debugContextHelp.innerHTML = help[selectedDebugLayer] || help[1];
  }

  function updateDebugWorkspaceStatus() {
    if (!debugStatus) return;
    const mode = debugMode === 'sprites' ? 'SPRITES'
      : debugMode === 'inspect' ? 'INSPECT'
      : (debugEraserActive ? ('ERASE ' + layerName(selectedDebugLayer)) : layerName(selectedDebugLayer));
    debugStatus.textContent = 'ROOM ' + currentDebugRoom() + ' · ' + mode + ' · ' + brushSize + ' PX · AUTO-SAVED';
    updateDebugContextHelp();
  }

  function saveDebugWorkspacePrefs() {
    try {
      localStorage.setItem(DEBUG_WORKSPACE_KEY, JSON.stringify({
        layer: selectedDebugLayer,
        view: debugViewMode,
        opacity: overlayOpacity,
        outline: debugOutline
      }));
    } catch (error) {}
  }

  function loadDebugWorkspacePrefs() {
    try {
      const saved = JSON.parse(localStorage.getItem(DEBUG_WORKSPACE_KEY) || '{}');
      selectedDebugLayer = Math.max(1, Math.min(5, Number(saved.layer) || selectedDebugLayer));
      debugViewMode = ['solo', 'all', 'none'].includes(saved.view) ? saved.view : debugViewMode;
      overlayOpacity = Math.max(25, Math.min(100, Number(saved.opacity) || overlayOpacity));
      debugOutline = !!saved.outline;
      debugOpacity.value = String(overlayOpacity);
      debugOpacityValue.textContent = overlayOpacity + '%';
      selectDebugLayer(selectedDebugLayer, false);
    } catch (error) {}
  }

  function debugModeButtons() {
    debugModePaint.classList.toggle('debug-selected', debugMode === 'paint');
    debugModeSprites.classList.toggle('debug-selected', debugMode === 'sprites');
    debugModeInspect.classList.toggle('debug-selected', debugMode === 'inspect');
    debugEraserButton.classList.toggle('debug-selected', debugEraserActive && debugMode === 'paint');
  }

  function syncVisibilityButtons() {
    debugVisibilityButtons.forEach(button => {
      const layer = Number(button.dataset.layerIndex);
      const visible = !!overlayVisibility[layer];
      button.classList.toggle('debug-hidden', !visible);
      button.setAttribute('aria-pressed', visible ? 'true' : 'false');
    });
  }

  function setOverlayVisible(layer, visible) {
    visible = !!visible;
    if (overlayVisibility[layer] === visible) return;
    const key = visibilityKeys[layer];
    if (!key) return;
    sendEditorShortcut(key);
    overlayVisibility[layer] = visible;
    syncVisibilityButtons();
  }

  function setAllOverlayVisibility(visible) {
    for (let layer = 1; layer <= 5; layer++) setOverlayVisible(layer, visible);
  }

  function applyDebugViewMode(mode) {
    debugViewMode = mode;
    debugViewSolo.classList.toggle('debug-selected', mode === 'solo');
    debugViewAll.classList.toggle('debug-selected', mode === 'all');
    debugViewNone.classList.toggle('debug-selected', mode === 'none');

    if (!paintUiActive || debugMode === 'sprites') return;
    if (mode === 'all') {
      setAllOverlayVisibility(true);
    } else if (mode === 'none') {
      setAllOverlayVisibility(false);
    } else {
      for (let layer = 1; layer <= 5; layer++) setOverlayVisible(layer, layer === selectedDebugLayer);
    }
    saveDebugWorkspacePrefs();
  }

  function setOutlineView(outline) {
    debugOutline = !!outline;
    if (paintUiActive && runtimeOutline !== debugOutline) {
      sendEditorShortcut('o');
      runtimeOutline = debugOutline;
    }
    debugFillButton.classList.toggle('debug-selected', !debugOutline);
    debugOutlineButton.classList.toggle('debug-selected', debugOutline);
    saveDebugWorkspacePrefs();
  }

  function applyOverlayOpacity(value) {
    overlayOpacity = Math.max(25, Math.min(100, Math.round((Number(value) || 70) / 5) * 5));
    debugOpacity.value = String(overlayOpacity);
    debugOpacityValue.textContent = overlayOpacity + '%';
    if (paintUiActive) {
      // Make the Java value absolute: clamp to 25%, then step upward.
      for (let i = 0; i < 20; i++) tapGameKey(',', 'Comma', 188);
      for (let value = 25; value < overlayOpacity; value += 5) tapGameKey('.', 'Period', 190);
      runtimeOpacity = overlayOpacity;
    }
    saveDebugWorkspacePrefs();
  }

  function leaveInspectIfNeeded() {
    if (!debugInspectActive) return;
    sendEditorShortcut('i');
    debugInspectActive = false;
  }

  function setDebugMode(mode) {
    ensureDebugEditorActive();
    if (mode === 'sprites') {
      leaveInspectIfNeeded();
      debugMode = 'sprites';
      debugEraserActive = false;
      tapGameKey('6', 'Digit6', 54);
    } else if (mode === 'inspect') {
      if (!debugInspectActive) {
        sendEditorShortcut('i');
        debugInspectActive = true;
      }
      debugMode = 'inspect';
      debugEraserActive = false;
      applyDebugViewMode(debugViewMode === 'none' ? 'solo' : debugViewMode);
    } else {
      leaveInspectIfNeeded();
      debugMode = 'paint';
      debugEraserActive = false;
      sendEditorShortcut(String(selectedDebugLayer));
      applyDebugViewMode(debugViewMode);
    }
    debugModeButtons();
    updateDebugWorkspaceStatus();
  }

  function selectDebugLayer(layer, applyView = true) {
    selectedDebugLayer = Math.max(1, Math.min(5, Number(layer) || 1));
    debugLayerButtons.forEach(button => {
      button.classList.toggle('debug-selected', button.dataset.debugLayer === String(selectedDebugLayer));
    });
    moveSpriteButton.classList.remove('debug-selected-action');
    debugEraserActive = false;
    if (applyView && paintUiActive) {
      debugMode = 'paint';
      debugInspectActive = false;
      sendEditorShortcut(String(selectedDebugLayer));
      if (debugViewMode === 'solo') applyDebugViewMode('solo');
      debugModeButtons();
    }
    updateDebugWorkspaceStatus();
    saveDebugWorkspacePrefs();
  }

  debugTestButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    sendF2();
    setPaintUiActive(false);
    focusGameCanvas();
  });
  debugModePaint.addEventListener('click', () => setDebugMode('paint'));
  debugModeSprites.addEventListener('click', () => setDebugMode('sprites'));
  debugModeInspect.addEventListener('click', () => setDebugMode('inspect'));

  debugEraserButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    ensureDebugEditorActive();
    if (debugMode !== 'paint') setDebugMode('paint');
    sendEditorShortcut('e');
    debugEraserActive = !debugEraserActive;
    debugModeButtons();
    updateDebugWorkspaceStatus();
  });

  debugViewSolo.addEventListener('click', () => applyDebugViewMode('solo'));
  debugViewAll.addEventListener('click', () => applyDebugViewMode('all'));
  debugViewNone.addEventListener('click', () => applyDebugViewMode('none'));

  debugOpacity.addEventListener('input', event => {
    overlayOpacity = Number(event.target.value);
    debugOpacityValue.textContent = overlayOpacity + '%';
  });
  debugOpacity.addEventListener('change', event => applyOverlayOpacity(event.target.value));

  debugFillButton.addEventListener('click', () => setOutlineView(false));
  debugOutlineButton.addEventListener('click', () => setOutlineView(true));
  debugFitButton.addEventListener('click', () => {
    ensureDebugEditorActive();
    tapGameKey('0', 'Digit0', 48);
    focusGameCanvas();
  });
  debugUndoButton.addEventListener('click', () => sendEditorShortcut('u'));
  debugRedoButton.addEventListener('click', () => sendEditorShortcut('y'));
  debugExportButton.addEventListener('click', () => exportCleanBackground());

  // Fast before/after peeking while authoring.
  window.addEventListener('keydown', event => {
    if (!paintUiActive || !event.isTrusted || event.repeat || event.metaKey || event.ctrlKey || event.altKey) return;
    const key = event.key.toLowerCase();
    if (key !== 'h' && key !== 'a') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    if (!peekVisibilityState) peekVisibilityState = { ...overlayVisibility };
    setAllOverlayVisibility(key === 'a');
  }, true);
  window.addEventListener('keyup', event => {
    if (!paintUiActive || !peekVisibilityState) return;
    const key = event.key.toLowerCase();
    if (key !== 'h' && key !== 'a') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    const restore = peekVisibilityState;
    peekVisibilityState = null;
    for (let layer = 1; layer <= 5; layer++) setOverlayVisible(layer, restore[layer]);
  }, true);

  // Native-feeling undo/redo on desktop.
  window.addEventListener('keydown', event => {
    if (!paintUiActive || !event.isTrusted || !(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== 'z') return;
    event.preventDefault();
    event.stopImmediatePropagation();
    sendEditorShortcut(event.shiftKey ? 'y' : 'u');
  }, true);

  setInterval(() => {
    if (paintUiActive) updateDebugWorkspaceStatus();
  }, 400);

  function applyBrushSize(value) {
'''
if text.count(function_anchor) != 1:
    raise RuntimeError('applyBrushSize function anchor not found')
text = text.replace(function_anchor, workspace_functions, 1)

# ---------------------------------------------------------------------------
# 4) Replace old layer/visibility handlers with SOLO-aware behavior.
# ---------------------------------------------------------------------------
old_select = r'''  function selectDebugLayer(layer) {
    debugLayerButtons.forEach(button => {
      button.classList.toggle('debug-selected', button.dataset.debugLayer === String(layer));
    });
    moveSpriteButton.classList.remove('debug-selected-action');
  }
'''
if old_select in text:
    # The new selectDebugLayer above owns this behavior.
    text = text.replace(old_select, '', 1)

old_layers = r'''  debugLayerButtons.forEach(button => {
    button.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const layer = Number(button.dataset.debugLayer);
      sendEditorShortcut(String(layer));
      selectDebugLayer(layer);
    });
  });
'''
new_layers = r'''  debugLayerButtons.forEach(button => {
    button.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      selectDebugLayer(Number(button.dataset.debugLayer), true);
    });
  });
'''
if text.count(old_layers) != 1:
    raise RuntimeError('old layer listener block not found')
text = text.replace(old_layers, new_layers, 1)

old_visibility = r'''  debugVisibilityButtons.forEach(button => {
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
'''
new_visibility = r'''  debugVisibilityButtons.forEach(button => {
    button.addEventListener('mousedown', event => { event.preventDefault(); event.stopPropagation(); });
    button.addEventListener('click', event => {
      event.preventDefault();
      event.stopPropagation();
      const layer = Number(button.dataset.layerIndex);
      setOverlayVisible(layer, !overlayVisibility[layer]);
      debugViewMode = 'manual';
      debugViewSolo.classList.remove('debug-selected');
      debugViewAll.classList.remove('debug-selected');
      debugViewNone.classList.remove('debug-selected');
    });
  });
  syncVisibilityButtons();
'''
if text.count(old_visibility) != 1:
    raise RuntimeError('old visibility listener block not found')
text = text.replace(old_visibility, new_visibility, 1)

# MOVE click still dispatches the engine key in the earlier listener; this second
# listener only mirrors the browser mode state.
old_move_state = r'''  moveSpriteButton.addEventListener('click', () => {
    debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
    moveSpriteButton.classList.add('debug-selected-action');
  });
'''
new_move_state = r'''  moveSpriteButton.addEventListener('click', () => {
    debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
    moveSpriteButton.classList.add('debug-selected-action');
    debugMode = 'sprites';
    debugInspectActive = false;
    debugEraserActive = false;
    debugModeButtons();
    updateDebugWorkspaceStatus();
  });
'''
if text.count(old_move_state) != 1:
    raise RuntimeError('MOVE state listener not found')
text = text.replace(old_move_state, new_move_state, 1)

old_keyboard_sync = r'''  window.addEventListener('keydown', event => {
    if (!event.isTrusted || !paintUiActive || event.repeat) return;
    if (/^[1-5]$/.test(event.key)) selectDebugLayer(Number(event.key));
    else if (event.key === '6') {
      debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
      moveSpriteButton.classList.add('debug-selected-action');
    }
  }, true);
'''
new_keyboard_sync = r'''  window.addEventListener('keydown', event => {
    if (!event.isTrusted || !paintUiActive || event.repeat) return;
    if (/^[1-5]$/.test(event.key)) {
      selectDebugLayer(Number(event.key), false);
      debugMode = 'paint';
      debugInspectActive = false;
      debugEraserActive = false;
      if (debugViewMode === 'solo') setTimeout(() => applyDebugViewMode('solo'), 0);
      debugModeButtons();
    } else if (event.key === '6') {
      debugLayerButtons.forEach(button => button.classList.remove('debug-selected'));
      moveSpriteButton.classList.add('debug-selected-action');
      debugMode = 'sprites';
      debugInspectActive = false;
      debugModeButtons();
    } else if (event.key.toLowerCase() === 'i') {
      debugInspectActive = !debugInspectActive;
      debugMode = debugInspectActive ? 'inspect' : 'paint';
      debugModeButtons();
    }
    updateDebugWorkspaceStatus();
  }, true);
'''
if text.count(old_keyboard_sync) != 1:
    raise RuntimeError('keyboard palette sync block not found')
text = text.replace(old_keyboard_sync, new_keyboard_sync, 1)

# Brush value changes should also refresh the compact status line.
brush_update = '''    brushValue.textContent = brushSize + ' PX';
'''
if text.count(brush_update) != 2:
    raise RuntimeError(f'brush readout anchors expected 2, found {text.count(brush_update)}')
text = text.replace(brush_update, brush_update + '    updateDebugWorkspaceStatus();\n')

# Cache-bust the rebuilt editor shell.
old_tag = "const BUILD_TAG = '20260827-script-fall-visible-2';"
new_tag = "const BUILD_TAG = '20260827-debug-workspace-v3';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('BUILD_TAG anchor not found')

path.write_text(text)
print('Debug workspace v3 installed: docked sidebar, SOLO/ALL views, PAINT/SPRITES/INSPECT, opacity/outline, undo/redo, no canvas overlap')
