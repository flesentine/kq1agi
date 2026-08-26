#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: add_reset_sprite_button.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()

button_anchor = '''    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <div id="debug-move-help">Click MOVE SPRITE, click the sprite once, then drag anywhere in the game.</div>\n'''
button_repl = '''    <button id="move-sprite-button" type="button">MOVE SPRITE</button>\n    <button id="reset-sprite-button" type="button" style="width:100%;box-sizing:border-box;padding:9px 10px;border:1px solid #ff8b8b;border-radius:7px;background:#2a1717;color:#fff;font:700 12px system-ui,-apple-system,BlinkMacSystemFont,sans-serif;cursor:pointer;">RESET SPRITE</button>\n    <div id="debug-move-help">MOVE SPRITE is temporary for Graham. RESET SPRITE clears every saved Graham debug pin and returns him to normal AGI movement.</div>\n'''
if text.count(button_anchor) != 1:
    raise RuntimeError('MOVE SPRITE button anchor not found')
text = text.replace(button_anchor, button_repl, 1)

const_anchor = '''  const moveSpriteButton = document.getElementById('move-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n'''
const_repl = '''  const moveSpriteButton = document.getElementById('move-sprite-button');\n  const resetSpriteButton = document.getElementById('reset-sprite-button');\n  const debugCopyButton = document.getElementById('debug-copy-button');\n'''
if text.count(const_anchor) != 1:
    raise RuntimeError('MOVE SPRITE const anchor not found')
text = text.replace(const_anchor, const_repl, 1)

listener_anchor = '''  debugCopyButton.addEventListener('click', event => {\n'''
listener_repl = r'''  function clearPersistedEgoPins() {
    const prefKey = 'agi-scene-mask-editor-v3:visualPinsV1s';

    // Remove Graham (AGI object 0) from the browser preference before the GWT
    // app starts. This makes old MOVE SPRITE accidents self-heal on reload.
    try {
      const saved = localStorage.getItem(prefKey);
      if (saved) {
        const kept = saved.split(';').filter(record => {
          const p = record.split(',');
          return !(p.length === 5 && Number(p[1]) === 0);
        });
        if (kept.length) localStorage.setItem(prefKey, kept.join(';'));
        else localStorage.removeItem(prefKey);
      }
    } catch (error) {
      console.warn('Could not clear persisted Graham debug pin', error);
    }

    // Also clear any already-loaded Graham pins from the live shared table so
    // RESET SPRITE works immediately without relying on keyboard focus/timing.
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab) return false;

      const data = new Int32Array(sab);
      const countIndex = 3981;
      const recordsIndex = 3982;
      const maxRecords = 32;
      const fieldsPerRecord = 5;
      const count = Math.max(0, Math.min(maxRecords, data[countIndex] | 0));
      let out = 0;

      for (let i = 0; i < count; i++) {
        const src = recordsIndex + (i * fieldsPerRecord);
        if ((data[src + 1] | 0) === 0) continue;
        if (out !== i) {
          const dst = recordsIndex + (out * fieldsPerRecord);
          for (let f = 0; f < fieldsPerRecord; f++) data[dst + f] = data[src + f];
        }
        out++;
      }

      for (let i = out; i < count; i++) {
        const base = recordsIndex + (i * fieldsPerRecord);
        for (let f = 0; f < fieldsPerRecord; f++) data[base + f] = 0;
      }
      data[countIndex] = out;
      return out !== count;
    } catch (error) {
      console.warn('Could not clear live Graham debug pin', error);
      return false;
    }
  }

  // This runs before prepareIsolation() starts AGILE, so fresh loads never
  // import a stale Graham visual pin into the Java Preferences instance.
  clearPersistedEgoPins();

  // If Java flushes its in-memory Preferences while exiting DEBUG, clean the
  // browser value again after that flush so an old Graham record cannot return.
  paintButton.addEventListener('click', () => {
    setTimeout(clearPersistedEgoPins, 160);
  });

  resetSpriteButton.addEventListener('mousedown', event => {
    event.preventDefault();
    event.stopPropagation();
  });
  resetSpriteButton.addEventListener('click', event => {
    event.preventDefault();
    event.stopPropagation();

    clearPersistedEgoPins();

    // Keep the engine-side Backspace path as a compatibility fallback if the
    // shared-table layout changes in a future AGILE build.
    if (!paintUiActive) {
      sendF2();
      setPaintUiActive(true);
    }
    tapGameKey('5', 'Digit5', 53);
    setTimeout(() => {
      tapGameKey('Backspace', 'Backspace', 8);
      clearPersistedEgoPins();
      focusGameCanvas();
      const old = resetSpriteButton.textContent;
      resetSpriteButton.textContent = 'GRAHAM RESET';
      setTimeout(() => { resetSpriteButton.textContent = old; }, 900);
    }, 60);
  });

  debugCopyButton.addEventListener('click', event => {
'''
if text.count(listener_anchor) != 1:
    raise RuntimeError('debug copy listener anchor not found')
text = text.replace(listener_anchor, listener_repl, 1)

path.write_text(text)
print('RESET SPRITE safety button installed; stale Graham debug pins are purged on load and reset')
