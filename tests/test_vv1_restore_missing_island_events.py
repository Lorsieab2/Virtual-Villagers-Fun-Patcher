"""A New Home: Restore Missing Island Events (A Mighty Storm, The Furry Food).

The owner asked for the two island events the original game never runs to
join the game's own random island-event roll, with the same chance as a
typical event and only when their own premise -- stored food -- holds.

Root cause, read from the stock executable (scripts/
build_vv1_restore_missing_island_events_feature.py has the details): each
chooser looks the rolled event's condition class up in a byte table and
jumps through a small table of condition checks.  A Mighty Storm (island
case 1) is the only user of island class 5, The Furry Food (encounter
variant 5) the only user of encounter class 4, and both entries are the
chooser's own re-roll.  The row re-aims exactly those two entries at a
stored-food test.

These tests pin the manifest and the bytes, decode the caves, render the row
alone and with every public A New Home patch in all three population modes,
run the REAL choosers of each build in an emulator (every first roll, food
and no food), run the REAL event handlers (the storm, both Furry Food
choices), and check the Story / Cheat Upgrades companion's copy of the row's
bytes against the manifest.
"""
from __future__ import annotations

import json
import re
import struct
import sys
import unittest
from pathlib import Path

import pefile
from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from vv_fun_patcher import (  # noqa: E402
    load_builds,
    load_fun_patches,
    load_public_fun_patches,
    render_patched_bytes,
)

FEATURE_ID = "vv1_restore_missing_island_events"
MANIFEST = ROOT / "data" / "vv1_restore_missing_island_events_feature.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - A New Home.exe"
STORY_VV1 = ROOT / "native" / "vvfp_story_upgrades" / "story_vv1.inc"
MODES = ("stock", "collection_progression", "immediate_fixed")
BASE = 0x400000

ISLAND_ENTRY, ENCOUNTER_ENTRY = 0x42869C, 0x4189A0
HELPER, ISLAND_STUB, ENCOUNTER_STUB = 0x4568E1, 0x4568EF, 0x456670
ISLAND_CHOOSER, ENCOUNTER_CHOOSER = 0x428470, 0x418920
ISLAND_RUN, ENCOUNTER_RESULT = 0x427CA0, 0x419380
RAND, STRING, SPRINTF, FORMAT = 0x402F10, 0x433970, 0x44B23D, 0x4184A0
ROOM_TEST, CHILD_PICK = 0x43A1A0, 0x43BE70
WORLD_GLOBAL, FOOD = 0x48AEDC, 0xA2EC
SICK, HEALTH, ACTIVE, AGE = 0x354, 0x344, 0x28, 0x348
STRIDE, RECORDS_N = 0x3D8, 256

STACK, THIS, WORLD, RECORDS, RETURN, TEXT = (
    0x70000000, 0x20000000, 0x30000000, 0x40000000, 0x0BAD0000, 0x50000000)


def _vv1():
    return next(build for build in load_builds() if build.id == "vv1")


def _render(mode: str, ids) -> bytes:
    rendered, _ = render_patched_bytes(STOCK, _vv1(), mode, list(ids))
    return bytes(rendered)


def _other_public_vv1_ids() -> list[str]:
    return [p.id for p in load_public_fun_patches() if p.game_id == "vv1" and p.id != FEATURE_ID]


def _changed(before: bytes, after: bytes) -> list[int]:
    field = pefile.PE(data=after, fast_load=True).OPTIONAL_HEADER.get_field_absolute_offset("CheckSum")
    return [i for i in range(min(len(before), len(after)))
            if before[i] != after[i] and not field <= i < field + 4]


class Village:
    """One emulated A New Home village around a rendered executable."""

    def __init__(self, exe: bytes, food: int, rolls=(), fallback: int = 0) -> None:
        pe = pefile.PE(data=exe)
        image = pe.get_memory_mapped_image()
        mu = self.mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(BASE, (len(image) + 0xFFFF) & ~0xFFFF)
        mu.mem_write(BASE, image)
        mu.mem_map(STACK - 0x40000, 0x50000)
        mu.mem_map(THIS, 0x10000)
        mu.mem_map(WORLD, 0x10000)
        mu.mem_map(RECORDS, 0x40000)
        mu.mem_map(RETURN, 0x1000)
        mu.mem_map(TEXT, 0x1000)
        mu.mem_write(TEXT, b"text\0")
        mu.mem_write(WORLD_GLOBAL, struct.pack("<I", WORLD))
        mu.mem_write(THIS + 0x50A4, struct.pack("<I", WORLD))
        mu.mem_write(THIS + 0x50A8, struct.pack("<I", RECORDS))
        mu.mem_write(THIS + 0x50AC, struct.pack("<I", TEXT))
        # Every other event's condition holds: crops (case 3), a clean beach
        # (case 9), and room / a child (the hooked tests below).
        mu.mem_write(WORLD + 0xA2E4, struct.pack("<i", 2))
        mu.mem_write(WORLD + 0x9FB8, b"\x01")
        mu.mem_write(WORLD + 0xA2BC, struct.pack("<i", 0))
        mu.mem_write(WORLD + 0xA2D4, struct.pack("<i", 0))
        mu.mem_write(WORLD + FOOD, struct.pack("<i", food))
        # Ten living villagers: eight adults and two children.
        for i in range(10):
            r = RECORDS + i * STRIDE
            mu.mem_write(r + ACTIVE, b"\x01")
            mu.mem_write(r + HEALTH, struct.pack("<i", 50))
            mu.mem_write(r + AGE, struct.pack("<i", 0x60 if i < 2 else 0x300))
        self.rolls = list(rolls)
        self.fallback = fallback
        self.rand_calls: list[int] = []
        self.strings: list[int] = []
        self.ran: tuple[int, int] | None = None
        self._hooks = {
            RAND: self._rand, STRING: self._string, SPRINTF: self._sprintf,
            FORMAT: self._format, ROOM_TEST: self._room, CHILD_PICK: self._child,
            ISLAND_RUN: self._island_run,
        }
        mu.hook_add(UC_HOOK_CODE, self._dispatch)

    # -- hooks: each emulates the callee and returns to its caller ----------
    def _ret(self, value: int, pop: int) -> None:
        esp = self.mu.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", self.mu.mem_read(esp, 4))[0]
        self.mu.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        self.mu.reg_write(UC_X86_REG_ESP, esp + 4 + pop)
        self.mu.reg_write(UC_X86_REG_EIP, back)

    def _arg(self, n: int) -> int:
        esp = self.mu.reg_read(UC_X86_REG_ESP)
        return struct.unpack("<i", self.mu.mem_read(esp + 4 * n, 4))[0]

    def _rand(self) -> None:
        bound = self._arg(1)
        self.rand_calls.append(bound)
        value = self.rolls.pop(0) if self.rolls else self.fallback
        assert 0 <= value < max(bound, 1), (value, bound)
        self._ret(value, 0)

    def _string(self) -> None:
        self.strings.append(self._arg(1))
        self._ret(TEXT, 4)

    def _sprintf(self) -> None:
        self._ret(0, 0)

    def _format(self) -> None:
        self._ret(0, 8)

    def _room(self) -> None:
        self._ret(1, 0)

    def _child(self) -> None:
        self._ret(0, 0)

    def _island_run(self) -> None:
        if self.ran is None and self.stop_at_run:
            self.ran = (self._arg(1), self._arg(2))
            self.mu.emu_stop()

    def _dispatch(self, mu, address, size, _user) -> None:
        hook = self._hooks.get(address)
        if hook is not None:
            hook()

    # -- entry points --------------------------------------------------------
    def _call(self, entry: int, args=(), stop_at_run: bool = False) -> int:
        self.stop_at_run = stop_at_run
        esp = STACK - 0x100 - 4 * len(args)
        self.mu.mem_write(esp, struct.pack("<I", RETURN) + b"".join(struct.pack("<i", a) for a in args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, THIS)
        self.mu.emu_start(entry, RETURN, count=200000)
        return self.mu.reg_read(UC_X86_REG_EAX)

    def island_case(self) -> int:
        """The real island chooser (type 2, magnitude 3): the case it runs."""
        self._call(ISLAND_CHOOSER, (2, 3), stop_at_run=True)
        assert self.ran is not None and self.ran[1] == 3, self.ran
        return self.ran[0]

    def encounter_variant(self) -> int:
        return self._call(ENCOUNTER_CHOOSER)

    def run_island_case(self, case: int) -> None:
        self._call(ISLAND_RUN, (case, 3))

    def furry_food_choice(self, choice: int) -> None:
        self.mu.mem_write(THIS + 0x5094, struct.pack("<i", 5))
        self.mu.mem_write(THIS + 0x509C, struct.pack("<i", choice))
        self._call(ENCOUNTER_RESULT)

    def food(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(WORLD + FOOD, 4))[0]

    def field(self, index: int, offset: int) -> int:
        return struct.unpack("<i", self.mu.mem_read(RECORDS + index * STRIDE + offset, 4))[0]


def _first_roll_table(exe: bytes, food: int, bound: int, encounter: bool):
    """For every first roll: (the event chosen, how many rolls it took).
    Re-rolls answer 0 (island case 0) / 1 (encounter 1), whose conditions
    always hold."""
    table = {}
    for first in range(bound):
        v = Village(exe, food, rolls=[first], fallback=1 if encounter else 0)
        chosen = v.encounter_variant() if encounter else v.island_case()
        table[first] = (chosen, len(v.rand_calls))
        assert set(v.rand_calls) == {bound}, v.rand_calls
    return table


class RestoreMissingIslandEventsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stock = STOCK.read_bytes()
        cls.row = json.loads(MANIFEST.read_text(encoding="utf-8"))
        cls.builds = {}
        others = _other_public_vv1_ids()
        for mode in MODES:
            cls.builds[(mode, "stock")] = _render(mode, [])
            cls.builds[(mode, "row")] = _render(mode, [FEATURE_ID])
            cls.builds[(mode, "all")] = _render(mode, others + [FEATURE_ID])
            cls.builds[(mode, "all_but_row")] = _render(mode, others)

    # -- manifest -----------------------------------------------------------
    def test_manifest_row(self) -> None:
        raw = self.row
        self.assertEqual(raw["id"], FEATURE_ID)
        self.assertEqual(raw["game_id"], "vv1")
        self.assertEqual(raw["name"], "Restore Missing Island Events")
        self.assertEqual(raw["output_tag"], "Missing Island Events")
        self.assertTrue(raw["description"].endswith("**Needs no other patch.**"))
        self.assertNotIn("dependencies", raw)
        self.assertIn(FEATURE_ID, {p.id for p in load_public_fun_patches()})
        self.assertEqual(
            [(int(p["offset"], 16), len(p["after"]) // 2) for p in raw["patches"]],
            [(ISLAND_ENTRY - BASE, 4), (ENCOUNTER_ENTRY - BASE, 4), (HELPER - BASE, 30),
             (ENCOUNTER_STUB - BASE, 16)],
        )
        for patch in raw["patches"]:
            off = int(patch["offset"], 16)
            before = bytes.fromhex(patch["before"])
            self.assertEqual(self.stock[off:off + len(before)], before)

    def test_generator_reproduces_the_manifest(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts"))
        import build_vv1_restore_missing_island_events_feature as gen
        self.assertEqual(gen.build(), self.row)

    def test_default_on_and_ticked_by_every_button(self) -> None:
        from vv_fun_patcher_gui import (
            default_fun_patch_selection,
            owners_default_fun_patch_selection,
            select_all_fun_patch_selection,
        )
        self.assertTrue(default_fun_patch_selection(FEATURE_ID))
        self.assertTrue(owners_default_fun_patch_selection(FEATURE_ID))
        self.assertTrue(select_all_fun_patch_selection(FEATURE_ID))

    def test_release_ships_the_manifest(self) -> None:
        text = (ROOT / "scripts" / "build_release.py").read_text(encoding="utf-8")
        self.assertIn('"data/vv1_restore_missing_island_events_feature.json"', text)

    # -- the stock gate -----------------------------------------------------
    def test_stock_tables_keep_the_two_events_out(self) -> None:
        s = self.stock
        island_classes = s[0x4286A0 - BASE:0x4286A0 - BASE + 15]
        encounter_classes = s[0x4189A4 - BASE:0x4189A4 - BASE + 16]
        self.assertEqual([i for i, c in enumerate(island_classes) if c == 5], [1])
        self.assertEqual([i for i, c in enumerate(encounter_classes) if c == 4], [5])
        self.assertEqual(struct.unpack_from("<I", s, ISLAND_ENTRY - BASE)[0], 0x4284D6)
        self.assertEqual(struct.unpack_from("<I", s, ENCOUNTER_ENTRY - BASE)[0], 0x418930)

    def test_caves_decode(self) -> None:
        rendered = self.builds[("stock", "row")]
        md = Cs(CS_ARCH_X86, CS_MODE_32)

        def listing(va: int, n: int):
            return [(i.address, i.mnemonic, i.op_str)
                    for i in md.disasm(rendered[va - BASE:va - BASE + n], va)]

        self.assertEqual(listing(HELPER, 30), [
            (0x4568E1, "mov", "ecx, dword ptr [0x48aedc]"),
            (0x4568E7, "cmp", "dword ptr [ecx + 0xa2ec], 0"),
            (0x4568EE, "ret", ""),
            (0x4568EF, "call", "0x4568e1"),
            (0x4568F4, "jle", "0x4284d6"),
            (0x4568FA, "jmp", "0x428671"),
        ])
        self.assertEqual(listing(ENCOUNTER_STUB, 16), [
            (0x456670, "call", "0x4568e1"),
            (0x456675, "jle", "0x418930"),
            (0x45667B, "jmp", "0x41895d"),
        ])
        self.assertEqual(struct.unpack_from("<I", rendered, ISLAND_ENTRY - BASE)[0], ISLAND_STUB)
        self.assertEqual(struct.unpack_from("<I", rendered, ENCOUNTER_ENTRY - BASE)[0], ENCOUNTER_STUB)

    # -- rendering ----------------------------------------------------------
    def _assert_only_row_bytes(self, without: bytes, rendered: bytes) -> None:
        ranges = [(int(p["offset"], 16), len(p["after"]) // 2) for p in self.row["patches"]]
        diff = _changed(without, rendered)
        self.assertTrue(diff)
        self.assertTrue(all(any(o <= i < o + n for o, n in ranges) for i in diff),
                        [hex(i) for i in diff[:8]])
        self.assertEqual(len(rendered), len(without))
        for p in self.row["patches"]:
            o = int(p["offset"], 16)
            self.assertEqual(rendered[o:o + len(p["after"]) // 2], bytes.fromhex(p["after"]))
            self.assertEqual(without[o:o + len(p["before"]) // 2], bytes.fromhex(p["before"]))

    def test_render_alone_in_every_mode(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                self._assert_only_row_bytes(self.builds[(mode, "stock")], self.builds[(mode, "row")])

    def test_render_with_every_public_vv1_patch_in_every_mode(self) -> None:
        self.assertGreater(len(_other_public_vv1_ids()), 20)
        self.assertIn("vv1_story_cheat_upgrades", _other_public_vv1_ids())
        self.assertIn("vv1_fix_vanilla_bugs", _other_public_vv1_ids())
        for mode in MODES:
            with self.subTest(mode=mode):
                self._assert_only_row_bytes(self.builds[(mode, "all_but_row")], self.builds[(mode, "all")])

    def test_story_detour_sites_are_untouched(self) -> None:
        """Pick Island Event's case/encounter rolls and unlock stubs keep
        their stock bytes under the row (the companion guards on them)."""
        for site, n in ((0x4284DB, 5), (0x4284EC, 7), (0x418932, 5), (0x418941, 7)):
            for mode in MODES:
                rendered = self.builds[(mode, "all")]
                self.assertEqual(rendered[site - BASE:site - BASE + n], self.stock[site - BASE:site - BASE + n])

    # -- the choosers, emulated ---------------------------------------------
    def test_island_chooser_every_first_roll(self) -> None:
        for mode in MODES:
            for label in ("stock", "row", "all"):
                exe = self.builds[(mode, label)]
                for food in (0, 1, 500):
                    with self.subTest(mode=mode, build=label, food=food):
                        table = _first_roll_table(exe, food, 15, encounter=False)
                        restored = label != "stock" and food > 0
                        for first, (case, rolls) in table.items():
                            if first == 1 and not restored:
                                # A Mighty Storm is re-rolled (stock behaviour).
                                self.assertEqual((case, rolls), (0, 2))
                            else:
                                # Accepted on its first roll, like every other case.
                                self.assertEqual((case, rolls), (first, 1))

    def test_encounter_chooser_every_first_roll(self) -> None:
        for mode in MODES:
            for label in ("stock", "row", "all"):
                exe = self.builds[(mode, label)]
                for food in (0, 1, 500):
                    with self.subTest(mode=mode, build=label, food=food):
                        table = _first_roll_table(exe, food, 16, encounter=True)
                        restored = label != "stock" and food > 0
                        for first, (variant, rolls) in table.items():
                            if first == 5 and not restored:
                                self.assertEqual((variant, rolls), (1, 2))
                            else:
                                self.assertEqual((variant, rolls), (first, 1))

    def test_typical_odds(self) -> None:
        """With stored food, each event is chosen by exactly one of the 15
        (island) / 16 (encounter) equally likely first rolls -- the same share
        as any other event whose condition holds -- and nothing else moves."""
        exe = self.builds[("stock", "all")]
        island = _first_roll_table(exe, 300, 15, encounter=False)
        encounter = _first_roll_table(exe, 300, 16, encounter=True)
        island_share = {c: sum(1 for k in island.values() if k[0] == c) for c in range(15)}
        encounter_share = {c: sum(1 for k in encounter.values() if k[0] == c) for c in range(16)}
        self.assertEqual(set(island_share.values()), {1})
        self.assertEqual(set(encounter_share.values()), {1})

    # -- the events' own handlers, emulated ---------------------------------
    def test_mighty_storm_washes_away_all_the_food(self) -> None:
        for label in ("row", "all"):
            with self.subTest(build=label):
                v = Village(self.builds[("stock", label)], 750)
                before = bytes(v.mu.mem_read(WORLD, 0x10000))
                v.run_island_case(1)
                after = bytes(v.mu.mem_read(WORLD, 0x10000))
                self.assertEqual(v.food(), 0)
                self.assertEqual(v.strings, [0x1ED])        # "A Mighty Storm ... washed away"
                changed = [i for i in range(len(before)) if before[i] != after[i]]
                self.assertEqual(changed, [FOOD, FOOD + 1])   # 750 = 0x2EE: only the food

    def test_furry_food_throw_out_all_the_food(self) -> None:
        v = Village(self.builds[("stock", "all")], 750)
        v.furry_food_choice(2)
        self.assertEqual(v.food(), 0)
        self.assertEqual(v.strings, [0x164])                # "Throw out all the food."
        self.assertEqual([v.field(i, SICK) for i in range(10)], [0] * 10)
        self.assertEqual(v.rand_calls, [])

    def test_furry_food_remove_the_moldy_pieces(self) -> None:
        rolls = [3, 97, 49, 50, 0, 99, 12, 75, 48, 51]
        v = Village(self.builds[("stock", "all")], 750, rolls=rolls)
        v.furry_food_choice(1)
        self.assertEqual(v.food(), 750)                      # the food is kept
        self.assertEqual(v.strings, [0x163])                # "...a few villagers seem to have stomach troubles."
        self.assertEqual(v.rand_calls, [100] * 10)          # one rand(100) per living villager
        self.assertEqual([v.field(i, SICK) for i in range(10)], [int(r < 50) for r in rolls])
        self.assertEqual([v.field(i, HEALTH) for i in range(10)], [50] * 10)

    # -- Story / Cheat Upgrades ---------------------------------------------
    def test_story_companion_detects_the_row_by_its_own_bytes(self) -> None:
        source = STORY_VV1.read_text(encoding="utf-8")

        def array(name: str) -> bytes:
            body = re.search(r"%s\[\d+\] = \{([^}]*)\}" % name, source).group(1)
            return bytes(int(x, 16) for x in re.findall(r"0x([0-9A-Fa-f]{2})", body))

        rendered = self.builds[("stock", "row")]
        self.assertEqual(array("VV1_STORM_ENTRY"), rendered[ISLAND_ENTRY - BASE:ISLAND_ENTRY - BASE + 4])
        self.assertEqual(array("VV1_FURRY_ENTRY"), rendered[ENCOUNTER_ENTRY - BASE:ENCOUNTER_ENTRY - BASE + 4])
        self.assertEqual(array("VV1_STORM_STUB"), rendered[ISLAND_STUB - BASE:ISLAND_STUB - BASE + 16])
        self.assertEqual(array("VV1_FURRY_STUB"), rendered[ENCOUNTER_STUB - BASE:ENCOUNTER_STUB - BASE + 16])
        self.assertEqual(array("VV1_RESTORED_FOOD_TEST"), rendered[HELPER - BASE:HELPER - BASE + 14])
        for va in (ISLAND_ENTRY, ENCOUNTER_ENTRY, ISLAND_STUB, ENCOUNTER_STUB, HELPER):
            self.assertIn("0x%Xu" % va, source)
        # Without the row none of them match: the base game's events stay dead.
        stock = self.builds[("stock", "all_but_row")]
        self.assertNotEqual(array("VV1_STORM_ENTRY"), stock[ISLAND_ENTRY - BASE:ISLAND_ENTRY - BASE + 4])
        self.assertNotEqual(array("VV1_FURRY_ENTRY"), stock[ENCOUNTER_ENTRY - BASE:ENCOUNTER_ENTRY - BASE + 4])


if __name__ == "__main__":
    unittest.main()
