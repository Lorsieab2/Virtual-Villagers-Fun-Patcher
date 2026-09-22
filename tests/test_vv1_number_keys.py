"""Numeric keys for A New Home, and the matching tip wording in The Lost Children.

The feature is a companion DLL of its own (native/vv1_number_keys) that the
Origins companion loads and ticks once per frame.  These guards pin:

  * the game facts the DLL relies on, each derived from the stock executable
    rather than restated -- the village-state global, the scroll pair, and
    the four clamp bounds the game's own map-click handler applies;
  * the SDL event layout and the key classification;
  * the glide (signed truncating tenth-of-remaining step, driven by the
    native village update, including while a villager is carried);
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
    def setUp(self) -> None:
        self.text = KEYS_C.read_text(encoding="utf-8")

    def test_game_facts_come_from_the_map_click_handler(self) -> None:
        """Positive control on the executable: the clamp at 0x429C8E..0x429CCF
        and the getter's global are exactly what the DLL encodes."""
        if not VV1_STOCK.is_file():
            self.skipTest("stock VV1 executable not present")
        blob = VV1_STOCK.read_bytes()
        import pefile
        pe = pefile.PE(str(VV1_STOCK))
        mem = bytes(pe.get_memory_mapped_image())
        def at(va, n):
            return mem[va - 0x400000: va - 0x400000 + n]
        # cmp ecx, -205 / mov [eax+8], -205 / cmp ecx, 885 / mov [eax+8], 885
        self.assertEqual(at(0x429C8E, 6), b"\x81\xf9" + struct.pack("<i", -205))
        self.assertEqual(at(0x429C9F, 6), b"\x81\xf9" + struct.pack("<i", 885))
        self.assertEqual(at(0x429CB4, 3), b"\x83\xf8\xfb")            # cmp eax, -5
        self.assertEqual(at(0x429CC8, 5), b"\x3d" + struct.pack("<i", 1205))  # cmp eax, 1205
        self.assertEqual(at(0x429C73, 3), b"\x89\x41\x08")            # mov [ecx+8], eax  (x)
        self.assertEqual(at(0x429C85, 3), b"\x89\x50\x0c")            # mov [eax+0xC], edx (y)
        self.assertEqual(at(0x429D44, 5), b"\xe8" + struct.pack("<i", 0x41D500 - 0x429D49))  # call getter
        self.assertEqual(at(0x41D516, 5), b"\xa1" + struct.pack("<I", 0x48AEDC))            # mov eax,[0x48AEDC]
        self.assertEqual(_macro(self.text, "VV1_SCROLL_X_MIN"), -205)
        self.assertEqual(_macro(self.text, "VV1_SCROLL_X_MAX"), 885)
        self.assertEqual(_macro(self.text, "VV1_SCROLL_Y_MIN"), -5)
        self.assertEqual(_macro(self.text, "VV1_SCROLL_Y_MAX"), 1205)
        self.assertEqual(_macro(self.text, "VV1_SCROLL_X_OFFSET"), 8)
        self.assertEqual(_macro(self.text, "VV1_SCROLL_Y_OFFSET"), 0xC)
        self.assertIn("(*(unsigned char **)0x0048AEDCu)", self.text)

    def test_sdl_layout_and_key_classification(self) -> None:
        self.assertEqual(_macro(self.text, "VV1_SDL_KEYDOWN"), 0x300)
        self.assertEqual(_macro(self.text, "VV1_SDL_KEY_REPEAT_OFFSET"), 13)
        self.assertEqual(_macro(self.text, "VV1_SDL_KEY_SYM_OFFSET"), 20)
        self.assertEqual(_macro(self.text, "VV1_SDL_KEY_MOD_OFFSET"), 24)
        self.assertEqual(_macro(self.text, "VV1_SDLK_KP_1"), 0x40000059)
        self.assertEqual(_macro(self.text, "VV1_SDLK_KP_9"), 0x40000061)
        digit = _function(self.text, "static int vv1_numkeys_digit(")
        self.assertRegex(digit, r"e\[VV1_SDL_KEY_REPEAT_OFFSET\]\s*!=\s*0")
        self.assertRegex(digit, r"VV1_KMOD_CTRL\s*\|\s*VV1_KMOD_ALT")
        self.assertRegex(digit, r"sym\s*>=\s*'1'\s*&&\s*sym\s*<=\s*'9'")
        self.assertRegex(digit, r"sym\s*>=\s*VV1_SDLK_KP_1\s*&&\s*sym\s*<=\s*VV1_SDLK_KP_9")

    def test_keypad_layout_maps_explicit_measured_targets(self) -> None:
        jump = _function(self.text, "static int vv1_numkeys_jump(")
        self.assertIn("vv1_pan_target_xs[digit - 1]", jump)
        self.assertIn("vv1_pan_target_ys[digit - 1]", jump)
        self.assertIn("digit < 1 || digit > 9", jump)
        self.assertIn("-150, 300, 850", self.text)
        self.assertIn("1200, 1200, 1200", self.text)
        self.assertIn("500, 570, 500", self.text)
        self.assertIn("0, 0, 0", self.text)
        # the key sets a target; it does not write the scroll itself
        self.assertNotRegex(jump, r"\*\(int \*\)\(state \+ VV1_SCROLL_[XY]_OFFSET\)\s*=")

    def test_glide_is_native_update_driven_with_measured_residual_stop(self) -> None:
        self.assertEqual(_macro(self.text, "VV1_PAN_DIVISOR"), 10)
        step = _function(self.text, "static int vv1_pan_step(")
        self.assertIn("return cur + (target - cur) / VV1_PAN_DIVISOR", step)
        self.assertNotIn("step == 0", step)
        update = _function(self.text, "static int vv1_pan_update(")
        self.assertIn("screen_bytes + 0x10", update)
        self.assertIn("state != VV1_VILLAGE_STATE_PTR", update)
        self.assertIn("screen_bytes + 0x2D8", update)
        self.assertIn("screen_bytes + 0x2DC", update)
        self.assertRegex(update, r"\(vv1_pan_target_x - \*x\)\s*/\s*VV1_PAN_DIVISOR\s*==\s*0")
        self.assertRegex(update, r"\(vv1_pan_target_y - \*y\)\s*/\s*VV1_PAN_DIVISOR\s*==\s*0")
        self.assertIn("return 1", update, "the completion tick is consumed")
        self.assertNotIn("vv1_pan_last_x", self.text)
        self.assertNotIn("vv1_pan_last_y", self.text)
        tick = _function(self.text, "__declspec(dllexport) int __stdcall Vv1NumberKeysTick(")
        self.assertIn("Vv1NumberKeysInstall()", tick)
        self.assertNotIn("vv1_pan_update", tick)
        export = _function(self.text, "__declspec(dllexport) int __stdcall Vv1NumberKeysUpdate(")
        self.assertIn("Vv1NumberKeysInstall()", export)
        self.assertIn("vv1_pan_update(screen)", export)

    def test_key_before_village_does_not_arm_future_village(self) -> None:
        jump = _function(self.text, "static int vv1_numkeys_jump(")
        self.assertIn("VV1_VILLAGE_STATE_PTR == NULL", jump)

    def test_exports_and_built_dll(self) -> None:
        deftext = KEYS_DEF.read_text(encoding="utf-8")
        for name in ("Vv1NumberKeysInstall=_Vv1NumberKeysInstall@0", "Vv1NumberKeysTick=_Vv1NumberKeysTick@0", "Vv1NumberKeysUpdate=_Vv1NumberKeysUpdate@4", "Vv1NumberKeysProbe=_Vv1NumberKeysProbe@4"):
            self.assertIn(name, deftext)
        self.assertTrue(KEYS_DLL.is_file())
        blob = KEYS_DLL.read_bytes()
        for needle in (b"SDL2.dll\0", b"SDL_AddEventWatch\0", b"Vv1NumberKeysTick\0", b"Vv1NumberKeysUpdate\0", struct.pack("<i", -150), struct.pack("<i", 1200), struct.pack("<i", 570)):
            self.assertIn(needle, blob, needle)


class OriginsBridgeTest(unittest.TestCase):
    def test_bridge_loads_from_the_exe_directory_and_ticks_every_frame(self) -> None:
        text = ORIGINS_C.read_text(encoding="utf-8")
        bridge = _function(text, "static int vv1_numkeys_resolve(")
        self.assertIn("GetModuleFileNameA(NULL, path, MAX_PATH)", bridge)
        self.assertIn('lstrcpyA(slash + 1, "VVFP VV1 Number Keys.dll")', bridge)
        self.assertIn("LoadLibraryA(path)", bridge)
        self.assertNotIn('LoadLibraryA("VVFP', bridge, "never by bare name: the search path is not ours")
        self.assertIn('GetProcAddress(keys, "Vv1NumberKeysTick")', bridge)
        self.assertRegex(bridge, r"if\s*\(\s*vv1_numkeys_bridge_state\s*==\s*1\s*\)\s*\{\s*return\s+1;")
        self.assertRegex(bridge, r"keys\s*==\s*NULL\s*\)\s*\{\s*vv1_numkeys_bridge_state\s*=\s*-1;", "missing file: remembered, fail open")
        bridge_tick = _function(text, "static void vv1_numkeys_bridge(")
        self.assertIn("vv1_numkeys_tick();", bridge_tick)
        tick = _function(text, "__declspec(dllexport) void __stdcall Vv1MaskTick(")
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
