"""New Believers statistics count believers only (owner, 2026-09-30).

"HEATHENS SHOULD NEVER COUNT AS VILLAGERS FOR HIGHEST POPULATION, OLDEST
VILLAGER OR ANYTHING IN THE STATISTICS LOG UNLESS EXPLICITLY ASKED FOR." A
converted Heathen counts like any villager from the moment of conversion, never
before. Heathens Converted is the one Heathen row.

New Believers keeps its Heathens in the villager array beside the tribe; the
record's faction byte +0x1CEC is 0 for a believer. The stock counters that could
credit a Heathen, and the guard each now has (scripts/build_statistics_features.py
VV5_BELIEVER_GUARDS and vv5_believers_only):

* Oldest Villager (+0x20): the per-villager update skips a Heathen's aging but
  not the maximum -- live, a new village's Heathen at internal age 1000 made the
  row read 50. The skip now also skips the maximum.
* People Cured (+0x10): the drag-a-healer cure 0x468C10 finds its patient with
  no faction test; a patient who was a Heathen when the cure began is not
  counted (this includes the purple Heathen, whom the cure itself converts).
* Babies Made (+0x08), Twins Birthed (+0x28), Triplets Birthed (+0x2C): counted
  inside the conception routine 0x465E00 on its mother, with no faction test; a
  Heathen mother's conception is not counted.

Villagers Buried needs no guard: the owner rules that a Heathen grave is never
made (2026-09-30), so a Heathen-corpse check could never fire.

Two layers. The first runs the wrappers straight from the manifest's cave bytes
and needs no game file, so it runs in CI. The second executes the patched game
routines themselves, rendered by the patcher, and the same routines unpatched --
which must still credit the Heathen, so every check here is able to fail; it
needs the stock executable and is skipped without it.
"""
from __future__ import annotations

import base64
import json
import struct
import sys
import unittest
from pathlib import Path

from capstone import CS_ARCH_X86, CS_MODE_32, Cs
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

MANIFEST = ROOT / "data" / "statistics_features.json"
STOCK = ROOT / "research" / "stock-executables" / "Virtual Villagers - New Believers.exe"
CAVE_FILE, CAVE_VA = 0x94932, 0x494932
FACTION, SICK, TYPE, AGE = 0x1CEC, 0x1C48, 0x1CFC, 0x1B8C
BLOCK = 0x51D358
BABIES, CURED, OLDEST, TWINS, TRIPLETS = (BLOCK + 0x08, BLOCK + 0x10, BLOCK + 0x20,
                                          BLOCK + 0x28, BLOCK + 0x2C)
HEAP, STACK = 0x20000000, 0x10000000
RETURN = 0x0BADC0DE
HEATHEN, BELIEVER = 1, 0


def feature() -> dict:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return next(f for f in manifest["features"] if f["game_id"] == "vv5")


def patch_at(offset: int) -> dict:
    return next(p for p in feature()["patches"] if int(p["offset"], 0) == offset)


def cave() -> bytes:
    return base64.b64decode(patch_at(CAVE_FILE)["after_base64"])


def jump_target(offset: int) -> int:
    after = bytes.fromhex(patch_at(offset)["after"])
    assert after[0] == 0xE9
    return offset + 0x400000 + 5 + struct.unpack("<i", after[1:5])[0]


def rd(mu: Uc, address: int) -> int:
    return struct.unpack("<i", mu.mem_read(address, 4))[0]


def wr(mu: Uc, address: int, value: int) -> None:
    mu.mem_write(address, struct.pack("<i", value))


class WrapperShapeTests(unittest.TestCase):
    """What the manifest installs, decoded. Needs no game file."""

    def test_oldest_villager_skip_now_jumps_past_the_maximum(self):
        patch = patch_at(0x7007F)
        self.assertEqual(patch["before"], "750C")      # jne 0x47008D: into the maximum
        self.assertEqual(patch["after"], "7538")
        decoded = next(Cs(CS_ARCH_X86, CS_MODE_32).disasm(bytes.fromhex(patch["after"]), 0x47007F))
        self.assertEqual((decoded.mnemonic, decoded.op_str), ("jne", "0x4700b9"),
                         "a Heathen must rejoin where both paths meet, after the maximum")

    def test_each_detour_replaces_whole_instructions_with_a_jump(self):
        sites = {0x68C3C: "389E481C0000751D", 0x68D4D: "830568D3510001",
                 0x65F1A: "830584D3510001", 0x65F2D: "830580D3510001",
                 0x65F3E: "010D60D35100"}
        for offset, before in sites.items():
            with self.subTest(offset=hex(offset)):
                patch = patch_at(offset)
                after = bytes.fromhex(patch["after"])
                self.assertEqual(patch["before"], before)
                self.assertEqual(len(after), len(bytes.fromhex(before)))
                self.assertEqual(after[0], 0xE9)
                self.assertEqual(after[5:], b"\x90" * (len(after) - 5))
                self.assertTrue(CAVE_VA <= jump_target(offset) < CAVE_VA + len(cave()))


class CaveWrapperTests(unittest.TestCase):
    """The wrappers executed from the manifest's own cave bytes."""

    def machine(self) -> Uc:
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x465000, 0x6000)                     # resume addresses land here
        mu.mem_map(0x472000, 0x4000)                     # (a block is decoded past its first instruction)
        mu.mem_map(CAVE_VA & ~0xFFF, 0x2000)
        mu.mem_write(CAVE_VA, cave())
        mu.mem_map(BLOCK & ~0xFFF, 0x1000)
        mu.mem_map(HEAP, 0x10000)
        mu.mem_map(STACK - 0x1000, 0x2000)
        mu.reg_write(UC_X86_REG_ESP, STACK)
        return mu

    def run_wrapper(self, mu: Uc, entry: int, exits: tuple[int, ...]) -> int:
        reached = []

        def stop(uc, address, size, _):
            if address in exits:
                reached.append(address)
                uc.emu_stop()

        mu.hook_add(UC_HOOK_CODE, stop)
        mu.emu_start(entry, 0xFFFFFFFF, count=50)
        self.assertEqual(len(reached), 1, "the wrapper did not resume the game")
        return reached[0]

    def record(self, mu: Uc, faction: int, sick: int = 0) -> int:
        mu.mem_write(HEAP + FACTION, bytes([faction]))
        mu.mem_write(HEAP + SICK, bytes([sick]))
        mu.reg_write(UC_X86_REG_ESI, HEAP)
        return HEAP

    def test_people_cured_capture_keeps_the_stock_sickness_test(self):
        for faction in (BELIEVER, HEATHEN):
            for sick, resume in ((1, 0x468C61), (0, 0x468C44)):
                with self.subTest(faction=faction, sick=sick):
                    mu = self.machine()
                    self.record(mu, faction, sick)
                    mu.reg_write(UC_X86_REG_EBX, 0)
                    wr(mu, STACK + 0x18, 0x7F7F7F7F)
                    self.assertEqual(self.run_wrapper(mu, jump_target(0x68C3C), (0x468C61, 0x468C44)),
                                     resume)
                    self.assertEqual(mu.reg_read(UC_X86_REG_ESP), STACK, "stack not balanced")
                    self.assertEqual(mu.mem_read(STACK + 0x18, 1)[0], faction,
                                     "the patient's faction was not captured")

    def test_people_cured_counts_only_a_patient_who_began_as_a_believer(self):
        for faction, expected in ((BELIEVER, 1), (HEATHEN, 0), (2, 0)):
            with self.subTest(faction=faction):
                mu = self.machine()
                mu.mem_write(STACK + 0x18, bytes([faction, 0, 0, 0]))
                self.assertEqual(self.run_wrapper(mu, jump_target(0x68D4D), (0x468D54,)), 0x468D54)
                self.assertEqual(rd(mu, CURED), expected)

    def test_litter_rows_count_only_a_believer_mother(self):
        cases = (
            (0x65F1A, TRIPLETS, 0x465F21, None),
            (0x65F2D, TWINS, 0x465F34, None),
            (0x65F3E, BABIES, 0x465F44, 3),
        )
        for offset, counter, resume, litter in cases:
            for faction, counted in ((BELIEVER, True), (HEATHEN, False)):
                with self.subTest(site=hex(offset), faction=faction):
                    mu = self.machine()
                    self.record(mu, faction)
                    wr(mu, counter, 7)
                    if litter is not None:
                        mu.reg_write(UC_X86_REG_ECX, litter)
                    self.assertEqual(self.run_wrapper(mu, jump_target(offset), (resume,)), resume)
                    step = (litter or 1) if counted else 0
                    self.assertEqual(rd(mu, counter), 7 + step)
                    self.assertEqual(mu.reg_read(UC_X86_REG_ESI), HEAP)


# ---------------------------------------------------------------------------
# The game routines themselves, stock and patched.

_IMAGES: dict = {}


def image(patched: bool) -> bytes:
    if patched not in _IMAGES:
        import pefile
        import vv_fun_patcher as vfp
        if patched:
            build = next(b for b in vfp.load_builds() if b.id == "vv5")
            data, _ = vfp.render_patched_bytes(STOCK, build, "immediate_fixed",
                                               ["vv5_write_village_statistics"])
            data = bytes(data)
        else:
            data = STOCK.read_bytes()
        _IMAGES[patched] = pefile.PE(data=data, fast_load=True).get_memory_mapped_image()
    return _IMAGES[patched]


class GameRoutine:
    """The patched or stock image in an emulator, with named callees stubbed.

    A stub returns to its caller as the callee would: it pops the return
    address, removes its own stack arguments (these callees clean up after
    themselves; the C runtime helpers leave that to the caller) and sets EAX.
    """

    def __init__(self, patched: bool, stubs: dict):
        img = image(patched)
        self.mu = mu = Uc(UC_ARCH_X86, UC_MODE_32)
        mu.mem_map(0x400000, (len(img) + 0xFFF) & ~0xFFF)
        mu.mem_write(0x400000, img)
        mu.mem_map(HEAP, 0x100000)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(RETURN & ~0xFFF, 0x1000)
        self.stubs = stubs
        self.calls: list[int] = []
        mu.hook_add(UC_HOOK_CODE, self._stub)

    def _stub(self, uc, address, size, _):
        if address not in self.stubs:
            return
        cleanup, result = self.stubs[address]
        esp = uc.reg_read(UC_X86_REG_ESP)
        back = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        args = [struct.unpack("<I", uc.mem_read(esp + 4 + 4 * i, 4))[0] for i in range(3)]
        self.calls.append(address)
        value = result(uc, args) if callable(result) else result
        uc.reg_write(UC_X86_REG_EAX, value & 0xFFFFFFFF)
        uc.reg_write(UC_X86_REG_ESP, esp + 4 + cleanup)
        uc.reg_write(UC_X86_REG_EIP, back)

    def call(self, entry: int, ecx: int, args: tuple[int, ...] = ()) -> None:
        esp = STACK - 4 * len(args) - 4
        self.mu.mem_write(esp, struct.pack("<I", RETURN) + b"".join(struct.pack("<I", a) for a in args))
        self.mu.reg_write(UC_X86_REG_ESP, esp)
        self.mu.reg_write(UC_X86_REG_ECX, ecx)
        self.mu.emu_start(entry, RETURN, count=5000)


def villager(mu: Uc, base: int, faction: int, *, age: int = 400, sick: int = 0, vtype: int = 0) -> int:
    mu.mem_write(base, b"\0" * 0x2F44)
    mu.mem_write(base + FACTION, bytes([faction]))
    mu.mem_write(base + SICK, bytes([sick]))
    wr(mu, base + TYPE, vtype)
    wr(mu, base + AGE, age)
    wr(mu, base + 0x1CD4, 1)
    return base


@unittest.skipUnless(STOCK.exists(), "stock New Believers executable not available")
class OldestVillagerRoutineTests(unittest.TestCase):
    """0x470077..0x4700B9 of the per-villager update: the faction test, the
    aging call it guards, and the Oldest Villager maximum."""

    def oldest_after(self, patched: bool, faction: int, age: int, oldest: int = 18) -> tuple[int, bool]:
        aged = []
        game = GameRoutine(patched, {0x46F7F0: (4, lambda uc, a: aged.append(1) or 0)})
        mu = game.mu
        record = villager(mu, HEAP, faction, age=age)
        wr(mu, OLDEST, oldest)
        mu.reg_write(UC_X86_REG_ESI, record)
        mu.reg_write(UC_X86_REG_EBX, 0)
        mu.reg_write(UC_X86_REG_EDI, 1)
        mu.reg_write(UC_X86_REG_ESP, STACK)
        mu.emu_start(0x470077, 0x4700B9, count=100)
        return rd(mu, OLDEST), bool(aged)

    def test_a_heathen_never_sets_oldest_villager(self):
        # The live case: a Heathen at internal age 1000 read as "Oldest Villager: 50".
        self.assertEqual(self.oldest_after(True, HEATHEN, 1000), (18, False))

    def test_stock_let_the_heathen_set_it(self):
        self.assertEqual(self.oldest_after(False, HEATHEN, 1000), (50, False))

    def test_believers_and_converted_heathens_count_and_age_as_before(self):
        for patched in (True, False):
            with self.subTest(patched=patched):
                self.assertEqual(self.oldest_after(patched, BELIEVER, 860), (43, True))
                # A converted Heathen is a believer (faction 0) with whatever age
                # it had; it counts from the moment of conversion.
                self.assertEqual(self.oldest_after(patched, BELIEVER, 1000), (50, True))
                self.assertEqual(self.oldest_after(patched, BELIEVER, 300, oldest=43), (43, True))


@unittest.skipUnless(STOCK.exists(), "stock New Believers executable not available")
class PeopleCuredRoutineTests(unittest.TestCase):
    """The whole drag-a-healer cure 0x468C10, callees stubbed."""

    HEALER, PATIENT = HEAP, HEAP + 0x4000

    def cure(self, patched: bool, faction: int, *, sick: int = 1, vtype: int = 0) -> tuple[int, int]:
        def position(uc, args):
            uc.mem_write(args[0], b"\0" * 8)
            return args[0]

        def belief(uc, args):
            # 0x467F90 sets belief; crossing zero converts (0x4668B0), which
            # clears the faction -- as it does for the purple Heathen.
            uc.mem_write(self.PATIENT + FACTION, b"\0")
            return 0

        stubs = {
            0x466350: (4, position), 0x4706F0: (0xC, self.PATIENT), 0x473440: (0, 0),
            0x46B270: (8, 1), 0x464F90: (4, 0), 0x465580: (8, 0), 0x413450: (8, 0),
            0x403660: (0, 5), 0x467F90: (8, belief), 0x478950: (4, 0), 0x437D50: (0, 0),
            0x474910: (4, 0), 0x4733F0: (4, 0),
        }
        game = GameRoutine(patched, stubs)
        villager(game.mu, self.HEALER, BELIEVER)
        villager(game.mu, self.PATIENT, faction, sick=sick, vtype=vtype)
        wr(game.mu, CURED, 0)
        game.call(0x468C10, self.HEALER)
        self.assertIn(0x474910, game.calls, "the cure did not run to the counter")
        return rd(game.mu, CURED), game.mu.mem_read(self.PATIENT + SICK, 1)[0]

    def test_a_sick_heathen_is_cured_but_not_counted(self):
        # The Missing Kids makes its Heathen child sick (0x416203).
        self.assertEqual(self.cure(True, HEATHEN), (0, 0))
        self.assertEqual(self.cure(False, HEATHEN), (1, 0), "stock counted the Heathen")

    def test_the_purple_heathen_the_cure_converts_is_not_counted(self):
        self.assertEqual(self.cure(True, HEATHEN, sick=0, vtype=12)[0], 0)
        self.assertEqual(self.cure(False, HEATHEN, sick=0, vtype=12)[0], 1, "stock counted it")

    def test_believers_and_converted_heathens_count(self):
        for patched in (True, False):
            with self.subTest(patched=patched):
                self.assertEqual(self.cure(patched, BELIEVER), (1, 0))
                # a purple-masked believer (the Heathen mask mod sets type 12)
                self.assertEqual(self.cure(patched, BELIEVER, sick=0, vtype=12)[0], 1)


@unittest.skipUnless(STOCK.exists(), "stock New Believers executable not available")
class ConceptionRoutineTests(unittest.TestCase):
    """The whole conception routine 0x465E00, as Abandoned Infants calls it
    (0x471B6D), including the 150-slot saturation guards every build applies."""

    MOTHER = HEAP

    def conceive(self, patched: bool, faction: int, rolls: list[int]) -> tuple[int, int, int, int]:
        rolls = list(rolls)
        stubs = {
            0x472BD0: (0, 1),                      # room in the village
            0x47C9B0: (0, 50),                     # float to int
            0x475730: (8, 0),
            0x47D7C0: (0, 0),                      # the father's name copy (cdecl)
            0x423600: (4, 3),                      # the level that allows multiples
            0x403660: (0, lambda uc, a: rolls.pop(0)),
        }
        game = GameRoutine(patched, stubs)
        villager(game.mu, self.MOTHER, faction, age=500)
        for address in (BABIES, TWINS, TRIPLETS):
            wr(game.mu, address, 0)
        game.call(0x465E00, self.MOTHER, (1, 0, 0, 0x4B8E1C, 2, 2, 0))
        litter = rd(game.mu, self.MOTHER + 0x1C50)
        return rd(game.mu, BABIES), rd(game.mu, TWINS), rd(game.mu, TRIPLETS), litter

    SINGLE, TWIN, TRIPLET = [90], [0, 90], [0, 0]

    def test_a_heathen_mothers_conception_counts_nothing(self):
        for rolls, litter in ((self.SINGLE, 1), (self.TWIN, 2), (self.TRIPLET, 3)):
            with self.subTest(litter=litter):
                self.assertEqual(self.conceive(True, HEATHEN, rolls), (0, 0, 0, litter),
                                 "the litter itself must be unchanged")

    def test_stock_counted_a_heathen_mother(self):
        self.assertEqual(self.conceive(False, HEATHEN, self.TWIN), (2, 1, 0, 2))
        self.assertEqual(self.conceive(False, HEATHEN, self.TRIPLET), (3, 0, 1, 3))

    def test_a_believer_mothers_conception_counts_as_before(self):
        for patched in (True, False):
            for rolls, expected in ((self.SINGLE, (1, 0, 0, 1)), (self.TWIN, (2, 1, 0, 2)),
                                    (self.TRIPLET, (3, 0, 1, 3))):
                with self.subTest(patched=patched, litter=expected[3]):
                    self.assertEqual(self.conceive(patched, BELIEVER, rolls), expected)


if __name__ == "__main__":
    unittest.main()
