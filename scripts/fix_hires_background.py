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

/** Loads optional modern replacement artwork for AGI rooms at its native source resolution. */
public final class RoomBackgrounds {
    private static final int AGI_SCREEN_HEIGHT = 200;
    private static final int AGI_PICTURE_TOP = 8;
    private static final int AGI_PICTURE_HEIGHT = 168;

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

        // Keep every source pixel. The replacement artwork represents the 168-line AGI
        // picture area, so only add the black top/bottom screen bands at the same scale.
        // There is no crop, intermediate 320px framebuffer, or arbitrary texture cap.
        int picturePixelWidth = source.getWidth();
        int picturePixelHeight = source.getHeight();
        int screenPixelHeight = Math.max(1, Math.round(
                picturePixelHeight * (AGI_SCREEN_HEIGHT / (float)AGI_PICTURE_HEIGHT)));
        int pictureTopPixels = Math.round(
                picturePixelHeight * (AGI_PICTURE_TOP / (float)AGI_PICTURE_HEIGHT));

        Pixmap screen = new Pixmap(picturePixelWidth, screenPixelHeight, Pixmap.Format.RGBA8888);
        screen.setBlending(Pixmap.Blending.None);
        screen.setColor(0, 0, 0, 1);
        screen.fill();

        // 1:1 copy: source pixels are never resampled before WebGL renders the scene.
        screen.drawPixmap(source, 0, 0, 0, pictureTopPixels, picturePixelWidth, picturePixelHeight);

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

print('Native-resolution room background patch applied successfully')
