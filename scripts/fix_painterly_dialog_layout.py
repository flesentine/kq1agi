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

# The original generated PNG has a very faint alpha halo outside the actual sign.
# At 320x200 AGI resolution those almost-transparent pixels were being stretched
# into long grey/green bars. Treat low-alpha fringe as empty, snap the painted
# sign/parchment to opaque, and retain only a narrow antialiased outer edge.
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
        // PAINTERLY_DIALOG_LAYOUT_V3: the original generated image contains a
        // low-alpha fringe well outside the visible frame. Do not let that fringe
        // blend the scene into the sign when the nine-slice is stretched.
        if (alpha < 64) return;
        if (alpha >= 180) alpha = 255;
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
        // Stretch the painted middle continuously. Tiling the center produced seams.
        int sourceCenter = Math.max(1, sourceLength - (sourceCap * 2));
        int destinationCenter = Math.max(1, destinationLength - (destinationCap * 2));
        int local = destination - destinationCap;
        return sourceCap + Math.min(sourceCenter - 1, (local * sourceCenter) / destinationCenter);
    }
'''
if text.count(old_coord) != 1:
    raise RuntimeError('painterly dialogSourceCoord block not found')
text = text.replace(old_coord, new_coord, 1)

# The uploaded original is 2048x682. Its actual visible painted frame begins near
# alpha y=79 and ends near y=596, but the raw alpha bbox extends roughly y=35..682.
# The embedded 128px copy therefore has about 3 junk rows above and 5-6 below.
# Rescale source coordinates through the useful area instead of CLAMPING them;
# clamping was duplicating a fringe row across the whole top/bottom of the popup.
old_sample = '''                int sourcePixel = DIALOG_FRAME_PIXELS[(sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
'''
new_sample = '''                int usefulTop = Math.min(3, Math.max(0, DIALOG_FRAME_HEIGHT - 1));
                int usefulBottom = Math.min(6, Math.max(0, DIALOG_FRAME_HEIGHT - usefulTop - 1));
                int usefulHeight = Math.max(1, DIALOG_FRAME_HEIGHT - usefulTop - usefulBottom);
                if (DIALOG_FRAME_HEIGHT > 1) {
                    sourceY = usefulTop + ((sourceY * (usefulHeight - 1)) / (DIALOG_FRAME_HEIGHT - 1));
                }
                int sourcePixel = DIALOG_FRAME_PIXELS[(sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
'''
if text.count(old_sample) != 1:
    raise RuntimeError('painterly source sampling block not found')
text = text.replace(old_sample, new_sample, 1)

# Size the popup around the text while leaving enough room for the generated
# wooden corners/rails. Horizontal padding also keeps letters off the side posts.
old_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.
        int windowDim = ((numLines * CHARHEIGHT + 2 * VMARGIN) << 8) | (maxLength * CHARWIDTH + 2 * HMARGIN);
        int windowPos = ((left * CHARWIDTH - HMARGIN) << 8) | (bottom * CHARHEIGHT + VMARGIN - 1);
'''
new_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.
        // Painterly graphical windows use the proportions of the original generated frame:
        // a larger fixed border around a text-sized parchment center.
        int windowVMargin = state.graphicsMode ? 13 : VMARGIN;
        int windowHMargin = state.graphicsMode ? 14 : HMARGIN;
        int windowDim = ((numLines * CHARHEIGHT + 2 * windowVMargin) << 8)
                | (maxLength * CHARWIDTH + 2 * windowHMargin);
        int windowPos = ((left * CHARWIDTH - windowHMargin) << 8)
                | (bottom * CHARHEIGHT + windowVMargin - 1);
'''
if text.count(old_dims) != 1:
    raise RuntimeError('TextGraphics window dimension block not found')
text = text.replace(old_dims, new_dims, 1)

text_graphics.write_text(text)
print('Painterly dialog layout v3 installed: original-art alpha fringe removed, source rescaled, corners preserved, text-fit padding')