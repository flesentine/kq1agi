#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
PARTS_DIR = ROOT / "backgrounds_bin" / "room_001_q60"
OUT_DIR = ROOT / "backgrounds"
EXPECTED_SIZE = 264266
EXPECTED_SHA256 = "532f8c0f22ad5d5bc4c805568130bad159306f17b43d348fb7c2f0b59e18f594"
EXPECTED_DIMS = (1586, 992)
PART_RE = re.compile(r"^part_(\d+)([a-z]*)\.bin$")


def part_key(path: Path):
    match = PART_RE.match(path.name)
    if not match:
        raise ValueError(f"Unexpected part filename: {path.name}")
    return int(match.group(1)), match.group(2)


def jpeg_dimensions(data: bytes):
    if data[:2] != b"\xff\xd8":
        return None
    i = 2
    sof = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
           0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
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
            return width, height
        i += seglen
    return None


parts = sorted(PARTS_DIR.glob("part_*.bin"), key=part_key)
if not parts:
    raise SystemExit(f"No binary room parts found in {PARTS_DIR}")

print(f"assembling {len(parts)} verified binary parts")
data = b"".join(part.read_bytes() for part in parts)
actual_size = len(data)
actual_sha = hashlib.sha256(data).hexdigest()
actual_dims = jpeg_dimensions(data)

print(f"rebuilt room 1 q60: {actual_size:,} bytes, sha256={actual_sha}, dimensions={actual_dims}")
if actual_size != EXPECTED_SIZE:
    raise SystemExit(f"Room 1 q60 size mismatch: expected {EXPECTED_SIZE:,}, got {actual_size:,}")
if actual_sha != EXPECTED_SHA256:
    raise SystemExit(f"Room 1 q60 SHA-256 mismatch: expected {EXPECTED_SHA256}, got {actual_sha}")
if actual_dims != EXPECTED_DIMS:
    raise SystemExit(f"Room 1 q60 dimensions mismatch: expected {EXPECTED_DIMS}, got {actual_dims}")
if data[-2:] != b"\xff\xd9":
    raise SystemExit("Room 1 q60 JPEG is missing its end marker")

OUT_DIR.mkdir(parents=True, exist_ok=True)
for old in OUT_DIR.glob("room_001_hires.*"):
    old.unlink()
out = OUT_DIR / "room_001_hires.jpg"
out.write_bytes(data)
print(f"verified q60 test image -> {out.relative_to(ROOT)}")
