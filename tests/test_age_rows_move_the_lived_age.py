"""Every game's Set Age to 18, Grant Youth and All Villagers are 18 MOVE the age, never just write it.

Each game keeps the shown age and the age its villager tick has already lived, and the tick steps every villager
whose lived age is behind one unit at a time until none is -- all inside one update, job turns included:

    A New Home       shown +0x348   lived +0x34C   conception mark +0x358   (life loop 0x42EC74)
    The Lost Children shown +0x530  lived +0x534   conception mark +0x540   (life loop 0x43BA92)
    The Secret City  shown +0xDC4   lived +0xE74   conception mark +0xE8C   (aging loop 0x46001E)
    The Tree of Life shown +0x1B8C  lived +0x1C3C  conception mark +0x1C4C  (life tick 0x46846D)
    New Believers    shown +0x1B8C  lived +0x1C3C  conception mark +0x1C4C  (tick 0x472C90; its own test,
                                                                              tests/test_vv5_age18_all_keeps_lived_age.py)

The conception mark is the lived age at the conception; the birth is due 40 units later.  So an age change moves the
lived age and a running mark by the same delta, as the stock age change itself does (A New Home 0x419543-0x4195BE:
the lived age follows the new age, the pregnancy keeps how far along it is).  Written alone, a child made 18 lived
every missing year in one update (New Believers live, 2026-11-20: four to seven conceptions and births each at shown
age 360) and an elder stopped living until the age caught up; the older 318 (360 - 42) mark made every carrier give
birth on the next update.

Each test runs the shipped bytes (the manifests' patches, the rebuilt VV2 companion) in an emulator: a child (no
replay: the lived age comes with it), a villager mid-pregnancy (the 20 units already carried are kept) and an elder
(no years skipped)."""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

import capstone
from keystone import KS_ARCH_X86, KS_MODE_32, Ks
from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, UC_PROT_ALL, Uc
from unicorn.x86_const import UC_X86_REG_ECX, UC_X86_REG_EDX, UC_X86_REG_ESP

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

import build_village_wide_origins_features as wide  # noqa: E402

# game: (shown, lived, conception mark, record stride)
FIELDS = {
    "vv1": (0x348, 0x34C, 0x358, 0x3D8),
    "vv2": (0x530, 0x534, 0x540, 0xE48C),
    "vv3": (0xDC4, 0xE74, 0xE8C, 0x1F8C),
    "vv4": (0x1B8C, 0x1C3C, 0x1C4C, 0x2E3C),
}
CODE, RECORDS, STACK, RETURN = 0x10000000, 0x20000000, 0x0F000000, 0x0E000000


def _asm(source: str) -> bytes:
    return bytes(Ks(KS_ARCH_X86, KS_MODE_32).asm(source, CODE)[0])


def _patches(name: str) -> list[dict]:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))["patches"]


def _find_once(name: str, needle: bytes) -> tuple[bytes, int]:
    found = []
    for patch in _patches(name):
        blob = bytes.fromhex(patch["after"])
        at = blob.find(needle)
        while at >= 0:
            found.append((blob, at))
            at = blob.find(needle, at + 1)
    if len(found) != 1:
        raise AssertionError(f"{name}: {len(found)} copies of {needle.hex()}")
    return found[0]


def _ages(uc: Uc, at: int, game: str) -> tuple[int, int, int]:
    shown, lived, mark, _ = FIELDS[game]
    return tuple(struct.unpack("<i", bytes(uc.mem_read(at + off, 4)))[0] for off in (shown, lived, mark))


def _put(uc: Uc, at: int, game: str, ages: tuple[int, int, int], health: int = 50, active=None) -> None:
    shown, lived, mark, _ = FIELDS[game]
    for off, value in zip((shown, lived, mark), ages):
        uc.mem_write(at + off, struct.pack("<i", value))
    if active is not None:
        uc.mem_write(at + active[0], bytes([1]))
        uc.mem_write(at + active[1], struct.pack("<i", health))


class DetailRows(unittest.TestCase):
    """Set Age to 18 and Grant Youth on the Villager Details screen (EDX = the villager's record)."""

    MANIFEST = {"vv1": "vv1_origins_feature.json", "vv2": "vv2_origins_feature.json",
                "vv4": "vv4_origins_feature.json"}

    def _run(self, game: str, row: str, ages: tuple[int, int, int]) -> tuple[int, int, int]:
        shown, lived, mark, stride = FIELDS[game]
        shift = _asm(f"add dword ptr [edx+{shown:#x}], eax; add dword ptr [edx+{lived:#x}], eax; "
                     f"cmp dword ptr [edx+{mark:#x}], 0")
        blob, shift_at = _find_once(self.MANIFEST[game], shift)
        # The shift's je goes to detail_success: the run ends there.
        je = next(capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32).disasm(
            blob[shift_at + len(shift):shift_at + len(shift) + 6], CODE + shift_at + len(shift)))
        self.assertEqual(je.mnemonic, "je")
        success = int(je.op_str, 16)
        if row == "age18":
            # The detail row jumps to the shared shift (a village-wide copy falls straight into its own).
            entry = _asm(f"mov eax, 360; sub eax, dword ptr [edx+{shown:#x}]")
            starts = [i for i in range(len(blob)) if blob.startswith(entry, i) and blob[i + len(entry)] in (0xEB, 0xE9)]
            self.assertEqual(len(starts), 1, starts)
            entry_at = starts[0]
        else:
            entry_blob, entry_at = _find_once(self.MANIFEST[game], _asm(f"mov eax, dword ptr [edx+{shown:#x}]; sub eax, 700"))
            self.assertTrue(entry_blob == blob, "Grant Youth and the shift are in one patch")
        uc = Uc(UC_ARCH_X86, UC_MODE_32)
        uc.mem_map(CODE, (len(blob) + 0xFFF) & ~0xFFF)
        uc.mem_write(CODE, blob)
        uc.mem_map(RECORDS, (stride + 0xFFF) & ~0xFFF)
        uc.mem_map(STACK - 0x10000, 0x10000)
        uc.reg_write(UC_X86_REG_ESP, STACK - 0x100)
        uc.reg_write(UC_X86_REG_EDX, RECORDS)
        _put(uc, RECORDS, game, ages)
        reached = []

        def stop(u, address, size, data):
            if address == success:
                reached.append(address)
                u.emu_stop()
        uc.hook_add(UC_HOOK_CODE, stop)
        uc.emu_start(CODE + entry_at, 0, count=100)
        self.assertEqual(reached, [success], "the row ends at detail_success")
        return _ages(uc, RECORDS, game)

    def test_set_age_to_18(self) -> None:
        for game in self.MANIFEST:
            with self.subTest(game=game):
                self.assertEqual(self._run(game, "age18", (148, 148, 0)), (360, 360, 0))       # a child
                self.assertEqual(self._run(game, "age18", (150, 147, 0)), (360, 357, 0))       # a tick not yet run
                self.assertEqual(self._run(game, "age18", (500, 500, 480)), (360, 360, 340))   # 20 units carried
                self.assertEqual(self._run(game, "age18", (1302, 1302, 0)), (360, 360, 0))     # an elder

    def test_grant_youth(self) -> None:
        for game in self.MANIFEST:
            with self.subTest(game=game):
                self.assertEqual(self._run(game, "youth", (1302, 1302, 0)), (602, 602, 0))
                self.assertEqual(self._run(game, "youth", (500, 500, 480)), (100, 100, 80))
                self.assertEqual(self._run(game, "youth", (900, 897, 0)), (200, 197, 0))

    def test_the_secret_city_and_new_believers_rows_already_moved_it(self) -> None:
        vv3 = (ROOT / "scripts/build_vv3_origins_feature.py").read_text(encoding="utf-8")
        self.assertIn("add dword ptr [edx + 0xE74], ecx", vv3)
        self.assertIn("add dword ptr [edx + 0xE8C], ecx", vv3)
        vv5 = (ROOT / "scripts/build_vv5_task9_native_actions.py").read_text(encoding="utf-8")
        body = vv5[vv5.index("def build_age("):vv5.index("def build_mastery(")]
        self.assertIn("mov dword ptr [esi+0x1C3C], eax", body)
        self.assertIn("mov dword ptr [esi+0x1C4C], eax", body)


class VillageWideRows(unittest.TestCase):
    """All Villagers are 18 in A New Home, The Secret City and The Tree of Life: the VVFPOWU payload's command 8
    (ECX = the first record, EDX = the record bound)."""

    MANIFEST = {"vv1": "vv1_origins_village_wide_upgrades.json", "vv3": "vv3_origins_village_wide_upgrades.json",
                "vv4": "vv4_origins_village_wide_upgrades.json"}

    def test_every_living_villager_moves_by_the_same_delta(self) -> None:
        for game, name in self.MANIFEST.items():
            with self.subTest(game=game):
                config = wide.CONFIG[game]
                shown, lived, mark, stride = FIELDS[game]
                self.assertEqual((config["age"], config["lived"], config["nursing"]), (shown, lived, mark))
                (patch,) = [p for p in _patches(name) if int(p["offset"], 16) == config["payload_offset"]]
                payload = bytes.fromhex(patch["after"])
                self.assertEqual(payload[:7], b"VVFPOWU")
                payload_va = config["cave_va"] + (config["payload_offset"] - config["cave_offset"])
                age_va = payload_va + config["age_code_offset"]
                uc = Uc(UC_ARCH_X86, UC_MODE_32)
                page = payload_va & ~0xFFF
                uc.mem_map(page, ((payload_va + len(payload) - page) + 0x1FFF) & ~0xFFF, UC_PROT_ALL)
                uc.mem_write(payload_va, payload)
                count = 7
                uc.mem_map(RECORDS, ((count * stride) + 0xFFF) & ~0xFFF)
                uc.mem_map(STACK - 0x10000, 0x10000)
                uc.mem_map(RETURN, 0x1000)
                active = (config["active"], config["health"])
                cases = [((148, 148, 0), (360, 360, 0)),          # a child
                         ((150, 147, 0), (360, 357, 0)),          # a tick not yet run
                         ((500, 500, 480), (360, 360, 340)),      # 20 units into a pregnancy
                         ((1302, 1302, 0), (360, 360, 0)),        # an elder
                         ((360, 355, 0), (360, 355, 0)),          # already 18
                         ((200, 200, 0), (200, 200, 0)),          # dead: untouched
                         ((1000, 990, 0), (360, 350, 0))]         # the last record
                for i, (before, _) in enumerate(cases):
                    _put(uc, RECORDS + i * stride, game, before, health=0 if i == 5 else 50, active=active)
                uc.mem_write(STACK - 0x100, struct.pack("<I", RETURN))
                uc.reg_write(UC_X86_REG_ESP, STACK - 0x100)
                uc.reg_write(UC_X86_REG_ECX, RECORDS)
                uc.reg_write(UC_X86_REG_EDX, count)
                uc.emu_start(age_va, RETURN, count=5000)
                for i, (_, after) in enumerate(cases):
                    self.assertEqual(_ages(uc, RECORDS + i * stride, game), after, f"record {i}")


class LostChildrenVillageWide(unittest.TestCase):
    """The Lost Children's All Villagers are 18 is the companion's ApplyVV2AgeToAll(record array)."""

    def test_every_living_villager_moves_by_the_same_delta(self) -> None:
        from story_emulator import Process

        exe = (ROOT / "research/stock-executables/Virtual Villagers - The Lost Children.exe").read_bytes()
        proc = Process(exe, ROOT / "assets/origins/VVFP VV2 Origins Icons.dll")
        proc.api_handlers["GetForegroundWindow"] = lambda p: (0x1234, 0)
        proc.api_handlers["IsWindow"] = lambda p: (1, 4)
        shown, lived, mark, stride = FIELDS["vv2"]
        base = proc.alloc(256 * stride)
        cases = [((148, 148, 0), (360, 360, 0)), ((500, 500, 480), (360, 360, 340)),
                 ((1302, 1302, 0), (360, 360, 0)), ((360, 355, 0), (360, 355, 0))]
        for i, (before, _) in enumerate(cases):
            r = base + i * stride
            proc.write(r + 0x30, b"\x01")
            proc.put32(r + 0x52C, 50)
            for off, value in zip((shown, lived, mark), before):
                proc.put32(r + off, value)
        self.assertEqual(proc.export("ApplyVV2AgeToAll", base), 1)
        for i, (_, after) in enumerate(cases):
            r = base + i * stride
            got = tuple(struct.unpack("<i", proc.read(r + off, 4))[0] for off in (shown, lived, mark))
            self.assertEqual(got, after, f"record {i}")
        self.assertTrue(proc.messages[-1].startswith("Set 3 Villagers to Age 18."), proc.messages[-1])


if __name__ == "__main__":
    unittest.main()
