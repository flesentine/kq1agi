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

image = Image.open(asset).convert('RGBA')
if image.size != (160, 41):
    raise RuntimeError(f'expected clean painterly frame 160x41, got {image.size}')

pixels = []
for r, g, b, a in image.getdata():
    a = 0 if a < 128 else 255
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

frame_constants = f'''    private static final int UNASSIGNED = -1;\n\n    // PAINTERLY_DIALOG_FRAME CLEAN_V4: pre-cleaned hard-alpha nine-slice.\n    private static final int DIALOG_FRAME_WIDTH = {image.width};\n    private static final int DIALOG_FRAME_HEIGHT = {image.height};\n    private static final int DIALOG_FRAME_CAP_X = 9;\n    private static final int DIALOG_FRAME_CAP_Y = 8;\n    private static final int[] DIALOG_FRAME_PIXELS = {{\n{pixel_literal}\n    }};\n'''
text = text.replace(marker, frame_constants, 1)

method_start = text.index('    public void drawWindow(TextWindow textWindow) {')
method_end_marker = '''    /**\n     * Checks if there is a text window currently open.\n'''
method_end = text.index(method_end_marker, method_start)

replacement = r'''    private int dialogSourceCoord(int destination, int destinationLength, int sourceLength, int sourceCap) {
        if (destinationLength <= 1) return sourceCap;

        int destinationCap = Math.min(sourceCap, Math.max(1, destinationLength / 2));

        if (destination < destinationCap) {
            return Math.min(sourceCap - 1,
                    (destination * sourceCap) / destinationCap);
        }

        if (destination >= destinationLength - destinationCap) {
            int local = destination - (destinationLength - destinationCap);
            return Math.min(sourceLength - 1,
                    sourceLength - sourceCap + ((local * sourceCap) / destinationCap));
        }

        int sourceCenter = Math.max(1, sourceLength - (sourceCap * 2));
        int destinationCenter = Math.max(1, destinationLength - (destinationCap * 2));
        int local = destination - destinationCap;
        return sourceCap + Math.min(sourceCenter - 1,
                (local * sourceCenter) / destinationCenter);
    }

    private void putPainterlyPixel(int screenX, int screenY, int sourcePixel) {
        if (screenX < 0 || screenX >= 320 || screenY < 0 || screenY >= 200) return;

        int alpha = sourcePixel & 0xFF;
        if (alpha < 128) return;

        int screenPos = (screenY * 320) + screenX;
        pixelData.putPixel(screenPos, (sourcePixel & 0xFFFFFF00) | 0xFF);
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
                int sourcePixel = DIALOG_FRAME_PIXELS[
                        (sourceY * DIALOG_FRAME_WIDTH) + sourceX];
                putPainterlyPixel(startX + x, startY + y, sourcePixel);
            }
        }
    }

    /** Draws AGI glyphs without painting white 8x8 cells over the parchment. */
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
        textWindow = (textWindow == null ? openWindow : textWindow);

        if (textWindow != null) {
            int backgroundRGBA8888 = EgaPalette.colours[textWindow.backgroundColour];
            int borderRGBA8888 = EgaPalette.colours[textWindow.borderColour];
            int startScreenPos = (textWindow.y() * 320) + textWindow.x();
            int screenYAdd = (320 - textWindow.width());
            boolean painterlyWindow = state.graphicsMode && textWindow.textLines != null;

            boolean storeBackPixels = (textWindow.backPixels == null);
            if (storeBackPixels) {
                textWindow.backPixels = new int[textWindow.width() * textWindow.height()];
            }

            int backPixelsPos = 0;
            for (int y = 0, screenPos = startScreenPos;
                    y < textWindow.height();
                    y++, screenPos += screenYAdd) {

                for (int x = 0; x < textWindow.width(); x++, screenPos++) {
                    if (storeBackPixels) {
                        textWindow.backPixels[backPixelsPos++] = pixelData.getPixel(screenPos);
                    }

                    if (!painterlyWindow) {
                        pixelData.putPixel(screenPos, backgroundRGBA8888);
                    }
                }
            }

            if (painterlyWindow) {
                drawPainterlyWindow(textWindow);
            }
            else {
                for (int x = 0, screenPos = (startScreenPos + 320 + 2);
                        x < (textWindow.width() - 4); x++, screenPos++) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                }

                for (int x = 0,
                        screenPos = (startScreenPos + (320 * (textWindow.height() - 2) + 2));
                        x < (textWindow.width() - 4); x++, screenPos++) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                }

                for (int y = 1, screenPos = (startScreenPos + 640 + 2);
                        y < (textWindow.height() - 2); y++, screenPos += 320) {
                    pixelData.putPixel(screenPos, borderRGBA8888);
                    pixelData.putPixel(screenPos + 1, borderRGBA8888);
                    pixelData.putPixel(screenPos + (textWindow.width() - 6), borderRGBA8888);
                    pixelData.putPixel(screenPos + (textWindow.width() - 5), borderRGBA8888);
                }
            }

            if (textWindow.textLines != null) {
                for (int i = 0; i < textWindow.textLines.length; i++) {
                    int textX = (textWindow.left << 3);
                    int textY = ((textWindow.top + i) << 3);

                    if (painterlyWindow) {
                        drawWindowStringTransparent(
                                textWindow.textLines[i], textX, textY, textWindow.textColour);
                    }
                    else {
                        drawString(pixelData, textWindow.textLines[i], textX, textY,
                                textWindow.textColour, textWindow.backgroundColour);
                    }
                }
            }

            if (textWindow.aniObj != null) {
                textWindow.aniObj.draw();
                textWindow.aniObj.show(pixelData);
            }
        }
    }

'''
text = text[:method_start] + replacement + text[method_end:]

old_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.\n        int windowDim = ((numLines * CHARHEIGHT + 2 * VMARGIN) << 8) | (maxLength * CHARWIDTH + 2 * HMARGIN);\n        int windowPos = ((left * CHARWIDTH - HMARGIN) << 8) | (bottom * CHARHEIGHT + VMARGIN - 1);\n'''
new_dims = '''        // Compute window size and position and put them into the appropriate bytes of the words.\n        // PAINTERLY_DIALOG_CLEAN_V4 keeps the generated rails/corners visible.\n        int windowVMargin = state.graphicsMode ? 10 : VMARGIN;\n        int windowHMargin = state.graphicsMode ? 14 : HMARGIN;\n        int windowDim = ((numLines * CHARHEIGHT + 2 * windowVMargin) << 8)\n                | (maxLength * CHARWIDTH + 2 * windowHMargin);\n        int windowPos = ((left * CHARWIDTH - windowHMargin) << 8)\n                | (bottom * CHARHEIGHT + windowVMargin - 1);\n'''
if text.count(old_dims) != 1:
    raise RuntimeError('TextGraphics window dimension block not found')
text = text.replace(old_dims, new_dims, 1)

text_graphics.write_text(text)
print('Painterly AGI dialog CLEAN_V4 installed: opaque parchment, preserved wood rails/corners, dynamic AGI text')
