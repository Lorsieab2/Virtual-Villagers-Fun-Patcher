"""Super-Secret Golden Mushroom (all five games, off by default).

The owner: 1 in 1000 of the normal random mushroom spawns is golden, picking
it gives 100 food, it never comes from anything else (New Believers' Hand of
Bloom, island events, story items), and the patcher says nothing about it but
the owner's description.  The art is a separate image drawn by its own
companion DLL (not an edited sprite sheet) -- that part is pinned in
tests/test_golden_mushroom_art.py; this file pins the spawn roll and the award.

Everything here RUNS the patcher's own rendered bytes in an emulator with the
game's rand stubbed:

* the spawn roll gives golden only on rand(1000) == 0 and keeps the stock
  brown/red odds otherwise (A New Home over all 1000 outcomes: 1/50/949);
* the award is 100 for golden and the stock amount for brown and red;
* The Lost Children registers the golden type as a mushroom zone;
* the stock bytes give the stock result (so each check can fail).
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EIP, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
NAMES = {1: "A New Home", 2: "The Lost Children", 3: "The Secret City", 4: "The Tree of Life", 5: "New Believers"}
RAND = {1: 0x402F10, 2: 0x4031A0, 3: 0x4032D0, 4: 0x4036D0, 5: 0x403660}
STACK = 0x10000000
HEAP = 0x20000000
DESCRIPTION = ("Adds a super-secret golden spotted mushroom to the game. You'll have to pick it to see what "
               "it does! (Original art found in Virtual Villagers 2's files)")
_IMAGES: dict[tuple[int, bool], bytes] = {}


def _image(game: int, patched: bool) -> tuple[bytes, int]:
    key = (game, patched)
    if key not in _IMAGES:
        exe = STOCK / f"Virtual Villagers - {NAMES[game]}.exe"
        if patched:
            build = next(b for b in vfp.load_builds() if b.id == f"vv{game}")
            data, applied = vfp.render_patched_bytes(exe, build, "immediate_fixed",
                                                     [f"vv{game}_super_secret_golden_mushroom"])
            assert f"feature:vv{game}_super_secret_golden_mushroom" in {r["owner"] for r in applied}
            data = bytes(data)
        else:
            data = exe.read_bytes()
        pe = pefile.PE(data=data, fast_load=True)
        _IMAGES[key] = pe.get_memory_mapped_image()
    return _IMAGES[key], 0x400000


def run(game, start, stop, regs, rand1000=0, rand_other=50, stubs=None, patched=True, setup=None):
    image, base = _image(game, patched)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(base, (len(image) + 0xFFF) & ~0xFFF)
    mu.mem_write(base, image)
    mu.mem_map(STACK - 0x10000, 0x20000)
    mu.mem_map(HEAP, 0x2000000)
    for r, v in regs.items():
        mu.reg_write(r, v)
    mu.reg_write(UC_X86_REG_ESP, STACK)
    if setup:
        setup(mu)
    stubs = dict(stubs or {})
    calls = []

    def hook(uc, addr, size, user_data):
        if addr == RAND[game]:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, arg = struct.unpack("<II", uc.mem_read(esp, 8))
            calls.append(("rand", arg))
            uc.reg_write(UC_X86_REG_EAX, rand1000 if arg == 1000 else rand_other)
            uc.reg_write(UC_X86_REG_ESP, esp + 4)
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif addr in stubs:
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret, arg = struct.unpack("<II", uc.mem_read(esp, 8))
            calls.append(("stub", addr, arg))
            uc.reg_write(UC_X86_REG_ESP, esp + 4 + stubs[addr])
            uc.reg_write(UC_X86_REG_EIP, ret)
        elif addr == stop:
            uc.emu_stop()

    mu.hook_add(UC_HOOK_CODE, hook)
    mu.emu_start(start, 0xFFFFFFFF, count=5000)
    return mu, calls


def rd32(mu, a):
    return struct.unpack("<I", mu.mem_read(a, 4))[0]


class NewHomeTests(unittest.TestCase):
    """A New Home: one roll rand(1000) picks the kind -- 0 golden (flag 2),
    1..50 red (flag 1, the stock 5%), else brown -- then the stock expiry."""

    def _spawn(self, r, patched=True):
        mgr = HEAP + 0x100000
        mu, calls = run(1, 0x4236C7, 0x42370B, {UC_X86_REG_ESI: HEAP, UC_X86_REG_EBX: 0},
                        rand1000=r, rand_other=r, patched=patched,
                        setup=lambda m: m.mem_write(HEAP + 0x10, struct.pack("<I", mgr)))
        return rd32(mu, mgr + 0xACB0), rd32(mu, mu.reg_read(UC_X86_REG_ESP)), STACK - mu.reg_read(UC_X86_REG_ESP), calls

    def test_the_roll_over_every_outcome(self):
        counts = {0: 0, 1: 0, 2: 0}
        for r in range(1000):
            flag, pushed, depth, calls = self._spawn(r)
            counts[flag] += 1
            self.assertEqual((pushed, depth), (0x21, 4), r)
            self.assertEqual(calls, [("rand", 1000)], "one rand call, as stock makes one")
        self.assertEqual(counts, {2: 1, 1: 50, 0: 949})
        self.assertEqual(self._spawn(0)[0], 2)

    def test_stock_never_makes_golden(self):
        for r in (0, 4, 5, 99):
            self.assertIn(self._spawn(r, patched=False)[0], (0, 1))

    def test_the_job_picks_pose_and_award_from_the_kind(self):
        for flag, pose, award in ((0, 0xD, 0x20), (1, 0xE, 0x21), (2, 0xF, 0x22)):
            mgr = HEAP + 0x100000

            def setup(m, flag=flag):
                m.mem_write(mgr + 0xACB0, struct.pack("<I", flag))
            for start, stop, want in ((0x444591, 0x4445A3, pose), (0x444653, 0x444665, award)):
                mu, _ = run(1, start, stop, {UC_X86_REG_ECX: mgr, UC_X86_REG_ESI: 0x1234}, setup=setup)
                self.assertEqual(rd32(mu, mu.reg_read(UC_X86_REG_ESP)), want, (flag, hex(start)))
                self.assertEqual(mu.reg_read(UC_X86_REG_ECX), 0x1234, "ecx = esi, as stock")

    def test_callback_0x22_pushes_100_into_the_stock_mushroom_award(self):
        image, base = _image(1, True)
        entry = struct.unpack_from("<I", image, 0x43B46C - base + 4 * (0x22 - 1))[0]
        self.assertEqual(entry, 0x444683)
        mu, _ = run(1, entry, 0x43AFF1, {})
        self.assertEqual(rd32(mu, mu.reg_read(UC_X86_REG_ESP)), 100)
        stock_image, _ = _image(1, False)
        self.assertEqual(stock_image[0x43B04C - base:0x43B04C - base + 2], b"\x6A\x2D", "red pushes 45 into the same path")


class LaterGamesTests(unittest.TestCase):
    def test_vv2_spawn(self):
        for r100, r1000, want in ((50, 5, 0x30), (3, 5, 0x31), (50, 0, 0x32), (3, 0, 0x32)):
            with self.subTest(r100=r100, r1000=r1000):
                mu, _ = run(2, 0x41592C, 0x415EC5, {UC_X86_REG_ESI: HEAP}, rand1000=r1000, rand_other=r100,
                            setup=lambda m: m.mem_write(HEAP + 0x28, struct.pack("<I", 0xDEADBEEF)))
                esp = mu.reg_read(UC_X86_REG_ESP)
                self.assertEqual(rd32(mu, HEAP + 0x28), want)
                self.assertEqual((rd32(mu, esp), STACK - esp), (0x2F, 4))

    def test_vv2_golden_is_a_mushroom_zone(self):
        for patched, typ, want in ((True, 0x32, 0x2F), (True, 0x30, 0x2F), (True, 0x31, 0x2F), (True, 0x05, 0x30),
                                   (False, 0x32, 0x30)):
            with self.subTest(patched=patched, typ=typ):
                def setup(m, typ=typ):
                    m.mem_write(HEAP + 0x28, struct.pack("<I", typ))
                    m.mem_write(HEAP + 0x30, struct.pack("<I", HEAP + 0x1000))
                mu, _ = run(2, 0x4152E0, 0x418230, {UC_X86_REG_ECX: HEAP}, setup=setup, patched=patched)
                self.assertEqual(rd32(mu, mu.reg_read(UC_X86_REG_ESP) + 0x14), want)

    def test_vv2_award(self):
        game = HEAP + 0x100000
        for entry, carry, want in ((0x4633C5, 0x4E, 6), (0x463422, 0x4F, 35), (0x463422, 0x50, 100)):
            with self.subTest(carry=hex(carry)):
                def setup(m, carry=carry):
                    m.mem_write(STACK + 0x18, struct.pack("<I", 3))
                    m.mem_write(game + 3 * 0xE48C + 0x44, struct.pack("<I", carry))
                    m.mem_write(game + 0xE574D4, struct.pack("<I", HEAP + 0x1800000))
                mu, _ = run(2, entry, 0x4262B0, {UC_X86_REG_ESI: game}, setup=setup)
                self.assertEqual(rd32(mu, mu.reg_read(UC_X86_REG_ESP) + 4), want)
                self.assertEqual(mu.reg_read(UC_X86_REG_ECX), HEAP + 0x1800000)

    def test_vv3_spawn_and_award(self):
        slot = HEAP + 0x200
        for entry, r1000, want in ((0x42DA8B, 7, 0x65), (0x42DA94, 7, 0x64), (0x42DA8B, 0, 0x66), (0x42DA94, 0, 0x66)):
            with self.subTest(entry=hex(entry), r1000=r1000):
                mu, _ = run(3, entry, 0x42DAD6, {UC_X86_REG_EDI: slot, UC_X86_REG_EBX: 0x1234}, rand1000=r1000,
                            setup=lambda m: m.mem_write(slot + 8, struct.pack("<I", 0x11223344)))
                self.assertEqual(rd32(mu, slot + 8), want)
                self.assertEqual(mu.reg_read(UC_X86_REG_ESP), STACK)
        for patched, esi, want in ((True, 0x64, 6), (True, 0x65, 35), (True, 0x66, 100), (False, 0x66, 35)):
            with self.subTest(patched=patched, id=hex(esi)):
                mu, _ = run(3, 0x42E064, 0x42E079, {UC_X86_REG_ESI: esi}, patched=patched)
                self.assertEqual(rd32(mu, mu.reg_read(UC_X86_REG_ESP)), want)
                self.assertEqual(mu.reg_read(UC_X86_REG_ECX), 0x582490)

    def test_vv4_and_vv5_spawn_and_award(self):
        cases = {
            4: dict(stores=(0x413F9C, 0x413FB4), ids=(0x77, 0x76, 0x78), stop=0x414093,
                    regs={UC_X86_REG_EDI: HEAP, UC_X86_REG_ESI: 2}, slot=HEAP + 2 * 0x1C,
                    award=(0x4145DE, 0x41465A, 0x412F90)),
            5: dict(stores=(0x4142A1, 0x4142BA), ids=(0x81, 0x80, 0x82), stop=0x4143C7,
                    regs={UC_X86_REG_EBP: HEAP, UC_X86_REG_EBX: 5}, slot=HEAP + 5 * 0x1C,
                    award=(0x4148E6, 0x414965, 0x413450)),
        }
        for game, c in cases.items():
            red, brown, golden = c["ids"]
            for entry, r1000, want in ((c["stores"][0], 3, red), (c["stores"][1], 3, brown),
                                       (c["stores"][0], 0, golden), (c["stores"][1], 0, golden)):
                with self.subTest(game=game, entry=hex(entry), r1000=r1000):
                    mu, _ = run(game, entry, c["stop"], dict(c["regs"]), rand1000=r1000)
                    self.assertEqual(rd32(mu, c["slot"] + 8), want)
                    self.assertEqual(mu.reg_read(UC_X86_REG_ESP), STACK)
            start, stop, achievement = c["award"]
            for patched, esi, want in ((True, brown, 6), (True, red, 35), (True, golden, 100), (False, golden, 35)):
                with self.subTest(game=game, patched=patched, id=hex(esi)):
                    mu, _ = run(game, start, stop, {UC_X86_REG_ESI: esi}, stubs={achievement: 8}, patched=patched)
                    self.assertEqual(mu.reg_read(UC_X86_REG_ESI), want)
            # The owner: the golden mushroom counts as a rare mushroom for
            # achievements -- the same achievement calls as the red one.
            _, red_calls = run(game, start, stop, {UC_X86_REG_ESI: red}, stubs={achievement: 8})
            _, golden_calls = run(game, start, stop, {UC_X86_REG_ESI: golden}, stubs={achievement: 8})
            _, brown_calls = run(game, start, stop, {UC_X86_REG_ESI: brown}, stubs={achievement: 8})
            with self.subTest(game=game, check="rare achievements"):
                self.assertEqual(golden_calls, red_calls)
                self.assertNotEqual(red_calls, brown_calls, "the rare achievements are the extra calls")


class DescriptionTests(unittest.TestCase):
    def test_the_patcher_says_only_the_owners_text_and_the_rows_are_off_by_default(self):
        from vv_fun_patcher_gui import default_fun_patch_selection
        rows = {p.id: p for p in vfp.load_fun_patches()}
        for game in NAMES:
            rid = f"vv{game}_super_secret_golden_mushroom"
            with self.subTest(game=game):
                row = rows[rid].raw
                self.assertEqual(row["name"], "Super-Secret Golden Mushroom")
                self.assertEqual(row["description"], DESCRIPTION)
                self.assertFalse(default_fun_patch_selection(rid))
                # The loader derives these from the description when a row
                # has none: they may hold the owner's text and nothing else.
                self.assertIn(row.get("behavior_changes", [DESCRIPTION]), ([DESCRIPTION], []))
                self.assertEqual(row.get("explicit_non_changes", []), [])
                text = " ".join(p["purpose"] for p in row["patches"]).lower()
                # The image companion's run-time detours describe themselves
                # too; only the DLL's own file name may carry the row's name.
                text += " " + " ".join(d["routine"] for d in row.get("runtime_detours", [])).lower()
                for d in row.get("runtime_detours", []):
                    self.assertEqual(d["installed_by"], f"VVFP Golden Mushroom.dll, ordinal {game}")
                self.assertEqual({c["destination"] for c in row.get("companion_files", [])},
                                 set() if game == 2 else {"VVFP Golden Mushroom.dll", "Images/golden_mushroom.png"})
                # (behavior_changes / explicit_non_changes / evidence_status are
                # the loader's derived defaults, checked above and below.)
                self.assertEqual(set(row) - {"id", "game_id", "name", "description", "output_tag", "patches",
                                             "companion_files", "runtime_detours", "behavior_changes",
                                             "explicit_non_changes", "evidence_status"}, set(),
                                 "no other field says anything about the row")
                text += " " + str(row.get("evidence_status", "")).lower()
                for word in ("100", "food", "golden", "gold"):
                    self.assertNotIn(word, text, f"a purpose line gives it away: {word!r}")


if __name__ == "__main__":
    unittest.main()
