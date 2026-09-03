#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_certification.py /path/to/index.html')

path = Path(sys.argv[1])
html = path.read_text()

if 'id="certify-button"' in html or 'certification/certification-panel.mjs' in html:
    raise RuntimeError('CERTIFY browser integration is already present')

for anchor, label in [
    ('</style>', 'style close'),
    ('<div id="boot-message">', 'boot message'),
    ('</body>', 'body close'),
]:
    if html.count(anchor) != 1:
        raise RuntimeError(f'CERTIFY {label}: expected exactly one anchor, found {html.count(anchor)}')

css = r'''
    /* CERTIFY remains below the normal launcher stack. */
    #certify-button {
      position: fixed; top: 150px; left: 14px; z-index: 10003; display: none;
      width: 104px; min-height: 36px; box-sizing: border-box;
      padding: 9px 13px; border: 2px solid #7fffb0; border-radius: 8px;
      background: rgba(7, 28, 18, .92); color: #b8ffd0;
      font: 800 13px system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      letter-spacing: .05em; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.45);
    }
    #certify-button:hover { background: rgba(17, 58, 36, .96); }
    #certify-panel {
      position: fixed; top: 198px; left: 14px; z-index: 10004; width: min(450px, calc(100vw - 28px));
      max-height: calc(100vh - 212px); overflow: auto; box-sizing: border-box;
      padding: 14px; border: 1px solid rgba(127,255,176,.65); border-radius: 10px;
      background: rgba(5, 10, 8, .96); color: #e7ffee;
      font: 13px/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      box-shadow: 0 8px 30px rgba(0,0,0,.6);
    }
    #certify-panel[aria-hidden="true"] { display: none; }
    #certify-panel header { display: flex; align-items: center; gap: 8px; margin-bottom: 10px; }
    #certify-panel h2 { margin: 0; flex: 1; font: 800 14px system-ui, sans-serif; letter-spacing: .06em; }
    #certify-panel button, #certify-panel select, #certify-panel input {
      box-sizing: border-box; border: 1px solid #456252; border-radius: 6px;
      background: #0f1813; color: #effff4; font: inherit; padding: 7px 8px;
    }
    #certify-panel button { cursor: pointer; font-weight: 700; }
    #certify-panel button:disabled { opacity: .45; cursor: default; }
    #certify-panel label { display: grid; gap: 4px; margin: 8px 0; color: #b8c9be; }
    #certify-actions { display: flex; gap: 7px; flex-wrap: wrap; margin: 10px 0; }
    #certify-status { display: inline-block; margin: 4px 0 8px; padding: 5px 8px; border-radius: 999px; background: #1a211d; font-weight: 800; }
    #certify-status[data-state="MATCH"], #certify-status[data-state="READY"] { background: #103a22; color: #9dffbd; }
    #certify-status[data-state="DIVERGED"], #certify-status[data-state="ERROR"] { background: #4a1717; color: #ffb3b3; }
    #certify-status[data-state="BUSY"], #certify-status[data-state="WAITING"] { background: #43350e; color: #ffe59a; }
    #certify-recording { margin: 8px 0; padding: 7px 8px; border-radius: 6px; background: #101713; color: #c5d8cb; }
    #certify-progress { color: #b8c9be; margin-bottom: 8px; }
    #certify-detail { margin: 0; padding: 9px; white-space: pre-wrap; overflow-wrap: anywhere; background: #070b09; border-radius: 6px; color: #d7e7dc; }
    #certify-privacy { color: #8fa99a; font: 11px/1.35 system-ui, sans-serif; margin: 8px 0 0; }
    @media (max-width: 520px) {
      #certify-button { top: 140px; left: 8px; width: 96px; }
      #certify-panel {
        top: 188px; left: 8px; width: calc(100vw - 16px);
        max-height: calc(100vh - 196px);
      }
    }
'''
html = html.replace('</style>', css + '</style>', 1)

# This bootstrap must execute before AGILE starts. It records only the exact
# transport values already sent to the normal PLAY worker; it does not intercept
# browser key mapping or upload/persist the journal.
recording_bootstrap = r'''<script id="phase1d-recording-bootstrap">
(function () {
  const MAX_EVENTS = 250000;
  window.__kq1agiPlayRecordingRaw = [];
  window.__kq1agiPlayRecordingSeq = 0;
  window.__kq1agiPlayRecordingOverflow = false;
  window.__kq1agiPlayLastCompletedTick = 0;
  window.__kq1agiRecordTransportEvent = function (event) {
    if (!event || typeof event !== 'object') return;
    const journal = window.__kq1agiPlayRecordingRaw;
    if (!Array.isArray(journal)) return;
    if (journal.length >= MAX_EVENTS) {
      window.__kq1agiPlayRecordingOverflow = true;
      return;
    }
    let vars = null;
    try {
      if (window.__kq1agiVariableSAB) vars = new Int32Array(window.__kq1agiVariableSAB);
    } catch (ignored) {}
    const suppliedTick = Number(event.tick);
    const tick = Number.isFinite(suppliedTick)
      ? Math.max(0, suppliedTick | 0)
      : (vars ? Math.max(0, Atomics.load(vars, 512) | 0) : 0);
    const inTick = vars ? (Atomics.load(vars, 517) | 0) : 0;
    const copy = Object.assign({}, event, {
      tick: tick,
      phase: inTick === 0 ? 'idle' : 'busy',
      seq: ++window.__kq1agiPlayRecordingSeq
    });
    journal.push(copy);
  };
})();
</script>
'''

panel = r'''<button id="certify-button" type="button" title="Open deterministic ORIGINAL-vs-EDITED certification">CERTIFY</button>
<aside id="certify-panel" aria-hidden="true" aria-label="Truth engine certification">
  <header>
    <h2>ORIGINAL vs EDITED · CERTIFY</h2>
    <button id="certify-close-button" type="button" title="Close certification panel">×</button>
  </header>
  <label>Local imported game
    <select id="certify-game-select"><option>Scanning…</option></select>
  </label>
  <label>Shared barriers for no-input smoke
    <input id="certify-barrier-count" type="number" min="1" max="1000" step="1" value="60">
  </label>
  <div id="certify-recording">PLAY journal: waiting for the first logical tick…</div>
  <div id="certify-actions">
    <button id="certify-refresh-button" type="button">REFRESH</button>
    <button id="certify-run-button" type="button">SMOKE RUN</button>
    <button id="certify-replay-button" type="button">REPLAY PLAY</button>
    <button id="certify-stop-button" type="button" disabled>STOP</button>
  </div>
  <div id="certify-status" data-state="IDLE">IDLE</div>
  <div id="certify-progress">0 certified barriers</div>
  <pre id="certify-detail">Phase -1D records the normal PLAY transport from page start so the same input/RNG/timing window can be replayed through ORIGINAL and EDITED.</pre>
  <p id="certify-privacy">Local-only: GAMEFILES.DAT stays in same-origin OPFS and the PLAY journal stays in memory. Nothing is uploaded.</p>
</aside>
'''
html = html.replace('<div id="boot-message">', recording_bootstrap + panel + '<div id="boot-message">', 1)
html = html.replace('</body>', '<script type="module" src="certification/certification-panel.mjs"></script>\n<script type="module" src="certification/certification-phase1d.mjs"></script>\n</body>', 1)

for marker in [
    '#certify-button {',
    'top: 150px; left: 14px',
    'top: 198px; left: 14px',
    'id="phase1d-recording-bootstrap"',
    '__kq1agiRecordTransportEvent',
    '__kq1agiPlayLastCompletedTick',
    'id="certify-button"',
    'id="certify-panel"',
    'id="certify-replay-button"',
    'id="certify-recording"',
    'certification/certification-panel.mjs',
    'certification/certification-phase1d.mjs',
]:
    if marker not in html:
        raise RuntimeError(f'CERTIFY injection failed to produce marker: {marker}')

path.write_text(html)
print('Phase -1D CERTIFY replay UI and in-memory PLAY journal injected')
