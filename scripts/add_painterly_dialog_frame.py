#!/usr/bin/env python3
from pathlib import Path
import sys

from PIL import Image

if len(sys.argv) != 2:
    raise SystemExit('usage: add_painterly_dialog_frame.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()
repo_root = Path(__file__).resolve().parents[1]
asset = repo_root / 'assets/ui/painterly_dialog_frame.png'
if not asset.exists():
    raise RuntimeError(f'missing painterly dialog asset: {asset}')

# Compile a small copy of the generated oil-painted frame directly into the core
# renderer. This avoids any browser-worker asset-loading problems while preserving
# the original transparent PNG in the repo for future art changes.
image = Image.open(asset).convert('RGBA')
bbox = image.getchannel('A').getbbox()
if bbox:
    image = image.crop(bbox)
source_w = 128
source_h = max(1, round(image.height * source_w / image.width))
image = image.resize((source_w, source_h), Image.Resampling.LANCZOS)

pixels = []
for r, g, b, a in image.getdata():
    pixels.append((r << 24) | (g << 16) | (b << 8) | a)

rows = []
for i in range(0, len(pixels), 8):
    rows.append('        ' + ', '.join(f'0x{value:08X}' for value in pixels[i:i+8]))
pixel_literal = ',\n'.join(rows)

text_graphics = root / 'core/src/main/java/com/agifans/agile/TextGraphics.java'
text = text_graphics.read_text()

marker = '    private static final int UNASSIGNED = -1;\n'
if text.count(marker) != 1:
    raise RuntimeError('TextGraphics constant marker not found')

frame_constants = f'''    private static final int UNASSIGNED = -1;\n\n    // PAINTERLY_DIALOG_FRAME: generated oil-painted nine-slice source. The corners\n    // are preserved while the edge/interior strips repeat to fit dynamic AGI text.\n    private static final int DIALOG_FRAME_WIDTH = {source_w};\n    private static final int DIALOG_FRAME_HEIGHT = {source_h};\n    private static final int DIALOG_FRAME_CAP_X = 9;\n    private static final int DIALOG_FRAME_CAP_Y = 7;\n    private static final int[] DIALOG_FRAME_PIXELS = {{\n{pixel_literal}\n    }};\n'''
text = text.replace(marker, frame_constants, 1)

method_start = text.index('    public void drawWindow(TextWindow textWindow) {')
method_end_marker = '''    /**\n     * Checks if there is a text window currently open.\n'''
method_end = text.index(method_end_marker, method_start)

replacement = r'''    private int dialogSourceCoord(int destination, int destinationLength, int sourceLength, int sourceCap) {
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

    private void putPainterlyPixel(int screenX, int screenY, int sourcePixel) {
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

    private void drawPainterlyWindow(TextWindow textWindow) {
        int destinationWidth = textWindow.width();
        int destinationHeight = textWindow.height();
        int startX = textWindow.x();
        int startY = textWindow.y();

        for (int y = 0; y < destinationHeight; y++) {
            int sourceY = dialogSourceCoord(y, destinationHeight,
                    DIALOG_FRAME_HEIGHT, DIALOG_FRAME_CAP_Y);
            for (int x = 0; x < destinationWidth; x++) {
                int sourceX = dialogSourceCoord(x, destinationWidth,
                        DIALOG_FRAME_WIDTH, DIALOG_FRAME_CAP_X);
                int sourcePixel = DIALOG_FRAME_PIXELS[(sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
            }
        }
    }

    /** Draws AGI glyphs without painting white 8x8 cells over the oil texture. */
    private void drawWindowCharTransparent(byte charNum, int x, int y, int foregroundColour) {
        int colour = EgaPalette.colours[foregroundColour & 0x0F];
        for (int byteNum = 0; byteNum < 8; byteNum++) {
            int fontByte = (IBM_BIOS_FONT[(((int)charNum & 0xFF) << 3) + byteNum] & 0xFF);
            for (int bytePos = 7; bytePos >= 0; bytePos--) {
                if ((fontByte & (1 << bytePos)) != 0) {
                    int px = x + (7 - bytePos);
                    int py = y + byteNum;
                    if (px >= 0 && px < 320 && py >= 0 && py < 200) {
                        pixelData.putPixel((py * 320) + px, colour);
                    }
                }
            }
        }
    }

    private void drawWindowStringTransparent(String value, int x, int y, int foregroundColour) {
        byte[] textBytes = StringUtils.getBytesFromString(value);
        for (int i = 0; i < textBytes.length; i++) {
            drawWindowCharTransparent(textBytes[i], x + (i * 8), y, foregroundColour);
        }
    }

    public void drawWindow(TextWindow textWindow) {
        // Defaults to the currently open window if one was not provided by the caller.
        textWindow = (textWindow == null ? openWindow : textWindow);

        if (textWindow != null) {
            int backgroundRGBA8888 = EgaPalette.colours[textWindow.backgroundColour];
            int borderRGBA8888 = EgaPalette.colours[textWindow.borderColour];
            int startScreenPos = (textWindow.y() * 320) + textWindow.x();
            int screenYAdd = (320 - textWindow.width());
            boolean painterlyWindow = state.graphicsMode && textWindow.textLines != null;

            // The first time DrawWindow is invoked for a TextWindow, save what was
            // behind it. The painterly frame is then composited over those pixels.
            boolean storeBackPixels = (textWindow.backPixels == null);
            if (storeBackPixels) textWindow.backPixels = new int[textWindow.width() * textWindow.height()];

            int backPixelsPos = 0;
            for (int y = 0, screenPos = startScreenPos; y < textWindow.height(); y++, screenPos += screenYAdd) {
                for (int x = 0; x < textWindow.width(); x++, screenPos++) {
                    if (storeBackPixels) textWindow.backPixels[backPixelsPos++] = pixelData.getPixel(screenPos);
                    if (!painterlyWindow) pixelData.putPixel(screenPos, backgroundRGBA8888);
                }
            }

            if (painterlyWindow) {
                drawPainterlyWindow(textWindow);
            }
            else {
                // Original AGI box remains the fallback for non-graphics/text-screen windows.
                for (int x = 0, screenPos = (startScreenPos + 320 + 2); x < (textWindow.width() - 4); x++, screenPos++) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                }
                for (int x = 0, screenPos = (startScreenPos + (320 * (textWindow.height() - 2) + 2)); x < (textWindow.width() - 4); x++, screenPos++) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                }
                for (int y = 1, screenPos = (startScreenPos + 640 + 2); y < (textWindow.height() - 2); y++, screenPos += 320) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                    pixelData.putPixel(screenPos + 1, borderRGBA8888);
                    pixelData.putPixel(screenPos + (textWindow.width() - 6), borderRGBA8888);
                    pixelData.putPixel(screenPos + (textWindow.width() - 5), borderRGBA8888);
                }
            }

            // Dynamic AGI text stays exactly as before, but on painterly windows its
            // character backgrounds are transparent so the oil texture remains visible.
            if (textWindow.textLines != null) {
                for (int i = 0; i < textWindow.textLines.length; i++) {
                    int textX = (textWindow.left << 3);
                    int textY = ((textWindow.top + i) << 3);
                    if (painterlyWindow) {
                        drawWindowStringTransparent(textWindow.textLines[i], textX, textY, textWindow.textColour);
                    }
                    else {
                        drawString(pixelData, textWindow.textLines[i], textX, textY,
                                textWindow.textColour, textWindow.backgroundColour);
                    }
                }
            }

            // Embedded AnimatedObject support remains intact for inventory descriptions.
            if (textWindow.aniObj != null) {
                textWindow.aniObj.draw();
                textWindow.aniObj.show(pixelData);
            }
        }
    }

'''

text = text[:method_start] + replacement + text[method_end:]
text_graphics.write_text(text)

print(f'Painterly AGI dialog frame installed: {source_w}x{source_h} embedded nine-slice, transparent dynamic text')

# Refine the generated frame for AGI-scale rendering: trim alpha halo artifacts,
# make the parchment opaque, and give dynamic messages enough vertical padding.
import runpy
runpy.run_path(str(Path(__file__).with_name('fix_painterly_dialog_layout.py')), run_name='__main__')
