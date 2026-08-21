#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_room1_overlay_runtime.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

# tune_room1_tree.py originally published the foreground-overlay flag from the
# no-argument GameState.drawObjects(). That method is used for full redraws, but
# the normal animation loop calls drawObjects(List<AnimatedObject>) directly.
# Result: while Graham walks, the UI thread never receives his current depth and
# the real tree overlay stays off. Publish the flag from the overload that is
# actually called every animation tick.
path = root / 'core/src/main/java/com/agifans/agile/GameState.java'
text = path.read_text()

marker = '''    public void drawObjects(List<AnimatedObject> objectDrawList) {
        // Draw the AnimatedObjects to screen in priority order.
'''
replacement = '''    public void drawObjects(List<AnimatedObject> objectDrawList) {
        // Publish Room 1 foreground depth on EVERY animation redraw. Interpreter
        // animateObjects() calls this overload directly, so this is the reliable
        // worker -> UI handoff for the real painted tree overlay.
        boolean modernTreeOverlay =
                "KQ1".equalsIgnoreCase(gameId)
                && (getVar(Defines.CURROOM) == 1)
                && pictureVisible
                && (ego != null)
                && ego.drawn
                && (ego.y <= 122);
        variableData.setModernRoomOverlay(modernTreeOverlay);

        // Draw the AnimatedObjects to screen in priority order.
'''

if text.count(marker) != 1:
    raise RuntimeError(
        f'GameState drawObjects(List) marker expected once, found {text.count(marker)}'
    )

path.write_text(text.replace(marker, replacement))

print('Room 1 overlay runtime hook fixed: depth flag now updates every animation frame')
