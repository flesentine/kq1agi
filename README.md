# King's Quest AGI — browser build

This repository turns the supplied King's Quest AGI files into a browser game using the open-source [AGILE](https://github.com/lanceewing/agile-gdx) interpreter.

The browser build is pinned to AGILE commit `81c42ba63b3b7f5fb260d282592681c097d46da9`, launches King's Quest automatically, and includes a browser-only visual background layer that keeps the original AGI priority/control data for walking and collision.

## Play

Once GitHub Pages is enabled for this repository, the game is published at:

**https://flesentine.github.io/kq1agi/**

The first visit may reload once. That is intentional: GitHub Pages does not provide the COOP/COEP response headers required by AGILE's `SharedArrayBuffer`, so this project uses `coi-serviceworker` to establish cross-origin isolation in the browser.

## Replace a room background with a real image

Put a PNG or JPEG in the `backgrounds/` folder using the AGI room number:

```text
backgrounds/room_001.jpg
backgrounds/room_002.png
backgrounds/room_003.jpg
```

Push to `main`. GitHub Actions rebuilds and redeploys the browser game automatically.

The engine still decodes Sierra's original AGI picture and preserves its priority/control maps. Only pixels that match the untouched room background are made transparent; Graham, animated objects, text, menus, scripts, collision, water/control lines, and room logic remain AGI-driven. This first pass works best when the replacement art keeps roughly the same layout as the original room.

Images may be any normal size. They are center-cropped to the corrected AGI display aspect ratio and scaled into the 320×168 AGI picture area.

## Repository layout

- `.github/workflows/pages.yml` — builds AGILE and deploys the static web app.
- `scripts/patch_agile.py` — applies the browser direct-launch and real-background engine changes.
- `game/kq1.zip.b64.part*` — the supplied game ZIP encoded as text chunks for repository transport.
- `backgrounds/` — optional real-image room replacements.
- `web/coi-serviceworker.js` — MIT-licensed COOP/COEP service-worker helper used on GitHub Pages.

## Upstream

AGILE is by Lance Ewing and contributors and is distributed under its upstream license. The build workflow fetches the pinned upstream source and publishes a copy of the upstream license with the deployed site.

`coi-serviceworker` is by Guido Zuidhof and contributors and is MIT licensed.
