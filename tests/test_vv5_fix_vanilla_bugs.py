"""New Believers: "Fix Vanilla Bugs" (vv5_fix_vanilla_bugs) -- the gold dust sound and the eDemo text id.

The row's earlier fixes have their own tests (tests/test_every_default_name_can_be_chosen.py, the
"%" in names tests, tests/test_vanilla_likes_panel.py).  This file covers the two added in v1.35.70:

1. The gold dust pouring sound.  Sound table entry 0x98 (0x4CE508) names its file
   "gold_dust_pour .ogg" (0x49AA20) -- a stray space before the dot -- while the game ships
   Sounds\\gold_dust_pour.ogg, so the sound never loads (its "lightning .ogg" is right: the file it ships has
   that very name) and the game's own log says
   "ldwSoundFx Missing File ->gold_dust_pour .ogg" (seen in the owner's own ldwLog.txt).  The fix
   rewrites the 20-byte string in place.  No other game has this sound, and no file name in any of the
   five executables has the same kind of typo (checked below).

2. "String Table (sm.xml) malformed near id=\"eDemo\"" at every start.  The string table loader
   (0x450A60) looks every id of its 1409-entry table up in Assets\\sm.xml; entry 0x302 (0x4D7530) asks
   for "eDemo", which New Believers' sm.xml calls "eTipDemo" (the demo version's "max population of 9"
   message; The Tree of Life's sm.xml still has "eDemo").  The entry keeps its own built-in text, so the
   player never saw a difference; only the log line.  The fix points the entry's name at a new
   "eTipDemo" string written into the zero tail of .rdata's last page (0x4C5FF0; the section's raw data,
   which the loader maps with that page, runs to 0x4C6000).
"""
from __future__ import annotations

import functools
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    EXPERIMENTAL_FUN_PATCH_IDS,
    PatcherError,
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

try:
    import pefile
except ImportError:  # pragma: no cover
    pefile = None

FEATURE_ID = "vv5_fix_vanilla_bugs"
STOCK_DIR = ROOT / "research" / "stock-executables"
STOCK = STOCK_DIR / "Virtual Villagers - New Believers.exe"
EXES = {
    "vv1": "Virtual Villagers - A New Home.exe",
    "vv2": "Virtual Villagers - The Lost Children.exe",
    "vv3": "Virtual Villagers - The Secret City.exe",
    "vv4": "Virtual Villagers - The Tree of Life.exe",
    "vv5": "Virtual Villagers - New Believers.exe",
}
MODES = ("stock", "collection_progression", "immediate_fixed")
IMAGE_BASE = 0x400000
NO_STOCK = "stock executables are not available"

GOLD = (0x9AA20, b"gold_dust_pour .ogg\0", b"gold_dust_pour.ogg\0\0")
TIP_DEMO = (0xC5FF0, b"\0" * 9, b"eTipDemo\0")
EDEMO_ENTRY = (0xD7534, bytes.fromhex("508A4A00"), bytes.fromhex("F05F4C00"))
NEW_FIXES = (GOLD, TIP_DEMO, EDEMO_ENTRY)
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_details_name_identity import name_identity_fixes  # noqa: E402
SOUND_ENTRY = 0x4CE508          # {0x98, name, file, 0}
TEXT_ENTRY = 0x4D7530           # {0x302, name, built-in text, 0}
TEXT_TABLE = (0x4D31F0, 1409)   # 16-byte entries, as the loader 0x450A60 walks them (0x581)
# A file name with a space right before its extension, as "gold_dust_pour .ogg".
SPACED = re.compile(rb"[!-~]* \.(?:ogg|wav|png|jpg|jpeg|gif|bmp|xml|dat|swf)\0", re.I)


@functools.lru_cache(maxsize=None)
def _vv5():
    return next(build for build in load_builds() if build.id == "vv5")


@functools.lru_cache(maxsize=None)
def _render(mode: str, ids: tuple[str, ...]) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv5(), mode, list(ids))
    return bytes(rendered)


def _mapped(data: bytes) -> bytes:
    return pefile.PE(data=data).get_memory_mapped_image()


def _cstring(image: bytes, va: int) -> bytes:
    at = va - IMAGE_BASE
    return image[at:image.index(b"\0", at)]


def _others() -> tuple[str, ...]:
    return tuple(p.id for p in load_public_fun_patches()
                 if p.game_id == "vv5" and p.id != FEATURE_ID and p.id not in EXPERIMENTAL_FUN_PATCH_IDS)


class RowTests(unittest.TestCase):
    def test_the_row_carries_both_fixes_and_says_so(self):
        row = next(p for p in load_fun_patches() if p.id == FEATURE_ID).raw
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        pinned = [(int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"]))
                  for p in row["patches"]]
        identity = list(name_identity_fixes("vv5"))     # tests/test_details_name_identity.py
        self.assertEqual(pinned[-len(identity):], identity)
        self.assertEqual(pinned[-len(identity) - 3:-len(identity)], list(NEW_FIXES))
        self.assertEqual(len({off for off, _, _ in pinned}), len(pinned))
        description = row["description"]
        self.assertIn("gold_dust_pour .ogg", description)
        self.assertIn("eTipDemo", description)
        self.assertTrue(description.endswith("**Needs no other patch.**"))

    def test_default_on(self):
        from vv_fun_patcher_gui import DEFAULT_OFF_FUN_PATCH_IDS, SELECT_ALL_OFF_FUN_PATCH_IDS
        self.assertNotIn(FEATURE_ID, DEFAULT_OFF_FUN_PATCH_IDS)
        self.assertNotIn(FEATURE_ID, SELECT_ALL_OFF_FUN_PATCH_IDS)


@unittest.skipUnless(pefile is not None and STOCK.is_file(), NO_STOCK)
class StockTests(unittest.TestCase):
    def setUp(self):
        self.raw = STOCK.read_bytes()
        self.image = _mapped(self.raw)

    def test_the_stock_bytes(self):
        for offset, before, _after in NEW_FIXES:
            self.assertEqual(self.raw[offset:offset + len(before)], before)
        pe = pefile.PE(str(STOCK), fast_load=True)
        for offset, _before, _after in NEW_FIXES:
            self.assertEqual(pe.get_offset_from_rva(offset), offset)   # file offset == RVA in VV5

    def test_the_sound_entry_names_the_misspelt_file(self):
        entry = struct.unpack_from("<4I", self.image, SOUND_ENTRY - IMAGE_BASE)
        self.assertEqual(entry[0], 0x98)
        self.assertEqual(entry[2], IMAGE_BASE + GOLD[0])
        self.assertEqual(_cstring(self.image, entry[2]), b"gold_dust_pour .ogg")

    def test_the_text_entry_asks_for_edemo_with_its_own_text(self):
        entry = struct.unpack_from("<4I", self.image, TEXT_ENTRY - IMAGE_BASE)
        self.assertEqual(entry[0], 0x302)
        self.assertEqual(_cstring(self.image, entry[1]), b"eDemo")
        self.assertEqual(_cstring(self.image, entry[2]), b"Demo version has a max population of 9!")
        self.assertEqual(entry[3], 0)
        start, count = TEXT_TABLE
        names = [_cstring(self.image, struct.unpack_from("<I", self.image, start - IMAGE_BASE + 16 * i + 4)[0])
                 for i in range(count)]
        self.assertEqual(names.count(b"eDemo"), 1)
        self.assertNotIn(b"eTipDemo", names)
        self.assertNotIn(b"eTipDemo\0", self.raw)

    def test_the_new_string_lies_in_mapped_read_only_data(self):
        pe = pefile.PE(str(STOCK), fast_load=True)
        rdata = next(s for s in pe.sections if s.Name.rstrip(b"\0") == b".rdata")
        va = TIP_DEMO[0]
        end_of_page = (rdata.VirtualAddress + rdata.Misc_VirtualSize + 0xFFF) & ~0xFFF
        self.assertGreaterEqual(va, rdata.VirtualAddress + rdata.Misc_VirtualSize)
        self.assertLessEqual(va + len(TIP_DEMO[2]), end_of_page)
        self.assertLessEqual(va + len(TIP_DEMO[2]), rdata.VirtualAddress + rdata.SizeOfRawData)
        self.assertEqual(rdata.PointerToRawData, rdata.VirtualAddress)
        self.assertFalse(rdata.Characteristics & 0x80000000)        # not writable

    def test_no_other_file_name_in_any_game_has_the_same_typo(self):
        for game, name in EXES.items():
            path = STOCK_DIR / name
            if not path.is_file():
                self.skipTest(NO_STOCK)
            data = path.read_bytes()
            spaced = [m.start() for m in SPACED.finditer(data)]
            # 0x9A9D0 "lightning .ogg" (eSound_LightningStrike) is spelt exactly as New Believers' own
            # file, Sounds\lightning .ogg, space included, so it loads; only the gold dust name is wrong.
            self.assertEqual(spaced, [0x9A9D0, GOLD[0]] if game == "vv5" else [], game)


@unittest.skipUnless(pefile is not None and STOCK.is_file(), NO_STOCK)
class RenderTests(unittest.TestCase):
    def _check(self, data: bytes):
        for offset, _before, after in NEW_FIXES:
            self.assertEqual(data[offset:offset + len(after)], after, hex(offset))
        image = _mapped(data)
        sound = struct.unpack_from("<4I", image, SOUND_ENTRY - IMAGE_BASE)
        self.assertEqual(_cstring(image, sound[2]), b"gold_dust_pour.ogg")
        text = struct.unpack_from("<4I", image, TEXT_ENTRY - IMAGE_BASE)
        self.assertEqual(_cstring(image, text[1]), b"eTipDemo")
        self.assertEqual(_cstring(image, text[2]), b"Demo version has a max population of 9!")
        self.assertNotIn(b"gold_dust_pour .ogg", data)

    def test_alone_in_every_mode(self):
        for mode in MODES:
            with self.subTest(mode=mode):
                without = _render(mode, ())
                for offset, before, _after in NEW_FIXES:
                    self.assertEqual(without[offset:offset + len(before)], before)
                self._check(_render(mode, (FEATURE_ID,)))

    def test_with_every_other_patch_in_every_mode(self):
        others = _others()
        self.assertGreater(len(others), 10)
        for mode in MODES:
            with self.subTest(mode=mode):
                self._check(_render(mode, others + (FEATURE_ID,)))

    def test_with_256_villagers(self):
        experimental = tuple(p.id for p in load_public_fun_patches()
                             if p.game_id == "vv5" and p.id in EXPERIMENTAL_FUN_PATCH_IDS)
        self.assertTrue(experimental)
        rendered = 0
        for mode in MODES:
            try:
                data = _render(mode, _others() + experimental + (FEATURE_ID,))
            except PatcherError:
                continue
            self._check(data)
            rendered += 1
        self.assertGreater(rendered, 0)

    def test_without_the_row_nothing_changes_there(self):
        for mode in MODES:
            data = _render(mode, _others())
            for offset, before, _after in NEW_FIXES:
                self.assertEqual(data[offset:offset + len(before)], before, (mode, hex(offset)))


if __name__ == "__main__":
    unittest.main()
