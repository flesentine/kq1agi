#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: tune_room1_tree.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
path = root / 'core/src/main/java/com/agifans/agile/ModernRoomDepth.java'
text = path.read_text()

# The bark detector finds the right side well, but on the interactive left side
# it includes dark/ochre texture several AGI pixels before the painted silhouette
# actually reaches Graham. Keep the generated solid mask, then impose a manual
# left-edge floor measured from play-test screenshots. This changes ONLY the left
# edge; the right edge that already behaved well stays untouched.
priority_old = '''        return treeBitAt(x, y) ? ROOM1_TREE_PRIORITY : DEFAULT_PRIORITY;\n'''
priority_new = '''        boolean tree = treeBitAt(x, y);\n        int minimumX = minimumTreeXForRow(y);\n        if (tree && minimumX > 0 && x < minimumX) {\n            tree = false;\n        }\n        return tree ? ROOM1_TREE_PRIORITY : DEFAULT_PRIORITY;\n'''
if text.count(priority_old) != 1:
    raise RuntimeError('ModernRoomDepth priority return site not found')
text = text.replace(priority_old, priority_new)

priority_marker = '''    /**\n     * Returns -1 when Sierra's original visual priority should be used.\n'''
helper = '''    /**\n     * Hand-tuned left edge of the painted trunk at AGI resolution.\n     *\n     * These values are intentionally conservative: foreground grass must never\n     * erase Graham. The generated mask still supplies the irregular right edge\n     * and all branch detail.\n     */\n    private static int minimumTreeXForRow(int y) {\n        if (y >= 80 && y <= 85) return 130;\n        if (y >= 86 && y <= 91) return 132;\n        if (y >= 92 && y <= 99) return 134;\n        if (y >= 100 && y <= 117) return 135;\n        if (y >= 118 && y <= 124) return 136;\n        if (y >= 125 && y <= 126) return 134;\n        if (y >= 127 && y <= 130) return 136;\n        if (y >= 131 && y <= 133) return 138;\n        return 0;\n    }\n\n'''
if text.count(priority_marker) != 1:
    raise RuntimeError('ModernRoomDepth priority marker not found')
text = text.replace(priority_marker, helper + priority_marker)

# Physical collision belongs at the ground-contact roots, not in the vertical
# trunk. Moving the footprint down means Graham can walk behind the tree at the
# depth shown in the screenshots, but cannot walk through the base in front.
start = text.index('    private static boolean treeBasePoint(int x, int y) {')
end_marker = '    /** True when Graham\'s baseline overlaps the physical tree base. */'
end = text.index(end_marker, start)
replacement = '''    private static boolean treeBasePoint(int x, int y) {\n        switch (y) {\n            case 136: return x >= 134 && x <= 148;\n            case 137: return x >= 132 && x <= 150;\n            case 138: return x >= 131 && x <= 151;\n            case 139: return x >= 130 && x <= 152;\n            case 140: return x >= 131 && x <= 151;\n            default: return false;\n        }\n    }\n\n'''
text = text[:start] + replacement + text[end:]

path.write_text(text)
print('Final Room 1 tree tuning applied: conservative left silhouette; root collision Y=136..140')
