"""New Believers' "Heathens Keep Their Masks When Converted" (the owner, 2026-11-08: "when a heathen converts their
mask stays on their head (as if the player manually set it using Change Appearance)", "Oh and the player can always
Change Appearance to change it or take it off if they want to.").

EMULATED, on the executable the patcher renders for the row (with the Origins base it needs), in each of the three
public modes, and with 256 Villagers (Experimental):

* "VVFP Heathens Keep Masks.dll" is started as VVFP Startup.dll starts it (VvfpStartup(5, ...));
* the game's own conversion 0x4668B0 runs on a Heathen record (its sound, sparkle, message and trophy calls stood
  in for; the faction setter 0x466880 writes the faction byte), and The Defector's answer 0x416970 runs its direct
  setter call 0x41699F;
* the Origins companion is a stand-in whose VvfpMaskOf answers from the mask table as its caf_get_mask does, whose
  WriteMaskSidecar records each write, and whose Vv5MaskSync exists.

Then the mask the Heathen wore -- blue, orange, red, purple (the Heathen Doctor and the three Masters) or the
Chief's -- is the villager's nibble in the mask table, read back by the Task9 page's own mask_get (the routine the
render and Change Appearance read), and the Village Masks file is written once.  The page's own mask_set (what
Change Appearance's OK and Reset to original write through) changes it or takes it off afterwards, and nothing
puts it back.  With the companion not started, without the Origins companion, or with one that answers another
table, nothing is kept and the convert loses the mask as in the stock game.
"""
from __future__ import annotations

import importlib.util
import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402

try:
    from test_companion_installs_all_or_none import HAVE_EMULATOR, Machine, render, stock_path, with_requirements
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

ROW = "vv5_heathens_keep_masks_when_converted"
DLL = ROOT / "assets" / "heathens_keep_masks" / "VVFP Heathens Keep Masks.dll"
FEATURE = ROOT / "data" / "vv5_heathens_keep_masks_feature.json"
MODES = ("stock", "collection_progression", "immediate_fixed")

STRIDE, ACTIVE, FACTION, ORANGE, RED, ROLE, FAITH = 0x2F44, 0x1CD4, 0x1CEC, 0x1CED, 0x1CEE, 0x1CFC, 0x1CF0
STOCK_RECORDS, STOCK_TABLE = 0x554148 + 0x48, 0x7B1D20
BIG_RECORDS, BIG_TABLE = 0x800000 + 0x48, 0x7F1400
ORIGINS_BASE = 0x0B000000
OTHER_TABLE = 0x23000000            # high in the emulator's heap: zeros, never the game's table
CONVERT, DEFECTOR = 0x4668B0, 0x416970

# What the conversion 0x4668B0 calls, each popping its own arguments (thiscall/stdcall): sound 0x44C440, the
# villager's spot 0x466350 (answers a point: the pointer it is given), the sparkle 0x476D00, the scene 0x470810,
# the say-event 0x465580, the message 0x44EF60, the music 0x44E730, the trophies 0x413450, the tutorial 0x43AE80
# (answered 1: the hint is skipped), the activity clear 0x473440.
CONVERSION_CALLS = {0x44C440: 4, 0x466350: 4, 0x476D00: 20, 0x470810: 12, 0x465580: 8, 0x44EF60: 8,
                    0x44E730: 12, 0x413450: 8, 0x43AE80: 4, 0x473440: 0}

# The mask each Heathen kind wears (0x4728C6) and the nibble Change Appearance keeps for it.
KINDS = {
    "blue": (0, 0, 0, 1),
    "orange": (0, 1, 0, 2),
    "red": (0, 0, 1, 3),
    "purple (Heathen Doctor)": (12, 0, 0, 4),
    "purple (Heathen Master)": (14, 0, 0, 4),
    "purple (Heathen Master Farmer)": (16, 0, 0, 4),
    "the Chief's": (13, 0, 0, 5),
}


def _t9():
    spec = importlib.util.spec_from_file_location("vv5_task9_native_actions",
                                                  ROOT / "scripts" / "build_vv5_task9_native_actions.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T9 = _t9()
PAGE_VA = 0x7C9000
MASK_GET = PAGE_VA + T9.OFF["mask_get"]
MASK_SET = PAGE_VA + T9.OFF["mask_set"]


class Village(Machine):
    """The rendered game, the companion, and a stand-in Origins companion."""

    def __init__(self, exe: bytes, *, big: bool = False, origins: bool = True, answers=None):
        super().__init__(exe, DLL)
        self.records = BIG_RECORDS if big else STOCK_RECORDS
        self.table = BIG_TABLE if big else STOCK_TABLE
        self.answers = answers if answers is not None else self.table   # the table VvfpMaskOf reads
        self.origins = origins
        self.sidecar_writes: list[bytes] = []
        self.faction_calls: list[tuple[int, int, int]] = []
        stubs = self.alloc(0x100)
        self.exports_of_origins = {"WriteMaskSidecar": stubs, "VvfpMaskOf": stubs + 0x10, "Vv5MaskSync": stubs + 0x20}
        self.stub(stubs, self._write_masks)
        self.stub(stubs + 0x10, self._mask_of)
        self.stub(stubs + 0x20, lambda p: (1, 0))
        self.api_handlers["GetModuleHandleA"] = self._module
        self.api_handlers["GetProcAddress"] = self._proc
        for va, pop in CONVERSION_CALLS.items():
            self.stub(va, self._game_call(va, pop))
        self.stub(0x466880, self._faction_setter)

    # ---- the stand-in Origins companion ---------------------------------------------------------------------
    def _module(self, p):
        name = p.cstring(p.arg(0))
        return (ORIGINS_BASE if self.origins and name == "VVFP Origins Icons.dll" else 0), 4

    def _proc(self, p):
        if p.arg(0) != ORIGINS_BASE:
            return 0, 8
        return self.exports_of_origins.get(p.cstring(p.arg(1)), 0), 8

    def _index(self, record: int) -> int:
        return (record - self.records) // STRIDE

    def _mask_of(self, p):
        index = self._index(p.arg(0))
        byte = p.read(self.answers + (index >> 1), 1)[0]
        return ((byte >> 4) if index & 1 else byte) & 0x0F, 4

    def _write_masks(self, p):
        self.sidecar_writes.append(p.read(p.arg(0), 128))
        return 0, 4

    # ---- the game ---------------------------------------------------------------------------------------
    def _game_call(self, va: int, pop: int):
        def call(p):
            if va == 0x466350:
                return p.arg(0), pop                 # the spot: a point the caller reads
            if va == 0x43AE80:
                return 1, pop                        # the tutorial hint is not shown
            return 0, pop
        return call

    def _faction_setter(self, p):
        record, value = p.reg("ecx"), p.arg(0) & 0xFF
        self.faction_calls.append((record, value, p.u32(p.reg("esp"))))
        p.write(record + FACTION, bytes([value]))
        return 0, 4

    def record(self, index: int) -> int:
        return self.records + index * STRIDE

    def heathen(self, index: int, role: int, orange: int, red: int) -> int:
        record = self.record(index)
        self.write(record, bytes(STRIDE))
        self.write(record + ACTIVE, b"\x01")
        self.write(record + 0x1B9C, f"Heathen{index}".encode() + b"\0")
        self.write(record + FACTION, b"\x01")
        self.write(record + ORANGE, bytes([orange]))
        self.write(record + RED, bytes([red]))
        self.put32(record + ROLE, role)
        return record

    def convert(self, record: int) -> None:
        self.call(CONVERT, [], ecx=record)

    def defector(self, record: int) -> None:
        """The Defector's "welcome" (0x416970 with answer 0): SetFaith(+20), which leaves the Faith at or below 0
        here (no conversion), then the faction setter with 0 at 0x41699F."""
        event = self.alloc(0x20)
        self.put32(event + 4, record)
        self.stub(0x470920, lambda p: (0, 4))
        self.stub(0x467F90, lambda p: (0, 8))
        self.call(DEFECTOR, [0], ecx=event)

    def mask_get(self, record: int) -> int:
        """The Task9 page's mask_get: what the render's mask flip and Change Appearance read."""
        return self.call(MASK_GET, regs={"esi": record})

    def mask_set(self, record: int, mask: int) -> None:
        """The Task9 page's mask_set: what Change Appearance's OK (and Reset to original) writes."""
        self.call(MASK_SET, regs={"esi": record, "ebx": mask})


def _skip() -> str | None:
    if not HAVE_EMULATOR:
        return "unicorn/pefile not installed"
    if not stock_path(5).is_file():
        return "stock executable not present (inputs/)"
    if not DLL.is_file():
        return f"{DLL} missing"
    return None


class TheRow(unittest.TestCase):
    def test_the_row_is_new_believers_and_needs_the_origins_base(self):
        row = json.loads(FEATURE.read_text(encoding="utf-8"))
        self.assertEqual(row["id"], ROW)
        self.assertEqual(row["name"], "Heathens Keep Their Masks When Converted")
        self.assertEqual(row["game_id"], "vv5")
        self.assertEqual(row["dependencies"], ["vv5_enable_origins_exclusive_features"])
        self.assertEqual(row["patches"], [])
        self.assertTrue(row["description"].startswith("**Needs Enable Origins-Exclusive Features"),
                        "the dependency comes first, in bold")
        ids = {p.id for p in patcher.load_public_fun_patches()}
        self.assertIn(ROW, ids)
        self.assertEqual([c["destination"] for c in row["companion_files"]], ["VVFP Heathens Keep Masks.dll"])
        self.assertIn("VVFP Heathens Keep Masks.dll", patcher.STARTUP_LOADER_COMPANIONS_2)


@unittest.skipIf(_skip(), _skip() or "")
class KeptMasks(unittest.TestCase):
    maxDiff = None

    def village(self, mode="collection_progression", *, big=False, start=True, **kw) -> Village:
        rows = [ROW] + (["vv5_population_256"] if big else [])
        v = Village(render(5, with_requirements(5, rows), mode), big=big, **kw)
        if start:
            v.export("VvfpStartup", 5, 0)
            self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 1)
        return v

    def test_every_mask_kind_is_kept_in_every_mode(self):
        for mode in MODES:
            for kind, (role, orange, red, mask) in KINDS.items():
                with self.subTest(mode=mode, kind=kind):
                    v = self.village(mode)
                    record = v.heathen(7, role, orange, red)
                    self.assertEqual(v.mask_get(record), 0, "no Change Appearance mask before")
                    v.convert(record)
                    self.assertEqual(v.read(record + FACTION, 1), b"\0", "the game's conversion still converts")
                    self.assertEqual(v.u32(record + ROLE), 13 if role == 13 else 0,
                                     "every role but the Chief's is cleared, as in the stock game")
                    self.assertEqual(v.mask_get(record), mask, "the mask they wore is their mask now")
                    self.assertEqual(len(v.sidecar_writes), 1, "the Village Masks file is written once")
                    self.assertEqual(v.export("VvfpHeathensKeepMasksKept"), 1)

    def test_with_256_villagers_the_table_of_that_build(self):
        for index in (0, 149, 150, 255):
            with self.subTest(record=index):
                v = self.village(big=True)
                record = v.heathen(index, 0, 0, 1)
                v.convert(record)
                self.assertEqual(v.mask_get(record), 3)
                self.assertEqual(v.read(STOCK_TABLE, 0x80), bytes(0x80), "the stock build's table is not used")

    def test_neighbours_keep_their_masks(self):
        """A nibble shares its byte with the record beside it: that one's mask is untouched."""
        v = self.village()
        left, right = v.record(4), v.heathen(5, 0, 1, 0)
        v.write(left, bytes(STRIDE))
        v.write(left + ACTIVE, b"\x01")
        v.mask_set(left, 4)
        v.convert(right)
        self.assertEqual((v.mask_get(left), v.mask_get(right)), (4, 2))

    def test_change_appearance_can_change_it_or_take_it_off_later(self):
        v = self.village()
        record = v.heathen(3, 0, 0, 1)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 3)
        v.mask_set(record, 1)                         # Change Appearance: Blue
        self.assertEqual(v.mask_get(record), 1)
        v.mask_set(record, 0)                         # Change Appearance: No Mask (and Reset to original: none)
        self.assertEqual(v.mask_get(record), 0)
        v.convert(record)                             # a believer reaching the conversion again: nothing is kept
        self.assertEqual(v.mask_get(record), 0, "a believer's own choice is never put back")
        self.assertEqual(len(v.sidecar_writes), 1)

    def test_a_heathen_who_comes_back_takes_the_mask_of_this_conversion(self):
        """A believer with a Change Appearance mask who became a Heathen and joins again wears, and keeps, the
        Heathen mask the game draws now."""
        v = self.village()
        record = v.heathen(2, 0, 1, 0)
        v.mask_set(record, 5)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 2)

    def test_the_defector_direct_setter_keeps_it_too(self):
        v = self.village()
        record = v.heathen(9, 14, 0, 0)
        v.defector(record)
        self.assertEqual(v.read(record + FACTION, 1), b"\0")
        self.assertEqual(v.faction_calls[-1][2], 0x4169A4, "the setter sees the stock return address")
        self.assertEqual(v.mask_get(record), 4)
        self.assertEqual(len(v.sidecar_writes), 1)

    def test_the_defector_after_a_conversion_keeps_nothing_twice(self):
        v = self.village()
        record = v.heathen(9, 0, 0, 0)
        v.convert(record)                             # SetFaith(+20) converted already
        v.defector(record)
        self.assertEqual(v.mask_get(record), 1)
        self.assertEqual(len(v.sidecar_writes), 1)

    def test_the_patch_off_keeps_nothing(self):
        """Without the row the companion is not shipped, so VVFP Startup.dll never starts it: the stock loss."""
        v = Village(render(5, with_requirements(5, ["vv5_enable_origins_exclusive_features"]), "collection_progression"))
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 0)
        self.assertEqual(v.sidecar_writes, [])
        shipping = {p.id for p in patcher.load_fun_patches()
                    if any(c.get("destination") == "VVFP Heathens Keep Masks.dll" for c in p.raw.get("companion_files", []))}
        self.assertEqual(shipping, {ROW}, "only this row ships the companion")

    def test_without_the_origins_companion_nothing_is_kept(self):
        v = self.village(origins=False)
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.read(record + FACTION, 1), b"\0", "the conversion goes on")
        self.assertEqual(v.mask_get(record), 0)
        self.assertEqual(v.sidecar_writes, [])
        self.assertEqual(v.export("VvfpHeathensKeepMasksKept"), 0)

    def test_an_origins_companion_answering_another_table_is_never_written_into(self):
        v = self.village(answers=OTHER_TABLE)
        record = v.heathen(7, 0, 1, 0)
        v.convert(record)
        self.assertEqual(v.mask_get(record), 0, "the nibble is put back")
        self.assertEqual(v.sidecar_writes, [])

    def test_the_install_is_refused_on_other_bytes(self):
        exe = bytearray(render(5, with_requirements(5, [ROW]), "collection_progression"))
        pe_offset = 0x41699F - 0x400000            # .text: file offset = VA - 0x400000
        exe[pe_offset] = 0x90
        v = Village(bytes(exe))
        v.export("VvfpStartup", 5, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)
        self.assertEqual(v.read(0x466966, 7), bytes.fromhex("83BEFC1C00000D"), "neither site is written")

    def test_another_game_installs_nothing(self):
        v = self.village(start=False)
        for game in (1, 2, 3, 4):
            v.export("VvfpStartup", game, 0)
        self.assertEqual(v.export("VvfpHeathensKeepMasksInstalled"), 0)


if __name__ == "__main__":
    unittest.main()
