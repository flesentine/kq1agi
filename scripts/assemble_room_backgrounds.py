#!/usr/bin/env python3
from pathlib import Path
import base64
import hashlib
import struct

ROOT = Path(__file__).resolve().parents[1]
PARTS_ROOT = ROOT / "backgrounds_parts"
OUT_DIR = ROOT / "backgrounds"
EXPECTED = (1586, 992)


def image_info(data: bytes):
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "png", width, height

    if data[:2] == b"\xff\xd8":
        i = 2
        sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
        while i + 4 <= len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            while i < len(data) and data[i] == 0xFF:
                i += 1
            if i >= len(data):
                break
            marker = data[i]
            i += 1
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                continue
            if i + 2 > len(data):
                break
            seglen = struct.unpack(">H", data[i:i + 2])[0]
            if seglen < 2 or i + seglen > len(data):
                break
            if marker in sof and seglen >= 7:
                height, width = struct.unpack(">HH", data[i + 3:i + 7])
                return "jpg", width, height
            i += seglen
    return None


candidates = []
for folder in sorted(PARTS_ROOT.glob("room_001*")):
    if not folder.is_dir():
        continue
    parts = sorted(folder.glob("part_*.b64"))
    if not parts:
        continue
    try:
        encoded = "".join(p.read_text().strip() for p in parts)
        data = base64.b64decode(encoded, validate=True)
    except Exception as exc:
        print(f"skip {folder.name}: invalid base64 ({exc})")
        continue

    info = image_info(data)
    if info is None:
        print(f"skip {folder.name}: decoded bytes are not a complete PNG/JPEG")
        continue
    ext, width, height = info
    print(f"candidate {folder.name}: {width}x{height}, {len(data):,} bytes, {ext}")
    if (width, height) == EXPECTED:
        candidates.append((len(data), folder.name, ext, data))

if not candidates:
    raise SystemExit(f"No complete {EXPECTED[0]}x{EXPECTED[1]} room-1 image found in {PARTS_ROOT}")

# Every candidate has the exact requested pixel dimensions. Prefer the largest encoded
# source so we keep the highest-quality version that was staged in the repository.
candidates.sort(reverse=True, key=lambda item: item[0])
size, source_name, ext, data = candidates[0]
OUT_DIR.mkdir(parents=True, exist_ok=True)
for old in OUT_DIR.glob("room_001_hires.*"):
    old.unlink()
out = OUT_DIR / f"room_001_hires.{ext}"
out.write_bytes(data)
sha = hashlib.sha256(data).hexdigest()
print(f"selected {source_name} -> {out.relative_to(ROOT)} ({size:,} bytes, sha256={sha})")
