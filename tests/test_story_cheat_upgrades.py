"""Story / Cheat Upgrades (all five games, default-off).

The owner: "When enabled, all Origins Upgrades cost 0 Tech Points. Also adds
... Pick Island Event -- Allows the player to directly choose which stock
Island Event occurs ... Selecting an event causes that specific event to occur
through the game's Island Event system."

Everything here runs the shipped bytes: each game's executable as the patcher
renders it (all three population modes), with the test build of "VVFP Story
Upgrades.dll" mapped beside it in an emulator (tests/story_emulator.py).

* Install: the companion's own VvfpStoryInstall finds every listed site
  holding exactly the Origins bytes, and writes them -- or, if ANY differs,
  writes nothing.  Nothing outside the listed sites changes.
* Cost 0: every Origins instruction that compares, deducts, refunds or passes
  a price is EXECUTED after the install with a balance of 0: no comparison
  refuses, no deduction or refund moves the balance.  The same instructions
  executed before the install refuse a balance of 0 -- so the check is live.
* Pick Island Event: each game's own chooser is run with the pick armed and
  delivers the picked event to the game's native dispatch (VV1 0x427CA0,
  VV2 0x433600 / 0x41F570, the event-object selectors of VV3-VV5), only when
  the event's own condition holds; otherwise the game's own choice stands.
* The lock: arming writes exactly what the Origins Island Event purchase
  writes, so the game's own pending check reports an island event queued, and
  a second pick is refused.
* Dead events are not offered; every offered title is the game's own text.

The tests that need a stock executable or the test build skip when absent.
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import vv_fun_patcher as patcher  # noqa: E402
import story_island_events  # noqa: E402
from vv_fun_patcher_gui import (  # noqa: E402
    DEFAULT_OFF_FUN_PATCH_IDS,
    default_fun_patch_selection,
    owners_default_fun_patch_selection,
)

try:
    import pefile
    from capstone import CS_ARCH_X86, CS_MODE_32, Cs
    from capstone.x86 import X86_OP_IMM, X86_OP_MEM, X86_OP_REG
    from unicorn.x86_const import UC_X86_REG_EFLAGS

    from story_emulator import HEAP, Process

    HAVE_EMULATOR = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_EMULATOR = False

GAMES = ("vv1", "vv2", "vv3", "vv4", "vv5")
MODES = ("stock", "collection_progression", "immediate_fixed")
DLL = ROOT / "assets" / "story_upgrades" / "VVFP Story Upgrades.dll"
# A mutation run points this at a deliberately broken test build.
TEST_DLL = Path(os.environ.get(
    "VVFP_STORY_TEST_DLL", ROOT / "tests" / "test_dlls" / "VVFP Story Upgrades.test.dll"))
TEST_BUILD_ABSENT = "test builds are not in the release source archive (tests/test_dlls)"
PRICES = (5000, 30000, 40000, 50000, 75000, 100000, 450000, 500000, 1000000)
TEN_MINUTES = 10 * 60 * 1000


def feature_id(game: str) -> str:
    return f"{game}_story_cheat_upgrades"


@functools.lru_cache(maxsize=None)
def _builds():
    return {build.id: build for build in patcher.load_builds()}


def stock_path(game: str) -> Path:
    return ROOT / "inputs" / f"{game}-stock-copy" / _builds()[game].input_name


def have_stock(game: str) -> bool:
    return stock_path(game).is_file()


@functools.lru_cache(maxsize=None)
def render(game: str, mode: str, story: bool = True) -> bytes:
    ids = [f"{game}_origins_village_wide_upgrades"] + ([feature_id(game)] if story else [])
    data, _ = patcher.render_patched_bytes(stock_path(game), _builds()[game], mode, ids)
    return bytes(data)


@functools.lru_cache(maxsize=None)
def manifest(game: str) -> dict:
    return json.loads((ROOT / "data" / f"{game}_story_cheat_upgrades_feature.json").read_text(
        encoding="utf-8"))


def process(game: str, mode: str = "collection_progression", *, data: bytes | None = None):
    proc = Process(render(game, mode) if data is None else data, TEST_DLL)
    return proc


def sites(proc: "Process", game: str):
    """The companion's own site table: [(va, expect, replace)], writes first."""
    n = int(game[2:])
    out = []
    buf = HEAP + 0x3F00000
    proc.write(buf, bytes(0x400))
    index = 0
    while True:
        length = proc.export("VvfpStoryProbeSite", n, index, buf, buf + 0x100, buf + 0x200)
        if length == 0:
            return out
        out.append((proc.u32(buf), proc.read(buf + 0x100, length), proc.read(buf + 0x200, length)))
        index += 1


def emulated(cls):
    return unittest.skipUnless(HAVE_EMULATOR, "capstone/unicorn/pefile not installed")(
        unittest.skipUnless(TEST_DLL.is_file(), TEST_BUILD_ABSENT)(cls))


# ---------------------------------------------------------------------------
# The rows
# ---------------------------------------------------------------------------

class RowTests(unittest.TestCase):
    def test_five_rows_named_and_described_by_the_owner(self):
        catalog = {p.id: p for p in patcher.load_public_fun_patches()}
        for game in GAMES:
            with self.subTest(game=game):
                row = catalog[feature_id(game)]
                self.assertEqual(row.name, "Story / Cheat Upgrades")
                text = row.raw["description"]
                self.assertIn("all Origins Upgrades cost 0 Tech Points", text)
                self.assertIn("Pick Island Event", text)
                self.assertIn("Off by default", text)
                self.assertIn("**Requires Enable Origins Tech, Details, and Village-Wide Upgrades", text)
                self.assertEqual(text.count("**") % 2, 0)
                # Part 2, in the owner's own words.
                self.assertIn("Custom Island Event -- Allows the player to create and trigger a "
                              "custom Island Event for storytelling, testing, sandbox play, or "
                              "cheats.", text)
                self.assertIn("Custom events should appear and behave as closely as practical to "
                              "ordinary Island Events, while clearly allowing player-defined "
                              "outcomes.", text)
                self.assertIn("**A pregnancy a custom event starts is written to the Births and "
                              "Conceptions log only with Write Births and Conceptions Log to Text "
                              "File ticked.**", text)
                if game == "vv1":
                    self.assertIn("only with Show Parents in Details Screen ticked", text)
                self.assertTrue(row.raw["custom_island_event"]["offered"])
                for omitted in row.raw["custom_island_event"]["omitted"]:
                    self.assertTrue(omitted["reason"], omitted)
                self.assertEqual(row.raw["dependencies"], [f"{game}_origins_village_wide_upgrades"])

    def test_off_by_default_and_not_ticked_by_owners_defaults(self):
        for game in GAMES:
            with self.subTest(game=game):
                self.assertIn(feature_id(game), DEFAULT_OFF_FUN_PATCH_IDS)
                self.assertFalse(default_fun_patch_selection(feature_id(game)))
                self.assertFalse(owners_default_fun_patch_selection(feature_id(game)))

    def test_requires_the_origins_upgrades(self):
        for game in GAMES:
            with self.subTest(game=game):
                with self.assertRaises(patcher.PatcherError):
                    patcher.resolve_fun_patch_ids([feature_id(game)], game_id=game)
                order = patcher.resolve_fun_patch_ids(
                    [feature_id(game), f"{game}_origins_village_wide_upgrades"], game_id=game)
                self.assertLess(order.index(f"{game}_origins_village_wide_upgrades"),
                                order.index(feature_id(game)))

    def test_patches_no_executable_byte_and_pins_its_companion(self):
        digest = hashlib.sha256(DLL.read_bytes()).hexdigest().upper()
        for game in GAMES:
            with self.subTest(game=game):
                row = manifest(game)
                self.assertEqual(row["patches"], [])
                self.assertEqual(row["companion_files"], [{
                    "source": "assets/story_upgrades/VVFP Story Upgrades.dll",
                    "destination": "VVFP Story Upgrades.dll",
                    "sha256": digest,
                }])

    def test_the_render_is_byte_identical_without_the_row(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    self.assertEqual(render(game, mode, True), render(game, mode, False))


# ---------------------------------------------------------------------------
# Install: all or nothing, and only the listed sites
# ---------------------------------------------------------------------------

@emulated
class InstallTests(unittest.TestCase):
    def test_every_mode_installs_every_site_and_nothing_else(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                with self.subTest(game=game, mode=mode):
                    proc = process(game, mode)
                    base = proc.image_base
                    size = len(proc.read(base, 0x1000)) and pefile.PE(
                        data=render(game, mode), fast_load=True).OPTIONAL_HEADER.SizeOfImage
                    before = proc.read(base, size)
                    table = sites(proc, game)
                    self.assertEqual(proc.export("VvfpStoryInstall", int(game[2:])), 1)
                    self.assertEqual(proc.export("VvfpStoryActive", int(game[2:])), 1)
                    after = proc.read(base, size)
                    touched = set()
                    for va, expect, replace in table:
                        self.assertEqual(before[va - base:va - base + len(expect)], expect, hex(va))
                        self.assertEqual(after[va - base:va - base + len(replace)], replace, hex(va))
                        touched.update(range(va - base, va - base + len(expect)))
                    changed = {i for i in range(size) if before[i] != after[i]}
                    self.assertTrue(changed <= touched, sorted(hex(i + base) for i in changed - touched)[:5])

    def test_the_manifest_lists_exactly_the_companions_sites(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc = process(game)
                table = sites(proc, game)
                detours = manifest(game)["runtime_detours"]
                self.assertEqual(len(detours), len(table))
                for (va, expect, replace), entry in zip(table, detours):
                    self.assertEqual(int(entry["va"], 16), va)
                    self.assertEqual(bytes.fromhex(entry["stock_bytes"]), expect)
                    if "written_bytes" in entry:
                        self.assertEqual(bytes.fromhex(entry["written_bytes"]), replace)

    def test_one_wrong_byte_anywhere_installs_nothing(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            proc = process(game)
            table = sites(proc, game)
            for victim in (0, len(table) // 2, len(table) - 1):
                with self.subTest(game=game, site=hex(table[victim][0])):
                    data = bytearray(render(game, "collection_progression"))
                    pe = pefile.PE(data=bytes(data), fast_load=True)
                    va, expect, _ = table[victim]
                    data[pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)] ^= 0xFF
                    broken = Process(bytes(data), TEST_DLL)
                    snapshot = [broken.read(v, len(e)) for v, e, _ in table]
                    self.assertEqual(broken.export("VvfpStoryInstall", int(game[2:])), 0)
                    self.assertEqual(broken.export("VvfpStoryActive", int(game[2:])), 0)
                    self.assertEqual([broken.read(v, len(e)) for v, e, _ in table], snapshot)

    def test_a_build_without_origins_installs_nothing(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                proc = Process(stock_path(game).read_bytes(), TEST_DLL)
                self.assertEqual(proc.export("VvfpStoryInstall", int(game[2:])), 0)


# ---------------------------------------------------------------------------
# Every Origins price is 0 once installed -- executed
# ---------------------------------------------------------------------------

def _price_instructions(proc, game):
    """(va, insn bytes before, after) for each instruction site the companion
    rewrites (tables and strings are checked separately)."""
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    out = []
    for va, expect, replace in sites(proc, game):
        insns = list(md.disasm(expect, va))
        if len(insns) == 1 and insns[0].size == len(expect) and any(
                op.type == X86_OP_IMM and abs(op.imm if op.imm < 0x80000000 else op.imm - (1 << 32)) in PRICES
                for op in insns[0].operands):
            out.append((va, expect, replace))
    return out


def _execute_one(proc, va, balance):
    """Execute the single instruction at `va` with every register pointing at
    a zeroed scratch area whose dwords (and any absolute operand) hold
    `balance`.  Returns (mnemonic, CF, destination value or pushed value)."""
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = True
    insn = next(md.disasm(proc.read(va, 16), va))
    scratch = HEAP + 0x100000
    proc.write(scratch - 0x1000, struct.pack("<I", balance) * (0x50000 // 4))
    for reg in ("eax", "ebx", "ecx", "edx", "esi", "edi", "ebp"):
        proc.set_reg(reg, scratch)
    proc.set_reg("esp", HEAP + 0x3000000)
    target = None
    if insn.mnemonic in ("cmp", "sub", "add") and insn.operands[0].type == X86_OP_REG:
        # `cmp eax, price` / `sub eax, price`: the register holds the balance
        # the routine loaded (or read back) just before.
        proc.mu.reg_write(insn.operands[0].reg, balance)
    for op in insn.operands:
        if op.type == X86_OP_MEM:
            if op.mem.base == 0:
                target = op.mem.disp & 0xFFFFFFFF
                proc.put32(target, balance)
            else:
                target = (scratch + op.mem.disp) & 0xFFFFFFFF
    proc.mu.emu_start(va, va + insn.size, count=1)
    cf = proc.mu.reg_read(UC_X86_REG_EFLAGS) & 1
    if insn.mnemonic == "push":
        value = proc.u32(proc.reg("esp"))
    elif target is not None and insn.mnemonic in ("sub", "add"):
        value = proc.u32(target)
    elif insn.operands and insn.operands[0].type == X86_OP_REG:
        value = proc.mu.reg_read(insn.operands[0].reg)
    else:
        value = None
    return insn.mnemonic, cf, value


@emulated
class CostZeroTests(unittest.TestCase):
    def test_every_price_instruction_charges_nothing_in_every_mode(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            for mode in MODES:
                proc = process(game, mode)
                instructions = _price_instructions(proc, game)
                self.assertTrue(instructions)
                self.assertEqual(proc.export("VvfpStoryInstall", int(game[2:])), 1)
                for va, before, after in instructions:
                    with self.subTest(game=game, mode=mode, site=hex(va)):
                        mnemonic, cf, value = _execute_one(proc, va, 0)
                        if mnemonic == "cmp":
                            self.assertEqual(cf, 0, "a balance of 0 is refused")
                        elif mnemonic in ("sub", "add"):
                            self.assertEqual(value, 0, "the balance moved")
                        elif mnemonic in ("push", "mov"):
                            self.assertEqual(value, 0, "a price is still passed on")
                        else:
                            self.fail(f"unexpected price instruction {mnemonic}")

    def test_before_the_install_the_same_instructions_charge(self):
        """The check above is live: stock Origins refuses or charges 0 points."""
        for game in GAMES:
            if not have_stock(game):
                continue
            proc = process(game)
            for va, before, after in _price_instructions(proc, game):
                with self.subTest(game=game, site=hex(va)):
                    mnemonic, cf, value = _execute_one(proc, va, 0)
                    if mnemonic == "cmp":
                        self.assertEqual(cf, 1)
                    else:
                        self.assertNotEqual(value, 0)

    def test_price_tables_and_prompts_read_zero(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            proc = process(game)
            table = sites(proc, game)
            self.assertEqual(proc.export("VvfpStoryInstall", int(game[2:])), 1)
            for va, expect, replace in table:
                if len(expect) % 4 == 0 and len(expect) >= 40 and all(
                        v in PRICES for v in struct.unpack(f"<{len(expect) // 4}I", expect)):
                    with self.subTest(game=game, table=hex(va)):
                        self.assertEqual(proc.read(va, len(expect)), bytes(len(expect)))
                elif all(32 <= b < 127 for b in expect):
                    with self.subTest(game=game, string=hex(va)):
                        text = proc.cstring(va)
                        self.assertNotRegex(text, r"\d{1,3},\d{3}")
                        self.assertRegex(text, r"\b0[ -]")

    def test_the_rendered_origins_bytes_hold_no_other_price(self):
        """The generator's completeness check, re-run: every price an Origins
        row's bytes hold is one the companion zeroes."""
        import build_story_cheat_upgrades_features as gen

        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                minimal, full = gen._feature_ids(patcher, game)
                image = gen.Image(gen._render(patcher, game, "collection_progression", full))
                gen._price_sites(patcher, game, image, full, gen._price_writes(game, image))


@emulated
class ChargePathTests(unittest.TestCase):
    """Whole Origins charge paths, run with a balance of 0 after the install."""

    def test_vv1_rows_one_to_four_buy_for_nothing(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        proc = process("vv1")
        proc.export("VvfpStoryInstall", 1)
        world = proc.alloc(0xB000)
        for row in (1, 2, 3, 4):
            with self.subTest(row=row):
                proc.put32(world + 0xA2FC, 0)
                proc.set_reg("ebx", row)
                proc.set_reg("edi", world)
                proc.run(0x456B03, 0x456B1C)        # load, cmp/jb, sub, cmp ebx,1
                self.assertEqual(proc.u32(world + 0xA2FC), 0)

    def test_vv2_rows_one_three_four_buy_for_nothing(self):
        if not have_stock("vv2"):
            self.skipTest("no stock executable")
        proc = process("vv2")
        proc.export("VvfpStoryInstall", 2)
        world = proc.alloc(0x31000)
        for row in (1, 3, 4):
            with self.subTest(row=row):
                proc.put32(world + 0x2EADC, 0)
                proc.set_reg("ebx", row)
                proc.set_reg("edi", world)
                proc.run(0x49475E, 0x49477C)
                self.assertEqual(proc.u32(world + 0x2EADC), 0)

    def test_vv3_island_event_buys_for_nothing_and_keeps_its_lock(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        proc = process("vv3")
        proc.export("VvfpStoryInstall", 3)
        proc.put32(0x582644, 0)
        proc.write(0x6E0050, b"\0")
        proc.set_reg("ebx", 1)
        proc.run(0x4A3623, 0x4A3654)              # through the pending check and the sub
        self.assertEqual(proc.u32(0x582644), 0)
        # With an island event pending, the same path still refuses (code 10).
        proc.write(0x6E0050, b"\1")
        proc.set_reg("ebx", 1)
        proc.run(0x4A3623, 0x4A3739)
        self.assertEqual(proc.reg("eax"), 10)


# ---------------------------------------------------------------------------
# Pick Island Event: the game's own chooser runs the picked event
# ---------------------------------------------------------------------------

def _rand_script(values):
    values = list(values)

    def rand(proc):
        bound = proc.arg(0)
        value = values.pop(0) if values else 0
        assert 0 <= value < bound, (value, bound)
        return value, 0
    return rand


def _position(game: str, slot: int) -> int:
    return [e["slot"] for e in story_island_events.EVENTS[game]].index(slot)


class _ObjectTable:
    """Fake event objects whose condition (vtable[1]) answers per slot."""

    def __init__(self, proc, table_va, count, ok):
        self.proc = proc
        self.answer = dict(ok)
        self.condition = proc.alloc(0x100)
        proc.write(self.condition, b"\xC3")
        self.objects = {}
        for slot in range(1, count + 1):
            obj = proc.alloc(0x40)
            vtable = proc.alloc(0x40)
            proc.put32(obj, vtable)
            proc.put32(obj + 0x30, slot)
            proc.put32(vtable + 4, self.condition)
            proc.put32(table_va + 4 * slot, obj)
            self.objects[slot] = obj

        def condition(p):
            slot = p.u32(p.reg("ecx") + 0x30)
            return (1 if self.answer.get(slot, True) else 0), 0
        proc.stub(self.condition, condition)


SELECTORS = {
    # game: (event table, slots, hook site, resume, register holding the object)
    "vv3": (0x4B3C78, 57, 0x419BDB, 0x419BE2, "edx"),
    "vv4": (0x4CCA28, 49, 0x4180F7, 0x4180FE, "eax"),
    "vv5": (0x4DC850, 55, 0x41895B, 0x418962, "eax"),
}


@emulated
class TablePickTests(unittest.TestCase):
    """VV3-VV5: the replacement at the point the selector has chosen."""

    def _at_site(self, game, *, pick_slot=None, ok=None, chosen=2, tick=0, arm_tick=0,
                 host=None, between=None):
        table, count, site, resume, register = SELECTORS[game]
        proc = process(game)
        n = int(game[2:])
        self.assertEqual(proc.export("VvfpStoryInstall", n), 1)
        if host is not None:
            import test_story_custom_island_event as part2

            host = part2.Host(proc, n, host)
        objects = _ObjectTable(proc, table, count, ok or {})
        if pick_slot is not None:
            self.assertEqual(proc.export("VvfpStoryProbeSetPick", n, _position(game, pick_slot), arm_tick),
                             pick_slot)
        if between is not None:
            between(proc, n, host)
        proc.export("VvfpStoryProbeSetTick", tick)
        proc.set_reg("esi", chosen)
        proc.set_reg("esp", HEAP + 0x3000000)
        proc.run(site, resume)
        return proc, objects, proc.reg("esi"), proc.reg(register)

    def test_no_pick_keeps_the_games_choice(self):
        for game in SELECTORS:
            with self.subTest(game=game):
                proc, objects, esi, obj = self._at_site(game, chosen=3)
                self.assertEqual((esi, obj), (3, objects.objects[3]))

    def test_the_pick_replaces_the_choice_when_its_condition_holds(self):
        for game in SELECTORS:
            slot = story_island_events.EVENTS[game][-1]["slot"]
            with self.subTest(game=game, slot=slot):
                proc, objects, esi, obj = self._at_site(game, pick_slot=slot, chosen=3)
                self.assertEqual((esi, obj), (slot, objects.objects[slot]))
                self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 0xFFFFFFFF, "consumed")

    def test_a_false_condition_keeps_the_games_choice_and_says_so(self):
        for game in SELECTORS:
            slot = story_island_events.EVENTS[game][4]["slot"]
            with self.subTest(game=game, slot=slot):
                proc, objects, esi, obj = self._at_site(game, pick_slot=slot, ok={slot: False}, chosen=3)
                self.assertEqual((esi, obj), (3, objects.objects[3]))
                self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 0xFFFFFFFF)
                stats = proc.read(proc.exports["VvfpStoryStats"], 12)
                self.assertEqual(struct.unpack("<3i", stats), (0, 1, 0))

    def test_a_pick_never_reaches_another_village(self):
        """Picked in one village, then another slot loaded, Start Over or a
        tribe deleted: the game keeps its own choice."""
        def other_slot(proc, n, host):
            host.slot = 3

        def reset(proc, n, host):
            proc.export("VvfpStoryVillageReset", n, 2)

        def same(proc, n, host):
            host.slot = 2
        for game in SELECTORS:
            slot = story_island_events.EVENTS[game][-1]["slot"]
            for case, between in (("other slot", other_slot), ("start over", reset)):
                with self.subTest(game=game, case=case):
                    proc, objects, esi, obj = self._at_site(game, pick_slot=slot, chosen=3, host=2,
                                                            between=between)
                    self.assertEqual((esi, obj), (3, objects.objects[3]))
                    self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 0xFFFFFFFF, "discarded")
                    stats = struct.unpack("<4i", proc.read(proc.exports["VvfpStoryStats"], 16))
                    self.assertEqual(stats, (0, 0, 0, 1))
            with self.subTest(game=game, case="same village"):
                proc, objects, esi, obj = self._at_site(game, pick_slot=slot, chosen=3, host=2,
                                                        between=same)
                self.assertEqual((esi, obj), (slot, objects.objects[slot]))

    def test_a_pick_older_than_ten_minutes_lapses(self):
        for game in SELECTORS:
            slot = story_island_events.EVENTS[game][0]["slot"]
            with self.subTest(game=game):
                proc, objects, esi, obj = self._at_site(
                    game, pick_slot=slot, chosen=3, arm_tick=1000, tick=1000 + TEN_MINUTES + 1)
                self.assertEqual(esi, 3)
                stats = struct.unpack("<3i", proc.read(proc.exports["VvfpStoryStats"], 12))
                self.assertEqual(stats, (0, 0, 1))

    def test_vv3_never_spends_a_pick_on_the_origins_barrel(self):
        """The Origins barrel points every slot at the barrel object and calls
        the same selector; a pick must survive that, not become the barrel."""
        game = "vv3"
        table, count, site, resume, register = SELECTORS[game]
        proc = process(game)
        proc.export("VvfpStoryInstall", 3)
        barrel = proc.alloc(0x40)
        for slot in range(1, count + 1):
            proc.put32(table + 4 * slot, barrel)
        proc.export("VvfpStoryProbeSetPick", 3, _position(game, 12), 0)
        proc.export("VvfpStoryProbeSetTick", 0)
        proc.set_reg("esi", 57)
        proc.set_reg("esp", HEAP + 0x3000000)
        proc.run(site, resume)
        self.assertEqual(proc.reg("esi"), 57)
        self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 12, "still armed")


@emulated
class SelectorRunTests(unittest.TestCase):
    """VV3-VV5: the game's whole selector, from its entry to the point where
    it hands the chosen event object to its presenter."""

    def _run(self, game, *, pick_slot=None, rands=(), rescue=False):
        table, count, site, resume, register = SELECTORS[game]
        proc = process(game)
        n = int(game[2:])
        proc.export("VvfpStoryInstall", n)
        objects = _ObjectTable(proc, table, count, {})
        if pick_slot is not None:
            proc.export("VvfpStoryProbeSetPick", n, _position(game, pick_slot), 0)
        proc.export("VvfpStoryProbeSetTick", 0)
        rand = _rand_script(rands)
        if game == "vv3":
            proc.stub(0x4032D0, rand)
            proc.stub(0x45FDE0, lambda p: (0 if rescue else 0xFFFFFFFF, 0))
            proc.stub(0x45E8F0, lambda p: (10, 0))
            entry, args = 0x419B30, [0x12345]
        elif game == "vv4":
            proc.stub(0x4036D0, rand)
            proc.stub(0x412F90, lambda p: (0, 8))
            proc.stub(0x448E10, lambda p: (0, 4))
            proc.stub(0x468300, lambda p: (0 if rescue else 0xFFFFFFFF, 0))
            proc.stub(0x467610, lambda p: (10, 0))
            entry, args = 0x418000, [0x12345]
        else:
            proc.stub(0x403660, rand)
            proc.stub(0x413450, lambda p: (0, 8))
            proc.stub(0x472B80, lambda p: (0 if rescue else 0xFFFFFFFF, 0))
            proc.stub(0x4713F0, lambda p: (10, 0))
            entry, args = 0x418870, [0x12345]
        proc.call(entry, args, until=resume)
        return objects, proc.reg("esi"), proc.reg(register)

    def test_the_games_own_selector_delivers_the_pick(self):
        for game in SELECTORS:
            slot = story_island_events.EVENTS[game][len(story_island_events.EVENTS[game]) // 2]["slot"]
            with self.subTest(game=game, slot=slot):
                # every condition true: the list holds every slot; the roll picks index 0
                objects, esi, obj = self._run(game, pick_slot=slot, rands=(0, 99, 99))
                self.assertEqual((esi, obj), (slot, objects.objects[slot]))

    def test_without_a_pick_the_selector_is_stock(self):
        for game in SELECTORS:
            with self.subTest(game=game):
                objects, esi, obj = self._run(game, rands=(4, 99, 99))
                self.assertEqual((esi, obj), (5, objects.objects[5]))

    def test_the_pick_also_wins_over_the_games_rescue_override(self):
        """VV3-VV5 force a rescue event (canoe/barrel/chutes) in a tiny
        village; a pick is applied after that override."""
        for game, forced in (("vv3", 57), ("vv4", 25), ("vv5", 30)):
            slot = story_island_events.EVENTS[game][2]["slot"]
            with self.subTest(game=game):
                objects, esi, _ = self._run(game, rands=(0, 99, 0))
                self.assertEqual(esi, 1)        # no rescue without the low-population gate
                objects, esi, _ = self._run(game, rands=(0, 99, 0), rescue=True)
                self.assertEqual(esi, forced, "the stock rescue override")
                objects, esi, obj = self._run(game, pick_slot=slot, rands=(0, 99, 0), rescue=True)
                self.assertEqual((esi, obj), (slot, objects.objects[slot]))


@emulated
class FamilyPickTests(unittest.TestCase):
    """VV1 and VV2: each chooser's own roll returns the picked event, once."""

    def _roll(self, proc, site, bound):
        """Run the rewritten `call` at `site` as the game does: push bound."""
        esp = HEAP + 0x3000000
        proc.put32(esp, bound)
        proc.set_reg("esp", esp)
        proc.run(site, site + 5)
        return proc.reg("eax")

    def _proc(self, game, slot, rand_va, rands=()):
        proc = process(game)
        n = int(game[2:])
        proc.export("VvfpStoryInstall", n)
        proc.stub(rand_va, _rand_script(rands))
        proc.export("VvfpStoryProbeSetTick", 0)
        if slot is not None:
            proc.export("VvfpStoryProbeSetPick", n, _position(game, slot), 0)
        return proc

    def test_vv1_family_rolls(self):
        for family, first, second in ((0, 99, 0), (1, 0, None), (2, 99, 99)):
            slot = (family << 6) | (9 if family == 0 else 3)
            with self.subTest(family=family):
                proc = self._proc("vv1", slot, 0x402F10)
                self.assertEqual(self._roll(proc, 0x423818, 100), first)
                if second is not None:
                    self.assertEqual(self._roll(proc, 0x42383A, 100), second)
        proc = self._proc("vv1", None, 0x402F10, rands=(42, 17))
        self.assertEqual(self._roll(proc, 0x423818, 100), 42, "no pick: the game's roll")
        self.assertEqual(self._roll(proc, 0x42383A, 100), 17)

    def test_vv1_island_selector_dispatches_the_picked_case(self):
        """0x428470, the game's own selector (behind Origins' barrel cave), runs
        the picked case through 0x427CA0 with the game's own magnitude."""
        proc = self._proc("vv1", 9, 0x402F10, rands=(3,))
        world = proc.alloc(0xB000)
        proc.write(world + 0x9FB8, b"\1")           # The Big Wave's own condition
        event = proc.alloc(0x5100)
        proc.put32(event + 0x50A4, world)
        dispatched = []
        proc.stub(0x427CA0, lambda p: (dispatched.append((p.arg(0), p.arg(1))) or 0, 8))
        proc.call(0x428470, [2, 6], ecx=event)
        self.assertEqual(dispatched, [(9, 6)])
        # Taken once: the next selection is the game's own.
        proc.stub(0x402F10, _rand_script((13,)))
        proc.call(0x428470, [2, 6], ecx=event)
        self.assertEqual(dispatched[-1], (13, 6))

    def test_vv1_a_failed_condition_falls_back_to_the_games_reroll(self):
        """Forced once: an impossible pick (Big Wave on an uncleaned beach)
        cannot hang the selector -- the re-roll is the game's own."""
        proc = self._proc("vv1", 9, 0x402F10, rands=(13,))
        world = proc.alloc(0xB000)                 # [9FB8] == 0: condition false
        event = proc.alloc(0x5100)
        proc.put32(event + 0x50A4, world)
        dispatched = []
        proc.stub(0x427CA0, lambda p: (dispatched.append((p.arg(0), p.arg(1))) or 0, 8))
        proc.call(0x428470, [2, 6], ecx=event)
        self.assertEqual(dispatched, [(13, 6)])

    def test_vv1_the_barrel_purchase_still_reaches_case_12(self):
        proc = self._proc("vv1", 9, 0x402F10)
        event = proc.alloc(0x5100)
        dispatched = []
        proc.stub(0x427CA0, lambda p: (dispatched.append((p.arg(0), p.arg(1))) or 0, 8))
        proc.call(0x428470, [1, 0x7F4B1A2C], ecx=event)
        self.assertEqual(dispatched, [(12, 10)])
        self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), 9, "the barrel leaves the pick armed")

    def test_vv1_encounter_chooser_returns_the_picked_variant(self):
        proc = self._proc("vv1", (1 << 6) | 14, 0x402F10)
        event = proc.alloc(0x5100)
        proc.put32(event + 0x50A4, proc.alloc(0xB000))
        self.assertEqual(proc.call(0x418920, [], ecx=event), 14)

    def test_vv1_crate_roll_returns_the_picked_variant(self):
        proc = self._proc("vv1", (2 << 6) | 4, 0x402F10)
        self.assertEqual(self._roll(proc, 0x42B03E, 9), 4)

    def test_vv2_family_rolls(self):
        for family, first, second in ((0, 99, 0), (1, 0, None), (2, 99, 99)):
            slot = (family << 6) | 5
            with self.subTest(family=family):
                proc = self._proc("vv2", slot, 0x4031A0)
                self.assertEqual(self._roll(proc, 0x42EF28, 100), first)
                if second is not None:
                    self.assertEqual(self._roll(proc, 0x42EF4A, 100), second)

    def test_vv2_single_result_selector_dispatches_the_picked_case(self):
        proc = self._proc("vv2", (0 << 6) | 22, 0x4031A0)
        event = proc.alloc(0x5100)
        dispatched = []
        proc.stub(0x433600, lambda p: (dispatched.append((p.arg(0), p.arg(1))) or 0, 8))
        proc.call(0x434570, [2, 7], ecx=event)
        self.assertEqual(dispatched, [(22, 7)])

    def test_vv2_two_choice_selector_returns_the_picked_event(self):
        proc = self._proc("vv2", (1 << 6) | 16, 0x4031A0)
        event = proc.alloc(0x5100)
        self.assertEqual(proc.call(0x41F570, [], ecx=event), 16)

    def test_vv2_sack_roll_returns_the_picked_variant(self):
        proc = self._proc("vv2", (2 << 6) | 6, 0x4031A0)
        self.assertEqual(self._roll(proc, 0x437B0E, 8), 6)

    def test_a_pick_of_another_family_leaves_the_roll_alone(self):
        proc = self._proc("vv1", (1 << 6) | 3, 0x402F10, rands=(7,))
        self.assertEqual(self._roll(proc, 0x4284DB, 15), 7)
        self.assertEqual(proc.export("VvfpStoryProbeArmedSlot"), (1 << 6) | 3)


# ---------------------------------------------------------------------------
# Arming: the Island Event purchase's own writes, and its lock
# ---------------------------------------------------------------------------

CLOCK = 1_700_000_000


@emulated
class LockTests(unittest.TestCase):
    def _world(self, proc, game):
        if game == "vv1":
            world = proc.alloc(0xB000)
            proc.put32(0x48AEDC, world)
            proc.put32(world + 0xA300, CLOCK + 36000)
            proc.stub(0x402F70, lambda p: (CLOCK, 0))
        elif game == "vv2":
            world = proc.alloc(0x31000)
            proc.put32(0x4997BC, world)
            proc.put32(world + 0x2EAE0, CLOCK + 36000)
            proc.stub(0x403200, lambda p: (CLOCK, 0))
        elif game == "vv3":
            world = proc.alloc(0x13000)
            proc.put32(0x4B309C, world)
            proc.write(0x6E0050, b"\0")
            proc.stub(0x403330, lambda p: (CLOCK, 0))
        elif game == "vv4":
            world = proc.alloc(0x18000)
            proc.put32(0x4CB51C, world)
            proc.put32(world + 0x170E0, CLOCK + 36000)
            proc.write(0x728B04, b"\0\0\0\0\0\0\0\0\0\0\0\0")
            proc.stub(0x403750, lambda p: (CLOCK, 0))
        else:
            world = proc.alloc(0x18000)
            proc.put32(0x4DACE0, world)
            proc.put32(world + 0x17D3C, CLOCK + 36000)
            proc.put32(0x51D388, 0)
        return world

    def _purchase(self, proc, game, world):
        """The Origins Island Event purchase's own code, on `world`."""
        proc.set_reg("esp", HEAP + 0x3000000)
        if game == "vv1":
            proc.set_reg("edi", world)
            proc.run(0x456B3B, 0x456B4D)
        elif game == "vv2":
            proc.set_reg("edi", world)
            proc.set_reg("esp", HEAP + 0x3000000)
            proc.run(0x494818, 0x49482A)
        elif game == "vv3":
            proc.call(0x6DF340, [], ecx=world)
        elif game == "vv4":
            proc.stub(0x41FE70, lambda p: (world, 0))
            proc.set_reg("esp", HEAP + 0x3000000)
            proc.run(0x4897A7, 0x4897CA)
        else:
            proc.set_reg("edi", world)
            proc.run(0x7CCCFC, 0x7CCD16)

    STATE = {
        "vv1": lambda w: ((w, 0xA300, 4),),
        "vv2": lambda w: ((w, 0x2EAE0, 4),),
        "vv3": lambda w: ((w, 0x12EF4, 4), (0x6E0050, 0, 1), (0x6E0054, 0, 4)),
        "vv4": lambda w: ((w, 0x170E0, 4), (0x728B08, 0, 1), (0x728B0C, 0, 4)),
        "vv5": lambda w: ((w, 0x17D3C, 4), (0x51D388, 0, 4)),
    }

    def test_arming_writes_exactly_what_the_island_event_purchase_writes(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                picked = process(game)
                picked_world = self._world(picked, game)
                self.assertEqual(picked.export("VvfpStoryProbePending", n), 0)
                slot = story_island_events.EVENTS[game][0]["slot"]
                self.assertEqual(picked.export("VvfpStoryProbeArm", n, 0, 0), slot)
                bought = process(game)
                bought_world = self._world(bought, game)
                self._purchase(bought, game, bought_world)
                for (base_p, off, size), (base_b, _, _) in zip(
                        self.STATE[game](picked_world), self.STATE[game](bought_world)):
                    self.assertEqual(picked.read(base_p + off, size), bought.read(base_b + off, size),
                                     hex(off))

    def test_an_armed_pick_is_the_island_events_lock(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = process(game)
                self._world(proc, game)
                proc.export("VvfpStoryInstall", n)
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                self.assertEqual(proc.export("VvfpStoryProbePending", n), 1)
                self.assertEqual(proc.export("VvfpStoryPickPending", n), 1)
                # A second pick is refused before any dialog (DialogBoxParamA
                # is not stubbed: reaching it would fail the run).
                self.assertEqual(proc.export("VvfpStoryPickIslandEvent", n, 0), 0)
                self.assertIn("already queued", proc.messages[-1])

    def test_the_games_own_pending_check_sees_the_pick(self):
        """The Tech menu's own state word marks the Island Event row pending."""
        for game in ("vv1", "vv2", "vv4", "vv5"):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                n = int(game[2:])
                proc = process(game)
                world = self._world(proc, game)
                proc.export("VvfpStoryProbeArm", n, 0, 0)
                if game == "vv1":
                    menu = proc.alloc(0x100)
                    proc.put32(menu + 0xC, world)
                    proc.call(0x48DF00, [], regs={"esi": menu, "edi": 0})
                    state = proc.reg("edi")
                elif game == "vv2":
                    proc.set_reg("esp", HEAP + 0x3000000)
                    proc.set_reg("eax", 0)
                    proc.set_reg("edi", world)
                    proc.run(0x49C280, 0x49C2A7)
                    state = proc.reg("eax")
                elif game == "vv4":
                    proc.call(0x728C20, [], regs={"eax": 0})
                    state = proc.reg("eax")
                else:
                    proc.call(0x7C9A22, [], regs={"eax": 0})
                    state = proc.reg("eax")
                self.assertTrue(state & 0x800000, hex(state))

    def test_vv3_the_companion_flag_is_the_purchase_flag(self):
        if not have_stock("vv3"):
            self.skipTest("no stock executable")
        proc = process("vv3")
        self._world(proc, "vv3")
        proc.export("VvfpStoryProbeArm", 3, 0, 0)
        self.assertEqual(proc.read(0x6E0050, 1), b"\1", "the flag the Island Event row refuses on")


# ---------------------------------------------------------------------------
# The events offered
# ---------------------------------------------------------------------------

class EventListTests(unittest.TestCase):
    def test_every_offered_title_is_the_games_own_text(self):
        for game in GAMES:
            if not have_stock(game):
                continue
            data = stock_path(game).read_bytes()
            for event in story_island_events.EVENTS[game]:
                with self.subTest(game=game, title=event["title"]):
                    self.assertIn(event["title"].encode("latin-1"), data)

    def test_slots_are_unique_and_each_has_a_description(self):
        for game in GAMES:
            events = story_island_events.EVENTS[game]
            with self.subTest(game=game):
                self.assertEqual(len({e["slot"] for e in events}), len(events))
                labels = [(e["title"], e["variant"]) for e in events]
                self.assertEqual(len(set(labels)), len(labels), "duplicate titles need a variant")
                for e in events:
                    self.assertTrue(e["description"].strip())
                    self.assertTrue(e["requires"].strip())

    def test_the_rows_list_the_events_and_the_exclusions(self):
        for game in GAMES:
            with self.subTest(game=game):
                row = manifest(game)
                self.assertEqual([e["slot"] for e in row["island_events"]],
                                 [e["slot"] for e in story_island_events.EVENTS[game]])
                self.assertEqual(row["excluded_island_events"], story_island_events.EXCLUDED[game])
                self.assertTrue(row["excluded_island_events"])


class DeadEventTests(unittest.TestCase):
    """The excluded events can never run in the shipping game, read from it."""

    def _image(self, game):
        data = stock_path(game).read_bytes()
        pe = pefile.PE(data=data, fast_load=True)
        return data, pe

    def _read(self, game, va, n):
        data, pe = self._image(game)
        o = pe.get_offset_from_rva(va - pe.OPTIONAL_HEADER.ImageBase)
        return data[o:o + n]

    @unittest.skipUnless(HAVE_EMULATOR, "pefile not installed")
    def test_vv1_storm_and_furry_food_always_reroll(self):
        if not have_stock("vv1"):
            self.skipTest("no stock executable")
        island_class = self._read("vv1", 0x4286A0, 15)
        island_jump = struct.unpack("<6I", self._read("vv1", 0x428688, 24))
        self.assertEqual(island_jump[island_class[1]], 0x4284D6, "case 1 -> the re-roll")
        # 0x4284D6 is the head of the selector's roll: `mov eax,[esp+14h]; push eax; call rand`.
        self.assertEqual(self._read("vv1", 0x4284D6, 6), bytes.fromhex("8B442414 50 E8".replace(" ", "")))
        encounter_class = self._read("vv1", 0x4189A4, 16)
        encounter_jump = struct.unpack("<5I", self._read("vv1", 0x418990, 20))
        self.assertEqual(encounter_jump[encounter_class[5]], 0x418930, "variant 5 -> the re-roll")
        offered = {e["slot"] for e in story_island_events.EVENTS["vv1"]}
        self.assertNotIn(1, offered)
        self.assertNotIn((1 << 6) | 5, offered)
        # Every other case and variant is offered.
        self.assertEqual({s for s in offered if s >> 6 == 0}, set(range(15)) - {1})
        self.assertEqual({s & 0x3F for s in offered if s >> 6 == 1}, set(range(16)) - {5})
        self.assertEqual({s & 0x3F for s in offered if s >> 6 == 2}, set(range(9)))

    @unittest.skipUnless(HAVE_EMULATOR, "pefile not installed")
    def test_vv2_cases_never_valid(self):
        if not have_stock("vv2"):
            self.skipTest("no stock executable")
        table = struct.unpack("<28I", self._read("vv2", 0x434868, 28 * 4))
        never = {i for i, target in enumerate(table) if target == 0x434824}
        self.assertEqual(never, {4, 18, 20, 26})
        offered = {e["slot"] for e in story_island_events.EVENTS["vv2"] if e["slot"] >> 6 == 0}
        self.assertEqual(offered, set(range(28)) - never)
        self.assertEqual({e["slot"] & 0x3F for e in story_island_events.EVENTS["vv2"] if e["slot"] >> 6 == 1},
                         set(range(21)))
        self.assertEqual({e["slot"] & 0x3F for e in story_island_events.EVENTS["vv2"] if e["slot"] >> 6 == 2},
                         set(range(8)))

    @unittest.skipUnless(HAVE_EMULATOR, "capstone not installed")
    def test_vv4_and_vv5_dead_conditions_are_xor_al_ret(self):
        import test_vv5_barrel_event_index as vv5index

        for game, dead_fn, table_ctor in (("vv4", 0x4146E0, None), ("vv5", 0x415B10, None)):
            if not have_stock(game):
                continue
            with self.subTest(game=game):
                self.assertEqual(self._read(game, dead_fn, 3), bytes.fromhex("32C0C3"))
        if have_stock("vv5"):
            image = vv5index.VV5Image(stock_path("vv5"))
            old = vv5index.CONSTRUCTOR_END
            vv5index.CONSTRUCTOR_END = 0x418020
            try:
                slots, vtables = vv5index._walk_constructor(image)
            finally:
                vv5index.CONSTRUCTOR_END = old
            dead = {s for s, vt in vtables.items() if image.u32(vt + 4) == 0x415B10}
            self.assertEqual(dead, {25, 29, 33, 48, 49, 50, 51, 52, 53, 54})
            offered = {e["slot"] for e in story_island_events.EVENTS["vv5"]}
            self.assertEqual(offered, set(slots) - dead)

    def test_vv3_and_vv4_offer_every_live_slot(self):
        self.assertEqual({e["slot"] for e in story_island_events.EVENTS["vv3"]}, set(range(1, 58)))
        self.assertEqual({e["slot"] for e in story_island_events.EVENTS["vv4"]},
                         set(range(1, 50)) - {1, 6, 16, 19, 24})


# ---------------------------------------------------------------------------
# Conditions the chooser checks before offering an event
# ---------------------------------------------------------------------------

@emulated
class ConditionTests(unittest.TestCase):
    def test_vv1_the_big_wave_needs_a_cleaned_beach(self):
        proc = process("vv1")
        world = proc.alloc(0xB000)
        records = proc.alloc(0x3E100)
        proc.put32(0x48AEDC, world)
        proc.put32(0x48B614, records)
        proc.put32(world + 0x9E40, 3)                    # not the first event
        proc.write(records + 0x28, b"\1")                # one living adult
        proc.put32(records + 0x344, 100)
        proc.put32(records + 0x348, 400)
        big_wave = _position("vv1", 9)
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, big_wave), 0)
        proc.write(world + 0x9FB8, b"\1")
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, big_wave), 1)
        # The first island event of a village is always an encounter.
        proc.put32(world + 0x9E40, 0)
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, big_wave), 0)
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, _position("vv1", (1 << 6) | 1)), 1)

    def test_vv1_measles_needs_a_child_and_nothing_runs_without_an_adult(self):
        proc = process("vv1")
        world = proc.alloc(0xB000)
        records = proc.alloc(0x3E100)
        proc.put32(0x48AEDC, world)
        proc.put32(0x48B614, records)
        proc.put32(world + 0x9E40, 3)
        measles = _position("vv1", 4)
        proc.write(records + 0x28, b"\1")
        proc.put32(records + 0x344, 100)
        proc.put32(records + 0x348, 100)                 # a child only
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, measles), 0, "no adult: no event")
        rec2 = records + 0x3D8
        proc.write(rec2 + 0x28, b"\1")
        proc.put32(rec2 + 0x344, 100)
        proc.put32(rec2 + 0x348, 400)
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, measles), 1)
        proc.put32(records + 0x344, 0)                   # the child has died
        self.assertEqual(proc.export("VvfpStoryProbePossible", 1, measles), 0)

    def test_vv2_a_dangerous_mission_needs_more_than_sixty(self):
        proc = process("vv2")
        world = proc.alloc(0x31000)
        pool = proc.alloc(0xE58000)
        proc.put32(0x4997BC, world)
        proc.put32(0x499F24, pool)
        proc.put32(world + 0x2E51C, 1)
        proc.put32(world + 0x305A4, pool)
        rec = pool + 0x30
        proc.write(rec, b"\1")
        proc.put32(rec + 0x4FC, 100)
        proc.put32(rec + 0x500, 400)
        counted = []
        proc.stub(0x425860, lambda p: (counted.append(1) or 61, 0))
        mission = _position("vv2", 16)
        self.assertEqual(proc.export("VvfpStoryProbePossible", 2, mission), 1)
        proc.stub(0x425860, lambda p: (60, 0))
        self.assertEqual(proc.export("VvfpStoryProbePossible", 2, mission), 0)

    def test_vv3_vv5_ask_the_events_own_condition(self):
        for game in SELECTORS:
            table, count, *_ = SELECTORS[game]
            with self.subTest(game=game):
                proc = process(game)
                slot = story_island_events.EVENTS[game][3]["slot"]
                objects = _ObjectTable(proc, table, count, {slot: False})
                self.assertEqual(proc.export("VvfpStoryProbePossible", int(game[2:]), 3), 0)
                objects.answer[slot] = True
                self.assertEqual(proc.export("VvfpStoryProbePossible", int(game[2:]), 3), 1)


# ---------------------------------------------------------------------------
# The Origins companions
# ---------------------------------------------------------------------------

ORIGINS_SOURCES = {
    "vv1": ROOT / "native" / "vv1_origins_icons" / "vv1_origins_icons.c",
    "vv2": ROOT / "native" / "vv2_origins_icons" / "vv2_origins_icons.c",
    "vv3": ROOT / "native" / "vv3_full_mastery_candidate" / "vv3_full_mastery_candidate.c",
    "vv4": ROOT / "native" / "vv4_origins_icons" / "vv4_origins_icons.c",
    "vv5": ROOT / "native" / "vv5_task9_origins" / "vv5_task9_origins.c",
}
ORIGINS_DLLS = {
    "vv1": ROOT / "assets" / "origins" / "VVFP VV1 Origins Icons.dll",
    "vv2": ROOT / "assets" / "origins" / "VVFP VV2 Origins Icons.dll",
    "vv3": ROOT / "data" / "candidates" / "VVFP VV3 Safe Upgrades.dll",
    "vv4": ROOT / "assets" / "origins" / "VVFP VV4 Origins Icons.dll",
    "vv5": ROOT / "data" / "candidates" / "VVFP VV5 Task9 Origins Icons.dll",
}


class OriginsCompanionTests(unittest.TestCase):
    def test_each_companion_loads_the_story_dll_and_offers_the_pick(self):
        for game in GAMES:
            with self.subTest(game=game):
                source = ORIGINS_SOURCES[game].read_text(encoding="utf-8")
                number = "VV_STORY_GAME" if game == "vv1" else game[2:]
                self.assertIn('#include "../shared/story_bridge.h"', source
                              if game != "vv2" else ORIGINS_SOURCES["vv1"].read_text(encoding="utf-8"))
                self.assertIn(f"vvfp_story_bridge({number})", source)
                self.assertIn(f"vvfp_story_relabel({number}, window)", source)
                self.assertIn(f"vvfp_story_add_pick_button({number}, window)", source)
                self.assertIn("command == VVFP_STORY_PICK_ID", source)
                binary = ORIGINS_DLLS[game].read_bytes()
                self.assertIn(b"VVFP Story Upgrades.dll", binary)
                self.assertIn(b"VvfpStoryPickIslandEvent", binary)
                self.assertIn(b"VvfpStoryInstall", binary)

    def test_the_pick_shares_the_island_rows_lock(self):
        for game in GAMES:
            with self.subTest(game=game):
                source = ORIGINS_SOURCES[game].read_text(encoding="utf-8")
                body = source[source.index("command == VVFP_STORY_PICK_ID"):][:700]
                self.assertIn("ISLAND", body)
                self.assertIn("vvfp_story_pick_clicked", body)

    def test_companion_side_prices_go_through_the_story_price(self):
        """Every price a companion charges itself is 0 while the row is active."""
        expectations = {
            "vv1": ["vvfp_story_price(VV_STORY_GAME, VV_FORALL_COST)"],
            "vv2": ["vvfp_story_price(2, VV2_APPEARANCE_COST_DLL)", "vvfp_story_price(2, VV2_CAF_COST)",
                    "vvfp_story_price_text(2, vv2_tech_action_costs[action])"],
            "vv3": ["vvfp_story_price(3, EDL_COST)", "vvfp_story_price(3, VV3_CAF_COST)",
                    "vvfp_story_price_text(\n                3, s_villager_menu"],
            "vv4": ["vvfp_story_price(4, 450000)", "vvfp_story_price_text(4, g_tech_costs[row])"],
            "vv5": ["vvfp_story_price(5, 450000)", "if (vvfp_story_free(5))"],
        }
        for game, needles in expectations.items():
            source = ORIGINS_SOURCES[game].read_text(encoding="utf-8")
            for needle in needles:
                with self.subTest(game=game, needle=needle):
                    self.assertIn(needle, source)


class NoDeadCodeTests(unittest.TestCase):
    def test_shipped_dll_has_no_probe(self):
        pe = pefile.PE(str(DLL)) if HAVE_EMULATOR else None
        if pe is None:
            self.skipTest("pefile not installed")
        names = {e.name.decode() for e in pe.DIRECTORY_ENTRY_EXPORT.symbols if e.name}
        self.assertFalse({n for n in names if "Probe" in n or "Stats" in n}, names)
        self.assertTrue({"VvfpStoryInstall", "VvfpStoryActive", "VvfpStoryPickIslandEvent",
                         "VvfpStoryPickPending"} <= names)


if __name__ == "__main__":
    unittest.main()
