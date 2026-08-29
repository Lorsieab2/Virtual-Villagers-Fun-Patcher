"""Emulate VV1's manual drag-pair hook to prove it never dereferences a stale register.

This exists because the same root-cause bug shipped twice: the Birth Control
manual-pairing hook is spliced late in FUN_0043dad0 (0x43DD03), where EDI no
longer holds the candidate villager record it held earlier in the function --
by that point the stock code has reassigned it to an RNG(3)+5 duration value.

  * v1.34.10 crashed at page offset 0x22   (the age compare read [edi+0x348])
  * v1.34.11 crashed at 0x43DDE1           (the reject block reads [edi+0x344])

Byte-level pins catch a known-bad sequence, but they cannot tell you whether
some *other* path still dereferences a stale register. Emulating the real
patched bytes can. Every path out of the splice point is executed here against
a mapped, known-good villager array; any read outside the regions this test
deliberately maps is a stale-pointer dereference and fails the test.

Skipped (not failed) when the optional `unicorn` package is unavailable, so
this never becomes a hard dependency of the suite.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

try:  # optional dependency
    from unicorn import (
        UC_ARCH_X86,
        UC_HOOK_CODE,
        UC_HOOK_MEM_FETCH_UNMAPPED,
        UC_HOOK_MEM_READ_UNMAPPED,
        UC_HOOK_MEM_WRITE_UNMAPPED,
        UC_MODE_32,
        Uc,
        UcError,
    )
    from unicorn.x86_const import (
        UC_X86_REG_EAX,
        UC_X86_REG_EBP,
        UC_X86_REG_EBX,
        UC_X86_REG_EDI,
        UC_X86_REG_EIP,
        UC_X86_REG_ESI,
        UC_X86_REG_ESP,
    )

    HAVE_UNICORN = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_UNICORN = False

try:
    import pefile

    HAVE_PEFILE = True
except ImportError:  # pragma: no cover - environment dependent
    HAVE_PEFILE = False


STOCK = ROOT / "inputs" / "vv1-stock-copy" / "Virtual Villagers - A New Home.exe"

IMAGE_BASE = 0x400000
THIS = 0x10000000  # villager-record array base ("this")
STATE = 0x20000000  # game-state singleton (*(this + 0x3e010))
STACK = 0x30000000
RECORD_SIZE = 0x3D8

HOOK_ENTRY = 0x43DD03  # the manual-pairing splice point
COMMON_TAIL = 0x43DEA4  # where every path converges before returning

VV1_FUN_PATCH_IDS = (
    "vv1_visual_mods",
    "vv1_school_lessons_grant_skill",
    "vv1_continue_research_at_max_technologies",
    "vv1_f6_clothing_change_cheat",
    "vv1_magic_fruit_alters_mortality",
    "vv1_builder_action_fixes",
    "vv1_birth_control",
    "vv1_write_village_statistics",
)


def _render(mode: str) -> bytes:
    import vv_fun_patcher as patcher

    builds = {build.id: build for build in patcher.load_builds()}
    rendered, _ = patcher.render_patched_bytes(
        STOCK, builds["vv1"], mode, list(VV1_FUN_PATCH_IDS)
    )
    return bytes(rendered)


def _emulate(
    image_bytes: bytes,
    *,
    actor_index: int,
    candidate_index: int,
    actor_category: int,
    actor_age: int,
    candidate_age: int,
) -> tuple[bool, list[int]]:
    """Run one manual-pair decision. Returns (completed_ok, out_of_bounds_reads)."""
    pe = pefile.PE(data=image_bytes, fast_load=True)
    pe.parse_data_directories()
    image = pe.get_memory_mapped_image()

    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    image_size = ((len(image) + 0xFFF) & ~0xFFF) + 0x10000
    mu.mem_map(IMAGE_BASE, image_size)
    mu.mem_write(IMAGE_BASE, image)
    mu.mem_map(THIS, 0x400000)
    mu.mem_map(STATE, 0x10000)
    mu.mem_map(STACK, 0x100000)

    def wr32(addr: int, value: int) -> None:
        mu.mem_write(addr, int(value).to_bytes(4, "little"))

    actor = THIS + actor_index * RECORD_SIZE
    candidate = THIS + candidate_index * RECORD_SIZE
    wr32(actor + 0x350, actor_category)
    wr32(actor + 0x348, actor_age)
    wr32(candidate + 0x350, 3 - actor_category)
    wr32(candidate + 0x348, candidate_age)
    for record in (actor, candidate):
        wr32(record + 0x344, 100)  # positive health
        wr32(record + 0x354, 0)
        wr32(record + 0x358, 0)
    # Force the branch that dereferences the candidate record in the reject
    # block; with this byte clear the crashing path is skipped entirely.
    mu.mem_write(actor + 0x29, b"\x01")
    wr32(THIS + 0x3E010, STATE)
    mu.mem_write(STATE + 0x158, b"\x00")
    wr32(STATE + 0xA2EC, 1000)

    bad_reads: list[int] = []

    def on_unmapped(uc, access, address, size, value, user_data):  # noqa: ANN001
        bad_reads.append(address)
        return False

    mu.hook_add(
        UC_HOOK_MEM_READ_UNMAPPED
        | UC_HOOK_MEM_WRITE_UNMAPPED
        | UC_HOOK_MEM_FETCH_UNMAPPED,
        on_unmapped,
    )

    def skip_calls(uc, address, size, user_data):  # noqa: ANN001
        # Stub every call: this test exercises branch/pointer logic, not the
        # callees (message boxes, population counts, action resets).
        if uc.mem_read(address, 1)[0] == 0xE8:
            uc.reg_write(UC_X86_REG_EIP, address + size)
            uc.reg_write(UC_X86_REG_EAX, 10)

    mu.hook_add(UC_HOOK_CODE, skip_calls)

    mu.reg_write(UC_X86_REG_ESI, THIS)
    mu.reg_write(UC_X86_REG_EBP, actor)
    mu.reg_write(UC_X86_REG_EBX, candidate_index)
    # The stale value: by the splice point EDI is the RNG(3)+5 embrace
    # duration, NOT the candidate record pointer it held earlier.
    mu.reg_write(UC_X86_REG_EDI, 6)
    mu.reg_write(UC_X86_REG_ESP, STACK + 0x80000)
    wr32(STACK + 0x80000 + 0x20, actor_index)
    # FUN_0043DAD0 saved record pointers in its stack frame earlier in the
    # function; the carrier (category-2) accept block at 0x43DD0E reads one of
    # them from [esp+0x1C] and dereferences [rec+0x36C]. Point it at a mapped
    # record so the stock read resolves. (The old buggy control flow mis-routed
    # carriers to the non-carrier block at 0x43DD5E -- which reads [ebp+0x36C]
    # instead -- so this local was never exercised until the stack-balance fix
    # restored the correct 0x43DD0E path.)
    wr32(STACK + 0x80000 + 0x18, candidate)

    completed = True
    try:
        mu.emu_start(HOOK_ENTRY, COMMON_TAIL, count=4000)
    except UcError:
        completed = False
    return completed, bad_reads


@unittest.skipUnless(HAVE_UNICORN and HAVE_PEFILE, "requires unicorn and pefile")
@unittest.skipUnless(STOCK.exists(), "requires the exact-build VV1 stock executable")
class VV1BirthControlManualPairEmulationTests(unittest.TestCase):
    # (label, actor_category, actor_age, candidate_age)
    CASES = (
        ("carrier actor over 50 -> reject", 2, 1200, 400),
        ("non-carrier actor, candidate over 50 -> reject", 1, 400, 1200),
        ("non-carrier actor, both eligible -> accept", 1, 400, 400),
        ("carrier actor, both eligible -> accept", 2, 400, 400),
    )

    def test_no_path_dereferences_a_stale_register(self) -> None:
        for mode in ("stock", "collection_progression", "immediate_fixed"):
            image = _render(mode)
            for label, category, actor_age, candidate_age in self.CASES:
                with self.subTest(mode=mode, case=label):
                    completed, bad_reads = _emulate(
                        image,
                        actor_index=3,
                        candidate_index=7,
                        actor_category=category,
                        actor_age=actor_age,
                        candidate_age=candidate_age,
                    )
                    self.assertEqual(
                        bad_reads,
                        [],
                        f"{mode}/{label}: dereferenced unmapped address(es) "
                        f"{[hex(a) for a in bad_reads]} -- a stale register is "
                        f"being used as a pointer",
                    )
                    self.assertTrue(
                        completed,
                        f"{mode}/{label}: did not reach the function's common tail",
                    )


if __name__ == "__main__":
    unittest.main()
