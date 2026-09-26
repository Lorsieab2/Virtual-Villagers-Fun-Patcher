"""VV4 and VV5 log every accepted conception, on every path -- verified by running
the real conception routine from the rendered executable.

The owner's requirement: every way a villager conceives is logged --
autonomous embracing, the player dropping one villager on another, time
catch-up and island events -- in all five games.

VV4's and VV5's parentage hook used to replace ONE call to the conception
routine (the role resolver's), so only that path was logged. Each routine has
four callers: that one, the two gender branches of autonomous embracing, and
village seeding. The hook now sits at the routine's success exit, which every
accepted conception reaches and the capacity rejection never does. The routine
is the only code that writes the pregnancy fields (checked over every writer
of those offsets in the stock image), so that exit sees every path.

These tests load the patched executable -- as the patcher renders it -- into an
emulator and run the game's OWN conception routine, stubbing only the helpers
it calls (the capacity check, random rolls, a string copy, the message box).
Each case is run twice, on the stock image and on the patched one, and must end
in the same registers and the same memory: the hook adds a log call and changes
nothing else. It must log accepted conceptions once, with the mother and the
father's record; never log a rejected attempt; and never log village seeding.
"""
from __future__ import annotations

import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

try:
    import pefile
    from keystone import KS_ARCH_X86, KS_MODE_32, Ks
    from unicorn import UC_ARCH_X86, UC_MODE_32, Uc
    from unicorn.x86_const import (
        UC_X86_REG_EAX, UC_X86_REG_EBP, UC_X86_REG_EBX, UC_X86_REG_ECX,
        UC_X86_REG_EDI, UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_ESP,
    )
    HAVE_TOOLS = True
except ImportError:  # pragma: no cover - optional emulator
    HAVE_TOOLS = False

GAMES = {
    4: dict(
        exe="Virtual Villagers - The Tree of Life.exe", build="vv4",
        feature="vv4_write_parentage_log", routine=0x45E7B0,
        container=0x50E568, iat=(0x48A1D8, 0x48A1DC, 0x48A1E0),
        capacity=0x468350, ftol=0x471630, setf=0x46AD80, strcpy=0x4724E0,
        chance=0x41E1C0, rand=0x4036D0, message=0x412F90,
        stats=(0x4D6DE8, 0x4D6E08, 0x4D6E0C),
    ),
    5: dict(
        exe="Virtual Villagers - New Believers.exe", build="vv5",
        feature="vv5_write_parentage_log", routine=0x465E00,
        container=0x554148, iat=(0x4951D8, 0x4951DC, 0x4951E0),
        capacity=0x472BD0, ftol=0x47C9B0, setf=0x475730, strcpy=0x47D7C0,
        chance=0x423600, rand=0x403660, message=None,
        stats=(0x51D360, 0x51D380, 0x51D384),
    ),
}

SCRATCH = 0x0F000000          # control block and fakes
CTRL_CAPACITY = SCRATCH + 0x00
CTRL_CHANCE = SCRATCH + 0x04
CTRL_INDEX = SCRATCH + 0x08
CTRL_SEQUENCE = SCRATCH + 0x10
EXPORT_CALLS = SCRATCH + 0x40
EXPORT_ARGS = SCRATCH + 0x44
FAKE_MODULE = SCRATCH + 0x100
FAKE_PROC = SCRATCH + 0x140
FAKE_LOAD = SCRATCH + 0x180
FAKE_EXPORT = SCRATCH + 0x1C0
RETURN = SCRATCH + 0x800
VILLAGERS = 0x0E000000
MOTHER = VILLAGERS + 0x44
FATHER = VILLAGERS + 0x44 + 0x2F44 * 3
STACK_TOP = 0x10800000
NAME_OFFSET = 0x1B9C


def asm(source: str, address: int) -> bytes:
    code, _ = Ks(KS_ARCH_X86, KS_MODE_32).asm(source, address)
    return bytes(code)


def rendered(game: int) -> tuple[bytes, bytes]:
    from vv_fun_patcher import load_builds, render_patched_bytes, resolve_fun_patch_ids

    """The same mode rendered without and with the parentage log.

    The baseline is NOT the raw stock file: Immediate Fixed already patches this
    routine's twin and triplet writes (the capacity safety rows), so a raw-stock
    baseline differs for reasons that have nothing to do with the hook. Rendering
    both sides in the same mode leaves the hook as the only difference."""
    cfg = GAMES[game]
    stock = ROOT / "research/stock-executables" / cfg["exe"]
    stock.read_bytes()   # conftest turns a missing stock exe into a skip
    build = next(b for b in load_builds() if b.id == cfg["build"])
    ids = resolve_fun_patch_ids([cfg["feature"]], game_id=cfg["build"])
    baseline, _ = render_patched_bytes(stock, build, "immediate_fixed", [])
    patched, _ = render_patched_bytes(stock, build, "immediate_fixed", ids)
    return bytes(baseline), bytes(patched)


def run(game: int, image: bytes, capacity: int, flag: int, chance: int,
        sequence: list[int], father_name: int) -> dict:
    cfg = GAMES[game]
    pe = pefile.PE(data=image)
    mu = Uc(UC_ARCH_X86, UC_MODE_32)
    size = (pe.OPTIONAL_HEADER.SizeOfImage + 0xFFF) & ~0xFFF
    mu.mem_map(0x400000, size)
    mu.mem_write(0x400000, image[: pe.OPTIONAL_HEADER.SizeOfHeaders])
    for section in pe.sections:
        data = section.get_data()
        mu.mem_write(0x400000 + section.VirtualAddress, data)
    mu.mem_map(SCRATCH, 0x1000)
    mu.mem_map(VILLAGERS, 0x40000)
    mu.mem_map(STACK_TOP - 0x10000, 0x10000)

    # The helpers the routine calls, reduced to their contracts.
    mu.mem_write(cfg["capacity"], asm(f"mov eax, dword ptr [{CTRL_CAPACITY}]; ret", cfg["capacity"]))
    mu.mem_write(cfg["ftol"], asm("fstp st(0); mov eax, 50; ret", cfg["ftol"]))
    mu.mem_write(cfg["setf"], asm("ret 8", cfg["setf"]))
    mu.mem_write(cfg["strcpy"], asm("ret", cfg["strcpy"]))
    mu.mem_write(cfg["chance"], asm(f"mov eax, dword ptr [{CTRL_CHANCE}]; ret 4", cfg["chance"]))
    mu.mem_write(cfg["rand"], asm(
        f"mov eax, dword ptr [{CTRL_INDEX}]; mov eax, dword ptr [{CTRL_SEQUENCE} + eax*4];"
        f" inc dword ptr [{CTRL_INDEX}]; ret", cfg["rand"]))
    if cfg["message"]:
        mu.mem_write(cfg["message"], asm("ret 8", cfg["message"]))

    # The loader imports the trampoline resolves, and the export it calls.
    mu.mem_write(FAKE_MODULE, asm(f"mov eax, {FAKE_MODULE}; ret 4", FAKE_MODULE))
    mu.mem_write(FAKE_LOAD, asm(f"mov eax, {FAKE_MODULE}; ret 4", FAKE_LOAD))
    mu.mem_write(FAKE_PROC, asm(f"mov eax, {FAKE_EXPORT}; ret 8", FAKE_PROC))
    mu.mem_write(FAKE_EXPORT, asm(
        f"inc dword ptr [{EXPORT_CALLS}];"
        f" mov eax, [esp+4]; mov [{EXPORT_ARGS}], eax;"
        f" mov eax, [esp+8]; mov [{EXPORT_ARGS + 4}], eax;"
        f" mov eax, [esp+12]; mov [{EXPORT_ARGS + 8}], eax;"
        f" mov eax, [esp+16]; mov [{EXPORT_ARGS + 12}], eax;"
        f" mov eax, 1; ret 0x10", FAKE_EXPORT))
    module, proc, load = cfg["iat"]
    mu.mem_write(module, struct.pack("<I", FAKE_MODULE))
    mu.mem_write(proc, struct.pack("<I", FAKE_PROC))
    mu.mem_write(load, struct.pack("<I", FAKE_LOAD))

    mu.mem_write(CTRL_CAPACITY, struct.pack("<I", capacity))
    mu.mem_write(CTRL_CHANCE, struct.pack("<I", chance))
    mu.mem_write(CTRL_INDEX, struct.pack("<I", 0))
    mu.mem_write(CTRL_SEQUENCE, b"".join(struct.pack("<I", v) for v in sequence))

    # __thiscall with seven stack arguments; the fourth is the father's name.
    args = [1, 2, 3, father_name, 17, 9, flag]
    esp = STACK_TOP - 0x100
    for value in reversed(args):
        esp -= 4
        mu.mem_write(esp, struct.pack("<I", value))
    esp -= 4
    mu.mem_write(esp, struct.pack("<I", RETURN))
    mu.reg_write(UC_X86_REG_ESP, esp)
    mu.reg_write(UC_X86_REG_ECX, MOTHER)
    mu.reg_write(UC_X86_REG_EBX, 0x11111111)
    mu.reg_write(UC_X86_REG_ESI, 0x22222222)
    mu.reg_write(UC_X86_REG_EDI, 0x33333333)
    mu.reg_write(UC_X86_REG_EBP, 0x44444444)
    mu.emu_start(cfg["routine"], RETURN, count=100000)

    return {
        "regs": {name: mu.reg_read(reg) for name, reg in (
            ("eax", UC_X86_REG_EAX), ("ebx", UC_X86_REG_EBX), ("ecx", UC_X86_REG_ECX),
            ("edx", UC_X86_REG_EDX), ("esi", UC_X86_REG_ESI), ("edi", UC_X86_REG_EDI),
            ("ebp", UC_X86_REG_EBP), ("esp", UC_X86_REG_ESP))},
        "mother": bytes(mu.mem_read(MOTHER, 0x2000)),
        "stats": [struct.unpack("<I", mu.mem_read(a, 4))[0] for a in cfg["stats"]],
        "calls": struct.unpack("<I", mu.mem_read(EXPORT_CALLS, 4))[0],
        "args": struct.unpack("<4I", mu.mem_read(EXPORT_ARGS, 16)),
        "litter": struct.unpack("<I", mu.mem_read(MOTHER + 0x1C50, 4))[0],
    }


CASES = {
    #  name: (capacity ok, suppression flag, chance, rand sequence, expected litter, logged)
    "single": (1, 0, 0, [], 1, True),
    "twins": (1, 0, 3, [0, 0x30], 2, True),
    "triplets": (1, 0, 3, [0, 0], 3, True),
    "rejected at capacity": (0, 0, 0, [], 0, False),
    "village seeding": (0, 1, 0, [], 1, False),
}


@unittest.skipUnless(HAVE_TOOLS, "pefile, keystone and unicorn are needed")
class EveryConceptionPathIsLogged(unittest.TestCase):
    def test_the_patched_routine_behaves_as_stock_and_logs_accepted_conceptions(self) -> None:
        for game in GAMES:
            stock, patched = rendered(game)
            for name, (capacity, flag, chance, seq, litter, logged) in CASES.items():
                with self.subTest(game=game, case=name):
                    father_name = FATHER + NAME_OFFSET
                    before = run(game, stock, capacity, flag, chance, seq, father_name)
                    after = run(game, patched, capacity, flag, chance, seq, father_name)
                    self.assertEqual(before["litter"], litter, "the stub drives the case")
                    self.assertEqual(after["regs"], before["regs"],
                                     "the routine must return exactly as stock")
                    self.assertEqual(after["mother"], before["mother"])
                    self.assertEqual(after["stats"], before["stats"])
                    self.assertEqual(before["calls"], 0)
                    if logged:
                        self.assertEqual(after["calls"], 1, "logged exactly once")
                        self.assertEqual(
                            after["args"], (game, GAMES[game]["container"], MOTHER, FATHER),
                            "game id, container, the mother, and the father's record")
                    else:
                        self.assertEqual(after["calls"], 0, "must not be logged")

    def test_a_father_who_is_not_a_villager_is_passed_as_given(self) -> None:
        """An event father given as a string (VV4's seeding 'Joey' is one) is
        not a record; the hook passes name - 0x1B9C unchanged and the
        companion's slot check refuses it. Nothing is scanned or invented."""
        for game in GAMES:
            _, patched = rendered(game)
            with self.subTest(game=game):
                literal = 0x401000
                after = run(game, patched, 1, 0, 0, [], literal)
                self.assertEqual(after["calls"], 1)
                self.assertEqual(after["args"][3], literal - NAME_OFFSET)

    def test_the_old_call_site_is_back_to_stock(self) -> None:
        for game, site in ((4, 0x460A2E), (5, 0x467DBE)):
            stock, patched = rendered(game)
            with self.subTest(game=game):
                self.assertEqual(patched[site - 0x400000: site - 0x400000 + 5],
                                 stock[site - 0x400000: site - 0x400000 + 5])


if __name__ == "__main__":
    unittest.main()
