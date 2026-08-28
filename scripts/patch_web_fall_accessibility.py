#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_web_fall_accessibility.py /path/to/index.html')

path = Path(sys.argv[1])
text = path.read_text()


def one(old, new, label):
    global text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: expected 1 match, found {count}')
    text = text.replace(old, new, 1)


# Make the FALL button and legend identifiable without relying on magenta/orange.
style_anchor = '  </style>\n'
style = r'''    /* FALL accessibility: pattern/contrast are primary; hue is secondary. */
    .debug-layer[data-debug-layer="5"] {
      color: #fff !important;
      background-image: repeating-linear-gradient(135deg,
        rgba(255,255,255,.18) 0 3px, rgba(0,0,0,.28) 3px 6px) !important;
    }
    .debug-layer[data-debug-layer="5"].debug-selected {
      background-color: #4e420d !important;
      background-image: repeating-linear-gradient(135deg,
        rgba(255,255,255,.26) 0 3px, rgba(0,0,0,.34) 3px 6px) !important;
    }
    .fall-access-title { font-weight: 850; color: #fff; }
    .fall-access-status { display: block; margin-top: 3px; font-weight: 750; color: #f2f2f2; }
    .fall-access-none { color: #fff; text-decoration: underline; text-underline-offset: 2px; }
    .fall-pattern-swatch {
      display: inline-block; width: 18px; height: 9px; margin: 0 4px 0 2px;
      border: 1px solid rgba(255,255,255,.7); vertical-align: -1px;
    }
    .fall-editable-pattern {
      background: repeating-linear-gradient(135deg, #fff 0 2px, #111 2px 4px);
    }
    .fall-script-pattern {
      background: linear-gradient(90deg, #111 0 50%, #fff 50% 100%);
    }
    .fall-halo-pattern {
      border-style: dashed; background: transparent;
    }
    .fall-access-warning {
      display: block; margin-top: 4px; padding-top: 4px;
      border-top: 1px solid rgba(255,255,255,.14); font-weight: 750;
    }
  </style>
'''
one(style_anchor, style, 'FALL accessibility style anchor')

old_help = r'''  function updateDebugContextHelp() {
    const help = {
      1: '<span class="legend-dot legend-front"></span><strong>FRONT</strong> redraws room pixels over Graham.',
      2: '<span class="legend-dot legend-block"></span><strong>BLOCK</strong> is the active walk/collision map.',
      3: '<span class="legend-dot legend-behind"></span><strong>BEHIND</strong> marks where Graham passes behind foreground art.',
      4: '<span class="legend-dot legend-water"></span><strong>WATER</strong> is the editable AGI water control.',
      5: '<span class="legend-dot legend-fall"></span><strong>FALL</strong> editable danger · <span class="legend-dot legend-script"></span>orange = original scripted danger.'
    };
    debugContextHelp.innerHTML = help[selectedDebugLayer] || help[1];
  }
'''
new_help = r'''  const FALL_MASK_WORDS = 840;
  const FALL_MASK_BITS_BASE = 4143;
  const FALL_CONTROL_SEED_STATE = 4983;
  const SCRIPT_FALL_BITS_BASE = 4984;
  const SCRIPT_FALL_SEED_STATE = 5824;

  function readDebugInt(values, index) {
    try { return Atomics.load(values, index); }
    catch (error) { return values[index] || 0; }
  }

  function popcount32(value) {
    let v = value >>> 0;
    v = v - ((v >>> 1) & 0x55555555);
    v = (v & 0x33333333) + ((v >>> 2) & 0x33333333);
    return ((((v + (v >>> 4)) & 0x0f0f0f0f) * 0x01010101) >>> 24);
  }

  function countExactMaskPixels(values, start) {
    let total = 0;
    for (let i = 0; i < FALL_MASK_WORDS; i++) total += popcount32(readDebugInt(values, start + i));
    return total;
  }

  function readFallAccessibilityState() {
    try {
      const sab = window.__kq1agiVariableSAB;
      if (!sab) return { available: false };
      const values = new Int32Array(sab);
      if (values.length <= SCRIPT_FALL_SEED_STATE) return { available: false };
      const room = readDebugInt(values, 0) & 255;
      const fallReady = readDebugInt(values, FALL_CONTROL_SEED_STATE) === room + 1;
      const scriptReady = readDebugInt(values, SCRIPT_FALL_SEED_STATE) === room + 1;
      return {
        available: true,
        room,
        fallReady,
        scriptReady,
        fallPixels: fallReady ? countExactMaskPixels(values, FALL_MASK_BITS_BASE) : null,
        scriptPixels: scriptReady ? countExactMaskPixels(values, SCRIPT_FALL_BITS_BASE) : null
      };
    } catch (error) {
      return { available: false };
    }
  }

  function fallAccessibilityHelp() {
    const state = readFallAccessibilityState();
    if (!state.available) {
      return '<span class="fall-access-title">FALL</span><span class="fall-access-status">Mask state unavailable.</span>';
    }

    const fallText = state.fallReady ? (state.fallPixels + ' px') : 'SCANNING…';
    const scriptText = state.scriptReady ? (state.scriptPixels + ' px') : 'SCANNING…';
    const ready = state.fallReady && state.scriptReady;
    const empty = ready && state.fallPixels === 0 && state.scriptPixels === 0;
    let html = '<span class="fall-access-title">FALL · AGI HITSPEC / control 2</span>'
      + '<span class="fall-access-status' + (empty ? ' fall-access-none' : '') + '">'
      + (empty ? 'NONE IN THIS ROOM · ' : '')
      + 'HITSPEC: ' + fallText + ' · DETECTED SCRIPT: ' + scriptText + '</span>';

    if (ready && !empty) {
      html += '<span class="fall-access-status">'
        + '<span class="fall-pattern-swatch fall-editable-pattern"></span>//// = editable HITSPEC '
        + '<span class="fall-pattern-swatch fall-script-pattern"></span>two-tone = exact detected trigger '
        + '<span class="fall-pattern-swatch fall-halo-pattern"></span>dotted = visibility halo only'
        + '</span>';
    } else if (!ready) {
      html += '<span class="fall-access-status">Waiting for the room control/script scan before deciding whether FALL is empty.</span>';
    }

    if (debugEraserActive) {
      html += '<span class="fall-access-warning">ERASE warning: removing an exact detected-script marker can disable that detected hazard.</span>';
    }
    return html;
  }

  function updateDebugContextHelp() {
    const help = {
      1: '<span class="legend-dot legend-front"></span><strong>FRONT</strong> redraws room pixels over Graham.',
      2: '<span class="legend-dot legend-block"></span><strong>BLOCK</strong> is the active walk/collision map.',
      3: '<span class="legend-dot legend-behind"></span><strong>BEHIND</strong> marks where Graham passes behind foreground art.',
      4: '<span class="legend-dot legend-water"></span><strong>WATER</strong> is the editable AGI water control.'
    };
    debugContextHelp.innerHTML = selectedDebugLayer === 5
      ? fallAccessibilityHelp()
      : (help[selectedDebugLayer] || help[1]);
  }
'''
one(old_help, new_help, 'FALL context help block')

# Cache-bust the accessible renderer/sidebar as one coherent build.
old_tag = "const BUILD_TAG = '20260827-debug-workspace-v3-display1';"
new_tag = "const BUILD_TAG = '20260828-fall-accessible-v1';"
if old_tag in text:
    text = text.replace(old_tag, new_tag, 1)
elif new_tag not in text:
    raise RuntimeError('FALL accessibility build tag not found')

path.write_text(text)
print('FALL browser accessibility installed: scan-aware exact counts, non-colour legend, erase warning')
