#!/usr/bin/env python3
from pathlib import Path
import json
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: patch_agile.py /path/to/agile-gdx')

ROOT = Path(sys.argv[1]).resolve()


def p(rel: str) -> Path:
    return ROOT / rel


def read(rel: str) -> str:
    return p(rel).read_text()


def write(rel: str, text: str) -> None:
    path = p(rel)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def replace_exact(rel: str, old: str, new: str, expected: int = 1) -> None:
    text = read(rel)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f'{rel}: expected {expected} occurrences, found {count}: {old[:90]!r}')
    write(rel, text.replace(old, new))


# Keep the browser build focused on King's Quest. The commercial game data is imported by the user once and then stored in the browser.
games_path = p('assets/data/games.json')
games = json.loads(games_path.read_text())
kq1 = next((app for app in games.get('apps', []) if str(app.get('gameId', '')).upper() == 'KQ1'), None)
if not kq1:
    raise RuntimeError('Could not find KQ1 in assets/data/games.json')
kq1['name'] = "King's Quest"
kq1['displayName'] = "King's Quest"
kq1['filePath'] = ''
kq1['fileType'] = 'UNK'
games['apps'] = [kq1]
games_path.write_text(json.dumps(games, indent=2) + '\n')

# After the first KQ1 import, launch immediately instead of making the user click the game a second time.
rel = 'core/src/main/java/com/agifans/agile/HomeScreen.java'
text = read(rel)
old = '                                showGamePage(appConfigItem, false);'
if text.count(old) != 1:
    raise RuntimeError('HomeScreen import-complete launch site not found')
text = text.replace(old, old + '\n                                processGameSelection(appConfigItem);')
write(rel, text)

# GitHub Pages is hosted under /kq1agi/. Ignore the URL path and launch KQ1 immediately.
rel = 'html/src/main/java/com/agifans/agile/gwt/GwtLauncher.java'
text = read(rel)
start = text.index('        Map<String, String> argsMap = new HashMap<>();')
end = text.index('        GwtDialogHandler gwtDialogHandler', start)
text = text[:start] + (
    '        Map<String, String> argsMap = new HashMap<>();\n'
    '        argsMap.put("uri", "kings-quest");\n\n'
) + text[end:]
text = text.replace('createPreloaderPanel("/agile_title.png")', 'createPreloaderPanel("agile_title.png")')
write(rel, text)

# Make the web worker and navigation paths relative to the GitHub Pages project path.
rel = 'html/src/main/java/com/agifans/agile/gwt/GwtAgileRunner.java'
text = read(rel)
method_start = text.index('    public void start(AppConfigItem appConfigItem) {')
url_start = text.index('        String newURL = "";', method_start)
url_end = text.index('        // Set title for the browser tab.', url_start)
text = text[:url_start] + '        // Keep the current GitHub Pages URL stable.\n' + text[url_end:]
text = text.replace('worker = Worker.create("/worker/worker.nocache.js");', 'worker = Worker.create("worker/worker.nocache.js");')
text = text.replace(
    '        super(userInput, wavePlayer, savedGameStore, pixelData, variableData);\n    }',
    '        super(userInput, wavePlayer, savedGameStore, pixelData, variableData);\n'
    '        ((GwtPixelData)pixelData).setVariableData(variableData);\n'
    '    }'
)
text = text.replace(
    '        JavaScriptObject pixelDataSAB = gwtPixelData.getSharedArrayBuffer();\n',
    '        JavaScriptObject pixelDataSAB = gwtPixelData.getSharedArrayBuffer();\n'
    '        JavaScriptObject backgroundDataSAB = gwtPixelData.getBackgroundSharedArrayBuffer();\n'
)
text = text.replace(
    '                variableSAB,\n                pixelDataSAB));',
    '                variableSAB,\n                pixelDataSAB,\n                backgroundDataSAB));'
)
text = text.replace(
    '            JavaScriptObject variableSAB,\n            JavaScriptObject pixelDataSAB)/*-{',
    '            JavaScriptObject variableSAB,\n            JavaScriptObject pixelDataSAB,\n            JavaScriptObject backgroundDataSAB)/*-{'
)
text = text.replace(
    '            variableSAB: variableSAB,\n            pixelDataSAB: pixelDataSAB\n',
    '            variableSAB: variableSAB,\n            pixelDataSAB: pixelDataSAB,\n            backgroundDataSAB: backgroundDataSAB\n'
)
clear_start = text.index('    private void clearUrl() {')
clear_end = text.index('    @Override\n    public void reset()', clear_start)
text = text[:clear_start] + '    private void clearUrl() {\n        // Keep the Pages project URL unchanged.\n    }\n    \n' + text[clear_end:]
write(rel, text)

# Share a second pixel buffer containing only the original AGI room background.
rel = 'html/src/main/java/com/agifans/agile/worker/AgileWebWorker.java'
text = read(rel)
text = text.replace(
    '                JavaScriptObject pixelDataSAB = getNestedObject(eventObject, "pixelDataSAB");\n',
    '                JavaScriptObject pixelDataSAB = getNestedObject(eventObject, "pixelDataSAB");\n'
    '                JavaScriptObject backgroundDataSAB = getNestedObject(eventObject, "backgroundDataSAB");\n'
)
text = text.replace('pixelData = new GwtPixelData(pixelDataSAB);', 'pixelData = new GwtPixelData(pixelDataSAB, backgroundDataSAB);')
text = text.replace('this.importScript("/opfs-saved-games.js");', 'this.importScript("../opfs-saved-games.js");')
write(rel, text)

# Add an optional hook to capture the untouched room background before animated objects are drawn.
rel = 'core/src/main/java/com/agifans/agile/PixelData.java'
text = read(rel)
needle = '    public abstract void pixelCopy(int[] rgba888Src, int agiScreenIndex, int agiScreenLength);\n'
if needle not in text:
    raise RuntimeError('PixelData.pixelCopy signature not found')
text = text.replace(
    needle,
    needle + '\n'
    '    /**\n'
    '     * Captures the current untouched visual room background. Platforms that do not\n'
    '     * need a separate background layer may ignore this hook.\n'
    '     */\n'
    '    public void captureBackground(int[] rgba888Src, int agiScreenIndex, int agiScreenLength) {\n'
    '        // Optional platform hook.\n'
    '    }\n'
)
write(rel, text)

# Capture the background after the AGI picture is decoded, but before actors are composited.
rel = 'core/src/main/java/com/agifans/agile/Commands.java'
text = read(rel)
old = '        updatePixelArrays();\n\n        state.drawObjects();'
count = text.count(old)
if count != 2:
    raise RuntimeError(f'Commands: expected 2 background capture sites, found {count}')
text = text.replace(
    old,
    '        updatePixelArrays();\n\n'
    '        pixelData.captureBackground(\n'
    '                state.visualPixels, (8 * state.pictureRow) * 320, state.visualPixels.length);\n\n'
    '        state.drawObjects();'
)
write(rel, text)

# Extend GWT pixel transport with a shared original-background buffer and alpha-mask it only
# when a replacement room image exists. The interpreter still sees untouched AGI pixels.
rel = 'html/src/main/java/com/agifans/agile/gwt/GwtPixelData.java'
text = read(rel)
text = text.replace(
    'import com.agifans.agile.PixelData;\n',
    'import com.agifans.agile.Defines;\n'
    'import com.agifans.agile.PixelData;\n'
    'import com.agifans.agile.RoomBackgrounds;\n'
    'import com.agifans.agile.VariableData;\n'
)
text = text.replace(
    '    private Uint8ClampedArray pixelArray;\n',
    '    private Uint8ClampedArray pixelArray;\n\n'
    '    private Uint8ClampedArray backgroundPixelArray;\n\n'
    '    private VariableData variableData;\n'
)
text = text.replace(
    '    public GwtPixelData(JavaScriptObject sharedArrayBuffer) {\n'
    '        pixelArray = createPixelArray(sharedArrayBuffer);',
    '    public GwtPixelData(JavaScriptObject sharedArrayBuffer, JavaScriptObject backgroundSharedArrayBuffer) {\n'
    '        pixelArray = createPixelArray(sharedArrayBuffer);\n'
    '        backgroundPixelArray = createPixelArray(backgroundSharedArrayBuffer);'
)
text = text.replace(
    '    public native JavaScriptObject getSharedArrayBuffer()/*-{\n'
    '        var pixelArray = this.@com.agifans.agile.gwt.GwtPixelData::pixelArray;\n'
    '        return pixelArray.buffer;\n'
    '    }-*/;\n',
    '    public native JavaScriptObject getSharedArrayBuffer()/*-{\n'
    '        var pixelArray = this.@com.agifans.agile.gwt.GwtPixelData::pixelArray;\n'
    '        return pixelArray.buffer;\n'
    '    }-*/;\n\n'
    '    public native JavaScriptObject getBackgroundSharedArrayBuffer()/*-{\n'
    '        var backgroundPixelArray = this.@com.agifans.agile.gwt.GwtPixelData::backgroundPixelArray;\n'
    '        return backgroundPixelArray.buffer;\n'
    '    }-*/;\n'
)
text = text.replace(
    '        pixelArray = createPixelArray(width, height);\n',
    '        pixelArray = createPixelArray(width, height);\n'
    '        backgroundPixelArray = createPixelArray(width, height);\n'
)
constructor_marker = '    @Override\n    public void putPixel(int agiScreenIndex, int rgba8888Colour) {'
text = text.replace(
    constructor_marker,
    '    public void setVariableData(VariableData variableData) {\n'
    '        this.variableData = variableData;\n'
    '    }\n\n' + constructor_marker
)
save_marker = '    @Override\n    public void savePixels() {'
text = text.replace(
    save_marker,
    '    @Override\n'
    '    public void captureBackground(int[] rgba888Src, int agiScreenIndex, int agiScreenLength) {\n'
    '        for (int i = 0; i < backgroundPixelArray.length(); i++) {\n'
    '            backgroundPixelArray.set(i, 0);\n'
    '        }\n'
    '        int index = agiScreenIndex * 4;\n'
    '        for (int srcPos = 0; srcPos < agiScreenLength; srcPos++) {\n'
    '            int rgba8888Colour = rgba888Src[srcPos];\n'
    '            int paletteColour = egaToPaletteMap.getOrDefault(rgba8888Colour, rgba8888Colour);\n'
    '            backgroundPixelArray.set(index++, (paletteColour >> 24) & 0xFF);\n'
    '            backgroundPixelArray.set(index++, (paletteColour >> 16) & 0xFF);\n'
    '            backgroundPixelArray.set(index++, (paletteColour >> 8) & 0xFF);\n'
    '            backgroundPixelArray.set(index++, paletteColour & 0xFF);\n'
    '        }\n'
    '    }\n\n' + save_marker
)
text = text.replace(
    '    public void clearPixels() {\n'
    '        for (int index = 0; index < pixelArray.length(); index++) {\n'
    '            pixelArray.set(index, 0);\n'
    '        }\n'
    '    }',
    '    public void clearPixels() {\n'
    '        for (int index = 0; index < pixelArray.length(); index++) {\n'
    '            pixelArray.set(index, 0);\n'
    '            backgroundPixelArray.set(index, 0);\n'
    '        }\n'
    '    }'
)
text = text.replace(
    '    public void updatePixmap(Pixmap pixmap) {\n'
    '        setImageData(pixelArray, pixmap.getWidth(), pixmap.getHeight(), pixmap.getContext());\n'
    '    }',
    '    public void updatePixmap(Pixmap pixmap) {\n'
    '        int room = (variableData != null)? variableData.getVar(Defines.CURROOM) : -1;\n'
    '        if ((room >= 0) && RoomBackgrounds.hasBackground(room)) {\n'
    '            setImageDataWithBackgroundMask(\n'
    '                    pixelArray, backgroundPixelArray, pixmap.getWidth(), pixmap.getHeight(), pixmap.getContext());\n'
    '        } else {\n'
    '            setImageData(pixelArray, pixmap.getWidth(), pixmap.getHeight(), pixmap.getContext());\n'
    '        }\n'
    '    }'
)
native_marker = '    @Override\n    protected void updatePixelsForNewPalette() {'
mask_method = r'''    private native static void setImageDataWithBackgroundMask(
            ArrayBufferView pixels, ArrayBufferView backgroundPixels, int width, int height, Context2d ctx)/*-{
        var imgData = ctx.createImageData(width, height);
        var data = imgData.data;

        for (var i = 0, len = width * height * 4; i < len; i += 4) {
            var sameAsBackground =
                (backgroundPixels[i + 3] != 0) &&
                ((pixels[i] & 0xff) == (backgroundPixels[i] & 0xff)) &&
                ((pixels[i + 1] & 0xff) == (backgroundPixels[i + 1] & 0xff)) &&
                ((pixels[i + 2] & 0xff) == (backgroundPixels[i + 2] & 0xff)) &&
                ((pixels[i + 3] & 0xff) == (backgroundPixels[i + 3] & 0xff));

            data[i] = pixels[i] & 0xff;
            data[i + 1] = pixels[i + 1] & 0xff;
            data[i + 2] = pixels[i + 2] & 0xff;
            data[i + 3] = sameAsBackground ? 0 : (pixels[i + 3] & 0xff);
        }
        ctx.putImageData(imgData, 0, 0);
    }-*/;

'''
if native_marker not in text:
    raise RuntimeError('GwtPixelData updatePixelsForNewPalette marker not found')
text = text.replace(native_marker, mask_method + native_marker)
write(rel, text)

# A small cross-platform room-image cache. GWT preloads files under assets/, so standard
# PNG/JPEG files can be used without browser-specific asynchronous image handling.
write('core/src/main/java/com/agifans/agile/RoomBackgrounds.java', r'''package com.agifans.agile;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.Texture;

/** Loads optional modern replacement artwork for AGI rooms. */
public final class RoomBackgrounds {
    private static final int SCREEN_WIDTH = 320;
    private static final int SCREEN_HEIGHT = 200;
    private static final int PICTURE_TOP = 8;
    private static final int PICTURE_HEIGHT = 168;
    private static final float DISPLAY_PICTURE_RATIO = 266.0f / 168.0f;

    private static final Map<Integer, Texture> textures = new HashMap<Integer, Texture>();
    private static final Set<Integer> missing = new HashSet<Integer>();

    private RoomBackgrounds() {
    }

    public static boolean hasBackground(int room) {
        return getTexture(room) != null;
    }

    public static Texture getTexture(int room) {
        if (textures.containsKey(room)) {
            return textures.get(room);
        }
        if (missing.contains(room)) {
            return null;
        }

        FileHandle file = find(room);
        if (file == null) {
            missing.add(room);
            return null;
        }

        Pixmap source = new Pixmap(file);
        Pixmap screen = new Pixmap(SCREEN_WIDTH, SCREEN_HEIGHT, Pixmap.Format.RGBA8888);
        screen.setBlending(Pixmap.Blending.None);
        screen.setColor(0, 0, 0, 1);
        screen.fill();

        int sx = 0;
        int sy = 0;
        int sw = source.getWidth();
        int sh = source.getHeight();
        float sourceRatio = sw / (float)sh;

        if (sourceRatio > DISPLAY_PICTURE_RATIO) {
            int croppedWidth = Math.round(sh * DISPLAY_PICTURE_RATIO);
            sx = Math.max(0, (sw - croppedWidth) / 2);
            sw = Math.min(sw, croppedWidth);
        } else if (sourceRatio < DISPLAY_PICTURE_RATIO) {
            int croppedHeight = Math.round(sw / DISPLAY_PICTURE_RATIO);
            sy = Math.max(0, (sh - croppedHeight) / 2);
            sh = Math.min(sh, croppedHeight);
        }

        screen.drawPixmap(source, sx, sy, sw, sh, 0, PICTURE_TOP, SCREEN_WIDTH, PICTURE_HEIGHT);
        Texture texture = new Texture(screen);
        texture.setFilter(Texture.TextureFilter.Linear, Texture.TextureFilter.Linear);
        source.dispose();
        screen.dispose();
        textures.put(room, texture);
        return texture;
    }

    private static FileHandle find(int room) {
        String number = room < 10 ? "00" + room : (room < 100 ? "0" + room : String.valueOf(room));
        String[] extensions = new String[] { "png", "jpg", "jpeg" };
        for (String extension : extensions) {
            FileHandle file = Gdx.files.internal("backgrounds/room_" + number + "." + extension);
            if (file.exists()) {
                return file;
            }
        }
        return null;
    }
}
''')

# Draw the replacement image first, then the alpha-masked AGI foreground over it.
rel = 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = read(rel)
old = '''        batch.setProjectionMatrix(camera.combined);
        batch.disableBlending();
        batch.begin();
        Color c = batch.getColor();
        batch.setColor(c.r, c.g, c.b, 1f);
        batch.draw(
                getDrawScreen(), 
                0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT, 
                false, false);
        batch.end();
'''
new = '''        batch.setProjectionMatrix(camera.combined);
        Color c = batch.getColor();
        batch.setColor(c.r, c.g, c.b, 1f);

        Texture roomBackground = RoomBackgrounds.getTexture(
                agileRunner.getVariableData().getVar(Defines.CURROOM));
        if (roomBackground != null) {
            batch.disableBlending();
            batch.begin();
            batch.draw(
                    roomBackground,
                    0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                    0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,
                    false, false);
            batch.end();
            batch.enableBlending();
        } else {
            batch.disableBlending();
        }

        batch.begin();
        batch.draw(
                getDrawScreen(),
                0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,
                false, false);
        batch.end();
'''
if old not in text:
    raise RuntimeError('GameScreen render block not found')
write(rel, text.replace(old, new))

# GitHub Pages-safe root page. COI service worker supplies the headers SharedArrayBuffer needs.
index_path = p('html/webapp/index.html')
index_path.write_text(r'''<!DOCTYPE html>
<html>
<head>
  <title>King's Quest - Browser AGI</title>
  <meta name="description" content="King's Quest running directly in a browser with AGILE and optional modern room backgrounds." />
  <meta http-equiv="content-type" content="text/html; charset=UTF-8">
  <meta id="gameViewport" name="viewport" content="width=device-width, initial-scale=1.0, interactive-widget=resizes-content">
  <meta name="theme-color" content="#000000">
  <link href="styles.css" rel="stylesheet" type="text/css">
  <style>
    html, body { margin: 0; width: 100%; height: 100%; background: #000; overflow: hidden; }
    #boot-message { position: fixed; inset: 0; display: grid; place-items: center; color: #ddd; font: 16px system-ui, sans-serif; }
  </style>
</head>
<body>
<div align="center" id="embed-html"></div>
<div id="boot-message">Preparing King's Quest…</div>
<script src="coi-serviceworker.js"></script>
<script>
(function () {
  if (!window.crossOriginIsolated) return;
  document.getElementById('boot-message').style.display = 'none';
  const scripts = ['dialog.js', 'jszip.min.js', 'html/html.nocache.js'];
  for (const src of scripts) {
    const s = document.createElement('script');
    s.src = src;
    s.async = false;
    document.body.appendChild(s);
  }
})();

function handleMouseDown(evt) {
  evt.preventDefault();
  evt.stopPropagation();
  window.focus();
}
function handleMouseUp(evt) {
  evt.preventDefault();
  evt.stopPropagation();
}
document.addEventListener('contextmenu', event => event.preventDefault());
document.getElementById('embed-html').addEventListener('mousedown', handleMouseDown, false);
document.getElementById('embed-html').addEventListener('mouseup', handleMouseUp, false);
</script>
</body>
</html>
''')

print('AGILE browser patch applied successfully')
