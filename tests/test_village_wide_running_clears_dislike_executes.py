"""Village-wide "All Villagers Like Running", RUN from each game's render.

Every game's manifest says Running "removes any Running Dislike whether or not
a Like was added (so full-Like villagers still have a Running Dislike cleared
for free)", per the OFFICIAL Origins Upgrade Prompts spreadsheet. VV2, VV3 and
VV5 used to skip the Dislike scan for a villager whose Like slots were all
full: the villager kept the Dislike and ECX reported nothing removed, while the
VV3 companion's dry run had already told the player it would be removed.

Each game's optional payload is rendered by the patcher and entered at its own
entry with EAX = 6, ECX = the first record and EDX = the record count. VV4 and
VV5 call the game's own Like/Dislike helpers, so those run from the rendered
image as well. The field offsets are pinned here independently of the
generator (scripts/build_village_wide_origins_features.py).

Counts: EDX = already-Running skips, ECX = Running Dislikes removed. EAX is the
full-Like skip count in every game except VV4, whose native-helper branch
returns villagers granted Running there (its base payload passes EAX to the
companion as "granted"). VV1 and VV2 also store the granted count in the
scratch dword at entry + 0x30, which their base payloads pass to the result
dialog.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

import pefile
from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX, UC_X86_REG_EDI,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import vv_fun_patcher as vfp  # noqa: E402

STOCK = ROOT / "research" / "stock-executables"
RUNNING = 38
RECORDS = 0x20000000
RETURN = 0x0F000800
STACK_TOP = 0x10800000
KEPT = dict(ebx=UC_X86_REG_EBX, esi=UC_X86_REG_ESI, edi=UC_X86_REG_EDI, ebp=UC_X86_REG_EBP)

# exe, entry VA, stride, active, health, likes, dislikes, slots,
# EAX meaning ("full" or "granted"), granted scratch dword (or None)
GAMES = {
    "vv1": ("Virtual Villagers - A New Home.exe", 0x48D1A0, 0x3D8, 0x28, 0x344, 0x398, 0x3A8, 4, "full", 0x48D1D0),
    "vv2": ("Virtual Villagers - The Lost Children.exe", 0x49C820, 0xE48C, 0x30, 0x52C, 0x5F0, 0x6E8, 62, "full", 0x49C850),
    "vv3": ("Virtual Villagers - The Secret City.exe", 0x47B840, 0x1F8C, 0xF10, 0xE78, 0xFB4, 0xFC0, 3, "full", None),
    "vv4": ("Virtual Villagers - The Tree of Life.exe", 0x728240, 0x2E3C, 0x1CC4, 0x1C40, 0x1E60, 0x1E6C, 3, "granted", None),
    "vv5": ("Virtual Villagers - New Believers.exe", 0x494C40, 0x2F44, 0x1CD4, 0x1C40, 8028, 8040, 3, "full", None),
}

_RENDERS: dict[str, bytes] = {}


def _render(game: str) -> bytes:
    if game not in _RENDERS:
        feature = f"{game}_origins_village_wide_upgrades"
        exe = STOCK / GAMES[game][0]
        build = next(b for b in vfp.load_builds() if b.id == game)
        ids = vfp.resolve_fun_patch_ids([feature], game_id=game)
        rendered, applied = vfp.render_patched_bytes(exe, build, "immediate_fixed", ids)
        assert f"feature:{feature}" in {r["owner"] for r in applied}
        _RENDERS[game] = bytes(rendered)
    return _RENDERS[game]


def _full(slots: int) -> list[int]:
    # Distinct, non-Running Likes filling every slot.
    return [100 + i for i in range(slots)]


def _run(game: str, villagers: list[tuple[list[int], list[int]]]) -> tuple[dict, list]:
    _, entry, stride, active, health, likes, dislikes, slots, _, granted_va = GAMES[game]
    image = _render(game)
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    mu.mem_map(0x400000, (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF)
    mu.mem_write(0x400000, image[:pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        mu.mem_write(0x400000 + section.VirtualAddress, section.get_data())
    mu.mem_map(RETURN & ~0xFFF, 0x1000)
    mu.mem_map(RECORDS, (len(villagers) * stride + 0xFFFF) & ~0xFFFF)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)
    mu.mem_write(RETURN, b"\xF4")
    if granted_va is not None:
        mu.mem_write(granted_va, struct.pack("<I", 0xDEADBEEF))
    pad = lambda values: list(values) + [-1] * (slots - len(values))  # noqa: E731
    for i, (like_values, dislike_values) in enumerate(villagers):
        base = RECORDS + i * stride
        mu.mem_write(base + active, b"\x01")
        mu.mem_write(base + health, struct.pack("<i", 50))
        mu.mem_write(base + likes, struct.pack(f"<{slots}i", *pad(like_values)))
        mu.mem_write(base + dislikes, struct.pack(f"<{slots}i", *pad(dislike_values)))
    esp = STACK_TOP - 0x100
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    sentinels = dict(ebx=0x11111111, esi=0x22222222, edi=0x33333333, ebp=0x44444444)
    for name, value in sentinels.items():
        mu.reg_write(KEPT[name], value)
    mu.reg_write(UC_X86_REG_EAX, 6)
    mu.reg_write(UC_X86_REG_ECX, RECORDS)
    mu.reg_write(UC_X86_REG_EDX, len(villagers))
    mu.emu_start(entry, RETURN, count=500000)
    regs = {n: mu.reg_read(r) for n, r in (("eax", UC_X86_REG_EAX), ("edx", UC_X86_REG_EDX), ("ecx", UC_X86_REG_ECX))}
    if granted_va is not None:
        regs["granted"] = struct.unpack("<I", mu.mem_read(granted_va, 4))[0]
    regs["kept"] = {n: mu.reg_read(r) for n, r in KEPT.items()} == sentinels
    regs["esp"] = mu.reg_read(UC_X86_REG_ESP) - esp
    after = []
    for i in range(len(villagers)):
        base = RECORDS + i * stride
        after.append((list(struct.unpack(f"<{slots}i", mu.mem_read(base + likes, 4 * slots))),
                      list(struct.unpack(f"<{slots}i", mu.mem_read(base + dislikes, 4 * slots)))))
    return regs, after


class VillageWideRunningClearsDislikeExecutes(unittest.TestCase):
    def _expect(self, game, villagers, expected, full, granted, already, removed):
        slots = GAMES[game][7]
        regs, after = _run(game, villagers)
        pad = lambda values: list(values) + [-1] * (slots - len(values))  # noqa: E731
        for i, (like_values, dislike_values) in enumerate(expected):
            with self.subTest(game=game, villager=i):
                self.assertEqual(after[i], (pad(like_values), pad(dislike_values)))
        eax = full if GAMES[game][8] == "full" else granted
        self.assertEqual(regs["eax"], eax, f"{game} EAX")
        self.assertEqual(regs["edx"], already, f"{game} EDX already-Running skips")
        self.assertEqual(regs["ecx"], removed, f"{game} ECX Running Dislikes removed")
        if "granted" in regs:
            self.assertEqual(regs["granted"], granted, f"{game} granted scratch dword")
        self.assertTrue(regs["kept"], f"{game} must preserve EBX/ESI/EDI/EBP")
        self.assertEqual(regs["esp"], 4, f"{game} near ret")

    def test_full_like_villager_loses_a_running_dislike(self):
        for game in GAMES:
            full = _full(GAMES[game][7])
            with self.subTest(game=game):
                self._expect(game, [(full, [RUNNING])], [(full, [])],
                             full=1, granted=0, already=0, removed=1)

    def test_full_like_villager_running_dislike_in_a_later_slot(self):
        for game in GAMES:
            full = _full(GAMES[game][7])
            with self.subTest(game=game):
                self._expect(game, [(full, [7, RUNNING])], [(full, [7, -1])],
                             full=1, granted=0, already=0, removed=1)

    def test_full_like_villager_without_a_running_dislike_is_untouched(self):
        for game in GAMES:
            full = _full(GAMES[game][7])
            with self.subTest(game=game):
                self._expect(game, [(full, [7, RUNNING - 1])], [(full, [7, RUNNING - 1])],
                             full=1, granted=0, already=0, removed=0)

    def test_villager_with_a_free_slot_gains_running_and_loses_the_dislike(self):
        for game in GAMES:
            with self.subTest(game=game):
                self._expect(game, [([5], [RUNNING, 9])], [([5, RUNNING], [-1, 9])],
                             full=0, granted=1, already=0, removed=1)
                self._expect(game, [([5], [9])], [([5, RUNNING], [9])],
                             full=0, granted=1, already=0, removed=0)

    def test_already_running_villager_is_unchanged(self):
        for game in GAMES:
            with self.subTest(game=game):
                self._expect(game, [([5, RUNNING], [9])], [([5, RUNNING], [9])],
                             full=0, granted=0, already=1, removed=0)

    def test_mixed_village_counts(self):
        for game in GAMES:
            full = _full(GAMES[game][7])
            village = [
                (full, [RUNNING]),          # full Likes, Dislike cleared
                (full, [4]),                # full Likes, nothing to clear
                ([], [RUNNING]),            # granted, Dislike cleared
                ([3, RUNNING], []),         # already Running
                ([RUNNING - 1], [6]),       # Swimming is not Running: granted
            ]
            expected = [
                (full, []),
                (full, [4]),
                ([RUNNING], []),
                ([3, RUNNING], []),
                ([RUNNING - 1, RUNNING], [6]),
            ]
            with self.subTest(game=game):
                self._expect(game, village, expected, full=2, granted=2, already=1, removed=2)


if __name__ == "__main__":
    unittest.main()
