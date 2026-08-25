#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_painterly_dialog_layout.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
text_graphics = root / 'core/src/main/java/com/agifans/agile/TextGraphics.java'
text = text_graphics.read_text()

if 'PAINTERLY_DIALOG_FRAME' not in text:
    raise RuntimeError('painterly dialog frame patch must run first')

# The generated source art intentionally contains a transparent halo around the
# painted sign. At AGI scale that halo became long see-through/dashed streaks.
# Keep only the useful painted area when sampling, and make the parchment itself
# fully opaque while preserving a little edge antialiasing.
old_put = '''    private void putPainterlyPixel(int screenX, int screenY, int sourcePixel) {
        if (screenX < 0 || screenX >= 320 || screenY < 0 || screenY >= 200) return;
        int alpha = sourcePixel & 0xFF;
        if (alpha == 0) return;
        int screenPos = (screenY * 320) + screenX;
        if (alpha == 255) {
            pixelData.putPixel(screenPos, sourcePixel);
            return;
        }

        int destinationPixel = pixelData.getPixel(screenPos);
        int inverse = 255 - alpha;
        int sr = (sourcePixel >>> 24) & 0xFF;
        int sg = (sourcePixel >>> 16) & 0xFF;
        int sb = (sourcePixel >>> 8) & 0xFF;
        int dr = (destinationPixel >>> 24) & 0xFF;
        int dg = (destinationPixel >>> 16) & 0xFF;
        int db = (destinationPixel >>> 8) & 0xFF;
        int r = ((sr * alpha) + (dr * inverse) + 127) / 255;
        int g = ((sg * alpha) + (dg * inverse) + 127) / 255;
        int b = ((sb * alpha) + (db * inverse) + 127) / 255;
        pixelData.putPixel(screenPos, (r << 24) | (g << 16) | (b << 8) | 0xFF);
    }
'''
new_put = '''    private void putPainterlyPixel(int screenX, int screenY, int sourcePixel) {
        if (screenX < 0 || screenX >= 320 || screenY < 0 || screenY >= 200) return;
        int alpha = sourcePixel & 0xFF;
        if (alpha == 0) return;
        // PAINTERLY_DIALOG_LAYOUT_V2: generated parchment is effectively opaque;
        // snap near-opaque pixels to 255 so the scene never ghosts through it.
        if (alpha >= 220) alpha = 255;
        int screenPos = (screenY * 320) + screenX;
        if (alpha == 255) {
            pixelData.putPixel(screenPos, (sourcePixel & 0xFFFFFF00) | 0xFF);
            return;
        }

        int destinationPixel = pixelData.getPixel(screenPos);
        int inverse = 255 - alpha;
        int sr = (sourcePixel >>> 24) & 0xFF;
        int sg = (sourcePixel >>> 16) & 0xFF;
        int sb = (sourcePixel >>> 8) & 0xFF;
        int dr = (destinationPixel >>> 24) & 0xFF;
        int dg = (destinationPixel >>> 16) & 0xFF;
        int db = (destinationPixel >>> 8) & 0xFF;
        int r = ((sr * alpha) + (dr * inverse) + 127) / 255;
        int g = ((sg * alpha) + (dg * inverse) + 127) / 255;
        int b = ((sb * alpha) + (db * inverse) + 127) / 255;
        pixelData.putPixel(screenPos, (r << 24) | (g << 16) | (b << 8) | 0xFF);
    }
'''
if text.count(old_put) != 1:
    raise RuntimeError('painterly putPainterlyPixel block not found')
text = text.replace(old_put, new_put, 1)

old_coord = '''    private int dialogSourceCoord(int destination, int destinationLength, int sourceLength, int sourceCap) {
        if (destinationLength <= 1) return 0;
        int destinationCap = Math.min(sourceCap, Math.max(1, destinationLength / 2));
        if (destination < destinationCap) {
            return Math.min(sourceCap - 1, (destination * sourceCap) / destinationCap);
        }
        if (destination >= destinationLength - destinationCap) {
            int local = destination - (destinationLength - destinationCap);
            return Math.min(sourceLength - 1,
                    sourceLength - sourceCap + ((local * sourceCap) / destinationCap));
        }
        int centerLength = Math.max(1, sourceLength - (sourceCap * 2));
        return sourceCap + ((destination - destinationCap) % centerLength);
    }
'''
new_coord = '''    private int dialogSourceCoord(int destination, int destinationLength, int sourceLength, int sourceCap) {
        if (destinationLength <= 1) return sourceCap;
        int destinationCap = Math.min(sourceCap, Math.max(1, destinationLength / 3));
        if (destination < destinationCap) {
            return (destination * sourceCap) / destinationCap;
        }
        if (destination >= destinationLength - destinationCap) {
            int local = destination - (destinationLength - destinationCap);
            return Math.min(sourceLength - 1,
                    sourceLength - sourceCap + ((local * sourceCap) / destinationCap));
        }
        // Stretch the painted middle rather than wrapping/repeating it. Repeating a
        // tiny source strip created visible seams when the box was short or very wide.
        int sourceCenter = Math.max(1, sourceLength - (sourceCap * 2));
        int destinationCenter = Math.max(1, destinationLength - (destinationCap * 2));
        int local = destination - destinationCap;
        return sourceCap + Math.min(sourceCenter - 1, (local * sourceCenter) / destinationCenter);
    }
'''
if text.count(old_coord) != 1:
    raise RuntimeError('painterly dialogSourceCoord block not found')
text = text.replace(old_coord, new_coord, 1)

# Skip the transparent halo rows/columns from the generated source. The useful
# painted sign begins a few source pixels in from the alpha bounding box.
old_sample = '''                int sourcePixel = DIALOG_FRAME_PIXELS[(sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
'''
new_sample = '''                sourceX = Math.max(2, Math.min(DIALOG_FRAME_WIDTH - 3, sourceX));
                sourceY = Math.max(3, Math.min(DIALOG_FRAME_HEIGHT - 7, sourceY));
                int sourcePixel = DIALOG_FRAME_PIXELS[(sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
'''
if text.count(old_sample) != 1:
    raise RuntimeError('painterly source sampling block not found')
text = text.replace(old_sample, new_sample, 1)

# The original AGI popup only has five vertical pixels of padding. That is fine
# for a 1px red border but not for a painted wooden frame. Give graphical message
# windows nine pixels above/below the text, so 1-line, 2-line, and long messages
# all size naturally from their actual line count without touching the frame.
old_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.
        int windowDim = ((numLines * CHARHEIGHT + 2 * VMARGIN) << 8) | (maxLength * CHARWIDTH + 2 * HMARGIN);
        int windowPos = ((left * CHARWIDTH - HMARGIN) << 8) | (bottom * CHARHEIGHT + VMARGIN - 1);
'''
new_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.
        // Painterly graphical windows need extra vertical breathing room for the wood rails.
        int windowVMargin = state.graphicsMode ? 9 : VMARGIN;
        int windowDim = ((numLines * CHARHEIGHT + 2 * windowVMargin) << 8) | (maxLength * CHARWIDTH + 2 * HMARGIN);
        int windowPos = ((left * CHARWIDTH - HMARGIN) << 8) | (bottom * CHARHEIGHT + windowVMargin - 1);
'''
if text.count(old_dims) != 1:
    raise RuntimeError('TextGraphics window dimension block not found')
text = text.replace(old_dims, new_dims, 1)

text_graphics.write_text(text)
print('Painterly dialog layout v2 installed: opaque parchment, halo trimmed, stretched nine-slice, dynamic vertical padding')
