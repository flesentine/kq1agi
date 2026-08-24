#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_brush_overlay.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

css_anchor = '''    #paint-button:hover, #export-bg-button:hover { background: #333; }
    #paint-button:active, #export-bg-button:active { transform: translateY(1px); }
'''
css_repl = '''    #paint-button:hover, #export-bg-button:hover { background: #333; }
    #paint-button:active, #export-bg-button:active { transform: translateY(1px); }
    #brush-control {
      position: fixed;
      left: 16px;
      bottom: 18px;
      z-index: 10002;
      display: none;
      width: 220px;
      box-sizing: border-box;
      padding: 9px 11px 10px;
      border: 1px solid rgba(255,255,255,.65);
      border-radius: 9px;
      background: rgba(12,12,12,.88);
      color: #fff;
      font: 700 12px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      box-shadow: 0 2px 10px rgba(0,0,0,.5);
      user-select: none;
    }
    #brush-control .brush-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
    #brush-control .brush-value { min-width: 44px; text-align: right; font-variant-numeric: tabular-nums; }
    #brush-control .brush-hint { margin-top: 3px; opacity: .65; font-weight: 500; font-size: 10px; }
    #brush-size { width: 100%; margin: 7px 0 0; accent-color: #fff; cursor: pointer; }
'''
if text.count(css_anchor) != 1:
    raise RuntimeError('web brush CSS anchor not found')
text = text.replace(css_anchor, css_repl)

html_anchor = '''<button id="export-bg-button" type="button" title="Download the clean high-resolution room background">EXPORT BG</button>
<button id="paint-button" type="button" title="Toggle live scene-mask paint mode (Tab shortcut)">PAINT</button>
'''
html_repl = '''<button id="export-bg-button" type="button" title="Download the clean high-resolution room background">EXPORT BG</button>
<button id="paint-button" type="button" title="Open debug edit mode (Tab shortcut)">DEBUG</button>
<div id="brush-control" aria-label="Debug brush size">
  <div class="brush-row"><span>BRUSH SIZE</span><span id="brush-value" class="brush-value">2 PX</span></div>
  <input id="brush-size" type="range" min="1" max="12" step="1" value="2" aria-label="Brush size from 1 to 12 pixels">
  <div class="brush-hint">1 px = single mask pixel · Space + drag = pan</div>
</div>
'''
if text.count(html_anchor) != 1:
    raise RuntimeError('web brush HTML anchor not found')
text = text.replace(html_anchor, html_repl)

const_anchor = '''  const paintButton = document.getElementById('paint-button');
  const exportBgButton = document.getElementById('export-bg-button');
'''
const_repl = '''  const paintButton = document.getElementById('paint-button');
  const exportBgButton = document.getElementById('export-bg-button');
  const brushControl = document.getElementById('brush-control');
  const brushSlider = document.getElementById('brush-size');
  const brushValue = document.getElementById('brush-value');
  let paintUiActive = false;
  let brushSize = 2;
'''
if text.count(const_anchor) != 1:
    raise RuntimeError('web brush JS constants anchor not found')
text = text.replace(const_anchor, const_repl)

send_anchor = '''  async function exportCleanBackground() {
'''
helpers = '''  function gameCanvas() {
    return document.querySelector('#embed-html canvas, canvas');
  }

  function focusGameCanvas() {
    const canvas = gameCanvas();
    if (canvas) canvas.focus();
    window.focus();
    return canvas;
  }

  function tapGameKey(key, code, keyCode) {
    const canvas = focusGameCanvas();
    function fire(type) {
      const event = new KeyboardEvent(type, {
        key,
        code,
        bubbles: true,
        cancelable: true
      });
      try { Object.defineProperty(event, 'keyCode', { get: () => keyCode }); } catch (e) {}
      try { Object.defineProperty(event, 'which', { get: () => keyCode }); } catch (e) {}
      (canvas || document).dispatchEvent(event);
      document.dispatchEvent(event);
      window.dispatchEvent(event);
    }
    fire('keydown');
    fire('keyup');
  }

  function setPaintUiActive(active) {
    paintUiActive = !!active;
    brushControl.style.display = paintUiActive ? 'block' : 'none';
    paintButton.textContent = paintUiActive ? 'TEST' : 'DEBUG';
    paintButton.title = paintUiActive ? 'Return to live test mode (Tab shortcut)' : 'Open debug edit mode (Tab shortcut)';
  }

  function applyBrushSize(value) {
    brushSize = Math.max(1, Math.min(12, Number(value) || 1));
    brushSlider.value = String(brushSize);
    brushValue.textContent = brushSize + ' PX';
    if (!paintUiActive) return;

    // Clamp Java's brush to 1, then step up to the exact requested value. This
    // makes the HTML slider absolute even if [ or ] was used previously.
    for (let i = 0; i < 12; i++) tapGameKey('[', 'BracketLeft', 219);
    for (let i = 1; i < brushSize; i++) tapGameKey(']', 'BracketRight', 221);
    focusGameCanvas();
  }

  async function exportCleanBackground() {
'''
if text.count(send_anchor) != 1:
    raise RuntimeError('web brush helper insertion anchor not found')
text = text.replace(send_anchor, helpers)

paint_click = '''  paintButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    sendF2();
  });
'''
paint_click_repl = '''  paintButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();
    sendF2();
    setPaintUiActive(!paintUiActive);
    if (paintUiActive) applyBrushSize(brushSize);
  });
'''
if text.count(paint_click) != 1:
    raise RuntimeError('web debug button click anchor not found')
text = text.replace(paint_click, paint_click_repl)

tab_anchor = '''  window.addEventListener('keydown', event => {
    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
    event.preventDefault();
    event.stopPropagation();
    sendF2();
  }, true);
'''
tab_repl = '''  window.addEventListener('keydown', event => {
    if (event.key !== 'Tab' || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
    event.preventDefault();
    event.stopPropagation();
    sendF2();
    setPaintUiActive(!paintUiActive);
    if (paintUiActive) applyBrushSize(brushSize);
  }, true);

  // If the user presses an actual F2 key, keep the browser overlay in sync. The
  // synthetic F2 sent by DEBUG/Tab is untrusted and therefore does not double-toggle.
  window.addEventListener('keydown', event => {
    if (!event.isTrusted || event.key !== 'F2' || event.repeat) return;
    setPaintUiActive(!paintUiActive);
    if (paintUiActive) applyBrushSize(brushSize);
  }, true);

  brushControl.addEventListener('mousedown', event => {
    event.stopPropagation();
  });
  brushControl.addEventListener('mouseup', event => {
    event.stopPropagation();
  });
  brushSlider.addEventListener('input', event => {
    event.stopPropagation();
    applyBrushSize(event.target.value);
  });
  brushSlider.addEventListener('change', () => focusGameCanvas());

  // Keep the numeric browser readout aligned when the old [ / ] shortcuts are used.
  window.addEventListener('keydown', event => {
    if (!paintUiActive || !event.isTrusted || event.repeat) return;
    if (event.code === 'BracketLeft') {
      brushSize = Math.max(1, brushSize - 1);
      brushSlider.value = String(brushSize);
      brushValue.textContent = brushSize + ' PX';
    } else if (event.code === 'BracketRight') {
      brushSize = Math.min(12, brushSize + 1);
      brushSlider.value = String(brushSize);
      brushValue.textContent = brushSize + ' PX';
    }
  }, true);
'''
if text.count(tab_anchor) != 1:
    raise RuntimeError('web Tab shortcut anchor not found')
text = text.replace(tab_anchor, tab_repl)

# Hide the control during recovery just like the other editor UI.
recovery_anchor = '''    paintButton.style.display = 'none';
    exportBgButton.style.display = 'none';
'''
recovery_repl = '''    paintButton.style.display = 'none';
    exportBgButton.style.display = 'none';
    brushControl.style.display = 'none';
    paintUiActive = false;
'''
if text.count(recovery_anchor) != 1:
    raise RuntimeError('web recovery UI anchor not found')
text = text.replace(recovery_anchor, recovery_repl)

path.write_text(text)
print('Fixed browser debug brush overlay installed: persistent through zoom, 1-12 px numeric slider')
