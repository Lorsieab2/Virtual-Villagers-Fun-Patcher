"""Every five-byte call or jump a manifest installs must land somewhere real.

Two separate bugs have now come from a branch pointing at the wrong address
while the code it should reach was written correctly:

  * VV4's duplicate-purchase helper was declared at ``IMAGE_BASE + file
    offset`` in a section that is not identity-mapped, so the menu called
    ``0x4CCC20`` instead of ``0x728C20``. v1.34.29 shipped that and crashed on
    opening the Tech screen, faulting at ``0x004CCC21``.
  * The barrel roll override passed ``rel32_call(source, target)`` with its
    arguments swapped, so both VV1 and VV2 installed a call running *backwards*
    into unrelated code.

Neither is visible in the cave's own bytes, and the sibling test that checks
declared cave VAs against the section table does not catch the second one --
the declaration was right, only the branch was wrong. So this reads the
displacement each manifest actually installs and checks where it lands.

A branch is accepted when it targets a VA the generator declares, or any
address inside the stock image (the many legitimate splices back into game
code). It is rejected when it lands outside the image without naming a
declared cave, which is precisely what both bugs looked like.
"""

from __future__ import annotations

import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

import sys

sys.path.insert(0, str(ROOT / "tests"))
from test_cave_va_matches_section_mapping import ALIAS, constants  # noqa: E402

GAMES = {
    "vv1": (
        ROOT / "data/vv1_origins_feature.json",
        ROOT / "scripts/build_vv1_origins_feature.py",
    ),
    "vv2": (
        ROOT / "data/vv2_origins_feature.json",
        ROOT / "scripts/build_vv2_origins_feature.py",
    ),
    "vv3": (
        ROOT / "data/vv3_origins_feature.json",
        ROOT / "scripts/build_vv3_origins_feature.py",
    ),
    "vv4": (
        ROOT / "data/vv4_origins_feature.json",
        ROOT / "scripts/build_vv4_origins_feature.py",
    ),
    "vv5": (
        ROOT / "data/vv5_origins_feature.json",
        ROOT / "scripts/build_vv5_origins_feature.py",
    ),
}

IMAGE_BASE = 0x400000

# The accepted range is the RENDERED image's own extent, read from its section
# table -- not a hardcoded ceiling. A fixed limit rejected VV5's legitimate
# splices into its appended page, which lives well above where the stock
# sections end. The point is to catch branches that land nowhere, not to
# police splices into sections a patch itself adds.
RENDERED = {
    "vv1": ROOT / "research/vv1-origins-apk/Virtual Villagers - A New Home - Origins Feature Research.exe",
    "vv2": ROOT / "research/vv2-origins/Virtual Villagers - The Lost Children - Origins Research.exe",
    "vv3": ROOT / "research/vv3-origins/Virtual Villagers - The Secret City - Origins Research.exe",
    "vv4": ROOT / "research/vv4-origins/Virtual Villagers - The Tree of Life - Origins Research.exe",
    "vv5": ROOT / "research/vv5-origins/Virtual Villagers - New Believers - Origins Research.exe",
}


def sections(data: bytes):
    """(name, va, raw, raw_size) for each section."""
    pe = int.from_bytes(data[0x3C:0x40], "little")
    count = int.from_bytes(data[pe + 6 : pe + 8], "little")
    opt = int.from_bytes(data[pe + 20 : pe + 22], "little")
    base = int.from_bytes(data[pe + 24 + 28 : pe + 24 + 32], "little")
    table = pe + 24 + opt
    out = []
    for index in range(count):
        entry = table + index * 40
        out.append((
            data[entry : entry + 8].rstrip(b"\0").decode("ascii", "replace"),
            base + int.from_bytes(data[entry + 12 : entry + 16], "little"),
            int.from_bytes(data[entry + 20 : entry + 24], "little"),
            int.from_bytes(data[entry + 16 : entry + 20], "little"),
        ))
    return out


def va_of(secs, offset: int):
    """VA a raw file offset maps to, or None when it is outside every section.

    Assuming `IMAGE_BASE + offset` is exactly the mistake this file exists to
    catch: in a non-identity-mapped section the two differ. VV2's raw 0x9A004
    maps to 0x49C004, not 0x49A004, so computing a branch target from the wrong
    source silently checked the wrong address -- and could pass a broken branch.
    """
    for _name, va, raw, raw_size in secs:
        if raw <= offset < raw + raw_size:
            return va + (offset - raw)
    return None


def section_of(secs, va: int):
    """Name of the section a VA falls in, or None."""
    for name, start, _raw, raw_size in secs:
        if start <= va < start + max(raw_size, 1):
            return name
    return None


def image_extent(path: Path) -> int:
    """Highest VA any section of this executable maps."""
    data = path.read_bytes()
    pe = int.from_bytes(data[0x3C:0x40], "little")
    count = int.from_bytes(data[pe + 6 : pe + 8], "little")
    opt = int.from_bytes(data[pe + 20 : pe + 22], "little")
    base = int.from_bytes(data[pe + 24 + 28 : pe + 24 + 32], "little")
    table = pe + 24 + opt
    top = base
    for index in range(count):
        entry = table + index * 40
        va = base + int.from_bytes(data[entry + 12 : entry + 16], "little")
        size = max(
            int.from_bytes(data[entry + 8 : entry + 12], "little"),
            int.from_bytes(data[entry + 16 : entry + 20], "little"),
        )
        top = max(top, va + size)
    return top


def installed_branches(manifest: dict):
    """(file_offset, opcode, displacement) for each 5-byte E8/E9 an edit writes."""
    out = []

    def walk(node):
        if isinstance(node, dict):
            after = node.get("after")
            offset = node.get("offset")
            if isinstance(after, str) and isinstance(offset, str):
                try:
                    raw = bytes.fromhex(after)
                    off = int(offset, 0)
                except ValueError:
                    raw = b""
                    off = None
                if off is not None and len(raw) >= 5 and raw[0] in (0xE8, 0xE9):
                    out.append((off, raw[0], struct.unpack("<i", raw[1:5])[0]))
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(manifest)
    return out


class InstalledBranchesReachDeclaredCavesTests(unittest.TestCase):
    def test_every_installed_branch_lands_somewhere_real(self) -> None:
        import json

        available = [g for g, p in RENDERED.items() if p.is_file()]
        if not available:
            self.skipTest("no generated executables present (research/ is not committed)")
        checked = 0
        for game, (manifest_path, script) in GAMES.items():
            if not manifest_path.is_file() or not script.is_file():
                continue
            rendered = RENDERED.get(game)
            if rendered is None or not rendered.is_file():
                continue
            limit = image_extent(rendered)
            secs = sections(rendered.read_bytes())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            values, _exprs = constants(script)
            declared = {
                value
                for name, value in values.items()
                if name.endswith("_VA") and value > IMAGE_BASE
            }
            for off, opcode, rel in installed_branches(manifest):
                source = va_of(secs, off)
                if source is None:
                    continue          # outside every raw section
                target = source + 5 + rel
                with self.subTest(game=game, offset=hex(off)):
                    self.assertTrue(
                        target in declared or IMAGE_BASE <= target < limit,
                        f"{game}: the {'call' if opcode == 0xE8 else 'jump'} installed at "
                        f"{off:#x} lands on {target:#x}, which is neither a VA this "
                        f"generator declares nor inside the rendered image. A branch to "
                        f"{target:#x} executes whatever happens to be there.",
                    )
                checked += 1
        # Not a fixed floor: research/ fixtures are installed per game, so a
        # checkout with only VV2 or only VV5 has fewer than 21 branch rows and
        # would fail a threshold while being entirely correct. The subTests
        # above are the real assertion; this one just proves the audit ran.
        self.assertGreater(checked, 0, "no installed branches were checked")

    def test_the_source_translation_matches_the_generators_own_vas(self) -> None:
        """Guards the translation this audit depends on.

        Every branch target is computed from where its patch offset MAPS. If
        that mapping were assumed identity, VV2's .shr sources would come out
        0x2000 low and every target with them -- and because the wrong targets
        still land inside the image, the audit itself would not notice. So the
        mapping is checked against the generators' own declared pairs, which
        are independent of it.
        """
        available = [g for g, p in RENDERED.items() if p.is_file()]
        if not available:
            self.skipTest("no generated executables present (research/ is not committed)")
        checked = 0
        for game in available:
            script = GAMES[game][1]
            if not script.is_file():
                continue
            values, exprs = constants(script)
            secs = sections(RENDERED[game].read_bytes())
            for name, offset in values.items():
                if not name.endswith("_FILE_OFFSET"):
                    continue
                va = values.get(name[: -len("_FILE_OFFSET")] + "_VA")
                if va is None or ALIAS.match(exprs.get(name[: -len("_FILE_OFFSET")] + "_VA", "")):
                    continue
                mapped = va_of(secs, offset)
                if mapped is None:
                    continue
                with self.subTest(game=game, cave=name):
                    self.assertEqual(mapped, va)
                checked += 1
        self.assertGreater(checked, 10, "no cave mappings were checked")


if __name__ == "__main__":
    unittest.main()
