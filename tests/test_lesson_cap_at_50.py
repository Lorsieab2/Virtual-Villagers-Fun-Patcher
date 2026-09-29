"""Lessons stop at 50 (A New Home, The Lost Children): the callback bodies,
RUN in an emulator over a villager record.

The owner: going to school (VV1) and attending lessons (VV2) limit skill
gain to exactly 50, and a lesson picks only among the skills still below 50
(option b), as The Tree of Life's and New Believers' Nursery Schools skip any
skill at 50 or above.

The bytes under test are the ones the manifest ships (data/builds.json),
placed at their cave addresses, with the games' RNG at its stock address
replaced by a scripted one so every branch can be forced:

  * every skill below 50: exactly one gains 7..9, the RNG is asked for
    one of five;
  * a skill at 49 gains and stops at exactly 50;
  * a Master (100) and a skill at 50 are never chosen and never lowered:
    the RNG is asked for one of the skills still below 50 only;
  * all five at 50 or above: nothing changes and the RNG is not consulted;
  * every other callback id reaches the stock dispatcher with the displaced
    prologue replayed (VV2's callback 126 still heals one point, capped).
"""
from __future__ import annotations

import json
import struct
import sys
import unittest
from pathlib import Path

from unicorn import UC_ARCH_X86, UC_HOOK_CODE, UC_MODE_32, Uc
from unicorn.x86_const import (
    UC_X86_REG_EAX, UC_X86_REG_ECX, UC_X86_REG_EIP, UC_X86_REG_ESP,
)

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
BUILDS = json.loads((ROOT / "data" / "builds.json").read_text(encoding="utf-8"))

ARRAY = 0x50000000
STACK = 0x70000000
RETURN = 0x7F000000
CAP = 50

GAMES = {
    "vv1": dict(cave=0x4566C1, file="0x566C1", rng=0x402F10, stride=0x3D8,
                skills=0x3BC, resume=0x43A235, feature="vv1_school_lessons_grant_skill"),
    "vv2": dict(cave=0x473F50, file="0x73F50", rng=0x4031A0, stride=0xE48C,
                skills=0x7E4, resume=0x461B15, health=0x52C, feature=None),
}


def _body(game: str) -> bytes:
    g = GAMES[game]
    if g["feature"]:
        rows = [f for f in BUILDS["fun_patches"] if f["id"] == g["feature"]]
    else:
        rows = [s for s in BUILDS["fun_patch_support"] if s["game_id"] == game]
    (row,) = rows
    (patch,) = [p for p in row["patches"] if p["offset"] == g["file"]]
    assert patch["before"] == "00" * (len(patch["after"]) // 2), "a cave: written over zeros"
    return bytes.fromhex(patch["after"])


class Run:
    """One callback call: ecx = the villager array, args (index, callback)."""

    def __init__(self, game: str, index: int, callback: int, skills: list[int],
                 rng: list[int], health: int = 0):
        g = GAMES[game]
        self.g = g
        self.rng_calls: list[int] = []
        self.rng = list(rng)
        mu = Uc(UC_ARCH_X86, UC_MODE_32)
        page = g["cave"] & ~0xFFF
        mu.mem_map(page, 0x2000)
        mu.mem_write(g["cave"], _body(game))
        mu.mem_map(g["rng"] & ~0xFFF, 0x1000)
        mu.mem_map(g["resume"] & ~0xFFF, 0x1000)
        # A ret at each stand-in address ends the translation block there, so
        # the emulator never decodes a page of zeros into the next page.
        mu.mem_write(g["rng"], b"\xC3")
        mu.mem_write(g["resume"], b"\xC3")
        mu.mem_map(ARRAY, 0x100000)
        mu.mem_map(STACK - 0x10000, 0x20000)
        mu.mem_map(RETURN & ~0xFFF, 0x1000)
        record = ARRAY + index * g["stride"]
        mu.mem_write(record + g["skills"], struct.pack("<5i", *skills))
        if "health" in g:
            mu.mem_write(record + g["health"], struct.pack("<i", health))
        esp = STACK - 0x100
        mu.mem_write(esp, struct.pack("<3I", RETURN, index, callback))
        mu.reg_write(UC_X86_REG_ESP, esp)
        mu.reg_write(UC_X86_REG_ECX, ARRAY)
        mu.hook_add(UC_HOOK_CODE, self._hook)
        self.mu = mu
        self.record = record
        self.stopped_at = None
        try:
            mu.emu_start(g["cave"], RETURN, count=10000)
        except Exception:
            pass
        self.eip = mu.reg_read(UC_X86_REG_EIP)
        if self.stopped_at is None and self.eip == RETURN:
            self.stopped_at = RETURN   # emu_start's `until` stops before the hook runs

    def _hook(self, mu, address, size, user_data):
        g = self.g
        if address == g["rng"]:
            esp = mu.reg_read(UC_X86_REG_ESP)
            bound = struct.unpack("<I", mu.mem_read(esp + 4, 4))[0]
            self.rng_calls.append(bound)
            value = self.rng.pop(0) if self.rng else 0
            assert 0 <= value < bound, (value, bound)
            mu.reg_write(UC_X86_REG_EAX, value)
            ret = struct.unpack("<I", mu.mem_read(esp, 4))[0]
            mu.reg_write(UC_X86_REG_ESP, esp + 4)
            mu.reg_write(UC_X86_REG_EIP, ret)
        elif address == g["resume"] or address == RETURN:
            self.stopped_at = address
            mu.emu_stop()

    def skills(self) -> list[int]:
        return list(struct.unpack("<5i", self.mu.mem_read(self.record + self.g["skills"], 20)))

    def health(self) -> int:
        return struct.unpack("<i", self.mu.mem_read(self.record + self.g["health"], 4))[0]


class LessonCapTests(unittest.TestCase):
    def check_award(self, game: str):
        # Every skill below 50: one of five, 7..9 points.
        for pick, extra in ((0, 0), (4, 2), (2, 1)):
            r = Run(game, 3, 127, [10, 20, 30, 40, 0], rng=[pick, extra])
            self.assertEqual(r.stopped_at, RETURN, "callback 127 returns to the runner")
            self.assertEqual(r.rng_calls, [5, 3])
            expected = [10, 20, 30, 40, 0]
            expected[pick] += 7 + extra
            self.assertEqual(r.skills(), expected)

    def check_stops_at_exactly_50(self, game: str):
        for start, extra in ((49, 0), (49, 2), (43, 0), (43, 2), (41, 2), (42, 1)):
            r = Run(game, 0, 127, [start, 0, 0, 0, 0], rng=[0, extra])
            self.assertEqual(r.skills()[0], min(CAP, start + 7 + extra), (start, extra))
        r = Run(game, 0, 127, [41, 0, 0, 0, 0], rng=[0, 1])
        self.assertEqual(r.skills()[0], 49, "41 + 8 stays under the cap")

    def check_only_skills_below_50_are_chosen(self, game: str):
        # Skills 0 (a Master) and 2 (exactly 50) are out; the RNG is asked
        # for one of the three left, and the k-th eligible is the k-th of
        # those three in record order.
        for k, index in ((0, 1), (1, 3), (2, 4)):
            r = Run(game, 7, 127, [100, 12, 50, 33, 49], rng=[k, 1])
            self.assertEqual(r.rng_calls, [3, 3], "RNG(3) picks among the three below 50")
            expected = [100, 12, 50, 33, 49]
            expected[index] = min(CAP, expected[index] + 8)
            self.assertEqual(r.skills(), expected, k)
        # A skill above 50 is never lowered.
        r = Run(game, 7, 127, [100, 60, 50, 51, 99], rng=[])
        self.assertEqual(r.skills(), [100, 60, 50, 51, 99])
        self.assertEqual(r.rng_calls, [], "no eligible skill: the RNG is not consulted")

    def check_all_at_50_awards_nothing(self, game: str):
        r = Run(game, 1, 127, [50, 50, 50, 50, 50], rng=[])
        self.assertEqual(r.skills(), [50] * 5)
        self.assertEqual(r.rng_calls, [])
        self.assertEqual(r.stopped_at, RETURN)

    def check_stock_callbacks_pass_through(self, game: str):
        g = GAMES[game]
        for callback in (0, 1, 42, 126 if game == "vv1" else 125, 128, 200):
            r = Run(game, 2, callback, [1, 2, 3, 4, 5], rng=[])
            self.assertEqual(r.stopped_at, g["resume"], callback)
            self.assertEqual(r.skills(), [1, 2, 3, 4, 5])
            self.assertEqual(r.rng_calls, [])
            eax = r.mu.reg_read(UC_X86_REG_EAX)
            esp = r.mu.reg_read(UC_X86_REG_ESP)
            if game == "vv1":
                # displaced: mov eax, [esp+8]; dec eax
                self.assertEqual(eax, (callback - 1) & 0xFFFFFFFF)
                self.assertEqual(esp, STACK - 0x100)
            else:
                # displaced: push ecx; mov eax, [esp+0xC]
                self.assertEqual(eax, callback)
                self.assertEqual(esp, STACK - 0x104)
                self.assertEqual(struct.unpack("<I", r.mu.mem_read(esp, 4))[0], ARRAY)

    def test_vv1_school_lessons(self):
        for check in (self.check_award, self.check_stops_at_exactly_50,
                      self.check_only_skills_below_50_are_chosen,
                      self.check_all_at_50_awards_nothing, self.check_stock_callbacks_pass_through):
            with self.subTest(check=check.__name__):
                check("vv1")

    def test_vv2_attending_lessons(self):
        for check in (self.check_award, self.check_stops_at_exactly_50,
                      self.check_only_skills_below_50_are_chosen,
                      self.check_all_at_50_awards_nothing, self.check_stock_callbacks_pass_through):
            with self.subTest(check=check.__name__):
                check("vv2")

    def test_vv2_hospital_recovery_callback_126_is_unchanged(self):
        for health, expected in ((0, 1), (98, 99), (99, 100), (100, 100), (150, 150)):
            r = Run("vv2", 5, 126, [1, 2, 3, 4, 5], rng=[], health=health)
            self.assertEqual(r.stopped_at, RETURN)
            self.assertEqual(r.health(), expected, health)
            self.assertEqual(r.skills(), [1, 2, 3, 4, 5])

    def test_the_manifest_bytes_are_what_the_generator_assembles(self):
        import build_lesson_cap_bodies as gen
        code = gen.bodies()
        self.assertEqual(_body("vv1"), code["vv1"])
        self.assertEqual(_body("vv2"), code["vv2"])
        self.assertLessEqual(len(code["vv1"]), 0x6F, "before Write Village Statistics' wrapper at 0x56730")
        self.assertLessEqual(len(code["vv2"]), 0x9D, "before Write Village Statistics' skeleton wrapper at 0x73FED")


if __name__ == "__main__":
    unittest.main()
