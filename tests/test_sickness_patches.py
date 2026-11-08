"""2-10x Sickness (all five games) and Sickness works like VV1-3 (The Tree of Life, New Believers).  The traces are in
scripts/build_sickness_features.py.

  * The rewritten roll, run in unicorn with the game's helpers stubbed (the game-state getter, rand, the Medicine
    level, the fire, the old-age test), gives The Secret City's table at every Medicine level, difficulty and fire
    state with no Aromatherapy: the highest rand result that still makes a villager sick is k x m, m = 1 + (fire out)
    + (Hard); Easy's "not sick" half the time, an existing sickness and the old villagers' roll as stock.
  * The stock VV4 / VV5 roll gives m = 1 always (the reason for the patch).
  * 2-10x Sickness writes round(n / N) at the right sites, stock or with the rewritten roll, and stacks.
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import vv_fun_patcher as patcher  # noqa: E402
import vv_fun_patcher_gui as gui  # noqa: E402

try:
    import build_sickness_features as build
    import pefile
    from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP
    HAVE = True
except ImportError:  # pragma: no cover
    HAVE = False

STOCK_DIR = ROOT / "research" / "stock-executables"
STATE, VILLAGER, STACK, RETURN = 0x0200_0000, 0x0210_0000, 0x0100_0000, 0x0100_F000
K = {1: 3, 2: 3, 3: 2}                      # The Secret City's k by Medicine level
MODULUS = {1: 1440, 2: 2460, 3: 5400}


def image(game: int, patched: bool) -> bytes:
    data = bytearray((STOCK_DIR / f"Virtual Villagers - {build.NAMES[game]}.exe").read_bytes())
    if patched:
        for p in json.loads((ROOT / "data" / f"vv{game}_sickness_like_vv3_feature.json").read_text("utf-8"))["patches"]:
            at, before, after = int(p["offset"], 16), bytes.fromhex(p["before"]), bytes.fromhex(p["after"])
            assert data[at:at + len(before)] == before
            data[at:at + len(after)] = after
    return bytes(data)


_EMU: dict = {}


def roll(game: int, patched: bool, difficulty: int, medicine: int, fire: bool, rolls: list[int],
         sick: bool = False, elder: bool = False) -> tuple[int, list[int]]:
    """(the roll's answer, the moduli rand was asked for)."""
    c = build.LIKE_VV3[game]
    key = (game, patched)
    if key not in _EMU:
        data = image(game, patched)
        pe = pefile.PE(data=data, fast_load=True)
        base = pe.OPTIONAL_HEADER.ImageBase
        text = next(s for s in pe.sections if s.Name.startswith(b".text"))
        lo = (base + text.VirtualAddress) & ~0xFFF
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(lo, ((base + text.VirtualAddress + text.Misc_VirtualSize + 0xFFF) & ~0xFFF) - lo)
        uc.mem_write(base + text.VirtualAddress, bytes(data[text.PointerToRawData:text.PointerToRawData
                                                           + text.SizeOfRawData][:text.Misc_VirtualSize]))
        for at in (STATE, VILLAGER, STACK):
            uc.mem_map(at, 0x20000)
        state = {}

        def hook(uc, address, size, _):
            esp = uc.reg_read(UC_X86_REG_ESP)
            ret = struct.unpack("<I", uc.mem_read(esp, 4))[0]
            if address == c["MGR"]:
                result, pop = STATE, 4
            elif address == c["RAND"]:
                state["asked"].append(struct.unpack("<i", uc.mem_read(esp + 4, 4))[0])
                result, pop = state["rolls"].pop(0), 4
            elif address == c["TECH"]:
                result, pop = state["medicine"], 8
            elif address == c["FIRE"]:
                result, pop = int(state["fire"]), 4
            elif address == c["ELDER"]:
                result, pop = int(state["elder"]), 4
            else:
                return
            uc.reg_write(UC_X86_REG_EAX, result)
            uc.reg_write(UC_X86_REG_ESP, esp + pop)
            uc.reg_write(UC_X86_REG_EIP, ret)

        uc.hook_add(UC_HOOK_CODE, hook)
        _EMU[key] = (uc, state)
    uc, state = _EMU[key]
    state.update(rolls=list(rolls), asked=[], medicine=medicine, fire=fire, elder=elder)
    uc.mem_write(STATE + c["DIFF"], struct.pack("<i", difficulty))
    uc.mem_write(VILLAGER + 0x1C48, bytes([1 if sick else 0]))
    uc.mem_write(STACK + 0x8000, struct.pack("<I", RETURN))
    uc.reg_write(UC_X86_REG_ESP, STACK + 0x8000)
    uc.reg_write(UC_X86_REG_ECX, VILLAGER)
    uc.emu_start(c["start"], RETURN, count=2000)
    return uc.reg_read(UC_X86_REG_EAX), state["asked"]


def highest_sick(game: int, patched: bool, difficulty: int, medicine: int, fire: bool) -> int:
    """The highest rand(n) result that still makes a villager sick (Easy's first roll passed, not an elder)."""
    best = -1
    for r in range(0, 12):
        rolls = ([60] if difficulty == 0 else []) + [r]
        if roll(game, patched, difficulty, medicine, fire, rolls)[0]:
            best = r
    return best


@unittest.skipUnless(HAVE, "unicorn / pefile / keystone not installed")
class LikeVV3(unittest.TestCase):
    def setUp(self) -> None:
        if not all((STOCK_DIR / f"Virtual Villagers - {build.NAMES[g]}.exe").is_file() for g in (4, 5)):
            self.skipTest("stock executables not present")

    def test_the_secret_citys_table_without_aromatherapy(self) -> None:
        for game in (4, 5):
            for difficulty in (0, 1, 2):
                for medicine in (1, 2, 3):
                    for fire in (True, False):
                        m = 1 + (not fire) + (difficulty == 2)
                        with self.subTest(game=game, difficulty=difficulty, medicine=medicine, fire=fire):
                            self.assertEqual(highest_sick(game, True, difficulty, medicine, fire), K[medicine] * m)
                            self.assertEqual(highest_sick(game, False, difficulty, medicine, fire), K[medicine])

    def test_the_moduli_easy_existing_sickness_and_elders(self) -> None:
        for game in (4, 5):
            for medicine in (1, 2, 3):
                self.assertEqual(roll(game, True, 1, medicine, True, [5999, 5999])[1][0], MODULUS[medicine])
            self.assertEqual(roll(game, True, 0, 1, True, [10])[0], 0, "Easy: not sick half the time")
            self.assertEqual(roll(game, True, 1, 1, False, [], sick=True)[0], 1, "an existing sickness stays")
            self.assertEqual(roll(game, True, 1, 1, True, [5999, 14], elder=True), (1, [1440, 1000]))
            self.assertEqual(roll(game, True, 1, 1, True, [5999, 15], elder=True)[0], 0)
            self.assertEqual(roll(game, True, 1, 0, True, [14], elder=True), (1, [1000]), "no Medicine level")


@unittest.skipUnless(HAVE, "keystone / pefile not installed")
class Slider(unittest.TestCase):
    def test_both_variants_every_n(self) -> None:
        builds = {b.id: b for b in patcher.load_builds()}
        for game in range(1, 6):
            stock = STOCK_DIR / f"Virtual Villagers - {build.NAMES[game]}.exe"
            if not stock.is_file():
                self.skipTest("stock executables not present")
            variants = [[f"vv{game}_sickness_multiplier"]]
            if game in (4, 5):
                variants.append([f"vv{game}_sickness_multiplier", f"vv{game}_sickness_like_vv3"])
            record = json.loads((ROOT / "data" / f"vv{game}_sickness_multiplier_feature.json").read_text("utf-8"))
            for ids in variants:
                sites = record["sickness_multiplier"]["sites"]["stock" if len(ids) == 1 else ids[1]]
                for n in (2, 3, 10):
                    data, applied = patcher.render_patched_bytes(stock, builds[f"vv{game}"], "stock", ids)
                    patcher.apply_sickness_multiplier(data, f"vv{game}", n, applied, set(ids))
                    with self.subTest(game=game, ids=ids, n=n):
                        for row in sites:
                            at, m = int(row["offset"], 16), row["modulus"]
                            self.assertEqual(data[at - 1], 0x68)
                            self.assertEqual(struct.unpack_from("<I", data, at)[0], (2 * m + n) // (2 * n))
                        self.assertEqual(patcher.sickness_multiplier_applied(applied), n)

    def test_not_selected_writes_nothing(self) -> None:
        data = bytearray(b"\0" * 16)
        patcher.apply_sickness_multiplier(data, "vv1", 5, [], set())
        self.assertEqual(data, bytearray(b"\0" * 16))
        with self.assertRaises(patcher.PatcherError):
            patcher.validate_sickness_multiplier(11)


class Catalog(unittest.TestCase):
    def test_defaults_classic_and_owners_slider(self) -> None:
        ids = {p.id for p in patcher.load_public_fun_patches()}
        for game in range(1, 6):
            self.assertIn(f"vv{game}_sickness_multiplier", ids)
            self.assertFalse(gui.default_fun_patch_selection(f"vv{game}_sickness_multiplier"))
            self.assertTrue(gui.owners_default_fun_patch_selection(f"vv{game}_sickness_multiplier"))
        for game in (4, 5):
            patch_id = f"vv{game}_sickness_like_vv3"
            self.assertIn(patch_id, ids)
            self.assertTrue(gui.owners_default_fun_patch_selection(patch_id))
            classic = json.loads((ROOT / "data" / f"vv{game}_classic_vv_difficulty_feature.json").read_text("utf-8"))
            self.assertIn(patch_id, classic["dependencies"])
        self.assertEqual(gui.saved_sickness_multiplier({"sickness_multiplier": 4}), 4)
        self.assertEqual(gui.saved_sickness_multiplier({"sickness_multiplier": 1}), 2)


if __name__ == "__main__":
    unittest.main()
