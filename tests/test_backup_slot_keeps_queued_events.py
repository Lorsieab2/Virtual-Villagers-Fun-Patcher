"""A save's backup generation is not another village: a bought Barrel survives every save.

Every save writes the slot's backup too: the game builds the path of slot N + 20
(and N + 40 when the backup is itself rotated) through the same "%s%d.ldw"
builder the patcher's slot stub detours.  The Lost Children's stub took 23 for a
village change, so every autosave (600 s), quit save, Change Tribe and load
cleared a bought, not yet delivered Barrel O' Babies -- the 75,000 tech points
stayed spent and the babies never came (v1.35.66, proved by emulation of the
patched executable).  The other games' stubs take slots 1..5 only.

This runs each game's RENDERED slot stub under emulation with the queued-event
state set, through the sequence a save makes (N, N + 20, N + 40, N) and then a
real change of village.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

try:
    from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
    from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_ESP
except ImportError:  # pragma: no cover
    Uc = None

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

STOCK = {
    "vv1": ROOT / "inputs/vv1-stock-copy/Virtual Villagers - A New Home.exe",
    "vv2": ROOT / "inputs/vv2-stock-copy/Virtual Villagers - The Lost Children.exe",
    "vv3": ROOT / "inputs/vv3-stock-copy/Virtual Villagers - The Secret City.exe",
    "vv4": ROOT / "inputs/vv4-stock-copy/Virtual Villagers - The Tree of Life.exe",
}
# The save-path builder each stub detours, and the queued-event state it clears.
CASES = {
    "vv1": (0x402ED0, (0x48D700, 0x48D704)),
    "vv2": (0x403160, (0x49C700, 0x49C708)),
    "vv3": (0x403290, (0x6E0058,)),
}
VV4_SLOT_CAVE = 0x728FD0       # entered for every save with the slot as its argument
VV4_QUEUED = (0x728B00, 0x728B04)
RETURN = 0xDEAD0000


def _render(game):
    from src.vv_fun_patcher import load_builds, render_patched_bytes
    build = next(b for b in load_builds() if b.id == game)
    image, _ = render_patched_bytes(STOCK[game], build, "immediate_fixed",
                                    [f"{game}_enable_origins_exclusive_features",
                                     f"{game}_origins_village_wide_upgrades"])
    return bytes(image)


def _emulator(image):
    pe = struct.unpack_from("<I", image, 0x3C)[0]
    count = struct.unpack_from("<H", image, pe + 6)[0]
    opt = struct.unpack_from("<H", image, pe + 20)[0]
    size_of_image = struct.unpack_from("<I", image, pe + 24 + 56)[0]
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (size_of_image + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:0x1000])
    for i in range(count):
        e = pe + 24 + opt + i * 40
        va = 0x400000 + struct.unpack_from("<I", image, e + 12)[0]
        raw_size = struct.unpack_from("<I", image, e + 16)[0]
        raw = struct.unpack_from("<I", image, e + 20)[0]
        mu.mem_write(va, image[raw:raw + raw_size])
    mu.mem_map(0x10000000, 0x100000)
    return mu


def _call(mu, entry, slot, stops):
    def hook(uc, address, size, user):
        if address in stops:
            uc.emu_stop()
    handle = mu.hook_add(UC_HOOK_CODE, hook)
    esp = 0x10080000
    mu.mem_write(esp, struct.pack("<II", RETURN, slot))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, 0x10010000)
    mu.reg_write(UC_X86_REG_EAX, slot)
    mu.emu_start(entry, RETURN, count=4000)
    mu.hook_del(handle)


def _values(mu, addresses):
    return [struct.unpack("<I", bytes(mu.mem_read(a, 4)))[0] & (0xFF if i == 0 else 0xFFFFFFFF)
            for i, a in enumerate(addresses)]


@unittest.skipIf(Uc is None, "unicorn is not installed")
class BackupSlotKeepsQueuedEvents(unittest.TestCase):
    def _run_sequence(self, mu, entry, stops, queued):
        seen = []
        for slot in (3, 3, 23, 43, 23, 3):
            mu.mem_write(queued[0], b"\x02")
            for address in queued[1:]:
                mu.mem_write(address, struct.pack("<I", 40))
            _call(mu, entry, slot, stops)
            seen.append((slot, _values(mu, queued)))
        kept = [v for v in seen[1:]]
        mu.mem_write(queued[0], b"\x02")
        _call(mu, entry, 4, stops)                 # a real change of village
        return seen[0], kept, _values(mu, queued)

    def test_every_save_keeps_the_queued_barrel_and_a_change_of_village_clears_it(self):
        for game, (detour, queued) in CASES.items():
            with self.subTest(game=game):
                if not STOCK[game].is_file():
                    self.skipTest(f"no stock {game} executable")
                mu = _emulator(_render(game))
                op = bytes(mu.mem_read(detour, 5))
                self.assertEqual(op[0], 0xE9, "the save-path builder is not detoured")
                entry = detour + 5 + struct.unpack("<i", op[1:5])[0]
                stops = {detour + n for n in range(5, 9)}
                _first, kept, changed = self._run_sequence(mu, entry, stops, queued)
                for slot, values in kept:
                    self.assertEqual(values[0], 2, f"{game}: saving slot {slot} cleared the queued Barrel")
                self.assertEqual(changed[0], 0, f"{game}: a change of village no longer clears it")

    def test_the_tree_of_life_gates_its_slot_cave_to_village_slots(self):
        if not STOCK["vv4"].is_file():
            self.skipTest("no stock vv4 executable")
        mu = _emulator(_render("vv4"))
        _first, kept, changed = self._run_sequence(mu, VV4_SLOT_CAVE, {0x403676}, VV4_QUEUED)
        for slot, values in kept:
            self.assertEqual(values[0], 2, f"vv4: saving slot {slot} cleared the purchased Barrel")
        self.assertEqual(changed[0], 0)


if __name__ == "__main__":
    unittest.main()
