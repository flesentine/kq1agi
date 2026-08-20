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
import com.badlogic.gdx.graphics.Texture;

/** Loads optional modern replacement artwork for AGI rooms at native source resolution. */
public final class RoomBackgrounds {
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

        // Do not copy, pad, crop, or resample the replacement art here.
        // Upload the source image directly as the WebGL texture so every source pixel
        // survives until the final on-screen draw.
        Texture texture = new Texture(file);
        texture.setFilter(Texture.TextureFilter.Linear, Texture.TextureFilter.Linear);
        textures.put(room, texture);
        return texture;
    }

    private static FileHandle find(int room) {
        String number = room < 10 ? "00" + room : (room < 100 ? "0" + room : String.valueOf(room));
        String[] extensions = new String[] { "png", "jpg", "jpeg" };

        // Cache-busting high-resolution art always wins when present.
        for (String extension : extensions) {
            FileHandle hires = Gdx.files.internal("backgrounds/room_" + number + "_hires." + extension);
            if (hires.exists()) {
                return hires;
            }
        }

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
new = '''            // AGI's picture area is screen rows 8..175 from the top. In libGDX's
            // bottom-left coordinate system that is y=24 with a height of 168.
            // Draw the native-resolution texture directly into that rectangle.
            batch.draw(
                    roomBackground,
                    0, 24, ADJUSTED_WIDTH, 168,
                    0, 0, roomBackground.getWidth(), roomBackground.getHeight(),
                    false, false);'''
if text.count(old) != 1:
    raise RuntimeError('Patched GameScreen room-background draw block not found')
game_screen.write_text(text.replace(old, new))

print('Direct native-resolution room background patch applied successfully')
