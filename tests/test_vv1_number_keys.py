"""Numeric keys for A New Home, and the matching tip wording in The Lost Children.

The feature is a companion DLL of its own (native/vv1_number_keys) that
VVFP Startup.dll arms at game start and the Origins companion's native
village-update hook drives.  These guards pin:

  * the game facts the DLL relies on, each derived from the stock executables
    rather than restated -- The Lost Children's nine targets, A New Home's
    village-state global and its clamp's four screen margins;
  * that the keys are the game's own text characters (no SDL watch);
  * the glide (The Lost Children's 0x42F814) and the all-or-nothing install
    (the emulator runs both: tests/test_vv1_number_keys_like_vv2.py);
  * the Origins bridge (load from the executable's own directory, tick per
    frame, fail open);
  * the two manifests: every `before` is the stock bytes, the VV1 tip
    lands on a free id resolved by the game's own first-match lookup, and
    the VV2 rewording touches nothing but one pointer and dead storage.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

KEYS_C = ROOT / "native" / "vv1_number_keys" / "vv1_number_keys.c"
KEYS_DEF = ROOT / "native" / "vv1_number_keys" / "vv1_number_keys.def"
KEYS_DLL = ROOT / "assets" / "number_keys" / "VVFP VV1 Number Keys.dll"
ORIGINS_C = ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c"
ORIGINS_DLL = ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll"
VV1_MANIFEST = ROOT / "data" / "vv1_number_keys_feature.json"
VV2_MANIFEST = ROOT / "data" / "vv2_numeric_keys_tip_feature.json"
VV1_STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
VV2_STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - The Lost Children.exe"

TIP = b"You can zip around the island with your numeric keys.\0"


def _macro(text: str, name: str) -> int:
    match = re.search(r"^#define\s+%s\s+\(?(-?0x[0-9A-Fa-f]+|-?\d+)u?\)?" % re.escape(name), text, re.MULTILINE)
    assert match, name
    return int(match.group(1), 0)


def _function(text: str, opening: str) -> str:
    start = text.index(opening)
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start:index + 1]
    raise AssertionError("unterminated " + opening)


class NumberKeysDllTest(unittest.TestCase):
    """Static pins on the companion; tests/test_vv1_number_keys_like_vv2.py
    runs it, against The Lost Children's own code."""

    def setUp(self) -> None:
        self.text = KEYS_C.read_text(encoding="utf-8")

    def _mem(self, path: Path) -> bytes:
        import pefile
        return bytes(pefile.PE(str(path)).get_memory_mapped_image())

    def test_targets_are_the_lost_childrens_nine(self) -> None:
        """The Lost Children's handler 0x429E70: '1'..'9' index its jump table
        (0x42A0F0 bytes 0x11..0x19 -> cases 2..10 of 0x42A0AC), each case a
        `mov [esi+0x230], x; mov [esi+0x234], y`."""
        if not VV2_STOCK.is_file():
            self.skipTest("stock VV2 executable not present")
        mem = self._mem(VV2_STOCK)
        u32 = lambda va: struct.unpack_from("<I", mem, va - 0x400000)[0]
        index = mem[0x42A0F0 - 0x400000 + 0x11: 0x42A0F0 - 0x400000 + 0x1A]
        self.assertEqual(list(index), list(range(2, 11)))
        found = []
        for case in index:
            at = u32(0x42A0AC + 4 * case) - 0x400000
            self.assertEqual(mem[at:at + 2], b"\xc7\x86")
            self.assertEqual(struct.unpack_from("<I", mem, at + 2)[0], 0x230)
            self.assertEqual(mem[at + 10:at + 12], b"\xc7\x86")
            self.assertEqual(struct.unpack_from("<I", mem, at + 12)[0], 0x234)
            found.append(struct.unpack_from("<ii", mem, at + 6)[0:1] + struct.unpack_from("<i", mem, at + 16))
        xs = [int(v) for v in re.search(r"vv1_target_xs\[9\] = \{([^}]*)\}", self.text).group(1).replace("\n", " ").split(",")]
        ys = [int(v) for v in re.search(r"vv1_target_ys\[9\] = \{([^}]*)\}", self.text).group(1).replace("\n", " ").split(",")]
        self.assertEqual(found, list(zip(xs, ys)))

    def test_the_clamp_fields_are_a_new_homes_own(self) -> None:
        """A New Home's clamp after the scroll (0x423FD6) reads the four
        margins the glide predicts it with, against the same 0x690."""
        if not VV1_STOCK.is_file():
            self.skipTest("stock VV1 executable not present")
        mem = self._mem(VV1_STOCK)
        at = lambda va, n: mem[va - 0x400000: va - 0x400000 + n]
        self.assertEqual(at(0x423FD9, 6), b"\x8b\x86" + struct.pack("<I", 0x298))
        self.assertEqual(at(0x423FE8, 6), b"\x8b\xae" + struct.pack("<I", 0x2A0))
        self.assertEqual(at(0x423FEE, 5), b"\xb8" + struct.pack("<I", 0x690))
        self.assertEqual(at(0x424002, 6), b"\x8b\x86" + struct.pack("<I", 0x29C))
        self.assertEqual(at(0x42401B, 6), b"\x2b\x86" + struct.pack("<I", 0x2A4))
        self.assertEqual(at(0x41D516, 5), b"\xa1" + struct.pack("<I", 0x48AEDC))  # the state getter's global
        for name, value in (("VV1_MARGIN_LEFT_OFFSET", 0x298), ("VV1_MARGIN_TOP_OFFSET", 0x29C),
                            ("VV1_MARGIN_RIGHT_OFFSET", 0x2A0), ("VV1_MARGIN_BOTTOM_OFFSET", 0x2A4),
                            ("VV1_MAP_SPAN", 0x690), ("VV1_EDGE_X_OFFSET", 0x2D8), ("VV1_EDGE_Y_OFFSET", 0x2DC),
                            ("VV1_SCROLL_X_OFFSET", 8), ("VV1_SCROLL_Y_OFFSET", 0xC), ("VV1_PAN_DIVISOR", 10)):
            self.assertEqual(_macro(self.text, name), value, name)
        self.assertIn("(*(unsigned char **)0x0048AEDCu)", self.text)

    def test_no_sdl_watch_any_more(self) -> None:
        """Digits arrive as the game's own text characters, as in every later
        game; the SDL key watch (which ignored repeats and read the keypad by
        key code) is gone."""
        self.assertNotIn("SDL_AddEventWatch", self.text)
        self.assertNotIn("SDL2.dll", self.text)
        blob = KEYS_DLL.read_bytes()
        self.assertNotIn(b"SDL_AddEventWatch\0", blob)
        self.assertNotIn(b"SDL2.dll\0", blob)

    def test_glide_is_the_lost_childrens(self) -> None:
        step = _function(self.text, "static int vv1_glide_step(")
        self.assertIn("return cur + (target - cur) / VV1_PAN_DIVISOR", step)
        update = _function(self.text, "static int vv1_glide_update(")
        self.assertRegex(update, r"vv1_target_x == 0 && vv1_target_y == 0\)\s*\{\s*return 0;")
        self.assertIn("state != VV1_VILLAGE_STATE_PTR", update)
        self.assertRegex(update, r"\(vv1_target_x - x\) / VV1_PAN_DIVISOR == 0 && \(vv1_target_y - y\) / VV1_PAN_DIVISOR == 0")
        self.assertEqual(update.count("vv1_target_x = 0;"), 3, "two clamp edges and arrival")
        self.assertEqual(update.count("vv1_target_y = 0;"), 3)
        self.assertIn("return 1;", update)
        export = _function(self.text, "__declspec(dllexport) int __stdcall Vv1NumberKeysUpdate(")
        self.assertIn("vv1_glide_update(", export)
        tick = _function(self.text, "__declspec(dllexport) int __stdcall Vv1NumberKeysTick(")
        self.assertNotIn("vv1_glide_update", tick)

    def test_install_is_all_or_nothing_and_armed_at_startup(self) -> None:
        install = _function(self.text, "__declspec(dllexport) int __stdcall Vv1NumberKeysInstall(")
        self.assertLess(install.index("vv1_site_is_stock"), install.index("VirtualProtect"),
                        "every site is checked before any is written")
        self.assertIn("vv1_numkeys_installed = -1;", install)
        startup = _function(self.text, "__declspec(dllexport) void __stdcall VvfpStartup(")
        self.assertIn("game == VV1_GAME", startup)
        self.assertIn("Vv1NumberKeysInstall()", startup)
        dllmain = _function(self.text, "BOOL WINAPI DllMain(")
        self.assertNotIn("Install", dllmain)

    def test_exports_and_built_dll(self) -> None:
        deftext = KEYS_DEF.read_text(encoding="utf-8")
        for name in ("VvfpStartup=_VvfpStartup@8", "Vv1NumberKeysInstall=_Vv1NumberKeysInstall@0",
                     "Vv1NumberKeysTick=_Vv1NumberKeysTick@0", "Vv1NumberKeysUpdate=_Vv1NumberKeysUpdate@4"):
            self.assertIn(name, deftext)
        # The test seams ship only in the TEST build (VVFP_TEST).
        self.assertNotIn("Probe", deftext)
        testdef = KEYS_DEF.with_name("vv1_number_keys_test.def").read_text(encoding="utf-8")
        self.assertIn("Vv1NumberKeysProbeTarget=_Vv1NumberKeysProbeTarget@8", testdef)
        self.assertIn("Vv1NumberKeysProbeSite=_Vv1NumberKeysProbeSite@16", testdef)
        self.assertTrue(KEYS_DLL.is_file())
        blob = KEYS_DLL.read_bytes()
        for needle in (b"VvfpStartup\0", b"Vv1NumberKeysTick\0", b"Vv1NumberKeysUpdate\0",
                       struct.pack("<i", -150), struct.pack("<i", 1200), struct.pack("<i", 570),
                       bytes.fromhex("8B44242483C0E0"), bytes.fromhex("8B8EF0020000")):
            self.assertIn(needle, blob, needle)
        self.assertNotIn(b"Probe", blob)


class OriginsBridgeTest(unittest.TestCase):
    def test_bridge_loads_from_the_exe_directory_and_ticks_every_frame(self) -> None:
        text = ORIGINS_C.read_text(encoding="utf-8")
        bridge = _function(text, "static int vv1_numkeys_resolve(")
        # By full path in the patcher's folder, wide (native/shared/patcher_files.h).
        self.assertIn('vvfp_load_patcher_dll("VVFP VV1 Number Keys.dll")', bridge)
        self.assertNotIn("LoadLibrary", bridge, "never by bare name: the search path is not ours")
        self.assertIn('GetProcAddress(keys, "Vv1NumberKeysTick")', bridge)
        self.assertRegex(bridge, r"if\s*\(\s*vv1_numkeys_bridge_state\s*==\s*1\s*\)\s*\{\s*return\s+1;")
        self.assertRegex(bridge, r"keys\s*==\s*NULL\s*\)\s*\{\s*vv1_numkeys_bridge_state\s*=\s*-1;", "missing file: remembered, fail open")
        bridge_tick = _function(text, "static void vv1_numkeys_bridge(")
        self.assertIn("vv1_numkeys_tick();", bridge_tick)
        tick = _function(text, "void __stdcall Vv1MaskTick(")
        self.assertLess(tick.index("vv1_numkeys_bridge();"), tick.index("vv1_mask_prepare_slot()"),
                        "the bridge runs before any early return of the mask tick")
        blob = ORIGINS_DLL.read_bytes()
        self.assertIn(b"VVFP VV1 Number Keys.dll\0", blob)
        self.assertIn(b"Vv1NumberKeysTick\0", blob)


class ManifestTest(unittest.TestCase):
    def _load(self, path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    def _apply(self, stock: bytes, record: dict) -> bytes:
        out = bytearray(stock)
        for patch in record["patches"]:
            offset = int(patch["offset"], 16)
            before = bytes.fromhex(patch["before"])
            after = bytes.fromhex(patch["after"])
            self.assertEqual(out[offset:offset + len(before)], before, patch["purpose"][:60])
            self.assertEqual(len(after), len(before))
            out[offset:offset + len(after)] = after
        return bytes(out)

    @staticmethod
    def _vv1_lookup(mem: bytes, string_id: int):
        """The game's own 0x433880: first match over 629 twenty-byte records at 0x487208."""
        if not 0 <= string_id < 0x280:
            return None
        for k in range(0x275):
            va = 0x487208 + 20 * k
            rid, en = struct.unpack_from("<II", mem, va - 0x400000)
            if rid == string_id:
                end = mem.index(b"\0", en - 0x400000)
                return mem[en - 0x400000:end]
        return None

    def test_vv1_row_declares_its_companion_and_dependency(self) -> None:
        record = self._load(VV1_MANIFEST)
        self.assertEqual(record["game_id"], "vv1")
        self.assertEqual(record["dependencies"], ["vv1_enable_origins_exclusive_features"])
        companion = record["companion_files"]
        self.assertEqual([c["destination"] for c in companion], ["VVFP VV1 Number Keys.dll"])
        import hashlib
        self.assertEqual(companion[0]["sha256"], hashlib.sha256(KEYS_DLL.read_bytes()).hexdigest().upper())
        self.assertTrue(record.get("enabled", True) and record.get("catalog_enabled", True))

    def test_vv1_tip_lands_on_a_free_id_through_the_games_own_lookup(self) -> None:
        if not VV1_STOCK.is_file():
            self.skipTest("stock VV1 executable not present")
        import pefile
        record = self._load(VV1_MANIFEST)
        stock = VV1_STOCK.read_bytes()
        patched = self._apply(stock, record)
        pe = pefile.PE(data=patched)
        mem = bytes(pe.get_memory_mapped_image())
        stock_mem = bytes(pefile.PE(data=stock).get_memory_mapped_image())
        # the picker now draws 31 ids from 0x207
        self.assertEqual(mem[0x4256B0 - 0x400000: 0x4256B0 - 0x400000 + 2], b"\x6a\x1f")
        self.assertEqual(mem[0x4256BA - 0x400000: 0x4256BA - 0x400000 + 5], b"\x05\x07\x02\x00\x00")
        # every id the picker can produce resolves, distinctly, and the 31st is the new tip
        texts = [self._vv1_lookup(mem, 0x207 + n) for n in range(31)]
        self.assertTrue(all(texts))
        self.assertEqual(len(set(texts)), 31)
        self.assertEqual(texts[30], TIP.rstrip(b"\0"))
        self.assertEqual(texts[:30], [self._vv1_lookup(stock_mem, 0x207 + n) for n in range(30)], "the thirty stock tips are unchanged")
        # "points." kept its wording; its one reader asks for the new id
        self.assertEqual(self._vv1_lookup(mem, 0x27E), b"points.")
        self.assertIsNone(self._vv1_lookup(stock_mem, 0x27E), "0x27E was free in the stock game")
        self.assertEqual(mem[0x4346E7 - 0x400000: 0x4346E7 - 0x400000 + 5], b"\x68\x7e\x02\x00\x00")
        self.assertEqual(self._vv1_lookup(stock_mem, 0x225), b"points.")
        # the repurposed record was the demo message, and nothing in code asked for it
        self.assertEqual(self._vv1_lookup(stock_mem, 0x259), b"Demo version has a max population of 9!")
        self.assertIsNone(self._vv1_lookup(mem, 0x259))
        self.assertNotIn(b"\x68\x59\x02\x00\x00", stock_mem, "no push 0x259 anywhere: the demo record is dead")
        # the tip text and its storage never leave the demo record's own bytes
        span = mem[0x481240 - 0x400000: 0x481240 - 0x400000 + 92]
        self.assertTrue(span.startswith(TIP))
        self.assertEqual(span[len(TIP):], b"\0" * (92 - len(TIP)))
        self.assertEqual(mem[0x481240 - 0x400000 + 92: 0x481240 - 0x400000 + 96], stock_mem[0x481240 - 0x400000 + 92: 0x481240 - 0x400000 + 96])

    def test_vv2_rewording_touches_one_pointer_and_dead_storage_only(self) -> None:
        if not VV2_STOCK.is_file():
            self.skipTest("stock VV2 executable not present")
        import pefile
        record = self._load(VV2_MANIFEST)
        self.assertEqual(record["game_id"], "vv2")
        self.assertEqual(record.get("companion_files"), [])
        self.assertEqual(len(record["patches"]), 2)
        stock = VV2_STOCK.read_bytes()
        patched = self._apply(stock, record)
        mem = bytes(pefile.PE(data=patched).get_memory_mapped_image())
        stock_mem = bytes(pefile.PE(data=stock).get_memory_mapped_image())
        rid, en, de = struct.unpack_from("<III", mem, 0x498034 - 0x400000)
        self.assertEqual((rid, en, de), (0x312, 0x48F4DC, 0x483970))
        self.assertEqual(mem[en - 0x400000: en - 0x400000 + len(TIP)], TIP)
        self.assertEqual(stock_mem[0x4836F0 - 0x400000: 0x4836F0 - 0x400000 + 47], b"You can zip around the island with your keypad.")
        self.assertEqual(mem[0x4836F0 - 0x400000: 0x4836F0 - 0x400000 + 47], b"You can zip around the island with your keypad.", "the old text is left in place, merely unreferenced")
        drid, den, dde = struct.unpack_from("<III", stock_mem, 0x4964C8 - 0x400000)
        self.assertEqual((drid, den, dde), (0x35C, 0x48F510, 0x48F4DC), "the storage belongs to the demo record")
        self.assertNotIn(b"\x68\x5c\x03\x00\x00", stock_mem, "nothing pushes 0x35C: the demo record is dead")


if __name__ == "__main__":
    unittest.main()
