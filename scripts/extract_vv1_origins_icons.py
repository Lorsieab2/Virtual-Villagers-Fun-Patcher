"""Extract only the eight VV1 Origins icons used by the desktop feature.

The source atlases come from the user-supplied Origins APK under the ignored
research tree. The small derived PNG/ICO files are the runtime assets.
"""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "research" / "vv1-origins-apk" / "extracted" / "assets"
OUTPUT = ROOT / "assets" / "origins"

WANTED = {
    "vv1_timewarpbutton.png": ("time-warp", 101),
    "vv1_islandeventbutton.png": ("island-event", 102),
    "vv1_barrelobabiesbutton.png": ("barrel-of-babies", 103),
    "vv1_techpointdoubler.png": ("tech-point-doubler", 104),
    "vv1_fooddoubler.png": ("food-point-doubler", 105),
    "vv1_grantyouth.png": ("grant-youth", 106),
    "vv1_masteryicon.png": ("grant-full-mastery", 107),
    "vv1_grantrunningicon.png": ("grant-running", 108),
}


def load_rgba4444(path: Path) -> Image.Image:
    data = path.read_bytes()
    if len(data) < 52:
        raise ValueError(f"Truncated PVR: {path}")
    header_size, height, width, _mips, _flags, data_size, bits = struct.unpack_from(
        "<7I", data
    )
    if header_size != 52 or bits != 16 or data_size != width * height * 2:
        raise ValueError(f"Unexpected Origins atlas format: {path}")
    values = struct.unpack_from(f"<{width * height}H", data, header_size)
    pixels = bytes(
        channel * 17
        for value in values
        for channel in (
            (value >> 12) & 0xF,
            (value >> 8) & 0xF,
            (value >> 4) & 0xF,
            value & 0xF,
        )
    )
    return Image.frombytes("RGBA", (width, height), pixels)


def load_entries(path: Path) -> dict[str, tuple[int, int, int, int]]:
    data = path.read_bytes()
    if len(data) < 5:
        raise ValueError(f"Truncated descriptor: {path}")
    count = struct.unpack_from("<H", data, 3)[0]
    position = 5
    entries: dict[str, tuple[int, int, int, int]] = {}
    for _ in range(count):
        name_length = data[position]
        position += 1
        name = data[position : position + name_length].decode("ascii").rstrip("\0")
        position += name_length
        _flags = data[position]
        x, y, width, height, _original_width, _original_height = (
            struct.unpack_from("<6H", data, position + 1)
        )
        position += 13
        entries[name] = (x, y, width, height)
    if position != len(data):
        raise ValueError(f"Unexpected descriptor tail in {path}")
    return entries


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    found: set[str] = set()
    for atlas_name in ("tp10", "tp17"):
        atlas = load_rgba4444(SOURCE / f"{atlas_name}.pvr")
        entries = load_entries(SOURCE / f"{atlas_name}.dat")
        for source_name, (output_name, icon_id) in WANTED.items():
            if source_name not in entries:
                continue
            x, y, width, height = entries[source_name]
            top = atlas.height - y - height
            icon = atlas.crop((x, top, x + width, top + height)).transpose(
                Image.Transpose.FLIP_TOP_BOTTOM
            )
            icon.thumbnail((64, 64), Image.Resampling.LANCZOS)
            canvas = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            canvas.alpha_composite(
                icon, ((64 - icon.width) // 2, (64 - icon.height) // 2)
            )
            canvas.save(OUTPUT / f"{icon_id}-{output_name}.png")
            canvas.save(
                OUTPUT / f"{icon_id}-{output_name}.ico",
                sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64)],
            )
            found.add(source_name)
    missing = set(WANTED) - found
    if missing:
        raise RuntimeError(f"Missing Origins atlas entries: {sorted(missing)}")
    print(f"Extracted {len(found)} Origins icons to {OUTPUT}")


if __name__ == "__main__":
    main()
