#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: fix_hires_background.py /path/to/agile-gdx')

root = Path(sys.argv[1]).resolve()

room_backgrounds = root / 'core/src/main/java/com/agifans/agile/RoomBackgrounds.java'
room_backgrounds.write_text(r'''package com.agifans.agile;

import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;

import com.badlogic.gdx.Gdx;
import com.badlogic.gdx.files.FileHandle;
import com.badlogic.gdx.graphics.Pixmap;
import com.badlogic.gdx.graphics.Texture;

/** Loads optional modern replacement artwork for AGI rooms without reducing it to AGI resolution. */
public final class RoomBackgrounds {
    private static final int AGI_SCREEN_WIDTH = 320;
    private static final int AGI_SCREEN_HEIGHT = 200;
    private static final int AGI_PICTURE_TOP = 8;
    private static final int AGI_PICTURE_HEIGHT = 168;

    // This is the aspect ratio the source image should have before AGI's historical
    // non-square-pixel correction squeezes 320 logical pixels to the displayed width.
    private static final float DISPLAY_PICTURE_RATIO = 266.0f / 168.0f;

    // Keeps browser/GPU memory sane while still providing far more detail than the
    // original 320-pixel AGI framebuffer. A 2048-wide background is plenty for the
    // browser view and remains compatible with conservative WebGL texture limits.
    private static final int MAX_TEXTURE_WIDTH = 2048;

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

        // Centre-crop the source to the corrected on-screen picture ratio.
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

        // Preserve the source's real detail. The old implementation always created a
        // 320x200 texture, which destroyed the photo before WebGL ever displayed it.
        // Here the picture area stays near source resolution and only the logical AGI
        // pixel-aspect correction is pre-applied horizontally.
        int maxPictureHeight = Math.round(
                MAX_TEXTURE_WIDTH * (AGI_PICTURE_HEIGHT / (float)AGI_SCREEN_WIDTH));
        int picturePixelHeight = Math.max(1, Math.min(sh, maxPictureHeight));
        int screenPixelWidth = Math.max(1, Math.round(
                picturePixelHeight * (AGI_SCREEN_WIDTH / (float)AGI_PICTURE_HEIGHT)));
        int screenPixelHeight = Math.max(1, Math.round(
                picturePixelHeight * (AGI_SCREEN_HEIGHT / (float)AGI_PICTURE_HEIGHT)));
        int pictureTopPixels = Math.round(
                picturePixelHeight * (AGI_PICTURE_TOP / (float)AGI_PICTURE_HEIGHT));

        Pixmap screen = new Pixmap(screenPixelWidth, screenPixelHeight, Pixmap.Format.RGBA8888);
        screen.setBlending(Pixmap.Blending.None);
        screen.setFilter(Pixmap.Filter.BiLinear);
        screen.setColor(0, 0, 0, 1);
        screen.fill();
        screen.drawPixmap(
                source,
                sx, sy, sw, sh,
                0, pictureTopPixels, screenPixelWidth, picturePixelHeight);

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

game_screen = root / 'core/src/main/java/com/agifans/agile/GameScreen.java'
text = game_screen.read_text()
old = '''            batch.draw(
                    roomBackground,
                    0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                    0, 0, AGI_SCREEN_WIDTH, AGI_SCREEN_HEIGHT,
                    false, false);'''
new = '''            batch.draw(
                    roomBackground,
                    0, 0, ADJUSTED_WIDTH, ADJUSTED_HEIGHT,
                    0, 0, roomBackground.getWidth(), roomBackground.getHeight(),
                    false, false);'''
if text.count(old) != 1:
    raise RuntimeError('Patched GameScreen room-background draw block not found')
game_screen.write_text(text.replace(old, new))

print('High-resolution room background patch applied successfully')
